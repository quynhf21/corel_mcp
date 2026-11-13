"""Tính bố cục 25 sticker trên 1 trang A4, chia 2 khối trên/dưới để cắt đôi bỏ túi.

Mọi đơn vị là mm, gốc toạ độ ở góc trên-trái trang, trục y hướng xuống.
Mỗi khối là một lưới: các hàng chia đều chiều cao khối, mỗi hàng chia đều chiều rộng
thành các ô cách nhau GAP mm. Sticker được thu/phóng để vừa ô (giữ tỉ lệ), căn giữa ô,
nên các sticker cùng hàng thẳng hàng, các hàng cùng số cột thẳng cột.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

PAGE_W, PAGE_H = 210.0, 297.0


@dataclass
class Config:
    # Hai khối 166 x 116 mm, cách nhau 3,5 mm; giữ tâm vùng mẫu ST16.cdr
    # và né 4 dấu L của máy cắt, vừa túi 12 x 17,1 cm.
    left: float = 22.0
    right: float = 188.0
    top: float = 35.75
    bottom: float = 271.25
    cut_gap: float = 3.5      # khoảng trống giữa 2 khối, đường cắt đôi tờ nằm giữa
    gap: float = 1.5          # khoảng cách giữa các ô sticker
    min_size: float = 30.0    # cạnh dài của sticker phải >= giá trị này (mm)
    size_tolerance: float = 0.12  # sticker lớn nhất không vượt quá trung vị (1 + tol)
    allow_rotate: bool = True     # cho xoay 90° nếu vừa ô hơn rõ rệt
    rotate_gain: float = 1.10     # chỉ xoay khi to thêm >= 10%
    max_rows: int = 4

    @property
    def block_w(self) -> float:
        return self.right - self.left

    @property
    def block_h(self) -> float:
        return (self.bottom - self.top - self.cut_gap) / 2


@dataclass
class Cell:
    x: float
    y: float
    w: float
    h: float


@dataclass
class Placement:
    index: int        # chỉ số sticker trong danh sách đầu vào
    cx: float         # tâm hình trên trang
    cy: float
    w: float          # kích thước hình khi CHƯA xoay
    h: float
    angle: float = 0.0  # góc xoay (độ, dương = ngược kim đồng hồ), quanh tâm

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """Hộp bao (x0, y0, x1, y1) sau khi xoay."""
        a = math.radians(self.angle)
        bw = abs(self.w * math.cos(a)) + abs(self.h * math.sin(a))
        bh = abs(self.w * math.sin(a)) + abs(self.h * math.cos(a))
        return self.cx - bw / 2, self.cy - bh / 2, self.cx + bw / 2, self.cy + bh / 2


@dataclass
class Layout:
    placements: list[Placement]
    rows: tuple[tuple[int, ...], tuple[int, ...]]  # số ô mỗi hàng của khối trên, khối dưới
    cut_y: float
    score: float
    warnings: list[str] = field(default_factory=list)
    min_gap: float | None = None  # khoảng cách nhỏ nhất đo được giữa hai hình (mm)
    # đường cắt (contour.py): index sticker -> các đa giác kín (mm, toạ độ trang); None = không cắt
    cuts: dict[int, list] | None = None
    marks: list[list[tuple[float, float]]] | None = None  # 4 dấu L


def _compositions(n: int, rows: int, lo: int = 2, hi: int = 7):
    """Các cách chia n ô thành `rows` hàng, chênh lệch giữa các hàng tối đa 1."""
    base, extra = divmod(n, rows)
    if base < lo or base + (extra > 0) > hi:
        return
    for pos in itertools.combinations(range(rows), extra):
        yield tuple(base + (i in pos) for i in range(rows))


def _cells(cfg: Config, y0: float, counts: tuple[int, ...]) -> list[Cell]:
    rows = len(counts)
    ch = (cfg.block_h - cfg.gap * (rows - 1)) / rows
    cells = []
    for r, k in enumerate(counts):
        cw = (cfg.block_w - cfg.gap * (k - 1)) / k
        y = y0 + r * (ch + cfg.gap)
        cells += [Cell(cfg.left + c * (cw + cfg.gap), y, cw, ch) for c in range(k)]
    return cells


def _fit(cfg: Config, w: float, h: float, cell: Cell) -> tuple[float, bool]:
    """Hệ số phóng lớn nhất để (w, h) vừa ô; trả thêm cờ có xoay hay không."""
    k = min(cell.w / w, cell.h / h)
    if cfg.allow_rotate:
        kr = min(cell.w / h, cell.h / w)
        if kr >= k * cfg.rotate_gain:
            return kr, True
    return k, False


def _evaluate(cfg: Config, sizes: list[tuple[float, float]], cells: list[Cell]):
    """Ghép sticker vào ô theo tỉ lệ khung (rộng/cao) rồi tính điểm = tổng diện tích."""
    by_aspect = sorted(range(len(sizes)), key=lambda i: sizes[i][0] / sizes[i][1])
    cell_order = sorted(range(len(cells)), key=lambda j: cells[j].w / cells[j].h)
    pairs = list(zip(by_aspect, cell_order))
    fits = {i: _fit(cfg, *sizes[i], cells[j]) for i, j in pairs}
    # giới hạn chênh lệch kích thước: không cho sticker nào to hơn trung vị quá tol
    ks = sorted(k for k, _ in fits.values())
    cap = ks[len(ks) // 2] * (1 + cfg.size_tolerance)
    placements, area = [], 0.0
    for i, j in pairs:
        k, rot = fits[i]
        k = min(k, cap)
        w, h = sizes[i][0] * k, sizes[i][1] * k
        c = cells[j]
        # xoay 90° theo chiều kim đồng hồ = -90° theo quy ước ngược kim đồng hồ
        placements.append(Placement(i, c.x + c.w / 2, c.y + c.h / 2, w, h, -90.0 if rot else 0.0))
        area += w * h
    return area, placements


def plan(sizes_px: list[tuple[int, int]], cfg: Config | None = None) -> Layout:
    """sizes_px: kích thước (rộng, cao) của từng sticker sau khi tách, đơn vị px.

    Chỉ tỉ lệ khung là quan trọng; kích thước tuyệt đối do ô lưới quyết định.
    """
    cfg = cfg or Config()
    n = len(sizes_px)
    sizes = [(float(w), float(h)) for w, h in sizes_px]
    y_top = cfg.top
    y_bot = cfg.top + cfg.block_h + cfg.cut_gap
    best: Layout | None = None
    for n_top in {n // 2, n - n // 2}:
        n_bot = n - n_top
        for r1, r2 in itertools.product(range(1, cfg.max_rows + 1), repeat=2):
            for c1 in _compositions(n_top, r1):
                for c2 in _compositions(n_bot, r2):
                    cells = _cells(cfg, y_top, c1) + _cells(cfg, y_bot, c2)
                    area, pl = _evaluate(cfg, sizes, cells)
                    if best is None or area > best.score:
                        best = Layout(pl, (c1, c2), cfg.top + cfg.block_h + cfg.cut_gap / 2, area)
    if best is None:
        raise ValueError(f"Không tìm được lưới cho {n} sticker")
    for p in best.placements:
        if max(p.w, p.h) < cfg.min_size:
            best.warnings.append(
                f"sticker {p.index + 1}: {p.w:.1f}x{p.h:.1f} mm, nhỏ hơn {cfg.min_size} mm")
    best.placements.sort(key=lambda p: (p.cy, p.cx))
    return best
