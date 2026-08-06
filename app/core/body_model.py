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
from dataclasses import dataclass
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

POSE_LIGHTNING = DepthModel(
    id="movenet-lightning",
    label="MoveNet Lightning (9 MB, one person)",
    url="https://huggingface.co/onnx-community/movenet-lightning-web/resolve/main/onnx/model.onnx",
    filename="movenet-lightning.onnx",
    approx_bytes=9_366_903,
    license="Apache-2.0",
    commercial_ok=True,
    note="Fastest. Finds a single figure only; anyone else in shot is left alone.",
)

POSE_THUNDER = DepthModel(
    id="movenet-thunder",
    label="MoveNet Thunder (25 MB, one person, more accurate)",
    url="https://huggingface.co/Xenova/movenet-singlepose-thunder/resolve/main/onnx/model.onnx",
    filename="movenet-thunder.onnx",
    approx_bytes=25_067_197,
    license="Apache-2.0",
    commercial_ok=True,
    note="Places joints more precisely than Lightning. Still one figure only.",
)

POSE_MULTIPOSE = DepthModel(
    id="movenet-multipose",
    label="MoveNet MultiPose (19 MB, up to 6 people)",
    url="https://huggingface.co/Xenova/movenet-multipose-lightning/resolve/main/onnx/model.onnx",
    filename="movenet-multipose.onnx",
    approx_bytes=19_049_169,
    license="Apache-2.0",
    commercial_ok=True,
    note="Recommended. Gives every figure in the frame its own body parts.",
)


@dataclass(frozen=True)
class PoseSpec:
    """Each export wants a different input, so carry it with the model."""

    model: DepthModel
    size: int
    dtype: type
    channels: int
    multi: bool


POSE_SPECS: dict[str, PoseSpec] = {
    POSE_LIGHTNING.id: PoseSpec(POSE_LIGHTNING, 192, np.uint8, 4, False),
    POSE_THUNDER.id: PoseSpec(POSE_THUNDER, 256, np.int32, 3, False),
    POSE_MULTIPOSE.id: PoseSpec(POSE_MULTIPOSE, 256, np.int32, 3, True),
}
POSE_MODELS: tuple[DepthModel, ...] = tuple(spec.model for spec in POSE_SPECS.values())
DEFAULT_POSE = POSE_MULTIPOSE.id

SEGMENT_SIZE = 256
# A person smaller than this fraction of the frame is skipped: below it the
# joints are too close together for the parts to survive the feather.
MIN_FIGURE_SPAN = 0.12

# MoveNet's 17 COCO keypoints, in output order.
KEYPOINTS = (
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
)
MIN_CONFIDENCE = 0.3
# Below this the pose is too incomplete to place parts from. Portrait crops,
# which is most of what this gets pointed at, routinely return only the head
# and shoulders: measured across a set of them, a figure filling 60% of the
# frame was rejected on 7 of 17 joints. What actually matters is whether a
# trunk can be built, and the "could not place its limbs" guard downstream
# already checks exactly that, so this only has to exclude noise.
MIN_KEYPOINTS = 5
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


# How far forward hair sits relative to the figure's own centre. Hair has no
# joints, so there is nothing in the pose to place it from; it gets one value
# of its own. It is high because hair against a face that is pinned still is
# the clearest read of "this is bouncing" a still photo can give.
HAIR_RELIEF = 0.85

# How far the background setting stretches the scene's own depth around its
# median at full strength. This deliberately amplifies what the depth model
# already found rather than rebuilding anything: there are no joints out there
# to place parts from, and flattening a room onto the figure's plane would be
# the same "background drags along with the subject" fault from the other side.
BACKGROUND_SPREAD = 0.60


class Keypoint(NamedTuple):
    x: float
    y: float
    score: float


@dataclass(frozen=True)
class ReliefWeights:
    """How much of the relief each region of the picture is allowed to take.

    Which parts of a person should move is a taste decision, so it belongs to
    the user rather than being decided here. Zero means a region keeps exactly
    the depth the depth model gave it, so it moves with the scene and not
    against it.
    """

    face: float = 0.0
    hair: float = 0.85
    body: float = 1.0
    # Off by default. Body Relief is for moving a person, and a background that
    # drifts along with them is the artefact this module was written to remove.
    # Raising it deliberately is a different thing: it deepens the scene the
    # figure is standing in, rather than dragging the scene with the figure.
    background: float = 0.0

    @classmethod
    def from_settings(cls, settings) -> "ReliefWeights":
        def read(name: str, default: float) -> float:
            return max(0.0, min(1.0, float(getattr(settings, name, default))))

        return cls(
            face=read("relief_face", 0.0),
            hair=read("relief_hair", 0.85),
            body=read("relief_body", 1.0),
            background=read("relief_background", 0.0),
        )


class BodyReliefUnavailable(RuntimeError):
    """Raised when the picture has no figure this can work on."""


def pose_spec(pose_id: str) -> PoseSpec:
    return POSE_SPECS.get(pose_id, POSE_SPECS[DEFAULT_POSE])


def required_models(pose_id: str) -> tuple[DepthModel, ...]:
    from app.core.face_parser import FACE_PARSER

    return (SEGMENT_MODEL, pose_spec(pose_id).model, FACE_PARSER)


def models_ready(pose_id: str = DEFAULT_POSE) -> bool:
    return all(has_file(m) for m in required_models(pose_id))


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


def pose_people(rgb: np.ndarray, pose_id: str) -> list[dict[str, Keypoint]]:
    """Landmarks per figure, in pixel coordinates.

    The image is letterboxed into a square rather than stretched: squashing a
    portrait moves every joint and the landmarks come back in the wrong places.
    """
    spec = pose_spec(pose_id)
    session = open_session(file_path(spec.model), spec.model.id)
    height, width = rgb.shape[:2]
    side = max(height, width)
    canvas = np.zeros((side, side, 3), np.uint8)
    off_y, off_x = (side - height) // 2, (side - width) // 2
    canvas[off_y:off_y + height, off_x:off_x + width] = rgb

    square = cv2.resize(canvas, (spec.size, spec.size), interpolation=cv2.INTER_LINEAR)
    if spec.channels == 4:
        square = np.dstack([square, np.full((spec.size, spec.size, 1), 255, np.uint8)])
    tensor = square[None].astype(spec.dtype)
    raw = session.run(
        [session.get_outputs()[0].name], {session.get_inputs()[0].name: tensor}
    )[0]

    # Single-pose exports give (1, 1, 17, 3); MultiPose gives (1, 6, 56), where
    # each row is 17 keypoints followed by a bounding box and its score.
    rows = np.squeeze(raw)
    people_raw = (
        [r[:51].reshape(17, 3) for r in rows.reshape(-1, 56)]
        if spec.multi
        else [rows.reshape(17, 3)]
    )

    people: list[dict[str, Keypoint]] = []
    for kp_raw in people_raw:
        found: dict[str, Keypoint] = {}
        for i, part in enumerate(KEYPOINTS):
            y_norm, x_norm, score = (float(v) for v in kp_raw[i])
            if score < MIN_CONFIDENCE:
                continue
            found[part] = Keypoint(x_norm * side - off_x, y_norm * side - off_y, score)
        if len(found) < MIN_KEYPOINTS:
            continue
        ys = [p.y for p in found.values()]
        xs = [p.x for p in found.values()]
        span = max(max(ys) - min(ys), max(xs) - min(xs))
        if span < side * MIN_FIGURE_SPAN:
            continue
        people.append(found)
    return people


def _smoothstep(value: np.ndarray, low: float, high: float) -> np.ndarray:
    """0 at or below ``low``, 1 at or above ``high``, smooth in between.

    Reaches its limits exactly, which a Gaussian falloff never does. That is
    the whole point here: "leave the background alone" has to mean untouched,
    not nearly untouched.
    """
    t = np.clip((value - low) / max(high - low, 1e-6), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _midpoint(a: Keypoint, b: Keypoint, t: float = 0.5) -> Keypoint:
    return Keypoint(
        a.x + (b.x - a.x) * t,
        a.y + (b.y - a.y) * t,
        min(a.score, b.score),
    )


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

    if shoulders and not hips:
        # A portrait crop: the hips are simply not in the picture. This is the
        # common case for the photographs this gets pointed at, and refusing it
        # left the whole feature unavailable on them. Shoulder width is the one
        # scale the pose still offers, and a torso runs roughly 1.6 of it, so
        # the trunk is carried down that far along the head-to-shoulder axis.
        # Using that axis rather than straight down keeps a leaning or reclining
        # figure's trunk on the figure.
        head = [kp[n] for n in ("nose", "left_eye", "right_eye") if n in kp]
        shoulder_mid = shoulders[0] if len(shoulders) == 1 else _midpoint(*shoulders)
        if len(shoulders) == 2:
            width = max(
                1.0,
                ((shoulders[0].x - shoulders[1].x) ** 2
                 + (shoulders[0].y - shoulders[1].y) ** 2) ** 0.5,
            )
        else:
            width = 1.0
        if head and width > 1.0:
            hx = sum(p.x for p in head) / len(head)
            hy = sum(p.y for p in head) / len(head)
            dx, dy = shoulder_mid.x - hx, shoulder_mid.y - hy
            length = max(1e-6, (dx * dx + dy * dy) ** 0.5)
            reach = width * 1.6
            hips = [
                Keypoint(
                    shoulder_mid.x + dx / length * reach,
                    shoulder_mid.y + dy / length * reach,
                    min(p.score for p in shoulders),
                )
            ]

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

    # No head bone. Displacing a face by an amount of its own tears the
    # features apart and it is the first thing the eye goes to, so the head
    # keeps whatever depth the model gave it and simply travels with the body.
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
    # Sized to a limb's thickness, not the whole figure. At 8.5% of the figure
    # the three trunk bones -- only ~11% of it apart -- averaged into each
    # other and the field delivered a chest/waist gap of 0.11 where the table
    # asked for 1.20. At 3% it delivers 0.93, and the final map carries 6.9x
    # more separation between the parts.
    base_sigma = max(3.0, span * 0.030)

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


def _suggest_motion(
    depth: np.ndarray,
    solid: np.ndarray,
    people: list[dict[str, Keypoint]],
    span_fraction: float,
    centre: float,
) -> dict[str, float]:
    """Motion settings derived from this particular scene.

    Fixed values would be wrong for most pictures: a head-and-shoulders crop
    and a full-length figure across a room need very different travel to read
    the same. Everything here comes off the picture.
    """
    # Focus is the plane that does not move. Left mid-frame it sits behind the
    # figure, so every part is on the same side of it and they all slide
    # together, differing only in amount. On the figure's own median depth the
    # chest is in front and the hips behind, and they travel opposite ways.
    # The plane everything was pulled onto, so a region given zero weight sits
    # exactly on it and does not move. This has to be the same number
    # body_part_depth used as its centre, or the regions meant to be still
    # acquire travel again from the mismatch.
    focus = float(centre)

    # How the figure sits in frame. A wide pose -- seated, arms out, reclining
    # -- has parts spread across both axes and can carry vertical travel; a
    # narrow standing figure only reads sideways.
    widths, heights = [], []
    for kp in people:
        xs = [pt.x for pt in kp.values()]
        ys = [pt.y for pt in kp.values()]
        widths.append(max(xs) - min(xs))
        heights.append(max(ys) - min(ys))
    aspect = (max(widths) / max(max(heights), 1.0)) if widths else 0.5

    # A figure filling the frame needs less travel than a distant one: the same
    # pixel offset reads as far more movement when the subject is large.
    fill = min(1.0, max(0.05, span_fraction))
    return {
        "focus_depth": max(0.05, min(0.95, focus)),
        "motion_scale_x": 1.0,
        "motion_scale_y": float(min(0.75, max(0.12, aspect * 0.55))),
        # Eased back where the figure is largest, since zoom travels along the
        # same axis as the part separation, but never so far that the control
        # looks broken when the user goes to move it.
        "zoom_strength": float(max(0.20, 0.45 - 0.25 * fill)),
        "layer_intensity": float(min(0.85, max(0.38, 0.85 - 0.45 * fill))),
        "duration": float(min(7.5, max(2.5, 2.6 + 4.2 * fill))),
    }


def body_part_depth(
    image: QImage,
    base_depth: np.ndarray,
    strength: float | None = None,
    pose_id: str = DEFAULT_POSE,
    weights: ReliefWeights | None = None,
) -> np.ndarray:
    """Rebuild the depth inside a figure from its pose.

    ``base_depth`` is the depth model's output, already normalised 0..1. The
    figure keeps the distance the depth model gave it, so it still sits
    correctly in the scene; only its internal shape is replaced.
    """
    from app.core import face_parser

    weights = weights or ReliefWeights()
    rgb = _rgb(image)
    height, width = rgb.shape[:2]

    mask = person_mask(rgb)
    if float((mask > 0.5).mean()) < MIN_PERSON_FRACTION:
        raise BodyReliefUnavailable(
            "No person found in this image. Body Relief needs a visible figure."
        )

    people = pose_people(rgb, pose_id)
    if not people:
        # The three pose exports disagree on tight crops and unusual poses:
        # measured across a set of portraits, MultiPose missed a figure that
        # Thunder found. Refusing outright when another installed model would
        # have succeeded is a worse answer than trying it.
        for spare in POSE_SPECS:
            if spare == pose_id or not has_file(POSE_SPECS[spare].model):
                continue
            people = pose_people(rgb, spare)
            if people:
                logger.info("Pose %s found nothing; %s did", pose_id, spare)
                pose_id = spare
                break
    if not people:
        raise BodyReliefUnavailable(
            "Found a figure but not its pose. Body Relief needs a mostly "
            "unobstructed person, large enough in the frame to place joints on."
        )

    scale = min(1.0, 384.0 / max(height, width))
    small_shape = (max(1, int(height * scale)), max(1, int(width * scale)))

    # Every figure the pose model found gets its own bones, and they are
    # painted into one field. With a single-person model there is just the one.
    all_bones: list[tuple[Keypoint, Keypoint, float, float]] = []
    spans: list[float] = []
    heads: list[tuple[float, float, float]] = []
    for kp in people:
        bones = _segments(kp)
        if not bones:
            continue
        ys = [pt.y for pt in kp.values()]
        xs = [pt.x for pt in kp.values()]
        span = max(max(ys) - min(ys), max(xs) - min(xs), 1.0)
        spans.append(span)
        all_bones.extend(
            (
                Keypoint(a_.x * scale, a_.y * scale, a_.score),
                Keypoint(b_.x * scale, b_.y * scale, b_.score),
                depth,
                thick,
            )
            for a_, b_, depth, thick in bones
        )
        head = [kp[n] for n in ("nose", "left_eye", "right_eye", "left_ear", "right_ear") if n in kp]
        if head:
            hx = sum(pt.x for pt in head) / len(head)
            hy = sum(pt.y for pt in head) / len(head)
            # Sized from the landmarks themselves rather than a fraction of the
            # figure: those points sit around eye level and span roughly the
            # width of the face, so the whole head including jaw and hair is
            # about 2.6x their spread. The floor covers a profile shot, where
            # only one or two of them are found and the spread collapses.
            reach = max(
                (max(abs(pt.x - hx), abs(pt.y - hy)) for pt in head), default=0.0
            )
            # Sized from the face landmarks, never from the figure. The old
            # floor of span * 0.13 meant a full-length figure produced a head
            # box the size of its torso, and the parser, which is trained on
            # tight face crops, then labelled shirt as skin and the wall as
            # hair. Rendered as a region map that is unmistakable: a rectangular
            # block of "face" over the whole chest. The cap does the same job
            # from the other side for a pose whose landmarks came back spread.
            radius = max(reach * 2.6, span * 0.05)
            radius = min(radius, span * 0.30)
            heads.append((hx * scale, hy * scale, radius * scale))

    if not all_bones:
        raise BodyReliefUnavailable(
            "Found a figure but could not place its limbs. Body Relief needs "
            "the torso and at least one arm or leg visible."
        )
    span = max(spans)

    field, coverage = _relief_field(all_bones, small_shape, span * scale)

    if scale < 1.0:
        field = cv2.resize(field, (width, height), interpolation=cv2.INTER_LINEAR)
        coverage = cv2.resize(coverage, (width, height), interpolation=cv2.INTER_LINEAR)

    # Which pixels of a head are face and which are hair. Up to here the only
    # thing available was a circle drawn around the averaged face landmarks,
    # which is wrong in both directions at once: wide enough to cover hair it
    # swallows the jaw and neck, tight enough to fit the face it lets the
    # relief onto the forehead, and being one circle it could only ever
    # exclude hair along with the face. The parser labels them separately, so
    # the face can be pinned exactly while the hair moves.
    head_boxes = [(hx / scale, hy / scale, radius / scale) for hx, hy, radius in heads]
    face_mask, hair_mask = face_parser.head_masks((height, width), rgb, head_boxes)
    parsed = float(face_mask.max()) > 0.0
    if not parsed and heads:
        # No parser installed. Fall back to holding the whole head still,
        # which is the old behaviour: worse, because the hair stops moving
        # too, but never wrong in the direction that matters.
        yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
        for hx, hy, radius in head_boxes:
            distance = np.sqrt((xx - hx) ** 2 + (yy - hy) ** 2) / max(radius, 1e-6)
            face_mask = np.maximum(face_mask, 1.0 - _smoothstep(distance, 1.0, 1.8))
        logger.warning("Face parser not installed; holding whole heads still")


    # Keep the figures where the depth model put them, and give them the pose
    # field for their shape. A little of the model's own detail rides on top so
    # clothing folds do not go completely flat.
    solid = mask > 0.5
    centre = float(np.median(base_depth[solid]))
    detail = base_depth - cv2.GaussianBlur(
        base_depth, (0, 0), sigmaX=max(1.0, span * 0.10)
    )
    # The slider says how much separation the user wants; the picture says how
    # much of it reads. The same offset in depth is a strong effect on a
    # head-and-shoulders crop and barely visible on a full-length figure across
    # a room, so a fixed number is wrong for most photographs. Scale it by how
    # much of the frame the figure actually occupies.
    base_spread = BODY_SPREAD if strength is None else max(0.05, float(strength))
    fill = float(solid.mean())
    scene_scale = float(np.clip(1.35 - 0.85 * min(1.0, fill / 0.32), 0.65, 1.35))
    spread = base_spread * scene_scale
    # Hair has no joints, so the bone field says nothing about it. Give it one
    # value of its own, well forward of the figure's centre, so it travels
    # against a face that is not moving at all.
    field = field * (1.0 - hair_mask) + HAIR_RELIEF * hair_mask
    rebuilt = centre + field * spread + detail * MODEL_DETAIL

    # How much of the relief each pixel takes, built in two independent halves
    # so neither can undo the other.
    #
    # First, which region a pixel belongs to. These override in priority order,
    # each replacing rather than adding to what is under it, so a pixel ends up
    # carrying exactly one region's weight and the numbers in Settings mean
    # what they say. Face is applied last so it wins over everything: at its
    # default weight of zero this is exactly zero across every face pixel,
    # which is the one guarantee this function has to make.
    region = coverage * weights.body
    region = region * (1.0 - hair_mask) + hair_mask * weights.hair
    region = region * (1.0 - face_mask) + face_mask * weights.face

    # Second, the silhouette, as a hard outer clamp that nothing above can
    # reach past. It is tempting to let hair escape it, since selfie
    # segmentation does clip the odd flyaway strand, but a dark background
    # behind dark hair is precisely where the parser mislabels, and any escape
    # hatch turns that mislabel into a drifting background. Clipped strands
    # staying still is a far better failure than a moving background, so the
    # mask wins and hair keeps no exemption.
    apply = np.clip(_smoothstep(mask, 0.55, 0.85) * region, 0.0, 1.0)

    # Fit the rebuilt figure into the room available around its own depth,
    # rather than renormalising the finished map. A global renormalise was
    # rescaling every pixel in the frame, so changing the body quietly moved
    # the background with it -- measured, the background shifted by a third of
    # what the body did, on pixels this is supposed to leave alone.
    sel = apply > 0.05
    if sel.any():
        low, high = (float(v) for v in np.percentile(rebuilt[sel], (1.0, 99.0)))
        middle = (low + high) * 0.5
        have = (high - low) * 0.5
        room = max(0.05, min(centre, 1.0 - centre) * 0.95)
        if have > room:
            rebuilt = middle + (rebuilt - middle) * (room / have)

    blended = base_depth * (1.0 - apply) + rebuilt * apply

    # The background, separately and only when asked for. It gets no rebuild:
    # there are no joints out there to place parts from, and pushing it onto
    # the figure's plane would be the same "background drags along with the
    # subject" fault seen from the other side. What it gets is more of the
    # depth the model already found, stretched around its own median, so a
    # room reads as deeper without the figure's motion bleeding into it.
    outside = 1.0 - _smoothstep(mask, 0.55, 0.85)
    bg_gate = outside * weights.background
    if weights.background > 0.0 and outside.max() > 0.0:
        far = outside > 0.5
        bg_centre = float(np.median(base_depth[far])) if far.any() else 0.5
        expanded = bg_centre + (base_depth - bg_centre) * (
            1.0 + BACKGROUND_SPREAD * weights.background
        )
        blended = blended * (1.0 - bg_gate) + np.clip(expanded, 0.0, 1.0) * bg_gate

    # Now the part that actually decides what moves.
    #
    # Leaving a region "unchanged" is not the same as leaving it still, and
    # confusing the two is what made every complaint about this feature true at
    # once. Displacement is (depth - focus), so a background the depth model put
    # far from the focus plane travels furthest of anything in the frame no
    # matter how carefully the relief was kept off it: measured on these
    # photographs, the background moved 60px and the face 51px while the chest
    # and hips moved 10 to 20. The relief was innocent and the animation was
    # still wrong.
    #
    # So every region is pulled onto the focus plane in proportion to how much
    # of the relief it was given. A weight of zero now means the region sits
    # exactly at focus and travels exactly zero pixels, which is what the
    # sliders in Settings have always looked like they promised.
    motion_weight = np.full((height, width), weights.background, dtype=np.float32)
    body_here = _smoothstep(mask, 0.55, 0.85)
    # Hair only counts where the silhouette agrees there is a person. On the
    # big-hair portraits the parser labels some of the background behind the
    # head as hair, and unclamped that handed 85% of the travel to pixels that
    # are not on anybody: measured, 4% of background moving with excursions of
    # 43px. Clipped strands going still is the better failure.
    hair_here = hair_mask * body_here
    motion_weight = motion_weight * (1.0 - body_here) + body_here * weights.body
    motion_weight = motion_weight * (1.0 - hair_here) + hair_here * weights.hair
    motion_weight = motion_weight * (1.0 - face_mask) + face_mask * weights.face
    blended = centre + (blended - centre) * motion_weight

    figure_frac = float(solid.mean())
    face_frac = float((face_mask > 0.5).mean())
    hair_frac = float((hair_mask > 0.5).mean())
    logger.info(
        "Body relief: %d figures, %d bones, %.1f%% of frame, spread %.2f "
        "(slider %.2f x scene %.2f), "
        "face %.2f%% at weight %.2f, hair %.2f%% at weight %.2f, parser %s",
        len(spans), len(all_bones), figure_frac * 100, spread,
        base_spread, scene_scale,
        face_frac * 100, weights.face, hair_frac * 100, weights.hair,
        "yes" if parsed else "no",
    )
    parts = [
        f"{len(spans)} figure{'s' if len(spans) != 1 else ''}",
        f"{len(all_bones)} body parts",
    ]
    if parsed:
        parts.append("face held still" if weights.face <= 0.0 else f"face {weights.face:.0%}")
        parts.append("hair still" if weights.hair <= 0.0 else f"hair {weights.hair:.0%}")
    else:
        parts.append("no face parser, whole head held still")
    body_part_depth.last_report = ", ".join(parts)
    result = np.clip(blended, 0.0, 1.0).astype(np.float32)
    # The gate goes back to the caller so the finished maps can be composited
    # through it. Everything downstream of here -- the feather in particular --
    # blurs across the silhouette, which would carry the figure's new values
    # out into the background however cleanly they were masked here.
    # The whole frame is authored now, not just the figure, so the caller keeps
    # all of it. The gate used to exist to stop the feather carrying the
    # figure's new values out across the silhouette into a background that had
    # been left alone; there is no longer a background being left alone to
    # protect, and the step at the silhouette is smaller than it was, because
    # both sides now sit near the same focus plane.
    body_part_depth.last_gate = np.ones((height, width), dtype=np.float32)

    # Where the answer is "this must not move", stated strongly enough to
    # survive the feather that runs after this function. Flattening a region
    # onto the focus plane is not enough on its own: the feather blurs across
    # the region's outline and drags its edge back off the plane, which
    # measured as 9 to 16px of travel on a rim around a face that is supposed
    # to be motionless. The caller re-asserts the plane through this map.
    #
    # Both terms are already ramped outside the region they protect: the face
    # mask was dilated by the full reach of its blur before being feathered,
    # and the silhouette term ramps across the segmentation's own soft edge. So
    # re-asserting through them introduces no step inside the region itself.
    still = face_mask * (1.0 - weights.face)
    still = np.maximum(still, (1.0 - body_here) * (1.0 - weights.background))
    still = np.minimum(still, 1.0 - hair_here * weights.hair)
    body_part_depth.last_still = np.clip(still, 0.0, 1.0).astype(np.float32)
    body_part_depth.suggested_motion = _suggest_motion(
        result, solid, people, span / max(height, width), centre
    )
    return result
