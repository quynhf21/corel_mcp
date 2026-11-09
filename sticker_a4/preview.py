"""Vẽ thử trang A4 ra PNG (không cần Corel) để kiểm tra bố cục.

python preview.py anh_goc_1.png preview.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from layout import PAGE_H, PAGE_W, Config, Layout, plan
from split_stickers import split_sheet


def render(stickers: list[Image.Image], lay: Layout, cfg: Config, dpi: int = 150) -> Image.Image:
    k = dpi / 25.4
    page = Image.new("RGB", (round(PAGE_W * k), round(PAGE_H * k)), "#d9d9d9")
    d = ImageDraw.Draw(page)
    # vùng 2 khối và đường cắt đôi
    for y0 in (cfg.top, cfg.top + cfg.block_h + cfg.cut_gap):
        d.rectangle([cfg.left * k, y0 * k, cfg.right * k, (y0 + cfg.block_h) * k], outline="#3b82f6")
    d.line([0, lay.cut_y * k, page.width, lay.cut_y * k], fill="#ef4444", width=2)
    for p in lay.placements:
        im = stickers[p.index]
        if p.rotated:
            im = im.rotate(-90, expand=True)
        im = im.resize((round(p.w * k), round(p.h * k)), Image.LANCZOS)
        page.paste(im, (round(p.x * k), round(p.y * k)), im)
        d.rectangle([p.x * k, p.y * k, (p.x + p.w) * k, (p.y + p.h) * k], outline="#10b981")
    return page


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("png", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--no-rotate", action="store_true")
    a = ap.parse_args()
    cfg = Config(allow_rotate=not a.no_rotate)
    st = split_sheet(a.png)
    lay = plan([s.image.size for s in st], cfg)
    render([s.image for s in st], lay, cfg).save(a.out)
    print("hàng:", lay.rows, "| đường cắt y =", round(lay.cut_y, 1), "mm")
    for p in lay.placements:
        print(f"  #{p.index + 1:2d} {p.w:5.1f} x {p.h:5.1f} mm{'  (xoay)' if p.rotated else ''}")
    for w in lay.warnings:
        print("CẢNH BÁO:", w)


if __name__ == "__main__":
    main()
