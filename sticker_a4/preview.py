"""Vẽ thử trang A4 ra PNG (không cần Corel) để kiểm tra bố cục.

python preview.py anh_goc_1.png preview.png            # xếp lồng, xoay tuỳ ý (mặc định)
python preview.py anh_goc_1.png preview.png --mode grid
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from layout import PAGE_H, PAGE_W, Config, Layout, plan
from contour import CutConfig, lmarks, page_outlines
from nest import QUALITY, NestConfig, plan_nest
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
        im = stickers[p.index].resize((round(p.w * k), round(p.h * k)), Image.LANCZOS)
        if p.angle:
            im = im.rotate(p.angle, resample=Image.BICUBIC, expand=True)
        page.paste(im, (round(p.cx * k - im.width / 2), round(p.cy * k - im.height / 2)), im)
    for polys in (lay.cuts or {}).values():  # contour cắt: đỏ
        for poly in polys:
            d.line([(x * k, y * k) for x, y in poly] + [(poly[0][0] * k, poly[0][1] * k)],
                   fill="#e94e36", width=1)
    for mark in lay.marks or []:  # dấu L: đen, nét 1 mm
        d.line([(x * k, y * k) for x, y in mark], fill="black", width=max(1, round(k)))
    return page


def make_layout(images: list[Image.Image], mode: str, allow_rotate: bool = True, log=None,
                quality: str = "fast", time_budget: float | None = None,
                cut: CutConfig | None = CutConfig()):
    """Tính bố cục; nếu `cut` khác None thì tính luôn contour cắt và 4 dấu L."""
    if mode == "grid":
        cfg = Config(allow_rotate=allow_rotate)
        lay = plan([im.size for im in images], cfg)
    else:
        opts = dict(QUALITY[quality])
        if time_budget is not None:
            opts["time_budget"] = time_budget
        cfg = NestConfig(**opts)
        lay = plan_nest(images, cfg, log=log)
    if cut is not None:
        lay.cuts = page_outlines(images, lay.placements, cut)
        lay.marks = lmarks(cut)
    return lay, cfg


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("png", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--mode", choices=["nest", "grid"], default="nest")
    ap.add_argument("--quality", choices=list(QUALITY), default="fast")
    ap.add_argument("--time-budget", type=float, help="giây cho mỗi file (chế độ high)")
    ap.add_argument("--no-cut", action="store_true", help="không tạo contour cắt và dấu L")
    ap.add_argument("--cut-offset", type=float, default=CutConfig.offset,
                    help="contour nằm ngoài mép hình bao nhiêu mm")
    a = ap.parse_args()
    st = split_sheet(a.png)
    images = [s.image for s in st]
    cut = None if a.no_cut else CutConfig(offset=a.cut_offset)
    lay, cfg = make_layout(images, a.mode, log=print, quality=a.quality,
                           time_budget=a.time_budget, cut=cut)
    render(images, lay, cfg).save(a.out)
    for p in lay.placements:
        print(f"  #{p.index + 1:2d} {p.w:5.1f} x {p.h:5.1f} mm, xoay {p.angle:g}°")
    if lay.min_gap is not None:
        print(f"khoảng cách nhỏ nhất giữa 2 hình: {lay.min_gap:.2f} mm")
    for w in lay.warnings:
        print("CẢNH BÁO:", w)


if __name__ == "__main__":
    main()
