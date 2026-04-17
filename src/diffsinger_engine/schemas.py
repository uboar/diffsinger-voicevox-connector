"""VOICEVOX Engine 互換の Pydantic モデル定義。

OpenAPI: https://voicevox.github.io/voicevox_engine/api/
歌唱合成は notes/Score → FrameAudioQuery → WAV のフローで合成する。
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ──────────────────────── Score (入力楽譜) ────────────────────────

class Note(BaseModel):
    """歌唱合成のノート。最初と最後は key=None, lyric="" の無音必須。"""

    id: str | None = Field(default=None, description="ノートID (任意)")
    key: int | None = Field(default=None, description="MIDI ノート番号。None で無音")
    frame_length: int = Field(ge=0, description="93.75fps 基準のフレーム数")
    lyric: str = Field(default="", description="歌詞 (1モーラ、ひらがな/カタカナ)")


class Score(BaseModel):
    notes: list[Note]


# ──────────────────────── FrameAudioQuery ────────────────────────

class FramePhoneme(BaseModel):
    phoneme: str
    frame_length: int = Field(ge=0)
    note_id: str | None = None


class FrameAudioQuery(BaseModel):
    """フレーム単位の音響パラメータ。/sing_frame_audio_query で生成 → /frame_synthesis へ渡す。"""

    f0: list[float] = Field(description="フレームごとの基本周波数 (Hz)")
    volume: list[float] = Field(description="フレームごとの音量")
    phonemes: list[FramePhoneme]
    volumeScale: float = 1.0
    outputSamplingRate: int = Field(
        default=44100,
        description="出力サンプリングレート。既定 44100 (DiffSinger native)",
    )
    outputStereo: bool = False


# ──────────────────────── 歌手 / Speaker ────────────────────────

class StyleType(str, Enum):
    talk = "talk"
    singing_teacher = "singing_teacher"
    frame_decode = "frame_decode"
    sing = "sing"


class SpeakerStyle(BaseModel):
    name: str
    id: int
    type: StyleType = StyleType.sing


class SupportedFeaturesPerSpeaker(BaseModel):
    permitted_synthesis_morphing: Literal["ALL", "SELF_ONLY", "NOTHING"] = "NOTHING"


class Speaker(BaseModel):
    """/speakers, /singers のレスポンス要素。"""

    name: str
    speaker_uuid: str
    styles: list[SpeakerStyle]
    version: str = "0.0.0"
    supported_features: SupportedFeaturesPerSpeaker = Field(
        default_factory=SupportedFeaturesPerSpeaker
    )


class StyleInfo(BaseModel):
    id: int
    icon: str = Field(description="base64 エンコード PNG (resource_format=base64) または URL")
    portrait: str | None = None
    voice_samples: list[str] = Field(default_factory=list)


class SpeakerInfo(BaseModel):
    policy: str
    portrait: str
    style_infos: list[StyleInfo]


# ──────────────────────── EngineManifest ────────────────────────

class EngineSupportedFeatures(BaseModel):
    """engine_manifest.supported_features。VOICEVOX エディタが機能可否を判定する。"""

    model_config = ConfigDict(populate_by_name=True)

    adjust_mora_pitch: bool
    adjust_phoneme_length: bool
    adjust_speed_scale: bool
    adjust_pitch_scale: bool
    adjust_intonation_scale: bool
    adjust_volume_scale: bool
    adjust_pause_length: bool | None = None
    interrogative_upspeak: bool
    synthesis_morphing: bool
    sing: bool | None = None
    manage_library: bool | None = None
    return_resource_url: bool | None = None
    apply_katakana_english: bool | None = None


class UpdateInfo(BaseModel):
    version: str
    descriptions: list[str]
    contributors: list[str] = Field(default_factory=list)


class DependencyLicense(BaseModel):
    name: str
    version: str
    license: str
    text: str = ""


class EngineManifest(BaseModel):
    manifest_version: str
    name: str
    brand_name: str
    uuid: str
    url: str
    icon: str = Field(description="base64 PNG")
    default_sampling_rate: int
    frame_rate: float
    terms_of_service: str
    update_infos: list[UpdateInfo]
    dependency_licenses: list[DependencyLicense]
    supported_vvlib_manifest_version: str | None = None
    supported_features: EngineSupportedFeatures
    version: str = "0.1.0"


# ──────────────────────── SupportedDevices ────────────────────────

class SupportedDevices(BaseModel):
    cpu: bool = True
    cuda: bool = False
    dml: bool = False


# ──────────────────────── ヘルスチェック ────────────────────────

class HealthStatus(BaseModel):
    status: Literal["ok", "no_models", "error"]
    loaded_singers: int
    message: str = ""
