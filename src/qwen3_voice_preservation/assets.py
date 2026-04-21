from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from .models import SpeakerRecord, SpeakerRegistry


@dataclass(slots=True)
class ReferenceAsset:
    reference_id: str
    speaker_id: str
    language: str
    speaking_style: str
    recording_condition: str
    audio_path: Path
    transcript_path: Path
    metadata_path: Path
    transcript: str
    notes: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["audio_path"] = str(self.audio_path)
        payload["transcript_path"] = str(self.transcript_path)
        payload["metadata_path"] = str(self.metadata_path)
        return payload


def register_reference_asset(
    project_root: Path,
    registry: SpeakerRegistry,
    *,
    speaker_id: str,
    source_audio_path: Path,
    transcript: str,
    language: str,
    speaking_style: str,
    recording_condition: str,
    notes: str = "",
    reference_id: str | None = None,
) -> ReferenceAsset:
    try:
        speaker = registry.speakers[speaker_id]
    except KeyError as exc:
        raise ValueError(f"Unknown speaker id: {speaker_id}") from exc

    _validate_speaker_for_asset(speaker, language)

    source_audio_path = source_audio_path.resolve()
    if not source_audio_path.exists():
        raise FileNotFoundError(f"Audio source does not exist: {source_audio_path}")
    if not transcript.strip():
        raise ValueError("Transcript must not be empty.")

    asset_id = reference_id or _default_reference_id(language=language, speaking_style=speaking_style)
    asset_dir = project_root / "data" / "consented_voices" / speaker_id / asset_id
    asset_dir.mkdir(parents=True, exist_ok=False)

    audio_target = asset_dir / f"source{source_audio_path.suffix.lower()}"
    transcript_target = asset_dir / "transcript.txt"
    metadata_target = asset_dir / "metadata.json"

    shutil.copy2(source_audio_path, audio_target)
    transcript_target.write_text(transcript.strip() + "\n", encoding="utf-8")

    payload = {
        "reference_id": asset_id,
        "speaker_id": speaker_id,
        "display_name": speaker.display_name,
        "language": language,
        "speaking_style": speaking_style,
        "recording_condition": recording_condition,
        "consent_scope": speaker.consent_scope,
        "consent_expires_on": speaker.consent_expires_on,
        "source_audio_filename": source_audio_path.name,
        "audio_path": str(audio_target.relative_to(project_root)),
        "transcript_path": str(transcript_target.relative_to(project_root)),
        "registered_at": _utc_now(),
        "notes": notes,
    }
    metadata_target.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    return ReferenceAsset(
        reference_id=asset_id,
        speaker_id=speaker_id,
        language=language,
        speaking_style=speaking_style,
        recording_condition=recording_condition,
        audio_path=audio_target,
        transcript_path=transcript_target,
        metadata_path=metadata_target,
        transcript=transcript.strip(),
        notes=notes,
    )


def load_reference_asset(project_root: Path, speaker_id: str, reference_id: str) -> ReferenceAsset:
    asset_dir = project_root / "data" / "consented_voices" / speaker_id / reference_id
    metadata_path = asset_dir / "metadata.json"
    transcript_path = asset_dir / "transcript.txt"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing asset metadata: {metadata_path}")
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    audio_path = project_root / payload["audio_path"]
    return ReferenceAsset(
        reference_id=payload["reference_id"],
        speaker_id=payload["speaker_id"],
        language=payload["language"],
        speaking_style=payload["speaking_style"],
        recording_condition=payload["recording_condition"],
        audio_path=audio_path,
        transcript_path=transcript_path,
        metadata_path=metadata_path,
        transcript=transcript_path.read_text(encoding="utf-8").strip(),
        notes=payload.get("notes", ""),
    )


def _validate_speaker_for_asset(speaker: SpeakerRecord, language: str) -> None:
    if speaker.consent_status.lower() != "approved":
        raise ValueError(f"Speaker {speaker.speaker_id} is not approved.")
    expires_on = date.fromisoformat(speaker.consent_expires_on)
    if expires_on < date.today():
        raise ValueError(f"Speaker {speaker.speaker_id} consent expired on {speaker.consent_expires_on}.")
    if language not in speaker.allowed_languages:
        raise ValueError(
            f"Language {language} is not allowed for speaker {speaker.speaker_id}. "
            f"Allowed: {speaker.allowed_languages}"
        )


def _default_reference_id(*, language: str, speaking_style: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{language}-{_slugify(speaking_style)}-{timestamp}"


def _slugify(value: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    collapsed = "-".join(part for part in normalized.split("-") if part)
    return collapsed or "default"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
