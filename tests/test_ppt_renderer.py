"""PPT 本地渲染器 spec（纯函数，无网络）。

给定固定 spec → ``render_beautified_deck`` → 产物可打开、页数对、标题/bullets 在场、
accent 色填到了某 shape。覆盖三种 layout 与 theme 缺省兜底、未知 layout 兜底。
"""

from __future__ import annotations

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_FILL

from wps_tool.services.ppt_renderer import render_beautified_deck

SPEC = {
    "theme": {"accent": "#1F4E79", "bg": "#FFFFFF"},
    "slides": [
        {"layout": "title", "title": "季度汇报", "subtitle": "2026 Q2"},
        {"layout": "bullets", "title": "业绩", "bullets": ["收入 +18%", "成本 -4%"]},
        {"layout": "two_column", "title": "对比", "left": ["Q1 数据"], "right": ["Q2 数据"]},
    ],
}


def _rendered(out_path, spec):
    render_beautified_deck(spec, str(out_path))
    assert out_path.read_bytes()[:4] == b"PK\x03\x04"  # 合法 pptx zip
    return Presentation(str(out_path))


def _all_text(prs) -> str:
    return "\n".join(
        shape.text_frame.text
        for slide in prs.slides
        for shape in slide.shapes
        if shape.has_text_frame
    )


def _has_accent_fill(prs, hex_color: str) -> bool:
    target = RGBColor.from_string(hex_color.lstrip("#"))
    for slide in prs.slides:
        for shape in slide.shapes:
            fill = shape.fill
            if fill.type == MSO_FILL.SOLID and fill.fore_color.rgb == target:
                return True
    return False


def test_renders_all_layouts(tmp_output_dir):
    out = tmp_output_dir / "b.pptx"
    prs = _rendered(out, SPEC)
    assert len(prs.slides) == len(SPEC["slides"])

    text = _all_text(prs)
    for needle in ("季度汇报", "2026 Q2", "业绩", "收入 +18%", "成本 -4%",
                    "对比", "Q1 数据", "Q2 数据"):
        assert needle in text, f"missing {needle!r}"

    assert _has_accent_fill(prs, SPEC["theme"]["accent"])


def test_theme_defaults_when_missing(tmp_output_dir):
    """spec 没有 theme 时用默认 accent/bg，照样产出合法 deck、accent 填上。"""
    spec = {"slides": [{"layout": "bullets", "title": "X", "bullets": ["y"]}]}
    out = tmp_output_dir / "d.pptx"
    prs = _rendered(out, spec)
    assert len(prs.slides) == 1
    assert _has_accent_fill(prs, "#1F4E79")  # 默认 accent


def test_unknown_layout_falls_back_to_bullets(tmp_output_dir):
    """未知 layout → 当 bullets 兜底（用 left/right/subtitle 任意文本）。"""
    spec = {
        "theme": {"accent": "#AA00AA", "bg": "#FFFFFF"},
        "slides": [
            {"layout": "weird", "title": "T", "left": ["L1"], "right": ["R1"]},
        ],
    }
    out = tmp_output_dir / "u.pptx"
    prs = _rendered(out, spec)
    text = _all_text(prs)
    assert "L1" in text and "R1" in text
    assert _has_accent_fill(prs, "#AA00AA")
