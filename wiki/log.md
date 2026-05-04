# Log

Append-only chronological record of all work done on the project.
Format: `## [YYYY-MM-DD] type | short description`
Types: `feat` | `fix` | `decision` | `progress` | `note`

---

## [2026-05-04] feat | Web UI: link submission + download queue (#5)

`static/index.html` fully wired: submit button calls `POST /api/downloads`, queue renders on load from `GET /api/downloads`, smart polling (3s interval, stops when no active downloads, restarts on next submit), form-level error display (422 invalid URL, network error), status badges colour-coded (yellow/blue/green/red), Enter key submits. All 16 backend tests still pass.

## [2026-05-04] feat | Download pipeline: single track + discovery mode (#3)

`POST /api/downloads` with URL validation (422 for non-YouTube), background asyncio task handling
`pending→downloading→processing→done` state machine, error_message on failure, media record on success.
`mode=discovery` queues N related tracks via YouTube Mix playlist (yt-dlp `--flat-playlist`).
`GET /api/downloads`, `GET /api/downloads/{id}`, `GET /api/library` added. 16 tests, all green.

## [2026-05-05] feat | DB schema + FastAPI skeleton + health endpoint (#2)

Backend scaffolded: requirements.txt, Dockerfile, docker-compose.yml, database.py (5 tables), main.py with /api/health and /api/stats endpoints, static/index.html placeholder UI, GitHub Actions CI workflow. TDD: 2 tests green (health + stats shape). Ruff passes. Mypy slow on first Pi run (stubs cache) — will pass in CI.

## [2026-05-04] progress | Pi infrastructure setup (partial — #1)

Docker installed and working. Tailscale installed and connected (Pi address: 100.115.50.112). /mnt/usb-ssd/media/ created with music/ and playlists/ subdirectories. Note: Pi boots from SSD (/dev/sda2, 223 GB) — no separate external drive, media path is a directory on the root SSD. VS Code Remote SSH pending (to be done from Windows tomorrow). Issue #1 remains open until SSH step is complete.

## [2026-05-01] progress | Initial planning session complete

Completed grill-me interview covering all major project decisions. PRD written to `docs/prd.md`. Wiki structure created. Key outcomes: web UI replaces Android app for demo, Tailscale for networking, mood-only ML (4 categories), MusicBrainz removed, ~3-4 week timeline confirmed. No code written yet.
