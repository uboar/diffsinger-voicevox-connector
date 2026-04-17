"""FrameAudioQuery 構築。

DSInput と (任意の) F0 / volume から、VOICEVOX エディタへ返す
FrameAudioQuery (フレームレート 93.75fps) を構築する。
"""

from __future__ import annotations

import logging

from diffsinger_engine.schemas import FrameAudioQuery, FramePhoneme, Score

from .score_converter import DSInput

logger = logging.getLogger(__name__)


VOICEVOX_FRAME_RATE: float = 93.75


def _midi_to_hz(midi: int) -> float:
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def _seconds_to_frames(seconds: float, frame_rate: float = VOICEVOX_FRAME_RATE) -> int:
    return max(int(round(seconds * frame_rate)), 0)


def _build_frame_phonemes(ds_input: DSInput) -> list[FramePhoneme]:
    """DSInput.ph_seq / ph_dur をフレーム数付き FramePhoneme 列に変換。"""
    out: list[FramePhoneme] = []
    for phoneme, dur_sec in zip(ds_input.ph_seq, ds_input.ph_dur, strict=True):
        out.append(
            FramePhoneme(
                phoneme=phoneme,
                frame_length=_seconds_to_frames(dur_sec),
            )
        )
    return out


def _rule_based_f0(score: Score) -> list[float]:
    """Score の各ノートを key→Hz 変換し、frame_length 個ぶん並べた F0 列。"""
    f0: list[float] = []
    for note in score.notes:
        hz = 0.0 if note.key is None else _midi_to_hz(note.key)
        f0.extend([hz] * note.frame_length)
    return f0


def _rule_based_volume(score: Score, level: float = 1.0) -> list[float]:
    total = sum(n.frame_length for n in score.notes)
    return [level] * total


def build_frame_query(
    score: Score,
    ds_input: DSInput,
    f0: list[float] | None = None,
    volume: list[float] | None = None,
    output_sr: int = 44100,
) -> FrameAudioQuery:
    """FrameAudioQuery を構築する。

    Args:
        score: 元の Score (F0/volume の規則ベース算出に必要)。
        ds_input: score_to_ds_input の出力。
        f0: フレーム単位 F0 (Hz)。None の場合は規則ベース (key→Hz)。
        volume: フレーム単位 volume。None の場合は一定値 1.0。
        output_sr: 出力サンプリングレート (FrameAudioQuery.outputSamplingRate)。

    Returns:
        VOICEVOX 互換 FrameAudioQuery。
    """
    phonemes = _build_frame_phonemes(ds_input)
    total_frames = sum(p.frame_length for p in phonemes)

    if f0 is None:
        f0 = _rule_based_f0(score)
    if volume is None:
        volume = _rule_based_volume(score)

    # phonemes フレーム合計と F0/volume 長さの整合性を取る (短い方に合わせる)。
    if len(f0) != total_frames or len(volume) != total_frames:
        logger.debug(
            "フレーム数不整合 (phonemes=%d, f0=%d, volume=%d) → 整列します",
            total_frames,
            len(f0),
            len(volume),
        )
        f0 = _resize_to(f0, total_frames, fill=0.0)
        volume = _resize_to(volume, total_frames, fill=0.0)

    return FrameAudioQuery(
        f0=f0,
        volume=volume,
        phonemes=phonemes,
        outputSamplingRate=output_sr,
    )


def _resize_to(seq: list[float], length: int, fill: float) -> list[float]:
    if len(seq) == length:
        return seq
    if len(seq) > length:
        return seq[:length]
    return list(seq) + [fill] * (length - len(seq))


# 公開: 他モジュールから使えるユーティリティ
midi_to_hz = _midi_to_hz
seconds_to_frames = _seconds_to_frames
__all__ = [
    "VOICEVOX_FRAME_RATE",
    "build_frame_query",
    "midi_to_hz",
    "seconds_to_frames",
]
