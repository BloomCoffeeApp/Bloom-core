"""Generates build/icon.ico + icon.png from the Bloom logo (mirrors frontend/public/logo.svg).

Colors come from brand.json. Run: backend/.venv/Scripts/python build/make_icon.py
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BRAND = json.loads((ROOT / "brand.json").read_text(encoding="utf-8"))


def rgb(hex_color: str) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


BG = rgb(BRAND["colors"]["primary"])
ACCENT = rgb(BRAND["colors"]["accent"])
FG = rgb(BRAND["colors"]["background"])
SS = 8  # supersampling factor for smooth edges


def draw(size: int) -> Image.Image:
    big = size * SS
    u = big / 64  # 1 unit of the 64x64 SVG viewBox
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, big - 1, big - 1], radius=14 * u, fill=BG)

    # flower: 5 petals rotated around (32, 20)
    cx, cy = 32 * u, 20 * u
    for i in range(5):
        layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        ImageDraw.Draw(layer).ellipse([cx - 3.7 * u, cy - 12.4 * u, cx + 3.7 * u, cy], fill=FG)
        img.alpha_composite(layer.rotate(-72 * i, center=(cx, cy), resample=Image.BICUBIC))
    d = ImageDraw.Draw(img)
    d.ellipse([cx - 3.2 * u, cy - 3.2 * u, cx + 3.2 * u, cy + 3.2 * u], fill=ACCENT)

    # cup, handle, saucer
    d.rounded_rectangle([15 * u, 26 * u, 47 * u, 50 * u], radius=12 * u, fill=FG)
    d.rectangle([15 * u, 26 * u, 47 * u, 33 * u], fill=BG)
    d.rectangle([15 * u, 33 * u, 47 * u, 40 * u], fill=FG)
    d.rounded_rectangle([44 * u, 34 * u, 56 * u, 47 * u], radius=6 * u, outline=FG, width=int(3 * u))
    d.rectangle([40 * u, 33 * u, 46 * u, 48 * u], fill=FG)
    d.rounded_rectangle([11 * u, 52.5 * u, 51 * u, 55.5 * u], radius=1.5 * u, fill=FG)
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    out = Path(__file__).with_name("icon.ico")
    base = draw(256)
    base.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    base.save(out.with_name("icon.png"))
    base.save(ROOT / "frontend" / "public" / "icon-256.png")
    print(f"wrote {out}")
