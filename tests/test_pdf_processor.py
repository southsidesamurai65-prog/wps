"""PDF 处理器 spec（Layer a）。

未实现时这些测试因 NotImplementedError 红——这就是 spec 看板。
实现 merge/split/rotate/extract_pages/to_images/extract_text 后逐一转绿。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from wps_tool.processors.pdf_processor import (
    extract_pdf_pages,
    extract_pdf_text,
    merge_pdfs,
    pdf_to_images,
    rotate_pdf,
    split_pdf,
)


def test_extract_pdf_text(sample_pdf):
    assert "Hello PDF World" in extract_pdf_text(str(sample_pdf))


def test_merge_pdfs(sample_pdf, sample_pdf_multipage, tmp_output_dir):
    out = tmp_output_dir / "merged.pdf"
    merge_pdfs([str(sample_pdf_multipage), str(sample_pdf)], str(out))
    assert out.exists()
    assert len(PdfReader(str(out)).pages) == 3 + 1  # 3 + 1


def test_split_pdf(sample_pdf_multipage, tmp_output_dir):
    paths = split_pdf(str(sample_pdf_multipage), str(tmp_output_dir))
    assert len(paths) == 3
    assert all(Path(p).name == f"page_{i}.pdf" for i, p in enumerate(paths, start=1))
    # 每个拆分文件应恰好 1 页——抓「共用 writer 导致页累积」的错
    # （错的实现会让 page_2 含 2 页、page_3 含 3 页，但文件名/数量仍对）。
    for p in paths:
        assert len(PdfReader(p).pages) == 1, f"{p} 应只有 1 页"


def test_rotate_pdf(sample_pdf_multipage, tmp_output_dir):
    out = tmp_output_dir / "rotated.pdf"
    rotate_pdf(str(sample_pdf_multipage), str(out), angle=90)
    assert out.exists()
    assert len(PdfReader(str(out)).pages) == 3


def test_extract_pdf_pages(sample_pdf_multipage, tmp_output_dir):
    out = tmp_output_dir / "pages.pdf"
    extract_pdf_pages(str(sample_pdf_multipage), [0, 2], str(out))
    assert out.exists()
    assert len(PdfReader(str(out)).pages) == 2


def test_pdf_to_images(sample_pdf_multipage, tmp_output_dir):
    paths = pdf_to_images(str(sample_pdf_multipage), str(tmp_output_dir), zoom=1.0)
    assert len(paths) == 3
    for p in paths:
        assert Image.open(p).size[0] > 0


def test_extract_pdf_text_multipage(sample_pdf_multipage):
    text = extract_pdf_text(str(sample_pdf_multipage))
    for page_text in ("PAGE_A", "PAGE_B", "PAGE_C"):
        assert page_text in text

