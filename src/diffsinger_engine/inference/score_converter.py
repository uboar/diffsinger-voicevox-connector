"""VOICEVOX Score → DiffSinger 入力 (DSInput) 変換。

VOICEVOX の Note (key=MIDI番号 or None, frame_length=93.75fps基準, lyric=ひらがな1モーラ) を
DiffSinger acoustic モデルへの入力 (ph_seq / ph_dur / note_seq / note_dur / is_slur) に展開する。

フレーム配分ルール:
  - 1モーラ = 子音 0..n + 母音 1。子音は固定 0.05 秒、残りを母音に。
  - ノート長が子音長未満の場合は子音を省略。
  - key=None または lyric が空 → "rest" 音素 1個でノート全長を埋める。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from diffsinger_engine.schemas import Note, Score

from .g2p import hiragana_to_phonemes

logger = logging.getLogger(__name__)


# DiffSinger 日本語モデルの母音集合 (phonemes.txt 互換)。
# 子音判定のための補集合として使う。
_VOWELS: frozenset[str] = frozenset(["a", "i", "u", "e", "o", "N", "cl", "rest"])

DEFAULT_CONSONANT_SECONDS: float = 0.05


@dataclass
class DSInput:
    """DiffSinger acoustic モデルの入力テンソル材料。"""

    ph_seq: list[str] = field(default_factory=list)
    ph_dur: list[float] = field(default_factory=list)  # 秒
    ph_note_indexes: list[int] = field(default_factory=list)
    note_seq: list[str] = field(default_factory=list)  # "C4" / "rest"
    note_dur: list[float] = field(default_factory=list)  # 秒
    is_slur: list[int] = field(default_factory=list)


_NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def midi_to_note_name(midi: int) -> str:
    """MIDI 番号 → 音名 (例: 60 → "C4")。"""
    octave = midi // 12 - 1
    return f"{_NOTE_NAMES[midi % 12]}{octave}"


def _is_vowel(ph: str) -> bool:
    return ph in _VOWELS


def _split_consonant_vowel(
    phonemes: list[str], total_seconds: float, consonant_seconds: float
) -> list[float]:
    """音素列に対して秒単位の長さを割り振る。

    末尾の音素 (母音想定) に残り時間を全部割り当て、子音には固定長を割り振る。
    ノートが短くて子音が入らない場合は呼び出し側で子音を落とすこと。
    """
    if not phonemes:
        return []
    if len(phonemes) == 1:
        return [max(total_seconds, 0.0)]

    consonant_count = len(phonemes) - 1
    consonant_total = consonant_seconds * consonant_count
    if consonant_total >= total_seconds:
        # 子音だけで埋まってしまうケース。母音に最低 1ms 残す。
        vowel_dur = max(total_seconds * 0.5, 1e-3)
        remain = max(total_seconds - vowel_dur, 0.0)
        per_consonant = remain / consonant_count if consonant_count else 0.0
        return [per_consonant] * consonant_count + [vowel_dur]

    vowel_dur = total_seconds - consonant_total
    return [consonant_seconds] * consonant_count + [vowel_dur]


def _expand_note(
    note: Note,
    frame_rate: float,
    consonant_seconds: float,
) -> tuple[list[str], list[float], str, float]:
    """1ノート分の (ph_seq, ph_dur, note_name, note_dur_seconds) を返す。"""
    note_seconds = note.frame_length / frame_rate

    if note.key is None or not note.lyric.strip():
        return ["rest"], [note_seconds], "rest", note_seconds

    note_name = midi_to_note_name(note.key)
    phonemes = hiragana_to_phonemes(note.lyric)
    if not phonemes:
        logger.warning("音素変換が空です: lyric=%r → rest 扱い", note.lyric)
        return ["rest"], [note_seconds], "rest", note_seconds

    # ノートが極端に短く子音が入らないなら最後の母音だけにする。
    if len(phonemes) > 1 and note_seconds < consonant_seconds * (len(phonemes) - 1) + 1e-3:
        phonemes = [phonemes[-1]]

    durations = _split_consonant_vowel(phonemes, note_seconds, consonant_seconds)
    return phonemes, durations, note_name, note_seconds


def score_to_ds_input(
    score: Score,
    frame_rate: float = 93.75,
    consonant_seconds: float = DEFAULT_CONSONANT_SECONDS,
) -> DSInput:
    """VOICEVOX Score を DiffSinger 入力に変換する。

    Args:
        score: VOICEVOX Score (notes 配列)。
        frame_rate: スコアのフレームレート。VOICEVOX は 93.75fps。
        consonant_seconds: 子音音素 1個あたりの固定割り当て秒数。
    """
    out = DSInput()
    for note_index, note in enumerate(score.notes):
        phonemes, durations, note_name, note_seconds = _expand_note(
            note, frame_rate=frame_rate, consonant_seconds=consonant_seconds
        )
        out.ph_seq.extend(phonemes)
        out.ph_dur.extend(durations)
        out.ph_note_indexes.extend([note_index] * len(phonemes))
        # note_seq / note_dur は音素ごとに繰り返し展開する (DiffSinger 標準形式)。
        for _ in phonemes:
            out.note_seq.append(note_name)
            out.note_dur.append(note_seconds)
            out.is_slur.append(0)
    return out
