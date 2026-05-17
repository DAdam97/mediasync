import struct
import wave
from pathlib import Path


def _write_wav(path: Path, duration_seconds: float, sample_rate: int = 22050) -> None:
    n_samples = int(sample_rate * duration_seconds)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{n_samples}h", *([0] * n_samples)))


def test_extract_features_returns_57_values(tmp_path: Path) -> None:
    wav = tmp_path / "track.wav"
    _write_wav(wav, duration_seconds=90.0)

    from services.feature_extractor import extract_features

    features = extract_features(str(wav))
    assert isinstance(features, list)
    assert len(features) == 57
    assert all(isinstance(v, float) for v in features)


def test_extract_features_is_deterministic(tmp_path: Path) -> None:
    wav = tmp_path / "track.wav"
    _write_wav(wav, duration_seconds=90.0)

    from services.feature_extractor import extract_features

    assert extract_features(str(wav)) == extract_features(str(wav))


def test_extract_features_handles_short_file(tmp_path: Path) -> None:
    wav = tmp_path / "short.wav"
    _write_wav(wav, duration_seconds=10.0)

    from services.feature_extractor import extract_features

    features = extract_features(str(wav))
    assert len(features) == 57
