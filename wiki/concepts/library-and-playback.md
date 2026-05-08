---
title: Library vs Offline Playback
type: concept
related: [architecture.md, ../progress/issues.md]
updated: 2026-05-08
---

# Library vs Offline Playback

Two distinct concepts that are easy to confuse.

---

## Library (web UI, issue #6)

The server-side catalog of all downloaded tracks. Accessible via the web UI when the browser has a connection to the Pi (Tailscale or local WiFi).

- Lives on the Pi (`media` table in SQLite)
- Browsable, filterable, searchable via `GET /api/library`
- Filtering is **server-side**: `?mood=energetic`, `?search=rick` are SQL queries on the Pi
- Supports: browse, filter by mood, search by title/artist, delete track
- **Requires Pi connectivity** — does not work offline

## Offline Playback (Syncthing + Poweramp, issues #9 + #11)

MP3 files and `.m3u` playlists synced from the Pi to the Android phone via Syncthing. Poweramp plays them from local storage.

- Lives on the phone (local filesystem)
- Synced once over WiFi, then fully offline
- **Does not require Pi connectivity after sync**

---

## Stream vs Download to Device (issue #6 feature)

Two ways to get audio from the Pi to a PC for playback:

### Stream
The Pi serves MP3 files over HTTP (`/media/music/filename.mp3`). Clicking Stream opens the file URL in a new browser tab — the browser or OS default player handles playback. **Pi must be reachable** (Tailscale).

### Download to Device
Same HTTP URL, but with a `download` attribute — the browser saves the MP3 to the local `Downloads` folder. Once saved, playable offline from the file manager with any media player. **Pi needed only at download time.**

Use Download to Device before a demo on a PC where the Pi may not be reachable, or where Tailscale connectivity is uncertain.

---

## Mood field in the Library

`media.mood` is NULL for all tracks until the ML pipeline (issue #7) is complete. The mood filter in the Library UI is built now but will return empty results until tracks are tagged. This is expected — the filter is built in advance of the data.

Valid mood values (after #7): `energetic`, `chill`, `sad`, `intense`.
