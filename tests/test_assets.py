import json
from pathlib import Path

from qwen3_voice_preservation.assets import load_reference_asset, register_reference_asset
from qwen3_voice_preservation.config import load_speaker_registry


def test_register_reference_asset_copies_audio_and_writes_metadata(tmp_path: Path):
    project_root = tmp_path
    (project_root / "configs").mkdir()
    (project_root / "data" / "consented_voices").mkdir(parents=True)
    speakers_config = project_root / "configs" / "speakers.yaml"
    speakers_config.write_text(
        "\n".join(
            [
                "speakers:",
                "  - id: demo_speaker_01",
                "    display_name: Demo Speaker",
                "    consent_status: approved",
                "    consent_scope: internal_tts_only",
                "    consent_expires_on: 2099-12-31",
                "    source_audio_dir: data/consented_voices/demo_speaker_01",
                "    transcript_required: true",
                "    preferred_prompt_mode: icl",
                "    allowed_languages:",
                "      - zh",
            ]
        ),
        encoding="utf-8",
    )
    audio_source = project_root / "sample.wav"
    audio_source.write_bytes(b"RIFFdemo")

    registry = load_speaker_registry(speakers_config)
    asset = register_reference_asset(
        project_root=project_root,
        registry=registry,
        speaker_id="demo_speaker_01",
        source_audio_path=audio_source,
        transcript="測試逐字稿",
        language="zh",
        speaking_style="neutral",
        recording_condition="clean_mic",
        reference_id="demo-001",
    )

    assert asset.audio_path.exists()
    assert asset.transcript_path.read_text(encoding="utf-8").strip() == "測試逐字稿"
    payload = json.loads(asset.metadata_path.read_text(encoding="utf-8"))
    assert payload["reference_id"] == "demo-001"
    assert payload["language"] == "zh"


def test_load_reference_asset_reads_registered_paths(tmp_path: Path):
    project_root = tmp_path
    asset_dir = project_root / "data" / "consented_voices" / "demo_speaker_01" / "demo-001"
    asset_dir.mkdir(parents=True)
    (asset_dir / "source.wav").write_bytes(b"RIFFdemo")
    (asset_dir / "transcript.txt").write_text("測試逐字稿\n", encoding="utf-8")
    (asset_dir / "metadata.json").write_text(
        json.dumps(
            {
                "reference_id": "demo-001",
                "speaker_id": "demo_speaker_01",
                "language": "zh",
                "speaking_style": "neutral",
                "recording_condition": "clean_mic",
                "audio_path": "data/consented_voices/demo_speaker_01/demo-001/source.wav",
                "transcript_path": "data/consented_voices/demo_speaker_01/demo-001/transcript.txt",
                "notes": "",
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )

    asset = load_reference_asset(project_root, "demo_speaker_01", "demo-001")
    assert asset.reference_id == "demo-001"
    assert asset.transcript == "測試逐字稿"
    assert asset.audio_path.exists()


def test_register_reference_asset_rejects_disallowed_language(tmp_path: Path):
    project_root = tmp_path
    (project_root / "configs").mkdir()
    (project_root / "data" / "consented_voices").mkdir(parents=True)
    speakers_config = project_root / "configs" / "speakers.yaml"
    speakers_config.write_text(
        "\n".join(
            [
                "speakers:",
                "  - id: demo_speaker_01",
                "    display_name: Demo Speaker",
                "    consent_status: approved",
                "    consent_scope: internal_tts_only",
                "    consent_expires_on: 2099-12-31",
                "    source_audio_dir: data/consented_voices/demo_speaker_01",
                "    transcript_required: true",
                "    preferred_prompt_mode: icl",
                "    allowed_languages:",
                "      - zh",
            ]
        ),
        encoding="utf-8",
    )
    audio_source = project_root / "sample.wav"
    audio_source.write_bytes(b"RIFFdemo")

    registry = load_speaker_registry(speakers_config)
    try:
        register_reference_asset(
            project_root=project_root,
            registry=registry,
            speaker_id="demo_speaker_01",
            source_audio_path=audio_source,
            transcript="test transcript",
            language="en",
            speaking_style="neutral",
            recording_condition="clean_mic",
            reference_id="demo-001",
        )
    except ValueError as exc:
        assert "not allowed" in str(exc)
    else:
        raise AssertionError("Expected register_reference_asset to reject disallowed language.")
