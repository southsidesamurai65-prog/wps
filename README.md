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
- **PPT 美化**：LLM + 本地渲染——本地解析 pptx 每页 shape 清单（文本 + 图片占位），把清单（**不含图片字节**）发给 LLM（OpenAI，httpx 裸调）拿「shape 级重设计 spec」，再用 python-pptx 按 spec 坐标逐 shape 摆、本地抽图插入，重建一套干净 deck
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

## PPT 美化（LLM + 本地渲染）使用方法

美化一个 `.pptx`：**本地解析**每页 shape 清单（文本 + 图片占位）→ 把清单（**不含图片字节**，只含文本 + 图片的 `image_id`/位置/尺寸）发给 LLM（OpenAI）拿回「shape 级重设计 spec」→ **本地渲染**重建一套干净 deck（图片从原 pptx 本地抽图、按 `image_id` 插入新位置），写到源文件旁 `processed/`。

> 隐私：pptx 的二进制本体**不出本机**，图片字节也**只留本机内存**。发出本机的只有每页文本 + 图片占位（`image_id`/位置/尺寸）。请求体不含 pptx 的 zip 头 `PK\x03\x04`（`PPTX_MAGIC`），也**不含** PNG 头 `\x89PNG`（`PNG_MAGIC`）——这是写进测试的双隐私断言。若每页文本本身含敏感信息，仍会发给 LLM，请自行评估后再启用。

### 流程

1. 本地解析：`_extract_shape_manifest` 拿每页 shape 清单（文本/图片占位）+ 图片 blob 字典（本机）+ 画布尺寸。
2. 清单 → OpenAI `POST /v1/chat/completions`，`response_format={"type":"json_object"}` 强制 JSON，`Authorization: Bearer {key}`。LLM 既改写文案也定每页 shape 的坐标/尺寸/配色，返回 shape 级 spec。
3. 本地渲染：`render_beautified_deck(spec, output, style, images=images)` 用 python-pptx 按 spec 坐标逐 shape 摆（rect / rounded_rect / oval / textbox / image），图片按 `image_id` 从本机 `images` 取 blob 插入，`prs.save(output)`。

### spec 协议（LLM 返回，shape 级）

```json
{
  "slide_size": {"width": 13.333, "height": 7.5},
  "theme": {"accent": "#1F4E79", "bg": "#FFFFFF"},
  "slides": [
    {"bg": "#FFFFFF", "shapes": [
      {"type": "rect", "left": 0, "top": 0, "width": 13.333, "height": 1.4,
       "fill": "#1F4E79", "line": null, "text": "季度汇报", "font_size": 40,
       "font_color": "#FFFFFF", "bold": true, "align": "left",
       "valign": "middle", "margin_left": 0.5},
      {"type": "image", "image_id": "img_1", "left": 7.6, "top": 2,
       "width": 5, "height": 4.5},
      {"type": "textbox", "left": 0.6, "top": 2, "width": 6.5, "height": 4.5,
       "valign": "top", "paragraphs": [
         {"text": "收入 +18%", "bullet": true, "font_size": 22, "color": "#222222"}
       ]}
    ]}
  ]
}
```

约束：spec 页数 == 源页数（1:1，`beautify_file` 在对不齐时按源 shape 清单兜底补/截，**图片也跟着搬**）；每 shape 有 `type`+`left/top/width/height`（英寸）；`type` 取 `rect`/`rounded_rect`/`oval`/`textbox`/`image`；`image` 用 `image_id` 引用解析阶段给的占位 id；`align`∈left/center/right，`valign`∈top/middle/bottom，`line` null=无线。图片由本地抽图插入，LLM 看不到图片内容、只按占位重新摆位。

### 配置（`.env`）

默认关闭。启用：

```ini
ENABLE_API_UPLOAD=true
LLM_PROVIDER=openai
LLM_API_KEY=你的密钥
LLM_MODEL=gpt-4o
LLM_BASE_URL=https://api.openai.com
```

- `ENABLE_API_UPLOAD` 是「允许把内容发出本机」总开关（LLM 把文本+图片占位发出本机，归它管）。`false`（默认）→ `app.py::build_beautify_client(settings)` 返回 `None`，不构造客户端、不注入 MainWindow；此时点「美化」只提示「未配置」，**不发任何网络请求**。
- 仅当 `enable_api_upload=true` **且** `llm_configured()`（provider + key 都非空）时才构造 `PptBeautifyClient` 并注入。
- 当前只实现 `provider=openai`，走 httpx 裸调（不装 `openai` SDK）；其它 provider 在构造时抛 `ApiUnavailableError`。
- `LLM_MODEL` 可按需配，避免写死过时模型名。
- `LLM_BASE_URL` 接入点：默认官方 OpenAI；走中转/代理/Azure/自部署的 OpenAI 兼容 endpoint 在这换，**不用改源码**。

### UI 操作步骤

1. 启动 `./wps/bin/python -m wps_tool`，拖一个 `.pptx` 进窗口（或「打开文件…」）。
2. 在文件表里**选中一行 `.pptx`**（一次只美化一个；选中多行或非 `.pptx` 会提示）。
3. 点参数区「**美化选中 PPT**」按钮。
4. 后台执行：调 `client.beautify_file(input, output, style)`——本地解析 shape 清单 + 文本/占位发 OpenAI + 本地渲染重建 deck（含原图搬运）。
5. 美化后的文件写到「输出目录」（留空则源文件旁 `processed/`）下 `<文件名>_beautified.pptx`，路径显示在「结果」区。
6. 进度/成败在状态栏与进度区显示；失败经 runner 的 `failed` 信号提示，UI 不崩。

### 隐私说明

- pptx 二进制不出本机，**图片字节也不出本机**（只留本机内存供渲染插入）。发出本机的只有每页文本 + 图片占位（`image_id`/位置/尺寸）。请确认每页文本不含不宜外传的敏感信息后再启用，或先脱敏。
- 默认关闭（`ENABLE_API_UPLOAD=false`），所有功能本地处理。
- API Key 只存本地 `.env`（`.gitignore` 已忽略 `.env`）。
- `tests/test_ppt_beautify_api.py` 把「只发文本+图片占位」写成双隐私断言：请求体**不含** `PPTX_MAGIC`（`PK\x03\x04`，pptx 二进制）也**不含** `PNG_MAGIC`（`\x89PNG`，图片字节），且含 `image_id` 占位、打到 `/v1/chat/completions`、带鉴权、含 `model` 与 `response_format`；并断言产物 deck **含 picture shape**（图被搬过来了，之前美化后图全丢）。

### 程序化使用（不走 UI）

```python
from wps_tool.services.ppt_beautify_api import PptBeautifyClient

client = PptBeautifyClient("sk-...", model="gpt-4o")
# 本地解析 shape 清单 → 文本/图片占位发 OpenAI → 本地渲染重建 deck（含原图搬运）
client.beautify_file("in.pptx", "out.pptx", style="business")
client.close()
```

测试用 `httpx.MockTransport` 离线注入 transport，handler 回一段 canned chat-completion——**不联网也能跑**。渲染器 `render_beautified_deck` 是纯函数，`tests/test_ppt_renderer.py` 直接驱动、不碰网络。

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
    │   ├── ppt_beautify_api.py      # [完整] PptBeautifyClient：本地解析 shape 清单→LLM shape spec→本地渲染（隐私：只发文本+图片占位，字节不出本机）
    │   ├── ppt_renderer.py          # [完整] render_beautified_deck（按 spec 坐标逐 shape 摆 + 本地抽图插入，纯函数无网络）
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
| `ppt_beautify_api.py` | `beautify_file` | httpx + OpenAI chat-completions、本地解析 shape 清单→LLM shape spec→本地渲染（隐私：只发文本+图片占位，字节不出本机） |
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

### httpx（PPT 美化：OpenAI Chat Completions）

```python
import httpx

# 客户端必须持有「可注入 transport 的 Client」才能离线测
client = httpx.Client(base_url="https://api.openai.com", transport=transport, timeout=120)
r = client.post(
    "/v1/chat/completions",
    json={"model": "gpt-4o", "messages": [...], "response_format": {"type": "json_object"}},
    headers={"Authorization": f"Bearer {key}"},
)
r.raise_for_status()
spec = r.json()["choices"][0]["message"]["content"]  # JSON 字符串，再 json.loads

# 离线测试用 MockTransport，handler 回 canned chat-completion
transport = httpx.MockTransport(lambda req: httpx.Response(
    200, json={"choices": [{"message": {"content": spec_json_str}}]}))
```

`PPTX_MAGIC = b"PK\x03\x04"`（pptx 的 zip 头）、`PNG_MAGIC = b"\x89PNG"`（PNG 头）：美化只发每页文本 + 图片占位（`image_id`/位置/尺寸），**请求体不应含二者**——图片 blob 留本机内存供渲染插入。据此写成双隐私断言。本地渲染产物则**应**以 `PPTX_MAGIC` 开头（合法 pptx zip）。

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
