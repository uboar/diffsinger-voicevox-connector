"""波形のリサンプリング・WAV エンコーディング。"""

from __future__ import annotations

import io
import logging

import numpy as np

logger = logging.getLogger(__name__)


def to_wav_bytes(waveform: np.ndarray, src_sr: int, target_sr: int) -> bytes:
    """波形を 16-bit PCM mono WAV bytes にエンコードする。

    Args:
        waveform: float32 の 1次元配列 (-1.0〜+1.0)。
        src_sr: waveform のサンプリングレート。
        target_sr: 出力サンプリングレート。src_sr と異なる場合のみリサンプリング。

    Returns:
        WAV ヘッダ付きバイナリ。
    """
    audio = np.asarray(waveform, dtype=np.float32).reshape(-1)

    if src_sr != target_sr:
        import librosa  # type: ignore[import-not-found]

        audio = librosa.resample(audio, orig_sr=src_sr, target_sr=target_sr)

    import soundfile as sf  # type: ignore[import-not-found]

    buf = io.BytesIO()
    sf.write(buf, audio, target_sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()
