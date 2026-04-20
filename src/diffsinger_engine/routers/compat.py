"""VOICEVOX 互換用の補助 API。

起動直後に VOICEVOX Editor が呼ぶユーザー辞書同期 API と、
歌手初期化 API を最小限の互換で実装する。
"""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Body, Query, Request, Response, status

from ..runtime_state import get_or_load_models, get_singer

router = APIRouter(tags=["compat"])
WordType = Literal["PROPER_NOUN", "COMMON_NOUN", "VERB", "ADJECTIVE", "SUFFIX"]


def _user_dict_store(request: Request) -> dict[str, dict[str, object]]:
    store = getattr(request.app.state, "user_dict_store", None)
    if isinstance(store, dict):
        return store
    request.app.state.user_dict_store = {}
    return request.app.state.user_dict_store


def _initialized_speaker_ids(request: Request) -> set[int]:
    speaker_ids = getattr(request.app.state, "initialized_speaker_ids", None)
    if isinstance(speaker_ids, set):
        return speaker_ids
    request.app.state.initialized_speaker_ids = set()
    return request.app.state.initialized_speaker_ids


def _word_defaults(
    surface: str,
    pronunciation: str,
    accent_type: int,
    word_type: WordType | None,
    priority: int | None,
) -> dict[str, object]:
    # 辞書 UI と同期 API が必要とする最小限の整合した値を返す。
    return {
        "surface": surface,
        "priority": 5 if priority is None else priority,
        "context_id": 1348,
        "part_of_speech": "名詞",
        "part_of_speech_detail_1": (
            "固有名詞" if word_type == "PROPER_NOUN" else "一般"
        ),
        "part_of_speech_detail_2": "*",
        "part_of_speech_detail_3": "*",
        "inflectional_type": "*",
        "inflectional_form": "*",
        "stem": surface,
        "yomi": pronunciation,
        "pronunciation": pronunciation,
        "accent_type": accent_type,
        "mora_count": max(len(pronunciation), 1),
        "accent_associative_rule": "*",
    }


@router.get("/user_dict")
def get_user_dict_words(request: Request) -> dict[str, dict[str, object]]:
    return dict(_user_dict_store(request))


@router.post("/user_dict_word", response_model=str)
def add_user_dict_word(
    request: Request,
    surface: str = Query(...),
    pronunciation: str = Query(...),
    accent_type: int = Query(...),
    word_type: WordType | None = Query(default=None),
    priority: int | None = Query(default=None, ge=0, le=10),
) -> str:
    word_uuid = str(uuid4())
    _user_dict_store(request)[word_uuid] = _word_defaults(
        surface=surface,
        pronunciation=pronunciation,
        accent_type=accent_type,
        word_type=word_type,
        priority=priority,
    )
    return word_uuid


@router.put("/user_dict_word/{word_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def rewrite_user_dict_word(
    request: Request,
    word_uuid: str,
    surface: str = Query(...),
    pronunciation: str = Query(...),
    accent_type: int = Query(...),
    word_type: WordType | None = Query(default=None),
    priority: int | None = Query(default=None, ge=0, le=10),
) -> Response:
    _user_dict_store(request)[word_uuid] = _word_defaults(
        surface=surface,
        pronunciation=pronunciation,
        accent_type=accent_type,
        word_type=word_type,
        priority=priority,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/user_dict_word/{word_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_dict_word(request: Request, word_uuid: str) -> Response:
    _user_dict_store(request).pop(word_uuid, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/import_user_dict", status_code=status.HTTP_204_NO_CONTENT)
def import_user_dict_words(
    request: Request,
    override: bool = Query(...),
    import_dict_data: dict[str, dict[str, object]] = Body(...),
) -> Response:
    store = _user_dict_store(request)
    if override:
        store.update(import_dict_data)
    else:
        for word_uuid, word in import_dict_data.items():
            store.setdefault(word_uuid, word)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/is_initialized_speaker", response_model=bool)
def is_initialized_speaker(
    request: Request,
    speaker: int = Query(...),
) -> bool:
    singer = get_singer(request, speaker)
    acoustic_cache = getattr(request.app.state, "acoustic_cache", {})
    vocoder_cache = getattr(request.app.state, "vocoder_cache", {})
    if singer.style_id in acoustic_cache and singer.style_id in vocoder_cache:
        return True
    return singer.style_id in _initialized_speaker_ids(request)


@router.post("/initialize_speaker", status_code=status.HTTP_204_NO_CONTENT)
def initialize_speaker(
    request: Request,
    speaker: int = Query(...),
    skip_reinit: bool = Query(default=False),
) -> Response:
    initialized = _initialized_speaker_ids(request)
    singer = get_singer(request, speaker)
    if skip_reinit and singer.style_id in initialized:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    get_or_load_models(request.app, singer)
    initialized.add(singer.style_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
