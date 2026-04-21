import json
from dataclasses import dataclass
from pathlib import Path

from qwen3_voice_preservation.assets import register_reference_asset
from qwen3_voice_preservation.config import load_speaker_registry
from qwen3_voice_preservation.prompts import build_prompt_pack_from_reference


@dataclass
class FakePromptItem:
    ref_code: list[int] | None
    ref_spk_embedding: list[float]
    x_vector_only_mode: bool
    icl_mode: bool
    ref_text: str | None


class FakePromptBuilder:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create_voice_clone_prompt(self, *, ref_audio: str, ref_text: str | None, x_vector_only_mode: bool):
        self.calls.append(
            {
                "ref_audio": ref_audio,
                "ref_text": ref_text,
                "x_vector_only_mode": x_vector_only_mode,
            }
        )
        return [
            FakePromptItem(
                ref_code=None if x_vector_only_mode else [1, 2, 3],
                ref_spk_embedding=[0.1, 0.2, 0.3],
                x_vector_only_mode=x_vector_only_mode,
                icl_mode=not x_vector_only_mode,
                ref_text=ref_text,
            )
        ]


class JsonPromptWriter:
    def write(self, payload: dict, output_path: Path) -> None:
        output_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _make_registry(project_root: Path):
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
    return load_speaker_registry(speakers_config)


def test_build_prompt_pack_from_reference_uses_registered_asset(tmp_path: Path):
    project_root = tmp_path
    registry = _make_registry(project_root)
    audio_source = project_root / "sample.wav"
    audio_source.write_bytes(b"RIFFdemo")
    register_reference_asset(
        project_root=project_root,
        registry=registry,
        speaker_id="demo_speaker_01",
        source_audio_path=audio_source,
        transcript="測試逐字稿",
        language="zh",
        speaking_style="neutral",
        recording_condition="clean_mic",
        reference_id="demo-ref",
    )
    builder = FakePromptBuilder()

    artifact = build_prompt_pack_from_reference(
        project_root=project_root,
        registry=registry,
        speaker_id="demo_speaker_01",
        reference_id="demo-ref",
        prompt_id="demo-prompt",
        builder=builder,
        payload_writer=JsonPromptWriter(),
    )

    assert artifact.prompt_path.exists()
    assert artifact.metadata_path.exists()
    payload = json.loads(artifact.prompt_path.read_text(encoding="utf-8"))
    assert payload["items"][0]["icl_mode"] is True
    assert builder.calls[0]["ref_text"] == "測試逐字稿"


def test_build_prompt_pack_x_vector_mode_omits_transcript(tmp_path: Path):
    project_root = tmp_path
    registry = _make_registry(project_root)
    audio_source = project_root / "sample.wav"
    audio_source.write_bytes(b"RIFFdemo")
    register_reference_asset(
        project_root=project_root,
        registry=registry,
        speaker_id="demo_speaker_01",
        source_audio_path=audio_source,
        transcript="測試逐字稿",
        language="zh",
        speaking_style="neutral",
        recording_condition="clean_mic",
        reference_id="demo-ref",
    )
    builder = FakePromptBuilder()

    build_prompt_pack_from_reference(
        project_root=project_root,
        registry=registry,
        speaker_id="demo_speaker_01",
        reference_id="demo-ref",
        prompt_id="demo-prompt-xvec",
        x_vector_only_mode=True,
        builder=builder,
        payload_writer=JsonPromptWriter(),
    )

    assert builder.calls[0]["ref_text"] is None
    assert builder.calls[0]["x_vector_only_mode"] is True
