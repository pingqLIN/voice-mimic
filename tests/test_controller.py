from pathlib import Path

from qwen3_voice_preservation.config import load_session_config
from qwen3_voice_preservation.controller import DryRunBackend, RoundTripController
from qwen3_voice_preservation.controller_backends import CalibratedDryRunBackend
from qwen3_voice_preservation.models import (
    PromptCaptureRequest,
    RoundResult,
    ScoreBundle,
    SpeakerRecord,
    UpdatePlan,
)


def _load_config(project_root: Path):
    return load_session_config(project_root / "configs" / "session_calibration.example.yaml")


def _speaker() -> SpeakerRecord:
    return SpeakerRecord(
        speaker_id="demo_speaker_01",
        display_name="Demo Speaker",
        consent_status="approved",
        consent_scope="internal_tts_only",
        consent_expires_on="2027-12-31",
        source_audio_dir="data/consented_voices/demo_speaker_01",
        transcript_required=True,
        preferred_prompt_mode="icl",
        allowed_languages=["zh", "en"],
        notes="",
    )


def test_build_update_plan_prioritizes_playback_compensation(project_root: Path = Path(__file__).resolve().parents[1]):
    config = _load_config(project_root)
    plan = RoundTripController.build_update_plan(
        config=config,
        prior_rounds=[],
        current_scores=ScoreBundle(
            speaker_similarity=0.79,
            cer=0.09,
            prosody_drift=0.18,
            channel_residual=0.24,
        ),
        round_index=1,
    )
    assert plan.targets[0] == "playback_compensation"
    assert "prompt_pack_selection" in plan.targets
    assert "generation_parameters" in plan.targets


def test_evaluate_stop_reason_detects_intelligibility_regression(project_root: Path = Path(__file__).resolve().parents[1]):
    config = _load_config(project_root)
    rounds = [
        RoundResult(
            round_index=1,
            output_path=project_root / "artifacts" / "a.txt",
            captured_path=project_root / "artifacts" / "b.txt",
            scores=ScoreBundle(0.80, 0.05, 0.16, 0.20),
            update_plan=UpdatePlan(round_index=1, targets=["playback_compensation"]),
        ),
        RoundResult(
            round_index=2,
            output_path=project_root / "artifacts" / "c.txt",
            captured_path=project_root / "artifacts" / "d.txt",
            scores=ScoreBundle(0.81, 0.07, 0.15, 0.18),
            update_plan=UpdatePlan(round_index=2, targets=["output_loudness_normalization"]),
        ),
    ]
    stop_reason = RoundTripController.evaluate_stop_reason(config, rounds)
    assert stop_reason.value == "intelligibility_regression"


def test_dry_run_controller_generates_report(project_root: Path = Path(__file__).resolve().parents[1]):
    config = _load_config(project_root)
    controller = RoundTripController(project_root=project_root, backend=DryRunBackend())
    report = controller.run(
        config=config,
        speaker=_speaker(),
        request=PromptCaptureRequest(
            speaker_id="demo_speaker_01",
            reference_transcript="這是一段人工校正完成的參考文本。",
            target_text="這是一段人工校正完成的參考文本。",
            language="zh",
        ),
    )
    assert report.rounds
    assert Path(report.calibration_profile_path).exists()
    assert Path(report.run_log_path).exists()


def test_dry_run_prompt_metadata_tracks_reference_asset_id(project_root: Path = Path(__file__).resolve().parents[1]):
    config = _load_config(project_root)
    controller = RoundTripController(project_root=project_root, backend=DryRunBackend())
    report = controller.run(
        config=config,
        speaker=_speaker(),
        request=PromptCaptureRequest(
            speaker_id="demo_speaker_01",
            reference_transcript="來自已登錄資產的逐字稿。",
            target_text="來自已登錄資產的逐字稿。",
            language="zh",
            reference_asset_id="demo-ref-001",
        ),
    )
    metadata_path = project_root / "artifacts" / "voice_prompts" / "demo_speaker_01" / f"{report.prompt_id}.json"
    assert metadata_path.exists()
    assert '"reference_asset_id": "demo-ref-001"' in metadata_path.read_text(encoding="utf-8")


def test_calibrated_dry_run_backend_uses_generated_profile(project_root: Path = Path(__file__).resolve().parents[1]):
    config = _load_config(project_root)
    backend = CalibratedDryRunBackend(calibration_dry_run=True)
    controller = RoundTripController(project_root=project_root, backend=backend)
    report = controller.run(
        config=config,
        speaker=_speaker(),
        request=PromptCaptureRequest(
            speaker_id="demo_speaker_01",
            reference_transcript="這是校正整合測試。",
            target_text="這是校正整合測試。",
            language="zh",
        ),
    )
    assert Path(report.calibration_profile_path).exists()
    calibration_payload = Path(report.calibration_profile_path).read_text(encoding="utf-8")
    assert '"room_label": "office-desk-a"' in calibration_payload
