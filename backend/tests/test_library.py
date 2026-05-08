import os
import sqlite3
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def _create_media(
    client: TestClient,
    *,
    title: str = "Never Gonna Give You Up",
    artist: str = "Rick Astley",
    file_path: str = "music/rick.mp3",
    duration_seconds: int = 213,
    mood: str | None = None,
    url: str = "https://www.youtube.com/watch?v=abc123",
) -> None:
    mock_result = {
        "title": title,
        "artist": artist,
        "file_path": file_path,
        "file_size_bytes": 5_000_000,
        "duration_seconds": duration_seconds,
    }
    with patch(
        "services.downloader.run_download",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        client.post("/api/downloads", json={"url": url})

    if mood is not None:
        with sqlite3.connect(os.environ["DATABASE_PATH"]) as conn:
            conn.execute("UPDATE media SET mood=? WHERE title=?", (mood, title))
            conn.commit()


def test_list_library_mood_filter(client: TestClient) -> None:
    _create_media(
        client,
        title="Song A",
        mood="energetic",
        url="https://www.youtube.com/watch?v=aaa",
    )
    _create_media(
        client, title="Song B", mood="chill", url="https://www.youtube.com/watch?v=bbb"
    )

    response = client.get("/api/library?mood=energetic")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["title"] == "Song A"
    assert items[0]["mood"] == "energetic"


def test_list_library_search_filter(client: TestClient) -> None:
    _create_media(
        client,
        title="Never Gonna Give You Up",
        artist="Rick Astley",
        url="https://www.youtube.com/watch?v=aaa",
    )
    _create_media(
        client,
        title="Bohemian Rhapsody",
        artist="Queen",
        url="https://www.youtube.com/watch?v=bbb",
    )

    response = client.get("/api/library?search=rick")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["title"] == "Never Gonna Give You Up"

    response = client.get("/api/library?search=RHAPSODY")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["title"] == "Bohemian Rhapsody"


def test_get_library_item_by_id(client: TestClient) -> None:
    _create_media(client)

    item_id = client.get("/api/library").json()[0]["id"]
    response = client.get(f"/api/library/{item_id}")
    assert response.status_code == 200
    item = response.json()
    assert item["id"] == item_id
    assert item["title"] == "Never Gonna Give You Up"
    assert item["stream_url"] == "/media/music/rick.mp3"


def test_get_library_item_returns_404_for_missing(client: TestClient) -> None:
    response = client.get("/api/library/99999")
    assert response.status_code == 404


def test_delete_library_item_returns_204_and_removes_record(client: TestClient) -> None:
    _create_media(client)
    item_id = client.get("/api/library").json()[0]["id"]

    response = client.delete(f"/api/library/{item_id}")
    assert response.status_code == 204

    assert client.get(f"/api/library/{item_id}").status_code == 404
    assert client.get("/api/library").json() == []


def test_delete_library_item_removes_file_from_disk(client: TestClient) -> None:
    media_dir = os.environ["MEDIA_PATH"]
    music_dir = os.path.join(media_dir, "music")
    os.makedirs(music_dir, exist_ok=True)
    mp3_path = os.path.join(music_dir, "rick.mp3")
    open(mp3_path, "w").close()

    _create_media(client, file_path="music/rick.mp3")
    item_id = client.get("/api/library").json()[0]["id"]

    assert os.path.exists(mp3_path)
    client.delete(f"/api/library/{item_id}")
    assert not os.path.exists(mp3_path)


def test_delete_library_item_soft_fails_when_file_missing(client: TestClient) -> None:
    _create_media(client, file_path="music/nonexistent.mp3")
    item_id = client.get("/api/library").json()[0]["id"]

    response = client.delete(f"/api/library/{item_id}")
    assert response.status_code == 204
    assert client.get(f"/api/library/{item_id}").status_code == 404


def test_delete_library_item_returns_404_for_missing_record(client: TestClient) -> None:
    response = client.delete("/api/library/99999")
    assert response.status_code == 404


def test_media_files_are_served_over_http(client: TestClient) -> None:
    media_dir = os.environ["MEDIA_PATH"]
    music_dir = os.path.join(media_dir, "music")
    os.makedirs(music_dir, exist_ok=True)
    mp3_path = os.path.join(music_dir, "test.mp3")
    with open(mp3_path, "wb") as f:
        f.write(b"fake mp3 content")

    response = client.get("/media/music/test.mp3")
    assert response.status_code == 200
    assert response.content == b"fake mp3 content"


def test_list_library_returns_track_with_correct_fields(client: TestClient) -> None:
    _create_media(client)

    response = client.get("/api/library")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    item = items[0]
    assert item["title"] == "Never Gonna Give You Up"
    assert item["artist"] == "Rick Astley"
    assert item["duration_seconds"] == 213
    assert item["mood"] is None
    assert item["stream_url"] == "/media/music/rick.mp3"
    assert "file_path" not in item
