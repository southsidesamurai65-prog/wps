"""LibreOffice 命令行封装（已写好，学生不要改）。

用 LibreOffice 的 headless 模式把 DOCX/PPTX 转 PDF。本服务是「外部能力」胶水，
不算 Layer (a) TODO——学生只需在测试里理解它（test_office_convert.py 按二进制
是否安装决定 skip）。

字体提示：转换效果依赖系统字体；中文文档若缺字体会被替换，建议预装常用中文字体。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from wps_tool.core.errors import ConversionError

#: 候选二进制名（Linux/macOS: libreoffice/soffice；Windows: soffice.exe）。
_CANDIDATES = ("libreoffice", "soffice", "soffice.exe")


def find_libreoffice() -> str | None:
    """返回可用的 LibreOffice/soffice 可执行路径，找不到返回 None。"""
    for name in _CANDIDATES:
        path = shutil.which(name)
        if path:
            return path
    return None


def libreoffice_available() -> bool:
    """系统是否安装了 LibreOffice。"""
    return find_libreoffice() is not None


def convert_office_to_pdf(input_path: str, output_dir: str) -> Path:
    """把 DOCX/PPTX（等 Office 文件）转为 PDF，返回输出 PDF 路径。

    抛 ConversionError：未安装 / 转换失败（含字体缺失导致的非零退出）/ 超时 / 无输出。
    """
    binary = find_libreoffice()
    if not binary:
        raise ConversionError("未找到 LibreOffice/soffice，请先安装后重试。")

    out_folder = Path(output_dir)
    out_folder.mkdir(parents=True, exist_ok=True)

    cmd = [
        binary,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_folder),
        str(input_path),
    ]
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr or exc.stdout or str(exc)
        raise ConversionError(f"LibreOffice 转换失败：{detail}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ConversionError("LibreOffice 转换超时（>180s）。") from exc

    pdf_path = out_folder / f"{Path(input_path).stem}.pdf"
    if not pdf_path.exists():
        raise ConversionError(f"转换完成但未找到输出文件：{pdf_path}")
    return pdf_path


__all__ = ["convert_office_to_pdf", "find_libreoffice", "libreoffice_available"]
