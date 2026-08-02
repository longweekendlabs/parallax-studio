"""Per-body-part depth, for parallax that moves a figure's parts separately.

Depth Anything estimates a depth field. It has no idea what a person is, so
"stretch whatever is nearest" lands on walls, door frames and floors as
readily as on a subject -- measured on a room scene, that approach changed the
architecture 8.6x more than the person standing in it.

This module adds the two things the depth model cannot supply: where the
person is, and where their parts are. A segmentation mask confines the effect
to the figure, and pose landmarks place named control points on it. The depth
inside the figure is then rebuilt from those points, so chest, hips and legs
carry genuinely separate parallax rather than sliding as one cutout.

Both models are Apache-2.0, downloaded on first use like the depth model, and
run on the ONNX Runtime already in the build.
"""
from __future__ import annotations

import logging
from typing import Callable, NamedTuple

import cv2
import numpy as np
from PySide6.QtGui import QImage

from app.core.depth_model import (
    DepthModel,
    ensure_file,
    file_path,
    has_file,
    open_session,
)

logger = logging.getLogger(__name__)

SEGMENT_MODEL = DepthModel(
    id="selfie-segmentation",
    label="Person segmentation (0.5 MB)",
    url="https://huggingface.co/onnx-community/mediapipe_selfie_segmentation/resolve/main/onnx/model.onnx",
    filename="mediapipe-selfie-segmentation.onnx",
    approx_bytes=462_352,
    license="Apache-2.0",
    commercial_ok=True,
    note="Finds the person, so body relief never touches the background.",
)

POSE_MODEL = DepthModel(
    id="movenet-lightning",
    label="Pose landmarks (9 MB)",
    url="https://huggingface.co/onnx-community/movenet-lightning-web/resolve/main/onnx/model.onnx",
    filename="movenet-lightning.onnx",
    approx_bytes=9_366_903,
    license="Apache-2.0",
    commercial_ok=True,
    note="Locates shoulders, hips, knees and ankles to place the body parts.",
)

BODY_MODELS: tuple[DepthModel, ...] = (SEGMENT_MODEL, POSE_MODEL)

SEGMENT_SIZE = 256
POSE_SIZE = 192

# MoveNet's 17 COCO keypoints, in output order.
KEYPOINTS = (
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
)
MIN_CONFIDENCE = 0.3
# Below this the pose is too incomplete to place parts from.
MIN_KEYPOINTS = 8
# A figure smaller than this is not worth rebuilding; the feather would eat it.
MIN_PERSON_FRACTION = 0.01

# How much of the depth range the figure's own parts are allowed to span.
# Measured on a full-length photo the differential motion between chest and
# waist runs about 13px of a 1000px frame at 0.55, 21px at 1.30, with the
# sampling grid still clean throughout. The default sits high because subtle
# is not what this button is for; Settings exposes it per taste.
BODY_SPREAD = 1.10
# How much of the depth model's own within-figure detail to keep on top, so
# folds of clothing and the face do not go completely flat.
MODEL_DETAIL = 0.30

# Relative depth per control point, -1 furthest to +1 nearest. This table is
# the actual deliverable: it is what decides how each part moves.
#
# The values alternate down the body rather than ramping. A monotonic
# head-to-foot ramp reads as the whole figure tilting, because neighbouring
# parts still move almost together; alternating chest forward, waist back,
# hips forward, knees back gives adjacent parts opposing motion, which is what
# reads as parts bouncing against each other. Anatomical plausibility is
# secondary here -- this is a stylistic control, and the point is separation.
PART_DEPTHS: dict[str, float] = {
    "nose": 0.90,
    "left_eye": 0.80, "right_eye": 0.80,
    "left_ear": 0.20, "right_ear": 0.20,
    "left_shoulder": 0.30, "right_shoulder": 0.30,
    "chest": 1.00,
    "waist": -0.20,
    "pelvis": 0.60,
    "left_hip": 0.55, "right_hip": 0.55,
    "left_thigh": -0.10, "right_thigh": -0.10,
    "left_knee": 0.50, "right_knee": 0.50,
    "left_shin": -0.40, "right_shin": -0.40,
    "left_ankle": 0.20, "right_ankle": 0.20,
    "left_upper_arm": 0.40, "right_upper_arm": 0.40,
    "left_elbow": 0.45, "right_elbow": 0.45,
    "left_forearm": 0.70, "right_forearm": 0.70,
    "left_wrist": 1.00, "right_wrist": 1.00,
}


class Keypoint(NamedTuple):
    x: float
    y: float
    score: float


class BodyReliefUnavailable(RuntimeError):
    """Raised when the picture has no figure this can work on."""


def models_ready() -> bool:
    return all(has_file(model) for model in BODY_MODELS)


def _rgb(image: QImage) -> np.ndarray:
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    h, w = rgba.height(), rgba.width()
    arr = np.frombuffer(rgba.bits(), dtype=np.uint8).reshape((h, w, 4))
    return arr[:, :, :3].copy()


def person_mask(rgb: np.ndarray) -> np.ndarray:
    """Soft 0..1 person mask at the source resolution."""
    session = open_session(file_path(SEGMENT_MODEL), SEGMENT_MODEL.id)
    height, width = rgb.shape[:2]
    small = cv2.resize(rgb, (SEGMENT_SIZE, SEGMENT_SIZE), interpolation=cv2.INTER_LINEAR)
    # The export rescales to 0..1 and does no mean/std normalisation.
    tensor = np.transpose(small.astype(np.float32) / 255.0, (2, 0, 1))[None]
    name = session.get_inputs()[0].name
    out = session.run([session.get_outputs()[0].name], {name: tensor})[0]
    mask = np.squeeze(out).astype(np.float32)
    return cv2.resize(mask, (width, height), interpolation=cv2.INTER_LINEAR)


def pose_keypoints(rgb: np.ndarray) -> dict[str, Keypoint]:
    """Landmarks in pixel coordinates, keyed by name.

    MoveNet expects a square input, so the image is letterboxed rather than
    stretched: squashing a portrait to a square moves every joint and the
    landmarks come back in the wrong places.
    """
    session = open_session(file_path(POSE_MODEL), POSE_MODEL.id)
    height, width = rgb.shape[:2]
    side = max(height, width)
    canvas = np.zeros((side, side, 3), np.uint8)
    off_y, off_x = (side - height) // 2, (side - width) // 2
    canvas[off_y:off_y + height, off_x:off_x + width] = rgb

    square = cv2.resize(canvas, (POSE_SIZE, POSE_SIZE), interpolation=cv2.INTER_LINEAR)
    # This export takes uint8 NHWC with a fourth (alpha) channel.
    tensor = np.dstack([square, np.full((POSE_SIZE, POSE_SIZE, 1), 255, np.uint8)])[None]
    name = session.get_inputs()[0].name
    raw = session.run([session.get_outputs()[0].name], {name: tensor})[0]
    rows = np.squeeze(raw).reshape(-1, 3)

    found: dict[str, Keypoint] = {}
    for i, part in enumerate(KEYPOINTS):
        y_norm, x_norm, score = (float(v) for v in rows[i])
        if score < MIN_CONFIDENCE:
            continue
        found[part] = Keypoint(x_norm * side - off_x, y_norm * side - off_y, score)
    return found


def _midpoint(a: Keypoint, b: Keypoint, t: float = 0.5) -> Keypoint:
    return Keypoint(
        a.x + (b.x - a.x) * t,
        a.y + (b.y - a.y) * t,
        min(a.score, b.score),
    )


def _control_points(kp: dict[str, Keypoint]) -> dict[str, Keypoint]:
    """Landmarks plus the parts MoveNet has no keypoint for.

    There is no chest, waist, thigh or shin landmark, and those are exactly the
    regions worth separating, so they are interpolated between the joints that
    bracket them.
    """
    points = dict(kp)

    shoulders = [kp[s] for s in ("left_shoulder", "right_shoulder") if s in kp]
    hips = [kp[s] for s in ("left_hip", "right_hip") if s in kp]
    if shoulders and hips:
        shoulder_mid = shoulders[0] if len(shoulders) == 1 else _midpoint(*shoulders)
        hip_mid = hips[0] if len(hips) == 1 else _midpoint(*hips)
        points["chest"] = _midpoint(shoulder_mid, hip_mid, 0.25)
        points["waist"] = _midpoint(shoulder_mid, hip_mid, 0.62)
        points["pelvis"] = hip_mid

    for side in ("left", "right"):
        for name, a, b, t in (
            ("upper_arm", "shoulder", "elbow", 0.5),
            ("forearm", "elbow", "wrist", 0.5),
            ("thigh", "hip", "knee", 0.5),
            ("shin", "knee", "ankle", 0.45),
        ):
            first, second = f"{side}_{a}", f"{side}_{b}"
            if first in kp and second in kp:
                points[f"{side}_{name}"] = _midpoint(kp[first], kp[second], t)
    return points


def _segments(kp: dict[str, Keypoint]) -> list[tuple[Keypoint, Keypoint, float, float]]:
    """Body parts as bones: (start, end, depth, thickness multiplier).

    A limb is a region between two joints, not a point. Weighting by distance
    to a *point* gives every part a circular footprint, and a torso covered in
    overlapping discs is exactly the blobby ripple this is meant to avoid --
    that was the visible failure of the first attempt. Distance to the bone
    segment instead gives each part a limb-shaped region.
    """
    bones: list[tuple[Keypoint, Keypoint, float, float]] = []

    def add(a: str, b: str, depth: float, thick: float = 1.0):
        if a in kp and b in kp:
            bones.append((kp[a], kp[b], depth, thick))

    shoulders = [kp[s] for s in ("left_shoulder", "right_shoulder") if s in kp]
    hips = [kp[s] for s in ("left_hip", "right_hip") if s in kp]
    if shoulders and hips:
        shoulder_mid = shoulders[0] if len(shoulders) == 1 else _midpoint(*shoulders)
        hip_mid = hips[0] if len(hips) == 1 else _midpoint(*hips)
        # The trunk is split rather than treated as one bone: chest against
        # waist against hips is the separation actually being asked for.
        chest_end = _midpoint(shoulder_mid, hip_mid, 0.42)
        waist_end = _midpoint(shoulder_mid, hip_mid, 0.78)
        bones.append((shoulder_mid, chest_end, PART_DEPTHS["chest"], 1.7))
        bones.append((chest_end, waist_end, PART_DEPTHS["waist"], 1.5))
        bones.append((waist_end, hip_mid, PART_DEPTHS["pelvis"], 1.6))

    for side in ("left", "right"):
        add(f"{side}_shoulder", f"{side}_elbow", PART_DEPTHS["left_upper_arm"], 0.7)
        add(f"{side}_elbow", f"{side}_wrist", PART_DEPTHS["left_forearm"], 0.6)
        add(f"{side}_hip", f"{side}_knee", PART_DEPTHS["left_thigh"], 1.0)
        add(f"{side}_knee", f"{side}_ankle", PART_DEPTHS["left_shin"], 0.8)

    for eye in ("nose", "left_eye", "right_eye"):
        if eye in kp:
            bones.append((kp[eye], kp[eye], PART_DEPTHS["nose"], 0.9))
            break
    return bones


def _relief_field(
    bones: list[tuple[Keypoint, Keypoint, float, float]],
    shape: tuple[int, int],
    span: float,
) -> np.ndarray:
    """Paint each bone's depth over the region around it.

    Weight falls off with distance to the bone *segment*, so a thigh covers a
    thigh-shaped band rather than a disc at its midpoint. Weights are blended
    rather than winner-takes-all, which keeps the joins smooth and leaves no
    seam for the feather to have to fix.
    """
    height, width = shape
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    base_sigma = max(3.0, span * 0.085)

    total = np.zeros((height, width), np.float32)
    weight = np.zeros((height, width), np.float32)
    for start, end, depth, thick in bones:
        ax, ay, bx, by = start.x, start.y, end.x, end.y
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        if length_sq < 1e-6:
            dist_sq = (xx - ax) ** 2 + (yy - ay) ** 2
        else:
            # Project each pixel onto the segment, clamped to its ends.
            t = np.clip(((xx - ax) * dx + (yy - ay) * dy) / length_sq, 0.0, 1.0)
            dist_sq = (xx - (ax + t * dx)) ** 2 + (yy - (ay + t * dy)) ** 2
        sigma = base_sigma * thick
        w = np.exp(-dist_sq / (2.0 * sigma * sigma))
        w *= min(start.score, end.score)
        total += w * depth
        weight += w

    # Coverage says how strongly any bone actually reaches a pixel. Without it
    # the normalise below paints the whole frame with the nearest bone's depth,
    # and a second person in shot -- who has no bones, because the pose model
    # only finds one figure -- gets flooded with the first person's values.
    coverage = np.clip(weight / 0.35, 0.0, 1.0)
    return total / np.maximum(weight, 1e-6), coverage


def body_part_depth(
    image: QImage, base_depth: np.ndarray, strength: float | None = None
) -> np.ndarray:
    """Rebuild the depth inside a figure from its pose.

    ``base_depth`` is the depth model's output, already normalised 0..1. The
    figure keeps the distance the depth model gave it, so it still sits
    correctly in the scene; only its internal shape is replaced.
    """
    rgb = _rgb(image)
    height, width = rgb.shape[:2]

    mask = person_mask(rgb)
    if float((mask > 0.5).mean()) < MIN_PERSON_FRACTION:
        raise BodyReliefUnavailable(
            "No person found in this image. Body Relief needs a visible figure."
        )

    kp = pose_keypoints(rgb)
    if len(kp) < MIN_KEYPOINTS:
        raise BodyReliefUnavailable(
            f"Only {len(kp)} body landmarks were confident enough to use. "
            "Body Relief needs a mostly unobstructed figure."
        )

    ys = [p.y for p in kp.values()]
    xs = [p.x for p in kp.values()]
    span = max(max(ys) - min(ys), max(xs) - min(xs), 1.0)

    bones = _segments(kp)
    if not bones:
        raise BodyReliefUnavailable(
            "Found a figure but could not place its limbs. Body Relief needs "
            "the torso and at least one arm or leg visible."
        )

    # Built on a proxy: the field is smooth by construction, and the distance
    # loop costs one full-resolution array per bone otherwise.
    scale = min(1.0, 384.0 / max(height, width))
    small_shape = (max(1, int(height * scale)), max(1, int(width * scale)))
    scaled = [
        (
            Keypoint(a.x * scale, a.y * scale, a.score),
            Keypoint(b.x * scale, b.y * scale, b.score),
            depth,
            thick,
        )
        for a, b, depth, thick in bones
    ]
    field, coverage = _relief_field(scaled, small_shape, span * scale)
    if scale < 1.0:
        field = cv2.resize(field, (width, height), interpolation=cv2.INTER_LINEAR)
        coverage = cv2.resize(coverage, (width, height), interpolation=cv2.INTER_LINEAR)

    # Keep the figure where the depth model put it, and give it the pose field
    # for its shape. A little of the model's own within-figure detail rides on
    # top so faces and clothing folds do not go completely flat.
    solid = mask > 0.5
    centre = float(np.median(base_depth[solid]))
    detail = base_depth - cv2.GaussianBlur(
        base_depth, (0, 0), sigmaX=max(1.0, span * 0.10)
    )
    spread = BODY_SPREAD if strength is None else max(0.05, float(strength))
    rebuilt = centre + field * spread + detail * MODEL_DETAIL

    # Only where the pose actually reaches. Elsewhere -- background, and any
    # figure the pose model did not find -- the depth model's map stands.
    apply = mask * coverage
    blended = base_depth * (1.0 - apply) + rebuilt * apply
    lo, hi = (float(v) for v in np.percentile(blended, (2.0, 98.0)))
    if hi - lo < 1e-6:
        return base_depth
    logger.info(
        "Body relief: %d landmarks, %d bones, figure %.1f%% of frame, spread %.2f",
        len(kp), len(bones), float(solid.mean()) * 100, spread,
    )
    # Surfaced in the status bar, so a run that quietly did nothing is
    # distinguishable from one that worked.
    body_part_depth.last_report = (
        f"{len(kp)} landmarks, {len(bones)} body parts, "
        f"figure {float(solid.mean()) * 100:.0f}% of frame"
    )
    return np.clip((blended - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)
