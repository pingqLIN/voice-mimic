from __future__ import annotations

import importlib
import json
import sys
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol

from .assets import ReferenceAsset, load_reference_asset
from .models import SpeakerRecord, SpeakerRegistry


class VoicePromptBuilder(Protocol):
    def create_voice_clone_prompt(
        self,
        *,
        ref_audio: str,
        ref_text: str | None,
        x_vector_only_mode: bool,
    ) -> list[object]:
        ...


@dataclass(slots=True)
class PromptPackArtifact:
    prompt_id: str
    speaker_id: str
    reference_id: str
    language: str
    x_vector_only_mode: bool
    prompt_path: Path
    metadata_path: Path
    model_label: str

    def to_dict(self) -> dict[str, object]:
        return {
            "prompt_id": self.prompt_id,
            "speaker_id": self.speaker_id,
            "reference_id": self.reference_id,
            "language": self.language,
            "x_vector_only_mode": self.x_vector_only_mode,
            "prompt_path": str(self.prompt_path),
            "metadata_path": str(self.metadata_path),
            "model_label": self.model_label,
        }


def build_prompt_pack_from_reference(
    project_root: Path,
    registry: SpeakerRegistry,
    *,
    speaker_id: str,
    reference_id: str,
    model_size: str = "0.6B",
    prompt_id: str | None = None,
    x_vector_only_mode: bool = False,
    builder: VoicePromptBuilder | None = None,
    payload_writer: PromptPayloadWriter | None = None,
    model_source: str | None = None,
    device_map: str = "auto",
    dtype: str = "bfloat16",
    attn_implementation: str | None = None,
) -> PromptPackArtifact:
    try:
        speaker = registry.speakers[speaker_id]
    except KeyError as exc:
        raise ValueError(f"Unknown speaker id: {speaker_id}") from exc

    reference = load_reference_asset(project_root, speaker_id, reference_id)
    _validate_speaker_for_prompt(speaker, reference.language)

    active_builder = builder or _load_real_builder(
        project_root=project_root,
        model_size=model_size,
        model_source=model_source,
        device_map=device_map,
        dtype=dtype,
        attn_implementation=attn_implementation,
    )
    items = active_builder.create_voice_clone_prompt(
        ref_audio=str(reference.audio_path),
        ref_text=None if x_vector_only_mode else reference.transcript,
        x_vector_only_mode=x_vector_only_mode,
    )

    prompt_slug = prompt_id or _default_prompt_id(reference, x_vector_only_mode)
    prompt_dir = project_root / "artifacts" / "voice_prompts" / speaker_id
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = prompt_dir / f"{prompt_slug}.pt"
    metadata_path = prompt_dir / f"{prompt_slug}.json"

    payload = {"items": [_serialize_prompt_item(item) for item in items]}
    writer = payload_writer or TorchPromptPayloadWriter()
    writer.write(payload, prompt_path)

    metadata = {
        "prompt_id": prompt_slug,
        "speaker_id": speaker_id,
        "reference_id": reference_id,
        "language": reference.language,
        "reference_audio_path": str(reference.audio_path.relative_to(project_root)),
        "reference_transcript_path": str(reference.transcript_path.relative_to(project_root)),
        "x_vector_only_mode": x_vector_only_mode,
        "model_label": f"Qwen/Qwen3-TTS-12Hz-{model_size}-Base" if model_source is None else model_source,
        "created_at": _utc_now(),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=True, indent=2), encoding="utf-8")

    return PromptPackArtifact(
        prompt_id=prompt_slug,
        speaker_id=speaker_id,
        reference_id=reference_id,
        language=reference.language,
        x_vector_only_mode=x_vector_only_mode,
        prompt_path=prompt_path,
        metadata_path=metadata_path,
        model_label=metadata["model_label"],
    )


class PromptPayloadWriter(Protocol):
    def write(self, payload: dict[str, Any], output_path: Path) -> None:
        ...


class TorchPromptPayloadWriter:
    def write(self, payload: dict[str, Any], output_path: Path) -> None:
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError(
                "torch is required to write real prompt-pack .pt files. "
                "Install the upstream Qwen3-TTS runtime dependencies first."
            ) from exc
        torch.save(payload, output_path)


def _serialize_prompt_item(item: object) -> dict[str, Any]:
    if is_dataclass(item):
        raw = asdict(item)
    elif isinstance(item, dict):
        raw = item
    else:
        raise TypeError(f"Unsupported prompt item type: {type(item)!r}")
    if not isinstance(raw, dict):
        raise TypeError("Serialized prompt item must be a dict.")
    return raw


def _load_real_builder(
    *,
    project_root: Path,
    model_size: str,
    model_source: str | None,
    device_map: str,
    dtype: str,
    attn_implementation: str | None,
) -> VoicePromptBuilder:
    upstream_root = project_root / "upstream" / "Qwen3-TTS"
    if str(upstream_root) not in sys.path:
        sys.path.insert(0, str(upstream_root))

    try:
        import torch
    except ImportError as exc:
        raise RuntimeError(
            "torch is required for real prompt-pack generation. "
            "Install the upstream Qwen3-TTS runtime dependencies first."
        ) from exc

    try:
        snapshot_download = importlib.import_module("huggingface_hub").snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub is required for real prompt-pack generation."
        ) from exc

    qwen_tts = importlib.import_module("qwen_tts")
    model_cls = getattr(qwen_tts, "Qwen3TTSModel")
    model_path = model_source or snapshot_download(f"Qwen/Qwen3-TTS-12Hz-{model_size}-Base")

    dtype_map = {
        "float32": torch.float32,
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
    }
    if dtype not in dtype_map:
        raise ValueError(f"Unsupported dtype: {dtype}. Expected one of {sorted(dtype_map)}")

    kwargs: dict[str, Any] = {
        "device_map": device_map,
        "dtype": dtype_map[dtype],
    }
    if attn_implementation:
        kwargs["attn_implementation"] = attn_implementation
    return model_cls.from_pretrained(model_path, **kwargs)


def _validate_speaker_for_prompt(speaker: SpeakerRecord, language: str) -> None:
    if speaker.consent_status.lower() != "approved":
        raise ValueError(f"Speaker {speaker.speaker_id} is not approved.")
    expires_on = date.fromisoformat(speaker.consent_expires_on)
    if expires_on < date.today():
        raise ValueError(f"Speaker {speaker.speaker_id} consent expired on {speaker.consent_expires_on}.")
    if speaker.allowed_languages and language not in speaker.allowed_languages:
        raise ValueError(
            f"Language {language} is not allowed for speaker {speaker.speaker_id}. "
            f"Allowed: {speaker.allowed_languages}"
        )


def _default_prompt_id(reference: ReferenceAsset, x_vector_only_mode: bool) -> str:
    suffix = "xvec" if x_vector_only_mode else "icl"
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{reference.reference_id}-{suffix}-{timestamp}"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
