from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Protocol

from .models import (
    CalibrationProfile,
    PromptCaptureRequest,
    PromptPack,
    RoundResult,
    ScoreBundle,
    SessionConfig,
    SessionReport,
    SpeakerRecord,
    StopReason,
    UpdatePlan,
)


class ControllerBackend(Protocol):
    def precheck(self, config: SessionConfig, speaker: SpeakerRecord) -> list[str]:
        ...

    def calibrate(self, config: SessionConfig, project_root: Path) -> CalibrationProfile:
        ...

    def build_prompt_pack(
        self,
        config: SessionConfig,
        speaker: SpeakerRecord,
        request: PromptCaptureRequest,
        project_root: Path,
    ) -> PromptPack:
        ...

    def synthesize_round(
        self,
        config: SessionConfig,
        prompt_pack: PromptPack,
        calibration: CalibrationProfile,
        round_index: int,
        update_plan: UpdatePlan,
        project_root: Path,
    ) -> Path:
        ...

    def play_and_capture(
        self,
        config: SessionConfig,
        synthesis_output: Path,
        calibration: CalibrationProfile,
        round_index: int,
        project_root: Path,
    ) -> Path:
        ...

    def score_round(
        self,
        config: SessionConfig,
        prompt_pack: PromptPack,
        captured_output: Path,
        round_index: int,
    ) -> ScoreBundle:
        ...


class DryRunBackend:
    def __init__(self, score_sequence: list[ScoreBundle] | None = None) -> None:
        self._score_sequence = score_sequence or [
            ScoreBundle(0.78, 0.06, 0.18, 0.21),
            ScoreBundle(0.83, 0.05, 0.14, 0.13),
            ScoreBundle(0.831, 0.05, 0.14, 0.125),
        ]

    def precheck(self, config: SessionConfig, speaker: SpeakerRecord) -> list[str]:
        warnings: list[str] = []
        if speaker.consent_status.lower() != "approved":
            raise ValueError(f"Speaker {speaker.speaker_id} is not approved.")
        expires_on = date.fromisoformat(speaker.consent_expires_on)
        if expires_on < date.today():
            raise ValueError(f"Speaker {speaker.speaker_id} consent expired on {speaker.consent_expires_on}.")
        if config.roundtrip_experiment.fixed_prompt_mode != "transcript_backed_icl":
            warnings.append("Prompt mode is not transcript_backed_icl.")
        return warnings

    def calibrate(self, config: SessionConfig, project_root: Path) -> CalibrationProfile:
        return CalibrationProfile(
            session_id=config.session.session_id,
            room_label=config.session.room_label,
            playback_device_id=config.session.playback_device_id,
            capture_device_id=config.session.capture_device_id,
            latency_ms=57.0,
            noise_floor_dbfs=-53.0,
            frequency_tilt_db=2.4,
            eq_profile={"low_shelf_db": -1.5, "presence_db": 1.0},
            playback_gain_db=config.calibration.playback_gain_db,
            record_gain_db=config.calibration.record_gain_db,
        )

    def build_prompt_pack(
        self,
        config: SessionConfig,
        speaker: SpeakerRecord,
        request: PromptCaptureRequest,
        project_root: Path,
    ) -> PromptPack:
        transcript_hash = hashlib.sha256(request.reference_transcript.encode("utf-8")).hexdigest()[:12]
        prompt_id = f"{speaker.speaker_id}-{request.language}-{transcript_hash}"
        prompt_dir = project_root / "artifacts" / "voice_prompts" / speaker.speaker_id
        prompt_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = prompt_dir / f"{prompt_id}.json"
        payload = {
            "prompt_id": prompt_id,
            "speaker_id": speaker.speaker_id,
            "reference_asset_id": request.reference_asset_id,
            "prompt_mode": config.roundtrip_experiment.fixed_prompt_mode,
            "transcript": request.reference_transcript,
            "language": request.language,
            "source_audio_dir": speaker.source_audio_dir,
            "created_at": _utc_now(),
            "backend": "dry_run",
        }
        metadata_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        return PromptPack(
            prompt_id=prompt_id,
            speaker_id=speaker.speaker_id,
            prompt_mode=config.roundtrip_experiment.fixed_prompt_mode,
            transcript=request.reference_transcript,
            language=request.language,
            source_audio_dir=speaker.source_audio_dir,
            metadata_path=metadata_path,
        )

    def synthesize_round(
        self,
        config: SessionConfig,
        prompt_pack: PromptPack,
        calibration: CalibrationProfile,
        round_index: int,
        update_plan: UpdatePlan,
        project_root: Path,
    ) -> Path:
        output_dir = project_root / "artifacts" / "roundtrip_runs" / config.session.session_id / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"round-{round_index:02d}-tts.txt"
        payload = {
            "round_index": round_index,
            "prompt_id": prompt_pack.prompt_id,
            "update_targets": update_plan.targets,
            "notes": update_plan.notes,
            "created_at": _utc_now(),
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        return output_path

    def play_and_capture(
        self,
        config: SessionConfig,
        synthesis_output: Path,
        calibration: CalibrationProfile,
        round_index: int,
        project_root: Path,
    ) -> Path:
        capture_dir = project_root / "artifacts" / "roundtrip_runs" / config.session.session_id / "captures"
        capture_dir.mkdir(parents=True, exist_ok=True)
        capture_path = capture_dir / f"round-{round_index:02d}-capture.txt"
        payload = {
            "source_output": str(synthesis_output),
            "round_index": round_index,
            "latency_ms": calibration.latency_ms,
            "captured_at": _utc_now(),
        }
        capture_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        return capture_path

    def score_round(
        self,
        config: SessionConfig,
        prompt_pack: PromptPack,
        captured_output: Path,
        round_index: int,
    ) -> ScoreBundle:
        if round_index - 1 < len(self._score_sequence):
            return self._score_sequence[round_index - 1]
        return self._score_sequence[-1]


class RoundTripController:
    def __init__(self, project_root: Path, backend: ControllerBackend) -> None:
        self.project_root = project_root.resolve()
        self.backend = backend

    def run(
        self,
        config: SessionConfig,
        speaker: SpeakerRecord,
        request: PromptCaptureRequest,
    ) -> SessionReport:
        self._ensure_runtime_guards(config)
        self._validate_request_against_speaker(speaker, request)
        precheck_warnings = self.backend.precheck(config, speaker)

        calibration = self.backend.calibrate(config, self.project_root)
        calibration_profile_path = self._write_calibration_profile(calibration)

        prompt_pack = self.backend.build_prompt_pack(config, speaker, request, self.project_root)

        rounds: list[RoundResult] = []
        stop_reason: StopReason | None = None
        update_plan = UpdatePlan(round_index=0, targets=["playback_compensation"], notes=precheck_warnings)

        for round_index in range(1, config.roundtrip_experiment.max_rounds + 1):
            synthesis_output = self.backend.synthesize_round(
                config, prompt_pack, calibration, round_index, update_plan, self.project_root
            )
            captured_output = self.backend.play_and_capture(
                config, synthesis_output, calibration, round_index, self.project_root
            )
            scores = self.backend.score_round(config, prompt_pack, captured_output, round_index)
            update_plan = self.build_update_plan(config, rounds, scores, round_index)
            round_result = RoundResult(
                round_index=round_index,
                output_path=synthesis_output,
                captured_path=captured_output,
                scores=scores,
                update_plan=update_plan,
            )
            rounds.append(round_result)

            stop_reason = self.evaluate_stop_reason(config, rounds)
            if stop_reason is not None:
                break

        if stop_reason is None:
            stop_reason = StopReason.MAX_ROUNDS

        run_log_path = self._write_run_log(config, speaker, prompt_pack, calibration_profile_path, rounds, stop_reason)
        return SessionReport(
            session_id=config.session.session_id,
            prompt_id=prompt_pack.prompt_id,
            config_path=str(config.config_path),
            speaker_id=speaker.speaker_id,
            language=request.language,
            calibration_profile_path=str(calibration_profile_path),
            run_log_path=str(run_log_path),
            rounds=rounds,
            stop_reason=stop_reason,
        )

    @staticmethod
    def build_update_plan(
        config: SessionConfig,
        prior_rounds: list[RoundResult],
        current_scores: ScoreBundle,
        round_index: int,
    ) -> UpdatePlan:
        targets: list[str] = []
        notes: list[str] = []
        targets_config = config.roundtrip_experiment.target_metrics

        if current_scores.channel_residual > 0.1:
            targets.append("playback_compensation")
            notes.append("Channel residual is still high.")
        if current_scores.cer > targets_config.max_cer:
            targets.append("output_loudness_normalization")
            notes.append("CER exceeded target threshold.")
        if current_scores.speaker_similarity < targets_config.min_speaker_similarity:
            targets.append("prompt_pack_selection")
            notes.append("Speaker similarity is below the target floor.")
        if current_scores.prosody_drift > targets_config.max_prosody_drift:
            targets.append("generation_parameters")
            notes.append("Prosody drift exceeded target threshold.")

        if not targets:
            targets.append("stabilize_and_verify")
            notes.append("All primary metrics are within target range.")

        if prior_rounds:
            previous = prior_rounds[-1].scores
            if current_scores.channel_residual < previous.channel_residual:
                notes.append("Channel compensation is improving.")
            if current_scores.speaker_similarity > previous.speaker_similarity:
                notes.append("Speaker identity retention improved.")

        return UpdatePlan(round_index=round_index, targets=targets, notes=notes)

    @staticmethod
    def evaluate_stop_reason(
        config: SessionConfig,
        rounds: list[RoundResult],
    ) -> StopReason | None:
        latest = rounds[-1].scores
        targets = config.roundtrip_experiment.target_metrics
        if (
            latest.speaker_similarity >= targets.min_speaker_similarity
            and latest.cer <= targets.max_cer
            and latest.prosody_drift <= targets.max_prosody_drift
        ):
            return StopReason.TARGET_REACHED

        if len(rounds) < 2:
            return StopReason.MAX_ROUNDS if len(rounds) >= config.roundtrip_experiment.max_rounds else None

        previous = rounds[-2].scores
        if latest.cer > previous.cer + 0.01:
            return StopReason.INTELLIGIBILITY_REGRESSION

        similarity_gain = latest.speaker_similarity - previous.speaker_similarity
        channel_gain = previous.channel_residual - latest.channel_residual
        if similarity_gain <= 0.002 and channel_gain <= 0.01:
            return StopReason.NO_IDENTITY_GAIN

        if len(rounds) >= config.roundtrip_experiment.max_rounds:
            return StopReason.MAX_ROUNDS
        return None

    def _write_calibration_profile(self, profile: CalibrationProfile) -> Path:
        output_path = self.project_root / "artifacts" / "calibration_profiles" / f"{profile.session_id}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(asdict(profile), ensure_ascii=True, indent=2), encoding="utf-8")
        return output_path

    def _write_run_log(
        self,
        config: SessionConfig,
        speaker: SpeakerRecord,
        prompt_pack: PromptPack,
        calibration_profile_path: Path,
        rounds: list[RoundResult],
        stop_reason: StopReason,
    ) -> Path:
        run_dir = self.project_root / "artifacts" / "roundtrip_runs" / config.session.session_id
        run_dir.mkdir(parents=True, exist_ok=True)
        run_log_path = run_dir / "session-report.json"
        payload = {
            "session_id": config.session.session_id,
            "speaker_id": speaker.speaker_id,
            "prompt_id": prompt_pack.prompt_id,
            "calibration_profile_path": str(calibration_profile_path),
            "config_path": str(config.config_path),
            "stop_reason": stop_reason.value,
            "generated_at": _utc_now(),
            "rounds": [
                {
                    "round_index": item.round_index,
                    "output_path": str(item.output_path),
                    "captured_path": str(item.captured_path),
                    "scores": asdict(item.scores),
                    "update_plan": asdict(item.update_plan),
                }
                for item in rounds
            ],
        }
        run_log_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        return run_log_path

    @staticmethod
    def _ensure_runtime_guards(config: SessionConfig) -> None:
        experiment = config.roundtrip_experiment
        if experiment.fixed_prompt_mode != "transcript_backed_icl":
            raise ValueError("Controller currently requires transcript_backed_icl prompt mode.")
        if experiment.allow_prompt_regeneration_from_roundtrip_audio:
            raise ValueError("Round-trip prompt regeneration must remain disabled in v1.")
        if experiment.allow_model_finetuning:
            raise ValueError("Model fine-tuning must remain disabled in v1.")

    @staticmethod
    def _validate_request_against_speaker(speaker: SpeakerRecord, request: PromptCaptureRequest) -> None:
        if not request.reference_transcript.strip():
            raise ValueError("Reference transcript must not be empty.")
        if speaker.allowed_languages and request.language not in speaker.allowed_languages:
            raise ValueError(
                f"Language {request.language} is not allowed for speaker {speaker.speaker_id}. "
                f"Allowed: {speaker.allowed_languages}"
            )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
