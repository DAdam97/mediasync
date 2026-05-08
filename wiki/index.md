# Wiki Index

All pages in the MediaSync wiki. Read this file first at the start of every session.

## Process

| Page | Summary |
|---|---|
| [Implementation Guidelines](implementation-guidelines.md) | Definition of Done, recurring gotchas, manual test checklist — read every session |

## Concepts

| Page | Summary |
|---|---|
| [Architecture](concepts/architecture.md) | System overview: Pi backend, web UI, Syncthing, Tailscale, Poweramp |
| [yt-dlp](concepts/yt-dlp.md) | How yt-dlp is used, Deno requirement, known limitations |
| [TF Lite](concepts/tflite.md) | Mood classification ML pipeline: Colab training → TF Lite → Pi inference |
| [Syncthing](concepts/syncthing.md) | File sync setup: Pi send-only, phone receive-only, WiFi-only |

## Decisions

| Page | Summary |
|---|---|
| [Web UI over Android](decisions/web-ui-over-android.md) | Why a simple web UI replaces the Android app for the demo |
| [Tailscale Networking](decisions/tailscale-networking.md) | Why Tailscale was chosen for remote Pi access |
| [Mood-only ML](decisions/mood-only-ml.md) | Why we start with mood classification only, not genre |

## Progress

| Page | Summary |
|---|---|
| [Planning Phase](progress/planning.md) | Decisions made in the initial grill-me + PRD session |
| [Issues](progress/issues.md) | All GitHub issues with status and dependencies |
| [Manual Test Plan](progress/manual-test-plan.md) | Full step-by-step manual test plan for issues #2–#5 |
