"""DiffSinger pitch.onnx を使った F0 予測。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import yaml

from diffsinger_engine.schemas import Score

from .frame_query import VOICEVOX_FRAME_RATE
from .score_converter import DSInput

logger = logging.getLogger(__name__)

HEAD_FRAMES = 8
TAIL_FRAMES = 8
DEFAULT_PITCH_STEPS = 10
_FALLBACK_VOWELS: frozenset[str] = frozenset({"a", "i", "u", "e", "o", "N"})
_PHONEME_ALIAS_TO_MODEL: dict[str, str] = {
    "rest": "SP",
    "pau": "SP",
    "sil": "SP",
    "sp": "SP",
    "ap": "AP",
}


class _OnnxSessionLike(Protocol):
    def run(self, output_names: list[str] | None, input_feed: dict[str, Any]) -> list[np.ndarray]:
        ...

    def get_inputs(self) -> list[Any]:
        ...

    def get_outputs(self) -> list[Any]:
        ...


def _create_session(onnx_path: Path, providers: list[str]) -> _OnnxSessionLike:
    import onnxruntime as ort  # type: ignore[import-not-found]

    try:
        return ort.InferenceSession(str(onnx_path), providers=providers)  # type: ignore[return-value]
    except Exception as exc:
        if providers != ["CPUExecutionProvider"]:
            logger.warning(
                "Pitch predictor ONNX セッション生成に失敗 (%s)。CPU にフォールバックします: %s",
                providers,
                exc,
            )
            return ort.InferenceSession(  # type: ignore[return-value]
                str(onnx_path),
                providers=["CPUExecutionProvider"],
            )
        raise


def _resolve_relative_path(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise FileNotFoundError(f"必須設定が空です: {root}")
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path


def _load_phoneme_inventory(path: Path) -> dict[str, int]:
    phonemes = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    mapping = {symbol: index for index, symbol in enumerate(phonemes) if symbol}
    if "SP" in mapping:
        for alias in ("rest", "pau", "sil", "sp"):
            mapping.setdefault(alias, mapping["SP"])
    if "AP" in mapping:
        mapping.setdefault("ap", mapping["AP"])
    return mapping


def _load_vowels(dsdict_path: Path | None) -> frozenset[str]:
    if dsdict_path is None or not dsdict_path.is_file():
        return _FALLBACK_VOWELS

    data = yaml.safe_load(dsdict_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return _FALLBACK_VOWELS

    vowels = {
        str(symbol.get("symbol"))
        for symbol in data.get("symbols", [])
        if isinstance(symbol, dict) and symbol.get("type") == "vowel" and symbol.get("symbol")
    }
    return frozenset(vowels or _FALLBACK_VOWELS)


def _seconds_to_model_frames(seconds: list[float], frame_rate: float) -> list[int]:
    if not seconds:
        return []
    cumulative = np.rint(np.cumsum(np.asarray(seconds, dtype=np.float64)) * frame_rate).astype(np.int64)
    frames = np.diff(np.concatenate(([0], cumulative))).astype(np.int64)
    return np.maximum(frames, 0).tolist()


def _voicevox_notes_to_seconds(score: Score) -> list[float]:
    return [note.frame_length / VOICEVOX_FRAME_RATE for note in score.notes]


def _speedup_from_steps(steps: int) -> int:
    speedup = max(1, 1000 // max(steps, 1))
    while 1000 % speedup != 0 and speedup > 1:
        speedup -= 1
    return speedup


def _midi_to_hz(midi: np.ndarray) -> np.ndarray:
    return 440.0 * np.power(2.0, (midi - 69.0) / 12.0)


class PitchPredictor:
    def __init__(
        self,
        root: Path,
        dsconfig: dict[str, Any] | None = None,
        providers: list[str] | None = None,
        linguistic_session: _OnnxSessionLike | None = None,
        pitch_session: _OnnxSessionLike | None = None,
    ) -> None:
        self.root = Path(root)
        self.dsconfig = dsconfig or self._load_yaml(self.root / "dsconfig.yaml")
        self.providers = providers or ["CPUExecutionProvider"]

        self.linguistic_path = _resolve_relative_path(self.root, self.dsconfig.get("linguistic"))
        self.pitch_path = _resolve_relative_path(self.root, self.dsconfig.get("pitch"))
        phonemes_path = _resolve_relative_path(
            self.root,
            self.dsconfig.get("phonemes") or "phonemes.txt",
        )

        self.phoneme_to_id = _load_phoneme_inventory(phonemes_path)
        self.vowels = _load_vowels((self.root / "dsdict.yaml") if (self.root / "dsdict.yaml").is_file() else None)
        self.frame_rate = float(self.dsconfig.get("sample_rate") or 44100) / float(
            self.dsconfig.get("hop_size") or 512
        )

        self._linguistic_session = linguistic_session or _create_session(
            self.linguistic_path,
            self.providers,
        )
        self._pitch_session = pitch_session or _create_session(self.pitch_path, self.providers)
        self._linguistic_input_names = [inp.name for inp in self._linguistic_session.get_inputs()]
        self._linguistic_output_names = [out.name for out in self._linguistic_session.get_outputs()]
        self._pitch_input_names = [inp.name for inp in self._pitch_session.get_inputs()]
        self._pitch_output_names = [out.name for out in self._pitch_session.get_outputs()]

    def predict_f0(self, score: Score, ds_input: DSInput) -> list[float]:
        if not score.notes or not ds_input.ph_seq or not ds_input.ph_dur:
            return []

        ph_dur = _seconds_to_model_frames(ds_input.ph_dur, self.frame_rate)
        note_dur = self._build_note_dur(score, sum(ph_dur) + HEAD_FRAMES + TAIL_FRAMES)
        tokens = [self._tokenize_phoneme("SP"), *[self._tokenize_phoneme(ph) for ph in ds_input.ph_seq], self._tokenize_phoneme("SP")]
        ph_dur_with_padding = [HEAD_FRAMES, *ph_dur, TAIL_FRAMES]
        total_frames = sum(ph_dur_with_padding)

        linguistic_inputs = {
            "tokens": np.asarray([tokens], dtype=np.int64),
            "ph_dur": np.asarray([ph_dur_with_padding], dtype=np.int64),
        }
        if bool(self.dsconfig.get("predict_dur", False)):
            word_div, word_dur = self._build_word_dur(ds_input, ph_dur)
            linguistic_inputs["word_div"] = np.asarray([word_div], dtype=np.int64)
            linguistic_inputs["word_dur"] = np.asarray([word_dur], dtype=np.int64)

        linguistic_outputs = self._run_session(
            self._linguistic_session,
            self._linguistic_input_names,
            self._linguistic_output_names,
            linguistic_inputs,
        )
        encoder_out = linguistic_outputs.get("encoder_out")
        if encoder_out is None:
            encoder_out = next(iter(linguistic_outputs.values()), None)
        if encoder_out is None:
            raise RuntimeError("linguistic.onnx の encoder_out を取得できませんでした。")

        note_rest = self._build_note_rest(score, ds_input)
        note_midi = self._build_note_midi(score, note_rest)
        pitch_inputs = {
            "encoder_out": np.asarray(encoder_out, dtype=np.float32),
            "note_midi": np.asarray([note_midi], dtype=np.float32),
            "note_dur": np.asarray([note_dur], dtype=np.int64),
            "ph_dur": np.asarray([ph_dur_with_padding], dtype=np.int64),
            "pitch": np.full((1, total_frames), 60.0, dtype=np.float32),
            "retake": np.ones((1, total_frames), dtype=np.bool_),
            "speedup": np.asarray([_speedup_from_steps(DEFAULT_PITCH_STEPS)], dtype=np.int64),
            "steps": np.asarray([DEFAULT_PITCH_STEPS], dtype=np.int64),
            "expr": np.ones((1, total_frames), dtype=np.float32),
            "note_rest": np.asarray([note_rest], dtype=np.bool_),
        }
        pitch_outputs = self._run_session(
            self._pitch_session,
            self._pitch_input_names,
            self._pitch_output_names,
            pitch_inputs,
        )
        pitch_curve = np.asarray(next(iter(pitch_outputs.values())), dtype=np.float32).reshape(-1)
        if pitch_curve.size < HEAD_FRAMES + TAIL_FRAMES:
            raise RuntimeError("pitch.onnx の出力フレーム数が不足しています。")

        pitch_curve = pitch_curve[HEAD_FRAMES : pitch_curve.size - TAIL_FRAMES]
        hz = _midi_to_hz(pitch_curve.astype(np.float64)).astype(np.float32)
        self._mask_rest_frames(hz, ds_input.ph_seq, ph_dur)
        return hz.tolist()

    def _build_note_dur(self, score: Score, total_frames: int) -> list[int]:
        target_frames = max(total_frames - HEAD_FRAMES - TAIL_FRAMES, 0)
        note_seconds = np.asarray(_voicevox_notes_to_seconds(score), dtype=np.float64)
        if note_seconds.size == 0:
            return [total_frames]

        total_seconds = float(note_seconds.sum())
        if total_seconds <= 0:
            note_frames = [0] * len(score.notes)
        else:
            cumulative = np.rint(np.cumsum(note_seconds) / total_seconds * target_frames).astype(np.int64)
            note_frames = np.diff(np.concatenate(([0], cumulative))).astype(np.int64).tolist()

        note_dur = [HEAD_FRAMES, *note_frames]
        note_dur[-1] += TAIL_FRAMES
        return note_dur

    def _build_word_dur(self, ds_input: DSInput, ph_dur: list[int]) -> tuple[list[int], list[int]]:
        vowel_ids = [index for index, phoneme in enumerate(ds_input.ph_seq) if self._is_vowel(phoneme)]
        if not vowel_ids:
            vowel_ids = [len(ds_input.ph_seq) - 1]

        word_div = [
            vowel_ids[0] + 1,
            *[right - left for left, right in zip(vowel_ids, vowel_ids[1:], strict=False)],
            len(ds_input.ph_seq) - vowel_ids[-1] + 1,
        ]
        word_dur = [
            sum(ph_dur[: vowel_ids[0] + 1]) + HEAD_FRAMES,
            *[
                sum(ph_dur[left:right])
                for left, right in zip(vowel_ids, vowel_ids[1:], strict=False)
            ],
            sum(ph_dur[vowel_ids[-1] :]) + TAIL_FRAMES,
        ]
        return word_div, word_dur

    def _build_note_rest(self, score: Score, ds_input: DSInput) -> list[bool]:
        phonemes_by_note: list[list[str]] = [[] for _ in score.notes]
        for phoneme, note_index in zip(ds_input.ph_seq, ds_input.ph_note_indexes, strict=True):
            if 0 <= note_index < len(phonemes_by_note):
                phonemes_by_note[note_index].append(phoneme)

        note_rest = [True]
        for note, phonemes in zip(score.notes, phonemes_by_note, strict=True):
            is_rest = note.key is None or not phonemes or all(
                self._is_pause_like(phoneme) or not self._is_vowel(phoneme) for phoneme in phonemes
            )
            note_rest.append(is_rest)
        return note_rest

    def _build_note_midi(self, score: Score, note_rest: list[bool]) -> list[float]:
        note_midi = [float(score.notes[0].key or 0), *[float(note.key or 0) for note in score.notes]]
        rest_groups: list[tuple[int, int]] = []
        index = 0
        while index < len(note_rest):
            if not note_rest[index]:
                index += 1
                continue
            end = index + 1
            while end < len(note_rest) and note_rest[end]:
                end += 1
            rest_groups.append((index, end))
            index = end

        for start, end in rest_groups:
            if start == 0 and end == len(note_rest):
                break
            if start == 0:
                fill = note_midi[end]
                for idx in range(0, end):
                    note_midi[idx] = fill
                continue
            if end == len(note_rest):
                fill = note_midi[start - 1]
                for idx in range(start, end):
                    note_midi[idx] = fill
                continue

            midpoint = (start + end + 1) // 2
            left_fill = note_midi[start - 1]
            right_fill = note_midi[end]
            for idx in range(start, midpoint):
                note_midi[idx] = left_fill
            for idx in range(midpoint, end):
                note_midi[idx] = right_fill

        return note_midi

    def _mask_rest_frames(self, f0: np.ndarray, phonemes: list[str], ph_dur: list[int]) -> None:
        cursor = 0
        for phoneme, duration in zip(phonemes, ph_dur, strict=True):
            end = min(cursor + duration, f0.size)
            if self._is_pause_like(phoneme):
                f0[cursor:end] = 0.0
            cursor = end

    def _tokenize_phoneme(self, phoneme: str) -> int:
        candidates = [
            phoneme,
            _PHONEME_ALIAS_TO_MODEL.get(phoneme, phoneme),
            phoneme.lower(),
            phoneme.upper(),
        ]
        for candidate in candidates:
            if candidate in self.phoneme_to_id:
                return self.phoneme_to_id[candidate]
        raise KeyError(f"音素 {phoneme!r} を pitch predictor の語彙へ変換できませんでした。")

    def _is_vowel(self, phoneme: str) -> bool:
        normalized = _PHONEME_ALIAS_TO_MODEL.get(phoneme, phoneme)
        return normalized in self.vowels

    def _is_pause_like(self, phoneme: str) -> bool:
        normalized = _PHONEME_ALIAS_TO_MODEL.get(phoneme, phoneme)
        return normalized in {"SP", "AP"}

    def _run_session(
        self,
        session: _OnnxSessionLike,
        input_names: list[str],
        output_names: list[str],
        candidates: dict[str, np.ndarray],
    ) -> dict[str, np.ndarray]:
        feed = {name: value for name, value in candidates.items() if name in input_names}
        missing = [name for name in input_names if name not in feed]
        if missing:
            raise RuntimeError(f"未対応の pitch predictor 入力があります: {', '.join(missing)}")
        outputs = session.run(output_names, feed)
        return {name: value for name, value in zip(output_names, outputs, strict=True)}

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"YAML ルートが mapping ではありません: {path}")
        return loaded


__all__ = ["PitchPredictor"]
