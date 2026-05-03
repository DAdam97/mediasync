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

### 1. Training (Google Colab)

Location: `ml/mood_classification.ipynb`

Steps:
1. Load custom dataset: ~25-30 tracks per mood category (~100-120 tracks total)
2. Extract features from a 30-second clip per track using librosa
3. Train a Keras Sequential model
4. Export to TF Lite

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

Genre classification can be added later using the same pipeline: train a second model, export as `genre_classifier.tflite`, add a `genre` column to the `media` table, run inference alongside mood.
