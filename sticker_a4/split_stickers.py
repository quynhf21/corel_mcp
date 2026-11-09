"""Tách tấm sticker PNG (nền trong suốt) thành từng sticker riêng.

Dùng kênh alpha: gom các vùng điểm ảnh liền nhau, gộp mảnh nhỏ (tim, giọt mồ hôi...)
vào sticker gần nhất, rồi sắp theo thứ tự hàng -> cột như bản thảo gốc.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ALPHA_MIN = 16        # alpha <= ngưỡng này coi là nền
BRIDGE_PX = 3         # nối các mảnh cách nhau <= vài px (viền trắng bị đứt)
MIN_AREA_RATIO = 0.15 # mảnh nhỏ hơn 15% diện tích trung vị -> gộp vào sticker gần nhất


@dataclass
class Sticker:
    index: int          # thứ tự đọc: hàng trên trước, trái sang phải
    box: tuple[int, int, int, int]  # x0, y0, x1, y1 (px, x1/y1 không bao gồm)
    image: Image.Image  # ảnh RGBA đã cắt sát


def _merge_small(boxes: list[list[int]], areas: list[int]) -> list[list[int]]:
    """Gộp các mảnh nhỏ vào hộp lớn gần nhất (theo khoảng cách giữa hai hộp)."""
    med = float(np.median(areas))
    big = [i for i, a in enumerate(areas) if a >= MIN_AREA_RATIO * med]
    merged = {i: list(boxes[i]) for i in big}
    for i, a in enumerate(areas):
        if i in merged:
            continue
        x0, y0, x1, y1 = boxes[i]

        def gap(j: int) -> float:
            bx0, by0, bx1, by1 = boxes[j]
            dx = max(bx0 - x1, x0 - bx1, 0)
            dy = max(by0 - y1, y0 - by1, 0)
            return float(np.hypot(dx, dy))

        j = min(big, key=gap)
        m = merged[j]
        merged[j] = [min(m[0], x0), min(m[1], y0), max(m[2], x1), max(m[3], y1)]
    return list(merged.values())


def _reading_order(boxes: list[list[int]]) -> list[list[int]]:
    """Sắp hộp theo hàng (nhóm theo tâm y) rồi theo x."""
    boxes = sorted(boxes, key=lambda b: (b[1] + b[3]) / 2)
    med_h = float(np.median([b[3] - b[1] for b in boxes]))
    rows: list[list[list[int]]] = []
    for b in boxes:
        cy = (b[1] + b[3]) / 2
        if rows and abs(cy - np.mean([(r[1] + r[3]) / 2 for r in rows[-1]])) < med_h / 2:
            rows[-1].append(b)
        else:
            rows.append([b])
    return [b for row in rows for b in sorted(row, key=lambda b: b[0])]


def split_sheet(path: Path, expected: int | None = 25) -> list[Sticker]:
    img = Image.open(path).convert("RGBA")
    alpha = np.asarray(img)[:, :, 3] > ALPHA_MIN
    solid = ndimage.binary_dilation(alpha, iterations=BRIDGE_PX)
    labels, n = ndimage.label(solid)
    slices = ndimage.find_objects(labels)
    areas = ndimage.sum(alpha, labels, index=range(1, n + 1))
    boxes = [[s[1].start, s[0].start, s[1].stop, s[0].stop] for s in slices]
    boxes = _reading_order(_merge_small(boxes, list(areas)))
    if expected is not None and len(boxes) != expected:
        raise ValueError(f"{path.name}: tách được {len(boxes)} sticker, cần {expected}")
    stickers = []
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        crop = img.crop((x0, y0, x1, y1))
        # bỏ phần trong suốt thừa do dilation
        crop = crop.crop(crop.getchannel("A").point(lambda a: 255 if a > ALPHA_MIN else 0).getbbox())
        stickers.append(Sticker(i, (x0, y0, x1, y1), crop))
    return stickers


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("png", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--expected", type=int, default=25)
    a = ap.parse_args()
    a.out_dir.mkdir(parents=True, exist_ok=True)
    for s in split_sheet(a.png, a.expected):
        s.image.save(a.out_dir / f"{a.png.stem}_{s.index + 1:02d}.png")
        print(s.index + 1, s.image.size)


if __name__ == "__main__":
    main()
