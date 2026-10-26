# WPS 工具箱 — 本地 Office/PDF/扫描处理工具

一个本地优先的桌面工具箱（PySide6）：Office/PDF/图片/文档扫描尽量在本机完成，减少上传第三方网站；
仅「PPT 美化」按需调用大模型，且**只发文本**、文档二进制不出本机。

支持 `pdf / docx / pptx / 图片` 的常见处理，拖拽即用，后台执行不卡界面。

---

## 功能

- **PDF**：合并、拆分、旋转、抽取指定页、转图片、提取文本、提取图片、转 Word（.docx）、加密、解密、加文字水印、去水印、加页码
- **Word（DOCX）**：提取文本、提取图片、批量替换（保留 run 样式）
- **PPT（PPTX）**：提取文本、提取图片（含纯 SVG、组合图）、结构分析、批量替换 token
- **图片**：多图合成 PDF、压缩、缩放、格式转换、旋转、提取文本（内置 OCR）
- **文档扫描**：手机拍的照片 → 自动找纸边、透视矫正、滤镜增强、多页排序、手写签名、导出 PDF/JPG
- **Office 转 PDF**：LibreOffice 命令行封装（DOCX/PPTX → PDF，需本机装 LibreOffice）
- **OCR**：图片文字识别（内置 `rapidocr-onnxruntime`，中英文，无需另装引擎）
- **批量处理**：一键对列表里所有文件执行同一操作
- **PPT 美化**：本地解析每页 shape 清单（文本 + 图片占位）→ 把清单（**不含图片字节**）发给 LLM
  拿「shape 级重设计 spec」→ 本地用 python-pptx 按 spec 逐 shape 重建一套干净 deck，图片本地抽图插入
- **桌面 UI**：拖拽导入、文件列表、中文功能下拉（按文档类型分区）、参数区、进度区、结果区，后台执行不卡死

> 注：**PDF 转 Word** 基于 PDF 的文本层，保留文字（尽量带字号/粗斜体）与图片；复杂版式、
> 表格、多栏可能不完美。纯扫描件（无文本层）请先用 OCR 再转。

> 注：**PDF 去水印** 尽量处理两类水印——水印/图章类注释，以及内容流里跨多页重复的大号文字
> （可用「水印」输入框指定要去掉的文字；留空则自动识别）。以图片/矢量图形形式画进页面的
> 水印无法可靠去除，会保留。合并/拆分等操作不会破坏原文件。

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

> OCR（图片提取文本）已内置 `rapidocr-onnxruntime`（纯 pip、可打进 exe），无需另装引擎。

> **WSLg 用户注意**：WSLg 的 Wayland 有「下拉菜单弹出后收不回去」的已知缺陷（非本程序 bug）。
> 装上 X11 依赖后程序会自动改用 X11：`sudo apt-get install -y libxcb-cursor0`。也可手动指定
> `QT_QPA_PLATFORM=xcb ./wps/bin/python -m wps_tool`。

---

## 打包成可执行文件（发给不懂技术的人）

PyInstaller 打出**单文件**可执行程序，双击即用，无需装 Python。

```bash
./wps/bin/python -m pip install -e ".[dev]"        # 首次：装 pyinstaller
./wps/bin/python -m PyInstaller packaging/wps_tool.spec --noconfirm
# 产物：dist/wps-tool（Windows 为 dist\wps-tool.exe）
```

- **Windows 用户**：把仓库拷到 Windows，**双击 `packaging\build.bat`** 即可（自动建独立
  venv、装依赖、出 `dist\wps-tool.exe`）。前提：装了 Python ≥ 3.11。
- **不能跨平台打包**：Windows 的 `.exe` 必须在 Windows 上构建，Linux / macOS 同理。
- 想把 `.env`（美化用的 LLM 配置）也给别人：复制到可执行文件**同目录**，程序会优先读它。
  ⚠️ 别把含**真实 API Key** 的 `.env` 随 exe 分发（等于把 key 给了所有人，会消耗你的额度）。
  **不带 `.env` 时美化默认关闭**，其余本地功能照常可用。
- 程序运行日志写在 exe 同目录 `wps-tool.log`（不可写时退回 `~/.wps-tool/`），出问题可发来排查。
- 不想手动多平台构建？仓库带 `.github/workflows/build.yml`，在 GitHub 上手动触发
  （或打 `v*` tag）即可自动构建 Windows / macOS / Linux 三份产物并作为 artifact 下载。

---

## 界面使用

1. 启动后，把文件拖进窗口（或点「打开文件…」）。
2. **勾选**要处理的文件：表格第一列是勾选框，可勾选**任意不连续的多行**；工具栏「全选/全不选」
   可一键全选。批量操作（处理 / 合并 / 美化 / 删除）都按勾选来。
3. 在顶部「功能」下拉里选操作（中文分组：通用 / PDF / PPT / Word / 图片）。
4. 按需填参数区（**参数会随所选功能自动只显示相关项**，并给出一行说明）：
   - **输出目录**：留空 = 源文件旁 `processed/`（始终显示）。
   - **替换映射**：替换文本/占位符用，`旧文本=新文本`，多个用 `;` 分隔。
   - **角度**：旋转 PDF / 旋转图片。
   - **质量**：压缩图片（JPEG）。
   - **倍率**：PDF 转图片。
   - **页码**：抽取页面（0-based）。
   - **密码**：PDF 加密/解密。
   - **水印**：PDF 加水印/去水印，默认 `CONFIDENTIAL`。
   - **宽×高**：缩放图片，高度填 0 = 按宽度等比。
   - **格式**：图片转换的目标格式。
5. 点「**处理勾选**」只跑勾选的文件；点「**处理全部**」对列表里所有文件执行同一操作。
6. 勾选多个 PDF 可点「**合并勾选 PDF**」（支持不连续多行）；勾选一个 `.pptx` 可点
   「**美化勾选 PPT**」；「**删除勾选**」删除勾选的行（不想全清空时用）。
7. 结果与输出路径显示在「结果」区，进度/成败在进度条与状态栏。

批量处理时，每个文件单独生成任务，互不影响；某个文件失败只标红该行，不影响其余任务。

---

## 文档扫描（生成扫描件 PDF）

工具栏「文档扫描…」或功能下拉里选「文档扫描（生成 PDF）」，即可把手机拍的照片变成类似扫描全能王的扫描件。
全流程本地处理，不联网、不上传。

1. **添加图片**：拖入或点「添加图片…」，支持 jpg/png/bmp/webp/tif。
2. **裁边**：自动识别纸张四角；不满意就拖四个圆点微调，或点「重置四角」。
3. **滤镜**：原图 / 增强（去阴影 + 提对比）/ 灰度 / 黑白，实时预览。
   > 「原图」只是不做滤镜，仍会做透视矫正；预览按裁切后的比例显示，不套纸张白边。
4. **整理**：左侧页面列表可删除、上移/下移、左转/右转。
5. **签名**：手写签名（可调笔宽/颜色/位置/大小/透明度），可只签当前页或应用到所有页。
6. **导出**：
   - 格式：PDF / JPG；
   - 纸张：A4 竖向 / A4 横向 / 自动（按图片比例，保留原始像素）；
   - DPI：150 / 200 / 300（导出像素密度；150 适合屏幕，300 适合打印，越高文件越大，但不会凭空增加原本没有的细节）；
   - 质量：60–95%（JPEG 压缩质量，越高越清晰、文件越大，85–90 通常够用）。
   - **PDF 加密/水印不在这里做**：导出后回主界面用「加密 PDF / 加文字水印」即可，避免功能重复。

> 扫描窗口只负责裁边/滤镜/签名/导出。需要文字识别时，用主界面「提取文本（通用）」对**原始照片**
> 识别即可；需要加密/水印则对导出的 PDF 用主界面 PDF 功能处理。

> 如果觉得导出后变糊：多半是选了 A4 把较小的原图放大/留白了。想保留原始像素，把纸张改成「自动」，
> 或把 DPI 降到 150/200；也可以先试「增强」滤镜再导出。

> 局限：自动裁边不是 100% 准，背景杂乱/低对比时会失败，手动拖角即可；手写签名是图片叠加，
> 不是合规 CA 电子签名；OCR 目前提供文字提取，不生成“可搜索 PDF”文字层。

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
| 文档扫描 / 透视矫正 | OpenCV（crop、去阴影、二值化） |
| OCR | rapidocr-onnxruntime（纯 pip，内置） |
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
    ├── processors/         # 各格式处理算法（pdf/docx/ppt/image/scan）
    ├── services/           # 外部能力（LibreOffice / OCR / 美化 API / 渲染器）
    ├── models/             # 配置 + FileJob
    ├── ui/                 # 主窗口、扫描窗口、组件、主题样式
    └── utils/              # 路径、日志
tests/                      # pytest 测试
```

设计原则：`ui/` 只管界面；`processors/` 管文件操作；`services/` 管外部能力；
`core/` 管调度与异常；`models/` 放配置与数据结构；`utils/` 放路径与日志。
