from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_stats_returns_expected_shape(client: TestClient) -> None:
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_tracks"] == 0
    assert data["storage_used_bytes"] == 0
    assert set(data["downloads_by_status"].keys()) == {
        "pending",
        "downloading",
        "processing",
        "done",
        "error",
    }
    assert all(v == 0 for v in data["downloads_by_status"].values())
