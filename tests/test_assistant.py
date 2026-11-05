import json

import pytest
import requests

from deezy.interface.web import assistant as module


@pytest.fixture(autouse=True)
def clean_assistant(monkeypatch):
    module._requests.clear()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEZY_AI_ENABLED", raising=False)


def ask(client, message, **kwargs):
    return client.post("/api/assistant/respond", json={"message": message, **kwargs})


def apply(client, result, workspace=None, approved=True):
    return client.post(
        "/api/assistant/approve",
        json={
            "approved": approved,
            "actions": result["actions"],
            "base_revision": result["base_revision"],
            "workspace": workspace or {},
        },
    )


def test_connection_status_is_honest_and_does_not_expose_key(client, monkeypatch):
    assert client.get("/api/assistant/status").json()["ai_ready"] is False
    monkeypatch.setenv("OPENAI_API_KEY", "secret-test-value")
    assert client.get("/api/assistant/status").json()["ai_ready"] is False
    monkeypatch.setenv("DEEZY_AI_ENABLED", "1")
    response = client.get("/api/assistant/status")
    assert response.json()["ai_ready"] is True
    assert "secret-test-value" not in response.text


def test_unknown_request_does_not_search_a_fake_product_catalog(client):
    data = ask(client, "Explain how to prepare for my interview").json()
    assert data["mode"] == "tools_only"
    assert not data["actions"] and not data["sources"]
    assert "not connected" in data["message"]
    assert "product" not in data["message"].lower()


@pytest.mark.parametrize(
    "message,tool",
    [
        ("Add task Test the workspace", "add_task"),
        ("Remember I prefer concise replies", "save_memory"),
        ("Create file notes.md: A real note", "write_file"),
    ],
)
def test_changes_are_only_proposals_until_approval(client, message, tool):
    data = ask(client, message).json()
    assert data["actions"][0]["tool"] == tool
    assert data["events"] == [] and "Nothing" in data["message"]
    declined = apply(client, data, approved=False).json()
    assert declined["workspace"]["files"] == {}
    assert declined["workspace"]["tasks"] == []
    assert declined["workspace"]["memories"] == []
    approved = apply(client, data).json()
    assert approved["events"][0]["status"] == "completed"
    assert approved["workspace"]["revision"] == 1


def test_approved_file_can_be_read_back_and_is_isolated(client):
    data = ask(client, "Create file brief.md: document evidence").json()
    state = apply(client, data).json()["workspace"]
    read = ask(client, "Read file brief.md", workspace=state).json()
    assert read["events"][0]["result"]["content"] == "document evidence"
    other = ask(client, "Read file brief.md", workspace={}).json()
    assert not other["events"] and "not in the workspace" in other["message"]


def test_no_host_paths_or_unknown_tools_can_be_approved(client):
    for action in [
        {"tool": "write_file", "arguments": {"name": "../secret", "content": "x"}},
        {"tool": "shell", "arguments": {"command": "whoami"}},
        {"tool": "write_file", "arguments": {"name": "x.txt", "content": 12}},
    ]:
        r = apply(client, {"actions": [action], "base_revision": 0})
        assert r.status_code == 422


def test_stale_approval_does_not_overwrite_newer_workspace(client):
    data = ask(client, "Create file brief.md: draft").json()
    assert apply(client, data, {"revision": 1, "files": {"brief.md": "newer"}}).status_code == 409


def test_replayed_approval_does_not_duplicate_a_task(client):
    data = ask(client, "Add task Test replay").json()
    first = apply(client, data).json()["workspace"]
    data["base_revision"] = first["revision"]
    replay = apply(client, data, first).json()["workspace"]
    assert len(replay["tasks"]) == 1 and replay["revision"] == 1


def test_approval_is_atomic_when_a_later_action_is_invalid(client):
    actions = [
        {"tool": "write_file", "arguments": {"name": "a.txt", "content": "ok"}},
        {"tool": "complete_task", "arguments": {"id": "missing"}},
    ]
    assert apply(client, {"actions": actions, "base_revision": 0}).status_code == 422
    assert ask(client, "List files").json()["events"][0]["result"] == {"files": []}


def test_workspace_size_limits(client):
    r = ask(client, "List files", workspace={"files": {"big.txt": "x" * 24001}})
    assert r.status_code == 422


def enable(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setenv("DEEZY_AI_ENABLED", "1")


def response(*items):
    return {"output": list(items), "usage": {"input_tokens": 10, "output_tokens": 5}}


def call(name, arguments):
    return {"type": "function_call", "name": name, "call_id": "call-1", "arguments": json.dumps(arguments)}


def text(value):
    return {"type": "message", "content": [{"type": "output_text", "text": value}]}


def test_ai_tool_call_creates_approval_not_an_unverified_success(client, monkeypatch):
    enable(monkeypatch)
    monkeypatch.setattr(
        module,
        "openai_request",
        lambda *a, **kw: response(
            text("I saved the file."), call("write_file", {"name": "notes.md", "content": "draft"})
        ),
    )
    result = ask(client, "Draft a note about API testing").json()
    assert result["mode"] == "ai" and result["actions"][0]["tool"] == "write_file"
    assert result["message"] == "Review the proposed changes below. Nothing has been saved yet."
    assert result["events"] == []


def test_ai_reads_real_supplied_file_then_answers(client, monkeypatch):
    enable(monkeypatch)
    calls = []

    def fake(items, *args, **kwargs):
        calls.append(json.loads(json.dumps(items)))
        return (
            response(call("read_file", {"name": "brief.md"}))
            if len(calls) == 1
            else response(text("The brief says ship the API."))
        )

    monkeypatch.setattr(module, "openai_request", fake)
    result = ask(client, "Summarize my brief", workspace={"files": {"brief.md": "Ship the API."}}).json()
    assert result["events"][0]["result"]["content"] == "Ship the API."
    tool_output = next(i for i in calls[1] if i.get("type") == "function_call_output")
    assert json.loads(tool_output["output"])["content"] == "Ship the API."
    assert result["usage"]["input_tokens"] == 20


def test_model_cannot_silently_remember_an_inferred_fact(client, monkeypatch):
    enable(monkeypatch)
    outputs = iter([response(call("save_memory", {"content": "User is wealthy"})), response(text("How can I help?"))])
    monkeypatch.setattr(module, "openai_request", lambda *a, **kw: next(outputs))
    result = ask(client, "Hello").json()
    assert result["actions"] == [] and result["events"][0]["status"] == "failed"


def test_only_actual_citation_annotations_become_source_cards():
    source = {"type": "url_citation", "url": "https://example.com/source", "title": "Source"}
    malicious = {"type": "url_citation", "url": "javascript:alert(1)", "title": "Bad"}
    result = module.collect_sources([{"content": [{"annotations": [source, source, malicious]}]}])
    assert result == [{"url": source["url"], "title": "Source"}]


def test_provider_failure_is_not_disguised_as_a_completed_task(client, monkeypatch):
    enable(monkeypatch)
    monkeypatch.setattr(
        module.requests, "post", lambda *a, **kw: (_ for _ in ()).throw(requests.Timeout("secret-test-value"))
    )
    r = ask(client, "Research a public topic")
    assert r.status_code == 503 and "secret-test-value" not in r.text
    assert "No changes" in r.json()["detail"]


def test_requests_use_responses_api_without_storage_and_with_bound_output(monkeypatch):
    enable(monkeypatch)
    captured = {}

    class Reply:
        status_code = 200
        ok = True

        def json(self):
            return {"status": "completed", "output": []}

    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Reply()

    monkeypatch.setattr(module.requests, "post", post)
    module.openai_request([], [], "system")
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["json"]["store"] is False
    assert captured["json"]["parallel_tool_calls"] is False
    assert captured["json"]["max_output_tokens"] <= 1600


def test_throttle_returns_clear_error(client):
    for _ in range(12):
        assert ask(client, "List files").status_code == 200
    assert ask(client, "List files").status_code == 429


def test_hosted_legacy_state_is_not_exposed(client, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    assert client.get("/api/settings").status_code == 404
    assert client.get("/api/assistant/status").status_code == 200
    assert client.get("/api/health").status_code == 200
