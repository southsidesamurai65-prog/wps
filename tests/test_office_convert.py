"""LibreOffice 转换 spec。

LibreOffice/soffice 未安装时整文件 skip（避免假红）。已装时验证 docx→pdf。
"""

from __future__ import annotations

import shutil

import pytest

_HAS_OFFICE = bool(shutil.which("libreoffice") or shutil.which("soffice"))
pytestmark = pytest.mark.skipif(not _HAS_OFFICE, reason="未安装 LibreOffice/soffice")


def test_convert_docx_to_pdf(sample_docx, tmp_output_dir):
    from wps_tool.services.office_convert import convert_office_to_pdf

    pdf = convert_office_to_pdf(str(sample_docx), str(tmp_output_dir))
    assert pdf.exists()
    assert pdf.suffix == ".pdf"


def test_libreoffice_available_matches_detect():
    from wps_tool.services.office_convert import libreoffice_available

    assert libreoffice_available() is _HAS_OFFICE
