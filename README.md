# WPS Tool — 本地 Office/PDF 处理工具（教学骨架）

一个本地优先的 Office/PDF 桌面处理工具：尽量在本地处理敏感文件，减少上传第三方网站。支持 `pdf / docx / pptx / 图片` 的常见处理能力，并提供 PySide6 桌面 UI。

> **教学骨架**：框架（UI、配置、异常、日志、服务胶水）已写好，**核心逻辑留 TODO** 让学生实现，配套**测试即验收标准**——`pytest` 红 → 实现 → 绿。通过实现 TODO 练 Python 工程能力：GUI、文件处理、任务队列、处理器注册、异常处理、配置管理、测试。

---

## 功能

- **PDF**：合并、拆分、页面旋转、抽取指定页、转图片、提取文本
- **DOCX**：提取文本、批量替换（保留 run 样式）
- **PPTX**：提取文本、提取图片、结构分析（标题页/正文页）、批量替换 token
- **图片**：多图合成 PDF、压缩
- **Office 转 PDF**：LibreOffice 命令行封装（DOCX/PPTX → PDF）
- **OCR**：扫描版 PDF / 图片文字识别（pytesseract，可选）
- **PPT 美化 API 客户端**：httpx，支持「仅上传大纲」「上传完整文件」两种隐私模式
- **桌面 UI**：拖拽导入、文件列表、参数区、进度区、后台执行不卡死

覆盖范围 M1–M3（本地处理 + 转换 + 美化 API 客户端）。不含 M4 的插件化 / SQLite 任务历史 / CI。

---

## 快速开始

环境：Python ≥ 3.11。仓库自带 `./wps` 虚拟环境（Python 3.14，依赖已装）。

```bash
# 首次：注册包（src 布局）+ 装 dev 依赖（pytest / ruff）
./wps/bin/python -m pip install -e ".[dev]"

# 看测试 spec 看板（首日基线见下「测试即 spec」）
./wps/bin/python -m pytest -q

# 启动桌面 UI
./wps/bin/python -m wps_tool

# lint
./wps/bin/python -m ruff check src tests
```

外部可选依赖（按需）：
- **LibreOffice / soffice**：Office 转 PDF。未装则转换相关测试 skip。
- **tesseract** + `pip install pytesseract`：OCR。未装则 OCR 测试 skip。

---

## 教学设计：三层 TODO

核心逻辑分三层留 TODO，推荐实现顺序 **a → b → c**。

| 层 | 位置 | 你要实现的 | 已写好的依赖 |
|---|---|---|---|
| **(a) 算法** | `processors/{pdf,docx,ppt,image}_processor.py`<br>`services/{ppt_beautify_api,ocr_service}.py` | 文件处理函数体 | 各 `*Processor` 类（分派胶水） |
| **(b) 调度** | `core/registry.py` | `ProcessorRegistry.get_processor` | `FileProcessor` ABC + 默认 `can_handle` |
| **(c) 执行器** | `core/task.py` | `TaskRunner.{submit,_worker,cancel,shutdown}` | `TaskSignals` / `Runner` / `SyncTaskRunner`（`core/runner_iface.py`） |

**三层同时是 TODO 却不会卡死**——写好的接口层 + 可注入假实现把依赖隔断：

- (a) 是模块级纯函数，不依赖 (b)(c)，自带可测；
- (b) 用 `tests/_fakes.py::FakeProcessor` 注入即可独立测，不需任何真实处理器；
- (c) 用 `tests/_fakes.py::fake_job` 即可独立测，不需 Registry；
- UI 在 (c) 未实现时用 `SyncTaskRunner` 兜底也能端到端跑通。

「a → b → c」是**学习节奏**，不是硬前置——任一时刻你只面对一层红测试。`core/runner_iface.py::SyncTaskRunner` 就是 `TaskRunner` 的同步参考答案，实现 (c) 时可直接对照。

每个 TODO 桩统一 `raise NotImplementedError`（**不返回默认值**，避免 `isinstance(result, str)` 之类弱断言假绿），并配中文 docstring：`[学习]` 目标 + 契约 + `提示:` 关键 API。

---

## 测试即 spec

`tests/` 每个文件是对应 TODO 的验收 spec。夹具在 `tests/conftest.py` 用代码现场造「内容已知」的小样例（fitz / python-docx / python-pptx / PIL / pypdf），**不 ship 二进制**——文件里有什么就是夹具代码本身，不实现任何 TODO 夹具也能正常生成。

| 测试 | 首日 | 说明 |
|---|---|---|
| `test_pdf/docx/ppt/image_processor.py`<br>`test_registry.py`<br>`test_task_runner.py`（除 smoke）<br>`test_ppt_beautify_api.py` | 红 | `NotImplementedError`，实现到对应测试转绿 |
| `test_task_runner.py::test_sync_task_runner_smoke` | 绿 | 证明接口 / 夹具本身无误的基线 |
| `test_office_convert.py` | skip | 未装 LibreOffice/soffice 时跳过，不假红 |
| `test_ocr.py` | skip | 未装 tesseract / pytesseract 时跳过 |
| `test_integration.py` | xfail | 三层未齐时自动 xfail，三层齐了自动转绿（XPASS） |

首日全量 `pytest` 全红是**预期且信息性的**——它就是 spec 看板。真正要避免的「假红」只有环境缺二进制，故 LibreOffice/tesseract 一律 skip。

---

## 项目结构

```text
wps/
├── README.md
├── pyproject.toml                  # src 布局 + 依赖；[dev] 含 pytest/ruff
├── .env.example                     # 配置模板
├── wps/                             # Python 虚拟环境（非源码）
└── src/wps_tool/
    ├── __init__.py
    ├── app.py                       # [完整] QApplication 启动 + 装配 Registry/Runner/MainWindow
    ├── core/
    │   ├── errors.py                # [完整] 统一异常体系
    │   ├── runner_iface.py          # [完整] TaskSignals / Runner Protocol / SyncTaskRunner（接口层）
    │   ├── registry.py              # [TODO·b] ProcessorRegistry.get_processor
    │   └── task.py                  # [TODO·c] TaskRunner
    ├── processors/
    │   ├── __init__.py              # [完整] register_default_processors()
    │   ├── base.py                  # [完整] FileProcessor ABC + 默认 can_handle
    │   ├── pdf_processor.py         # [TODO·a] merge/split/rotate/extract_pages/to_images/extract_text
    │   ├── docx_processor.py        # [TODO·a] extract_text/replace_text
    │   ├── ppt_processor.py         # [TODO·a] extract_text/extract_images/analyze_structure/replace_tokens
    │   └── image_processor.py       # [TODO·a] images_to_pdf/compress_image
    ├── services/
    │   ├── office_convert.py        # [完整] LibreOffice 子进程封装 + 可用性检测
    │   ├── ppt_beautify_api.py      # [TODO·a] PptBeautifyClient.beautify_file/beautify_by_outline
    │   └── ocr_service.py           # [TODO·a] ocr_image（pytesseract）
    ├── models/
    │   ├── file_job.py              # [完整] FileJob dataclass + JobStatus 枚举
    │   └── settings.py              # [完整] pydantic-settings 配置
    ├── ui/
    │   ├── main_window.py           # [完整] 主窗口骨架
    │   ├── widgets.py               # [完整] DropArea / FileTable / build_job_func
    │   └── theme.py                 # [完整] QSS
    └── utils/
        ├── paths.py                 # [完整] 输出目录（源旁 processed/）
        └── logging.py               # [完整] loguru + 隐私脱敏 filter
tests/
├── conftest.py                      # [完整] qapp + 现场生成样例夹具
├── _fakes.py                        # [完整] FakeProcessor / fake_job（测试替身）
└── test_*.py                        # [测试] 各 TODO 的 spec（见上表）
```

设计原则：`ui/` 只负责界面，不直接处理文件；`processors/` 负责具体文件操作；`services/` 负责外部能力（LibreOffice / OCR / 美化 API）；`core/` 负任务调度、处理器注册、统一异常；`models/` 放配置与任务数据结构；`utils/` 放路径与日志。

---

## TODO 清单与学习目标

按推荐顺序，每实现一组对应测试转绿。

### Layer (a) 文件处理算法

| 文件 | TODO 函数 | 学什么 |
|---|---|---|
| `pdf_processor.py` | `extract_pdf_text` | PyMuPDF 读文本（最简，建议先做） |
| | `merge_pdfs` `split_pdf` | pypdf 读写、页操作 |
| | `rotate_pdf` `extract_pdf_pages` | pypdf 页旋转 / 抽取 |
| | `pdf_to_images` | PyMuPDF 渲染为图片 |
| `docx_processor.py` | `extract_docx_text` | python-docx 读段落 |
| | `replace_docx_text` | 遍历 run 替换（保样式，抓 `paragraph.text=` 丢 run 的坑） |
| `ppt_processor.py` | `extract_pptx_text` | python-pptx 遍历 shapes/text_frame |
| | `extract_pptx_images` | `MSO_SHAPE_TYPE.PICTURE` + `shape.image.blob` |
| | `analyze_pptx_structure` | 用 `slide_layout.name` 判页型 |
| | `replace_pptx_tokens` | 遍历 run 替换 |
| `image_processor.py` | `images_to_pdf` `compress_image` | Pillow 多图合 PDF / 压缩 |
| `ppt_beautify_api.py` | `beautify_file` `beautify_by_outline` | httpx multipart / JSON、鉴权、隐私模式 |
| `ocr_service.py` | `ocr_image` | pytesseract 调用 |

### Layer (b) 处理器注册调度

| 文件 | TODO | 学什么 |
|---|---|---|
| `core/registry.py` | `ProcessorRegistry.get_processor` | 注册表 + 策略模式：遍历、`can_handle` 命中分派 |

### Layer (c) 任务执行器

| 文件 | TODO | 学什么 |
|---|---|---|
| `core/task.py` | `TaskRunner.submit` | `ThreadPoolExecutor` 提交、立即返回 job_id |
| | `TaskRunner._worker` | worker 线程执行 + Qt 信号回调（finished/failed） |
| | `TaskRunner.cancel` `shutdown` | 取消排队任务、关闭线程池 |

> `*Processor.run`（分派胶水）和 `core/runner_iface.py` 全套已写好，**不要改**——它们是你 TODO 的调用方与接口契约。

---

## 库 API 速查

详细签名与提示见各 TODO 的 docstring。以下是按已装版本核对的坑点。

### pypdf（PDF 读写）

```python
from pypdf import PdfReader, PdfWriter

# 合并：append 保书签；也可 add_page 循环
writer = PdfWriter()
for p in input_paths:
    writer.append(PdfReader(p))
with open(output_path, "wb") as f:
    writer.write(f)

# 旋转：page.rotate(angle) 原地修改，须加到新 writer
reader = PdfReader(input_path)
writer = PdfWriter()
for page in reader.pages:
    page.rotate(90)
    writer.add_page(page)

# 加密：方法名是 encrypt，没有 add_encryption（PyPDF2 旧名）
writer.encrypt(user_password="pw", use_128bit=True)

# 解密读：is_encrypted 为 True 时须先 decrypt
reader = PdfReader(path)
if reader.is_encrypted:
    reader.decrypt("pw")
```

### PyMuPDF / fitz（渲染、文本）

```python
import fitz

doc = fitz.open(input_path)
for i, page in enumerate(doc, start=1):
    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))  # zoom
    pix.save(f"{output_dir}/page_{i}.png")               # 按扩展名定格式
    text = page.get_text()                                # 返回 str
```

### python-docx（DOCX）

```python
from docx import Document

doc = Document(path)
text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())

# 替换：必须遍历 run，不能 paragraph.text = ...（会丢 run 样式）
for para in doc.paragraphs:
    for run in para.runs:
        for old, new in mapping.items():
            run.text = run.text.replace(old, new)
```

### python-pptx（PPTX）

```python
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

prs = Presentation(path)
for slide in prs.slides:
    for shape in slide.shapes:
        if shape.has_text_frame:          # 避免对 Group/GraphicFrame 误访问 .text
            ... = shape.text_frame.text
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            blob = shape.image.blob        # bytes
            ext = shape.image.ext          # "png" / "jpeg"
    layout_name = slide.slide_layout.name # "Title Slide" / "Title and Content" ...
```

### httpx（PPT 美化 API）

```python
import httpx

# 客户端必须持有「可注入 transport 的 Client」才能离线测
client = httpx.Client(base_url=url, transport=transport, timeout=120)
r = client.post("/ppt/beautify", files={"file": (name, f, ctype)},
                data={"style": "business"}, headers={"Authorization": f"Bearer {key}"})
r.raise_for_status()

# 离线测试用 MockTransport，handler 可断言请求体隐私
transport = httpx.MockTransport(lambda req: httpx.Response(200, json={...}))
```

`PPTX_MAGIC = b"PK\x03\x04"`（pptx 的 zip 头）：仅大纲模式请求体不应含它，完整文件模式应含它——隐私要求据此变成可执行断言。

### Pillow（图片）

```python
from PIL import Image

# 多图合 PDF：所有图须 convert("RGB")，否则 RGBA/P 转 PDF 抛错
imgs = [Image.open(p).convert("RGB") for p in image_paths]
imgs[0].save(output_path, save_all=True, append_images=imgs[1:])

# 压缩
Image.open(input_path).convert("RGB").save(output_path, optimize=True, quality=85)
```

---

## 设计原则

- **本地优先**：默认所有功能本地处理；外部 API 功能默认关闭（`ENABLE_API_UPLOAD=false`）。
- **隐私从第一天起**：日志脱敏 filter（手机号/邮箱替换为占位号）；本地任务历史只记文件名/时间/操作/结果，不记正文；API 请求失败不把文件内容写进错误日志。
- **处理器注册机制**：每类文件处理器实现统一接口（`can_handle` + `run`），新增类型不污染主界面。
- **后台任务不卡死**：UI 只经 `TaskSignals` 回调更新界面，worker 线程绝不直接碰 QWidget；`TaskSignals` 在主线程构造，worker emit 的信号被 Qt 自动判为 Queued 连接。
- **配置管理**：`pydantic-settings` 从 `.env` / 环境变量读，API Key、路径、隐私开关集中管理。

## 技术栈

| 用途 | 库 |
|---|---|
| 桌面 UI | PySide6 |
| PDF 读写 | pypdf |
| PDF 渲染/文本 | PyMuPDF (fitz) |
| DOCX | python-docx |
| PPTX | python-pptx |
| Office 转 PDF | LibreOffice 命令行 |
| 图片 | Pillow |
| OCR | pytesseract（可选） |
| HTTP | httpx |
| 配置 | pydantic-settings |
| 日志 | loguru |
| 测试 / lint | pytest / ruff |
| 打包 | PyInstaller（M4，未覆盖） |

## 后续（M4，未覆盖）

插件化文件处理器、SQLite 任务历史、批处理模板、文件脱敏规则、PyInstaller 打包、CI——这些不在当前教学骨架范围内，可作为进阶练习。
