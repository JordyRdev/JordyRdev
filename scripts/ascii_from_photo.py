#!/usr/bin/env python3
"""Turn a photo into the ASCII portrait used on the profile card.

  pip install pillow numpy opencv-python-headless rembg onnxruntime
  python scripts/ascii_from_photo.py me.jpg     # writes assets/ascii.txt
  python scripts/profile.py                     # re-render the card

rembg removes the background (optional: without it the whole photo is used).
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

COLS, ROWS = 60, 36                     # matches ART_FONT in profile.py
RAMP = " .'`^,:;-~=+*xjk%#&$@"          # keep in sync with profile.py

im = Image.open(sys.argv[1]).convert("RGB")
try:
    from rembg import remove, new_session
    im = remove(im, session=new_session("u2net_human_seg"))
except ImportError:
    im.putalpha(255)
im = ImageOps.fit(im, (COLS * 22, ROWS * 40))  # crop to the art's aspect ratio
alpha = im.split()[-1]
mask = alpha.point(lambda p: 255 if p > 128 else 0)
L = im.convert("L")
try:  # local contrast keeps eyes / nose / beard readable
    import cv2
    L = Image.fromarray(cv2.createCLAHE(clipLimit=3.0, tileGridSize=(6, 6)).apply(np.asarray(L)))
except ImportError:
    pass
L = ImageEnhance.Sharpness(ImageOps.equalize(L, mask=mask)).enhance(2.0)

a = np.asarray(alpha.resize((COLS, ROWS), Image.BOX)) / 255
g = np.asarray(L.resize((COLS, ROWS), Image.BOX)) / 255
e = np.asarray(im.convert("L").filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(5))
               .resize((COLS, ROWS), Image.BOX)) / 255
e = np.clip(e / max(np.percentile(e[a > 0.5], 98), 1e-6), 0, 1)
v = np.clip(g + 0.15 * e, 0, 1)

lines = []
for y in range(ROWS):
    lines.append("".join(" " if a[y, x] < 0.45 else
                         RAMP[max(1, min(len(RAMP) - 1, int(v[y, x] * len(RAMP))))]
                         for x in range(COLS)).rstrip())
out = Path(__file__).resolve().parent.parent / "assets" / "ascii.txt"
out.write_text("\n".join(lines) + "\n")
print("\n".join(lines) + f"\n\nwrote {out}")
