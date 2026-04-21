from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .audio import list_audio_devices


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="List available audio devices")
    parser.add_argument("--json", action="store_true", help="Print device list as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    devices = list_audio_devices()
    if args.json:
        print(json.dumps([asdict(device) for device in devices], ensure_ascii=True, indent=2))
    else:
        for device in devices:
            print(
                f"[{device.index}] {device.name} "
                f"(in={device.max_input_channels}, out={device.max_output_channels}, "
                f"default_sr={device.default_samplerate:.0f})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
