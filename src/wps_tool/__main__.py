"""支持 ``python -m wps_tool`` 启动桌面 UI。

等价于 ``wps-tool`` 控制台脚本（见 pyproject.toml 的 [project.scripts]），
二者都调 ``wps_tool.app:main``。
"""

from wps_tool.app import main

if __name__ == "__main__":
    raise SystemExit(main())
