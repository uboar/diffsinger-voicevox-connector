"""ルーター間で共有するランタイム状態へのアクセサ。

app.state には以下が乗ることを想定:
    - settings: Settings
    - singers: list[LoadedSinger]   (起動時に model_loader が設定)
    - acoustic_cache: dict[int, AcousticModel]  (style_id → モデル)
    - vocoder_cache: dict[int, Vocoder]
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request, status

if TYPE_CHECKING:
    from fastapi import FastAPI

    from .inference.diffsinger_runner import AcousticModel
    from .inference.pitch_predictor import PitchPredictor
    from .inference.vocoder import Vocoder
    from .model_loader import LoadedSinger

logger = logging.getLogger(__name__)

_SING_STYLE_ID_OFFSETS: tuple[int, ...] = (6000, 3000)

_SINGER_NOT_FOUND_MSG = (
    "指定された歌手 (style_id={style_id}) が見つかりません。"
    "GET /singers で利用可能な歌手一覧を確認してください。"
)

_MODEL_LOAD_FAIL_MSG = (
    "DiffSinger モデルの読み込みに失敗しました。"
    "models/ の配置を docs/MODEL_SETUP.md で確認してください"
)


def get_singers(request: Request) -> list[LoadedSinger]:
    return list(getattr(request.app.state, "singers", []) or [])


def _style_id_candidates(style_id: int) -> list[int]:
    candidates = [style_id]
    for offset in _SING_STYLE_ID_OFFSETS:
        if style_id >= offset:
            candidates.append(style_id - offset)
    return candidates


def get_singer(request: Request, style_id: int) -> LoadedSinger:
    """style_id から LoadedSinger を解決。見つからなければ 404。"""
    singers = get_singers(request)
    candidates = _style_id_candidates(style_id)
    if len(candidates) > 1:
        logger.debug(
            "歌手 style_id=%s を候補 %s として解決します",
            style_id,
            candidates,
        )

    for candidate in candidates:
        for singer in singers:
            if singer.style_id == candidate:
                return singer
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=_SINGER_NOT_FOUND_MSG.format(style_id=style_id),
    )


def find_singer_by_uuid(request: Request, speaker_uuid: str) -> LoadedSinger:
    for singer in get_singers(request):
        if singer.uuid == speaker_uuid:
            return singer
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=(
            f"指定された歌手 UUID ({speaker_uuid}) が見つかりません。"
            "GET /singers のレスポンスにある speaker_uuid を指定してください。"
        ),
    )


def get_or_load_models(
    app: FastAPI, singer: LoadedSinger
) -> tuple[AcousticModel, Vocoder]:
    """app.state にキャッシュした acoustic / vocoder を返す。初回はロード試行。

    ロード失敗時は 500 を投げる (詳細メッセージは日本語)。
    """
    acoustic_cache: dict[int, AcousticModel] = getattr(app.state, "acoustic_cache", {})
    vocoder_cache: dict[int, Vocoder] = getattr(app.state, "vocoder_cache", {})

    if singer.style_id in acoustic_cache and singer.style_id in vocoder_cache:
        return acoustic_cache[singer.style_id], vocoder_cache[singer.style_id]

    settings = app.state.settings
    providers = (
        ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if getattr(settings, "use_gpu", False)
        else ["CPUExecutionProvider"]
    )

    try:
        from .inference.diffsinger_runner import AcousticModel
        from .inference.vocoder import Vocoder

        acoustic = AcousticModel(
            singer.acoustic_path,
            dsconfig=singer.dsconfig,
            providers=providers,
        )
        vocoder = Vocoder(
            singer.vocoder_path,
            providers=providers,
            sample_rate=int(
                singer.vocoder_config.get("sample_rate")
                or singer.dsconfig.get("sample_rate")
                or 44100
            ),
        )
    except Exception as exc:
        logger.exception("モデルロード失敗 (style_id=%s)", singer.style_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_MODEL_LOAD_FAIL_MSG,
        ) from exc

    acoustic_cache[singer.style_id] = acoustic
    vocoder_cache[singer.style_id] = vocoder
    app.state.acoustic_cache = acoustic_cache
    app.state.vocoder_cache = vocoder_cache
    return acoustic, vocoder


def get_or_load_pitch_predictor(app: FastAPI, singer: LoadedSinger) -> PitchPredictor | None:
    if not singer.has_pitch_predictor:
        return None

    pitch_cache: dict[int, PitchPredictor] = getattr(app.state, "pitch_cache", {})
    if singer.style_id in pitch_cache:
        return pitch_cache[singer.style_id]

    settings = app.state.settings
    providers = (
        ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if getattr(settings, "use_gpu", False)
        else ["CPUExecutionProvider"]
    )

    try:
        from .inference.pitch_predictor import PitchPredictor

        predictor = PitchPredictor(
            singer.pitch_root,
            dsconfig=singer.pitch_dsconfig,
            providers=providers,
        )
    except Exception:
        logger.exception("pitch predictor のロードに失敗したため規則ベース F0 にフォールバックします")
        return None

    pitch_cache[singer.style_id] = predictor
    app.state.pitch_cache = pitch_cache
    return predictor


def model_load_failure() -> HTTPException:
    """テスト/手動 raise 用に統一メッセージで 500 を構築。"""
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=_MODEL_LOAD_FAIL_MSG,
    )
