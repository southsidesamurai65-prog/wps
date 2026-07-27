"""PPT 美化 API 客户端 spec（Layer a 服务算法，离线）。

用 httpx.MockTransport 注入，handler 里断言请求体含 pptx 的 PK 头字节
（上传完整文件模式）。
"""

from __future__ import annotations

import httpx

from wps_tool.services.ppt_beautify_api import PPTX_MAGIC, PptBeautifyClient


def _capture(captured, body=b""):
    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        captured["content"] = request.content
        return httpx.Response(200, content=body)

    return handler


def test_beautify_file_sends_full_pptx(sample_pptx, tmp_output_dir):
    captured: dict = {}
    out = tmp_output_dir / "beautified.pptx"
    body = b"PPTX_RESULT_BYTES"
    transport = httpx.MockTransport(_capture(captured, body=body))
    client = PptBeautifyClient("https://api.example.com", "key", transport=transport)

    client.beautify_file(str(sample_pptx), str(out))
    assert out.read_bytes() == body

    assert PPTX_MAGIC in captured["content"]  # 上传了完整文件
    assert captured["request"].url.path == "/ppt/beautify"
    assert captured["request"].headers["Authorization"] == "Bearer key"
    client.close()
