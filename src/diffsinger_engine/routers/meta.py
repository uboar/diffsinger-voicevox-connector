"""エンジンメタ情報のエンドポイント (/version, /engine_manifest, /supported_devices, /health)。"""

from __future__ import annotations

import base64
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from .. import __version__
from ..schemas import (
    DependencyLicense,
    EngineManifest,
    EngineSupportedFeatures,
    HealthStatus,
    SupportedDevices,
    UpdateInfo,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["meta"])


# ──────────────────────── /version ────────────────────────

@router.get("/version", response_model=str)
def get_version() -> str:
    """エンジンバージョン文字列を返す。"""
    return __version__


# ──────────────────────── /engine_manifest ────────────────────────

@lru_cache(maxsize=8)
def _build_manifest(resources_dir_str: str) -> EngineManifest:
    """resources_dir を読んで EngineManifest を構築 (パス毎に一度だけ)。"""
    resources_dir = Path(resources_dir_str)
    manifest_path = resources_dir / "engine_manifest.json"

    if not manifest_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"engine_manifest.json が見つかりません: {manifest_path}。"
                "resources/ ディレクトリの配置を確認してください。"
            ),
        )

    raw: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))

    # icon: ファイル名 → base64 PNG
    icon_field = raw.get("icon", "icon.png")
    icon_path = resources_dir / icon_field
    if icon_path.is_file():
        raw["icon"] = base64.b64encode(icon_path.read_bytes()).decode("ascii")
    else:
        logger.warning("icon ファイルが見つかりません: %s (空文字を返します)", icon_path)
        raw["icon"] = ""

    # terms_of_service: ファイル名 → 内容
    tos_field = raw.get("terms_of_service", "terms.md")
    tos_path = resources_dir / tos_field
    raw["terms_of_service"] = tos_path.read_text(encoding="utf-8") if tos_path.is_file() else ""

    # update_infos: ファイル名 → JSON 配列
    update_field = raw.get("update_infos")
    if isinstance(update_field, str):
        update_path = resources_dir / update_field
        if update_path.is_file():
            raw["update_infos"] = json.loads(update_path.read_text(encoding="utf-8"))
        else:
            raw["update_infos"] = []

    # dependency_licenses: 同上
    dep_field = raw.get("dependency_licenses")
    if isinstance(dep_field, str):
        dep_path = resources_dir / dep_field
        if dep_path.is_file():
            raw["dependency_licenses"] = json.loads(dep_path.read_text(encoding="utf-8"))
        else:
            raw["dependency_licenses"] = []

    raw.setdefault("version", __version__)

    # 型整合: ネストされた pydantic モデルへ詰め替え。
    raw["update_infos"] = [UpdateInfo(**u) for u in raw.get("update_infos", [])]
    raw["dependency_licenses"] = [
        DependencyLicense(**d) for d in raw.get("dependency_licenses", [])
    ]
    raw["supported_features"] = EngineSupportedFeatures(**raw["supported_features"])
    return EngineManifest(**raw)


@router.get("/engine_manifest", response_model=EngineManifest)
def get_engine_manifest(request: Request) -> EngineManifest:
    settings = request.app.state.settings
    return _build_manifest(str(Path(settings.resources_dir).resolve()))


# ──────────────────────── /supported_devices ────────────────────────

@lru_cache(maxsize=1)
def _detect_supported_devices() -> SupportedDevices:
    cuda = False
    dml = False
    try:
        import onnxruntime as ort  # type: ignore[import-not-found]

        providers = list(ort.get_available_providers())
        cuda = "CUDAExecutionProvider" in providers
        dml = "DmlExecutionProvider" in providers
    except Exception as exc:
        logger.warning("onnxruntime のプロバイダ取得に失敗。CPU のみと判定: %s", exc)
    return SupportedDevices(cpu=True, cuda=cuda, dml=dml)


@router.get("/supported_devices", response_model=SupportedDevices)
def get_supported_devices() -> SupportedDevices:
    return _detect_supported_devices()


# ──────────────────────── /health ────────────────────────

@router.get("/health", response_model=HealthStatus)
def get_health(request: Request) -> HealthStatus:
    singers = list(getattr(request.app.state, "singers", []) or [])
    if not singers:
        return HealthStatus(
            status="no_models",
            loaded_singers=0,
            message=(
                "models/ に有効な DiffSinger モデルがありません。"
                "docs/MODEL_SETUP.md を参照してモデルを配置してください。"
            ),
        )
    return HealthStatus(
        status="ok",
        loaded_singers=len(singers),
        message=f"{len(singers)} 件の歌手モデルを読み込み済みです。",
    )
