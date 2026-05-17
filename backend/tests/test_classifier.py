import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest


def _write_scaler(path: Path) -> None:
    (path / "scaler_params.json").write_text(
        json.dumps({"mean": [0.0] * 57, "scale": [1.0] * 57})
    )


def test_classify_returns_energetic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MODELS_PATH", str(tmp_path))
    _write_scaler(tmp_path)
    (tmp_path / "mood_classifier.tflite").write_bytes(b"fake")

    probs = np.array([0.8, 0.1, 0.1], dtype=np.float32)
    with patch("services.classifier._infer", return_value=probs):
        from services import classifier

        mood, confidence = classifier.classify([0.0] * 57)

    assert mood == "energetic"
    assert abs(confidence - 0.8) < 1e-6


def test_classify_missing_model_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MODELS_PATH", str(tmp_path))
    from services import classifier

    mood, confidence = classifier.classify([0.0] * 57)
    assert mood is None
    assert confidence is None


def test_classify_returns_chill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MODELS_PATH", str(tmp_path))
    _write_scaler(tmp_path)
    (tmp_path / "mood_classifier.tflite").write_bytes(b"fake")

    probs = np.array([0.05, 0.9, 0.05], dtype=np.float32)
    with patch("services.classifier._infer", return_value=probs):
        from services import classifier

        mood, confidence = classifier.classify([0.0] * 57)

    assert mood == "chill"
    assert abs(confidence - 0.9) < 1e-6
