"""Chạy hàng loạt: mỗi file đầu vào (.cdr hoặc .png, 25 sticker) -> 1 trang A4 .cdr.

Ví dụ (Windows):
    python batch.py D:\\sticker\\goc D:\\sticker\\a4 --limit 10
    python batch.py D:\\sticker\\goc D:\\sticker\\a4 --dry-run   # chỉ vẽ preview, không mở Corel

File đã có kết quả sẽ bị bỏ qua (chạy lại để làm tiếp), trừ khi có --overwrite.
Không bao giờ ghi đè file gốc.
"""
from __future__ import annotations

import argparse
import csv
import shutil
import traceback
from pathlib import Path

from layout import Config, plan
from preview import render
from split_stickers import split_sheet


def process(src: Path, out_dir: Path, cfg: Config, corel, pdf: bool, expected: int) -> list[str]:
    work = out_dir / "_work" / src.stem
    work.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() == ".cdr":
        if corel is None:
            raise ValueError("--dry-run chỉ đọc được .png; file .cdr cần mở Corel")
        sheet = work / "sheet.png"
        corel.export_sheet_png(src, sheet)
    else:
        sheet = src
    stickers = split_sheet(sheet, expected)
    lay = plan([s.image.size for s in stickers], cfg)
    render([s.image for s in stickers], lay, cfg).save(out_dir / f"{src.stem}_A4_preview.png")
    if corel is None:
        return lay.warnings
    pngs = []
    rotated = {p.index: p.rotated for p in lay.placements}
    for s in stickers:
        im = s.image.rotate(-90, expand=True) if rotated[s.index] else s.image
        path = work / f"{s.index + 1:02d}.png"
        im.save(path)
        pngs.append(path)
    corel.build_page(pngs, lay, out_dir / f"{src.stem}_A4.cdr",
                     out_dir / f"{src.stem}_A4.pdf" if pdf else None)
    return lay.warnings


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("in_dir", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--limit", type=int, help="chỉ xử lý N file đầu (để test)")
    ap.add_argument("--dry-run", action="store_true", help="chỉ tạo preview PNG, không mở Corel")
    ap.add_argument("--pdf", action="store_true", help="xuất thêm PDF")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--keep-work", action="store_true", help="giữ thư mục _work (ảnh tách)")
    ap.add_argument("--expected", type=int, default=25, help="số sticker mỗi tấm")
    ap.add_argument("--no-rotate", action="store_true", help="không xoay sticker 90°")
    a = ap.parse_args()

    if a.in_dir.resolve() == a.out_dir.resolve():
        raise SystemExit("out_dir phải khác in_dir để không đụng vào file gốc")
    a.out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in a.in_dir.iterdir() if p.suffix.lower() in (".cdr", ".png"))
    if a.limit:
        files = files[: a.limit]
    cfg = Config(allow_rotate=not a.no_rotate)

    corel = None
    if not a.dry_run:
        from corel_build import Corel  # chỉ import trên Windows
        corel = Corel()

    log_path = a.out_dir / "log.csv"
    ok = fail = skip = 0
    with log_path.open("a", newline="", encoding="utf-8-sig") as fh:
        log = csv.writer(fh)
        for i, src in enumerate(files, 1):
            target = a.out_dir / f"{src.stem}_A4.cdr"
            if not a.dry_run and target.exists() and not a.overwrite:
                skip += 1
                continue
            print(f"[{i}/{len(files)}] {src.name}", flush=True)
            try:
                warnings = process(src, a.out_dir, cfg, corel, a.pdf, a.expected)
                log.writerow([src.name, "OK" if not warnings else "CANH_BAO", "; ".join(warnings)])
                ok += 1
                for w in warnings:
                    print("   cảnh báo:", w)
            except Exception as e:  # một file lỗi không làm dừng cả lô
                log.writerow([src.name, "LOI", repr(e)])
                traceback.print_exc()
                fail += 1
            fh.flush()
    if not a.keep_work:
        shutil.rmtree(a.out_dir / "_work", ignore_errors=True)
    print(f"Xong: {ok} OK, {fail} lỗi, {skip} bỏ qua (đã có). Log: {log_path}")


if __name__ == "__main__":
    main()
