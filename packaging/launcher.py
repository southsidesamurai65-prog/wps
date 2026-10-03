"""PyInstaller 打包入口，等价于 ``python -m wps_tool``。"""

from wps_tool.app import main

if __name__ == "__main__":
    raise SystemExit(main())
