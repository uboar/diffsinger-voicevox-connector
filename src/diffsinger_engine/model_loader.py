"""models/ ディレクトリをスキャンして DiffSinger モデルを発見・登録する。

各サブディレクトリは OpenUtau DiffSinger 互換の以下構成を期待:

    <singer_dir>/
        dsconfig.yaml       # 必須
        acoustic.onnx       # 必須
        vocoder.onnx        # 任意 (共有 vocoder を使う場合は不要)
        phonemes.txt        # 必須
        character.yaml      # 任意 (name, uuid, icon, portrait)
        icon.png            # 任意
        portrait.png        # 任意

OpenUtau 形式の共有 vocoder (`vocoder: nsf_hifigan`) は
`models/vocoders/` や `.oudep` から自動解決する。
不正なフォルダは warning ログを出してスキップする。
"""

from __future__ import annotations

import logging
import shutil
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


_NAMESPACE = uuid.NAMESPACE_URL
_REQUIRED_FILES: tuple[str, ...] = (
    "dsconfig.yaml",
    "acoustic.onnx",
    "phonemes.txt",
)
_IGNORED_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".cache",
        "_shared",
        "shared",
        "vocoders",
    }
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
    phoneme_to_id: dict[str, int]
    icon_path: Path | None = None
    portrait_path: Path | None = None
    character: dict[str, Any] = field(default_factory=dict)
    vocoder_config: dict[str, Any] = field(default_factory=dict)
    pitch_root: Path | None = None
    pitch_dsconfig: dict[str, Any] = field(default_factory=dict)

    @property
    def has_pitch_predictor(self) -> bool:
        return self.pitch_root is not None and bool(self.pitch_dsconfig)


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml  # type: ignore[import-not-found]

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML ルートが mapping ではありません: {path}")
    return data


def _deterministic_uuid(folder_name: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"diffsinger-connector:{folder_name}"))


def _load_phoneme_inventory(path: Path) -> dict[str, int]:
    phonemes = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    mapping = {symbol: index for index, symbol in enumerate(phonemes) if symbol}

    if "SP" in mapping:
        for alias in ("rest", "pau", "sil", "sp"):
            mapping.setdefault(alias, mapping["SP"])
    if "AP" in mapping:
        mapping.setdefault("ap", mapping["AP"])

    return mapping


def _candidate_vocoder_roots(folder: Path) -> list[Path]:
    roots = [
        folder,
        folder.parent,
        folder.parent / "vocoders",
        folder.parent / "_shared",
        folder.parent / "shared",
    ]

    deduped: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if root in seen:
            continue
        seen.add(root)
        deduped.append(root)
    return deduped


def _vocoder_candidates(folder: Path, vocoder_spec: str) -> tuple[list[Path], list[Path]]:
    if not vocoder_spec:
        vocoder_spec = "vocoder"

    roots = _candidate_vocoder_roots(folder)
    onnx_candidates: list[Path] = [folder / "vocoder.onnx"]
    archive_candidates: list[Path] = []

    def add_candidates(root: Path, spec: str) -> None:
        if spec.endswith(".onnx"):
            onnx_candidates.append(root / spec)
            return
        if spec.endswith(".oudep"):
            archive_candidates.append(root / spec)
            return

        onnx_candidates.extend(
            [
                root / f"{spec}.onnx",
                root / spec / f"{spec}.onnx",
                root / spec / "vocoder.onnx",
            ]
        )
        archive_candidates.extend(
            [
                root / f"{spec}.oudep",
                root / spec / f"{spec}.oudep",
                root / spec / "vocoder.oudep",
            ]
        )

    for root in roots:
        add_candidates(root, vocoder_spec)

    return onnx_candidates, archive_candidates


def _extract_vocoder_from_archive(
    archive_path: Path,
    vocoder_cache_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    vocoder_cache_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path) as archive:
        config: dict[str, Any] = {}
        if "vocoder.yaml" in archive.namelist():
            with archive.open("vocoder.yaml") as f:
                import yaml  # type: ignore[import-not-found]

                loaded = yaml.safe_load(f) or {}
                if isinstance(loaded, dict):
                    config = loaded

        model_name = config.get("model")
        if isinstance(model_name, str) and model_name.endswith(".onnx"):
            member_name = model_name
        else:
            try:
                member_name = next(name for name in archive.namelist() if name.endswith(".onnx"))
            except StopIteration as exc:
                raise FileNotFoundError(f"{archive_path} に ONNX vocoder が含まれていません") from exc

        target_dir = vocoder_cache_dir / archive_path.stem
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / Path(member_name).name

        if not target_path.is_file() or target_path.stat().st_mtime < archive_path.stat().st_mtime:
            with archive.open(member_name) as src, target_path.open("wb") as dst:
                shutil.copyfileobj(src, dst)

    return target_path, config


def _load_vocoder_from_onnx_path(path: Path) -> tuple[Path, dict[str, Any]]:
    config_path = path.parent / "vocoder.yaml"
    if config_path.is_file():
        try:
            return path, _load_yaml(config_path)
        except Exception as exc:
            logger.warning("vocoder.yaml の読み込みに失敗。既定値で継続します: %s (%s)", path, exc)
    return path, {}


def _resolve_vocoder(
    folder: Path,
    dsconfig: dict[str, Any],
    vocoder_cache_dir: Path,
) -> tuple[Path | None, dict[str, Any]]:
    vocoder_spec = str(dsconfig.get("vocoder") or "vocoder")
    onnx_candidates, archive_candidates = _vocoder_candidates(folder, vocoder_spec)

    for candidate in onnx_candidates:
        if candidate.is_file():
            return _load_vocoder_from_onnx_path(candidate)

    for archive in archive_candidates:
        if archive.is_file():
            try:
                return _extract_vocoder_from_archive(archive, vocoder_cache_dir)
            except Exception as exc:
                logger.warning("共有 vocoder の展開に失敗しました: %s (%s)", archive, exc)

    return None, {}


def _resolve_relative_path(root: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path


def _load_pitch_bundle(folder: Path, dsconfig: dict[str, Any]) -> tuple[Path | None, dict[str, Any]]:
    candidates: list[tuple[Path, dict[str, Any]]] = []

    dspitch_config = folder / "dspitch" / "dsconfig.yaml"
    if dspitch_config.is_file():
        try:
            candidates.append((folder / "dspitch", _load_yaml(dspitch_config)))
        except Exception as exc:
            logger.warning("dspitch/dsconfig.yaml の読み込みに失敗。pitch 予測を無効化します: %s (%s)", folder, exc)

    if dsconfig.get("pitch") and dsconfig.get("linguistic"):
        candidates.append((folder, dsconfig))

    for root, pitch_dsconfig in candidates:
        pitch_path = _resolve_relative_path(root, pitch_dsconfig.get("pitch"))
        linguistic_path = _resolve_relative_path(root, pitch_dsconfig.get("linguistic"))
        phonemes_path = _resolve_relative_path(root, pitch_dsconfig.get("phonemes") or "phonemes.txt")
        if pitch_path and pitch_path.is_file() and linguistic_path and linguistic_path.is_file() and phonemes_path and phonemes_path.is_file():
            return root, pitch_dsconfig
        logger.warning(
            "pitch predictor の必須ファイルが不足しているため無効化します: %s",
            root,
        )

    return None, {}


def _try_load_singer(folder: Path, style_id: int, vocoder_cache_dir: Path) -> LoadedSinger | None:
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

    try:
        phoneme_to_id = _load_phoneme_inventory(folder / "phonemes.txt")
    except Exception as exc:
        logger.warning("phonemes.txt の読み込みに失敗したためスキップ: %s (%s)", folder, exc)
        return None

    vocoder_path, vocoder_config = _resolve_vocoder(folder, dsconfig, vocoder_cache_dir)
    if vocoder_path is None:
        logger.warning(
            "モデルフォルダ %s の vocoder を解決できないためスキップします。"
            " models/vocoders/ に共有 vocoder を置くか .oudep を配置してください。",
            folder,
        )
        return None

    pitch_root, pitch_dsconfig = _load_pitch_bundle(folder, dsconfig)

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
        vocoder_path=vocoder_path,
        phonemes_path=folder / "phonemes.txt",
        phoneme_to_id=phoneme_to_id,
        icon_path=icon_path if icon_path.is_file() else None,
        portrait_path=portrait_path if portrait_path.is_file() else None,
        character=character,
        vocoder_config=vocoder_config,
        pitch_root=pitch_root,
        pitch_dsconfig=pitch_dsconfig,
    )


def load_singers(
    models_dir: Path,
    vocoder_cache_dir: Path | None = None,
) -> list[LoadedSinger]:
    """models_dir 直下のサブディレクトリを走査して LoadedSinger 一覧を返す。"""
    models_dir = Path(models_dir)
    if not models_dir.is_dir():
        logger.warning("models ディレクトリが存在しません: %s", models_dir)
        return []

    if vocoder_cache_dir is None:
        vocoder_cache_dir = models_dir / ".cache" / "vocoders"
    else:
        vocoder_cache_dir = Path(vocoder_cache_dir)

    singers: list[LoadedSinger] = []
    next_style_id = 0
    for child in sorted(models_dir.iterdir()):
        if child.name.startswith(".") or child.name in _IGNORED_DIR_NAMES:
            continue

        loaded = _try_load_singer(
            child,
            style_id=next_style_id,
            vocoder_cache_dir=vocoder_cache_dir,
        )
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
