import json
import sqlite3
from pathlib import Path

from services.playlist_generator import generate_mood_playlists, generate_playlist

_SCHEMA = """
CREATE TABLE media (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    artist TEXT,
    mood TEXT,
    genre TEXT,
    file_path TEXT NOT NULL,
    duration_seconds INTEGER
);
CREATE TABLE audio_features (
    media_id INTEGER PRIMARY KEY,
    feature_vector TEXT
);
CREATE TABLE playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    filter_criteria TEXT,
    m3u_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE playlist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id INTEGER,
    media_id INTEGER,
    position INTEGER NOT NULL
);
"""

_FV_A = [1.0] + [0.0] * 56
_FV_B = [0.0] + [1.0] + [0.0] * 55


def _make_db(tmp_path: Path) -> str:
    path = str(tmp_path / "test.db")
    con = sqlite3.connect(path)
    con.executescript(_SCHEMA)
    con.close()
    return path


def _insert_track(
    db_path: str,
    id_: int,
    title: str,
    *,
    mood: str | None = None,
    genre: str | None = None,
    features: list[float] | None = None,
    file_path: str | None = None,
) -> None:
    fp = file_path or f"music/{title.replace(' ', '_')}.mp3"
    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT INTO media (id, title, mood, genre, file_path) VALUES (?, ?, ?, ?, ?)",
        (id_, title, mood, genre, fp),
    )
    if features is not None:
        con.execute(
            "INSERT INTO audio_features (media_id, feature_vector) VALUES (?, ?)",
            (id_, json.dumps(features)),
        )
    con.commit()
    con.close()


# --- Cycle 1: tracer bullet — returns matching tracks ---


def test_generate_playlist_returns_matching_tracks(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    _insert_track(db, 1, "Track A", mood="energetic", features=_FV_A)
    _insert_track(db, 2, "Track B", mood="energetic", features=_FV_B)
    _insert_track(db, 3, "Track C", mood="chill", features=_FV_A)

    result = generate_playlist(db, str(tmp_path), name="Test", mood="energetic")

    titles = {t["title"] for t in result["tracks"]}
    assert titles == {"Track A", "Track B"}


# --- Cycle 2: track without feature vector goes last ---


def test_generate_playlist_no_features_appended_last(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    _insert_track(db, 1, "Has Features", mood="energetic", features=_FV_A)
    _insert_track(db, 2, "No Features", mood="energetic")

    result = generate_playlist(db, str(tmp_path), name="Test", mood="energetic")

    assert result["tracks"][-1]["title"] == "No Features"


# --- Cycle 3: limit is respected ---


def test_generate_playlist_respects_limit(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    for i in range(5):
        _insert_track(db, i + 1, f"Track {i}", mood="energetic", features=_FV_A)

    result = generate_playlist(
        db, str(tmp_path), name="Test", mood="energetic", limit=3
    )

    assert len(result["tracks"]) == 3


# --- Cycle 4: .m3u written with relative paths ---


def test_generate_playlist_writes_m3u_with_relative_paths(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    _insert_track(
        db,
        1,
        "My Song",
        mood="energetic",
        features=_FV_A,
        file_path="music/My_Song.mp3",
    )

    result = generate_playlist(db, str(tmp_path), name="My Playlist", mood="energetic")

    m3u_path = tmp_path / result["m3u_path"]
    assert m3u_path.exists()
    content = m3u_path.read_text()
    assert "#EXTM3U" in content
    assert "../music/My_Song.mp3" in content
    assert str(tmp_path) not in content  # no absolute paths


# --- Cycle 5: generate_mood_playlists writes one .m3u per mood ---


def test_generate_mood_playlists_creates_one_file_per_mood(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    _insert_track(db, 1, "E Track", mood="energetic", features=_FV_A)
    _insert_track(db, 2, "C Track", mood="chill", features=_FV_B)

    generate_mood_playlists(db, str(tmp_path))

    assert (tmp_path / "playlists" / "auto_energetic.m3u").exists()
    assert (tmp_path / "playlists" / "auto_chill.m3u").exists()
    assert (tmp_path / "playlists" / "auto_intense.m3u").exists()


# --- Cycle 6: generate_mood_playlists does not duplicate DB records on re-run ---


def test_generate_mood_playlists_replaces_not_duplicates(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    _insert_track(db, 1, "E Track", mood="energetic", features=_FV_A)

    generate_mood_playlists(db, str(tmp_path))
    generate_mood_playlists(db, str(tmp_path))

    con = sqlite3.connect(db)
    count = con.execute(
        "SELECT COUNT(*) FROM playlists WHERE name='auto_energetic'"
    ).fetchone()[0]
    con.close()
    assert count == 1
