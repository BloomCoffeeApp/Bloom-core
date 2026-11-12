"""Generates the installable-app (PWA) icons from build/icon.png into frontend/public/icons/.

- icon-192.png / icon-512.png: the logo as is (transparent corners), purpose "any".
- maskable-512.png: the logo at 80 % on the brand background (Android crops it to a circle/squircle).
- apple-touch-icon.png (180): opaque, iOS doesn't support transparency on the home screen.

Run after changing the logo: backend/.venv/Scripts/python build/make_pwa_icons.py
"""

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "build" / "icon.png"
OUT = ROOT / "frontend" / "public" / "icons"
BRAND = json.loads((ROOT / "brand.json").read_text(encoding="utf-8"))


def rgb(hex_color: str) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def on_background(logo: Image.Image, size: int, scale: float, color: tuple[int, int, int, int]) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), color)
    inner = round(size * scale)
    canvas.alpha_composite(logo.resize((inner, inner), Image.LANCZOS), ((size - inner) // 2, (size - inner) // 2))
    return canvas


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    logo = Image.open(SRC).convert("RGBA")
    for size in (192, 512):
        logo.resize((size, size), Image.LANCZOS).save(OUT / f"icon-{size}.png", optimize=True)
    bg = rgb(BRAND["colors"]["primary"])
    on_background(logo, 512, 0.8, bg).save(OUT / "maskable-512.png", optimize=True)
    on_background(logo, 180, 1.0, bg).convert("RGB").save(OUT / "apple-touch-icon.png", optimize=True)
    print(f"PWA icons written to {OUT}")


if __name__ == "__main__":
    main()
