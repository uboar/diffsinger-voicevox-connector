"""models/ ディレクトリをスキャンして DiffSinger モデルを発見・登録する。

各サブディレクトリは OpenUtau DiffSinger 互換の以下構成を期待:

    <singer_dir>/
        dsconfig.yaml       # 必須
        acoustic.onnx       # 必須
        vocoder.onnx        # 必須
        phonemes.txt        # 必須
        character.yaml      # 任意 (name, uuid, icon, portrait)
        icon.png            # 任意
        portrait.png        # 任意

不正なフォルダは warning ログを出してスキップする。
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


_NAMESPACE = uuid.NAMESPACE_URL
_REQUIRED_FILES: tuple[str, ...] = (
    "dsconfig.yaml",
    "acoustic.onnx",
    "vocoder.onnx",
    "phonemes.txt",
)


@dataclass
class LoadedSinger:
    """発見された DiffSinger モデル 1 個分のメタデータ。"""

    uuid: str
    name: str
    style_id: int
    folder: Path
    dsconfig: dict[str, Any]
    acoustic_path: Path
    vocoder_path: Path
    phonemes_path: Path
    icon_path: Path | None = None
    portrait_path: Path | None = None
    character: dict[str, Any] = field(default_factory=dict)


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml  # type: ignore[import-not-found]

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML ルートが mapping ではありません: {path}")
    return data


def _deterministic_uuid(folder_name: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"diffsinger-connector:{folder_name}"))


def _try_load_singer(folder: Path, style_id: int) -> LoadedSinger | None:
    """1つのモデルフォルダを検査・ロード。失敗時は None を返す。"""
    if not folder.is_dir():
        return None

    missing = [name for name in _REQUIRED_FILES if not (folder / name).is_file()]
    if missing:
        logger.warning(
            "モデルフォルダ %s に必須ファイルが不足しているためスキップします: %s",
            folder,
            ", ".join(missing),
        )
        return None

    try:
        dsconfig = _load_yaml(folder / "dsconfig.yaml")
    except Exception as exc:
        logger.warning("dsconfig.yaml の読み込みに失敗したためスキップ: %s (%s)", folder, exc)
        return None

    character: dict[str, Any] = {}
    character_path = folder / "character.yaml"
    if character_path.is_file():
        try:
            character = _load_yaml(character_path)
        except Exception as exc:
            logger.warning(
                "character.yaml の読み込みに失敗。フォルダ名から既定値を使用します: %s (%s)",
                folder,
                exc,
            )
            character = {}

    name = str(character.get("name") or folder.name)
    singer_uuid = str(character.get("uuid") or _deterministic_uuid(folder.name))

    icon_rel = character.get("icon")
    portrait_rel = character.get("portrait")
    icon_path = (folder / str(icon_rel)) if icon_rel else (folder / "icon.png")
    portrait_path = (folder / str(portrait_rel)) if portrait_rel else (folder / "portrait.png")

    return LoadedSinger(
        uuid=singer_uuid,
        name=name,
        style_id=style_id,
        folder=folder,
        dsconfig=dsconfig,
        acoustic_path=folder / "acoustic.onnx",
        vocoder_path=folder / "vocoder.onnx",
        phonemes_path=folder / "phonemes.txt",
        icon_path=icon_path if icon_path.is_file() else None,
        portrait_path=portrait_path if portrait_path.is_file() else None,
        character=character,
    )


def load_singers(models_dir: Path) -> list[LoadedSinger]:
    """models_dir 直下のサブディレクトリを走査して LoadedSinger 一覧を返す。"""
    models_dir = Path(models_dir)
    if not models_dir.is_dir():
        logger.warning("models ディレクトリが存在しません: %s", models_dir)
        return []

    singers: list[LoadedSinger] = []
    next_style_id = 0
    for child in sorted(models_dir.iterdir()):
        loaded = _try_load_singer(child, style_id=next_style_id)
        if loaded is None:
            continue
        singers.append(loaded)
        next_style_id += 1

    if not singers:
        logger.warning(
            "%s 配下に有効な DiffSinger モデルが見つかりません。"
            "ドキュメント (docs/MODEL_SETUP.md) を参照してモデルを配置してください。",
            models_dir,
        )

    return singers
