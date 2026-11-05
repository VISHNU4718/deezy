# Deezy

A personal assistant for research, planning and workspace tasks. The web app uses the OpenAI Responses API and a small allowlist of tools. It proposes changes, shows the exact arguments, and waits for approval before saving anything.

[Open the app](https://deezy-indol.vercel.app)

## What works

- Conversations with an OpenAI model when the server connection is enabled.
- Optional live web research with source links supplied by OpenAI's web search tool.
- Browser workspace: text files, to-do items, and preferences saved only when explicitly requested.
- Read-only tools execute immediately. File writes, task changes and memory changes need approval. File saves include read-back in the execution trace.
- Approval checks the workspace revision, rejects stale proposals, applies batches atomically, and treats repeated action IDs as already applied.
- Actual execution traces, provider timing/token usage, and clear errors. No fake shopping catalog or canned research answers in the new interface.
- Optional browser dictation (review before sending) and read-aloud.

Conversations and workspace data persist in this browser's local storage. They do not sync across devices. Export workspace data in Settings before clearing browser data. Files are virtual text files; the assistant has no host filesystem or shell access. To-do items are not scheduled notifications. There is no wake word, autonomous desktop control, email sending or purchasing.

Without a configured model, the app clearly says **Tools only**. Try `Add task Prepare a project walkthrough`, `Remember keep explanations concise`, `Create file notes.md: Project notes`, `Read file notes.md`, or `List files`. These commands execute real workspace operations after approval; they do not simulate intelligence.

## OpenAI setup

Add these environment variables privately to the hosting project's server settings, then redeploy:

| Variable | Value |
| --- | --- |
| `OPENAI_API_KEY` | Your OpenAI API key, server only |
| `DEEZY_AI_ENABLED` | `1` |
| `DEEZY_MODEL` | `gpt-4.1-mini` (default) |
| `DEEZY_WEB_SEARCH` | `1` to enable live research, otherwise `0` |

Never use a `VITE_` prefix for credentials or commit a key. Recheck the connection in Settings after deployment. The status endpoint reports readiness, never the key. A configured connection is not proof that the account has credit or that a particular request will succeed.

The public demo uses the owner's API account. Configure provider project spending controls and hosting access protection appropriate to your budget before enabling it. Requests are bounded to three model rounds, six function calls, 1,600 output tokens per round and a 48-second loop budget. Instance-local throttling allows 12 requests/minute/client; it is best effort and is not a global billing limit. Web search has separate provider costs. The host function allows 60 seconds.

Messages, recent conversation and saved preferences are sent to OpenAI when connected. File contents enter the model context when read. Requests set `store: false`; this does not guarantee zero provider retention. Browser speech services have their own data handling.

Implementation follows the [Responses function calling guide](https://developers.openai.com/api/docs/guides/function-calling) and [web search guide](https://developers.openai.com/api/docs/guides/tools-web-search).

## Run locally

Python 3.10+ and Node 18+:

```sh
pip install -r requirements-dev.txt
cd deezy/interface/web
npm ci
npm run build
cd ../../..
python -m deezy.interface.web.api
```

Open `http://127.0.0.1:8000`. The same server environment variables enable OpenAI locally. The new `/api/assistant/*` API is stateless: it validates the supplied workspace and returns changes to the same browser. Hosted Vercel deployments disable the old shared SQLite API endpoints. The health endpoint remains available.

## Verification and limits

```sh
pytest
ruff check .
ruff format --check .
cd deezy/interface/web && npm run build
```

`tests/test_assistant.py` checks approval/decline, atomic batches, stale/repeated approvals, file read-back, workspace isolation, tool/path restrictions, request bounds, rate limits, provider failures, Responses request shape and source annotations. Provider responses are faked in automated tests; these are regression tests, not a model accuracy benchmark. A real model smoke test requires a privately configured key and must be reported separately.

The original CLI and keyword planner are retained for compatibility; see [legacy documentation](LEGACY.md). They are not the model path used by the new web interface.
