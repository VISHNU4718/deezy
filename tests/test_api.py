import pytest


def test_health_reports_demo(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["demo"] is True


def test_tools_listed(client):
    names = {t["name"] for t in client.get("/api/tools").json()}
    assert {"search_files", "read_file", "create_file"} <= names


@pytest.mark.parametrize("objective", ["", "x" * 5000])
def test_task_validation(client, objective):
    assert client.post("/api/tasks", json={"objective": objective}).status_code == 422


def test_read_only_task_runs_immediately(client):
    task = client.post("/api/tasks", json={"objective": "find a desk lamp under 50"}).json()
    assert task["status"] == "completed"


def test_approval_flow(client):
    task = client.post("/api/tasks", json={"objective": "create a file api-flow.txt with content: ok"}).json()
    assert task["status"] == "waiting_for_approval"
    done = client.post(f"/api/tasks/{task['id']}/approve").json()
    assert done["status"] == "completed"
    # An approved task cannot be approved or rejected again.
    assert client.post(f"/api/tasks/{task['id']}/approve").status_code == 409
    assert client.post(f"/api/tasks/{task['id']}/reject").status_code == 409


def test_reject_flow_runs_nothing(client):
    task = client.post("/api/tasks", json={"objective": "create a file rejected.txt with content: no"}).json()
    rejected = client.post(f"/api/tasks/{task['id']}/reject").json()
    assert rejected["status"] == "cancelled"
    read = client.post("/api/tasks", json={"objective": "read rejected.txt"}).json()
    assert read["status"] == "failed"


def test_unknown_task_is_404(client):
    assert client.get("/api/tasks/999999").status_code == 404
    assert client.post("/api/tasks/999999/approve").status_code == 404


def test_history_lists_tasks(client):
    assert len(client.get("/api/history").json()) >= 1


def test_settings_validation_and_persistence(client):
    assert client.put("/api/settings", json={"agent": {"max_iterations": "lots"}}).status_code == 422
    assert client.put("/api/settings", json={"llm": {"provider": "nonsense"}}).status_code == 422
    assert client.put("/api/settings", json={"llm": {"provider": "openrouter"}}).status_code == 403
    ok = client.put("/api/settings", json={"llm": {"temperature": 0.3}})
    assert ok.status_code == 200
    assert client.get("/api/settings").json()["llm"]["temperature"] == 0.3


def test_conversation_lifecycle(client):
    conv = client.post("/api/conversations", json={"title": "First"}).json()
    cid = conv["id"]
    assert client.post(f"/api/conversations/{cid}/messages", json={"role": "user", "content": "hi"}).status_code == 200
    assert client.post(f"/api/conversations/{cid}/messages", json={"role": "bad", "content": "hi"}).status_code == 422
    full = client.get(f"/api/conversations/{cid}").json()
    assert [m["content"] for m in full["messages"]] == ["hi"]
    assert client.patch(f"/api/conversations/{cid}", json={"title": "Renamed"}).json()["title"] == "Renamed"
    exported = client.get(f"/api/conversations/{cid}/export").json()
    imported = client.post("/api/conversations/import", json=exported)
    assert imported.status_code == 200
    assert client.delete(f"/api/conversations/{cid}").status_code == 200
    assert client.get(f"/api/conversations/{cid}").status_code == 404


def test_memory_crud(client):
    created = client.post("/api/memories", json={"category": "fact", "content": "likes lamps"}).json()
    mid = created["id"]
    assert client.patch(f"/api/memories/{mid}", json={"content": "likes desks"}).json()["content"] == "likes desks"
    assert client.post("/api/memories", json={"category": "fact", "content": ""}).status_code == 422
    assert client.delete(f"/api/memories/{mid}").status_code == 200
    assert client.get(f"/api/memories/{mid}").status_code == 404
