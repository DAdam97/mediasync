import io
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def _add_media(
    client: TestClient, title: str = "Test Track", mood: str = "energetic"
) -> int:
    safe = title.replace(" ", "_")
    fake = {
        "title": title,
        "artist": "Artist",
        "file_path": f"music/{safe}.mp3",
        "file_size_bytes": 1000,
        "duration_seconds": 210,
    }
    with (
        patch("services.downloader.run_download", AsyncMock(return_value=fake)),
        patch("services.feature_extractor.extract_features", return_value=[0.0] * 57),
        patch("services.classifier.classify", return_value=(mood, 0.9)),
        patch("services.playlist_generator.generate_mood_playlists"),
    ):
        client.post(
            "/api/downloads", json={"url": "https://www.youtube.com/watch?v=abc123"}
        )
    return client.get("/api/library").json()[-1]["id"]


# --- Cycle 7: GET /api/playlists ---


def test_list_playlists_empty(client: TestClient) -> None:
    response = client.get("/api/playlists")
    assert response.status_code == 200
    assert response.json() == []


# --- Cycle 8: POST /api/playlists (manual) ---


def test_create_manual_playlist(client: TestClient) -> None:
    response = client.post("/api/playlists", json={"name": "My Workout"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Workout"
    assert data["type"] == "manual"
    assert data["id"] > 0


def test_list_playlists_after_create(client: TestClient) -> None:
    client.post("/api/playlists", json={"name": "Workout"})
    response = client.get("/api/playlists")
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Workout"


# --- Cycle 9: POST /api/playlists/generate ---


def test_generate_playlist_endpoint(client: TestClient) -> None:
    _add_media(client, "Energetic Song", mood="energetic")

    with patch("routers.playlists.generate_playlist") as mock_gen:
        mock_gen.return_value = {
            "id": 1,
            "name": "Demo",
            "type": "auto",
            "m3u_path": "playlists/demo.m3u",
            "tracks": [],
        }
        response = client.post(
            "/api/playlists/generate",
            json={"name": "Demo", "mood": "energetic", "limit": 5},
        )

    assert response.status_code == 201
    assert response.json()["name"] == "Demo"


# --- Cycle 10: POST /api/playlists/{id}/tracks ---


def test_add_track_to_playlist(client: TestClient) -> None:
    pl = client.post("/api/playlists", json={"name": "Workout"}).json()
    media_id = _add_media(client)

    response = client.post(
        f"/api/playlists/{pl['id']}/tracks", json={"media_id": media_id}
    )
    assert response.status_code == 200


def test_add_duplicate_track_returns_409(client: TestClient) -> None:
    pl = client.post("/api/playlists", json={"name": "Workout"}).json()
    media_id = _add_media(client)

    client.post(f"/api/playlists/{pl['id']}/tracks", json={"media_id": media_id})
    response = client.post(
        f"/api/playlists/{pl['id']}/tracks", json={"media_id": media_id}
    )
    assert response.status_code == 409


def test_add_track_to_missing_playlist_returns_404(client: TestClient) -> None:
    media_id = _add_media(client)
    response = client.post("/api/playlists/999/tracks", json={"media_id": media_id})
    assert response.status_code == 404


# --- Cycle 11: DELETE /api/playlists/{id} ---


def test_delete_playlist(client: TestClient) -> None:
    pl = client.post("/api/playlists", json={"name": "Temp"}).json()

    response = client.delete(f"/api/playlists/{pl['id']}")
    assert response.status_code == 204
    assert client.get("/api/playlists").json() == []


def test_delete_missing_playlist_returns_404(client: TestClient) -> None:
    response = client.delete("/api/playlists/999")
    assert response.status_code == 404


# --- Cycle 12: GET /api/playlists/{id}/download ---


def test_download_playlist_zip(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEDIA_PATH", str(tmp_path))

    mp3 = tmp_path / "music" / "Test_Track.mp3"
    mp3.parent.mkdir(exist_ok=True)
    mp3.write_bytes(b"fake mp3 bytes")

    pl = client.post("/api/playlists", json={"name": "Demo"}).json()
    media_id = _add_media(client, "Test Track")
    client.post(f"/api/playlists/{pl['id']}/tracks", json={"media_id": media_id})

    response = client.get(f"/api/playlists/{pl['id']}/download")
    assert response.status_code == 200
    assert "zip" in response.headers["content-type"]

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        assert "Demo/Test_Track.mp3" in zf.namelist()


# --- Cycle 13: GET /api/playlists/{id}/tracks ---


def test_list_playlist_tracks(client: TestClient) -> None:
    pl = client.post("/api/playlists", json={"name": "Workout"}).json()
    media_id = _add_media(client, "Track A")
    client.post(f"/api/playlists/{pl['id']}/tracks", json={"media_id": media_id})

    response = client.get(f"/api/playlists/{pl['id']}/tracks")
    assert response.status_code == 200
    tracks = response.json()
    assert len(tracks) == 1
    assert tracks[0]["id"] == media_id
    assert tracks[0]["title"] == "Track A"


def test_list_tracks_missing_playlist_returns_404(client: TestClient) -> None:
    response = client.get("/api/playlists/999/tracks")
    assert response.status_code == 404


# --- Cycle 15: DELETE /api/playlists/{id}/tracks/{media_id} ---


def test_remove_track_from_playlist(client: TestClient) -> None:
    pl = client.post("/api/playlists", json={"name": "Workout"}).json()
    media_id = _add_media(client, "Track A")
    client.post(f"/api/playlists/{pl['id']}/tracks", json={"media_id": media_id})

    response = client.delete(f"/api/playlists/{pl['id']}/tracks/{media_id}")
    assert response.status_code == 204

    # track gone from playlist
    tracks = client.get(f"/api/playlists/{pl['id']}/tracks").json()
    assert tracks == []

    # track still in library
    library = client.get("/api/library").json()
    assert any(t["id"] == media_id for t in library)


def test_remove_track_not_in_playlist_returns_404(client: TestClient) -> None:
    pl = client.post("/api/playlists", json={"name": "Workout"}).json()
    media_id = _add_media(client)

    response = client.delete(f"/api/playlists/{pl['id']}/tracks/{media_id}")
    assert response.status_code == 404


# --- Cycle 17: PATCH /api/playlists/{id} (rename) ---


def test_rename_playlist(client: TestClient) -> None:
    pl = client.post("/api/playlists", json={"name": "Old Name"}).json()

    response = client.patch(f"/api/playlists/{pl['id']}", json={"name": "New Name"})
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"

    listed = client.get("/api/playlists").json()
    assert listed[0]["name"] == "New Name"


def test_rename_missing_playlist_returns_404(client: TestClient) -> None:
    response = client.patch("/api/playlists/999", json={"name": "X"})
    assert response.status_code == 404
