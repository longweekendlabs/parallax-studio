"""Monocular depth estimation via Depth Anything V2 (ONNX Runtime).

The built-in heuristic in ``depth.auto_depth`` is a brightness and centre-bias
formula with no idea what is in the picture, which is why it produces ripple
patterns instead of separating a subject from its background. This module runs
a real depth model instead.

Models are downloaded on first use into the user's data directory and reused
afterwards; nothing is bundled into the installer.
"""
from __future__ import annotations

import logging
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from PySide6.QtGui import QImage

from app.utils.paths import models_dir

logger = logging.getLogger(__name__)

# Model input side used by Depth Anything V2 (multiple of 14 for the ViT patches).
INPUT_SIZE = 518

_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

HEURISTIC_ID = "heuristic"


@dataclass(frozen=True)
class DepthModel:
    id: str
    label: str
    url: str
    filename: str
    approx_bytes: int
    license: str
    commercial_ok: bool
    note: str


# Only the Small checkpoint is Apache-2.0. Base and Large are CC-BY-NC-4.0, so
# they must not be used in a product that is going to be sold.
MODELS: tuple[DepthModel, ...] = (
    DepthModel(
        id=HEURISTIC_ID,
        label="Built-in heuristic (no download)",
        url="",
        filename="",
        approx_bytes=0,
        license="n/a",
        commercial_ok=True,
        note="Brightness and centre bias only. Fast, but it cannot tell a person from a background.",
    ),
    DepthModel(
        id="dav2-small-fp16",
        label="Depth Anything V2 Small (50 MB)",
        url="https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model_fp16.onnx",
        filename="depth-anything-v2-small-fp16.onnx",
        approx_bytes=49_642_442,
        license="Apache-2.0",
        commercial_ok=True,
        note="Recommended. Separates subjects from the background properly.",
    ),
    DepthModel(
        id="dav2-small",
        label="Depth Anything V2 Small, full precision (99 MB)",
        url="https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model.onnx",
        filename="depth-anything-v2-small.onnx",
        approx_bytes=99_060_839,
        license="Apache-2.0",
        commercial_ok=True,
        note="Same model as above without half-precision rounding. Slightly cleaner, twice the download.",
    ),
    DepthModel(
        id="dav2-base",
        label="Depth Anything V2 Base (389 MB, non-commercial)",
        url="https://huggingface.co/onnx-community/depth-anything-v2-base/resolve/main/onnx/model.onnx",
        filename="depth-anything-v2-base.onnx",
        approx_bytes=388_917_010,
        license="CC-BY-NC-4.0",
        commercial_ok=False,
        note="Finer detail, but the licence forbids commercial use. Do not ship results in a paid product.",
    ),
)

_BY_ID = {model.id: model for model in MODELS}
_SESSIONS: dict[str, object] = {}


def get_model(model_id: str) -> DepthModel:
    return _BY_ID.get(model_id, MODELS[0])


def model_path(model_id: str) -> Path | None:
    model = get_model(model_id)
    if not model.filename:
        return None
    return models_dir() / model.filename


def is_downloaded(model_id: str) -> bool:
    path = model_path(model_id)
    if path is None or not path.is_file():
        return False
    # A partial file from an interrupted download would load as a corrupt model.
    return path.stat().st_size >= get_model(model_id).approx_bytes * 0.95


def is_available() -> bool:
    """True when ONNX Runtime is importable in this build."""
    try:
        import onnxruntime  # noqa: F401
        return True
    except Exception:
        return False


def download_model(
    model_id: str,
    progress_cb: Callable[[int, int], None] | None = None,
    cancelled_cb: Callable[[], bool] | None = None,
) -> Path:
    """Fetch the model to its cache path. Returns immediately if already there."""
    model = get_model(model_id)
    target = model_path(model_id)
    if target is None:
        raise ValueError(f"{model.label} has no model file to download")
    if is_downloaded(model_id):
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    # Download beside the target so an interrupted transfer never looks complete.
    partial = target.with_suffix(target.suffix + ".part")

    request = urllib.request.Request(model.url, headers={"User-Agent": "ParallaxStudio"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            total = int(response.headers.get("Content-Length") or model.approx_bytes)
            done = 0
            with open(partial, "wb") as handle:
                while True:
                    if cancelled_cb and cancelled_cb():
                        handle.close()
                        partial.unlink(missing_ok=True)
                        raise InterruptedError("Download cancelled")
                    chunk = response.read(262_144)
                    if not chunk:
                        break
                    handle.write(chunk)
                    done += len(chunk)
                    if progress_cb:
                        progress_cb(done, total)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"Could not download {model.label}: {exc}") from exc

    shutil.move(str(partial), str(target))
    logger.info("Downloaded %s to %s", model.label, target)
    return target


def _session(model_id: str):
    session = _SESSIONS.get(model_id)
    if session is not None:
        return session

    import onnxruntime as ort

    path = model_path(model_id)
    if path is None or not path.is_file():
        raise RuntimeError("Model file is missing; download it first")

    providers = ["CPUExecutionProvider"]
    available = set(ort.get_available_providers())
    if "CUDAExecutionProvider" in available:
        providers.insert(0, "CUDAExecutionProvider")

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session = ort.InferenceSession(str(path), options, providers=providers)
    _SESSIONS[model_id] = session
    logger.info("Loaded %s using %s", path.name, session.get_providers())
    return session


def _qimage_to_rgb(image: QImage) -> np.ndarray:
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    h, w = rgba.height(), rgba.width()
    arr = np.frombuffer(rgba.bits(), dtype=np.uint8).reshape((h, w, 4))
    return arr[:, :, :3].copy()


# Robust normalisation bounds, in percent.
NORM_PCT_LO = 2.0
NORM_PCT_HI = 98.0

# Feather width at a depth discontinuity, as a fraction of the image's long
# edge, and how much of the 0..1 range the result is allowed to span.
PARALLAX_FEATHER = 0.020
PARALLAX_RANGE = 0.80

# The renderer displaces by `amplitude * intensity * (depth - focus) * 2`, with
# amplitude 6% of the long edge. The sampling grid folds where that displacement
# changes by more than one pixel per pixel, so the depth gradient has to stay
# under `1 / (2 * amplitude * intensity)`. These are the defaults it is sized
# for; turning intensity up past them can still stretch the silhouette, which is
# inherent to displacing a flat image with no inpainting behind the subject.
DESIGN_AMPLITUDE = 0.06
DESIGN_INTENSITY = 0.4875
FOLD_MARGIN = 0.85

# Body-relief mode. The model separates a subject from its background cleanly
# but leaves the subject's own shape nearly flat: chest-to-hip relief measures
# around 8% of the silhouette step, because a chest sits centimetres proud of
# the hips while the subject is metres in front of the wall. That is
# geometrically right and reads as a rigid cutout sliding about.
#
# Depth at that scale has a lot of unused headroom before it folds: features
# ~20% of the frame apart stay safe up to about 0.46 of depth amplitude, so
# roughly 15x what the model gives.
#
# The gain sets how much of the 0..1 range the subject may claim for its own
# relief, at 0.12 per unit. 3.0 measured as a 5.6x lift in within-body depth
# spread with the sampling grid still monotonic; raise it for more separation
# between body parts, at the cost of looking less like a photograph.
RELIEF_GAIN = 3.0


def soften_for_parallax(depth: np.ndarray, relief_gain: float = 0.0) -> np.ndarray:
    """Make a model depth map survive being used as a displacement map.

    The model draws a subject's outline as a near-vertical step in depth. A
    step does not stretch under displacement, it tears: the sampling grid stops
    being monotonic and the image folds back over itself along the silhouette.
    On a 1600px frame that measured as a single source pixel smeared across 90
    output pixels, with the grid running backwards through the fold. Every
    parallax artefact the outline shows comes from this, and a sharper model
    makes it worse, not better.

    The fix is to spread that shear across a band of pixels instead of one, and
    to keep the range short of a full 0..1 swing. Both are applied only to
    model output; painted depth is already smooth because the brush has falloff.

    The feather is weighted by local gradient so it lands on the silhouette and
    leaves flat interiors alone: blurring uniformly would take the body's own
    relief (chest, hips) out with the step.
    """
    height, width = depth.shape[:2]
    if relief_gain > 0.0:
        depth = _body_relief(depth, relief_gain)
    depth = 0.5 + (depth - 0.5) * PARALLAX_RANGE
    sigma = max(1.0, max(width, height) * PARALLAX_FEATHER)

    # Both the feather and its weight map are smooth by construction, so they
    # are built on a proxy and upsampled. At 12MP a full-resolution blur of this
    # width costs seconds; this keeps the whole pass under 100ms.
    scale = min(1.0, 512.0 / max(width, height))
    if scale < 1.0:
        small = cv2.resize(depth, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    else:
        small = depth
    small_sigma = max(0.6, sigma * scale)
    small_blur = cv2.GaussianBlur(small, (0, 0), sigmaX=small_sigma)

    # Take the feathered version only where the depth gradient is steep enough
    # to fold the sampling grid, and keep the model's own detail everywhere
    # else. Blurring uniformly would lift the body's relief (chest, hips,
    # hands) out along with the step; measured, it costs 70-80% of any detail
    # finer than the feather.
    #
    # The threshold is the fold limit itself, not a fraction of the steepest
    # edge in the picture: scaling against the peak leaves every secondary edge
    # below it partly sharp, and those tear too.
    long_edge = max(width, height)
    amplitude = max(60.0, long_edge * DESIGN_AMPLITUDE)
    safe_grad = FOLD_MARGIN / (2.0 * amplitude * DESIGN_INTENSITY)

    # Sobel's 3x3 kernel sums to 8 over a unit ramp, and a proxy pixel spans
    # 1/scale source pixels, so undo both to get depth units per source pixel.
    # Measured on the unblurred proxy: the question is how steep the map being
    # replaced is, and reading it off the blurred copy makes a wider feather
    # look flatter, which drives the weight to zero and leaves the step intact.
    grad = cv2.magnitude(
        cv2.Sobel(small, cv2.CV_32F, 1, 0, ksize=3),
        cv2.Sobel(small, cv2.CV_32F, 0, 1, ksize=3),
    ) * (scale / 8.0)
    small_weight = np.clip(grad / safe_grad, 0.0, 1.0)
    # The band over the fold threshold is only a few pixels wide. Smoothing it
    # directly would flatten its own peak and leave most of the step unfeathered,
    # so grow it to cover the feather first, then soften only its edges.
    radius = max(1, int(round(small_sigma * 2.0)))
    small_weight = cv2.dilate(small_weight, np.ones((radius * 2 + 1,) * 2, np.uint8))
    small_weight = cv2.GaussianBlur(small_weight, (0, 0), sigmaX=max(0.6, small_sigma * 0.5))

    if scale < 1.0:
        blurred = cv2.resize(small_blur, (width, height), interpolation=cv2.INTER_LINEAR)
        weight = cv2.resize(small_weight, (width, height), interpolation=cv2.INTER_LINEAR)
    else:
        blurred, weight = small_blur, small_weight

    depth = depth * (1.0 - weight) + blurred * weight
    return np.clip(depth, 0.0, 1.0).astype(np.float32)


def _body_relief(depth: np.ndarray, gain: float) -> np.ndarray:
    """Amplify depth variation *within* a subject, leaving the outline alone.

    A band-pass at body-part scale: the subject-against-background separation
    is below it and model noise is above it, so what is left to lift is the
    chest/hip/leg relief. All of it is low-frequency, which is why it can be
    built on a proxy and upsampled.

    Both ends of the band-pass are edge-aware, against the same near/far mask.
    That matters more than it sounds: a plain Gaussian drags background depth
    across the outline, so the band-pass reads the entire figure as one large
    positive detail. Sharing one mask makes both ends follow the outline
    identically, so their difference is ~0 there by construction and the boost
    has nothing to grip.

    Runs before the range is compressed, and renormalises afterwards. Adding
    the boost to a map that already spans 0..1 just clips the subject flat,
    which is the failure it exists to prevent -- measured at half the frame
    saturated when it was applied the other way round.
    """
    near = _near_mask(depth)
    # Statistics come from confidently-classified pixels only. Taking them from
    # everything over 0.5 pulls in the mask's own soft boundary, and those
    # background-valued pixels drag the subject's low percentile down into the
    # background -- which makes the stretch below a no-op.
    subject = near > 0.9
    background = near < 0.1
    # No usable figure/ground split: a landscape, or a frame filled by one
    # surface. Stretching an arbitrary threshold there invents structure.
    if subject.sum() < depth.size * 0.02 or background.sum() < depth.size * 0.02:
        return depth

    lo_s, hi_s = (float(v) for v in np.percentile(depth[subject], (NORM_PCT_LO, NORM_PCT_HI)))
    lo_b, hi_b = (float(v) for v in np.percentile(depth[background], (NORM_PCT_LO, NORM_PCT_HI)))
    if hi_s - lo_s < 1e-5 or hi_b - lo_b < 1e-5:
        return depth

    # Give each side its own slice of the range and stretch its own variation
    # to fill it. The subject keeps the near band, so it still reads as being in
    # front, but its internal relief now spans `band` instead of the ~8% of the
    # step the model leaves it with. `gain` sets how much of the range the
    # subject is allowed to claim.
    band = min(0.48, 0.12 * gain)
    gap = (1.0 - 2.0 * band) * 0.5
    front = np.clip((depth - lo_s) / (hi_s - lo_s), 0.0, 1.0) * band + (band + 2.0 * gap)
    back = np.clip((depth - lo_b) / (hi_b - lo_b), 0.0, 1.0) * band

    return np.clip(near * front + (1.0 - near) * back, 0.0, 1.0).astype(np.float32)


def _near_mask(depth: np.ndarray) -> np.ndarray:
    """Soft 0..1 split between the near subject and the far background.

    Otsu picks the split, so it follows whatever the histogram actually does
    rather than assuming a fixed depth. It is only used to find the two groups
    though, not as the boundary: with clusters as separated as a subject and
    its background, every cut through the empty middle scores the same and
    Otsu returns the first, which sits hard against the near edge of the
    background. A sigmoid centred there never reaches 0 on the background side.

    So the sigmoid is centred between the two group means and scaled to their
    separation, which puts it in the middle of the gap on any histogram. The
    edge stays soft; a hard mask would put its own step into the depth map.
    """
    as_u8 = np.clip(depth * 255.0, 0, 255).astype(np.uint8)
    level, _ = cv2.threshold(as_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    split = float(level) / 255.0

    low = depth[depth <= split]
    high = depth[depth > split]
    if low.size == 0 or high.size == 0:
        return np.full(depth.shape, 0.5, dtype=np.float32)

    lo_mean, hi_mean = float(low.mean()), float(high.mean())
    centre = (lo_mean + hi_mean) * 0.5
    softness = max(0.02, (hi_mean - lo_mean) * 0.15)
    return (1.0 / (1.0 + np.exp(-(depth - centre) / softness))).astype(np.float32)


def estimate_depth(image: QImage, model_id: str, relief: bool = False) -> np.ndarray:
    """Run the model and return a float32 depth map, 0 far to 1 near.

    The result is the same size as ``image`` and matches the app's convention
    where higher values sit closer to the viewer.

    With ``relief`` the subject's own shape is amplified so body parts carry
    separate parallax instead of the whole figure sliding as one cutout.
    """
    session = _session(model_id)
    rgb = _qimage_to_rgb(image)
    height, width = rgb.shape[:2]

    resized = cv2.resize(rgb, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_CUBIC)
    tensor = resized.astype(np.float32) / 255.0
    tensor = (tensor - _IMAGENET_MEAN) / _IMAGENET_STD
    tensor = np.transpose(tensor, (2, 0, 1))[None]

    # Input/output names differ between exports, so read them off the session
    # rather than hard-coding them.
    input_name = session.get_inputs()[0].name
    expected = session.get_inputs()[0].type
    if "float16" in expected:
        tensor = tensor.astype(np.float16)
    output_name = session.get_outputs()[0].name

    raw = session.run([output_name], {input_name: tensor})[0]
    depth = np.squeeze(raw).astype(np.float32)
    depth = cv2.resize(depth, (width, height), interpolation=cv2.INTER_CUBIC)

    # Depth Anything predicts relative inverse depth: larger is nearer, with an
    # arbitrary scale, so normalise per image. Percentiles rather than min/max
    # because one specular highlight or blown-out sky would otherwise squeeze
    # the entire scene into a fraction of the range.
    lo, hi = (float(v) for v in np.percentile(depth, (NORM_PCT_LO, NORM_PCT_HI)))
    if hi - lo < 1e-6:
        return np.full((height, width), 0.5, dtype=np.float32)
    depth = np.clip((depth - lo) / (hi - lo), 0.0, 1.0)
    return soften_for_parallax(depth, relief_gain=RELIEF_GAIN if relief else 0.0)
