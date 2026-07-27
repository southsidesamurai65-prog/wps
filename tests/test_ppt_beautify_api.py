"""PPT 美化客户端 spec（LLM + 本地渲染，离线）。

用 httpx.MockTransport 注入：handler 回一段 canned OpenAI Chat Completions 响应，
断言：
  - 产物是合法 pptx（zip 头 PK\\x03\\x04）、可打开、页数 == spec 页数、标题在场；
  - 请求体**不含** pptx 二进制（隐私：只发文本）——断言 PPTX_MAGIC **不在** content；
  - 请求打到 /v1/chat/completions、带 Authorization、含 model 与 response_format。
"""

from __future__ import annotations

import json

import httpx
import pytest
from pptx import Presentation

from wps_tool.core.errors import ApiUnavailableError
from wps_tool.services.ppt_beautify_api import PPTX_MAGIC, PptBeautifyClient

#: canned spec：2 页，与 conftest 的 sample_pptx（2 页）页数一致。
SPEC = {
    "theme": {"accent": "#1F4E79", "bg": "#FFFFFF"},
    "slides": [
        {"layout": "title", "title": "重设标题", "subtitle": "2026"},
        {"layout": "bullets", "title": "要点", "bullets": ["A1", "A2"]},
    ],
}


def _chat_completion_handler(captured: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        captured["content"] = request.content
        body = json.loads(request.content)
        captured["body"] = body
        content = json.dumps(SPEC, ensure_ascii=False)
        resp = {
            "choices": [{"message": {"role": "assistant", "content": content}}]
        }
        return httpx.Response(200, json=resp)

    return handler


def test_beautify_file_sends_text_only_and_renders(sample_pptx, tmp_output_dir):
    captured: dict = {}
    out = tmp_output_dir / "beautified.pptx"
    transport = httpx.MockTransport(_chat_completion_handler(captured))
    client = PptBeautifyClient("key", model="gpt-4o", transport=transport)

    result = client.beautify_file(str(sample_pptx), str(out), style="business")

    assert result == str(out)
    # 产物是合法 pptx zip，且渲染了 spec 的页数与标题。
    assert out.read_bytes().startswith(PPTX_MAGIC)
    prs = Presentation(str(out))
    assert len(prs.slides) == len(SPEC["slides"])
    rendered_text = "\n".join(
        shape.text_frame.text
        for slide in prs.slides
        for shape in slide.shapes
        if shape.has_text_frame
    )
    assert "重设标题" in rendered_text
    assert "A1" in rendered_text

    # 隐私：请求体不含 pptx 二进制（只发文本）。
    assert PPTX_MAGIC not in captured["content"]

    # 请求打到 OpenAI Chat Completions，带鉴权，body 含 model 与 response_format。
    assert captured["request"].url.path == "/v1/chat/completions"
    assert captured["request"].headers["Authorization"] == "Bearer key"
    assert captured["body"]["model"] == "gpt-4o"
    assert captured["body"]["response_format"] == {"type": "json_object"}
    # user 消息里带的是源 pptx 的每页文本（T1/sub/T2/b1/b2），而非二进制。
    user_msg = next(
        m["content"] for m in captured["body"]["messages"] if m["role"] == "user"
    )
    assert "T1" in user_msg and "T2" in user_msg
    client.close()


def test_beautify_file_empty_key_raises(tmp_output_dir, sample_pptx):
    client = PptBeautifyClient("", model="gpt-4o", transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    with pytest.raises(ApiUnavailableError):
        client.beautify_file(str(sample_pptx), str(tmp_output_dir / "x.pptx"))
    client.close()


def test_unsupported_provider_raises():
    with pytest.raises(ApiUnavailableError):
        PptBeautifyClient("key", model="gpt-4o", provider="gemini")


def test_build_beautify_client_uses_llm_base_url():
    """app.py 装配：LLM_BASE_URL 真传进 client.base_url（不写死）。

    防回归：以后 build_beautify_client 漏传 base_url 时此测试会红——
    会退回 client 构造器的默认 https://api.openai.com，与配置不符。
    """
    from wps_tool.app import build_beautify_client
    from wps_tool.models.settings import Settings

    s = Settings(
        _env_file=None,
        enable_api_upload=True,
        llm_provider="openai",
        llm_api_key="k",
        llm_base_url="https://api.my-relay.example.com",
    )
    client = build_beautify_client(s)
    assert client is not None
    assert (
        str(client.client.base_url).rstrip("/")
        == "https://api.my-relay.example.com"
    )
    client.close()
