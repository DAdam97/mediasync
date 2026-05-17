"""
Smoke test — verify mood_classifier.tflite loads and runs on this device.

Usage:
    python ml/smoke_test.py
"""

import sys
from pathlib import Path

MODEL_PATH = Path(__file__).parent.parent / "backend" / "models" / "mood_classifier.tflite"
LABELS = ["energetic", "chill", "sad", "intense"]
FEATURE_COUNT = 57


def main() -> int:
    if not MODEL_PATH.exists():
        print(f"ERROR: model not found at {MODEL_PATH}", file=sys.stderr)
        return 1

    try:
        import numpy as np
        import tflite_runtime.interpreter as tflite
    except ImportError as exc:
        print(f"ERROR: missing dependency — {exc}", file=sys.stderr)
        return 1

    interpreter = tflite.Interpreter(model_path=str(MODEL_PATH))
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    dummy_input = np.zeros((1, FEATURE_COUNT), dtype=np.float32)
    interpreter.set_tensor(input_details[0]["index"], dummy_input)
    interpreter.invoke()

    output = interpreter.get_tensor(output_details[0]["index"])[0]
    predicted_idx = int(np.argmax(output))
    confidence = float(output[predicted_idx])

    print(f"Mood: {LABELS[predicted_idx]} (confidence: {confidence:.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
