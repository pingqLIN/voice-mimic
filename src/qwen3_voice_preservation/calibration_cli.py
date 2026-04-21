from __future__ import annotations

import argparse
import json
from pathlib import Path

from .calibration import run_precalibration
from .config import load_session_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run session pre-calibration")
    parser.add_argument("--project-root", default=".", help="Project root path.")
    parser.add_argument(
        "--config",
        default="configs/session_calibration.example.yaml",
        help="Session calibration config path.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Simulate capture instead of using devices.")
    parser.add_argument("--input-device", help="Optional sounddevice input device id or name.")
    parser.add_argument("--output-device", help="Optional sounddevice output device id or name.")
    parser.add_argument("--json", action="store_true", help="Print artifact paths as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    config = load_session_config(project_root / args.config)
    artifacts = run_precalibration(
        project_root=project_root,
        config=config,
        dry_run=args.dry_run,
        input_device=args.input_device,
        output_device=args.output_device,
    )

    if args.json:
        print(json.dumps(artifacts.to_dict(), ensure_ascii=True, indent=2))
    else:
        print(f"session_id: {artifacts.session_id}")
        print(f"profile_path: {artifacts.profile_path}")
        print(f"playback_signal_path: {artifacts.playback_signal_path}")
        print(f"captured_signal_path: {artifacts.captured_signal_path}")
        print(f"noise_signal_path: {artifacts.noise_signal_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
