from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from app.core.animator import motion_offset
from app.core.compositor import composite_animated_layers
from app.core.depth import ensure_depth_map
from app.core.layer import Layer

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def is_cuda_available() -> bool:
    """Check if PyTorch with CUDA acceleration is available."""
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False


@lru_cache(maxsize=1)
def is_nvenc_available() -> bool:
    """Check if FFmpeg with NVIDIA NVENC hardware encoder is available."""
    ffmpeg_exe = shutil.which("ffmpeg")
    if not ffmpeg_exe:
        return False
    try:
        res = subprocess.run(
            [ffmpeg_exe, "-encoders"],
            capture_output=True,
            text=True,
            check=False,
        )
        return "h264_nvenc" in res.stdout
    except Exception:
        return False


def _cuda_can_render(layers: Sequence[Layer]) -> str:
    """Return "" if the GPU path reproduces the CPU compositor for these layers.

    The GPU path composites every layer full-frame, so per-layer placement
    (scale / x_offset / y_offset) and mixed layer sizes are not reproduced.
    Rather than export something that silently differs from the preview,
    those projects stay on the CPU path.
    """
    visible = [layer for layer in layers if layer.visible and not layer.image.isNull()]
    if not visible:
        return "no visible layers"
    for layer in visible:
        if layer.scale != 1.0:
            return f"layer '{layer.name}' is scaled"
        if layer.x_offset or layer.y_offset:
            return f"layer '{layer.name}' is offset"
    sizes = {(layer.image.width(), layer.image.height()) for layer in visible}
    if len(sizes) > 1:
        return "layers have differing sizes"
    return ""


def _qimage_to_rgba(image: QImage) -> np.ndarray:
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    h, w = rgba.height(), rgba.width()
    arr = np.frombuffer(rgba.bits(), dtype=np.uint8).reshape((h, w, 4))
    return arr.copy()


def _qimage_to_rgb(image: QImage) -> np.ndarray:
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    h, w = rgba.height(), rgba.width()
    arr = np.frombuffer(rgba.bits(), dtype=np.uint8).reshape((h, w, 4)).copy()
    return arr[:, :, :3]


def _even_dims(arr: np.ndarray) -> np.ndarray:
    """Crop to even dimensions required by H.264."""
    h, w = arr.shape[:2]
    return arr[: h & ~1, : w & ~1]


def render_frames_cuda(
    layers: Sequence[Layer],
    duration: float,
    fps: int,
    scale: float = 1.0,
    loop_type: str = "Seamless Loop",
    global_intensity: float = 0.75,
    focus_depth: float = 0.5,
    progress_cb: Callable[[int, int], None] | None = None,
    cancelled_cb: Callable[[], bool] | None = None,
) -> list[np.ndarray]:
    """Accelerated rendering of animation frames using PyTorch on CUDA."""
    import torch
    import torch.nn.functional as F

    visible_layers = [layer for layer in layers if layer.visible and not layer.image.isNull()]
    if not visible_layers:
        return []

    orig_w = max(layer.image.width() for layer in visible_layers)
    orig_h = max(layer.image.height() for layer in visible_layers)
    if orig_w <= 0 or orig_h <= 0:
        return []

    # Matches the CPU path: scale to the requested size and leave the even-size
    # cropping H.264 needs to export_mp4, so both backends return identical dims.
    target_w = max(1, int(orig_w * scale))
    target_h = max(1, int(orig_h * scale))

    total = max(1, int(round(duration * fps)))
    device = torch.device("cuda:0")

    # Composite at source resolution and downscale afterwards, exactly like the
    # CPU path: sampling straight to a smaller grid would alias.
    yy, xx = torch.meshgrid(
        torch.linspace(-1.0, 1.0, orig_h, device=device, dtype=torch.float32),
        torch.linspace(-1.0, 1.0, orig_w, device=device, dtype=torch.float32),
        indexing="ij",
    )

    amplitude = max(60.0, max(orig_w, orig_h) * 0.06)
    gpu_layers = []
    for layer in visible_layers:
        rgba = _qimage_to_rgba(layer.image)
        lh, lw = rgba.shape[:2]
        img_t = torch.from_numpy(rgba).permute(2, 0, 1).unsqueeze(0).float().to(device)

        depth = ensure_depth_map(layer)
        # Depth modulates the sampling grid per pixel, so it has to match the
        # grid's resolution.
        if depth.shape != (orig_h, orig_w):
            depth = cv2.resize(depth, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
        depth_t = torch.from_numpy(np.ascontiguousarray(depth)).float().to(device)

        gpu_layers.append({
            "layer": layer,
            "img_t": img_t,
            "depth_t": depth_t,
            "lw": lw,
            "lh": lh,
        })

    frames: list[np.ndarray] = []
    for i in range(total):
        if cancelled_cb and cancelled_cb():
            return []

        phase = i / total
        comp_t = torch.zeros((3, orig_h, orig_w), device=device, dtype=torch.float32)

        for item in gpu_layers:
            layer = item["layer"]
            img_t = item["img_t"]
            depth_t = item["depth_t"]

            intensity = max(0.0, layer.intensity * global_intensity)
            m_strength = max(0.0, layer.movement_strength)
            dx, dy, zoom = motion_offset(
                layer.motion_scale_x,
                layer.motion_scale_y,
                phase,
                amplitude=amplitude * m_strength,
                zoom_strength=layer.zoom_strength,
                loop_type=loop_type,
            )

            depth_f = layer.focus_depth if layer.focus_depth is not None else focus_depth
            focus = max(0.0, min(1.0, depth_f))
            influence_t = (depth_t - focus) * 2.0

            eff_dx = dx * intensity
            eff_dy = dy * intensity
            eff_zoom = zoom * intensity

            # dx/dy are in source-image pixels (the CPU path displaces at source
            # resolution, then downscales). Normalise against the source size so
            # motion is identical at every export resolution.
            norm_dx = eff_dx * 2.0 / item["lw"]
            norm_dy = eff_dy * 2.0 / item["lh"]

            grid_x = xx - (norm_dx + xx * eff_zoom) * influence_t
            grid_y = yy - (norm_dy + yy * eff_zoom) * influence_t
            grid = torch.stack([grid_x, grid_y], dim=-1).unsqueeze(0)

            # "border" matches cv2.BORDER_REPLICATE used by the CPU/preview path.
            disp_t = F.grid_sample(
                img_t, grid, mode="bilinear", padding_mode="border", align_corners=True
            )
            disp_t = disp_t.squeeze(0)

            alpha = (disp_t[3:4, :, :] / 255.0) * max(0.0, min(1.0, layer.opacity))
            comp_t = comp_t * (1.0 - alpha) + disp_t[:3, :, :] * alpha

        if (orig_h, orig_w) != (target_h, target_w):
            comp_t = F.interpolate(
                comp_t.unsqueeze(0),
                size=(target_h, target_w),
                mode="bilinear",
                align_corners=False,
                antialias=True,
            ).squeeze(0)

        frame_rgb = torch.clamp(comp_t, 0, 255).permute(1, 2, 0).byte().cpu().numpy()
        frames.append(frame_rgb)

        if progress_cb:
            progress_cb(i + 1, total)

    del gpu_layers
    torch.cuda.empty_cache()
    return frames


def render_frames(
    layers: Sequence[Layer],
    duration: float,
    fps: int,
    scale: float = 1.0,
    loop_type: str = "Seamless Loop",
    global_intensity: float = 0.75,
    focus_depth: float = 0.5,
    progress_cb: Callable[[int, int], None] | None = None,
    cancelled_cb: Callable[[], bool] | None = None,
    backend_cb: Callable[[str], None] | None = None,
    use_gpu: bool = False,
) -> list[np.ndarray]:
    """Render animation frames as a list of RGB uint8 numpy arrays.

    Uses the CUDA path only when `use_gpu` is set (Settings > Hardware
    acceleration), PyTorch reports a usable GPU, and the project is one the GPU
    compositor reproduces exactly; otherwise renders on the CPU.
    `backend_cb` receives "cuda" or "cpu" once the backend is settled.
    """
    if use_gpu and is_cuda_available():
        blocker = _cuda_can_render(layers)
        if blocker:
            logger.info("GPU export unavailable (%s): rendering on CPU", blocker)
        else:
            try:
                if backend_cb:
                    backend_cb("cuda")
                return render_frames_cuda(
                    layers,
                    duration,
                    fps,
                    scale=scale,
                    loop_type=loop_type,
                    global_intensity=global_intensity,
                    focus_depth=focus_depth,
                    progress_cb=progress_cb,
                    cancelled_cb=cancelled_cb,
                )
            except Exception:
                # Never fail an export because of the GPU: fall back to the CPU
                # path, but make the reason visible instead of swallowing it.
                logger.exception("GPU export failed: falling back to CPU rendering")
                try:
                    import torch
                    torch.cuda.empty_cache()
                except Exception:
                    pass

    if backend_cb:
        backend_cb("cpu")

    visible_layers = [layer for layer in layers if layer.visible and not layer.image.isNull()]
    if not visible_layers:
        return []

    orig_w = max(layer.image.width() for layer in visible_layers)
    orig_h = max(layer.image.height() for layer in visible_layers)

    total = max(1, int(round(duration * fps)))
    frames: list[np.ndarray] = []
    amplitude = max(60.0, max(orig_w, orig_h) * 0.06)

    for i in range(total):
        if cancelled_cb and cancelled_cb():
            return []

        phase = i / total
        frame = composite_animated_layers(
            layers,
            phase,
            amplitude,
            global_intensity=global_intensity,
            depth_focus=focus_depth,
            loop_type=loop_type,
        )
        if frame is None:
            continue

        if scale != 1.0:
            new_w = max(1, int(frame.width() * scale))
            new_h = max(1, int(frame.height() * scale))
            frame = frame.scaled(
                new_w,
                new_h,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        frames.append(_qimage_to_rgb(frame))
        if progress_cb:
            progress_cb(i + 1, total)

    return frames


def export_mp4(
    frames: list[np.ndarray],
    output_path: Path,
    fps: int,
    progress_cb: Callable[[int, int], None] | None = None,
    use_nvenc: bool = True,
) -> None:
    if not frames:
        raise ValueError("No frames to export")

    first_frame = _even_dims(frames[0])
    h, w = first_frame.shape[:2]
    total = len(frames)

    ffmpeg_exe = shutil.which("ffmpeg")
    nvenc = use_nvenc and is_nvenc_available()

    if ffmpeg_exe:
        vcodec = "h264_nvenc" if nvenc else "libx264"
        cmd = [
            ffmpeg_exe,
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{w}x{h}",
            "-pix_fmt", "rgb24",
            "-r", str(fps),
            "-i", "-",
            "-c:v", vcodec,
        ]
        if nvenc:
            cmd.extend(["-preset", "p6", "-rc", "constqp", "-qp", "18", "-pix_fmt", "yuv420p"])
        else:
            cmd.extend(["-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p"])
        cmd.extend(["-movflags", "+faststart", str(output_path)])

        logger.info("Encoding %d frames at %dx%d with %s", total, w, h, vcodec)
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for i, frame in enumerate(frames):
                even_f = _even_dims(frame)
                if even_f.shape[:2] != (h, w):
                    # A short write desynchronises the raw stream and silently
                    # produces a scrambled video, so refuse rather than guess.
                    raise ValueError(
                        f"Frame {i} is {even_f.shape[1]}x{even_f.shape[0]}, expected {w}x{h}"
                    )
                proc.stdin.write(np.ascontiguousarray(even_f).tobytes())
                if progress_cb:
                    progress_cb(i + 1, total)
            proc.stdin.close()
            stderr = proc.stderr.read().decode("utf-8", "replace")
            proc.wait()
            if proc.returncode == 0:
                return
            logger.warning(
                "ffmpeg (%s) exited %s: retrying with imageio.\n%s",
                vcodec, proc.returncode, stderr[-2000:],
            )
        except Exception:
            logger.exception("ffmpeg encode failed: retrying with imageio")
            if proc.poll() is None:
                proc.kill()
        finally:
            for stream in (proc.stdin, proc.stderr):
                try:
                    if stream and not stream.closed:
                        stream.close()
                except Exception:
                    pass

    # Fallback to imageio if ffmpeg pipe fails. imageio ships its own ffmpeg
    # build, which is not guaranteed to carry NVENC: always ask for libx264.
    import imageio
    writer = imageio.get_writer(
        str(output_path),
        fps=fps,
        codec="libx264",
        quality=9,
        pixelformat="yuv420p",
    )
    try:
        for i, frame in enumerate(frames):
            writer.append_data(_even_dims(frame))
            if progress_cb:
                progress_cb(i + 1, total)
    finally:
        writer.close()


def export_gif(
    frames: list[np.ndarray],
    output_path: Path,
    fps: int,
    progress_cb: Callable[[int, int], None] | None = None,
) -> None:
    from PIL import Image

    if not frames:
        raise ValueError("No frames to export")

    duration_ms = max(1, int(round(1000 / fps)))
    total = len(frames)
    pil_frames = []
    for i, frame in enumerate(frames):
        pil_frames.append(Image.fromarray(frame))
        if progress_cb:
            progress_cb(i + 1, total)

    pil_frames[0].save(
        str(output_path),
        save_all=True,
        append_images=pil_frames[1:],
        loop=0,
        duration=duration_ms,
        optimize=True,
    )

