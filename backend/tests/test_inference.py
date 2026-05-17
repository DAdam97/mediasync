from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def _fake_download_result(file_path: str = "music/track.mp3") -> dict:
    return {
        "title": "Test Track",
        "artist": "Test Artist",
        "file_path": file_path,
        "file_size_bytes": 1_000_000,
        "duration_seconds": 210,
    }


def test_execute_download_sets_mood_on_media(client: TestClient) -> None:
    run_dl = AsyncMock(return_value=_fake_download_result())
    fake_features = [0.0] * 57

    with (
        patch("services.downloader.run_download", run_dl),
        patch(
            "services.feature_extractor.extract_features", return_value=fake_features
        ),
        patch("services.classifier.classify", return_value=("energetic", 0.85)),
    ):
        response = client.post(
            "/api/downloads",
            json={"url": "https://www.youtube.com/watch?v=test123"},
        )

    assert response.status_code == 201
    library = client.get("/api/library").json()
    assert len(library) == 1
    assert library[0]["mood"] == "energetic"


def test_execute_download_download_done_when_model_missing(client: TestClient) -> None:
    run_dl = AsyncMock(return_value=_fake_download_result())

    with patch("services.downloader.run_download", run_dl):
        response = client.post(
            "/api/downloads",
            json={"url": "https://www.youtube.com/watch?v=test123"},
        )

    assert response.status_code == 201
    record_id = response.json()["id"]
    download = client.get(f"/api/downloads/{record_id}").json()
    assert download["status"] == "done"
    library = client.get("/api/library").json()
    assert library[0]["mood"] is None


def test_execute_download_done_even_if_inference_raises(client: TestClient) -> None:
    run_dl = AsyncMock(return_value=_fake_download_result())

    with (
        patch("services.downloader.run_download", run_dl),
        patch(
            "services.feature_extractor.extract_features",
            side_effect=RuntimeError("librosa failed"),
        ),
    ):
        response = client.post(
            "/api/downloads",
            json={"url": "https://www.youtube.com/watch?v=test123"},
        )

    assert response.status_code == 201
    record_id = response.json()["id"]
    download = client.get(f"/api/downloads/{record_id}").json()
    assert download["status"] == "done"
