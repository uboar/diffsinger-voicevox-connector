"""talk 型エンドポイントのスタブ。

本エンジンは歌唱合成 (sing) 専用。VOICEVOX エディタの一部実装が
/speakers, /audio_query 等を呼ぶ可能性に備えて、互換性のため
最低限のレスポンス (空配列 / 404 / 501) を返す。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from ..schemas import Speaker

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tts-stub"])


_NOT_SUPPORTED_DETAIL = (
    "本エンジンは talk 型キャラクターをサポートしていません。"
    "歌唱には /singers を使用してください。"
)
_NOT_IMPLEMENTED_DETAIL = (
    "本エンジンは talk 合成 (audio_query / synthesis) をサポートしていません。"
    "歌唱合成の /sing_frame_audio_query / /frame_synthesis を使用してください。"
)


@router.get("/speakers", response_model=list[Speaker])
def list_speakers() -> list[Speaker]:
    """talk 型キャラクター一覧。本エンジンは未対応のため空配列を返す。"""
    return []


@router.get("/speaker_info")
def get_speaker_info() -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=_NOT_SUPPORTED_DETAIL,
    )


@router.post("/audio_query")
def audio_query() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=_NOT_IMPLEMENTED_DETAIL,
    )


@router.post("/synthesis")
def synthesis() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=_NOT_IMPLEMENTED_DETAIL,
    )
