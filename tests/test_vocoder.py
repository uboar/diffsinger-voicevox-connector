"""Vocoder ラッパーのテスト。"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from diffsinger_engine.inference.vocoder import Vocoder


class _SessionStub:
    def __init__(self) -> None:
        self.last_feed: dict[str, np.ndarray] | None = None

    def get_inputs(self):  # type: ignore[no-untyped-def]
        return [
            type("Input", (), {"name": "mel"})(),
            type("Input", (), {"name": "f0"})(),
        ]

    def get_outputs(self):  # type: ignore[no-untyped-def]
        return [type("Output", (), {"name": "waveform"})()]

    def run(self, _output_names, input_feed):  # type: ignore[no-untyped-def]
        self.last_feed = input_feed
        return [np.zeros((1, 8), dtype=np.float32)]


def test_vocoder_adds_batch_dimensions_for_1d_f0() -> None:
    session = _SessionStub()
    vocoder = Vocoder(Path("dummy.onnx"), session=session)

    waveform = vocoder.run(
        np.zeros((16, 128), dtype=np.float32),
        np.zeros(16, dtype=np.float32),
    )

    assert session.last_feed is not None
    assert session.last_feed["mel"].shape == (1, 16, 128)
    assert session.last_feed["f0"].shape == (1, 16)
    assert waveform.shape == (8,)
