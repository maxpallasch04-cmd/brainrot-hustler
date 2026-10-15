"""Still-frame cropping for the two-stage box detection.

Stage 1 finds the (big, high-contrast) scoreboard box on a full frame. Stage 2
crops *only* that box, upscales it, and lets the vision model find the sub-boxes
(name / score / list) inside it. The returned ``offset`` is the crop origin in the
original frame — add it to stage-2 coordinates to get full-frame boxes.
"""

from __future__ import annotations

from pathlib import Path


def crop_frame(path, box, out, *, scale: float = 2.0, pad: int = 0) -> dict:
    """Crop ``box`` (x, y, w, h) out of a still image, optionally scale/pad it.

    Returns ``{path, size, box, offset, scale}``. ``offset`` = (x, y) of the
    returned crop inside the original image.
    """
    from PIL import Image

    img = Image.open(str(path))
    width, height = img.size
    x, y, w, h = (int(v) for v in box)

    x = max(0, min(x, width - 2))
    y = max(0, min(y, height - 2))
    w = max(2, min(w, width - x))
    h = max(2, min(h, height - y))

    if pad:
        x = max(0, x - int(pad))
        y = max(0, y - int(pad))
        w = min(width - x, w + 2 * int(pad))
        h = min(height - y, h + 2 * int(pad))

    crop = img.crop((x, y, x + w, y + h))
    if scale and float(scale) != 1.0:
        crop = crop.resize((max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
                           Image.LANCZOS)

    if out:
        target = Path(out)
        target.parent.mkdir(parents=True, exist_ok=True)
        crop.save(str(target))
    return {"path": str(out) if out else None, "size": list(crop.size),
            "box": [x, y, w, h], "offset": [x, y], "scale": float(scale)}


def map_back(box, offset, scale: float = 1.0) -> list[int]:
    """Map a box found *in the crop* back to full-frame coordinates."""
    x, y, w, h = (float(v) for v in box)
    ox, oy = (float(v) for v in offset)
    s = float(scale) or 1.0
    return [int(round(ox + x / s)), int(round(oy + y / s)),
            int(round(w / s)), int(round(h / s))]
