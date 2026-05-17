from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def test_mix_mode_returns_pending_records_for_each_track(client: TestClient) -> None:
    tracks = ["Artist A - Song One", "Artist B - Song Two", "Artist C - Song Three"]

    extract_patch = patch(
        "services.mix_extractor.extract_tracklist",
        new_callable=AsyncMock,
        return_value=tracks,
    )
    noop = AsyncMock()
    with extract_patch, patch("services.download_queue.execute_download", noop):
        response = client.post(
            "/api/downloads",
            json={"url": "https://www.youtube.com/watch?v=abc123", "mode": "mix"},
        )

    assert response.status_code == 201
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 3
    assert all(item["mode"] == "mix" for item in data)
    assert all(item["status"] == "pending" for item in data)
    assert data[0]["url"] == "Artist A - Song One"


def test_mix_mode_returns_error_record_when_no_tracklist(client: TestClient) -> None:
    extract_patch = patch(
        "services.mix_extractor.extract_tracklist",
        new_callable=AsyncMock,
        return_value=[],
    )
    with extract_patch:
        response = client.post(
            "/api/downloads",
            json={"url": "https://www.youtube.com/watch?v=abc123", "mode": "mix"},
        )

    assert response.status_code == 201
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["status"] == "error"
    assert "No tracklist found" in data[0]["error_message"]


def test_mix_track_downloads_and_creates_media_record(client: TestClient) -> None:
    tracks = ["Artist A - Song One", "Artist B - Song Two", "Artist C - Song Three"]

    async def _make_result(
        query: str, blacklist_id: str = "", media_path: str = ""
    ) -> dict:
        slug = query.replace(" - ", "_").replace(" ", "_")
        return {
            "title": query.split(" - ")[1],
            "artist": query.split(" - ")[0],
            "file_path": f"music/{slug}.mp3",
            "file_size_bytes": 4_000_000,
            "duration_seconds": 210,
        }

    extract_patch = patch(
        "services.mix_extractor.extract_tracklist",
        new_callable=AsyncMock,
        return_value=tracks,
    )
    search_patch = patch(
        "services.downloader.search_and_download",
        new_callable=AsyncMock,
        side_effect=_make_result,
    )
    with extract_patch, search_patch:
        response = client.post(
            "/api/downloads",
            json={"url": "https://www.youtube.com/watch?v=abc123", "mode": "mix"},
        )

    assert response.status_code == 201
    records = response.json()

    done_count = sum(
        1
        for r in records
        if client.get(f"/api/downloads/{r['id']}").json()["status"] == "done"
    )
    assert done_count == 3

    library = client.get("/api/library").json()
    assert len(library) == 3
