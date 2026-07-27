"""PPT 美化外部 API 客户端。

Layer (a) 服务算法 TODO：PptBeautifyClient.beautify_file / beautify_by_outline。
类结构（构造、可注入 httpx.Client、鉴权头、关闭）已写好。

关键设计（httpx 0.28，测试离线）：客户端必须持有「可注入 transport 的 httpx.Client」，
而不是用模块级 httpx.post（瞬时 Client 无法注入 transport，无法离线测试）。
测试用 httpx.MockTransport(handler) 注入，handler 签名 (req)->Response，
并在 handler 里断言请求体隐私（仅大纲模式不含 .pptx / PK 头字节）。
"""

from __future__ import annotations

import httpx

#: 上传完整 pptx 时用的 Content-Type。
PPTX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)

#: pptx 文件的 zip 头字节（PK\\x03\\x04），用于隐私断言：仅大纲模式请求体不应含它。
PPTX_MAGIC = b"PK\x03\x04"


class PptBeautifyClient:
    """PPT 美化 API 客户端（构造已写好，两个 beautify 方法是 Layer (a) TODO）。"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 120,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        # 持有可注入 Client：测试传 transport=httpx.MockTransport(...) 即可离线。
        self._client = httpx.Client(
            base_url=self.base_url,
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

    def beautify_file(
        self, input_path: str, output_path: str, style: str = "business"
    ) -> str:
        """[学习·Layer (a) TODO] 上传完整 pptx，下载美化后的 pptx，返回 output_path。

        契约：
          - POST {base_url}/ppt/beautify，multipart：file=(filename, fobj, PPTX_CONTENT_TYPE)，
            data={"style": style, "privacy_mode": "full_file"}，
            headers=鉴权头；
          - response.raise_for_status()；把 response.content 写到 output_path；
          - 返回 output_path。
          - base_url/api_key 为空时 raise ApiUnavailableError。

        提示：
          - with open(input_path, "rb") as f: files={"file":(Path(input_path).name, f, PPTX_CONTENT_TYPE)}
          - self._client.post("/ppt/beautify", files=..., data=..., headers=self._auth_headers())
          - 测试断言请求体含 PPTX_MAGIC（b"PK\\x03\\x04"）——上传完整文件模式。
        """
        raise NotImplementedError("TODO(Layer a): 实现 PptBeautifyClient.beautify_file")

    def beautify_by_outline(
        self, slides: list[dict], style: str = "business", language: str = "zh-CN"
    ) -> dict:
        """[学习·Layer (a) TODO] 只上传文本大纲（隐私优先），返回美化建议 JSON。

        契约：
          - POST {base_url}/ppt/beautify-outline，json={"slides": slides, "style": style, "language": language}，
            headers=鉴权头；
          - response.raise_for_status()；返回 response.json()。
          - base_url/api_key 为空时 raise ApiUnavailableError。

        提示：
          - self._client.post("/ppt/beautify-outline", json=..., headers=self._auth_headers())
          - 测试断言请求体是 JSON 且不含 PPTX_MAGIC（仅大纲、不上传完整文件）。
        """
        raise NotImplementedError("TODO(Layer a): 实现 PptBeautifyClient.beautify_by_outline")


__all__ = ["PPTX_CONTENT_TYPE", "PPTX_MAGIC", "PptBeautifyClient"]
