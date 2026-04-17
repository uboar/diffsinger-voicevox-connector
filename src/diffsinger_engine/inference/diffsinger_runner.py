"""DiffSinger acoustic ONNX モデルの実行。

dsconfig.yaml から入出力名を読み取り、onnxruntime で推論する。
GPU フォールバック: CUDA → CPU の順に試行。
"""

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
    """onnxruntime セッションを生成。CUDA 失敗時は CPU に自動フォールバック。"""
    import onnxruntime as ort  # type: ignore[import-not-found]

    try:
        return ort.InferenceSession(str(onnx_path), providers=providers)  # type: ignore[return-value]
    except Exception as exc:
        if providers != ["CPUExecutionProvider"]:
            logger.warning(
                "ONNX セッション生成に失敗 (%s)。CPU にフォールバックします: %s",
                providers,
                exc,
            )
            return ort.InferenceSession(  # type: ignore[return-value]
                str(onnx_path),
                providers=["CPUExecutionProvider"],
            )
        raise


class AcousticModel:
    """DiffSinger acoustic.onnx 実行ラッパ。"""

    def __init__(
        self,
        onnx_path: Path,
        dsconfig: dict[str, Any] | None = None,
        providers: list[str] | None = None,
        session: _OnnxSessionLike | None = None,
    ) -> None:
        """
        Args:
            onnx_path: acoustic.onnx へのパス。
            dsconfig: dsconfig.yaml をパースした辞書。入出力名 / hop_size 等を読む。
            providers: onnxruntime providers 優先順。None なら CPU のみ。
            session: テスト用に差し込むモック ONNX セッション。
        """
        self.onnx_path = Path(onnx_path)
        self.dsconfig = dsconfig or {}
        self.providers = providers or ["CPUExecutionProvider"]

        if session is not None:
            self._session: _OnnxSessionLike = session
        else:
            self._session = _create_session(self.onnx_path, self.providers)

        # 入力名の決定。dsconfig に明示があればそれを優先、なければセッションから取得。
        self.input_names: list[str] = self.dsconfig.get("acoustic_input_names") or [
            inp.name for inp in self._session.get_inputs()
        ]
        self.output_names: list[str] = self.dsconfig.get("acoustic_output_names") or [
            out.name for out in self._session.get_outputs()
        ]

    def run(self, linguistic_features: dict[str, np.ndarray]) -> np.ndarray:
        """linguistic features を入力にメルスペクトログラムを返す。

        Args:
            linguistic_features: ONNX 入力名 → numpy 配列 の辞書。
                典型的に tokens / durations / f0 / note_midi 等。

        Returns:
            mel: shape=(T, n_mels) または (1, n_mels, T) の numpy 配列。モデル定義依存。
        """
        feed = {name: linguistic_features[name] for name in self.input_names if name in linguistic_features}
        outputs = self._session.run(self.output_names, feed)
        # 多くの DiffSinger acoustic モデルは出力 1 個 (mel)。
        return outputs[0]
