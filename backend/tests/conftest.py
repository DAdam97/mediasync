import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("MEDIA_PATH", str(tmp_path))
    from main import app

    with TestClient(app) as c:
        yield c
