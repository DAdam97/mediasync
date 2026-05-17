import numpy as np

CLIP_DURATION = 30.0
CLIP_OFFSET = 30.0
N_MFCC = 20
N_CHROMA = 12
FEATURE_COUNT = 57  # 20*2 + 1 + 1 + 1 + 12 + 1 + 1


def extract_features(file_path: str) -> list[float]:
    import librosa

    duration = librosa.get_duration(path=file_path)
    offset = CLIP_OFFSET if duration > CLIP_OFFSET else 0.0

    y, sr = librosa.load(file_path, offset=offset, duration=CLIP_DURATION, mono=True)

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC)
    mfcc_mean = np.mean(mfcc, axis=1).tolist()
    mfcc_std = np.std(mfcc, axis=1).tolist()

    centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr)))
    zcr = float(np.mean(librosa.feature.zero_crossing_rate(y=y)))

    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    chroma_mean = np.mean(chroma, axis=1).tolist()

    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    tempo_val = float(tempo) if np.ndim(tempo) == 0 else float(tempo[0])

    energy = float(np.mean(librosa.feature.rms(y=y)))

    features: list[float] = (
        mfcc_mean
        + mfcc_std
        + [centroid, rolloff, zcr]
        + chroma_mean
        + [tempo_val, energy]
    )
    assert (
        len(features) == FEATURE_COUNT
    ), f"Expected {FEATURE_COUNT}, got {len(features)}"
    return features
