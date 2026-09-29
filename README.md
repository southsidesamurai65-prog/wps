# WPS 工具箱 — 本地 Office/PDF 处理工具

一个本地优先的桌面工具箱（PySide6）：Office/PDF/图片处理尽量在本机完成，减少上传第三方网站；
仅「PPT 美化」按需调用大模型，且**只发文本**、文档二进制不出本机。

支持 `pdf / docx / pptx / 图片` 的常见处理，拖拽即用，后台执行不卡界面。

---

## 功能

- **PDF**：合并、拆分、旋转、抽取指定页、转图片、提取文本、加密、解密、加文字水印、加页码
- **Word（DOCX）**：提取文本、批量替换（保留 run 样式）
- **PPT（PPTX）**：提取文本、提取图片、结构分析、批量替换 token
- **图片**：多图合成 PDF、压缩、缩放、格式转换、旋转
- **Office 转 PDF**：LibreOffice 命令行封装（DOCX/PPTX → PDF，需本机装 LibreOffice）
- **OCR**：扫描版 PDF / 图片文字识别（pytesseract，可选）
- **批量处理**：一键对列表里所有文件执行同一操作
- **PPT 美化**：本地解析每页 shape 清单（文本 + 图片占位）→ 把清单（**不含图片字节**）发给 LLM
  拿「shape 级重设计 spec」→ 本地用 python-pptx 按 spec 逐 shape 重建一套干净 deck，图片本地抽图插入
- **桌面 UI**：拖拽导入、文件列表、中文功能下拉、参数区、进度区、结果区，后台执行不卡死

---

## 快速开始

环境：Python ≥ 3.11。仓库自带 `./wps` 虚拟环境（依赖已装）。

```bash
# 首次：注册包（src 布局）+ 装开发依赖（pytest / ruff）
./wps/bin/python -m pip install -e ".[dev]"

# 启动桌面 UI
./wps/bin/python -m wps_tool

# 跑测试 / lint（开发用）
./wps/bin/python -m pytest -q
./wps/bin/python -m ruff check src tests
```

外部可选依赖（按需，不装则相关功能/测试自动跳过）：

- **LibreOffice / soffice**：Office 转 PDF。
- **tesseract** + `pip install pytesseract`：OCR。

---

## 界面使用

1. 启动后，把文件拖进窗口（或点「打开文件…」）。
2. 在顶部「功能」下拉里选操作（中文分组：PDF / PPT / Word / 图片）。
3. 按需填参数区：
   - **输出目录**：留空 = 源文件旁 `processed/`。
   - **替换映射**：`旧文本=新文本`，多个用 `;` 分隔（替换类操作用）。
   - **角度 / 质量 / 倍率 / 页码**：旋转、压缩、渲染、抽页用。
   - **密码**：PDF 加密/解密用。
   - **水印**：水印文字，默认 `CONFIDENTIAL`。
   - **宽×高**：图片缩放，高度填 0 = 按宽度等比。
   - **格式**：图片转换的目标格式。
4. 点「**处理选中行**」只跑选中的文件；点「**处理全部**」对列表里所有文件执行同一操作。
5. 多个 PDF 可点「**合并选中 PDF**」；选中一个 `.pptx` 可点「**美化选中 PPT**」。
6. 结果与输出路径显示在「结果」区，进度/成败在进度条与状态栏。

批量处理时，每个文件单独生成任务，互不影响；某个文件失败只标红该行，不影响其余任务。

---

## PPT 美化（LLM + 本地渲染）

美化一个 `.pptx`：**本地解析**每页 shape 清单（文本 + 图片占位）→ 把清单发给 LLM
（OpenAI 兼容 Chat Completions，`response_format=json_object`）拿回「shape 级重设计 spec」→
**本地渲染**重建一套干净 deck，图片从原 pptx 本地抽图、按 `image_id` 插入新位置。

> 隐私：pptx 二进制本体**不出本机**，图片字节也**只留本机内存**。发出本机的只有每页文本 +
> 图片占位（`image_id`/位置/尺寸）。若每页文本本身含敏感信息，仍会发给 LLM，请自行评估后再启用。

### 配置（`.env`）

默认关闭。启用示例（默认走 opencode-go 的 DeepSeek V4.1 Flash，推理强度 high）：

```ini
ENABLE_API_UPLOAD=true
LLM_PROVIDER=opencode-go
LLM_API_KEY=你的密钥
LLM_MODEL=deepseek-v4.1-flash
LLM_BASE_URL=https://opencode.ai/zen/go
LLM_REASONING_EFFORT=high
```

- `ENABLE_API_UPLOAD` 是「允许把内容发出本机」总开关。`false`（默认）→ 不构造美化客户端，
  点「美化」只提示未配置，**不发任何网络请求**。
- 支持 `LLM_PROVIDER=openai` / `opencode-go`（均为 OpenAI 兼容端点）；其它 provider 会在
  构造客户端时报错。也可把 `LLM_BASE_URL` 指向自建/中转的 OpenAI 兼容 endpoint。
- `LLM_REASONING_EFFORT`（low/high/max，可留空）作为 `reasoning_effort` 发进请求体。
- opencode-go 要求请求带 `x-opencode-session`（客户端自动生成稳定 session id）与**非通用**
  `User-Agent`（`wps-tool/0.1`），否则返回 `400 MissingSessionID`——已内置。

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

约束：spec 页数 == 源页数（1:1）；每个 shape 有 `type` + `left/top/width/height`（英寸）；
`type` 取 `rect`/`rounded_rect`/`oval`/`textbox`/`image`；`image` 用 `image_id` 引用解析阶段
给的占位 id；页数对不齐时按源 shape 清单兜底补/截（图片也跟着搬）。

### 程序化使用（不走 UI）

```python
from wps_tool.services.ppt_beautify_api import PptBeautifyClient

client = PptBeautifyClient(
    "key", model="deepseek-v4.1-flash", provider="opencode-go",
    base_url="https://opencode.ai/zen/go", reasoning_effort="high",
)
client.beautify_file("in.pptx", "out.pptx", style="business")
client.close()
```

渲染器 `render_beautified_deck` 是纯函数（无网络）；测试用 `httpx.MockTransport` 离线注入，
不联网也能跑。

---

## 配置项（`.env`）

| 变量 | 默认 | 说明 |
|---|---|---|
| `ENABLE_API_UPLOAD` | `false` | 是否允许把内容发出本机（PPT 美化用）。 |
| `LLM_PROVIDER` | `openai` | `openai` / `opencode-go`。 |
| `LLM_API_KEY` | 空 | LLM 密钥。 |
| `LLM_MODEL` | `gpt-4o` | 模型名。 |
| `LLM_BASE_URL` | `https://api.openai.com` | OpenAI 兼容接入点。 |
| `LLM_REASONING_EFFORT` | 空 | 推理强度 low/high/max。 |
| `DEFAULT_OUTPUT_DIR` | 空 | 默认输出目录；空 = 源文件旁 `processed/`。 |
| `TASK_MAX_WORKERS` | `2` | 后台并发数。 |

`.env` 已被 `.gitignore` 忽略；模板见 `.env.example`。

---

## 隐私说明

- 默认所有功能本地处理；只有开启 `ENABLE_API_UPLOAD` 才会调用 LLM。
- PPT 美化只发每页文本 + 图片占位（`image_id`/位置/尺寸），pptx 与图片字节都不出本机。
- 日志脱敏（手机号/邮箱等替换为占位符）；API Key 只存本地 `.env`。

---

## 技术栈

| 用途 | 库 |
|---|---|
| 桌面 UI | PySide6 |
| PDF 读写 | pypdf |
| PDF 渲染/文本/水印/页码 | PyMuPDF (fitz) |
| DOCX | python-docx |
| PPTX | python-pptx |
| Office 转 PDF | LibreOffice 命令行 |
| 图片 | Pillow |
| OCR | pytesseract（可选） |
| HTTP | httpx |
| 配置 | pydantic-settings |
| 日志 | loguru |
| 测试 / lint | pytest / ruff |

---

## 项目结构

```text
wps/
├── pyproject.toml
├── .env.example
└── src/wps_tool/
    ├── app.py              # 启动 + 装配配置/注册表/执行器/主窗口
    ├── core/               # 注册表、任务执行器、异常、接口
    ├── processors/         # 各格式处理算法（pdf/docx/ppt/image）
    ├── services/           # 外部能力（LibreOffice / OCR / 美化 API / 渲染器）
    ├── models/             # 配置 + FileJob
    ├── ui/                 # 主窗口、组件、主题样式
    └── utils/              # 路径、日志
tests/                      # pytest 测试
```

设计原则：`ui/` 只管界面；`processors/` 管文件操作；`services/` 管外部能力；
`core/` 管调度与异常；`models/` 放配置与数据结构；`utils/` 放路径与日志。
