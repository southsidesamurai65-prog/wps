"""PPT 美化 API 客户端 spec（Layer a 服务算法，离线）。

用 httpx.MockTransport 注入，handler 里断言请求体隐私：
- 仅大纲模式：请求体是 JSON、不含 pptx 的 PK 头字节；
- 完整文件模式：请求体含 PK 头字节。
"""

from __future__ import annotations

import httpx

from wps_tool.services.ppt_beautify_api import PPTX_MAGIC, PptBeautifyClient


def _capture(captured, *, json_resp=None, body=b""):
    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        captured["content"] = request.content
        if json_resp is not None:
            return httpx.Response(200, json=json_resp)
        return httpx.Response(200, content=body)

    return handler


def test_beautify_by_outline_sends_json_not_file():
    captured: dict = {}
    transport = httpx.MockTransport(_capture(captured, json_resp={"ok": True}))
    client = PptBeautifyClient("https://api.example.com", "key", transport=transport)

    result = client.beautify_by_outline([{"slide": 1, "texts": ["T1"]}])
    assert result == {"ok": True}

    content = captured["content"]
    assert b'"slides"' in content  # JSON 大纲
    assert PPTX_MAGIC not in content  # 隐私：没上传完整 pptx
    assert captured["request"].url.path == "/ppt/beautify-outline"
    assert captured["request"].headers["Authorization"] == "Bearer key"
    client.close()


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
