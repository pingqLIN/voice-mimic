from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_speaker_registry
from .prompts import build_prompt_pack_from_reference


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a prompt-pack from a registered reference asset")
    parser.add_argument("--project-root", default=".", help="Project root path.")
    parser.add_argument(
        "--speakers-config",
        default="configs/authorized_speakers.example.yaml",
        help="Path to the authorized speaker registry.",
    )
    parser.add_argument("--speaker-id", required=True, help="Authorized speaker id.")
    parser.add_argument("--reference-id", required=True, help="Registered reference asset id.")
    parser.add_argument("--model-size", default="0.6B", help="Qwen3-TTS Base model size.")
    parser.add_argument("--prompt-id", help="Optional explicit prompt id.")
    parser.add_argument("--x-vector-only", action="store_true", help="Build an x-vector-only prompt.")
    parser.add_argument("--model-source", help="Optional local model directory or repo override.")
    parser.add_argument("--device-map", default="auto", help="Model device_map value.")
    parser.add_argument(
        "--dtype",
        default="bfloat16",
        choices=["float32", "float16", "bfloat16"],
        help="Torch dtype for the model.",
    )
    parser.add_argument("--attn-implementation", help="Optional attention implementation override.")
    parser.add_argument("--json", action="store_true", help="Print the prompt artifact as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    registry = load_speaker_registry(project_root / args.speakers_config)
    artifact = build_prompt_pack_from_reference(
        project_root=project_root,
        registry=registry,
        speaker_id=args.speaker_id,
        reference_id=args.reference_id,
        model_size=args.model_size,
        prompt_id=args.prompt_id,
        x_vector_only_mode=args.x_vector_only,
        model_source=args.model_source,
        device_map=args.device_map,
        dtype=args.dtype,
        attn_implementation=args.attn_implementation,
    )

    if args.json:
        print(json.dumps(artifact.to_dict(), ensure_ascii=True, indent=2))
    else:
        print(f"prompt_id: {artifact.prompt_id}")
        print(f"speaker_id: {artifact.speaker_id}")
        print(f"reference_id: {artifact.reference_id}")
        print(f"prompt_path: {artifact.prompt_path}")
        print(f"metadata_path: {artifact.metadata_path}")
        print(f"model_label: {artifact.model_label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
