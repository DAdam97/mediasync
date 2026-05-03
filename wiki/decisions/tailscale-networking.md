---
title: Tailscale for Remote Pi Access
type: decision
related: [architecture.md]
updated: 2026-05-01
---

# Tailscale for Remote Pi Access

## Decision

Tailscale is used to make the Raspberry Pi accessible from anywhere (school, work, other networks) without port forwarding or a VPN server.

## Why Tailscale

- **Free** for personal use (up to 100 devices)
- **Zero config:** install on Pi + install on laptop → both appear on the same virtual network immediately
- **No port forwarding needed:** works through NAT without opening ports on the home router
- **Works anywhere:** school network, mobile hotspot, any network
- **Secure:** WireGuard-based encryption, no traffic goes through a third-party server (peer-to-peer where possible)

## Alternatives Considered

| Option | Why rejected |
|---|---|
| Bring Pi to school | Inconvenient, not always possible |
| ngrok / Cloudflare Tunnel | Adds a public URL — unnecessary complexity for a personal project |
| Home VPN (WireGuard self-hosted) | More setup, needs port forwarding on home router |

## Setup

1. Install Tailscale on Pi: `curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up`
2. Install Tailscale on demo laptop and dev machines
3. Log in with the same account on all devices
4. Pi is reachable at its Tailscale IP (e.g. `100.x.x.x:8000`) or hostname

## Demo Usage

- Pi stays home, connected to home WiFi
- At school: laptop connects to school WiFi, Tailscale handles the routing
- Open browser → `http://pi-tailscale-ip:8000` → web UI works as if on home network
