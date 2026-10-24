"""Portrait motion: idle and flaunt motion for a single figure.

Moving every pixel by its own depth around a fixed focus plane is exactly
wrong for a person: the depth model sees the nose nearer than the ears
(measured, a 0.24 depth spread across one face), so the face stretched and
squashed by 30-50% of its area on every loop.

The idle style is ported from the working reference in Thornline
(``Game_04_thornline/shaders/portrait.gdshader`` ``alive_source``):

- the head and hair move as one rigid block, a slow turn and shift about the
  top of the neck, never a scale, so the face cannot stretch;
- an imagined camera orbits the figure with the head as its focus, so parts
  nearer than the head (chest, hips, knees) swing further than it;
- the hips sway sideways out of step with the orbit;
- the chest lifts with each breath, and never widens.

The flaunt style keeps the same rigid head and adds a rhythm on top: the hips
swing side to side while the shoulders lean against them (an S-curve), the
raised hip tips up, the chest bounces twice per swing and the head tilts
toward the raised hip.

The bounce style is a slow, smooth bounce on the spot, driven from the hips:
the body rises and falls, full from the hips up and fading to nothing at the
feet, so the legs bend instead of her lifting off. The head rides it. The
breasts move in time with it, further, trailing it slightly. Nothing moves
sideways.

Everything is driven by one depth map, a figure mask and a few points (head,
neck pivot, chest, hips, eye distance). The points come from the pose model
Body Relief already uses, so this adds no non-commercial model. The mask keeps
a background still: a cut-out's own alpha, otherwise the person segmentation
Body Relief uses.
"""
from __future__ import annotations

import math
import threading
from collections import OrderedDict

import cv2
import numpy as np
from PySide6.QtGui import QImage

from app.core import depth_model

IDLE = "idle"
FLAUNT = "flaunt"
BOUNCE = "bounce"

# Thornline's numbers, in units of the eye distance ("face") and seconds.
# Each entry is (amplitude, angular frequency rad/s, phase).
HEAD_TURN = ((0.02 * 0.65, 0.83, 0.0), (0.02 * 0.35, 1.37, 1.3))   # radians
HEAD_SHIFT_X = (0.04, 0.61, 0.4)
HEAD_SHIFT_Y = (0.03, 1.12, 0.0)
ORBIT_X = (0.42, 0.45, 0.0)
ORBIT_Y = (0.08, 0.31, 1.0)
HIP_SWAY = (0.12, 0.45, 2.4)
BREATH = (0.07, 1.4, 0.0)

# Flaunt, in eye distances (radians for the tilt). One full left-right swing
# takes FLAUNT_STEP seconds; everything else is a harmonic of it.
FLAUNT_STEP = 2.0
FLAUNT_HIP_SWING = 0.30      # hips sideways
FLAUNT_LEAN = 0.10           # shoulders, against the hips
FLAUNT_HIP_TIP = 0.10        # raised hip up, the other down
FLAUNT_BOUNCE = 0.09         # chest, twice per swing
FLAUNT_JIGGLE = 0.03         # chest, the overtone that makes it settle
FLAUNT_CHEST_LAG = 0.05      # chest sideways, trailing the swing
FLAUNT_BOB = 0.035           # whole figure, twice per swing
FLAUNT_HEAD_TILT = 0.035
FLAUNT_ORBIT = (0.22, 0.04)
# Knees and feet keep this much of the hip swing, so she is not skating.
FLAUNT_PLANTED = 0.3

# Bounce, in eye distances. One bounce takes BOUNCE_STEP seconds.
BOUNCE_STEP = 1.5
BOUNCE_BODY = 0.30           # body, straight up and down
BOUNCE_HEAD_SHARE = 0.9      # of the body's travel, so the neck does not stretch
# Visible feet do not move. When she is cropped above them the lowest row of
# her still carries this much, since the knees are below the frame.
BOUNCE_CROPPED_SHARE = 0.25
# The breasts, on top of the body: the same smooth rise and fall, further, and
# trailing it by this fraction of a bounce. A resonant spring here was tried
# and read as moving to its own rhythm, out of time with her.
BOUNCE_BUST = 0.35
BOUNCE_TRAIL = 0.06
BOUNCE_PAIR_OFFSET = 0.01    # left and right out of step, fraction of a bounce

# Loops in this app are 1-8 seconds, and the orbit's own period is 14s. The
# longest loop keeps the idle motion closest to the reference; flaunt reads
# best as two swings.
PORTRAIT_DURATION = 8.0
FLAUNT_DURATION = 4.0
BOUNCE_DURATION = 6.0

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


def figure_mask(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """0..1, where the figure is. Hard-edged; the motion feathers it.

    A cut-out already says where she is. A picture with a background goes
    through the person segmentation; on gallery renders it found the figure
    cleanly but left holes in the lower legs, so holes are filled and small
    gaps closed.
    """
    if float(alpha.min()) < 0.99:
        return (alpha > 0.5).astype(np.float32)
    from app.core import body_model

    mask = (body_model.person_mask(rgb) > 0.5).astype(np.uint8)
    height, width = mask.shape
    k = max(3, int(max(height, width) * 0.02)) | 1
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    # Fill enclosed holes: flood the background from the border, keep the rest.
    flood = np.pad(1 - mask, 1, constant_values=1)
    reach = np.zeros((height + 4, width + 4), np.uint8)
    cv2.floodFill(flood, reach, (0, 0), 2)
    filled = (flood[1:-1, 1:-1] != 2).astype(np.float32)
    return filled


def portrait_depth(rgb: np.ndarray, body: np.ndarray, model_id: str) -> np.ndarray:
    """0 far .. 1 near over the figure's own pixels, softened.

    Normalised over the figure rather than the frame, with everything else set
    to the far end, so the figure's own relief uses the whole range.
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

    inside = body > 0.5
    if inside.sum() < 64:
        inside = np.ones_like(inside)
    lo, hi = np.percentile(depth[inside], (3, 97))
    depth = np.clip((depth - lo) / max(1e-6, float(hi - lo)), 0.0, 1.0)
    depth[~inside] = 0.0
    # Thornline's PIL blur radius, which PIL treats as the standard deviation.
    # Hard steps at the outline and between limbs tear when displaced.
    sigma = float(max(6, width // 60))
    depth = cv2.GaussianBlur(depth, (0, 0), sigmaX=sigma)
    return np.clip(depth, 0.0, 1.0).astype(np.float32)


def portrait_rig(rgb: np.ndarray, pose_id: str) -> dict | None:
    """Head, neck pivot, chest and hip points plus the eye distance, in pixels.

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
    if "left_hip" in kp and "right_hip" in kp:
        hips = (np.array(kp["left_hip"][:2], np.float32) + np.array(kp["right_hip"][:2], np.float32)) / 2
    else:
        hips = chest + down * span * 2.8
    # The bust sits about 30% of the way from the shoulder line to the hips.
    # Placed from the face alone it landed below and off-centre on two of
    # eight test renders; from the shoulders it sat on the cleavage on all.
    if "left_shoulder" in kp and "right_shoulder" in kp:
        shoulders = (
            np.array(kp["left_shoulder"][:2], np.float32) + np.array(kp["right_shoulder"][:2], np.float32)
        ) / 2
        bust = shoulders + (hips - shoulders) * 0.3
    else:
        bust = chest + down * span * 0.3
    height, width = rgb.shape[:2]
    point = lambda v: [float(v[0]), float(v[1])]
    return {
        "head": point(head),
        "pivot": point(pivot),
        "chest": point(chest),
        "hips": point(hips),
        "bust": point(bust),
        "face": float(span),
        "width": width,
        "height": height,
        "style": IDLE,
    }


def prepare(
    image: QImage, model_id: str, pose_id: str
) -> tuple[np.ndarray, dict | None, np.ndarray]:
    """Depth map, rig and figure mask for a layer. The rig is None if no face was found."""
    rgb, alpha = _flatten(image)
    mask = figure_mask(rgb, alpha)
    return portrait_depth(rgb, mask, model_id), portrait_rig(rgb, pose_id), mask


def _smoothstep(low: float, high: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - low) / max(1e-6, high - low), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _fields(layer_id: str, revision: int, depth: np.ndarray, rig: dict, mask: np.ndarray | None) -> dict:
    """The parts of the motion that do not change from frame to frame."""
    height, width = depth.shape
    key = (layer_id, revision, width, height, id(rig), rig.get("style"), id(mask))
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
    hips = rig.get("hips") or [rig["chest"][0], rig["chest"][1] + rig["face"] * 2.8]
    ix, iy = hips[0] * sx, hips[1] * sy
    iy = max(iy, cy + face)

    # Motion is confined to the figure. The falloff sits entirely outside her,
    # so every figure pixel moves in full and the face stays rigid even where
    # it meets the outline. It has to be wide: flaunt carries the hips 0.3 face
    # sideways, and a 0.15-face feather dropped that to zero fast enough to fold
    # the picture at the side of a seated figure (Jacobian -0.12). Over this
    # band the background beside her stretches instead. Without a mask (older
    # projects) everything moves.
    if mask is None:
        m = np.ones((height, width), np.float32)
    else:
        hard = mask if mask.shape == (height, width) else cv2.resize(
            mask, (width, height), interpolation=cv2.INTER_LINEAR
        )
        hard = (hard > 0.5).astype(np.float32)
        # Specks thinner than this are not figure. One stripe has a single
        # opaque pixel column down its edge, which moved in full beside a
        # background that did not and folded there.
        speck = max(3, int(face * 0.1)) | 1
        hard = cv2.morphologyEx(
            hard, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (speck, speck))
        )
        sigma = max(1.0, face * 0.4)
        grow = max(1, int(round(sigma * 2.0)))
        # A zero border: dilate's default counts beyond the frame as figure,
        # which set a band down the frame edge moving and folded it.
        m = cv2.dilate(
            hard, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (grow * 2 + 1,) * 2),
            borderType=cv2.BORDER_CONSTANT, borderValue=0,
        )
        m = np.maximum(cv2.GaussianBlur(m, (0, 0), sigmaX=sigma), hard)

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
    body = 1.0 - wh
    rel_z = (depth - z_head) * body * m
    sway = _smoothstep(cy, cy + face * 2.8, yy) * m
    wc = np.exp(-(((xx - cx) / 2.6) ** 2 + ((yy - cy) / 2.0) ** 2) / (face * face)) * body * m

    fields = {
        "face": face,
        "m": m,
        "wh": (wh * m).astype(np.float32),
        "rel_x": (xx - px).astype(np.float32),
        "rel_y": (yy - py).astype(np.float32),
        "rel_z": rel_z.astype(np.float32),
        "hips": sway.astype(np.float32),
        "chest": wc.astype(np.float32),
        "xx": xx,
        "yy": yy,
    }
    if rig.get("style") == FLAUNT:
        # Hips swing, the upper body leans the other way, the legs stay planted.
        swing = _smoothstep(cy, iy, yy) * (
            1.0 - (1.0 - FLAUNT_PLANTED) * _smoothstep(iy + face, iy + face * 5.0, yy)
        )
        lean = 1.0 - _smoothstep(cy, iy, yy)
        tip_band = np.exp(-(((yy - iy) / (face * 2.2)) ** 2)) * body
        tip_side = np.clip((xx - ix) / (face * 1.5), -1.0, 1.0)
        fields.update(
            swing=(swing * m).astype(np.float32),
            lean=(lean * m).astype(np.float32),
            tip=(tip_band * tip_side * m).astype(np.float32),
        )
    if rig.get("style") == BOUNCE:
        # What the bounce carries: everything from the hips up, fading to
        # nothing at the feet so the legs bend; a share of it on the head block.
        if mask is not None and hard.any():
            feet = float(np.nonzero(hard.any(axis=1))[0].max())
        else:
            feet = float(height - 1)
        floor = BOUNCE_CROPPED_SHARE if feet >= height - 2 else 0.0
        legs = 1.0 - (1.0 - floor) * _smoothstep(iy, max(iy + face, feet), yy)
        carry = (wh * BOUNCE_HEAD_SHARE + body * legs) * m
        # One soft lobe per breast either side of the bust point.
        bust_at = rig.get("bust") or [rig["chest"][0], rig["chest"][1] + rig["face"] * 0.3]
        bx, by = bust_at[0] * sx, bust_at[1] * sy

        def lobe(x0: float) -> np.ndarray:
            return np.exp(
                -(((xx - x0) / 1.4) ** 2 + ((yy - by) / 1.6) ** 2) / (face * face)
            ) * body * m

        fields.update(
            carry=carry.astype(np.float32),
            bust_l=lobe(bx - face * 0.8).astype(np.float32),
            bust_r=lobe(bx + face * 0.8).astype(np.float32),
        )
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


def _idle(f: dict, phase: float, duration: float) -> tuple[np.ndarray, np.ndarray]:
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
    return dx, dy


def _flaunt(f: dict, phase: float, duration: float) -> tuple[np.ndarray, np.ndarray]:
    face = f["face"]
    steps = max(1, int(round(duration / FLAUNT_STEP)))
    t = math.tau * steps * phase
    swing = math.sin(t)

    # The head tilts toward the raised hip and rides the lean and the bob.
    angle = FLAUNT_HEAD_TILT * math.sin(t + 0.6)
    c, s = math.cos(angle) - 1.0, math.sin(angle)
    bob = face * FLAUNT_BOB * math.sin(2 * t + 0.3)
    bounce = face * (
        FLAUNT_BOUNCE * math.sin(2 * t - 0.5) + FLAUNT_JIGGLE * math.sin(4 * t - 1.4)
    )
    wh, rx, ry = f["wh"], f["rel_x"], f["rel_y"]
    dx = (
        wh * (c * rx - s * ry)
        - f["lean"] * face * FLAUNT_LEAN * swing
        + f["swing"] * face * FLAUNT_HIP_SWING * swing
        + f["chest"] * face * FLAUNT_CHEST_LAG * math.sin(t - 0.9)
        + f["rel_z"] * face * FLAUNT_ORBIT[0] * swing
    )
    dy = (
        wh * (s * rx + c * ry)
        - f["m"] * bob
        - f["tip"] * face * FLAUNT_HIP_TIP * swing
        - f["chest"] * bounce
        + f["rel_z"] * face * FLAUNT_ORBIT[1] * math.sin(2 * t)
    )
    return dx, dy


def _lift(p: float) -> float:
    """0 at rest, 1 at the top: one smooth rise and fall per bounce."""
    return 0.5 - 0.5 * math.cos(math.tau * p)


def _bounce(f: dict, phase: float, duration: float) -> tuple[np.ndarray, np.ndarray]:
    face = f["face"]
    cycles = max(1, int(round(duration / BOUNCE_STEP)))
    p = (phase * cycles) % 1.0

    # Up is negative y. Nothing moves sideways.
    dy = -f["carry"] * face * BOUNCE_BODY * _lift(p)
    for lobe, sign in ((f["bust_l"], -1.0), (f["bust_r"], 1.0)):
        trail = BOUNCE_TRAIL + sign * BOUNCE_PAIR_OFFSET
        dy = dy - lobe * face * BOUNCE_BUST * _lift(p - trail)
    return np.zeros_like(dy), dy


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
    mask: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Where each output pixel samples from, for cv2.remap."""
    f = _fields(layer_id, revision, depth, rig, mask)
    if rig.get("style") == FLAUNT:
        dx, dy = _flaunt(f, phase, duration)
    elif rig.get("style") == BOUNCE:
        dx, dy = _bounce(f, phase, duration)
    else:
        dx, dy = _idle(f, phase, duration)
    map_x = f["xx"] - dx * (amount * scale_x)
    map_y = f["yy"] - dy * (amount * scale_y)
    return map_x.astype(np.float32, copy=False), map_y.astype(np.float32, copy=False)
