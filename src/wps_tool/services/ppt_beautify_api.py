"""PPT 美化：LLM + 本地渲染（pptx 字节不出本机）。

流程：本地解析 pptx → 把每页「文本/结构」发给 LLM（OpenAI Chat Completions，
``response_format=json_object`` 强制 JSON）→ 拿回「重设计 spec」→
用 python-pptx 在本地重建一套干净 deck（``render_beautified_deck``）。

隐私：原 pptx 的二进制本体绝不上传；请求体里只有每页文本（断言**不含** pptx 的
zip 头 ``PK\\x03\\x04``，见 ``tests/test_ppt_beautify_api.py``）。

关键设计（httpx 0.28，测试离线）：客户端必须持有「可注入 transport 的 httpx.Client」，
而不是用模块级 httpx.post（瞬时 Client 无法注入 transport，无法离线测试）。
测试用 ``httpx.MockTransport(handler)`` 注入，handler 签名 ``(req) -> Response``，
并在 handler 里断言请求体**不含** PK 头、URL/鉴权头正确。
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from wps_tool.core.errors import ApiUnavailableError
from wps_tool.processors.ppt_processor import (
    analyze_pptx_structure,
    extract_pptx_text,
)
from wps_tool.services.ppt_renderer import render_beautified_deck

#: pptx 文件的 zip 头字节（PK\\x03\\x04）。隐私断言用：LLM 请求体**不应**含它。
PPTX_MAGIC = b"PK\x03\x04"

#: OpenAI Chat Completions 端点（相对 base_url）。
_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"

#: 当前实现的 LLM 供应商；其它 provider 会抛清晰错。
_SUPPORTED_PROVIDER = "openai"

_SYSTEM_PROMPT = (
    "你是资深 PPT 设计师。把用户给的每页文本重设计成一套干净、一致的商务 deck。"
    "你可以改写标题/要点文案（更精炼有力），并决定每页版式与配色。"
    "严格输出 JSON，schema：\n"
    '{"theme": {"accent": "#RRGGBB", "bg": "#RRGGBB"}, "slides": [\n'
    '  {"layout": "title", "title": "...", "subtitle": "..."},\n'
    '  {"layout": "bullets", "title": "...", "bullets": ["...", "..."]},\n'
    '  {"layout": "two_column", "title": "...", "left": ["..."], "right": ["..."]}\n'
    "]}\n"
    "约束：slides 数量必须 == 输入页数（1:1，逐页对应，顺序一致）；"
    'layout 只能取 title / bullets / two_column；accent 用饱和度适中的深色，bg 用浅色。'
)


def _build_user_prompt(
    texts: list[dict], structure: list[dict], style: str
) -> str:
    """把本地解析的每页文本/结构拼成给 LLM 的 user 消息。"""
    lines = [f"风格：{style}。请把下面 {len(texts)} 页重设计为同页数的 spec："]
    for t, s in zip(texts, structure, strict=True):
        lines.append(
            f"第{t['slide']}页（{s.get('page_type', 'content')}）："
            + " / ".join(t.get("texts", []))
        )
    lines.append("只输出 JSON，不要任何解释。")
    return "\n".join(lines)


class PptBeautifyClient:
    """PPT 美化客户端：本地解析 → LLM 拿 spec → 本地渲染重建 deck。"""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        *,
        provider: str = _SUPPORTED_PROVIDER,
        base_url: str = "https://api.openai.com",
        transport: httpx.BaseTransport | None = None,
        timeout: float = 120,
    ) -> None:
        if provider and provider.strip().lower() != _SUPPORTED_PROVIDER:
            raise ApiUnavailableError(
                f"PPT 美化当前只支持 provider=openai，得到：{provider!r}"
            )
        self.api_key = api_key
        self.model = model
        self.provider = _SUPPORTED_PROVIDER
        # 持有可注入 Client：测试传 transport=httpx.MockTransport(...) 即可离线。
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            transport=transport,
            timeout=timeout,
        )

    @property
    def client(self) -> httpx.Client:
        """暴露底层 Client，供测试读取（如断言发出的请求）。"""
        return self._client

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def close(self) -> None:
        self._client.close()

    def _call_llm(self, user_prompt: str) -> dict[str, Any]:
        """POST OpenAI Chat Completions，解析返回的 spec JSON。"""
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        response = self._client.post(
            _CHAT_COMPLETIONS_PATH,
            json=body,
            headers=self._auth_headers(),
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        spec = json.loads(content)
        if not isinstance(spec, dict) or "slides" not in spec:
            raise ApiUnavailableError(f"LLM 返回的 spec 不合法：{content!r}")
        return spec

    def beautify_file(
        self, input_path: str, output_path: str, style: str = "business"
    ) -> str:
        """美化一个 pptx：本地解析 → 文本 spec 发 OpenAI → 本地渲染重建 deck。

        契约：
          - 本地解析：``extract_pptx_text`` + ``analyze_pptx_structure``；
          - 把每页文本/结构（不含二进制）发 OpenAI ``/v1/chat/completions``，
            ``response_format=json_object``，headers ``Authorization: Bearer {key}``；
          - 拿回 spec → ``render_beautified_deck(spec, output_path, style)``；
          - 返回 ``output_path``。
          - api_key 为空 / provider 非 openai 时 raise ``ApiUnavailableError``。
          - 请求体**不含** pptx 二进制（隐私：只发文本）。
        """
        if not self.api_key:
            raise ApiUnavailableError("api_key 不能为空")
        texts = extract_pptx_text(input_path)
        structure = analyze_pptx_structure(input_path)
        user_prompt = _build_user_prompt(texts, structure, style)
        spec = self._call_llm(user_prompt)
        # spec 页数应 == 源页数；缺失或对不齐时，按源页数补齐/截断，保证产物可打开。
        src_pages = len(texts)
        slides = spec.get("slides", [])
        if len(slides) != src_pages:
            spec = {**spec, "slides": _align_pages(slides, src_pages, texts)}
        return render_beautified_deck(spec, output_path, style)


def _align_pages(
    slides: list[dict], n: int, texts: list[dict]
) -> list[dict]:
    """spec 页数与源页数对不齐时的兜底：截断到 n，或用源文本补足。"""
    aligned = list(slides[:n])
    for i in range(len(aligned), n):
        page_texts = texts[i].get("texts", []) if i < len(texts) else []
        aligned.append(
            {
                "layout": "title" if i == 0 else "bullets",
                "title": page_texts[0] if page_texts else f"第{i + 1}页",
                "bullets": page_texts[1:] if page_texts else [],
            }
        )
    return aligned


__all__ = ["PPTX_MAGIC", "PptBeautifyClient"]
