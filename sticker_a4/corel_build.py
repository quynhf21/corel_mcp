"""Điều khiển CorelDRAW 2020 qua COM (chỉ chạy trên Windows có cài Corel).

Hằng số Corel (cdrMillimeter, cdrPNG...) lấy từ type library qua gencache, không hard-code.
"""
from __future__ import annotations

from pathlib import Path

import win32com.client
from win32com.client import constants as C

from layout import PAGE_H, PAGE_W, Layout

PROG_ID = "CorelDRAW.Application.22"  # 22 = CorelDRAW 2020


class Corel:
    def __init__(self, visible: bool = True):
        self.app = win32com.client.gencache.EnsureDispatch(PROG_ID)
        self.app.Visible = visible

    # ---- đọc đầu vào .cdr ----
    def export_sheet_png(self, cdr_path: Path, png_path: Path) -> None:
        """Mở file .cdr, xuất ảnh bitmap lớn nhất (tấm sticker) ra PNG trong suốt."""
        doc = self.app.OpenDocument(str(cdr_path))
        try:
            doc.Unit = C.cdrMillimeter
            bitmaps = doc.ActivePage.Shapes.FindShapes(None, C.cdrBitmapShape, True)
            if bitmaps.Count == 0:
                raise ValueError(f"{cdr_path.name}: không thấy ảnh bitmap nào")
            shp = max((bitmaps.Item(i) for i in range(1, bitmaps.Count + 1)),
                      key=lambda s: s.SizeWidth * s.SizeHeight)
            bmp = shp.Bitmap
            dpi = round(bmp.SizeWidth / (shp.SizeWidth / 25.4))
            doc.ClearSelection()
            shp.CreateSelection()
            flt = doc.ExportBitmap(
                str(png_path), C.cdrPNG, C.cdrSelection, C.cdrRGBColorImage,
                bmp.SizeWidth, bmp.SizeHeight, dpi, dpi,
                C.cdrNormalAntiAliasing, False, True,  # dithered=False, transparent=True
            )
            flt.Finish()
        finally:
            doc.Close()

    # ---- dựng trang A4 ----
    def build_page(self, sticker_pngs: list[Path], lay: Layout, out_cdr: Path,
                   out_pdf: Path | None = None) -> None:
        """sticker_pngs[i] là ảnh (chưa xoay) của sticker có index i."""
        doc = self.app.CreateDocument()
        try:
            self._place(doc, sticker_pngs, lay)
            doc.SaveAs(str(out_cdr))
            if out_pdf is not None:
                doc.PublishToPDF(str(out_pdf))
        finally:
            doc.Close()

    def _place(self, doc, sticker_pngs: list[Path], lay: Layout) -> None:
        self.app.Optimization = True
        try:
            doc.Unit = C.cdrMillimeter
            page = doc.ActivePage
            page.SetSize(PAGE_W, PAGE_H)
            # Đổi toạ độ (mm, gốc trên-trái, y xuống) sang toạ độ trang của Corel,
            # không phụ thuộc gốc toạ độ / chiều trục y của tài liệu.
            sx = (page.RightX - page.LeftX) / PAGE_W
            sy = (page.BottomY - page.TopY) / PAGE_H

            def to_corel(x: float, y: float) -> tuple[float, float]:
                return page.LeftX + x * sx, page.TopY + y * sy

            layer = doc.ActiveLayer
            for p in lay.placements:
                layer.Import(str(sticker_pngs[p.index]))
                shp = doc.ActiveShape
                shp.Name = f"sticker_{p.index + 1:02d}"
                cx, cy = to_corel(p.cx, p.cy)
                shp.SetSizeEx(cx, cy, p.w, p.h)
                if p.angle:
                    # Rotate xoay quanh tâm hình, độ dương = ngược kim đồng hồ (như Pillow)
                    shp.Rotate(p.angle)
            # đường gióng (không in) tại vị trí cắt đôi tờ
            x0, y = to_corel(0, lay.cut_y)
            x1, _ = to_corel(PAGE_W, lay.cut_y)
            doc.MasterPage.GuidesLayer.CreateGuide(x0, y, x1, y)
            doc.ClearSelection()
        finally:
            self.app.Optimization = False
            self.app.Refresh()
