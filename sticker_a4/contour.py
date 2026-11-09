"""Đường cắt contour quanh từng sticker và 4 dấu L (registration mark) cho máy cắt.

Mô phỏng đúng những gì plugin AidCut tạo trong file mẫu ST16.cdr:
- layer "TraceLayer" chứa mỗi sticker một đường "TraceLine": đường gấp khúc kín, nằm
  ngoài mép hình ~0,4 mm, nét 0,5 pt màu đỏ, không tô;
- trên "Layer 1" (cùng layer với ảnh) một đối tượng "LMarkLine1" gồm 4 dấu L dài 20 mm,
  nét 1 mm, đen K100.
Toạ độ trả về theo mm, gốc trên-trái trang, trục y hướng xuống (giống layout.py).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage

from layout import Placement

ALPHA_MIN = 16


@dataclass(frozen=True)
class CutConfig:
    offset: float = 0.4        # contour nằm ngoài mép hình bao nhiêu mm
    tolerance: float = 0.05    # sai số tối đa khi giảm số điểm contour (mm)
    upsample: int = 4          # phóng mặt nạ trước khi dò để đường mượt hơn
    line_width_pt: float = 0.5           # nét contour (pt), như file mẫu
    line_rgb: tuple[int, int, int] = (233, 78, 54)  # đỏ #e94e36, như file mẫu
    # 4 dấu L: toạ độ đường tâm nét (mm), đo từ ST16.cdr
    mark_left: float = 9.93
    mark_right: float = 199.93
    mark_top: float = 30.01
    mark_bottom: float = 277.01
    mark_arm: float = 20.0
    mark_width: float = 1.0
    trace_layer: str = "TraceLayer"
    trace_name: str = "TraceLine"
    mark_name: str = "LMarkLine1"


def sticker_outline(im: Image.Image, mm_per_px: float, cfg: CutConfig) -> list[np.ndarray]:
    """Contour quanh một sticker, toạ độ px của ảnh gốc (chưa xoay), gốc trên-trái.

    Lấp lỗ bên trong, nới ra `offset` mm; mảnh rời quá xa (tim, giọt nước...) có
    contour riêng. Trả về list đa giác (N x 2, cột x, y)."""
    up = cfg.upsample
    big = im.getchannel("A").resize((im.width * up, im.height * up), Image.BICUBIC)
    mask = np.asarray(big) > ALPHA_MIN
    px = mm_per_px / up                       # mm mỗi px của lưới đã phóng
    pad = math.ceil(cfg.offset / px) + 2
    mask = np.pad(mask, pad)
    region = ndimage.distance_transform_edt(~mask) * px <= cfg.offset
    region = ndimage.binary_fill_holes(region).astype(np.uint8)
    found, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    polys = []
    for c in found:
        c = cv2.approxPolyDP(c, cfg.tolerance / px, True).reshape(-1, 2).astype(float)
        if len(c) < 3:
            continue
        polys.append((c - pad + 0.5) / up)    # tâm pixel lưới phóng -> px ảnh gốc
    return polys


def place_outline(polys: list[np.ndarray], im_size: tuple[int, int],
                  p: Placement) -> list[np.ndarray]:
    """Đưa contour từ toạ độ px của ảnh sang toạ độ trang (mm) theo placement."""
    k = p.w / im_size[0]                      # mm/px
    a = math.radians(p.angle)                 # dương = ngược kim đồng hồ khi nhìn
    cos, sin = math.cos(a), math.sin(a)
    out = []
    for poly in polys:
        x = (poly[:, 0] - im_size[0] / 2) * k
        y = (poly[:, 1] - im_size[1] / 2) * k
        # trục y hướng xuống nên xoay ngược kim đồng hồ: x' = x cos + y sin, y' = -x sin + y cos
        out.append(np.column_stack([p.cx + x * cos + y * sin, p.cy - x * sin + y * cos]))
    return out


def page_outlines(images: list[Image.Image], placements: list[Placement],
                  cfg: CutConfig) -> dict[int, list[np.ndarray]]:
    """Contour (toạ độ trang, mm) của mọi sticker, theo index sticker."""
    out = {}
    for p in placements:
        im = images[p.index]
        out[p.index] = place_outline(sticker_outline(im, p.w / im.width, cfg), im.size, p)
    return out


def lmarks(cfg: CutConfig) -> list[list[tuple[float, float]]]:
    """4 dấu L ở 4 góc, mỗi dấu là đường gấp khúc 3 điểm (đầu cánh - góc - đầu cánh)."""
    L, R, T, B, a = cfg.mark_left, cfg.mark_right, cfg.mark_top, cfg.mark_bottom, cfg.mark_arm
    return [
        [(L + a, T), (L, T), (L, T + a)],
        [(R - a, T), (R, T), (R, T + a)],
        [(L + a, B), (L, B), (L, B - a)],
        [(R - a, B), (R, B), (R, B - a)],
    ]
