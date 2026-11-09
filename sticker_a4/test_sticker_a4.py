"""pytest test_sticker_a4.py — chạy được cả khi không có Windows/Corel."""
from __future__ import annotations

import itertools
import sys
import types
from pathlib import Path
from unittest import mock

import pytest

from layout import Config, plan

# kích thước (px) đo từ anh_goc_1.png: có hình dọc, hình vuông, hình dẹt
SIZES = [(275, 262), (274, 257), (216, 275), (172, 274), (204, 274), (225, 274), (275, 175),
         (204, 275), (217, 274), (201, 275), (194, 274), (186, 276), (252, 264), (273, 261),
         (274, 239), (283, 274), (198, 274), (186, 274), (231, 284), (218, 271), (214, 285),
         (218, 274), (260, 274), (279, 140), (250, 273)]


def test_layout_fits_region_with_gap():
    cfg = Config()
    lay = plan(SIZES, cfg)
    assert sorted(p.index for p in lay.placements) == list(range(len(SIZES)))
    eps = 1e-6
    for p in lay.placements:
        assert cfg.left - eps <= p.x and p.x + p.w <= cfg.right + eps
        assert cfg.top - eps <= p.y and p.y + p.h <= cfg.bottom + eps
        # không hình nào vắt qua đường cắt đôi
        assert p.y + p.h <= lay.cut_y - cfg.cut_gap / 2 + eps or p.y >= lay.cut_y + cfg.cut_gap / 2 - eps
        assert max(p.w, p.h) >= cfg.min_size
    for a, b in itertools.combinations(lay.placements, 2):
        dx = max(b.x - (a.x + a.w), a.x - (b.x + b.w))
        dy = max(b.y - (a.y + a.h), a.y - (b.y + b.h))
        assert max(dx, dy) >= cfg.gap - eps, (a, b)


def test_aspect_ratio_preserved():
    lay = plan(SIZES, Config())
    for p in lay.placements:
        w, h = SIZES[p.index]
        if p.rotated:
            w, h = h, w
        assert p.w / p.h == pytest.approx(w / h, rel=1e-9)


def _fake_win32com():
    win32com = types.ModuleType("win32com")
    client = types.ModuleType("win32com.client")
    client.gencache = types.SimpleNamespace(EnsureDispatch=mock.MagicMock())
    client.constants = types.SimpleNamespace(cdrMillimeter=3)
    win32com.client = client
    return {"win32com": win32com, "win32com.client": client}


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
        doc.SaveAs.assert_not_called()
        assert corel.app.Optimization is False
    sys.modules.pop("corel_build", None)
