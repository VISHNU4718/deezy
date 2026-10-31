import os
import tempfile

import pytest

# Must be set before the app is imported: the app opens its database at import time.
_TMP = tempfile.mkdtemp(prefix="deezy-tests-")
os.environ["DEEZY_DEMO"] = "1"
os.environ["DEEZY_LLM_PROVIDER"] = "mock"
os.environ["DEEZY_DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ["DEEZY_SANDBOX_DIR"] = os.path.join(_TMP, "sandbox")

from fastapi.testclient import TestClient  # noqa: E402

from deezy.interface.web.api import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
