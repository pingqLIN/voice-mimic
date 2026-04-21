from __future__ import annotations

import argparse
import json
from pathlib import Path

from .assets import load_reference_asset
from .config import load_session_config, load_speaker_registry
from .controller import DryRunBackend, RoundTripController
from .controller_backends import CalibratedDryRunBackend
from .models import PromptCaptureRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Consent-based voice preservation controller")
    parser.add_argument(
        "--config",
        default="configs/session_calibration.example.yaml",
        help="Path to the session calibration config.",
    )
    parser.add_argument(
        "--speakers-config",
        default="configs/authorized_speakers.example.yaml",
        help="Path to the authorized speaker registry.",
    )
    parser.add_argument("--speaker-id", required=True, help="Authorized speaker id.")
    transcript_group = parser.add_mutually_exclusive_group(required=True)
    transcript_group.add_argument("--reference-transcript", help="Human-corrected transcript.")
    transcript_group.add_argument(
        "--reference-asset-id",
        help="Registered reference asset id under data/consented_voices/<speaker-id>/",
    )
    parser.add_argument("--target-text", help="Synthesis target text. Defaults to the reference transcript.")
    parser.add_argument("--language", default="zh", help="Target language tag.")
    parser.add_argument(
        "--backend",
        default="dry-run",
        choices=["dry-run", "calibrated-dry-run"],
        help="Controller backend implementation.",
    )
    parser.add_argument(
        "--calibration-dry-run",
        action="store_true",
        help="Use simulated capture during calibration when backend=calibrated-dry-run.",
    )
    parser.add_argument("--input-device", help="Optional sounddevice input device id or name.")
    parser.add_argument("--output-device", help="Optional sounddevice output device id or name.")
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root where artifacts and configs are located.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the final session report as JSON.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    config = load_session_config(project_root / args.config)
    registry = load_speaker_registry(project_root / args.speakers_config)

    try:
        speaker = registry.speakers[args.speaker_id]
    except KeyError as exc:
        raise SystemExit(f"Unknown speaker id: {args.speaker_id}") from exc

    reference_transcript = args.reference_transcript
    language = args.language
    if args.reference_asset_id:
        asset = load_reference_asset(project_root, args.speaker_id, args.reference_asset_id)
        reference_transcript = asset.transcript
        language = asset.language

    target_text = args.target_text or reference_transcript
    request = PromptCaptureRequest(
        speaker_id=args.speaker_id,
        reference_transcript=reference_transcript,
        target_text=target_text,
        language=language,
        reference_asset_id=args.reference_asset_id,
    )

    backend = _build_backend(args)
    controller = RoundTripController(project_root=project_root, backend=backend)
    report = controller.run(config=config, speaker=speaker, request=request)

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=True, indent=2))
    else:
        print(f"session_id: {report.session_id}")
        print(f"speaker_id: {report.speaker_id}")
        print(f"prompt_id: {report.prompt_id}")
        print(f"stop_reason: {report.stop_reason.value}")
        print(f"calibration_profile: {report.calibration_profile_path}")
        print(f"run_log: {report.run_log_path}")
        for item in report.rounds:
            print(
                f"round {item.round_index}: "
                f"sim={item.scores.speaker_similarity:.3f}, "
                f"cer={item.scores.cer:.3f}, "
                f"prosody={item.scores.prosody_drift:.3f}, "
                f"residual={item.scores.channel_residual:.3f}, "
                f"targets={','.join(item.update_plan.targets)}"
            )

    return 0


def _build_backend(args: argparse.Namespace):
    if args.backend == "dry-run":
        return DryRunBackend()
    return CalibratedDryRunBackend(
        calibration_dry_run=bool(args.calibration_dry_run),
        input_device=args.input_device,
        output_device=args.output_device,
    )


if __name__ == "__main__":
    raise SystemExit(main())
