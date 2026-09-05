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
- `requirements-tracing.txt` (LangSmith) and `requirements-otel.txt`
  (OpenTelemetry) are also optional — see below.

## Observability — two separate tracing systems

There are two independent tracing integrations here; don't conflate them.

- **LangSmith** (`app/tracing.py`, `@traceable` decorator) — traces individual
  agent `install`/`invoke` calls as LLM/agent-specific runs. Requires
  `LANGCHAIN_API_KEY` in `.env` and `pip install -r requirements-tracing.txt`.
  `app/main.py` calls `load_dotenv()` **before** importing `app.tracing` — that
  module reads `LANGCHAIN_API_KEY`/`LANGSMITH_API_KEY` at *import time*, so the
  load-before-import ordering is required, not cosmetic. Check status via
  `GET /admin/tracing-status`.
- **OpenTelemetry** (`app/otel.py`) — instruments the FastAPI HTTP layer itself
  (every request becomes a span), exported via OTLP to whatever vendor-neutral
  backend you point it at (Jaeger, Tempo, Honeycomb, an OTel Collector, etc.).
  Requires `pip install -r requirements-otel.txt`; configure with
  `OTEL_EXPORTER_OTLP_ENDPOINT` (default `http://localhost:4318`) and
  `OTEL_SERVICE_NAME` (default `agent-marketplace`). Check status via
  `GET /admin/otel-status`. Both packages degrade gracefully to a no-op if not
  installed, so the app runs fine with neither, either, or both enabled.

## Running

```bash
uvicorn app.main:app --reload
```
