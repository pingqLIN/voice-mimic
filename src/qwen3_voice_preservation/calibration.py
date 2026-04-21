from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .audio import (
    derive_eq_profile,
    estimate_frequency_tilt_db,
    estimate_latency_ms,
    estimate_noise_floor_dbfs,
    generate_log_sweep,
    play_and_record,
    record_room_noise,
    simulate_room_capture,
    write_wav,
)
from .models import CalibrationProfile, SessionConfig


@dataclass(slots=True)
class CalibrationRunArtifacts:
    session_id: str
    profile_path: Path
    playback_signal_path: Path
    captured_signal_path: Path
    noise_signal_path: Path

    def to_dict(self) -> dict[str, str]:
        return {
            "session_id": self.session_id,
            "profile_path": str(self.profile_path),
            "playback_signal_path": str(self.playback_signal_path),
            "captured_signal_path": str(self.captured_signal_path),
            "noise_signal_path": str(self.noise_signal_path),
        }


def run_precalibration(
    project_root: Path,
    config: SessionConfig,
    *,
    dry_run: bool = False,
    input_device: int | str | None = None,
    output_device: int | str | None = None,
) -> CalibrationRunArtifacts:
    sample_rate = config.calibration.sample_rate
    sweep = generate_log_sweep(
        sample_rate=sample_rate,
        duration_seconds=config.calibration.duration_seconds,
    )

    calibration_dir = project_root / "data" / "calibration" / config.session.session_id
    playback_path = calibration_dir / "playback_sweep.wav"
    captured_path = calibration_dir / "captured_sweep.wav"
    noise_path = calibration_dir / "room_noise.wav"
    profile_path = project_root / "artifacts" / "calibration_profiles" / f"{config.session.session_id}.json"

    write_wav(playback_path, sweep, sample_rate)

    if dry_run:
        captured = simulate_room_capture(
            sweep,
            sample_rate,
            latency_ms=57.0,
            frequency_tilt_db=2.4,
            noise_floor=0.0025,
        )
        noise_seed = np.zeros(sample_rate, dtype=np.float32)
        noise = simulate_room_capture(
            noise_seed,
            sample_rate,
            latency_ms=0.0,
            frequency_tilt_db=0.0,
            noise_floor=0.0015,
        )
    else:
        noise = record_room_noise(
            sample_rate=sample_rate,
            duration_seconds=1.0,
            input_device=input_device,
        )
        captured = play_and_record(
            sweep,
            sample_rate,
            input_device=input_device,
            output_device=output_device,
        )

    write_wav(captured_path, captured, sample_rate)
    write_wav(noise_path, noise, sample_rate)

    latency_ms = estimate_latency_ms(sweep, captured, sample_rate)
    frequency_tilt_db = estimate_frequency_tilt_db(sweep, captured, sample_rate)
    noise_floor_dbfs = estimate_noise_floor_dbfs(noise)
    eq_profile = derive_eq_profile(
        frequency_tilt_db,
        max_boost_db=config.compensation.max_eq_boost_db,
        max_cut_db=config.compensation.max_eq_cut_db,
    )

    profile = CalibrationProfile(
        session_id=config.session.session_id,
        room_label=config.session.room_label,
        playback_device_id=str(output_device or config.session.playback_device_id),
        capture_device_id=str(input_device or config.session.capture_device_id),
        latency_ms=latency_ms,
        noise_floor_dbfs=noise_floor_dbfs,
        frequency_tilt_db=frequency_tilt_db,
        eq_profile=eq_profile,
        playback_gain_db=config.calibration.playback_gain_db,
        record_gain_db=config.calibration.record_gain_db,
    )

    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(asdict(profile), ensure_ascii=True, indent=2), encoding="utf-8")

    return CalibrationRunArtifacts(
        session_id=config.session.session_id,
        profile_path=profile_path,
        playback_signal_path=playback_path,
        captured_signal_path=captured_path,
        noise_signal_path=noise_path,
    )
