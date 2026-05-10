---
title: TF Lite — Mood Classification Pipeline
type: concept
related: [architecture.md]
updated: 2026-05-01
---

# TF Lite — Mood Classification Pipeline

## Overview

The ML pipeline classifies each downloaded track into one of four mood categories: `energetic`, `chill`, `sad`, `intense`. It runs entirely on the Raspberry Pi using TF Lite — no cloud inference, no internet required after the model is trained.

## Pipeline Stages

### 1. Dataset Collection & Labeling

Tracks for training come from the existing Pi download pipeline — no separate collection step. The dataset size is flexible (start with whatever is available, expand later).

Labeling workflow (Library UI, "C approach"):
1. Download training tracks via the normal Pi pipeline
2. Open the Library web UI → each track card has a mood dropdown (energetic / chill / sad / intense — expandable)
3. Listen to a few seconds, click the mood → saved via `PATCH /api/library/{id}`
4. Rule: if unsure in 5 seconds, skip — clean examples beat noisy ones
5. Click "Export training CSV" → downloads `dataset_labels.csv` (filename + mood)

### 2. Feature Extraction (on Pi)

Script: `ml/extract_features.py` — run once on the Pi before training.

- Reads `dataset_labels.csv`
- Finds each MP3 in `/mnt/media/music/`
- Extracts the feature vector (same librosa code as production `services/feature_extractor.py`)
- Outputs `dataset.csv`: feature columns + mood label per row

This CSV (~120 rows × 58 columns) is uploaded to Google Drive for Colab. The MP3s never leave the Pi.

### 3. Training (Google Colab)

Location: `ml/mood_classification.ipynb`

- Colab free tier, CPU is sufficient — 120 samples trains in seconds
- No payment needed

Steps:
1. Mount Google Drive, load `dataset.csv`
2. Normalize features (StandardScaler)
3. Train Keras Sequential model (80/20 split)
4. Evaluate accuracy
5. Export to TF Lite

**Model architecture:**
```
Input (feature vector, ~60 values)
→ Dense(128, relu) → Dropout(0.3)
→ Dense(64, relu) → Dropout(0.3)
→ Dense(4, softmax)
```

**Feature vector (per track):**
- MFCC: 20 coefficients × mean + std = 40 values
- Spectral centroid (mean)
- Spectral rolloff (mean)
- Zero crossing rate (mean)
- Chroma mean: 12 values
- Tempo
- Energy (RMS mean)
Total: ~57 features

### 2. Model Export

```python
converter = tf.lite.TFLiteConverter.from_keras_model(model)
tflite_model = converter.convert()
with open("mood_classifier.tflite", "wb") as f:
    f.write(tflite_model)
```

The `.tflite` file is committed to the repo at `backend/models/mood_classifier.tflite`.

### 3. Feature Extraction on Pi (`services/feature_extractor.py`)

Uses `librosa` (not TensorFlow) to extract the same feature vector from the downloaded MP3. Extracts from a 30-second clip starting at 30s into the track (skips intros). Stores the result as a JSON array in the `audio_features` table.

### 4. Inference on Pi (`services/classifier.py`)

Uses `tflite-runtime` (NOT full TensorFlow — too heavy for Pi 4). Loads `mood_classifier.tflite`, runs inference on the feature vector, returns the top mood label and confidence score. Updates the `media` table: `mood` and `mood_confidence` columns.

## Why `tflite-runtime` and not `tensorflow`

Full TensorFlow is ~500 MB and requires significant RAM on import. `tflite-runtime` is ~5 MB and loads in milliseconds. On a Pi 4 with 4 GB RAM, using full TensorFlow for inference is wasteful and slow.

## Mood Categories

| Label | Description | Use case |
|---|---|---|
| `energetic` | High tempo, high energy | Workout, running |
| `chill` | Low tempo, smooth | Study, work, relaxing |
| `sad` | Melancholic, minor key | Quiet evenings |
| `intense` | High energy, aggressive | Focus, motivation |

## Future Extension

### Genre classification (later)
Genre comes from yt-dlp metadata (YouTube Music provides structured genre tags). No second ML model is planned.

For tracks without genre metadata: **KNN genre inference** — find the K nearest neighbors in `audio_features` by cosine similarity, take the majority genre label. Implemented in `services/classifier.py` as a lookup, not a trained model. Requires #8 to be complete (feature vectors must be stored).

Manual override: Library UI mood/genre dropdown + `PATCH /api/library/{id}`. User can correct any tag at any time.
