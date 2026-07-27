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

    ppt_beautify_base_url: str = ""
    ppt_beautify_api_key: str = ""
    default_output_dir: str = ""
    enable_api_upload: bool = False       # 默认关闭，所有功能本地处理
    task_max_workers: int = 2             # 后台并发数

    # 本地辅助 LLM（美化建议等可选增强能力用，与美化外部 API 相互独立）。
    llm_provider: str = "gemini"          # gemini | claude | openai
    llm_api_key: str = ""                 # 从 .env 的 LLM_API_KEY 读

    def api_configured(self) -> bool:
        """美化 API 是否已配置（url + key 都非空）。"""
        return bool(self.ppt_beautify_base_url and self.ppt_beautify_api_key)

    def llm_configured(self) -> bool:
        """本地辅助 LLM 是否已配置（provider + key 都非空）。"""
        return bool(self.llm_provider and self.llm_api_key)


__all__ = ["Settings"]
