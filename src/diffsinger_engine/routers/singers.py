"""歌手情報エンドポイント (/singers, /singer_info)。"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, status

from .. import __version__
from ..runtime_state import find_singer_by_uuid, get_singers
from ..schemas import Speaker, SpeakerInfo, SpeakerStyle, StyleInfo, StyleType

logger = logging.getLogger(__name__)

router = APIRouter(tags=["singers"])
_TRANSPARENT_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+yF9sAAAAASUVORK5CYII="
)


def _singer_to_speaker(singer) -> Speaker:  # type: ignore[no-untyped-def]
    return Speaker(
        name=singer.name,
        speaker_uuid=singer.uuid,
        styles=[
            SpeakerStyle(name="sing", id=singer.style_id, type=StyleType.sing),
        ],
        version=__version__,
    )


def _read_image_base64(path: Path | None, fallback: Path | None) -> str:
    """image を base64 で読み込む。見つからない場合も有効な PNG を返す。"""
    target = path if (path is not None and path.is_file()) else fallback
    if target is None or not target.is_file():
        return _TRANSPARENT_PNG_BASE64
    return base64.b64encode(target.read_bytes()).decode("ascii")


@router.get("/singers", response_model=list[Speaker])
def list_singers(request: Request) -> list[Speaker]:
    return [_singer_to_speaker(s) for s in get_singers(request)]


@router.get("/singer_info", response_model=SpeakerInfo)
def get_singer_info(
    request: Request,
    speaker_uuid: str = Query(..., description="GET /singers の speaker_uuid"),
    resource_format: Literal["base64", "url"] = Query(
        "base64",
        description="リソース返却形式。現在は base64 のみ対応。",
    ),
) -> SpeakerInfo:
    if resource_format == "url":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "resource_format=url は本エンジンでは未対応です。"
                "resource_format=base64 を指定してください。"
            ),
        )

    singer = find_singer_by_uuid(request, speaker_uuid)

    settings = request.app.state.settings
    resources_dir = Path(settings.resources_dir)
    defaults_dir = resources_dir / "default_singer_assets"
    engine_icon = resources_dir / "icon.png"
    fallback_icon = (
        defaults_dir / "icon.png"
        if (defaults_dir / "icon.png").is_file()
        else engine_icon
    )
    fallback_portrait = (
        defaults_dir / "portrait.png"
        if (defaults_dir / "portrait.png").is_file()
        else fallback_icon
    )

    icon_b64 = _read_image_base64(singer.icon_path, fallback_icon)
    portrait_b64 = _read_image_base64(
        singer.portrait_path,
        singer.icon_path if singer.icon_path is not None else fallback_portrait,
    )

    policy = singer.character.get("policy") or singer.character.get("description") or (
        "本歌手モデルの利用規約は配布元の指示に従ってください。"
    )

    style_info = StyleInfo(
        id=singer.style_id,
        icon=icon_b64,
        portrait=portrait_b64 or None,
        voice_samples=[],
    )
    return SpeakerInfo(
        policy=str(policy),
        portrait=portrait_b64,
        style_infos=[style_info],
    )
