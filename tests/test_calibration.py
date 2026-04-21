import json
from pathlib import Path

from qwen3_voice_preservation.audio import generate_log_sweep
from qwen3_voice_preservation.calibration import run_precalibration
from qwen3_voice_preservation.config import load_session_config


def test_generate_log_sweep_returns_expected_length():
    sweep = generate_log_sweep(sample_rate=48_000, duration_seconds=2)
    expected = int(48_000 * (2 + 0.25 + 0.75))
    assert len(sweep) == expected


def test_run_precalibration_dry_run_writes_profile_and_audio(tmp_path: Path):
    project_root = tmp_path
    (project_root / "configs").mkdir()
    (project_root / "data").mkdir()
    (project_root / "artifacts").mkdir()
    config_path = project_root / "configs" / "session.yaml"
    config_path.write_text(
        "\n".join(
            [
                "session:",
                "  session_id: test-session",
                "  room_label: desk",
                "  playback_device_id: default-speaker",
                "  capture_device_id: default-microphone",
                "  agc_disabled: true",
                "  aec_disabled: true",
                "  noise_suppression_disabled: true",
                "calibration:",
                "  signal_type: log_sine_sweep",
                "  sample_rate: 48000",
                "  duration_seconds: 2",
                "  playback_gain_db: -9.0",
                "  record_gain_db: 0.0",
                "  repetitions: 2",
                "compensation:",
                "  enable_latency_compensation: true",
                "  enable_eq_compensation: true",
                "  enable_dereverb: false",
                "  max_eq_boost_db: 6.0",
                "  max_eq_cut_db: 12.0",
                "roundtrip_experiment:",
                "  max_rounds: 3",
                "  fixed_prompt_mode: transcript_backed_icl",
                "  allow_prompt_regeneration_from_roundtrip_audio: false",
                "  allow_model_finetuning: false",
                "  target_metrics:",
                "    min_speaker_similarity: 0.82",
                "    max_cer: 0.08",
                "    max_prosody_drift: 0.15",
            ]
        ),
        encoding="utf-8",
    )

    config = load_session_config(config_path)
    artifacts = run_precalibration(project_root, config, dry_run=True)

    assert artifacts.profile_path.exists()
    assert artifacts.playback_signal_path.exists()
    assert artifacts.captured_signal_path.exists()
    profile = json.loads(artifacts.profile_path.read_text(encoding="utf-8"))
    assert profile["session_id"] == "test-session"
    assert "eq_profile" in profile
