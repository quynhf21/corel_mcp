"""Điều khiển CorelDRAW 2020 qua COM (chỉ chạy trên Windows có cài Corel).

Hằng số Corel (cdrMillimeter, cdrPNG...) lấy từ type library qua gencache, không hard-code.
"""
from __future__ import annotations

from pathlib import Path

import win32com.client
from win32com.client import constants as C

from contour import CutConfig
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
            # FindShapes qua wrapper COM 2020 có thể trả rỗng dù có bitmap.
            # Duyệt cả nhóm để không phụ thuộc bộ lọc tên/query tuỳ chọn.
            pending = list(doc.ActivePage.Shapes)
            bitmaps = []
            while pending:
                shape = pending.pop()
                if shape.Type == C.cdrBitmapShape:
                    bitmaps.append(shape)
                elif shape.Type == C.cdrGroupShape:
                    pending.extend(shape.Shapes)
            if not bitmaps:
                raise ValueError(f"{cdr_path.name}: không thấy ảnh bitmap nào")
            shp = max(bitmaps, key=lambda s: s.SizeWidth * s.SizeHeight)
            bmp = shp.Bitmap
            dpi = round(bmp.SizeWidth / (shp.SizeWidth / 25.4))
            doc.ClearSelection()
            shp.CreateSelection()
            flt = doc.ExportBitmap(
                str(png_path), C.cdrPNG, C.cdrSelection, C.cdrRGBColorImage,
                bmp.SizeWidth, bmp.SizeHeight, dpi, dpi,
                C.cdrNormalAntiAliasing, False, True,  # dithered=False, transparent=True
                True, False, 0, None, None,  # các tuỳ chọn COM object phải là null
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
            # Wrapper Corel 2020 dùng 0 cho tham số COM object tuỳ chọn;
            # pywin32 cần None (null IDispatch), không nhận số nguyên 0.
            doc.SaveAs(str(out_cdr), None)
            if out_pdf is not None:
                doc.PublishToPDF(str(out_pdf))
        finally:
            doc.Close()

    def _polyline(self, doc, layer, polys, closed: bool, to_corel):
        """Một đối tượng curve gồm nhiều đường gấp khúc (subpath)."""
        crv = self.app.CreateCurve(doc)
        for poly in polys:
            sp = crv.CreateSubPath(*to_corel(float(poly[0][0]), float(poly[0][1])))
            for x, y in poly[1:]:
                sp.AppendLineSegment(*to_corel(float(x), float(y)))
            sp.Closed = closed
        shp = layer.CreateCurve(crv)
        shp.Fill.ApplyNoFill()
        return shp

    def _draw_cuts(self, doc, image_layer, lay: Layout, to_corel, cut: CutConfig) -> None:
        """Dấu L trên layer ảnh, contour trên TraceLayer — giống cách AidCut tạo."""
        if lay.marks:
            m = self._polyline(doc, image_layer, lay.marks, False, to_corel)
            m.Name = cut.mark_name
            m.Outline.Width = cut.mark_width
            m.Outline.Color.CMYKAssign(0, 0, 0, 100)
        if lay.cuts:
            trace = doc.ActivePage.CreateLayer(cut.trace_layer)
            for i in sorted(lay.cuts):
                t = self._polyline(doc, trace, lay.cuts[i], True, to_corel)
                t.Name = cut.trace_name
                t.Outline.Width = cut.line_width_pt * 25.4 / 72  # pt -> mm
                t.Outline.Color.RGBAssign(*cut.line_rgb)
            image_layer.Activate()

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
                layer.Import(str(sticker_pngs[p.index]), C.cdrPNG, None)
                shp = doc.ActiveShape
                shp.Name = f"sticker_{p.index + 1:02d}"
                cx, cy = to_corel(p.cx, p.cy)
                shp.SetSizeEx(cx, cy, p.w, p.h)
                # SetSizeEx chỉ đổi kích thước quanh điểm neo, không đặt tâm hình.
                shp.SetPositionEx(C.cdrCenter, cx, cy)
                if p.angle:
                    # Rotate xoay quanh tâm hình, độ dương = ngược kim đồng hồ (như Pillow)
                    shp.Rotate(p.angle)
            self._draw_cuts(doc, layer, lay, to_corel, CutConfig())
            # đường gióng (không in) tại vị trí cắt đôi tờ
            x0, y = to_corel(0, lay.cut_y)
            x1, _ = to_corel(PAGE_W, lay.cut_y)
            doc.MasterPage.GuidesLayer.CreateGuide(x0, y, x1, y)
            doc.ClearSelection()
        finally:
            self.app.Optimization = False
            self.app.Refresh()
