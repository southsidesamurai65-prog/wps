# AGENTS.md

Local-first Office/PDF/图片 desktop tool (PySide6), shipped as a normal end-user app
(see `README.md`). Historically a teaching scaffold, so files still contain stale
`raise NotImplementedError("TODO(Layer …)")` lines and "学生不要改" notes even though the
functions are implemented and all tests pass. Docs/comments are in Chinese — keep it that way.

## Setup / commands

Run everything with the **bundled venv**, from the repo root. `wps/` is a Python 3.12
virtualenv, *not* the package (the package is `src/wps_tool`). System `python3` lacks all deps.

```bash
./wps/bin/python -m pip install -e ".[dev]"   # one-time: pytest+ruff are NOT preinstalled
./wps/bin/python -m pytest -q                 # full suite
./wps/bin/python -m pytest tests/test_pdf_processor.py::test_merge_pdfs -q  # single test
./wps/bin/python -m ruff check src tests      # lint (no typecheck, no CI, no pre-commit)
./wps/bin/python -m wps_tool                  # launch desktop UI
./wps/bin/python -m PyInstaller packaging/wps_tool.spec --noconfirm  # package onefile
```

- Run from repo root: `Settings` reads `.env` relative to cwd; tests import `_fakes`.
- Expected baseline: all tests green. Skips (`test_ocr`, `test_office_convert`) mean
  `rapidocr-onnxruntime` / LibreOffice are absent — not failures. `test_integration` XPASSes once all
  three layers are implemented (currently does).
- `ruff check src tests` is clean; run it after edits (no CI/pre-commit enforces it).

## Layout / wiring

- `src/wps_tool/core/` dispatch + execution (`registry.py`, `task.py`, `runner_iface.py`);
  `processors/` per-format algorithms (`scan_processor.py` = 文档扫描 CV/PDF 管线);
  `services/` external capabilities (LibreOffice, OCR, PPT beautify API); `ui/` UI only
  (`scan_dialog.py` = 扫描窗口); `models/` settings + `FileJob`; `utils/` paths/logging.
- Entrypoint: `app.py::main` assembles `Settings` + `ProcessorRegistry` + runner + `MainWindow`.
- **`app.py::build_runner` still returns `SyncTaskRunner`**, so the UI runs jobs synchronously
  even though `core/task.py::TaskRunner` is implemented. Switch it to `TaskRunner(...)` to get
  non-blocking background execution.
- Worker threads must only emit `TaskSignals` — never touch widgets directly (Qt auto-queues).
- UI action dropdown shows Chinese labels but stores internal ids as item data; read via
  `action_combo.currentData()`, not `currentText()`.
- 主窗口参数区由 `main_window.py` 的 `_ACTION_PARAMS` / `_ACTION_HINTS` 驱动，只显示当前功能
  用得到的参数。新增 action 时两个表和 `_build_options` 要一起更新，否则参数不显示/不生效。

## Gotchas

- TODO docstrings and unreachable `raise NotImplementedError` lines remain after functions are
  implemented. Tests are the source of truth, not docstrings — don't assume a stub is unfinished.
- Privacy invariant is tested: PPT beautify sends only per-page text + image placeholders; the
  request body must contain neither `PPTX_MAGIC` (`PK\x03\x04`) nor `PNG_MAGIC` (`\x89PNG`).
  Keep it that way. `ENABLE_API_UPLOAD` defaults to `false`.
- Beautify tests are offline (`httpx.MockTransport`); `render_beautified_deck` is a pure function.
- Beautify defaults to provider `opencode-go` (`deepseek-v4.1-flash`, `LLM_REASONING_EFFORT=high`,
  base `https://opencode.ai/zen/go`). That endpoint **requires** `x-opencode-session` + a
  non-generic `User-Agent` or it returns `400 MissingSessionID`; the client sets both. Live
  requests need `LLM_API_KEY` from the `opencode-go` entry in `~/.local/share/opencode/auth.json`.
- `conftest.py` builds all sample files in code — no binary fixtures are shipped.
- `.env` is gitignored and present locally; use `.env.example` as the template.
- This dev box is **WSL2/WSLg**, and the app runs on Qt's `wayland` platform. WSLg's Wayland has a
  compositor bug where combo/menu popups don't unmap ("stuck open"). `app.py::_prefer_x11_on_wsl`
  auto-switches to `xcb` once `libxcb-cursor0` is installed; don't remove it. The packaged Windows
  exe is unaffected (native Windows Qt).
- Packaging: `packaging/wps_tool.spec` + `launcher.py` (needs `pyinstaller`, in `[dev]`). PyInstaller
  can't cross-compile; `.github/workflows/build.yml` builds all three OSes. Frozen app reads `.env`
  next to the executable (`app.py::_settings_env_file`), not cwd.

## 文档扫描（scan）注意事项

- 核心算法在 `processors/scan_processor.py`，UI 在 `ui/scan_dialog.py`；`main_window` 里**延迟 import**
  扫描窗口，避免启动时就拉起 cv2/fitz/onnxruntime。
- 图片读写一律走 Pillow（`load_image`）。不要改用 `cv2.imread/imwrite`：Windows 中文路径会静默失败。
- 纸张四角在 `ScanPage.corners` 里是**归一化坐标**（TL/TR/BR/BL），预览/缩略图/全分辨率导出共用。
- 导出/OCR 在 QThread 里跑；`ScanDialog.reject()` 会拒绝在线程运行时关闭窗口。
- `add_watermark` 对非 ASCII 文本会自动找系统中文字体（Windows 用 msyh）；找不到时退回内置字体。
- 扫描窗口只负责裁边/滤镜/签名/导出 PDF/JPG；**PDF 加密/水印不要在这里重复实现**，
  导出后走主界面已有的 `encrypt` / `watermark` 动作。
- 扫描窗口不做 OCR：需要文字时用主界面「提取文本」对原始图片识别。扫描导出的 PDF 是图片型，
  主界面 `extract_text` 只读文本层，读不到扫描件文字（不要指望对扫描 PDF 直接提取）。
- 扫描测试 `tests/test_scan_processor.py` 现场生成带透视的文档照片，不依赖二进制 fixture。
- `opencv-python` 现在是直接依赖；PyInstaller spec 的 `collect_all` 已包含 `cv2`。
- Commit style: Conventional Commits with Chinese scope/message, e.g. `feat(pdf): …`, `docs(readme): …`.
