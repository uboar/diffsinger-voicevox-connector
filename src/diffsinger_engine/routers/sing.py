"""歌唱合成エンドポイント (/sing_frame_*, /frame_synthesis)。"""

from __future__ import annotations

import logging

import numpy as np
from fastapi import APIRouter, Body, HTTPException, Query, Request, Response, status

from ..inference.frame_query import VOICEVOX_FRAME_RATE, build_frame_query
from ..inference.postprocess import to_wav_bytes
from ..inference.score_converter import score_to_ds_input
from ..runtime_state import get_or_load_models, get_or_load_pitch_predictor, get_singer
from ..schemas import FrameAudioQuery, Score

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sing"])
_FRAME_AUDIO_QUERY_BODY = Body(...)
_PHONEME_ALIAS_TO_MODEL: dict[str, str] = {
    "rest": "SP",
    "pau": "SP",
    "sil": "SP",
    "sp": "SP",
    "ap": "AP",
}
_SCORE_BODY = Body(...)
_SCORE_AND_QUERY_BODY = Body(
    ...,
    description="{score: Score, frame_audio_query: FrameAudioQuery}",
)


def _build_query_for_singer(request: Request, singer, score: Score) -> FrameAudioQuery:  # type: ignore[no-untyped-def]
    settings = request.app.state.settings
    ds_input = score_to_ds_input(score, frame_rate=VOICEVOX_FRAME_RATE)
    predicted_f0: list[float] | None = None

    predictor = get_or_load_pitch_predictor(request.app, singer)
    if predictor is not None:
        try:
            predicted_f0 = predictor.predict_f0(score, ds_input)
        except Exception:
            logger.exception("pitch predictor の推論に失敗したため規則ベース F0 にフォールバックします")

    return build_frame_query(
        score=score,
        ds_input=ds_input,
        f0=predicted_f0,
        output_sr=int(settings.final_sampling_rate),
    )


# ──────────────────────── /sing_frame_audio_query ────────────────────────

@router.post("/sing_frame_audio_query", response_model=FrameAudioQuery)
def sing_frame_audio_query(
    request: Request,
    score: Score = _SCORE_BODY,
    speaker: int = Query(..., description="GET /singers の style id"),
) -> FrameAudioQuery:
    singer = get_singer(request, speaker)
    return _build_query_for_singer(request, singer, score)


# ──────────────────────── /sing_frame_f0 ────────────────────────

class _ScoreAndQuery(dict):
    """Body 用の最小スキーマ (Pydantic で受け取るため dict ベース)。"""


@router.post("/sing_frame_f0", response_model=list[float])
def sing_frame_f0(
    request: Request,
    payload: dict = _SCORE_AND_QUERY_BODY,
    speaker: int = Query(...),
) -> list[float]:
    singer = get_singer(request, speaker)
    score = Score.model_validate(payload["score"])
    return _build_query_for_singer(request, singer, score).f0


# ──────────────────────── /sing_frame_volume ────────────────────────

@router.post("/sing_frame_volume", response_model=list[float])
def sing_frame_volume(
    request: Request,
    payload: dict = _SCORE_AND_QUERY_BODY,
    speaker: int = Query(...),
) -> list[float]:
    singer = get_singer(request, speaker)
    score = Score.model_validate(payload["score"])
    return _build_query_for_singer(request, singer, score).volume


# ──────────────────────── /frame_synthesis ────────────────────────

@router.post(
    "/frame_synthesis",
    responses={200: {"content": {"audio/wav": {}}}},
    response_class=Response,
)
def frame_synthesis(
    request: Request,
    query: FrameAudioQuery = _FRAME_AUDIO_QUERY_BODY,
    speaker: int = Query(...),
) -> Response:
    singer = get_singer(request, speaker)
    acoustic, vocoder = get_or_load_models(request.app, singer)

    # VOICEVOX の 93.75fps 表現を、モデル native の hop_size/sample_rate に合わせて変換する。
    durations_list = _query_durations_to_model_frames(query, singer)
    total_frames = sum(durations_list)
    if total_frames <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="frame_synthesis に必要なフレーム列が空です。",
        )

    f0 = np.asarray(_resample_to_length(query.f0, total_frames), dtype=np.float32)
    volume = np.asarray(_resample_to_length(query.volume, total_frames), dtype=np.float32)
    tokens = np.asarray(
        [_phoneme_to_token_id(singer.phoneme_to_id, p.phoneme) for p in query.phonemes],
        dtype=np.int64,
    )[None, :]
    durations = np.asarray(durations_list, dtype=np.int64)[None, :]

    features = {
        "tokens": tokens,
        "durations": durations,
        "f0": f0[None, :],
        "volume": volume[None, :],
        "depth": np.asarray(int(singer.dsconfig.get("max_depth") or 400), dtype=np.int64),
        "speedup": np.asarray(max(int(singer.dsconfig.get("speedup") or 1), 1), dtype=np.int64),
    }

    mel = acoustic.run(features)
    waveform = vocoder.run(mel, f0)

    wav_bytes = to_wav_bytes(
        waveform,
        src_sr=int(getattr(vocoder, "sample_rate", 44100)),
        target_sr=int(query.outputSamplingRate),
    )
    return Response(content=wav_bytes, media_type="audio/wav")


def _query_durations_to_model_frames(query: FrameAudioQuery, singer) -> list[int]:  # type: ignore[no-untyped-def]
    model_frame_rate = _model_frame_rate(singer)
    durations: list[int] = []
    for phoneme in query.phonemes:
        model_frames = int(round((phoneme.frame_length / VOICEVOX_FRAME_RATE) * model_frame_rate))
        if phoneme.frame_length > 0 and model_frames <= 0:
            model_frames = 1
        durations.append(model_frames)
    return durations


def _model_frame_rate(singer) -> float:  # type: ignore[no-untyped-def]
    sample_rate = float(
        singer.dsconfig.get("sample_rate")
        or singer.vocoder_config.get("sample_rate")
        or 44100
    )
    hop_size = float(
        singer.dsconfig.get("hop_size")
        or singer.vocoder_config.get("hop_size")
        or 512
    )
    if hop_size <= 0:
        return VOICEVOX_FRAME_RATE
    return sample_rate / hop_size


def _resample_to_length(values: list[float], target_length: int) -> list[float]:
    if target_length <= 0:
        return []
    if not values:
        return [0.0] * target_length
    if len(values) == target_length:
        return list(values)
    if len(values) == 1:
        return [float(values[0])] * target_length

    source = np.asarray(values, dtype=np.float32)
    positions = np.linspace(0, len(source) - 1, num=target_length)
    indices = np.clip(np.rint(positions).astype(np.int64), 0, len(source) - 1)
    return source[indices].astype(np.float32).tolist()


def _phoneme_to_token_id(phoneme_to_id: dict[str, int], phoneme: str) -> int:
    candidates = [
        phoneme,
        _PHONEME_ALIAS_TO_MODEL.get(phoneme, phoneme),
        phoneme.lower(),
        phoneme.upper(),
    ]
    for candidate in candidates:
        if candidate in phoneme_to_id:
            return phoneme_to_id[candidate]

    if "SP" in phoneme_to_id:
        logger.warning("未登録音素 %r を SP にフォールバックします", phoneme)
        return phoneme_to_id["SP"]
    if "<PAD>" in phoneme_to_id:
        logger.warning("未登録音素 %r を <PAD> にフォールバックします", phoneme)
        return phoneme_to_id["<PAD>"]

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"音素 {phoneme!r} をモデル語彙へ変換できませんでした。",
    )
