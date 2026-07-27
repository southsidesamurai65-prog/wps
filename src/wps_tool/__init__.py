"""wps_tool —— 本地 Office/PDF 处理工具（教学骨架）。

设计要点：
- 框架（UI / 配置 / 异常 / 日志 / 服务胶水）已写好；
- 核心逻辑留 TODO，分三层，按 a -> b -> c 顺序实现：
    Layer (a) 文件处理算法函数体   见 processors/*.py、services/*.py
    Layer (b) 处理器注册调度        见 core/registry.py::ProcessorRegistry.get_processor
    Layer (c) 任务执行器            见 core/task.py::TaskRunner
- 测试即验收标准：tests/ 下每个 test_*.py 是对应 TODO 的 spec，
  实现 TODO 到测试转绿即完成。夹具在 tests/conftest.py 用代码现场生成。

注意：本包 import 时不触发 PySide6 导入，方便无 GUI 环境跑测试。
"""

__version__ = "0.1.0"
