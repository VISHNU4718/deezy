# Deezy

Deezy is a small agent loop with a CLI and a web UI. Given an objective, it:

1. plans a list of tool calls,
2. asks for approval if any step changes something,
3. runs the steps, passing results from one step into the next,
4. checks each step and retries or recovers where it can,
5. stores the outcome in a SQLite task history and in memory.

It started as a personal desktop assistant. This repository is the part that can run anywhere: the loop, the web UI and a set of safe sample tools.

## Hosted demo

The Vercel deployment runs with `DEEZY_DEMO=1` (set automatically when `VERCEL` is present). What that means:

- **No LLM.** The planner uses keyword rules, so it only understands a few kinds of request (product search, product evaluation, time, to-do items, file search/read/create). Anything else falls through to a product search over the sample catalog, which usually returns "No products matched that search".
- **Sample tools.** Product search runs over a built-in catalog of 12 items. Web search returns canned results. Nothing is bought, posted or sent.
- **Sandboxed files.** File tools only see a temporary directory (`/tmp/deezy-sandbox`). Paths that try to leave it are refused. System-inspection tools (running apps, system info) are not registered.
- **Temporary data.** Tasks, conversations and memories are stored in SQLite under `/tmp`. Serverless instances are recycled and are not shared, so data can disappear at any time.
- **Shared settings.** Settings changes apply to the whole running instance, not per visitor.
- **No streaming.** Serverless functions have no WebSockets, so a request runs the whole plan and returns. Plans with a step that changes something are saved and wait for **Approve** or **Reject** in the UI.

## Run locally

Requires Python 3.10+ and Node 18+.

```bash
pip install -r requirements.txt
cd deezy/interface/web && npm ci && npm run build && cd -
python -m deezy.interface.web.api      # http://127.0.0.1:8000
```

Add `DEEZY_DEMO=1` to run with the sandbox and mock provider locally. Without it, the file tools work on your real filesystem and the planner uses the configured LLM provider (`deezy/config/settings.yaml`), falling back to the keyword rules if the provider fails. Provider API keys are read from `<PROVIDER>_API_KEY`, for example `OPENROUTER_API_KEY`. The default `local` provider expects an [Ollama](https://ollama.com) server.

For frontend development run `npm run dev` in `deezy/interface/web` (Vite proxies `/api` to port 8000).

CLI:

```bash
python -m deezy.main task "find a desk lamp under 50"
python -m deezy.main tools
python -m deezy.main status
```

## Configuration

| Variable | Purpose |
| --- | --- |
| `DEEZY_DEMO` | `1` enables the sandbox and mock provider |
| `DEEZY_DB_PATH` | SQLite file (default `data/deezy.db`, `/tmp/deezy.db` on Vercel) |
| `DEEZY_CONFIG` | alternative settings YAML |
| `DEEZY_LLM_PROVIDER` | `local`, `openrouter`, `openai`, `anthropic` or `mock` |
| `DEEZY_SANDBOX_DIR` | demo sandbox directory |
| `DEEZY_CORS_ORIGINS` | extra comma-separated CORS origins |
| `AFFILIATE_TAG` | optional tag for product links |
| `PORT` | port for `python -m deezy.interface.web.api` |

## API

| Method | Path | |
| --- | --- | --- |
| GET | `/api/health` | status and demo flag |
| GET / PUT | `/api/settings` | read / validate and save settings |
| GET | `/api/tools` | registered tools |
| GET / POST | `/api/tasks` | list / plan and run a task (`{"objective": "..."}`) |
| GET | `/api/tasks/{id}` | one task, including its plan |
| POST | `/api/tasks/{id}/approve`, `/reject` | resolve a task that is `waiting_for_approval` (409 otherwise) |
| GET | `/api/history` | finished tasks |
| GET / POST | `/api/conversations` | list / create |
| GET / PATCH / DELETE | `/api/conversations/{id}` | read, rename, delete |
| POST | `/api/conversations/{id}/messages` | append a message |
| GET / POST | `/api/conversations/{id}/export`, `/api/conversations/import`, `/{id}/branch` | export, import, branch |
| GET / POST / PATCH / DELETE | `/api/memories` | long-term memory |

Interactive docs are at `/docs`.

## Tests

```bash
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
pytest
```

The tests cover plan resolution and summaries, the approval gate, sandbox path handling and the HTTP API. CI also type-checks and builds the frontend. The web UI itself has no unit tests.

## Layout

```
api/index.py            Vercel function entry
deezy/brain/            LLM providers, tool registry, models
deezy/core/             planner and agent loop
deezy/tools/            tools (sample implementations)
deezy/memory/           SQLite wrapper and memory store
deezy/interface/        CLI and FastAPI app
deezy/interface/web/    React + TypeScript + Tailwind frontend
```

## Limits

- The tools are samples. Nothing here shops, posts or controls your computer.
- Without an LLM the planner is a set of keyword rules.
- SQLite on serverless storage is not durable.
