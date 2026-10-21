"""Render Vacuula map JSON (run-length-encoded grids) to a PNG."""

from __future__ import annotations

from collections import Counter
from io import BytesIO
from typing import Any

# Floor legend from the server: 0 unknown, 1 free, 2 wall.
_PALETTE = {
    0: (0, 0, 0),  # unknown: transparent
    1: (58, 58, 66),  # free floor
    2: (235, 235, 240),  # wall
    3: (239, 68, 68),  # cleaned path
}
_PATH_INDEX = 3
_PAD = 8
_TARGET = 640
_MAX_SCALE = 8


def _expand_floor(rle: list[Any], size: int) -> bytearray:
    buf = bytearray()
    for pair in rle:
        value, count = int(pair[0]), int(pair[1])
        buf.extend(bytes([value if 0 <= value <= 2 else 0]) * count)
    buf.extend(bytes(max(0, size - len(buf))))
    return buf[:size]


def _expand_path_mask(rle: list[Any], size: int) -> bytearray:
    """1 where the robot drove, 0 elsewhere (background = most common value)."""
    totals: Counter[int] = Counter()
    for pair in rle:
        totals[int(pair[0])] += int(pair[1])
    if not totals:
        return bytearray(size)
    background = totals.most_common(1)[0][0]
    buf = bytearray()
    for pair in rle:
        flag = 0 if int(pair[0]) == background else 1
        buf.extend(bytes([flag]) * int(pair[1]))
    buf.extend(bytes(max(0, size - len(buf))))
    return buf[:size]


def render_map(floor: dict[str, Any], path: dict[str, Any] | None = None) -> bytes | None:
    """Return PNG bytes for a floor map, optionally with the run path on top."""
    from PIL import Image  # Pillow ships with Home Assistant

    try:
        width, height = int(floor["width"]), int(floor["height"])
        pixels = _expand_floor(floor["rle"], width * height)
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    if width <= 0 or height <= 0:
        return None

    if path:
        try:
            pw, ph = int(path["width"]), int(path["height"])
            mask = _expand_path_mask(path["rle"], pw * ph)
            if (pw, ph) != (width, height):
                mask_img = Image.frombytes("L", (pw, ph), bytes(mask))
                mask = bytearray(
                    mask_img.resize((width, height), Image.Resampling.NEAREST).tobytes()
                )
            pixels = bytearray(
                _PATH_INDEX if m else f for f, m in zip(pixels, mask)
            )
        except (KeyError, TypeError, ValueError, IndexError):
            pass  # no usable path: show the plain map

    image = Image.frombytes("P", (width, height), bytes(pixels))
    palette: list[int] = []
    for index in range(256):
        palette.extend(_PALETTE.get(index, (0, 0, 0)))
    image.putpalette(palette)
    image.info["transparency"] = 0

    bbox = image.getbbox()
    if bbox is None:
        return None
    left, top, right, bottom = bbox
    image = image.crop(
        (
            max(0, left - _PAD),
            max(0, top - _PAD),
            min(width, right + _PAD),
            min(height, bottom + _PAD),
        )
    )
    scale = max(1, min(_MAX_SCALE, _TARGET // max(image.size)))
    rgba = image.convert("RGBA")
    if scale > 1:
        rgba = rgba.resize(
            (rgba.width * scale, rgba.height * scale), Image.Resampling.NEAREST
        )
    out = BytesIO()
    rgba.save(out, format="PNG")
    return out.getvalue()
