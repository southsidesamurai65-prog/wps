"""处理器注册表 spec（Layer b）。

用 _fakes.FakeProcessor 注入，不依赖任何真实处理器——只测 dispatch 本身。
未实现 get_processor 时这些测试因 NotImplementedError 红。
"""

from __future__ import annotations

import pytest
from _fakes import FakeProcessor

from wps_tool.core.errors import NoProcessorError
from wps_tool.core.registry import ProcessorRegistry


def test_get_processor_dispatches_by_extension():
    reg = ProcessorRegistry()
    reg.register(FakeProcessor(ext=".pdf", result="PDF_RESULT"))
    reg.register(FakeProcessor(ext=".docx", result="DOCX_RESULT"))

    assert reg.get_processor("note.pdf").run("note.pdf", "x", {}) == "PDF_RESULT"
    assert reg.get_processor("note.docx").run("note.docx", "x", {}) == "DOCX_RESULT"


def test_get_processor_unknown_extension_raises():
    reg = ProcessorRegistry()
    reg.register(FakeProcessor(ext=".pdf"))
    with pytest.raises(NoProcessorError):
        reg.get_processor("unknown.xyz")


def test_get_processor_empty_registry_raises():
    reg = ProcessorRegistry()
    with pytest.raises(NoProcessorError):
        reg.get_processor("anything.pdf")


def test_can_handle_true_and_false():
    reg = ProcessorRegistry()
    reg.register(FakeProcessor(ext=".pdf"))
    assert reg.can_handle("a.pdf") is True
    assert reg.can_handle("a.xyz") is False
