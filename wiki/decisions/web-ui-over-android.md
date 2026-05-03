---
title: Web UI over Android App (for demo)
type: decision
related: [architecture.md]
updated: 2026-05-01
---

# Web UI over Android App (for demo)

## Decision

The primary client for submitting links and browsing the library is a simple web UI (single `index.html` + vanilla JS), not a custom Android app. The Android app is deferred to after the demo deadline.

## Why

- **Timeline:** Only ~3-4 weeks remain until the demo deadline. Building a working Android app in Kotlin from scratch (with minimal Android experience) would consume most of the available time, leaving the backend incomplete.
- **Demo requirement:** The teacher confirmed that a demo running on a laptop (home Pi + school laptop via Tailscale) is fully acceptable. A custom Android app is not required for the grade.
- **Personal use on Windows:** The web UI also serves as the day-to-day client when on a Windows desktop, which is the developer's primary machine.
- **Simplicity:** A single `index.html` served by FastAPI requires no build step, no framework, no deployment step. It works anywhere the Pi is reachable.

## What Replaces the Android App

- **Link submission:** Web UI from any browser
- **File playback on phone:** Syncthing-Fork (receive-only) + Poweramp — no custom app needed
- **Playlist playback on demo laptop:** VLC opens the generated `.m3u` files

## Android App Status

Not cancelled — deferred. After the demo, the Android app can be built as a Kotlin client that:
- Submits links (share intent receiver)
- Shows download queue and library
- Opens `.m3u` playlists in Poweramp via intent

The backend API is already designed to support the Android app — no backend changes needed when the app is built.
