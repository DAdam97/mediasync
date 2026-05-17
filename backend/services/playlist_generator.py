import json
import sqlite3
from pathlib import Path

import numpy as np


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0.0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def _mmr_select(
    with_features: list[dict],
    without_features: list[dict],
    limit: int,
) -> list[dict]:
    selected: list[dict] = []
    candidates = list(with_features)

    while candidates and len(selected) < limit:
        if not selected:
            best = candidates[0]
        else:
            best = max(
                candidates,
                key=lambda c: -max(
                    _cosine_similarity(c["_fv"], s["_fv"]) for s in selected
                ),
            )
        selected.append(best)
        candidates.remove(best)

    remaining = limit - len(selected)
    if remaining > 0:
        selected.extend(without_features[:remaining])

    return selected


def _write_m3u(tracks: list[dict], m3u_path: Path) -> None:
    m3u_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["#EXTM3U"]
    for t in tracks:
        duration = t.get("duration_seconds") or -1
        artist = t.get("artist") or ""
        title = t["title"]
        inf_title = f"{artist} - {title}" if artist else title
        lines.append(f"#EXTINF:{duration},{inf_title}")
        filename = Path(t["file_path"]).name
        lines.append(f"../music/{filename}")
    m3u_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_playlist(
    db_path: str,
    media_path: str,
    name: str,
    mood: str | None = None,
    genre: str | None = None,
    limit: int = 50,
    playlist_type: str = "auto",
) -> dict:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    sql = (
        "SELECT m.id, m.title, m.artist, m.mood, m.genre,"
        " m.file_path, m.duration_seconds, af.feature_vector"
        " FROM media m LEFT JOIN audio_features af ON af.media_id = m.id"
        " WHERE 1=1"
    )
    params: list[object] = []
    if mood is not None:
        sql += " AND m.mood=?"
        params.append(mood)
    if genre is not None:
        sql += " AND m.genre=?"
        params.append(genre)

    rows = con.execute(sql, params).fetchall()

    with_features: list[dict] = []
    without_features: list[dict] = []
    for row in rows:
        t = dict(row)
        fv_json = t.pop("feature_vector")
        if fv_json:
            t["_fv"] = json.loads(fv_json)
            with_features.append(t)
        else:
            without_features.append(t)

    ordered = _mmr_select(with_features, without_features, limit)
    tracks = [{k: v for k, v in t.items() if k != "_fv"} for t in ordered]

    playlists_dir = Path(media_path) / "playlists"
    safe_name = name.replace(" ", "_").lower()
    m3u_filename = f"{safe_name}.m3u"
    m3u_path = playlists_dir / m3u_filename
    _write_m3u(tracks, m3u_path)
    m3u_rel = f"playlists/{m3u_filename}"

    filter_criteria: dict[str, object] = {}
    if mood:
        filter_criteria["mood"] = mood
    if genre:
        filter_criteria["genre"] = genre

    cur = con.execute(
        "INSERT INTO playlists (name, type, filter_criteria, m3u_path)"
        " VALUES (?, ?, ?, ?)",
        (name, playlist_type, json.dumps(filter_criteria), m3u_rel),
    )
    playlist_id = cur.lastrowid
    assert playlist_id is not None

    for pos, track in enumerate(tracks):
        con.execute(
            "INSERT INTO playlist_items (playlist_id, media_id, position)"
            " VALUES (?, ?, ?)",
            (playlist_id, track["id"], pos),
        )

    con.commit()
    con.close()

    return {
        "id": playlist_id,
        "name": name,
        "type": playlist_type,
        "m3u_path": m3u_rel,
        "tracks": tracks,
    }


def _delete_auto_playlist(db_path: str, media_path: str, name: str) -> None:
    con = sqlite3.connect(db_path)
    row = con.execute(
        "SELECT id, m3u_path FROM playlists WHERE name=? AND type='auto'", (name,)
    ).fetchone()
    if row:
        m3u = Path(media_path) / row[1]
        m3u.unlink(missing_ok=True)
        con.execute("DELETE FROM playlist_items WHERE playlist_id=?", (row[0],))
        con.execute("DELETE FROM playlists WHERE id=?", (row[0],))
        con.commit()
    con.close()


def generate_mood_playlists(db_path: str, media_path: str) -> None:
    for mood in ("energetic", "chill", "intense"):
        name = f"auto_{mood}"
        _delete_auto_playlist(db_path, media_path, name)
        generate_playlist(db_path, media_path, name=name, mood=mood, limit=100)
