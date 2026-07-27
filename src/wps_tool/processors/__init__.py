"""processors —— 文件处理器（算法函数体是 Layer (a) TODO，*Processor 类已写好当胶水）。"""

from __future__ import annotations


def register_default_processors(registry: object) -> None:
    """把内置处理器注册到 registry。

    本函数已写好，学生不要改。它在 app 启动时被调用，把 Pdf/Docx/Pptx/Image
    四个处理器（它们的类已写好，run 会分派到各 Layer (a) TODO 函数）注册进
    ProcessorRegistry。学生实现完 Layer (b) 的 get_processor 后，整条调度链就通了。
    """
    # 延迟导入，避免本包 import 时拉起 PySide6/重库。
    from .docx_processor import DocxProcessor
    from .image_processor import ImageProcessor
    from .pdf_processor import PdfProcessor
    from .ppt_processor import PptxProcessor

    for processor in (PdfProcessor(), DocxProcessor(), PptxProcessor(), ImageProcessor()):
        registry.register(processor)
