from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class StopReason(StrEnum):
    TARGET_REACHED = "target_reached"
    INTELLIGIBILITY_REGRESSION = "intelligibility_regression"
    NO_IDENTITY_GAIN = "no_identity_gain"
    MAX_ROUNDS = "max_rounds"


@dataclass(slots=True)
class SessionSettings:
    session_id: str
    room_label: str
    playback_device_id: str
    capture_device_id: str
    agc_disabled: bool
    aec_disabled: bool
    noise_suppression_disabled: bool


@dataclass(slots=True)
class CalibrationSettings:
    signal_type: str
    sample_rate: int
    duration_seconds: int
    playback_gain_db: float
    record_gain_db: float
    repetitions: int


@dataclass(slots=True)
class CompensationSettings:
    enable_latency_compensation: bool
    enable_eq_compensation: bool
    enable_dereverb: bool
    max_eq_boost_db: float
    max_eq_cut_db: float


@dataclass(slots=True)
class TargetMetrics:
    min_speaker_similarity: float
    max_cer: float
    max_prosody_drift: float


@dataclass(slots=True)
class RoundTripExperimentSettings:
    max_rounds: int
    fixed_prompt_mode: str
    allow_prompt_regeneration_from_roundtrip_audio: bool
    allow_model_finetuning: bool
    target_metrics: TargetMetrics


@dataclass(slots=True)
class SessionConfig:
    session: SessionSettings
    calibration: CalibrationSettings
    compensation: CompensationSettings
    roundtrip_experiment: RoundTripExperimentSettings
    config_path: Path


@dataclass(slots=True)
class SpeakerRecord:
    speaker_id: str
    display_name: str
    consent_status: str
    consent_scope: str
    consent_expires_on: str
    source_audio_dir: str
    transcript_required: bool
    preferred_prompt_mode: str
    allowed_languages: list[str]
    notes: str = ""


@dataclass(slots=True)
class SpeakerRegistry:
    speakers: dict[str, SpeakerRecord]
    config_path: Path


@dataclass(slots=True)
class PromptCaptureRequest:
    speaker_id: str
    reference_transcript: str
    target_text: str
    language: str
    reference_asset_id: str | None = None


@dataclass(slots=True)
class CalibrationProfile:
    session_id: str
    room_label: str
    playback_device_id: str
    capture_device_id: str
    latency_ms: float
    noise_floor_dbfs: float
    frequency_tilt_db: float
    eq_profile: dict[str, float]
    playback_gain_db: float
    record_gain_db: float


@dataclass(slots=True)
class PromptPack:
    prompt_id: str
    speaker_id: str
    prompt_mode: str
    transcript: str
    language: str
    source_audio_dir: str
    metadata_path: Path


@dataclass(slots=True)
class ScoreBundle:
    speaker_similarity: float
    cer: float
    prosody_drift: float
    channel_residual: float


@dataclass(slots=True)
class UpdatePlan:
    round_index: int
    targets: list[str]
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RoundResult:
    round_index: int
    output_path: Path
    captured_path: Path
    scores: ScoreBundle
    update_plan: UpdatePlan


@dataclass(slots=True)
class SessionReport:
    session_id: str
    prompt_id: str
    config_path: str
    speaker_id: str
    language: str
    calibration_profile_path: str
    run_log_path: str
    rounds: list[RoundResult]
    stop_reason: StopReason

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "prompt_id": self.prompt_id,
            "config_path": self.config_path,
            "speaker_id": self.speaker_id,
            "language": self.language,
            "calibration_profile_path": self.calibration_profile_path,
            "run_log_path": self.run_log_path,
            "rounds": [round_result_to_dict(item) for item in self.rounds],
            "stop_reason": self.stop_reason.value,
        }


def round_result_to_dict(item: RoundResult) -> dict[str, Any]:
    payload = asdict(item)
    payload["output_path"] = str(item.output_path)
    payload["captured_path"] = str(item.captured_path)
    return payload
