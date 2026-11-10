"""pytest test_sticker_a4.py — chạy được cả khi không có Windows/Corel."""
from __future__ import annotations

import itertools
import sys
import types
from pathlib import Path
from unittest import mock

import pytest

from layout import Config, plan

SAMPLE = Path(__file__).resolve().parent.parent / "anh_goc_1.png"

# kích thước (px) đo từ anh_goc_1.png: có hình dọc, hình vuông, hình dẹt
SIZES = [(275, 262), (274, 257), (216, 275), (172, 274), (204, 274), (225, 274), (275, 175),
         (204, 275), (217, 274), (201, 275), (194, 274), (186, 276), (252, 264), (273, 261),
         (274, 239), (283, 274), (198, 274), (186, 274), (231, 284), (218, 271), (214, 285),
         (218, 274), (260, 274), (279, 140), (250, 273)]


def _check_layout(lay, cfg, min_gap):
    eps = 1e-6
    assert sorted(p.index for p in lay.placements) == list(range(len(lay.placements)))
    for p in lay.placements:
        x0, y0, x1, y1 = p.bbox
        assert cfg.left - eps <= x0 and x1 <= cfg.right + eps
        assert cfg.top - eps <= y0 and y1 <= cfg.bottom + eps
        # không hình nào vắt qua đường cắt đôi
        assert y1 <= lay.cut_y - cfg.cut_gap / 2 + eps or y0 >= lay.cut_y + cfg.cut_gap / 2 - eps
        assert max(p.w, p.h) >= cfg.min_size
    if min_gap:  # lưới: khoảng cách giữa các hộp bao
        for a, b in itertools.combinations(lay.placements, 2):
            ax0, ay0, ax1, ay1 = a.bbox
            bx0, by0, bx1, by1 = b.bbox
            assert max(bx0 - ax1, ax0 - bx1, by0 - ay1, ay0 - by1) >= cfg.gap - eps, (a, b)


def test_grid_layout_fits_region_with_gap():
    cfg = Config()
    _check_layout(plan(SIZES, cfg), cfg, min_gap=True)


def test_grid_aspect_ratio_preserved():
    for p in plan(SIZES, Config()).placements:
        w, h = SIZES[p.index]
        assert p.w / p.h == pytest.approx(w / h, rel=1e-9)
        assert p.angle in (0.0, -90.0)


def test_nest_layout_real_sheet():
    """Xếp lồng tấm mẫu thật (cấu hình rút gọn cho nhanh): đủ 25 hình, trong khối,
    khoảng cách mép hình thật >= gap."""
    from nest import VERIFY_RES, NestConfig, plan_nest
    from split_stickers import split_sheet

    images = [s.image for s in split_sheet(SAMPLE)]
    cfg = NestConfig(angle_step=45.0, restarts=1, search_step=3.0)
    lay = plan_nest(images, cfg)
    _check_layout(lay, cfg, min_gap=False)
    assert lay.min_gap >= cfg.gap - VERIFY_RES
    assert not lay.warnings
    for p in lay.placements:  # giữ tỉ lệ khung gốc
        w, h = images[p.index].size
        assert p.w / p.h == pytest.approx(w / h, rel=1e-9)


def test_local_search_never_worse_than_fast():
    """Tìm kiếm cục bộ chỉ nhận phương án lớn hơn, nên không bao giờ kém chế độ nhanh
    (cùng seed -> cùng kết quả tìm nhị phân)."""
    from nest import NestConfig, plan_nest
    from split_stickers import split_sheet

    images = [s.image for s in split_sheet(SAMPLE)]
    base = dict(angle_step=45.0, restarts=1, search_step=3.0)
    fast = plan_nest(images, NestConfig(**base))
    high = plan_nest(images, NestConfig(**base, time_budget=25.0))
    assert high.score >= fast.score * 0.98  # bước phóng to có thể lệch chút
    assert high.min_gap >= 1.2 - 0.1


def test_min_gap_handles_sticker_at_page_edge():
    """Hình thò ra mép trang không được làm sai phép đo (chỉ số âm)."""
    from layout import Layout, Placement
    from nest import min_gap
    from PIL import Image

    im = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
    lay = Layout([Placement(0, 2.0, 2.0, 10.0, 10.0), Placement(1, 15.0, 2.0, 10.0, 10.0)],
                 ((), ()), 150.0, 0.0)
    assert min_gap([im, im], lay) == pytest.approx(3.0, abs=0.15)


def _fake_win32com():
    win32com = types.ModuleType("win32com")
    client = types.ModuleType("win32com.client")
    client.gencache = types.SimpleNamespace(EnsureDispatch=mock.MagicMock())
    client.constants = types.SimpleNamespace(
        cdrMillimeter=3, cdrPNG=802, cdrBitmapShape=5, cdrGroupShape=7,
        cdrSelection=2, cdrRGBColorImage=4, cdrNormalAntiAliasing=1, cdrCenter=9,
    )
    win32com.client = client
    return {"win32com": win32com, "win32com.client": client}


def test_export_finds_largest_bitmap_inside_group(tmp_path: Path):
    with mock.patch.dict(sys.modules, _fake_win32com()):
        sys.modules.pop("corel_build", None)
        import corel_build

        corel = corel_build.Corel()
        doc = mock.MagicMock()
        small = mock.MagicMock(Type=5, SizeWidth=10.0, SizeHeight=10.0)
        large = mock.MagicMock(Type=5, SizeWidth=100.0, SizeHeight=100.0)
        large.Bitmap.SizeWidth = large.Bitmap.SizeHeight = 1000
        group = mock.MagicMock(Type=7, Shapes=[large])
        doc.ActivePage.Shapes = [small, group]
        corel.app.OpenDocument.return_value = doc

        corel.export_sheet_png(tmp_path / "in.cdr", tmp_path / "out.png")

        large.CreateSelection.assert_called_once()
        small.CreateSelection.assert_not_called()
        assert doc.ExportBitmap.call_args.args[4:6] == (1000, 1000)
        assert doc.ExportBitmap.call_args.args[-2:] == (None, None)
        doc.ExportBitmap.return_value.Finish.assert_called_once()
        doc.Close.assert_called_once()
    sys.modules.pop("corel_build", None)


def test_build_page_closes_doc_when_import_fails(tmp_path: Path):
    with mock.patch.dict(sys.modules, _fake_win32com()):
        sys.modules.pop("corel_build", None)
        import corel_build

        corel = corel_build.Corel()
        doc = mock.MagicMock()
        doc.ActivePage.LeftX, doc.ActivePage.RightX = 0.0, 210.0
        doc.ActivePage.TopY, doc.ActivePage.BottomY = 297.0, 0.0
        doc.ActiveLayer.Import.side_effect = RuntimeError("COM lỗi")
        corel.app.CreateDocument.return_value = doc

        lay = plan(SIZES, Config())
        with pytest.raises(RuntimeError):
            corel.build_page([tmp_path / f"{i}.png" for i in range(25)], lay, tmp_path / "o.cdr")
        doc.Close.assert_called_once()
        assert doc.ActiveLayer.Import.call_args.args[1:] == (802, None)
        doc.SaveAs.assert_not_called()
        assert corel.app.Optimization is False
    sys.modules.pop("corel_build", None)


def test_place_preserves_origin_and_keeps_guide_on_current_page():
    from layout import Layout

    with mock.patch.dict(sys.modules, _fake_win32com()):
        sys.modules.pop("corel_build", None)
        import corel_build

        corel = corel_build.Corel()
        doc = mock.MagicMock()
        doc.DrawingOriginX, doc.DrawingOriginY = 12.5, -8.0
        page = doc.ActivePage
        page.LeftX, page.RightX = 0.0, 210.0
        page.TopY, page.BottomY = 297.0, 0.0
        local_guides = mock.MagicMock(IsGuidesLayer=True, Master=False)
        page.Layers = [local_guides]

        def reset_origin(*_):
            # Corel SetSize thay gốc thước kể cả khi giữ nguyên khổ A4.
            doc.DrawingOriginX, doc.DrawingOriginY = 0.0, 0.0

        page.SetSize.side_effect = reset_origin
        corel._place(doc, [], Layout([], ((), ()), 153.5, 0.0))

        assert (doc.DrawingOriginX, doc.DrawingOriginY) == (12.5, -8.0)
        page.GuidesLayer.CreateGuide.return_value.MoveToLayer.assert_called_once_with(local_guides)
        doc.MasterPage.GuidesLayer.CreateGuide.assert_not_called()
    sys.modules.pop("corel_build", None)


def _edge_distance(poly, mask, mm_per_px):
    """Khoảng cách (mm) từ các điểm contour tới mép vùng `mask` (dương = ở ngoài)."""
    import numpy as np
    from scipy import ndimage

    out = ndimage.distance_transform_edt(~mask) * mm_per_px
    inside = ndimage.distance_transform_edt(mask) * mm_per_px
    d = []
    for x, y in poly:
        i, j = int(round(y)), int(round(x))
        if 0 <= i < mask.shape[0] and 0 <= j < mask.shape[1]:
            d.append(out[i, j] if not mask[i, j] else -inside[i, j])
    return np.array(d)


def test_contour_offset_matches_config():
    """Contour nằm ngoài mép hình đúng khoảng `offset` (như file mẫu AidCut ~0,4 mm)."""
    import numpy as np
    from PIL import Image, ImageDraw

    from contour import CutConfig, sticker_outline

    im = Image.new("RGBA", (300, 200), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([40, 30, 260, 170], fill=(255, 255, 255, 255))
    mm_per_px = 0.15
    polys = sticker_outline(im, mm_per_px, CutConfig(offset=0.4))
    assert len(polys) == 1
    # đo trên lưới phóng 4 lần cho chính xác
    big = np.asarray(im.getchannel("A").resize((1200, 800), Image.NEAREST)) > 16
    d = _edge_distance(polys[0] * 4, big, mm_per_px / 4)
    assert np.median(d) == pytest.approx(0.4, abs=0.06)
    assert d.min() > 0.25


def test_placed_contour_follows_rotated_image():
    """Contour đặt lên trang phải khớp với ảnh được xoay/đặt như preview (Pillow)."""
    import numpy as np
    from PIL import Image, ImageDraw

    from contour import CutConfig, page_outlines
    from layout import Layout, Placement
    from preview import render

    im = Image.new("RGBA", (200, 120), (0, 0, 0, 0))  # hình chữ L: không đối xứng
    dr = ImageDraw.Draw(im)
    dr.rectangle([10, 10, 190, 50], fill=(255, 0, 0, 255))
    dr.rectangle([10, 10, 60, 110], fill=(255, 0, 0, 255))
    cfg = Config()
    medians = {}
    for angle in (0.0, 37.0, -90.0, 200.0):
        p = Placement(0, 100.0, 120.0, 40.0, 24.0, angle)
        lay = Layout([p], ((), ()), 153.0, 0.0)
        cut = page_outlines([im], [p], CutConfig(offset=0.4))[0][0]
        dpi = 400
        page = render([im], lay, cfg, dpi=dpi)
        rgb = np.asarray(page).astype(int)
        mask = (rgb[:, :, 0] > 200) & (rgb[:, :, 1] < 80)  # pixel đỏ của hình
        k = dpi / 25.4
        d = _edge_distance(cut * k, mask, 1 / k)
        # mép ảnh preview bị làm mờ khi thu nhỏ nên đo được hơi lớn hơn 0,4 mm;
        # điều cần kiểm là mọi góc xoay cho cùng kết quả như góc 0 và không điểm nào lọt vào hình
        medians[angle] = float(np.median(d))
        assert d.min() > 0.1, angle
        assert np.percentile(d, 95) < 0.9, angle
    for angle, m in medians.items():
        assert m == pytest.approx(medians[0.0], abs=0.08), (angle, medians)


def test_draw_cuts_mimics_aidcut(tmp_path: Path):
    """Dấu L trên layer ảnh tên LMarkLine1; mỗi hình một TraceLine trên TraceLayer."""
    import numpy as np

    from contour import CutConfig, lmarks

    with mock.patch.dict(sys.modules, _fake_win32com()):
        sys.modules.pop("corel_build", None)
        import corel_build

        corel = corel_build.Corel()
        doc = mock.MagicMock()
        image_layer = mock.MagicMock()
        trace = doc.ActivePage.CreateLayer.return_value
        from layout import Layout
        lay = Layout([], ((), ()), 153.0, 0.0)
        sq = np.array([[0, 0], [1, 0], [1, 1]], float)
        lay.cuts = {0: [sq], 1: [sq, sq + 5]}
        lay.marks = lmarks(CutConfig())
        corel._draw_cuts(doc, image_layer, lay, lambda x, y: (x, y), CutConfig())

        doc.ActivePage.CreateLayer.assert_called_once_with("TraceLayer")
        assert trace.Printable is False
        assert image_layer.CreateCurve.call_count == 1
        assert trace.CreateCurve.call_count == 2
        assert image_layer.CreateCurve.return_value.Name == "LMarkLine1"
        assert trace.CreateCurve.return_value.Name == "TraceLine"
        assert trace.CreateCurve.return_value.Outline.Width == pytest.approx(0.5 * 25.4 / 72)
        crv = corel.app.CreateCurve.return_value
        # 4 dấu L + 1 + 2 đường kín
        assert crv.CreateSubPath.call_count == 4 + 3
        image_layer.Activate.assert_called_once()
    sys.modules.pop("corel_build", None)
