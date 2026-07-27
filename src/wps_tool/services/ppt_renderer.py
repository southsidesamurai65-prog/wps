"""PPT 美化本地渲染器（纯函数，无网络）。

把 LLM 返回的「重设计 spec JSON」用 python-pptx 在本地重建一套干净 deck。
pptx 字节不出本机——spec 只含文本/版式/配色，渲染全在本地完成，可被单测直接驱动。

spec 协议（LLM 返回）::

    {
      "theme": {"accent": "#1F4E79", "bg": "#FFFFFF"},
      "slides": [
        {"layout": "title",      "title": "...", "subtitle": "..."},
        {"layout": "bullets",    "title": "...", "bullets": ["...", "..."]},
        {"layout": "two_column", "title": "...", "left": ["..."], "right": ["..."]}
      ]
    }

约束：spec 页数应 == 源页数（1:1）；layout 取 ``title`` / ``bullets`` / ``two_column`` 三种。
未知 layout 当 ``bullets`` 兜底（取 ``bullets``/``left``/``right``/``subtitle`` 任意非空文本）。

v1 限制：fresh deck 是「重设计文本 deck」，不搬运原图图片——重设计的是文案/版式/配色，
不是 1:1 复刻原版面。
"""

from __future__ import annotations

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR
from pptx.util import Inches, Pt

#: 默认 accent 色（spec 缺 theme 时兜底，深商务蓝）。
_DEFAULT_ACCENT = "#1F4E79"
#: 默认背景色（spec 缺 theme 时兜底，纯白）。
_DEFAULT_BG = "#FFFFFF"
#: 正文文字色（深灰，不刺眼）。
_TEXT_DARK = "#222222"
#: EMU per inch（python-pptx 内部长度单位：914400 EMU = 1 英寸）。
_EMU_IN = 914400


def _hex(color: str) -> RGBColor:
    """``"#1F4E79"`` / ``"1F4E79"`` → ``RGBColor``。"""
    return RGBColor.from_string(color.lstrip("#"))


def _set_bg(slide, color: RGBColor) -> None:
    """整页背景填 ``color``（覆盖 layout/master 的背景）。"""
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _style_run(run, *, size: int, color: RGBColor, bold: bool = False) -> None:
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color


def _add_title_bar(slide, title: str, accent: RGBColor, white: RGBColor, slide_w: int) -> None:
    """顶部 accent 色矩形条 + 白字标题（一个 shape 同时承担「色条」和「标题容器」）。"""
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, slide_w, Inches(1.2)
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = accent
    bar.line.fill.background()  # 无描边
    tf = bar.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.4)
    p = tf.paragraphs[0]
    p.text = title or ""
    for run in p.runs:
        _style_run(run, size=32, color=white, bold=True)


def _add_textbox(slide, left_in: float, top_in: float, w_in: float, h_in: float):
    return slide.shapes.add_textbox(
        Inches(left_in), Inches(top_in), Inches(w_in), Inches(h_in)
    )


def _fill_paragraphs(text_frame, items: list[str], size: int, color: RGBColor) -> None:
    """把 ``items`` 填成若干段（首段用现成 paragraphs[0]，后续 add_paragraph），
    每段前缀 ``• ``，统一字号/色。"""
    text_frame.word_wrap = True
    for i, text in enumerate(items):
        p = text_frame.paragraphs[0] if i == 0 else text_frame.add_paragraph()
        p.text = f"• {text}"
        for run in p.runs:
            _style_run(run, size=size, color=color)


def _add_subtitle(slide, sub: str, dark: RGBColor, slide_w: int, slide_h: int) -> None:
    w_in = slide_w / _EMU_IN
    tb = _add_textbox(slide, 0.6, 2.2, w_in - 1.2, 1.0)
    p = tb.text_frame.paragraphs[0]
    p.text = sub or ""
    for run in p.runs:
        _style_run(run, size=20, color=dark)


def _add_bullets(slide, bullets: list[str], dark: RGBColor, slide_w: int, slide_h: int) -> None:
    w_in, h_in = slide_w / _EMU_IN, slide_h / _EMU_IN
    tb = _add_textbox(slide, 0.6, 1.6, w_in - 1.2, h_in - 2.0)
    _fill_paragraphs(tb.text_frame, bullets, size=20, color=dark)


def _add_column(
    slide, left_in: float, items: list[str], col_w_in: float, h_in: float, dark: RGBColor
) -> None:
    tb = _add_textbox(slide, left_in, 1.6, col_w_in, h_in - 2.0)
    _fill_paragraphs(tb.text_frame, items, size=18, color=dark)


def _add_two_column(
    slide, left_items: list[str], right_items: list[str], dark: RGBColor,
    slide_w: int, slide_h: int,
) -> None:
    w_in, h_in = slide_w / _EMU_IN, slide_h / _EMU_IN
    margin, gap = 0.6, 0.6
    col_w = (w_in - 2 * margin - gap) / 2
    _add_column(slide, margin, left_items, col_w, h_in, dark)
    _add_column(slide, margin + col_w + gap, right_items, col_w, h_in, dark)


def render_beautified_deck(
    spec: dict, output_path: str, style: str = "business"
) -> str:
    """把 LLM 返回的 ``spec`` 渲染成一套干净 deck，写到 ``output_path``，返回它。

    纯本地、无网络——可被单测直接驱动。``style`` 当前只影响语义（v1 版式固定），
    预留以便后续按风格切配色。
    """
    theme = (spec.get("theme") or {}) if isinstance(spec, dict) else {}
    accent = _hex(theme.get("accent") or _DEFAULT_ACCENT)
    bg = _hex(theme.get("bg") or _DEFAULT_BG)
    white = _hex("FFFFFF")
    dark = _hex(_TEXT_DARK)

    prs = Presentation()
    slide_w, slide_h = prs.slide_width, prs.slide_height
    for slide_spec in spec.get("slides", []) or []:
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank
        _set_bg(slide, bg)
        layout = (slide_spec.get("layout") or "bullets").strip().lower()
        title = slide_spec.get("title", "") or ""
        _add_title_bar(slide, title, accent, white, slide_w)

        if layout == "title":
            sub = slide_spec.get("subtitle", "") or ""
            if sub:
                _add_subtitle(slide, sub, dark, slide_w, slide_h)
        elif layout == "two_column":
            left = slide_spec.get("left", []) or []
            right = slide_spec.get("right", []) or []
            _add_two_column(slide, left, right, dark, slide_w, slide_h)
        else:
            # bullets / 未知 layout 兜底：优先 bullets，否则把 left/right/subtitle 拼出来。
            bullets = slide_spec.get("bullets")
            if bullets is None:
                bullets = list(slide_spec.get("left", []) or [])
                bullets += list(slide_spec.get("right", []) or [])
                if slide_spec.get("subtitle"):
                    bullets = [slide_spec["subtitle"], *bullets]
            _add_bullets(slide, bullets, dark, slide_w, slide_h)

    prs.save(output_path)
    return output_path


__all__ = ["render_beautified_deck"]
