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
import os
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
    return has_file(get_model(model_id))


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
    return ensure_file(get_model(model_id), progress_cb, cancelled_cb)


def _extra_model_dirs() -> tuple[Path, ...]:
    """Read-only places a model file may already be sitting.

    Long Weekend Labs apps publish from the same upstream sources, so the same
    file often exists twice on one machine. Swapio keeps its models beside its
    own code and already downloads the face parser this app wants; Castivo does
    the same with the InsightFace pack. Rather than pull another copy, look
    where a sibling checkout would have put it. This only ever reads.
    """
    dirs: list[Path] = []

    override = os.environ.get("PARALLAX_MODEL_DIRS", "").strip()
    for entry in override.split(os.pathsep):
        if entry.strip():
            dirs.append(Path(entry.strip()).expanduser())

    # A cache shared by every LWL app, for files that more than one of them use.
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home) if data_home else Path.home() / ".local" / "share"
    dirs.append(base / "long-weekend-labs" / "models")

    # Running from a source checkout: the sibling projects live next door.
    try:
        projects = Path(__file__).resolve().parents[3]
        if projects.is_dir():
            dirs.extend(sorted(projects.glob("*/models")))
    except (IndexError, OSError):
        pass

    seen: set[Path] = set()
    unique = []
    for path in dirs:
        if path not in seen and path.is_dir():
            seen.add(path)
            unique.append(path)
    return tuple(unique)


def _complete(path: Path, model: DepthModel) -> bool:
    # A partial file from an interrupted download would load as a corrupt model.
    return path.is_file() and path.stat().st_size >= model.approx_bytes * 0.95


def file_path(model: DepthModel) -> Path | None:
    """Where this model is, preferring a copy that already exists.

    Falls back to the app's own models directory, which is the only place a
    download is ever written.
    """
    if not model.filename:
        return None
    target = models_dir() / model.filename
    if _complete(target, model):
        return target
    for directory in _extra_model_dirs():
        candidate = directory / model.filename
        if _complete(candidate, model):
            logger.info("Using %s already present at %s", model.filename, directory)
            return candidate
    return target


def download_path(model: DepthModel) -> Path | None:
    """Where a download would be written, ignoring any shared copy."""
    return models_dir() / model.filename if model.filename else None


def has_file(model: DepthModel) -> bool:
    path = file_path(model)
    return path is not None and _complete(path, model)


def ensure_file(
    model: DepthModel,
    progress_cb: Callable[[int, int], None] | None = None,
    cancelled_cb: Callable[[], bool] | None = None,
) -> Path:
    """Download any cached model file. Shared with the body-part models."""
    if has_file(model):
        # Already here, possibly in a shared location another app filled in.
        return file_path(model)
    target = download_path(model)
    if target is None:
        raise ValueError(f"{model.label} has no model file to download")

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
    return open_session(model_path(model_id), model_id)


def open_session(path: Path | None, cache_key: str):
    """Cached ONNX session. Shared with the body-part models."""
    session = _SESSIONS.get(cache_key)
    if session is not None:
        return session

    import onnxruntime as ort

    if path is None or not path.is_file():
        raise RuntimeError("Model file is missing; download it first")

    providers = ["CPUExecutionProvider"]
    available = set(ort.get_available_providers())
    if "CUDAExecutionProvider" in available:
        providers.insert(0, "CUDAExecutionProvider")

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session = ort.InferenceSession(str(path), options, providers=providers)
    _SESSIONS[cache_key] = session
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

def soften_for_parallax(
    depth: np.ndarray, edge_source: np.ndarray | None = None
) -> np.ndarray:
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

    # Where to look for edges worth feathering. Body Relief passes the depth
    # model's own map here: the tearing risk lives on the figure's outline,
    # which that map already has, while the part structure Body Relief writes
    # inside the figure is broad and safe. Measuring edges on the rebuilt map
    # instead cost about half the part separation, because the outline's
    # dilated feather band reaches 40px inside the figure and smooths the parts
    # sitting near it.
    if edge_source is None:
        small_edges = small
    elif scale < 1.0:
        small_edges = cv2.resize(
            edge_source, (small.shape[1], small.shape[0]), interpolation=cv2.INTER_AREA
        )
    else:
        small_edges = edge_source
    if edge_source is not None:
        # Same compression the map itself got, so the gradient threshold below
        # means the same thing for both.
        small_edges = 0.5 + (small_edges - 0.5) * PARALLAX_RANGE

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
        cv2.Sobel(small_edges, cv2.CV_32F, 1, 0, ksize=3),
        cv2.Sobel(small_edges, cv2.CV_32F, 0, 1, ksize=3),
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


def estimate_depth(
    image: QImage, model_id: str, relief: bool = False,
    relief_strength: float | None = None,
    pose_id: str | None = None,
    relief_weights=None,
) -> np.ndarray:
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
    if relief:
        # Imported here: body_model imports this module for its download and
        # session helpers.
        from app.core import body_model

        rebuilt = body_model.body_part_depth(
            image, depth, relief_strength,
            pose_id or body_model.DEFAULT_POSE,
            weights=relief_weights,
        )
        gate = body_model.body_part_depth.last_gate
        plain = soften_for_parallax(depth)
        shaped = soften_for_parallax(rebuilt)
        result = (plain * (1.0 - gate) + shaped * gate).astype(np.float32)

        # soften_for_parallax compresses the whole range toward the middle by
        # PARALLAX_RANGE. Body Relief pulls every region it wants held still
        # onto one plane and reports that plane as the focus depth, so the
        # focus has to travel through the same compression or the two no longer
        # agree: measured, a 0.20 compression of a centre at 0.88 left the face
        # and the background sitting 0.076 off the focus plane and travelling
        # 10px each, on the two regions that are supposed to be motionless.
        motion = getattr(body_model.body_part_depth, "suggested_motion", None)
        focus_c = 0.5
        if motion and "focus_depth" in motion:
            focus = float(motion["focus_depth"])
            focus_c = max(0.05, min(0.95, 0.5 + (focus - 0.5) * PARALLAX_RANGE))
            motion["focus_depth"] = focus_c

        # Put the motionless regions back exactly on the focus plane. The
        # feather above blurs across their outlines and pulls their edges off
        # it, and an edge that moves is precisely what reads as the face
        # wobbling or the background creeping. Both masks ramp outside the
        # region they protect, so this adds no step inside it.
        still = getattr(body_model.body_part_depth, "last_still", None)
        if still is not None and still.shape == result.shape:
            result = (result * (1.0 - still) + focus_c * still).astype(np.float32)
        return result
    return soften_for_parallax(depth)
