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


def estimate_depth(image: QImage, model_id: str) -> np.ndarray:
    """Run the model and return a float32 depth map, 0 far to 1 near.

    The result is the same size as ``image`` and matches the app's convention
    where higher values sit closer to the viewer.
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
    # arbitrary scale, so normalise per image.
    lo = float(depth.min())
    hi = float(depth.max())
    if hi - lo < 1e-6:
        return np.full((height, width), 0.5, dtype=np.float32)
    return np.clip((depth - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)
