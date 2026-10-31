import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

ENTRY = Path(__file__).resolve().parent.parent / "api" / "index.py"


def _load():
    spec = importlib.util.spec_from_file_location("vercel_entry", ENTRY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rewritten_path_is_restored(client):
    entry = TestClient(_load().app)
    assert entry.get("/api/index?p=health").json()["status"] == "ok"
    assert entry.get("/api/index?p=tasks&limit=1").status_code == 200
