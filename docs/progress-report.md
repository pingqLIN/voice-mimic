# Repo Progress Report

Date: 2026-04-21

This report summarizes the current state of `qwen3-voice-preservation` based on the files, docs, tests, and recorded artifacts currently present in the workspace.

## 已完成

- Project direction and architecture are defined.
  - The repo is positioned as a local `desktop helper` research workspace with a secondary `Gradio web app` surface.
  - The upstream Hugging Face Space is treated as a mirrored dependency rather than the only product surface.
- The storage and operating structure are already in place.
  - `configs/` is used for consent and session configuration.
  - `data/consented_voices/` stores approved source clips and transcripts.
  - `artifacts/voice_prompts/` stores reusable prompt artifacts.
  - `artifacts/calibration_profiles/` and `artifacts/roundtrip_runs/` store session outputs and experiment results.
- Consent-gated asset handling is implemented.
  - The project includes a path for registering approved reference assets with transcript and metadata validation.
  - Consent status, expiration, transcript presence, and language constraints are part of the current flow.
- Prompt-pack generation is implemented.
  - The repo includes a command path that loads an approved reference asset and builds a reusable prompt-pack through the upstream prompt creation path.
  - This means the project has already moved past pure planning for prompt-backed voice preservation.
- Session pre-calibration and round-trip control logic exist as runnable project code.
  - The CLI surface includes audio-device listing, session calibration, asset registration, prompt generation, and round-trip control entrypoints.
  - The controller logic and supporting data models are covered by tests.
- A demo round-trip run has already been produced.
  - `artifacts/roundtrip_runs/2026-04-20-demo-session/session-report.json` shows a completed multi-round run with bounded controller updates.
  - The recorded metrics indicate improvement across rounds, including higher speaker similarity and lower channel residual.

## 進行中

- The repo is still primarily in research and dry-run validation mode.
  - The workflow is operational, but the project is not yet at a stage where the full real-device and real-generation path appears hardened.
  - README still distinguishes between dry-run usage and the need to install upstream runtime dependencies for real generation.
- The round-trip optimization loop is present, but controller behavior is still being refined.
  - Current update targets still include multiple axes such as playback compensation, prompt-pack selection, and generation parameter tuning.
  - That suggests the optimization policy is functional but still under active evaluation rather than fully locked down.
- Documentation and implementation are slightly out of sync.
  - Some planning documents still describe prompt-pack utilities as the next step, even though that capability now exists in the codebase.
  - The project has progressed from bootstrap planning into prototype execution, but not all docs reflect that shift yet.

## 下一步

- Update the docs so they match the actual implementation state.
  - The most important cleanup is to revise `README.md` and `docs/bootstrap-plan.md` so the listed next step reflects the current prototype stage rather than the earlier scaffold stage.
- Validate the real execution path end to end.
  - Install and verify the upstream runtime dependencies needed for actual prompt-pack generation and synthesis.
  - Confirm that calibration and round-trip flow work reliably outside dry-run mode with real devices.
- Expand the approved reference library.
  - Add more consented speakers, speaking styles, recording conditions, and language variants.
  - Treat prompt-pack coverage as the main short-term lever for identity retention before any speaker-specific fine-tuning discussion.
- Formalize evaluation.
  - Standardize the AB listening workflow and score interpretation for speaker similarity, intelligibility, prosody drift, and channel residual.
  - Use these measurements to decide whether prompt coverage and channel compensation are sufficient.
- Keep identity and environment optimization paths separate.
  - Continue using prompt-packs as clean speaker identity artifacts.
  - Keep acoustic compensation in session calibration outputs rather than feeding round-trip audio back into speaker assets.

## Current Assessment

The repo is beyond the initial planning stage.

The strongest current characterization is:

- completed bootstrap
- implemented consent-gated local research workflow
- implemented prompt-pack and round-trip dry-run prototype
- entering real-runtime validation and experiment-hardening phase

That means the practical next milestone is not designing the system from scratch.

It is making the current prototype reliable under real runtime conditions and turning the evaluation loop into a repeatable research workflow.
