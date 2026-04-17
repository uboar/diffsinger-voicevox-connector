"""日本語ひらがな/カタカナ → DiffSinger 音素列変換 (pyopenjtalk ベース)。

VOICEVOX スコアの `note.lyric` は 1モーラのひらがな/カタカナを想定。
pyopenjtalk のフルコンテキストラベルから音素列を抽出し、DiffSinger 日本語モデルの
phonemes.txt に存在する記号 (a,i,u,e,o,k,s,t,n,h,m,y,r,w,g,z,d,b,p,ky,sh,ch,ts,
ny,hy,my,ry,gy,by,py,N,cl,...) にマッピングする。
"""

from __future__ import annotations

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


# pyopenjtalk が出力する音素 (HTS 風表記) を DiffSinger 互換に正規化するマップ。
# 母音は小文字、撥音は N、促音は cl、長音記号 (chOH/aLong) は母音に置換、無音は pau→rest。
_PHONEME_NORMALIZE: dict[str, str] = {
    "A": "a",
    "I": "i",
    "U": "u",
    "E": "e",
    "O": "o",
    "cl": "cl",
    "q": "cl",
    "N": "N",
    "pau": "rest",
    "sil": "rest",
    "xx": "rest",
}


def _normalize_phoneme(p: str) -> str | None:
    if not p:
        return None
    return _PHONEME_NORMALIZE.get(p, p)


_FULLCTX_PHONE_RE = re.compile(r"^([^\-]+)-([^+]+)\+")


def _extract_phonemes_from_fullcontext(labels: list[str]) -> list[str]:
    """pyopenjtalk.run_frontend のフルコンテキストラベルから音素列を抽出。"""
    phonemes: list[str] = []
    for lab in labels:
        m = _FULLCTX_PHONE_RE.match(lab)
        if not m:
            continue
        phone = m.group(2)
        norm = _normalize_phoneme(phone)
        if norm is None:
            continue
        phonemes.append(norm)
    return phonemes


def _strip_silence(phonemes: list[str]) -> list[str]:
    """前後の無音 (rest) を除去。"""
    return [p for p in phonemes if p != "rest"]


def hiragana_to_phonemes(text: str) -> list[str]:
    """ひらがな/カタカナの 1モーラを DiffSinger 音素列に変換する。

    例:
        "あ" -> ["a"]
        "きゃ" -> ["ky", "a"]
        "ん" -> ["N"]
        "っ" -> ["cl"]
    """
    if not text:
        return []

    normalized = unicodedata.normalize("NFKC", text).strip()
    if not normalized:
        return []

    # 単独の "ん" / "っ" は pyopenjtalk が単独でうまく扱えないことがあるため直接判定。
    if normalized in ("ん", "ン"):
        return ["N"]
    if normalized in ("っ", "ッ"):
        return ["cl"]

    try:
        import pyopenjtalk  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - 依存欠如時の明示的失敗
        raise RuntimeError(
            "pyopenjtalk が import できません。`pip install pyopenjtalk` で導入してください。"
        ) from exc

    labels = pyopenjtalk.run_frontend(normalized)
    # pyopenjtalk のバージョンにより返り値が tuple か list[str] かが分かれる。
    if isinstance(labels, tuple):
        # 旧 API: (njd_features, fullcontext_labels)
        labels = labels[1]
    if labels and isinstance(labels[0], dict):
        # 新 API: NJD features → extract_fullcontext を呼ぶ
        labels = pyopenjtalk.make_label(labels)  # type: ignore[attr-defined]

    phonemes = _extract_phonemes_from_fullcontext(list(labels))
    return _strip_silence(phonemes)
