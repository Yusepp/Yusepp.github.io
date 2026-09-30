"""
Extract the example photos embedded in the PeqEMO paper PDF into projects/peqemo/media/.

    python scripts/media/extract_photos.py path/to/paper.pdf

Writes <name>.jpg (max 1600 px) + <name>.webp for each photo below. Figure-5 failure cases are
embedded as whole panels (title + photo + text), so the photo rectangle is cropped automatically.
"""

import sys
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "projects" / "peqemo" / "media"

# (output name, PDF page, index among that page's embedded images, crop panel?)
PHOTOS = [
    ("explore-pansies", 31, 0, False),
    ("explore-interior", 32, 0, False),
    ("explore-monkey", 33, 0, False),
    ("explore-team", 34, 0, False),
    ("success-couple", 9, 0, False),
    ("success-dogs", 9, 1, False),
    ("failure-dinosaur", 9, 2, True),
    ("failure-grid", 9, 3, True),
    ("failure-clown", 9, 4, True),
]

MAX_SIDE = 1600


def photo_bbox(img, dense=0.6):
    """Bounding box of the photo inside a white panel. The photo is the longest unbroken run of
    mostly non-white rows; text lines above/below have blank rows between them, so they're excluded."""
    small = img.convert("L").resize((img.width // 4, img.height // 4))
    w, h = small.size
    px = small.load()
    ink = lambda v: v < 235
    dense_row = [sum(ink(px[x, y]) for x in range(w)) > 0.3 * w for y in range(h)]
    best, start = (0, 0), None
    for y, d in enumerate(dense_row + [False]):
        if d and start is None:
            start = y
        elif not d and start is not None:
            if y - start > best[1] - best[0]:
                best = (start, y)
            start = None
    y0, y1 = best[0], best[1] - 1
    # columns measured only within the photo rows
    cols = [x for x in range(w) if sum(ink(px[x, y]) for y in range(y0, y1 + 1)) > dense * (y1 - y0 + 1)]
    return (min(cols) * 4 + 4, y0 * 4 + 4, (max(cols) + 1) * 4 - 4, (y1 + 1) * 4 - 4)


def main(pdf):
    reader = PdfReader(pdf)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, page, idx, crop in PHOTOS:
        img = reader.pages[page - 1].images[idx].image.convert("RGB")
        if crop:
            img = img.crop(photo_bbox(img))
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
        img.save(OUT / f"{name}.jpg", quality=88, optimize=True, progressive=True)
        img.save(OUT / f"{name}.webp", quality=82, method=6)
        print(f"{name}: {img.size[0]}x{img.size[1]}")


if __name__ == "__main__":
    main(sys.argv[1])
