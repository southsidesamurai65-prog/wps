"""配置管理（已写好，学生不要改）。

用 pydantic-settings 从 .env / 环境变量读配置。隐私原则默认关闭外部 API。
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """运行配置。从 .env 文件或环境变量读取。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    default_output_dir: str = ""
    enable_api_upload: bool = False       # 默认关闭，所有功能本地处理
    task_max_workers: int = 2             # 后台并发数

    # PPT 美化用的 LLM（本地解析 → 文本发 LLM 拿「重设计 spec」→ 本地渲染重建 deck。
    # pptx 字节不出本机，只发每页文本给 LLM）。
    llm_provider: str = "openai"          # 当前只实现 openai；其它 provider 会抛清晰错
    llm_api_key: str = ""                 # 从 .env 的 LLM_API_KEY 读
    llm_model: str = "gpt-4o"             # 从 .env 的 LLM_MODEL 读，避免写死过时模型名

    def llm_configured(self) -> bool:
        """PPT 美化 LLM 是否已配置（provider + key 都非空）。"""
        return bool(self.llm_provider and self.llm_api_key)


__all__ = ["Settings"]
