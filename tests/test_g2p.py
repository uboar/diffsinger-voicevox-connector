"""g2p モジュールのテスト。

pyopenjtalk が無い環境では importorskip でスキップ。
ある環境では代表的なひらがな/カタカナの音素分解を検証する。
"""

from __future__ import annotations

import pytest

from diffsinger_engine.inference import g2p


def test_empty_input_returns_empty_list() -> None:
    assert g2p.hiragana_to_phonemes("") == []
    assert g2p.hiragana_to_phonemes("   ") == []


def test_standalone_n() -> None:
    """単独の "ん" は pyopenjtalk を経由せず即時に返るべき。"""
    assert g2p.hiragana_to_phonemes("ん") == ["N"]
    assert g2p.hiragana_to_phonemes("ン") == ["N"]


def test_standalone_sokuon() -> None:
    assert g2p.hiragana_to_phonemes("っ") == ["cl"]
    assert g2p.hiragana_to_phonemes("ッ") == ["cl"]


def test_extract_phonemes_from_fullcontext_strips_silence() -> None:
    labels = [
        "xx^xx-sil+a=k/A:...",
        "xx^sil-a+k=a/A:...",
        "xx^a-k+a=sil/A:...",
        "xx^k-a+sil=xx/A:...",
        "xx^a-sil+xx=xx/A:...",
    ]
    phonemes = g2p._extract_phonemes_from_fullcontext(labels)
    # sil/pau は rest に正規化されているはず
    assert "rest" in phonemes
    stripped = g2p._strip_silence(phonemes)
    assert stripped == ["a", "k", "a"]


def test_normalize_phoneme_uppercase_vowels() -> None:
    assert g2p._normalize_phoneme("A") == "a"
    assert g2p._normalize_phoneme("I") == "i"
    assert g2p._normalize_phoneme("U") == "u"
    assert g2p._normalize_phoneme("E") == "e"
    assert g2p._normalize_phoneme("O") == "o"


def test_normalize_phoneme_specials() -> None:
    assert g2p._normalize_phoneme("N") == "N"
    assert g2p._normalize_phoneme("cl") == "cl"
    assert g2p._normalize_phoneme("q") == "cl"
    assert g2p._normalize_phoneme("pau") == "rest"
    assert g2p._normalize_phoneme("sil") == "rest"


# pyopenjtalk が入っている環境でのみ実行する代表ケース。
class TestWithPyOpenJTalk:
    def setup_method(self) -> None:
        pytest.importorskip("pyopenjtalk")

    def test_a(self) -> None:
        result = g2p.hiragana_to_phonemes("あ")
        assert result == ["a"]

    def test_i(self) -> None:
        assert g2p.hiragana_to_phonemes("い") == ["i"]

    def test_u(self) -> None:
        assert g2p.hiragana_to_phonemes("う") == ["u"]

    def test_kya(self) -> None:
        result = g2p.hiragana_to_phonemes("きゃ")
        # 拗音は子音 (ky) + 母音 (a) のはず
        assert result == ["ky", "a"] or result == ["k", "y", "a"]

    def test_sha(self) -> None:
        result = g2p.hiragana_to_phonemes("しゃ")
        assert result[-1] == "a"
        assert "sh" in result or "s" in result

    def test_katakana_same_as_hiragana(self) -> None:
        # NFKC 正規化でカタカナもひらがなと同等の音素列になる想定
        # (pyopenjtalk は両方扱える)
        assert g2p.hiragana_to_phonemes("ア") == ["a"]
