"""pitch_predictor のテスト。"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from diffsinger_engine.inference.pitch_predictor import PitchPredictor
from diffsinger_engine.inference.score_converter import score_to_ds_input
from diffsinger_engine.schemas import Note, Score


class _FakeSession:
    def __init__(self, inputs: list[str], outputs: list[str], result_factory) -> None:  # type: ignore[no-untyped-def]
        self._inputs = [type("Input", (), {"name": name})() for name in inputs]
        self._outputs = [type("Output", (), {"name": name})() for name in outputs]
        self.result_factory = result_factory

    def get_inputs(self):  # type: ignore[no-untyped-def]
        return self._inputs

    def get_outputs(self):  # type: ignore[no-untyped-def]
        return self._outputs

    def run(self, output_names, input_feed):  # type: ignore[no-untyped-def]
        return self.result_factory(output_names, input_feed)


def _write_predictor_files(root: Path) -> None:
    (root / "phonemes.txt").write_text("SP\na\n", encoding="utf-8")
    (root / "dsdict.yaml").write_text(
        "symbols:\n  - symbol: a\n    type: vowel\n",
        encoding="utf-8",
    )


def test_pitch_predictor_generates_expressive_curve_and_masks_rests(tmp_path: Path) -> None:
    _write_predictor_files(tmp_path)
    dsconfig = {
        "linguistic": "linguistic.onnx",
        "pitch": "pitch.onnx",
        "phonemes": "phonemes.txt",
        "predict_dur": True,
        "sample_rate": 44100,
        "hop_size": 512,
    }

    linguistic = _FakeSession(
        inputs=["tokens", "word_div", "word_dur"],
        outputs=["encoder_out"],
        result_factory=lambda _outputs, input_feed: [
            np.zeros((1, input_feed["tokens"].shape[1], 4), dtype=np.float32)
        ],
    )
    pitch = _FakeSession(
        inputs=["encoder_out", "note_midi", "note_dur", "ph_dur", "pitch", "retake", "speedup"],
        outputs=["pitch"],
        result_factory=lambda _outputs, input_feed: [
            np.linspace(60.0, 61.0, input_feed["pitch"].shape[1], dtype=np.float32)[None, :]
        ],
    )
    predictor = PitchPredictor(
        tmp_path,
        dsconfig=dsconfig,
        linguistic_session=linguistic,
        pitch_session=pitch,
    )

    score = Score(
        notes=[
            Note(key=None, frame_length=10, lyric=""),
            Note(key=60, frame_length=24, lyric="あ"),
            Note(key=None, frame_length=10, lyric=""),
        ]
    )
    ds_input = score_to_ds_input(score)

    f0 = predictor.predict_f0(score, ds_input)

    assert len(f0) > 0
    middle = [value for value in f0 if value > 0]
    assert middle
    assert middle[0] < middle[-1]
    assert any(value == 0.0 for value in f0[: max(1, len(f0) // 4)])
    assert any(value == 0.0 for value in f0[-max(1, len(f0) // 4) :])
