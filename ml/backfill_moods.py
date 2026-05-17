"""
Retroactively classify mood for all media records that have mood IS NULL.

Run inside the Docker container:
    docker compose exec api python3 /app/ml/backfill_moods.py

Uses the same logic as _run_inference in services/download_queue.py.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

MEDIA_PATH = os.getenv("MEDIA_PATH", "/mnt/media")
DATABASE_PATH = os.getenv("DATABASE_PATH", "/mnt/media/metadata.db")
MODELS_PATH = os.getenv("MODELS_PATH", "/app/models")

sys.path.insert(0, "/app")

from services.classifier import classify
from services.feature_extractor import extract_features


def main() -> None:
    db = sqlite3.connect(DATABASE_PATH)
    db.row_factory = sqlite3.Row

    rows = db.execute(
        "SELECT id, file_path FROM media WHERE mood IS NULL AND file_path IS NOT NULL"
    ).fetchall()

    print(f"Found {len(rows)} tracks without mood label.")

    ok = 0
    skipped = 0
    errors = 0

    for row in rows:
        media_id: int = row["id"]
        file_path: str = row["file_path"]
        full_path = str(Path(MEDIA_PATH) / file_path)

        if not Path(full_path).exists():
            print(f"  SKIP  #{media_id} — file not found: {full_path}")
            skipped += 1
            continue

        try:
            features = extract_features(full_path)

            db.execute(
                "INSERT OR IGNORE INTO audio_features"
                " (media_id, mfcc_mean, mfcc_std, spectral_centroid, spectral_rolloff,"
                " zero_crossing_rate, chroma_mean, tempo, energy, feature_vector)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    media_id,
                    json.dumps(features[:20]),
                    json.dumps(features[20:40]),
                    features[40],
                    features[41],
                    features[42],
                    json.dumps(features[43:55]),
                    features[55],
                    features[56],
                    json.dumps(features),
                ),
            )

            mood, confidence = classify(features)
            if mood is not None:
                db.execute(
                    "UPDATE media SET mood=?, mood_confidence=? WHERE id=?",
                    (mood, confidence, media_id),
                )
                db.commit()
                print(f"  OK    #{media_id} → {mood} ({confidence:.2f}) | {file_path}")
                ok += 1
            else:
                print(f"  SKIP  #{media_id} — model returned None (model missing?)")
                skipped += 1

        except Exception as e:
            print(f"  ERROR #{media_id} — {e}")
            errors += 1

    db.close()
    print(f"\nDone: {ok} labeled, {skipped} skipped, {errors} errors.")


if __name__ == "__main__":
    main()
