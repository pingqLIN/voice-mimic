# Bootstrap Plan

## 1. Chosen archetype

Primary archetype: `desktop helper`

Secondary surface: `Gradio web app`

Reasoning:

- the imported upstream project is a browser UI, but your actual product problem is local management of approved voice assets, prompt files, and experiment outputs
- voice preservation requires local durable storage and repeatable orchestration more than a public-facing SaaS structure
- this keeps the repo small while leaving room for a future local UI or internal service wrapper

## 2. Hard requirements that drive the structure

There are no platform packaging constraints equivalent to browser extensions or native desktop bundles yet.

Practical constraints from the upstream app and model code:

- Hugging Face authentication must work for model and Space sync operations
- approved reference audio and transcripts need durable local storage
- saved prompt artifacts are binary files and should be kept separate from source code
- user-facing audio generation must be treated as consent-gated

## 3. Chosen storage model

Primary storage model: `local file storage`

Split:

- `configs/`: consent registry and project config
- `data/consented_voices/`: approved source clips and transcripts
- `artifacts/voice_prompts/`: reusable prompt files produced from approved samples
- `upstream/`: imported upstream source mirror
- `docs/`: research notes and operating constraints

## 4. Chosen repo layout

Minimal local research layout:

- `upstream/Qwen3-TTS/`
- `docs/`
- `configs/`
- `data/consented_voices/`
- `artifacts/voice_prompts/`
- `scripts/`

Python project baseline:

- `pyproject.toml`
- `.python-version`
- `.env.example`
- `.gitignore`

## 5. Key architecture decisions

- use the upstream Space as a mirrored dependency, not as the only place where business logic lives
- treat reusable voice prompt files as first-class artifacts
- keep an explicit authorized-speaker registry instead of dropping random samples into the workspace
- prefer transcript-backed ICL prompts over `x_vector_only` prompts when the goal is stronger speaker identity retention
- defer speaker-specific fine-tuning until prompt-library quality is measured on approved data

## 6. Initial scaffold

- `README.md`
- `docs/bootstrap-plan.md`
- `docs/voice-preservation-research.md`
- `configs/authorized_speakers.example.yaml`
- `scripts/sync_space.ps1`
- `data/consented_voices/.gitkeep`
- `artifacts/voice_prompts/.gitkeep`

## 7. Config files to create

- `pyproject.toml`: Python + uv baseline
- `.python-version`: local Python pin
- `.env.example`: runtime environment placeholders
- `.gitignore`: ignore model caches, prompt binaries, and Python build artifacts

## 8. Next implementation step

Implement a `prompt-pack` utility that converts one approved voice bundle:

- reference wav/flac
- exact transcript
- speaker metadata

into:

- saved prompt file
- provenance metadata
- quick evaluation manifest for AB listening tests

That is the shortest path toward high-retention authorized voice playback.
