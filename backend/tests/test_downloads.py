from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    "url",
    [
        "https://spotify.com/track/123",
        "https://soundcloud.com/artist/track",
        "not-a-url-at-all",
        "",
        "https://google.com",
    ],
)
def test_post_download_rejects_invalid_url(client: TestClient, url: str) -> None:
    response = client.post("/api/downloads", json={"url": url})
    assert response.status_code == 422


def test_post_download_track_returns_pending_record(client: TestClient) -> None:
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    response = client.post("/api/downloads", json={"url": url, "mode": "track"})
    assert response.status_code == 201
    data = response.json()
    assert data["url"] == url
    assert data["status"] == "pending"
    assert data["mode"] == "track"
    assert "id" in data


async def _noop(*args: object, **kwargs: object) -> None:
    pass


def test_get_download_by_id_returns_record(client: TestClient) -> None:
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    with patch("routers.downloads._process_download", _noop):
        created = client.post("/api/downloads", json={"url": url}).json()

    response = client.get(f"/api/downloads/{created['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created["id"]
    assert data["url"] == url
    assert data["status"] == "pending"


def test_get_download_by_id_returns_404_for_missing(client: TestClient) -> None:
    response = client.get("/api/downloads/99999")
    assert response.status_code == 404


def test_list_downloads_returns_all(client: TestClient) -> None:
    with patch("routers.downloads._process_download", _noop):
        client.post(
            "/api/downloads", json={"url": "https://www.youtube.com/watch?v=aaa"}
        )
        client.post(
            "/api/downloads", json={"url": "https://www.youtube.com/watch?v=bbb"}
        )

    response = client.get("/api/downloads")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_downloads_filters_by_status(client: TestClient) -> None:
    with patch("routers.downloads._process_download", _noop):
        client.post(
            "/api/downloads", json={"url": "https://www.youtube.com/watch?v=aaa"}
        )

    response = client.get("/api/downloads?status=pending")
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = client.get("/api/downloads?status=done")
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_download_task_sets_error_on_failure(client: TestClient) -> None:
    with patch(
        "services.downloader.run_download",
        new_callable=AsyncMock,
        side_effect=RuntimeError("yt-dlp failed: private video"),
    ):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        response = client.post("/api/downloads", json={"url": url})
        download_id = response.json()["id"]

    status_response = client.get(f"/api/downloads/{download_id}")
    data = status_response.json()
    assert data["status"] == "error"
    assert "error_message" in data
    assert "yt-dlp failed" in data["error_message"]


def test_discovery_mode_creates_multiple_downloads(client: TestClient) -> None:
    seed_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    related_urls = [
        "https://www.youtube.com/watch?v=rel001",
        "https://www.youtube.com/watch?v=rel002",
        "https://www.youtube.com/watch?v=rel003",
    ]

    fetch_patch = patch(
        "services.downloader.fetch_related_urls",
        new_callable=AsyncMock,
        return_value=related_urls,
    )
    with fetch_patch, patch("routers.downloads._process_download", _noop):
        response = client.post(
            "/api/downloads",
            json={"url": seed_url, "mode": "discovery", "limit": 3},
        )

    assert response.status_code == 201
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 3
    assert all(item["mode"] == "discovery" for item in data)
    assert all(item["status"] == "pending" for item in data)


def test_discovery_limit_controls_track_count(client: TestClient) -> None:
    seed_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    many_urls = [f"https://www.youtube.com/watch?v=rel{i:03d}" for i in range(20)]

    fetch_patch = patch(
        "services.downloader.fetch_related_urls",
        new_callable=AsyncMock,
        return_value=many_urls,
    )
    with fetch_patch, patch("routers.downloads._process_download", _noop):
        response = client.post(
            "/api/downloads",
            json={"url": seed_url, "mode": "discovery", "limit": 5},
        )

    assert len(response.json()) == 5


def test_done_download_includes_media_metadata(client: TestClient) -> None:
    mock_result = {
        "title": "Never Gonna Give You Up",
        "artist": "Rick Astley",
        "file_path": "music/Rick Astley - Never Gonna Give You Up.mp3",
        "file_size_bytes": 5_000_000,
        "duration_seconds": 213,
    }
    run_patch = patch(
        "services.downloader.run_download",
        new_callable=AsyncMock,
        return_value=mock_result,
    )
    with run_patch:
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        download_id = client.post("/api/downloads", json={"url": url}).json()["id"]

    data = client.get(f"/api/downloads/{download_id}").json()
    assert data["status"] == "done"
    assert data["title"] == "Never Gonna Give You Up"
    assert data["artist"] == "Rick Astley"
    assert data["duration_seconds"] == 213


def test_retry_resets_error_and_reruns(client: TestClient) -> None:
    with patch(
        "services.downloader.run_download",
        new_callable=AsyncMock,
        side_effect=RuntimeError("name resolution failed"),
    ):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        download_id = client.post("/api/downloads", json={"url": url}).json()["id"]

    assert client.get(f"/api/downloads/{download_id}").json()["status"] == "error"

    mock_result = {
        "title": "Track",
        "artist": "Artist",
        "file_path": "music/Artist - Track.mp3",
        "file_size_bytes": 1_000_000,
        "duration_seconds": 180,
    }
    with patch(
        "services.downloader.run_download",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        response = client.post(f"/api/downloads/{download_id}/retry")
        assert response.status_code == 200
        assert response.json()["status"] == "pending"
        assert response.json()["error_message"] is None

    data = client.get(f"/api/downloads/{download_id}").json()
    assert data["status"] == "done"


def test_retry_returns_404_for_non_error_download(client: TestClient) -> None:
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    with patch("routers.downloads._process_download", _noop):
        download_id = client.post("/api/downloads", json={"url": url}).json()["id"]

    response = client.post(f"/api/downloads/{download_id}/retry")
    assert response.status_code == 404


def test_retry_returns_404_for_nonexistent_download(client: TestClient) -> None:
    response = client.post("/api/downloads/99999/retry")
    assert response.status_code == 404


def test_download_task_transitions_to_done(client: TestClient) -> None:
    mock_result = {
        "title": "Never Gonna Give You Up",
        "artist": "Rick Astley",
        "file_path": "music/Rick Astley - Never Gonna Give You Up.mp3",
        "file_size_bytes": 5_000_000,
        "duration_seconds": 213,
    }

    run_patch = patch(
        "services.downloader.run_download",
        new_callable=AsyncMock,
        return_value=mock_result,
    )
    with run_patch:
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        response = client.post("/api/downloads", json={"url": url})
        download_id = response.json()["id"]

    status_response = client.get(f"/api/downloads/{download_id}")
    assert status_response.json()["status"] == "done"

    media_response = client.get("/api/library")
    assert media_response.status_code == 200
    items = media_response.json()
    assert len(items) == 1
    assert items[0]["title"] == "Never Gonna Give You Up"
