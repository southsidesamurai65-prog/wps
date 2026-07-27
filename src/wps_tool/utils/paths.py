"""路径工具（已写好，学生不要改）。

默认输出到源文件旁的 processed/ 目录；可被 settings.default_output_dir 覆盖。
"""

from __future__ import annotations

from pathlib import Path


def default_output_dir_for(file_path: str) -> Path:
    """源文件旁的 processed/ 目录（不创建）。"""
    src = Path(file_path).resolve()
    return src.parent / "processed"


def ensure_output_dir(file_path: str, override: str | None = None) -> Path:
    """返回输出目录（已创建）。override 优先，否则用源旁 processed/。"""
    target = Path(override) if override else default_output_dir_for(file_path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def unique_output_path(dir_path: str | Path, stem: str, suffix: str) -> Path:
    """在 dir_path 下生成不冲突的输出路径：stem.suffix 或 stem (1).suffix ..."""
    directory = Path(dir_path)
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / f"{stem}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem} ({counter}){suffix}"
        counter += 1
    return candidate


__all__ = ["default_output_dir_for", "ensure_output_dir", "unique_output_path"]
