import json
from pathlib import Path

import numpy as np

from config import models_path

LABEL_MAP = {0: "energetic", 1: "chill", 2: "intense"}


def _infer(x: np.ndarray, model_path: str) -> np.ndarray:
    import tflite_runtime.interpreter as tflite

    interp = tflite.Interpreter(model_path=model_path)
    interp.allocate_tensors()
    inp = interp.get_input_details()
    out = interp.get_output_details()
    interp.set_tensor(inp[0]["index"], x.reshape(1, -1))
    interp.invoke()
    return interp.get_tensor(out[0]["index"])[0]  # type: ignore[no-any-return]


def classify(features: list[float]) -> tuple[str | None, float | None]:
    model_file = Path(models_path()) / "mood_classifier.tflite"
    scaler_file = Path(models_path()) / "scaler_params.json"
    if not model_file.exists() or not scaler_file.exists():
        return None, None

    with open(scaler_file) as f:
        params = json.load(f)
    mean = np.array(params["mean"], dtype=np.float32)
    scale = np.array(params["scale"], dtype=np.float32)
    x = (np.array(features, dtype=np.float32) - mean) / scale

    probs = _infer(x, str(model_file))
    idx = int(np.argmax(probs))
    return LABEL_MAP.get(idx), float(probs[idx])
