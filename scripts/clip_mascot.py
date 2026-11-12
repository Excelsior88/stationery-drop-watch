#!/usr/bin/env python3
"""Place the approved Stationery Drop Watch mascot, Clip, on a social graphic.

Uses only the locked v2 art in /workspace/dropwatch/mascot/v2/ (png-transparent).
Never redraw or restyle him. Callers pick a pose or pass a post kind:

  cheer   — back in stock / now available (including store batches)
  magnify — Stock Check
  sleepy  — sold out
  sign    — announcements or sign text
  wave    — general default

Keep him small, in a corner or margin, and off product names, prices,
store names, the footer tagline and the URL.

Future daily-post compose scripts should import place() or place_for_kind()
from this module rather than copying the PNG in by hand.
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

ART_DIR = Path(os.environ.get(
    "CLIP_MASCOT_DIR",
    "/workspace/dropwatch/mascot/v2/png-transparent",
))

POSES = {
    "master": "sdw-mascot_0master_transparent_1210x2433.png",
    "wave": "sdw-mascot_wave_transparent_1797x2659.png",
    "cheer": "sdw-mascot_cheer_transparent_1797x2659.png",
    "magnify": "sdw-mascot_magnify_transparent_1797x2659.png",
    "sleepy": "sdw-mascot_sleepy_transparent_1797x2659.png",
    "sign": "sdw-mascot_sign_transparent_1797x2659.png",
}

# Post kinds the automatic renderers pass in. Anything else falls back to wave.
_CHEER = frozenset({
    "restock", "new", "new_availability", "now_available",
    "back_in_stock", "store_batch",
})
_MAGNIFY = frozenset({"stock_check", "stockcheck"})
_SLEEPY = frozenset({"sold_out", "soldout"})
_SIGN = frozenset({"announcement", "sign"})

# Default placement on the 1080x1080 alert cards (footer is 70px).
# Heights are the visible (opaque) sprite, about 30–40% larger than the first pass
# (172→230 and 140→190) so he reads clearly without covering facts.
ALERT_FOOTER_H = 70
ALERT_HEIGHT = 230          # visible px; still fits the single-alert left margin
BATCH_HEIGHT = 190          # batch card is wider, so he sits in the left sage
                            # above the item list, not on top of the last row
ALERT_LEFT = 12
BATCH_LEFT = 2              # flush to the left outer margin; the card is wide
BATCH_BOTTOM_INSET = 8      # feet sit on the footer bar, left of the URL
BOTTOM_GAP = 6              # sage gap between Clip's feet and the footer bar (singles)
OPAQUE_ALPHA = 8


def pose_for(kind: str | None) -> str:
    key = (kind or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key in _CHEER:
        return "cheer"
    if key in _MAGNIFY:
        return "magnify"
    if key in _SLEEPY:
        return "sleepy"
    if key in _SIGN:
        return "sign"
    return "wave"


def art_path(pose: str) -> Path:
    if pose not in POSES:
        raise ValueError(f"unknown Clip pose {pose!r}; choose one of {sorted(POSES)}")
    path = ART_DIR / POSES[pose]
    if not path.is_file():
        raise FileNotFoundError(
            f"approved Clip art missing: {path} (pose {pose!r})"
        )
    return path


def load_pose(pose: str) -> Image.Image:
    """RGBA sprite cropped to the opaque bounding box (padding stripped)."""
    im = Image.open(art_path(pose)).convert("RGBA")
    bbox = im.getchannel("A").point(lambda a: 255 if a > OPAQUE_ALPHA else 0).getbbox()
    if not bbox:
        raise ValueError(f"Clip pose {pose!r} has no visible pixels")
    return im.crop(bbox)


def scale_to_height(sprite: Image.Image, height: int) -> Image.Image:
    height = max(1, int(height))
    width = max(1, round(sprite.width * height / sprite.height))
    return sprite.resize((width, height), Image.LANCZOS)


def place(
    canvas: Image.Image,
    pose: str = "wave",
    *,
    corner: str = "bottom_left",
    height: int = ALERT_HEIGHT,
    left: int = ALERT_LEFT,
    bottom_gap: int = BOTTOM_GAP,
    footer_h: int = ALERT_FOOTER_H,
    top: int | None = None,
) -> tuple[int, int, int, int]:
    """Composite Clip onto an RGBA canvas. Returns the pasted box (x0, y0, x1, y1).

    `corner` is bottom_left or bottom_right. By default the sprite sits in that
    margin, `bottom_gap` pixels above the footer bar, and is never drawn over
    the footer itself (so the URL and any tagline stay clear). Pass `top` to
    set the y origin instead, e.g. to keep him in an outer margin above a
    wide batch card.
    """
    if canvas.mode != "RGBA":
        raise ValueError("clip_mascot.place expects an RGBA canvas")
    if corner not in ("bottom_left", "bottom_right"):
        raise ValueError(f"unsupported corner {corner!r}")
    sprite = scale_to_height(load_pose(pose), height)
    w, h = canvas.size
    footer_top = h - footer_h
    y = top if top is not None else footer_top - bottom_gap - sprite.height
    if y < 0 or y + sprite.height > h:
        raise ValueError("Clip does not fit vertically on the canvas")
    if top is None and y + sprite.height > footer_top:
        raise ValueError("Clip height does not fit above the footer")
    x = left if corner == "bottom_left" else w - left - sprite.width
    if x < 0 or x + sprite.width > w:
        raise ValueError("Clip width does not fit in the chosen margin")
    canvas.alpha_composite(sprite, (x, y))
    return (x, y, x + sprite.width, y + sprite.height)


def place_for_kind(canvas: Image.Image, kind: str, *, layout: str = "alert") -> tuple[int, int, int, int]:
    """Convenience for the automatic alert and store-batch renderers."""
    pose = pose_for(kind)
    if layout == "batch":
        # The item list is nearly full-width, so a 190px Clip parked above
        # the footer would cover the last row, and the headline gap is too
        # narrow for him. Stand him in the lower-left outer corner, feet on
        # the footer bar (well left of the URL) and body in the card's
        # decorative pink margin, not on the names or times.
        h = canvas.size[1]
        top = h - BATCH_BOTTOM_INSET - BATCH_HEIGHT
        return place(canvas, pose, height=BATCH_HEIGHT, left=BATCH_LEFT, top=top)
    if layout != "alert":
        raise ValueError(f"unsupported layout {layout!r}")
    return place(canvas, pose, height=ALERT_HEIGHT, left=ALERT_LEFT)
