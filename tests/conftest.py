"""pytest 共通フィクスチャ。"""

from __future__ import annotations

from pathlib import Path

import pytest

from diffsinger_engine.settings import Settings


@pytest.fixture()
def tmp_models_dir(tmp_path: Path) -> Path:
    models = tmp_path / "models"
    models.mkdir()
    return models


@pytest.fixture()
def settings(tmp_models_dir: Path, tmp_path: Path) -> Settings:
    return Settings(
        host="127.0.0.1",
        port=0,
        models_dir=tmp_models_dir,
        resources_dir=Path(__file__).parent.parent / "resources",
        vocoder_cache_dir=tmp_path / "vocoder-cache",
        logs_dir=tmp_path / "logs",
        final_sampling_rate=44100,
        editor_default_sampling_rate=24000,
        use_gpu=False,
        log_level="WARNING",
    )
