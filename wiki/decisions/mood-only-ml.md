---
title: Mood-only ML Classification (no genre)
type: decision
related: [tflite.md]
updated: 2026-05-01
---

# Mood-only ML Classification (no genre)

## Decision

The ML classifier is trained for mood classification only (energetic, chill, sad, intense). Genre classification is explicitly out of scope for the demo.

## Why

- **Timeline:** ~3-4 weeks. Training one model is feasible; training and validating two models is risky given the deadline.
- **Direct utility:** Mood maps directly to the playlist use cases the user actually has (workout → energetic, study → chill, travel → anything). Genre is less actionable.
- **Dataset size:** With ~25-30 tracks per category, mood categories (which differ significantly in tempo, energy, and spectral characteristics) produce better-separated clusters than genre categories (which can overlap heavily in features).
- **Hungarian music coverage:** Genre labels from external sources (GTZAN, Last.fm) have poor coverage for Hungarian music. A custom mood dataset avoids this problem entirely — mood is language-agnostic.

## Mood Categories

| Label | Acoustic characteristics |
|---|---|
| `energetic` | High BPM, high RMS energy, high spectral centroid |
| `chill` | Low BPM, low energy, smooth spectral rolloff |
| `sad` | Slow tempo, minor-key chroma patterns, low energy |
| `intense` | High BPM, high energy, aggressive zero crossing rate |

## Dataset Plan

- 4 categories × ~25-30 tracks = ~100-120 tracks total
- User builds the dataset manually from their own YouTube library
- 30-second clips extracted per track (starting at 30s to skip intros)
- Features extracted with librosa, stored as `.npy` or CSV for Colab training

## Future Extension

Genre classification can be added after the demo by:
1. Building a genre dataset (same process)
2. Training a second Keras model
3. Exporting as `genre_classifier.tflite`
4. Adding `genre` and `genre_confidence` columns to the `media` table (columns already exist in the schema)
5. Running genre inference in `services/classifier.py` alongside mood inference
