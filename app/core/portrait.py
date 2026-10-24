"""Portrait motion: the "alive" idle motion for a single figure.

Auto Depth moves every pixel by its own depth around a fixed focus plane. On a
portrait that is exactly wrong: the depth model sees the nose nearer than the
ears (measured, a 0.24 depth spread across one face), so the face stretches and
squashes by 30-50% of its area on every loop.

This mode is ported from the working reference in Thornline
(``Game_04_thornline/shaders/portrait.gdshader`` ``alive_source``):

- the head and hair move as one rigid block, a slow turn and shift about the
  top of the neck, never a scale, so the face cannot stretch;
- an imagined camera orbits the figure with the head as its focus, so parts
  nearer than the head (chest, hips, knees) swing further than it;
- the hips sway sideways out of step with the orbit;
- the chest lifts with each breath, and never widens.

All of it is driven by one depth map and four points (head, neck pivot,
chest, eye distance). The points come from the pose model Body Relief already
uses, so this adds no download and no non-commercial model.
"""
from __future__ import annotations

import math
import threading
from collections import OrderedDict

import cv2
import numpy as np
from PySide6.QtGui import QImage

from app.core import depth_model

# Thornline's numbers, in units of the eye distance ("face") and seconds.
# Each entry is (amplitude, angular frequency rad/s, phase).
HEAD_TURN = ((0.02 * 0.65, 0.83, 0.0), (0.02 * 0.35, 1.37, 1.3))   # radians
HEAD_SHIFT_X = (0.04, 0.61, 0.4)
HEAD_SHIFT_Y = (0.03, 1.12, 0.0)
ORBIT_X = (0.42, 0.45, 0.0)
ORBIT_Y = (0.08, 0.31, 1.0)
HIP_SWAY = (0.12, 0.45, 2.4)
BREATH = (0.07, 1.4, 0.0)

# Loops in this app are 1-8 seconds, and the orbit's own period is 14s. The
# longest loop keeps the motion closest to the reference, so applying the mode
# sets it.
PORTRAIT_DURATION = 8.0

# The motion reads at its designed strength with the layer and global
# intensity at their defaults (1.0 and 0.75).
REFERENCE_INTENSITY = 0.75

# The pose model the rig is read from. The everyday pose setting defaults to
# MultiPose, which put the eye distance 18% high on one of three test portraits
# (enough to bring the warp near folding); Thunder stayed within 8% of SCRFD on
# all three. A portrait has one person, so the single-person model loses nothing.
PORTRAIT_POSE = "movenet-thunder"

# Where the mouth sits below the eyes, in eye distances. MoveNet has no mouth
# point; measured from SCRFD on three portraits it was 1.17, 1.33 and 1.25.
EYES_TO_MOUTH = 1.25

_CACHE_LOCK = threading.Lock()
_FIELDS: OrderedDict[tuple, dict] = OrderedDict()
_MAX_CACHED = 4


def _flatten(image: QImage) -> tuple[np.ndarray, np.ndarray]:
    """RGB with transparent pixels filled grey, and alpha 0..1.

    A cut-out keeps whatever colour was under its transparent pixels, which on
    a green-screen render is leftover green. The models see that colour, so it
    is replaced with neutral grey first.
    """
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    h, w = rgba.height(), rgba.width()
    arr = np.frombuffer(rgba.bits(), dtype=np.uint8).reshape((h, w, 4))
    alpha = arr[:, :, 3].astype(np.float32) / 255.0
    rgb = arr[:, :, :3].astype(np.float32)
    rgb = rgb * alpha[:, :, None] + 128.0 * (1.0 - alpha[:, :, None])
    return rgb.astype(np.uint8), alpha


def portrait_depth(rgb: np.ndarray, alpha: np.ndarray, model_id: str) -> np.ndarray:
    """0 far .. 1 near over the figure's own pixels, softened.

    Normalised over the figure rather than the frame, with the empty canvas
    set to the far end, so a cut-out's background stays flat instead of
    picking up the slope the model gives empty space.
    """
    session = depth_model.open_session(depth_model.file_path(depth_model.get_model(model_id)), model_id)
    height, width = rgb.shape[:2]
    size = depth_model.INPUT_SIZE
    x = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255.0
    x = ((x - depth_model._IMAGENET_MEAN) / depth_model._IMAGENET_STD).transpose(2, 0, 1)[None]
    inp = session.get_inputs()[0]
    if "float16" in inp.type:
        x = x.astype(np.float16)
    raw = session.run([session.get_outputs()[0].name], {inp.name: x})[0]
    depth = cv2.resize(np.squeeze(raw).astype(np.float32), (width, height), interpolation=cv2.INTER_CUBIC)

    body = alpha > 0.5
    if body.sum() < 64:
        body = np.ones_like(body)
    lo, hi = np.percentile(depth[body], (3, 97))
    depth = np.clip((depth - lo) / max(1e-6, float(hi - lo)), 0.0, 1.0)
    depth[~body] = 0.0
    # Hard steps at the outline and between limbs tear when displaced.
    # Thornline's PIL blur radius, which PIL treats as the standard deviation.
    sigma = float(max(6, width // 60))
    depth = cv2.GaussianBlur(depth, (0, 0), sigmaX=sigma)
    return np.clip(depth, 0.0, 1.0).astype(np.float32)


def portrait_rig(rgb: np.ndarray, pose_id: str) -> dict | None:
    """Head, neck pivot and chest points plus the eye distance, in pixels.

    Same construction as Thornline's rig, with the mouth placed from the eyes
    because the pose model does not find one. None when no face is found.
    """
    from app.core import body_model

    people = body_model.pose_people(rgb, pose_id)
    best = None
    for kp in people:
        if not all(k in kp for k in ("left_eye", "right_eye", "nose")):
            continue
        span = math.dist(kp["left_eye"][:2], kp["right_eye"][:2])
        if best is None or span > best[0]:
            best = (span, kp)
    if best is None or best[0] < 4.0:
        return None
    span, kp = best
    left = np.array(kp["left_eye"][:2], np.float32)
    right = np.array(kp["right_eye"][:2], np.float32)
    nose = np.array(kp["nose"][:2], np.float32)
    eyes = (left + right) / 2
    # Down the face: perpendicular to the eye line, on the nose's side.
    across = right - left
    down = np.array([-across[1], across[0]], np.float32)
    down /= max(1e-6, float(np.linalg.norm(down)))
    if float(np.dot(down, nose - eyes)) < 0:
        down = -down
    mouth = eyes + down * span * EYES_TO_MOUTH
    head = (eyes + nose + mouth) / 3
    chin = mouth + down * span * 0.75
    pivot = chin + down * span * 0.55
    chest = chin + down * span * 2.6
    height, width = rgb.shape[:2]
    return {
        "head": [float(head[0]), float(head[1])],
        "pivot": [float(pivot[0]), float(pivot[1])],
        "chest": [float(chest[0]), float(chest[1])],
        "face": float(span),
        "width": width,
        "height": height,
    }


def prepare(image: QImage, model_id: str, pose_id: str) -> tuple[np.ndarray, dict | None]:
    """Depth map and rig for a layer. The rig is None if no face was found."""
    rgb, alpha = _flatten(image)
    return portrait_depth(rgb, alpha, model_id), portrait_rig(rgb, pose_id)


def _smoothstep(low: float, high: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - low) / max(1e-6, high - low), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _fields(layer_id: str, revision: int, depth: np.ndarray, rig: dict) -> dict:
    """The parts of the motion that do not change from frame to frame."""
    height, width = depth.shape
    key = (layer_id, revision, width, height, id(rig))
    with _CACHE_LOCK:
        cached = _FIELDS.get(key)
        if cached is not None:
            _FIELDS.move_to_end(key)
            return cached

    # The rig is in source pixels; preview proxies are smaller.
    sx = width / float(rig["width"])
    sy = height / float(rig["height"])
    face = rig["face"] * (sx + sy) / 2
    hx, hy = rig["head"][0] * sx, rig["head"][1] * sy
    px, py = rig["pivot"][0] * sx, rig["pivot"][1] * sy
    cx, cy = rig["chest"][0] * sx, rig["chest"][1] * sy

    yy, xx = np.indices((height, width), dtype=np.float32)
    # Head and hair: 1 above the pivot, fading out down the neck and to the sides.
    wh = (1.0 - _smoothstep(py, py + face * 1.3, yy)) * (
        1.0 - _smoothstep(face * 2.6, face * 3.6, np.abs(xx - hx))
    )
    # The head's own depth, read off the map, and the depth relative to it.
    # Inside the head block depth is held at the head's, so the face stays rigid.
    r = max(1, int(face * 0.6))
    patch = depth[max(0, int(hy) - r):int(hy) + r + 1, max(0, int(hx) - r):int(hx) + r + 1]
    z_head = float(patch.mean()) if patch.size else 0.5
    rel_z = (depth - z_head) * (1.0 - wh)
    hips = _smoothstep(cy, cy + face * 2.8, yy)
    wc = np.exp(-(((xx - cx) / 2.6) ** 2 + ((yy - cy) / 2.0) ** 2) / (face * face)) * (1.0 - wh)

    fields = {
        "face": face,
        "wh": wh.astype(np.float32),
        "rel_x": (xx - px).astype(np.float32),
        "rel_y": (yy - py).astype(np.float32),
        "rel_z": rel_z.astype(np.float32),
        "hips": hips.astype(np.float32),
        "chest": wc.astype(np.float32),
        "xx": xx,
        "yy": yy,
    }
    with _CACHE_LOCK:
        _FIELDS[key] = fields
        while len(_FIELDS) > _MAX_CACHED:
            _FIELDS.popitem(last=False)
    return fields


def _wave(term: tuple[float, float, float], phase: float, duration: float) -> float:
    """One sine of the reference, snapped to whole cycles per loop.

    The reference runs on a free clock; a loop has to end where it began, so
    each frequency becomes the nearest whole number of cycles in the loop, and
    never zero.
    """
    amp, omega, offset = term
    cycles = max(1, int(round(omega * duration / math.tau)))
    return amp * math.sin(math.tau * cycles * phase + offset)


def source_maps(
    layer_id: str,
    revision: int,
    depth: np.ndarray,
    rig: dict,
    phase: float,
    duration: float,
    amount: float,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Where each output pixel samples from, for cv2.remap."""
    f = _fields(layer_id, revision, depth, rig)
    face = f["face"]

    angle = sum(_wave(t, phase, duration) for t in HEAD_TURN)
    shift_x = face * _wave(HEAD_SHIFT_X, phase, duration)
    shift_y = face * _wave(HEAD_SHIFT_Y, phase, duration)
    orbit_x = face * _wave(ORBIT_X, phase, duration)
    orbit_y = face * _wave(ORBIT_Y, phase, duration)
    sway = face * _wave(HIP_SWAY, phase, duration)
    amp, omega, offset = BREATH
    cycles = max(1, int(round(omega * duration / math.tau)))
    breath = face * amp * (0.5 + 0.5 * math.sin(math.tau * cycles * phase + offset))

    c, s = math.cos(angle) - 1.0, math.sin(angle)
    wh, rx, ry = f["wh"], f["rel_x"], f["rel_y"]
    dx = wh * (c * rx - s * ry + shift_x) + f["rel_z"] * orbit_x + f["hips"] * sway
    dy = wh * (s * rx + c * ry + shift_y) + f["rel_z"] * orbit_y - f["chest"] * breath

    map_x = f["xx"] - dx * (amount * scale_x)
    map_y = f["yy"] - dy * (amount * scale_y)
    return map_x.astype(np.float32, copy=False), map_y.astype(np.float32, copy=False)
