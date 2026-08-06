"""Per-pixel labels for a head: face, hair, ears, neck, clothing.

Everything else this app knows about a person is either a blob or a dot.
Selfie segmentation returns one class, person or not. MoveNet returns 17
joint positions. Neither can answer "is this pixel hair or is it cheek", so
Body Relief used to guess: it drew a circle around the averaged face landmarks
and held the relief off everything inside it. That circle is wrong in both
directions at once. Sized to cover the hair it eats the jaw and the neck;
sized to the face it lets the relief run over the forehead. And because it is
one circle, excluding the face necessarily also excluded the hair, which is
the one part of a head that should move.

BiSeNet gives the actual answer: 19 semantic classes over a head crop. The
face keeps its exact shape and never moves; hair, hat and clothing move.

The weights are the same file Swapio downloads, so on a machine that has both
apps this costs no extra download.
"""
from __future__ import annotations

import logging

import cv2
import numpy as np

from app.core.depth_model import DepthModel, file_path, has_file, open_session

logger = logging.getLogger(__name__)

FACE_PARSER = DepthModel(
    id="bisenet-face-parser",
    label="Face and hair parser (53 MB)",
    url=(
        "https://github.com/yakhyo/face-parsing/releases/download/weights/"
        "resnet18.onnx"
    ),
    filename="bisenet_resnet_18.onnx",
    approx_bytes=53_205_364,
    license="MIT",
    commercial_ok=True,
    note=(
        "Labels every pixel of a head: face, hair, ears, neck, clothing. Body "
        "Relief uses it to leave the face perfectly still while the hair moves."
    ),
)

# CelebAMask-HQ class order, which is what this checkpoint was trained on.
BACKGROUND = 0
SKIN = 1
BROW_L, BROW_R = 2, 3
EYE_L, EYE_R = 4, 5
GLASSES = 6
EAR_L, EAR_R = 7, 8
EARRING = 9
NOSE = 10
MOUTH = 11
LIP_U, LIP_L = 12, 13
NECK = 14
NECKLACE = 15
CLOTH = 16
HAIR = 17
HAT = 18

# What must never be displaced. Every feature of the face proper, because
# these are the pixels a viewer reads first and any relative motion between
# them registers immediately as the face deforming.
FACE_CLASSES = (SKIN, BROW_L, BROW_R, EYE_L, EYE_R, GLASSES, NOSE, MOUTH, LIP_U, LIP_L)
# What should move. Hair is the point: it is the part of a head that has any
# business bouncing.
HAIR_CLASSES = (HAIR, HAT)
# Ears and neck sit between the two. They belong to the head so they must not
# slide against the face, but they are not features, so they are held still
# along with it rather than being given their own motion.
STILL_EXTRA_CLASSES = (EAR_L, EAR_R, EARRING, NECKLACE)

INPUT_SIZE = 512
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# How wide the head crop is, as a multiple of the radius passed in.
#
# This checkpoint was trained on CelebAMask-HQ, which is tight, roughly aligned
# head crops. Hand it a box containing a torso and it does not decline: it
# labels shirt as skin and wall as hair, and the region map comes out as a
# rectangular block of "face" across the chest. At 3.4 the crop was about three
# times the width the model expects. 1.25 puts the box at roughly one and a
# half head widths, which covers hair above and jaw below with the context the
# model was trained to see and nothing beyond it.
CROP_REACH = 1.25

# How far the crop is lifted above the landmark centroid, as a fraction of its
# half width. Chosen so the box covers hair above the hairline rather than
# slicing through it.
CROP_LIFT = 0.30


def is_ready() -> bool:
    return has_file(FACE_PARSER)


def _session():
    return open_session(file_path(FACE_PARSER), FACE_PARSER.id)


def head_crop(shape: tuple[int, int], cx: float, cy: float, radius: float) -> tuple[int, int, int, int]:
    """A square box around a head, clamped to the picture."""
    height, width = shape
    half = max(8.0, radius * CROP_REACH * 0.5)
    # The landmarks this is centred on sit at eye level, but a head is not
    # symmetric about the eyes: there is far more of it above than below, and a
    # box centred on them cuts the top of the hair off flat. The parser cannot
    # label what it is not shown, so the clipped hair simply stops moving, with
    # a straight edge across it where the crop ended.
    lift = half * CROP_LIFT
    x0 = int(max(0, round(cx - half)))
    y0 = int(max(0, round(cy - half - lift)))
    x1 = int(min(width, round(cx + half)))
    y1 = int(min(height, round(cy + half - lift)))
    return x0, y0, x1, y1


def parse_head(rgb: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray | None:
    """Class label per pixel for one head crop, at the crop's own resolution.

    ``rgb`` is the full picture; ``box`` is the crop to look at. Returns None
    when the crop is degenerate or the model is not installed.
    """
    x0, y0, x1, y1 = box
    if x1 - x0 < 16 or y1 - y0 < 16:
        return None
    if not is_ready():
        return None

    crop = rgb[y0:y1, x0:x1]
    resized = cv2.resize(crop, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_LINEAR)
    tensor = resized.astype(np.float32) / 255.0
    tensor = (tensor - _MEAN) / _STD
    tensor = np.transpose(tensor, (2, 0, 1))[None]

    session = _session()
    output = session.run(None, {session.get_inputs()[0].name: tensor})[0]
    labels = np.argmax(output[0], axis=0).astype(np.uint8)
    # Nearest, not linear: these are class indices, and interpolating between
    # class 1 and class 17 would invent whatever class happens to sit between.
    return cv2.resize(
        labels, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST
    )


def _class_mask(labels: np.ndarray, classes) -> np.ndarray:
    mask = np.zeros(labels.shape, dtype=bool)
    for value in classes:
        mask |= labels == value
    return mask


def head_masks(
    shape: tuple[int, int],
    rgb: np.ndarray,
    heads: list[tuple[float, float, float]],
) -> tuple[np.ndarray, np.ndarray]:
    """Full-frame (still, moving) masks for every head found.

    ``still`` is the face and the parts that must not move relative to it.
    ``moving`` is hair and hat, which should. Both are float 0..1 and are
    feathered slightly so neither introduces a step for the displacement to
    tear on.
    """
    height, width = shape
    still = np.zeros((height, width), dtype=np.float32)
    moving = np.zeros((height, width), dtype=np.float32)
    # The parser's own answer, kept unfeathered so it can be re-asserted below.
    exact_face = np.zeros((height, width), dtype=np.float32)
    if not heads or not is_ready():
        return still, moving

    for cx, cy, radius in heads:
        box = head_crop(shape, cx, cy, radius)
        labels = parse_head(rgb, box)
        if labels is None:
            continue
        x0, y0, x1, y1 = box
        face = _class_mask(labels, FACE_CLASSES + STILL_EXTRA_CLASSES + (NECK,))
        hair = _class_mask(labels, HAIR_CLASSES)
        np.maximum(still[y0:y1, x0:x1], face.astype(np.float32), out=still[y0:y1, x0:x1])
        np.maximum(moving[y0:y1, x0:x1], hair.astype(np.float32), out=moving[y0:y1, x0:x1])
        strict = _class_mask(labels, FACE_CLASSES).astype(np.float32)
        np.maximum(exact_face[y0:y1, x0:x1], strict, out=exact_face[y0:y1, x0:x1])

    # The parser works at 512 on the crop, so its boundary is a step at full
    # resolution. A short blur turns it into a ramp the displacement can
    # stretch. The face mask is grown slightly first so the ramp falls outside
    # the face rather than eating into it: the requirement is that no face
    # pixel moves, so this side of the boundary has to err outwards.
    sigma = max(1.0, max(height, width) * 0.0015)
    # Grow by the full reach of the blur, not by one sigma. A Gaussian spreads
    # about three sigma, so dilating by one left two thirds of the ramp sitting
    # inside the face: measured on real portraits, face pixels were taking a
    # gate of up to 0.49 where the requirement is exactly zero. The ramp has to
    # land entirely outside the face for "no face pixel moves" to be true.
    grow = max(1, int(round(sigma * 3.0)))
    still = cv2.dilate(still, np.ones((grow * 2 + 1,) * 2, np.uint8))
    still = cv2.GaussianBlur(still, (0, 0), sigmaX=sigma)
    # Put the parser's own answer back at full strength. Dilating before the
    # blur pushes the ramp off the face but leaves the Gaussian's tail on it,
    # which measured as a gate of 0.0009 where the promise is zero. Re-asserting
    # the raw classes makes every pixel the parser called face exactly 1.0 here,
    # so the weight it receives downstream is exactly the number in Settings.
    still = np.maximum(still, exact_face)
    moving = cv2.GaussianBlur(moving, (0, 0), sigmaX=sigma)
    # Where they overlap after blurring, still wins.
    moving = np.clip(moving - still, 0.0, 1.0)
    return still, moving
