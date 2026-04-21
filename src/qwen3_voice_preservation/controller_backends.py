from __future__ import annotations

import json
from pathlib import Path

from .calibration import run_precalibration
from .controller import DryRunBackend
from .models import CalibrationProfile, SessionConfig, SpeakerRecord


class CalibratedDryRunBackend(DryRunBackend):
    def __init__(
        self,
        *,
        calibration_dry_run: bool = False,
        input_device: int | str | None = None,
        output_device: int | str | None = None,
    ) -> None:
        super().__init__()
        self.calibration_dry_run = calibration_dry_run
        self.input_device = input_device
        self.output_device = output_device

    def precheck(self, config: SessionConfig, speaker: SpeakerRecord) -> list[str]:
        warnings = super().precheck(config, speaker)
        if self.calibration_dry_run:
            warnings.append("Calibration is running in dry-run mode.")
        else:
            warnings.append("Calibration uses the live sounddevice backend.")
        return warnings

    def calibrate(self, config: SessionConfig, project_root: Path) -> CalibrationProfile:
        artifacts = run_precalibration(
            project_root=project_root,
            config=config,
            dry_run=self.calibration_dry_run,
            input_device=self.input_device,
            output_device=self.output_device,
        )
        raw = json.loads(artifacts.profile_path.read_text(encoding="utf-8"))
        return CalibrationProfile(
            session_id=raw["session_id"],
            room_label=raw["room_label"],
            playback_device_id=raw["playback_device_id"],
            capture_device_id=raw["capture_device_id"],
            latency_ms=float(raw["latency_ms"]),
            noise_floor_dbfs=float(raw["noise_floor_dbfs"]),
            frequency_tilt_db=float(raw["frequency_tilt_db"]),
            eq_profile={str(k): float(v) for k, v in raw["eq_profile"].items()},
            playback_gain_db=float(raw["playback_gain_db"]),
            record_gain_db=float(raw["record_gain_db"]),
        )
