---
title: GitHub Issues — All Slices
type: progress
related: [planning.md]
updated: 2026-05-04
---

# GitHub Issues

All vertical slices for the MediaSync project. Tracked at: https://github.com/DAdam97/mediasync/issues

Update the Status column and `updated` date whenever an issue is closed.

## Issue Map

| # | Title | Type | Status | Blocked by |
|---|---|---|---|---|
| [#1](https://github.com/DAdam97/mediasync/issues/1) | Pi infrastructure setup | HITL | open | — |
| [#2](https://github.com/DAdam97/mediasync/issues/2) | Database schema + FastAPI skeleton + health endpoint | AFK | open | #1 |
| [#3](https://github.com/DAdam97/mediasync/issues/3) | Download pipeline: single track (yt-dlp → MP3 → ID3 tags → DB) | AFK | open | #2 |
| [#4](https://github.com/DAdam97/mediasync/issues/4) | Download pipeline: YouTube playlist URL expansion | AFK | open | #3 |
| [#5](https://github.com/DAdam97/mediasync/issues/5) | Web UI: link submission + download queue view | AFK | open | #3 |
| [#6](https://github.com/DAdam97/mediasync/issues/6) | Library API + web UI: browse, filter by mood, search, delete | AFK | open | #3 |
| [#7](https://github.com/DAdam97/mediasync/issues/7) | ML pipeline: dataset collection + Colab training + TF Lite deployment | HITL | open | #3 |
| [#8](https://github.com/DAdam97/mediasync/issues/8) | Mood classifier inference on Pi (async, post-download) | AFK | open | #7 |
| [#9](https://github.com/DAdam97/mediasync/issues/9) | Playlist generation: mood-based .m3u files + API | AFK | open | #8 |
| [#10](https://github.com/DAdam97/mediasync/issues/10) | Web UI: playlist manager + server stats view | AFK | open | #9 |
| [#11](https://github.com/DAdam97/mediasync/issues/11) | Syncthing setup: Pi send-only + phone receive-only WiFi sync | HITL | open | #1 |

## Dependency Graph

```
#1 Pi infrastructure (HITL)
├── #2 DB + FastAPI skeleton
│   └── #3 Download pipeline (single track)
│       ├── #4 Playlist URL expansion
│       ├── #5 Web UI: submit + queue
│       ├── #6 Library API + web UI
│       └── #7 ML pipeline (HITL: dataset + Colab)
│           └── #8 Mood inference on Pi
│               └── #9 Playlist generation
│                   └── #10 Web UI: playlists + stats
└── #11 Syncthing setup (HITL)
```

## How to Update This File

When an issue is closed:
1. Change its Status from `open` to `done`
2. Update the `updated` date in the frontmatter
3. Add a log entry in `wiki/log.md`
