# agent-marketplace — project notes

## Python environment

Use the **project-local** venv, not the shared root one:

```bash
source /Users/ashadeepa/Documents/Projects/agent-marketplace/.venv/bin/activate
```

- This venv is Python **3.14.7**. The shared root venv at
  `/Users/ashadeepa/Documents/Projects/.venv` is Python 3.9.6 and cannot install
  `mcp` (requires Python 3.10+) without `eval_type_backport`.
- Install everything with:
  ```bash
  pip install -r requirements.txt -r requirements-mcp.txt
  ```
- `requirements-mcp.txt` is optional — only needed to run this project as an MCP
  server for Claude.

## Env vars / tracing

- Secrets live in `.env` (gitignored): `LANGCHAIN_API_KEY`.
- `app/main.py` calls `load_dotenv()` **before** importing `app.tracing` — that
  module reads `LANGCHAIN_API_KEY`/`LANGSMITH_API_KEY` at *import time*, so the
  load-before-import ordering is required, not cosmetic.
- Tracing is LangSmith-based (`app/tracing.py`, `@traceable` decorator), not
  OpenTelemetry. Check status via `GET /admin/tracing-status`.

## Running

```bash
uvicorn app.main:app --reload
```
