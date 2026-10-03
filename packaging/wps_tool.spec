# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：单文件可执行程序。

在仓库根目录运行：
    ./wps/bin/python -m PyInstaller packaging/wps_tool.spec --noconfirm
产物：dist/wps-tool（Windows 为 dist/wps-tool.exe），可直接发给别人双击运行。

注意：PyInstaller 不能跨平台打包——Windows 的 .exe 要在 Windows 上构建，
macOS / Linux 同理。多平台产物可用 .github/workflows/build.yml 自动构建。
"""

import os

from PyInstaller.utils.hooks import collect_all

# spec 目录 / 仓库根目录（不依赖运行时的当前目录）
_SPEC_DIR = os.path.abspath(SPECPATH)  # noqa: F821 — 由 PyInstaller 注入
_ROOT = os.path.dirname(_SPEC_DIR)

datas, binaries, hiddenimports = [], [], []
# 这些库带数据文件（模板/字体等），必须显式收集，否则打包后运行报错。
for pkg in ("pptx", "docx", "fitz", "pymupdf", "pydantic_settings", "loguru"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:  # noqa: BLE001 — 某包没有可收集内容时跳过
        print(f"[spec] collect_all({pkg}) 跳过: {exc}")

a = Analysis(
    [os.path.join(_SPEC_DIR, "launcher.py")],
    pathex=[os.path.join(_ROOT, "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "PIL.ImageQt"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="wps-tool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 桌面程序，不弹黑色控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
