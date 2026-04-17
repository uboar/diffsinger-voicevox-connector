"""score_converter のテスト。

g2p (pyopenjtalk) をモンキーパッチで置き換え、pyopenjtalk が無くても動くようにする。
"""

from __future__ import annotations

import pytest

from diffsinger_engine.inference import score_converter
from diffsinger_engine.schemas import Note, Score


@pytest.fixture(autouse=True)
def fake_g2p(monkeypatch: pytest.MonkeyPatch) -> None:
    """pyopenjtalk に依存せずテストするための簡易マッピング。"""
    table: dict[str, list[str]] = {
        "あ": ["a"],
        "い": ["i"],
        "う": ["u"],
        "え": ["e"],
        "お": ["o"],
        "か": ["k", "a"],
        "き": ["k", "i"],
        "ど": ["d", "o"],
        "きゃ": ["ky", "a"],
        "ん": ["N"],
        "っ": ["cl"],
    }

    def fake(text: str) -> list[str]:
        return table.get(text.strip(), [])

    monkeypatch.setattr(score_converter, "hiragana_to_phonemes", fake)


def test_midi_to_note_name() -> None:
    assert score_converter.midi_to_note_name(60) == "C4"
    assert score_converter.midi_to_note_name(69) == "A4"
    assert score_converter.midi_to_note_name(72) == "C5"


def test_rest_note_when_key_is_none() -> None:
    score = Score(notes=[Note(key=None, frame_length=94, lyric="")])
    out = score_converter.score_to_ds_input(score, frame_rate=93.75)
    assert out.ph_seq == ["rest"]
    assert out.note_seq == ["rest"]
    assert len(out.ph_dur) == 1
    assert out.ph_dur[0] == pytest.approx(94 / 93.75, rel=1e-6)


def test_single_vowel_note() -> None:
    # "あ" を 0.5秒ぶん (約47フレーム) 鳴らす
    score = Score(notes=[Note(key=60, frame_length=47, lyric="あ")])
    out = score_converter.score_to_ds_input(score, frame_rate=93.75)
    assert out.ph_seq == ["a"]
    assert out.note_seq == ["C4"]
    assert out.ph_dur[0] == pytest.approx(47 / 93.75, rel=1e-6)
    assert out.is_slur == [0]


def test_consonant_vowel_split() -> None:
    # "か" = ["k","a"] を 0.5秒ぶん。子音 0.05s, 母音 0.45s。
    frame_length = int(round(0.5 * 93.75))  # ≈ 47
    score = Score(notes=[Note(key=62, frame_length=frame_length, lyric="か")])
    out = score_converter.score_to_ds_input(score, frame_rate=93.75)
    assert out.ph_seq == ["k", "a"]
    assert out.note_seq == ["D4", "D4"]
    assert out.ph_dur[0] == pytest.approx(0.05, rel=1e-3)
    note_seconds = frame_length / 93.75
    assert out.ph_dur[1] == pytest.approx(note_seconds - 0.05, rel=1e-3)
    assert sum(out.ph_dur) == pytest.approx(note_seconds, rel=1e-6)


def test_youon_kya() -> None:
    score = Score(notes=[Note(key=64, frame_length=47, lyric="きゃ")])
    out = score_converter.score_to_ds_input(score, frame_rate=93.75)
    assert out.ph_seq == ["ky", "a"]
    assert out.note_seq == ["E4", "E4"]


def test_short_note_drops_consonant() -> None:
    # ノートが極端に短い (子音長 0.05s 未満) なら子音省略
    score = Score(notes=[Note(key=60, frame_length=2, lyric="か")])
    out = score_converter.score_to_ds_input(score, frame_rate=93.75)
    assert out.ph_seq == ["a"]
    assert sum(out.ph_dur) == pytest.approx(2 / 93.75, rel=1e-6)


def test_multiple_notes_concatenate() -> None:
    score = Score(
        notes=[
            Note(key=None, frame_length=10, lyric=""),
            Note(key=60, frame_length=47, lyric="あ"),
            Note(key=62, frame_length=47, lyric="い"),
            Note(key=None, frame_length=10, lyric=""),
        ]
    )
    out = score_converter.score_to_ds_input(score, frame_rate=93.75)
    assert out.ph_seq == ["rest", "a", "i", "rest"]
    assert out.note_seq == ["rest", "C4", "D4", "rest"]
    assert len(out.ph_dur) == 4
    assert len(out.is_slur) == 4


def test_unknown_lyric_falls_back_to_rest(monkeypatch: pytest.MonkeyPatch) -> None:
    # g2p が空を返した場合、rest 扱いにフォールバック
    monkeypatch.setattr(score_converter, "hiragana_to_phonemes", lambda _t: [])
    score = Score(notes=[Note(key=60, frame_length=47, lyric="???")])
    out = score_converter.score_to_ds_input(score)
    assert out.ph_seq == ["rest"]
