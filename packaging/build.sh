#!/usr/bin/env bash
# 构建当前平台的单文件可执行程序（Linux/macOS）。
# Windows 请用 packaging\build.bat。
set -euo pipefail
cd "$(dirname "$0")/.."
./wps/bin/python -m PyInstaller packaging/wps_tool.spec --noconfirm
echo "完成：dist/wps-tool"
