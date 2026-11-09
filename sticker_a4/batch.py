"""Chạy hàng loạt: mỗi file đầu vào (.cdr hoặc .png, 25 sticker) -> 1 trang A4 .cdr.

Ví dụ (Windows):
    python batch.py D:\\sticker\\goc D:\\sticker\\a4 --limit 10
    python batch.py D:\\sticker\\goc D:\\sticker\\a4 --dry-run   # chỉ vẽ preview, không mở Corel

Ba bước:
  1. (file .cdr) Corel xuất tấm sticker ra PNG.
  2. Tách sticker + tính bố cục, chạy song song nhiều file (--workers), vẽ preview.
  3. Corel dựng trang A4, lưu .cdr (+ .pdf nếu có --pdf). Corel chỉ chạy tuần tự.
File đã có kết quả sẽ bị bỏ qua (chạy lại để làm tiếp), trừ khi có --overwrite.
Không bao giờ ghi đè file gốc.
"""
from __future__ import annotations

import argparse
import csv
import os
import pickle
import shutil
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from contour import CutConfig
from preview import make_layout, render
from split_stickers import split_sheet


def layout_one(sheet: Path, work: Path, preview: Path, mode: str, allow_rotate: bool,
               expected: int, quality: str = "fast", time_budget: float | None = None,
               cut: CutConfig | None = None) -> list[str]:
    """Bước 2 cho một file: tách, tính bố cục (+ contour cắt), lưu ảnh từng sticker
    + layout.pkl."""
    stickers = split_sheet(sheet, expected)
    images = [s.image for s in stickers]
    lay, cfg = make_layout(images, mode, allow_rotate, quality=quality, time_budget=time_budget,
                           cut=cut)
    render(images, lay, cfg).save(preview)
    work.mkdir(parents=True, exist_ok=True)
    for s in stickers:
        s.image.save(work / f"{s.index + 1:02d}.png")
    with open(work / "layout.pkl", "wb") as fh:
        pickle.dump(lay, fh)
    return lay.warnings


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("in_dir", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--limit", type=int, help="chỉ xử lý N file đầu (để test)")
    ap.add_argument("--dry-run", action="store_true", help="chỉ tạo preview PNG, không mở Corel (chỉ đọc .png)")
    ap.add_argument("--pdf", action="store_true", help="xuất thêm PDF")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--keep-work", action="store_true", help="giữ thư mục _work (ảnh tách)")
    ap.add_argument("--expected", type=int, default=25, help="số sticker mỗi tấm")
    ap.add_argument("--mode", choices=["nest", "grid"], default="nest",
                    help="nest = xếp lồng, xoay tuỳ ý (mặc định); grid = lưới thẳng hàng")
    ap.add_argument("--no-rotate", action="store_true", help="(chỉ mode grid) không xoay 90°")
    ap.add_argument("--quality", choices=["fast", "high"], default="fast",
                    help="high = tìm kiếm cục bộ thêm, chặt hơn nhưng ~5 phút/file (chạy qua đêm)")
    ap.add_argument("--time-budget", type=float, help="giây tối đa cho mỗi file khi --quality high")
    ap.add_argument("--no-cut", action="store_true",
                    help="không tạo contour cắt (TraceLayer) và 4 dấu L (LMarkLine1)")
    ap.add_argument("--cut-offset", type=float, default=CutConfig.offset,
                    help="contour nằm ngoài mép hình bao nhiêu mm (mẫu AidCut: 0,4)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1),
                    help="số file tính bố cục cùng lúc")
    a = ap.parse_args()

    if a.in_dir.resolve() == a.out_dir.resolve():
        raise SystemExit("out_dir phải khác in_dir để không đụng vào file gốc")
    a.out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in a.in_dir.iterdir() if p.suffix.lower() in (".cdr", ".png"))
    if a.limit:
        files = files[: a.limit]
    if not a.dry_run and not a.overwrite:
        files = [f for f in files if not (a.out_dir / f"{f.stem}_A4.cdr").exists()]
    work_root = a.out_dir / "_work"
    status: dict[str, tuple[str, str]] = {}

    def fail(src: Path, e: BaseException) -> None:
        status[src.name] = ("LOI", repr(e))
        print(f"LỖI {src.name}: {e!r}")

    corel = None
    if not a.dry_run:
        from corel_build import Corel  # chỉ import trên Windows
        corel = Corel()

    # bước 1: lấy PNG tấm sticker
    sheets: dict[Path, Path] = {}
    for src in files:
        if src.suffix.lower() != ".cdr":
            sheets[src] = src
        elif corel is None:
            fail(src, ValueError("--dry-run chỉ đọc được .png; file .cdr cần mở Corel"))
        else:
            try:
                (work_root / src.stem).mkdir(parents=True, exist_ok=True)
                sheets[src] = work_root / src.stem / "sheet.png"
                corel.export_sheet_png(src, sheets[src])
            except Exception as e:
                sheets.pop(src, None)
                fail(src, e)

    # bước 2: tính bố cục song song
    done: list[Path] = []
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        jobs = {pool.submit(layout_one, sheet, work_root / src.stem,
                            a.out_dir / f"{src.stem}_A4_preview.png",
                            a.mode, not a.no_rotate, a.expected, a.quality, a.time_budget,
                            None if a.no_cut else CutConfig(offset=a.cut_offset)): src
                for src, sheet in sheets.items()}
        for n, fut in enumerate(as_completed(jobs), 1):
            src = jobs[fut]
            try:
                warnings = fut.result()
                status[src.name] = ("CANH_BAO" if warnings else "OK", "; ".join(warnings))
                done.append(src)
                print(f"[bố cục {n}/{len(jobs)}] {src.name}" + (f" — {warnings}" if warnings else ""), flush=True)
            except Exception as e:
                fail(src, e)

    # bước 3: dựng trang trong Corel
    if corel is not None:
        for n, src in enumerate(sorted(done), 1):
            work = work_root / src.stem
            try:
                with open(work / "layout.pkl", "rb") as fh:
                    lay = pickle.load(fh)
                pngs = [work / f"{i + 1:02d}.png" for i in range(len(lay.placements))]
                corel.build_page(pngs, lay, a.out_dir / f"{src.stem}_A4.cdr",
                                 a.out_dir / f"{src.stem}_A4.pdf" if a.pdf else None)
                print(f"[Corel {n}/{len(done)}] {src.name}", flush=True)
            except Exception as e:
                traceback.print_exc()
                fail(src, e)

    log_path = a.out_dir / "log.csv"
    with log_path.open("a", newline="", encoding="utf-8-sig") as fh:
        csv.writer(fh).writerows([name, st, msg] for name, (st, msg) in sorted(status.items()))
    if not a.keep_work:
        shutil.rmtree(work_root, ignore_errors=True)
    n_err = sum(st == "LOI" for st, _ in status.values())
    print(f"Xong: {len(status) - n_err} OK, {n_err} lỗi. Log: {log_path}")


if __name__ == "__main__":
    main()
