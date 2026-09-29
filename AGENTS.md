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
```

- Run from repo root: `Settings` reads `.env` relative to cwd; tests import `_fakes`.
- Expected baseline: all tests green. Skips (`test_ocr`, `test_office_convert`) mean
  LibreOffice/tesseract are absent — not failures. `test_integration` XPASSes once all
  three layers are implemented (currently does).
- `ruff check src tests` is clean; run it after edits (no CI/pre-commit enforces it).

## Layout / wiring

- `src/wps_tool/core/` dispatch + execution (`registry.py`, `task.py`, `runner_iface.py`);
  `processors/` per-format algorithms; `services/` external capabilities (LibreOffice, OCR,
  PPT beautify API); `ui/` UI only; `models/` settings + `FileJob`; `utils/` paths/logging.
- Entrypoint: `app.py::main` assembles `Settings` + `ProcessorRegistry` + runner + `MainWindow`.
- **`app.py::build_runner` still returns `SyncTaskRunner`**, so the UI runs jobs synchronously
  even though `core/task.py::TaskRunner` is implemented. Switch it to `TaskRunner(...)` to get
  non-blocking background execution.
- Worker threads must only emit `TaskSignals` — never touch widgets directly (Qt auto-queues).
- UI action dropdown shows Chinese labels but stores internal ids as item data; read via
  `action_combo.currentData()`, not `currentText()`.

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
- Commit style: Conventional Commits with Chinese scope/message, e.g. `feat(pdf): …`, `docs(readme): …`.
