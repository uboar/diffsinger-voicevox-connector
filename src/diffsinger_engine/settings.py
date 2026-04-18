"""ランタイム設定。CLI 引数 / 環境変数 / 既定値の順で解決。

VOICEVOX_DIFFSINGER_HOST=0.0.0.0 のような環境変数でも上書きできる。
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VOICEVOX_DIFFSINGER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="127.0.0.1", description="バインドホスト")
    port: int = Field(default=50122, description="HTTP ポート (VOICEVOX 公式は 50021)")
    models_dir: Path = Field(
        default=Path("./models"),
        description="DiffSinger モデルを配置するディレクトリ",
    )
    resources_dir: Path = Field(
        default=Path("./resources"),
        description="エンジンマニフェスト等のリソース配置ディレクトリ",
    )
    vocoder_cache_dir: Path = Field(
        default=Path("./models/.cache/vocoders"),
        description=(
            "OpenUtau .oudep などの共有 vocoder を展開して再利用するキャッシュディレクトリ"
        ),
    )
    logs_dir: Path = Field(
        default=Path("./logs"),
        description="ログファイル出力ディレクトリ",
    )
    final_sampling_rate: int = Field(
        default=44100,
        description=(
            "/frame_synthesis のデフォルト出力サンプリングレート。"
            "DiffSinger の native 44100 を維持するため既定 44100。"
            "FrameAudioQuery.outputSamplingRate で上書き可能。"
        ),
    )
    editor_default_sampling_rate: int = Field(
        default=24000,
        description=(
            "engine_manifest.default_sampling_rate に返す値。"
            "VOICEVOX エディタの内部処理互換のため 24000 を既定とする。"
        ),
    )
    use_gpu: bool = Field(
        default=False,
        description="True なら CUDAExecutionProvider を優先利用。失敗時は CPU フォールバック。",
    )
    log_level: str = Field(default="INFO")


_settings: Settings | None = None


def get_settings() -> Settings:
    """シングルトン取得。テストでは reload_settings() で差し替え。"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings(**overrides: object) -> Settings:
    """設定を再構築（主にテスト・CLI 用）。"""
    global _settings
    _settings = Settings(**overrides)  # type: ignore[arg-type]
    return _settings
