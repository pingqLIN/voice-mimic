# qwen3-voice-preservation

Local research workspace for consent-based voice preservation built around the upstream Hugging Face Space `PingKuei/Qwen3-TTS`.

This project is scoped for authorized or self-owned voices only. It is not a workspace for impersonation, fraud, or non-consensual voice cloning.

## What is in this repo

- `upstream/Qwen3-TTS/`: mirrored source downloaded from `https://huggingface.co/spaces/PingKuei/Qwen3-TTS`
- `docs/bootstrap-plan.md`: bootstrap architecture decisions
- `docs/voice-preservation-research.md`: research notes on preserving speaker identity effectively
- `docs/roundtrip-experiment-spec.md`: pre-calibration and round-trip optimization spec
- `configs/authorized_speakers.example.yaml`: example registry for consented speakers
- `configs/session_calibration.example.yaml`: example session-level channel calibration config
- `data/consented_voices/`: local storage root for approved reference clips and transcripts
- `data/calibration/`: raw calibration captures for speaker, room, and microphone path checks
- `artifacts/voice_prompts/`: reusable saved prompt files derived from approved samples
- `artifacts/calibration_profiles/`: session-scoped compensation and measurement outputs
- `scripts/sync_space.ps1`: refresh the upstream Space with `hf download`

## Why this structure

The upstream app is a Gradio web surface, but the long-term problem is local orchestration of reference audio, transcripts, saved prompt artifacts, and audit metadata. That makes this a local research helper first, with a secondary web demo surface.

The current upstream code already supports a stronger speaker-preservation path than raw `x-vector` cloning:

- `x_vector_only=true`: keeps only speaker embedding and is lower fidelity
- `x_vector_only=false`: requires exact reference transcript and preserves `ref_code + ref_spk_embedding + ref_text`

That means the first practical milestone is not full fine-tuning. It is building a clean, authorized prompt library per speaker and per speaking style.

## Sync upstream Space

```powershell
pwsh -File .\scripts\sync_space.ps1
```

Requirements:

- `hf` CLI installed
- `hf auth whoami` succeeds

## Run the dry-run controller

```powershell
uv run qwen3-vp `
  --speaker-id demo_speaker_01 `
  --reference-transcript "這是一段人工校正完成的參考文本。" `
  --language zh `
  --json
```

This executes:

1. session precheck
2. pre-calibration profile generation
3. prompt-pack metadata generation
4. one to three round-trip optimization rounds
5. session report export under `artifacts/roundtrip_runs/<session-id>/`

Or run the same controller from a registered reference asset:

```powershell
uv run qwen3-vp `
  --speaker-id demo_speaker_01 `
  --reference-asset-id demo-asset-test `
  --json
```

To use real pre-calibration before the controller loop:

```powershell
uv run qwen3-vp `
  --speaker-id demo_speaker_01 `
  --reference-asset-id demo-asset-test `
  --backend calibrated-dry-run `
  --input-device 24 `
  --output-device 18 `
  --json
```

Add `--calibration-dry-run` if you want to exercise the same path without touching live devices.

## Register an approved reference asset

```powershell
uv run qwen3-vp-assets `
  --speaker-id demo_speaker_01 `
  --audio-path .\samples\demo.wav `
  --transcript "這是一段人工校正完成的參考文本。" `
  --language zh `
  --speaking-style neutral `
  --recording-condition clean_mic `
  --reference-id demo-zh-neutral-001 `
  --json
```

This validates:

1. speaker consent status
2. consent expiration
3. language allowlist
4. transcript presence

Then it stores:

- copied source audio
- transcript text
- reference metadata

under `data/consented_voices/<speaker-id>/<reference-id>/`

## Build a prompt-pack from a registered reference asset

```powershell
uv run qwen3-vp-prompts `
  --speaker-id demo_speaker_01 `
  --reference-id demo-asset-test `
  --model-size 0.6B `
  --prompt-id demo-zh-neutral-icl `
  --json
```

This command:

1. loads the registered asset from `data/consented_voices/...`
2. validates consent status, expiration, and language
3. calls upstream `Qwen3TTSModel.create_voice_clone_prompt(...)`
4. writes a reusable prompt-pack `.pt` and sidecar metadata under `artifacts/voice_prompts/<speaker-id>/`

For real generation, install the upstream runtime dependencies first. The command lazy-loads `torch`, `huggingface_hub`, and the mirrored upstream `qwen_tts` package only when executed.

## List audio devices

```powershell
uv run qwen3-vp-audio-devices
```

## Run session pre-calibration

```powershell
uv run qwen3-vp-calibrate --dry-run --json
```

Remove `--dry-run` to use the default `sounddevice` live backend.

This command:

1. generates a log sweep
2. records room noise
3. plays and captures the sweep, or simulates it in dry-run mode
4. estimates latency, frequency tilt, and noise floor
5. writes a calibration profile under `artifacts/calibration_profiles/`

## Recommended next implementation step

Build a small local prompt-pack workflow that:

1. validates consent metadata
2. stores approved reference audio + transcript pairs
3. generates reusable prompt files from upstream `create_voice_clone_prompt(...)`
4. tags each prompt by language, emotion, recording condition, and intended use

That gives you repeatable voice retention without immediately committing to model fine-tuning per speaker.

After that, implement the session pre-calibration and round-trip scoring loop described in [docs/roundtrip-experiment-spec.md](Q:\Projects\qwen3-voice-preservation\docs\roundtrip-experiment-spec.md).
