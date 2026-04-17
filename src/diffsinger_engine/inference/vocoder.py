"""NSF-HiFiGAN ボコーダー ONNX 実行。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

import numpy as np

logger = logging.getLogger(__name__)


class _OnnxSessionLike(Protocol):
    def run(self, output_names: list[str] | None, input_feed: dict[str, Any]) -> list[np.ndarray]:
        ...

    def get_inputs(self) -> list[Any]: ...

    def get_outputs(self) -> list[Any]: ...


def _create_session(
    onnx_path: Path,
    providers: list[str],
) -> _OnnxSessionLike:
    import onnxruntime as ort  # type: ignore[import-not-found]

    try:
        return ort.InferenceSession(str(onnx_path), providers=providers)  # type: ignore[return-value]
    except Exception as exc:
        if providers != ["CPUExecutionProvider"]:
            logger.warning(
                "Vocoder ONNX セッション生成に失敗 (%s)。CPU にフォールバック: %s",
                providers,
                exc,
            )
            return ort.InferenceSession(  # type: ignore[return-value]
                str(onnx_path),
                providers=["CPUExecutionProvider"],
            )
        raise


class Vocoder:
    """NSF-HiFiGAN vocoder.onnx 実行ラッパ。"""

    def __init__(
        self,
        onnx_path: Path,
        providers: list[str] | None = None,
        sample_rate: int = 44100,
        session: _OnnxSessionLike | None = None,
    ) -> None:
        self.onnx_path = Path(onnx_path)
        self.providers = providers or ["CPUExecutionProvider"]
        self.sample_rate = sample_rate

        if session is not None:
            self._session: _OnnxSessionLike = session
        else:
            self._session = _create_session(self.onnx_path, self.providers)

        self.input_names: list[str] = [inp.name for inp in self._session.get_inputs()]
        self.output_names: list[str] = [out.name for out in self._session.get_outputs()]

    def run(self, mel: np.ndarray, f0: np.ndarray) -> np.ndarray:
        """mel + f0 → 波形 (44.1kHz mono float32)。"""
        feed: dict[str, np.ndarray] = {}
        # NSF-HiFiGAN の典型的な入力名: "mel" / "f0"。順不同で詰める。
        for name in self.input_names:
            lower = name.lower()
            if "mel" in lower:
                feed[name] = mel
            elif "f0" in lower or "pitch" in lower:
                feed[name] = f0
        if len(feed) != len(self.input_names):
            # フォールバック: 順番で詰める。
            tensors = [mel, f0]
            for name, tensor in zip(self.input_names, tensors, strict=False):
                feed.setdefault(name, tensor)

        outputs = self._session.run(self.output_names, feed)
        waveform = outputs[0]
        return np.asarray(waveform, dtype=np.float32).reshape(-1)
