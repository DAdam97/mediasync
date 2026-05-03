---
title: Syncthing
type: concept
related: [architecture.md]
updated: 2026-05-01
---

# Syncthing

## What It Is

Syncthing is an open-source, peer-to-peer file synchronisation tool. It automatically keeps folders in sync between devices over the local network (or internet). No cloud server, no account required.

In MediaSync, Syncthing handles the Pi → Android phone file sync. No custom sync code is written.

## Configuration

### Pi Side (Docker service)
- Folder: `/mnt/media/` (the entire media folder)
- Mode: **Send Only** — the Pi never accepts changes from the phone
- Access Syncthing web UI at `http://pi-ip:8384`

### Android Side
- App: **Syncthing-Fork** (from F-Droid or Play Store)
- Folder: `/sdcard/MediaSync/` (or user-chosen path)
- Mode: **Receive Only** — the phone never sends to the Pi
- Sync condition: **WiFi only** (set in Syncthing-Fork settings)
- Poweramp auto-scans this folder for music files

## How Auto-Sync Works

1. A new MP3 is added to `/mnt/media/music/` on the Pi (after download completes)
2. Syncthing on the Pi detects the new file
3. When the phone connects to WiFi and the Pi is reachable (same network or via Tailscale), Syncthing-Fork pulls the file
4. Poweramp detects the new file in its scan folder and adds it to the library

## Docker Compose Setup

```yaml
syncthing:
  image: syncthing/syncthing:latest
  ports:
    - "8384:8384"   # Web UI
    - "22000:22000" # Sync protocol (TCP + UDP)
  volumes:
    - media_data:/mnt/media
    - syncthing_config:/var/syncthing/config
  restart: unless-stopped
```

## Important Notes

- The first-time pairing between Pi and phone must be done manually via the Syncthing web UI (add device by device ID)
- Syncthing does not delete files from the phone if they are deleted on the Pi — this is intentional (receive-only mode protects the phone's library)
- `.m3u` playlist files are in the same synced folder, so Poweramp can open them directly
