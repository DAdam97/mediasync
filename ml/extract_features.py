"""
Standalone script — run on Pi after labeling tracks in the Library UI.

Usage:
    python ml/extract_features.py \
        --labels dataset_labels.csv \
        --media-dir /mnt/media/music \
        --output dataset.csv
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from services.feature_extractor import FEATURE_COUNT, extract_features


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", required=True, help="CSV with filename,mood columns")
    parser.add_argument("--media-dir", required=True, help="Directory containing MP3 files")
    parser.add_argument("--output", required=True, help="Output dataset CSV path")
    args = parser.parse_args()

    media_dir = Path(args.media_dir)
    rows: list[dict[str, object]] = []

    with open(args.labels, newline="") as f:
        reader = csv.DictReader(f)
        for record in reader:
            filename = record["filename"]
            mood = record["mood"]
            mp3_path = media_dir / filename

            if not mp3_path.exists():
                print(f"WARNING: {filename} not found in {media_dir} — skipping", file=sys.stderr)
                continue

            try:
                features = extract_features(str(mp3_path))
            except Exception as exc:
                print(f"WARNING: failed to extract features from {filename}: {exc}", file=sys.stderr)
                continue

            row: dict[str, object] = {f"f{i}": v for i, v in enumerate(features)}
            row["mood"] = mood
            rows.append(row)

    if not rows:
        print("ERROR: no rows to write — check that label filenames match files in media-dir", file=sys.stderr)
        sys.exit(1)

    fieldnames = [f"f{i}" for i in range(FEATURE_COUNT)] + ["mood"]
    with open(args.output, "w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Written {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
