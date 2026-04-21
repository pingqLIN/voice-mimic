from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import (
    CalibrationSettings,
    CompensationSettings,
    RoundTripExperimentSettings,
    SessionConfig,
    SessionSettings,
    SpeakerRecord,
    SpeakerRegistry,
    TargetMetrics,
)


def load_session_config(path: str | Path) -> SessionConfig:
    config_path = Path(path).resolve()
    raw = _load_yaml(config_path)

    session_raw = raw["session"]
    calibration_raw = raw["calibration"]
    compensation_raw = raw["compensation"]
    experiment_raw = raw["roundtrip_experiment"]
    target_metrics_raw = experiment_raw["target_metrics"]

    return SessionConfig(
        session=SessionSettings(
            session_id=str(session_raw["session_id"]),
            room_label=str(session_raw["room_label"]),
            playback_device_id=str(session_raw["playback_device_id"]),
            capture_device_id=str(session_raw["capture_device_id"]),
            agc_disabled=bool(session_raw["agc_disabled"]),
            aec_disabled=bool(session_raw["aec_disabled"]),
            noise_suppression_disabled=bool(session_raw["noise_suppression_disabled"]),
        ),
        calibration=CalibrationSettings(
            signal_type=str(calibration_raw["signal_type"]),
            sample_rate=int(calibration_raw["sample_rate"]),
            duration_seconds=int(calibration_raw["duration_seconds"]),
            playback_gain_db=float(calibration_raw["playback_gain_db"]),
            record_gain_db=float(calibration_raw["record_gain_db"]),
            repetitions=int(calibration_raw["repetitions"]),
        ),
        compensation=CompensationSettings(
            enable_latency_compensation=bool(compensation_raw["enable_latency_compensation"]),
            enable_eq_compensation=bool(compensation_raw["enable_eq_compensation"]),
            enable_dereverb=bool(compensation_raw["enable_dereverb"]),
            max_eq_boost_db=float(compensation_raw["max_eq_boost_db"]),
            max_eq_cut_db=float(compensation_raw["max_eq_cut_db"]),
        ),
        roundtrip_experiment=RoundTripExperimentSettings(
            max_rounds=int(experiment_raw["max_rounds"]),
            fixed_prompt_mode=str(experiment_raw["fixed_prompt_mode"]),
            allow_prompt_regeneration_from_roundtrip_audio=bool(
                experiment_raw["allow_prompt_regeneration_from_roundtrip_audio"]
            ),
            allow_model_finetuning=bool(experiment_raw["allow_model_finetuning"]),
            target_metrics=TargetMetrics(
                min_speaker_similarity=float(target_metrics_raw["min_speaker_similarity"]),
                max_cer=float(target_metrics_raw["max_cer"]),
                max_prosody_drift=float(target_metrics_raw["max_prosody_drift"]),
            ),
        ),
        config_path=config_path,
    )


def load_speaker_registry(path: str | Path) -> SpeakerRegistry:
    config_path = Path(path).resolve()
    raw = _load_yaml(config_path)
    speakers: dict[str, SpeakerRecord] = {}
    for speaker_raw in raw["speakers"]:
        record = SpeakerRecord(
            speaker_id=str(speaker_raw["id"]),
            display_name=str(speaker_raw["display_name"]),
            consent_status=str(speaker_raw["consent_status"]),
            consent_scope=str(speaker_raw["consent_scope"]),
            consent_expires_on=str(speaker_raw["consent_expires_on"]),
            source_audio_dir=str(speaker_raw["source_audio_dir"]),
            transcript_required=bool(speaker_raw["transcript_required"]),
            preferred_prompt_mode=str(speaker_raw["preferred_prompt_mode"]),
            allowed_languages=[str(item) for item in speaker_raw.get("allowed_languages", [])],
            notes=str(speaker_raw.get("notes", "")),
        )
        speakers[record.speaker_id] = record

    return SpeakerRegistry(speakers=speakers, config_path=config_path)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected mapping at root of {path}")
    return payload
