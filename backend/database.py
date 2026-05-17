from collections.abc import AsyncGenerator

import aiosqlite

from config import db_path

_CREATE_DOWNLOADS = """
CREATE TABLE IF NOT EXISTS downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    source TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    title TEXT,
    artist TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_MEDIA = """
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    artist TEXT,
    album TEXT,
    duration_seconds INTEGER,
    file_path TEXT NOT NULL,
    file_size_bytes INTEGER,
    media_type TEXT NOT NULL DEFAULT 'music',
    source_url TEXT,
    download_id INTEGER REFERENCES downloads(id),
    genre TEXT,
    genre_confidence REAL,
    mood TEXT,
    mood_confidence REAL,
    transcript_path TEXT,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP
)
"""

_CREATE_AUDIO_FEATURES = """
CREATE TABLE IF NOT EXISTS audio_features (
    media_id INTEGER PRIMARY KEY REFERENCES media(id),
    mfcc_mean TEXT,
    mfcc_std TEXT,
    spectral_centroid REAL,
    spectral_rolloff REAL,
    zero_crossing_rate REAL,
    chroma_mean TEXT,
    tempo REAL,
    energy REAL,
    feature_vector TEXT
)
"""

_CREATE_PLAYLISTS = """
CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    filter_criteria TEXT,
    m3u_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_PLAYLIST_ITEMS = """
CREATE TABLE IF NOT EXISTS playlist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id INTEGER REFERENCES playlists(id) ON DELETE CASCADE,
    media_id INTEGER REFERENCES media(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

_ALL_TABLES = [
    _CREATE_DOWNLOADS,
    _CREATE_MEDIA,
    _CREATE_AUDIO_FEATURES,
    _CREATE_PLAYLISTS,
    _CREATE_PLAYLIST_ITEMS,
]


async def init_db() -> None:
    async with aiosqlite.connect(db_path()) as db:
        for stmt in _ALL_TABLES:
            await db.execute(stmt)
        for col in ("title", "artist", "blacklist_id"):
            try:
                await db.execute(f"ALTER TABLE downloads ADD COLUMN {col} TEXT")
            except Exception:
                pass
        await db.commit()


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    async with aiosqlite.connect(db_path()) as db:
        yield db
