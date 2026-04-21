from __future__ import annotations

import argparse
import json
from pathlib import Path

from .assets import register_reference_asset
from .config import load_speaker_registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Register authorized reference audio assets")
    parser.add_argument("--project-root", default=".", help="Project root path.")
    parser.add_argument(
        "--speakers-config",
        default="configs/authorized_speakers.example.yaml",
        help="Path to the authorized speaker registry.",
    )
    parser.add_argument("--speaker-id", required=True, help="Authorized speaker id.")
    parser.add_argument("--audio-path", required=True, help="Path to the approved reference audio.")
    transcript_group = parser.add_mutually_exclusive_group(required=True)
    transcript_group.add_argument("--transcript", help="Human-corrected transcript text.")
    transcript_group.add_argument("--transcript-file", help="Path to a transcript text file.")
    parser.add_argument("--language", required=True, help="Language tag, e.g. zh or en.")
    parser.add_argument("--speaking-style", default="neutral", help="Style label for this capture.")
    parser.add_argument(
        "--recording-condition",
        default="clean_mic",
        help="Condition label, e.g. clean_mic or phone_mic.",
    )
    parser.add_argument("--notes", default="", help="Optional free-form notes.")
    parser.add_argument("--reference-id", help="Optional explicit reference id.")
    parser.add_argument("--json", action="store_true", help="Print the registered asset as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    registry = load_speaker_registry(project_root / args.speakers_config)

    transcript = args.transcript
    if args.transcript_file:
        transcript = Path(args.transcript_file).resolve().read_text(encoding="utf-8").strip()

    asset = register_reference_asset(
        project_root=project_root,
        registry=registry,
        speaker_id=args.speaker_id,
        source_audio_path=Path(args.audio_path),
        transcript=transcript,
        language=args.language,
        speaking_style=args.speaking_style,
        recording_condition=args.recording_condition,
        notes=args.notes,
        reference_id=args.reference_id,
    )

    if args.json:
        print(json.dumps(asset.to_dict(), ensure_ascii=True, indent=2))
    else:
        print(f"reference_id: {asset.reference_id}")
        print(f"speaker_id: {asset.speaker_id}")
        print(f"audio_path: {asset.audio_path}")
        print(f"transcript_path: {asset.transcript_path}")
        print(f"metadata_path: {asset.metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
