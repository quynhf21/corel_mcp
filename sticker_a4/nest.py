"""Xếp lồng sticker theo đúng hình dạng (kênh alpha), cho xoay góc bất kỳ.

Cách làm (raster nesting):
- Mỗi khối (nửa trang) là một lưới ô vuông cạnh RES mm.
- Sticker được rasterize "phủ dư" (ô nào có chút hình cũng tính là có hình), xoay
  theo một tập góc. Hình đã đặt được nới rộng (dilate) thêm khoảng cách tối thiểu.
- Đặt lần lượt sticker lớn trước, mỗi sticker thử mọi góc ở cả 2 khối, chọn vị trí
  áp sát nhiều nhất vào hình đã đặt / mép khối (lấp hốc). Va chạm và độ áp sát tính
  bằng tương quan FFT.
- Tìm kiếm nhị phân hệ số phóng chung lớn nhất mà vẫn xếp đủ mọi sticker (hình không
  vừa được thu nhỏ tối đa 10%). Xếp xong, thử phóng to từng hình thêm tối đa 10% để lấp hốc.
- Kiểm tra lại khoảng cách thật ở độ phân giải mịn (VERIFY_RES).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.signal import fftconvolve

from layout import Config, Layout, Placement

RES = 0.4          # mm mỗi ô lưới khi tìm chỗ
VERIFY_RES = 0.1   # mm mỗi ô khi kiểm tra khoảng cách cuối cùng
ALPHA_MIN = 16


@dataclass
class NestConfig(Config):
    gap: float = 1.2           # khoảng cách tối thiểu giữa mép hai hình (mm)
    angle_step: float = 15.0   # bước góc thử (độ); 15 -> 24 góc
    search_step: float = 0.5   # độ chính xác tìm kích thước (mm cạnh dài trung vị)
    max_size: float = 60.0     # cận trên cạnh dài trung vị khi tìm kiếm (mm)
    shrink: tuple[float, ...] = (1.0, 0.95, 0.9)  # hình không vừa thì thử nhỏ lại chút
    grow: tuple[float, ...] = (1.1, 1.05)  # xếp xong, thử phóng to từng hình để lấp hốc
    restarts: int = 6          # số thứ tự đặt hình được thử (càng nhiều càng chặt, càng lâu)
    seed: int = 0
    # --- chế độ chất lượng cao ---
    time_budget: float = 0.0   # tổng số giây cho mỗi file; phần còn lại sau tìm nhị phân
                               # dùng để tìm kiếm cục bộ (0 = tắt)


QUALITY = {
    "fast": {},
    "high": {"time_budget": 300.0, "angle_step": 10.0},
}


def _disk(r: int) -> np.ndarray:
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def _mask(alpha: Image.Image, angle: float, scale: float, res: float) -> np.ndarray:
    """Mặt nạ phủ dư của sticker sau khi xoay `angle` độ (ngược kim đồng hồ) và phóng
    `scale` mm/px, trên lưới `res` mm/ô."""
    rot = alpha.rotate(angle, resample=Image.BILINEAR, expand=True) if angle else alpha
    w = max(1, math.ceil(rot.width * scale / res))
    h = max(1, math.ceil(rot.height * scale / res))
    # BOX lấy trung bình vùng -> ô nào có pixel nào đó của hình sẽ > 0
    small = rot.resize((w, h), Image.BOX)
    return np.asarray(small) > 0


def _alphas(images: list[Image.Image]) -> list[Image.Image]:
    return [im.getchannel("A").point(lambda a: 255 if a > ALPHA_MIN else 0) for im in images]


def _ring(occ: np.ndarray, width: int = 2) -> np.ndarray:
    """Dải ô trống sát vật cản (hình đã đặt + mép khối), có viền 1 ô quanh khối."""
    env = np.pad(occ > 0, 1, constant_values=True)
    return (ndimage.binary_dilation(env, iterations=width) & ~env).astype(np.float32)


class _Packer:
    """Trạng thái xếp ở một hệ số phóng: mỗi hình đã đặt = (khối, y, x, góc, hệ số, mặt nạ)."""

    def __init__(self, alphas, scale, cfg: NestConfig, angles, cache):
        self.alphas, self.scale, self.cfg, self.angles = alphas, scale, cfg, angles
        self.cache = cache  # (index, góc, scale) -> mặt nạ, dùng chung giữa các lần thử
        self.bw = int(cfg.block_w / RES)
        self.bh = int(cfg.block_h / RES)
        self.r = math.ceil(cfg.gap / RES)
        self.disk = _disk(self.r)
        self.items: dict[int, tuple] = {}
        self.occ = [np.zeros((self.bh, self.bw), dtype=np.float32) for _ in range(2)]
        self.ring = [_ring(o) for o in self.occ]

    def _stamp(self, b, y, x, m):
        """Ghi hình (đã nới thêm khoảng cách) vào lưới vật cản của khối b."""
        r = self.r
        dil = ndimage.binary_dilation(np.pad(m, r), structure=self.disk)
        y0, x0 = y - r, x - r
        ys, xs = max(0, y0), max(0, x0)
        ye, xe = min(self.bh, y0 + dil.shape[0]), min(self.bw, x0 + dil.shape[1])
        o = self.occ[b]
        o[ys:ye, xs:xe] = np.maximum(o[ys:ye, xs:xe], dil[ys - y0:ye - y0, xs - x0:xe - x0])

    def _rebuild(self, b):
        self.occ[b][:] = 0
        for bb, y, x, _a, _f, m in self.items.values():
            if bb == b:
                self._stamp(b, y, x, m)
        self.ring[b] = _ring(self.occ[b])

    def place(self, i, factors) -> bool:
        """Đặt hình i với hệ số đầu tiên trong `factors` còn tìm được chỗ."""
        for f in factors:
            best = self._best_spot(i, self.scale * f)
            if best is not None:
                _, b, y, x, a, m = best
                self.items[i] = (b, y, x, a, f, m)
                self._stamp(b, y, x, m)
                self.ring[b] = _ring(self.occ[b])
                return True
        return False

    def _mask(self, i, a, scale):
        key = (i, a, scale)
        m = self.cache.get(key)
        if m is None:
            if len(self.cache) > 50000:
                self.cache.clear()
            m = self.cache[key] = _mask(self.alphas[i], a, scale, RES)
        return m

    def _best_spot(self, i, scale):
        """Vị trí tốt nhất cho hình i trên cả 2 khối, hoặc None nếu không còn chỗ."""
        best = None
        for a in self.angles:
            m = self._mask(i, a, scale)
            mh, mw = m.shape
            if mh > self.bh or mw > self.bw:
                continue
            kern = m[::-1, ::-1].astype(np.float32)
            for b in range(2):
                hit = fftconvolve(self.occ[b], kern, mode="valid") > 0.5
                if hit.all():
                    continue
                # ring có viền 1 ô -> vị trí (y, x) trong khối ứng với (y+1, x+1)
                contact = fftconvolve(self.ring[b], kern, mode="valid")[1:-1, 1:-1]
                contact[hit] = -1
                y, x = np.unravel_index(int(np.argmax(contact)), contact.shape)
                key = (-round(float(contact[y, x])), y + mh, x)
                if best is None or key < best[0]:
                    best = (key, b, y, x, a, m)
        return best

    def grow(self, factors) -> None:
        """Lấp hốc: nhấc từng hình (nhỏ trước) ra, thử đặt lại to hơn; không được thì
        trả về chỗ cũ."""
        for i in sorted(self.items, key=lambda i: self.items[i][4]):
            old = self.items.pop(i)
            bigger = [f for f in factors if f > old[4]]
            self._rebuild(old[0])
            if not bigger or not self.place(i, bigger):
                self.items[i] = old
                self._rebuild(old[0])

    def result(self):
        out = []
        for i, (b, y, x, a, f, m) in self.items.items():
            mh, mw = m.shape
            out.append((i, b, (x + mw / 2) * RES, (y + mh / 2) * RES, a, f))
        return out


def _try_pack(alphas, scale, cfg: NestConfig, angles, order, cache):
    """Thử xếp mọi sticker theo thứ tự `order` ở hệ số `scale` (mm/px).

    Với mỗi sticker, xét mọi góc ở cả 2 khối; chọn vị trí trống mà hình áp sát nhiều
    nhất vào vật cản (hình khác/mép khối), hoà thì chọn vị trí cao hơn, trái hơn.
    """
    pk = _Packer(alphas, scale, cfg, angles, cache)
    for i in order:
        if not pk.place(i, cfg.shrink):
            return None
    return pk


def _to_layout(pk: _Packer, sizes, cfg: NestConfig) -> Layout:
    y0 = [cfg.top, cfg.top + cfg.block_h + cfg.cut_gap]
    placements = []
    for i, b, cx, cy, a, f in pk.result():
        w, h = sizes[i][0] * pk.scale * f, sizes[i][1] * pk.scale * f
        placements.append(Placement(i, cfg.left + cx, y0[b] + cy, w, h, a))
    return Layout(placements, ((), ()), cfg.top + cfg.block_h + cfg.cut_gap / 2,
                  sum(p.w * p.h for p in placements))


def _mutate(order: list[int], rng) -> list[int]:
    """Đổi chỗ 1–3 cặp hình trong thứ tự đặt."""
    order = list(order)
    for _ in range(int(rng.integers(1, 4))):
        i, j = rng.choice(len(order), 2, replace=False)
        order[i], order[j] = order[j], order[i]
    return order


def plan_nest(images: list[Image.Image], cfg: NestConfig | None = None,
              log=None) -> Layout:
    """images: ảnh RGBA từng sticker (đã cắt sát). Trả về Layout với góc xoay tuỳ ý."""
    cfg = cfg or NestConfig()
    t_start = time.monotonic()
    alphas = _alphas(images)
    sizes = [im.size for im in images]
    long_px = float(np.median([max(s) for s in sizes]))
    n_ang = int(round(360 / cfg.angle_step))
    angles = [a * cfg.angle_step for a in range(n_ang)]
    cache: dict = {}

    rng = np.random.default_rng(cfg.seed)
    area = [sizes[i][0] * sizes[i][1] for i in range(len(images))]
    orders = [sorted(range(len(images)), key=lambda i: -area[i])]
    for _ in range(cfg.restarts - 1):  # lớn trước nhưng xáo trộn nhẹ
        noise = rng.uniform(0.75, 1.25, len(images))
        orders.append(sorted(range(len(images)), key=lambda i: -area[i] * noise[i]))

    def pack(size_mm: float, order, angs=angles):
        return _try_pack(alphas, size_mm / long_px, cfg, angs, order, cache)

    def attempt(size_mm: float):
        for order in orders:
            pk = pack(size_mm, order)
            if pk is not None:
                return pk, order
        return None

    lo, hi = cfg.min_size, cfg.max_size
    res = attempt(lo)
    if res is None:
        raise ValueError(f"Không xếp đủ {len(images)} hình kể cả khi cạnh dài = {lo} mm")
    (best, best_order), best_size = res, lo
    while hi - lo > cfg.search_step:
        mid = (lo + hi) / 2
        res = attempt(mid)
        if log:
            log(f"  thử cạnh dài {mid:.1f} mm: {'được' if res else 'không vừa'}")
        if res is None:
            hi = mid
        else:
            lo, (best, best_order), best_size = mid, res, mid

    # Tìm kiếm cục bộ: thử kích thước lớn hơn một bậc với thứ tự đặt bị đổi chỗ vài hình
    # và bộ góc lệch pha ngẫu nhiên (để phủ các góc nằm giữa hai bước).
    if cfg.time_budget > 0:
        deadline = t_start + cfg.time_budget
        target, tries = best_size + cfg.search_step, 0
        while time.monotonic() < deadline:
            tries += 1
            order = _mutate(best_order, rng)
            phase = float(rng.choice([0.0, cfg.angle_step / 2, cfg.angle_step / 3]))
            pk = pack(target, order, [a + phase for a in angles])
            if pk is not None:
                best, best_order, best_size = pk, order, target
                if log:
                    log(f"  tìm cục bộ: được {target:.1f} mm (lần thử {tries})")
                target += cfg.search_step
        if log:
            log(f"  tìm cục bộ: {tries} lần thử trong {cfg.time_budget:.0f} s")

    best.grow(cfg.grow)
    lay = _to_layout(best, sizes, cfg)
    gap = min_gap(images, lay)
    for p in lay.placements:
        if max(p.w, p.h) < cfg.min_size:
            lay.warnings.append(f"sticker {p.index + 1}: {p.w:.1f}x{p.h:.1f} mm, nhỏ hơn {cfg.min_size} mm")
    if gap < cfg.gap - VERIFY_RES:
        lay.warnings.append(f"khoảng cách nhỏ nhất {gap:.2f} mm < {cfg.gap} mm")
    lay.min_gap = gap
    return lay


def min_gap(images: list[Image.Image], lay: Layout) -> float:
    """Khoảng cách nhỏ nhất (mm) giữa mép hai hình bất kỳ, đo trên lưới VERIFY_RES."""
    from layout import PAGE_H, PAGE_W

    H, W = int(PAGE_H / VERIFY_RES), int(PAGE_W / VERIFY_RES)
    alphas = _alphas(images)
    labels = np.zeros((H, W), dtype=np.int16)
    for n, p in enumerate(lay.placements, 1):
        rot = alphas[p.index].rotate(p.angle, resample=Image.BILINEAR, expand=True)
        k = p.w / images[p.index].width  # mm/px
        w, h = max(1, round(rot.width * k / VERIFY_RES)), max(1, round(rot.height * k / VERIFY_RES))
        m = np.asarray(rot.resize((w, h), Image.BILINEAR)) > 127
        y = round(p.cy / VERIFY_RES - h / 2)
        x = round(p.cx / VERIFY_RES - w / 2)
        # cắt phần thò ra ngoài trang (tránh chỉ số âm bị hiểu là đếm từ cuối)
        ys, xs = max(0, y), max(0, x)
        ye, xe = min(H, y + h), min(W, x + w)
        if ye > ys and xe > xs:
            sub = labels[ys:ye, xs:xe]
            sub[m[ys - y:ye - y, xs - x:xe - x]] = n
    best = math.inf
    for n in range(1, len(lay.placements) + 1):
        mine = labels == n
        ys, xs = np.nonzero(mine)
        pad = int(5 / VERIFY_RES)
        y0, y1 = max(0, ys.min() - pad), min(H, ys.max() + pad + 1)
        x0, x1 = max(0, xs.min() - pad), min(W, xs.max() + pad + 1)
        win = labels[y0:y1, x0:x1]
        dist = ndimage.distance_transform_edt(~mine[y0:y1, x0:x1])
        others = (win > 0) & (win != n)
        if others.any():
            best = min(best, float(dist[others].min()) * VERIFY_RES)
    return best
