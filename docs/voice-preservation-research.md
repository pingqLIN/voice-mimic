# Voice Preservation Research

## Scope

This note is for consent-based voice preservation only.

It does not cover building a system for unauthorized impersonation, bypassing consent, or cloning a specific person's voice without explicit rights to do so.

## What the imported code already tells us

The upstream Space already exposes the critical quality tradeoff in code:

- `x_vector_only_mode=True` uses only the speaker embedding and ignores transcript and reference codec tokens
- `x_vector_only_mode=False` enables ICL mode and requires exact `ref_text`

In `qwen_tts/inference/qwen3_tts_model.py`, the reusable prompt contains:

- `ref_code`
- `ref_spk_embedding`
- `x_vector_only_mode`
- `icl_mode`
- `ref_text`

In `qwen_tts/cli/demo.py`, that prompt is serialized with `torch.save(...)` and later loaded to synthesize new text again. This is the strongest immediate hint for how to "preserve" a speaker profile without touching model weights.

## Practical conclusion

If the goal is to keep a target voice stable across sessions, start with a prompt library, not full fine-tuning.

Why:

- it is already supported by your imported code
- it is fast to regenerate when you improve source samples
- it lets you keep multiple variants of the same speaker
- it reduces risk compared with maintaining one forked model per speaker

## Highest-signal tactics for stronger speaker retention

### 1. Prefer transcript-backed prompts over `x_vector_only`

Your own code path states this directly:

- `x_vector_only`: lower quality, speaker embedding only
- transcript-backed ICL: preserves speaker embedding plus reference code and exact spoken content

Use `x_vector_only` only as a fallback when transcript quality is missing.

### 2. Keep multiple reference prompts per speaker

One prompt file is usually not enough for robust reuse. Store several approved prompt packs per speaker:

- neutral reading
- energetic style
- soft or low-volume delivery
- different languages or accent contexts
- clean mic versus phone mic

Then evaluate which prompt pack matches the desired output best.

### 3. Favor clean reference audio over longer but noisy clips

The imported code resamples and extracts speaker embedding, but noisy reference clips still hurt quality. If you want retention, curate:

- low background noise
- steady microphone distance
- minimal reverb
- accurate transcript
- at least a few stylistically representative samples

### 4. Use multi-reference prompting before per-speaker fine-tuning

Recent zero-shot TTS work points in the same direction:

- Mega-TTS 2 emphasizes multi-reference timbre encoding and prosody modeling for stronger identity preservation from arbitrary prompt sources
- DINO-VITS improves noise robustness and speaker similarity by strengthening the speaker-verification objective

That means your next improvement step should be better prompt construction and evaluation, not immediate checkpoint training.

### 5. Separate voice identity from speaking style

For an operational system, keep two layers:

- identity assets: approved speaker prompt files
- style controls: instruction text, emotional variants, language tags, speaking rate

This avoids mixing "who is speaking" with "how they speak" in one opaque artifact.

## Recommended project roadmap

### Phase 1: assetize approved speakers

- collect approved reference clips
- require exact transcripts
- generate prompt files with ICL mode
- store provenance and consent metadata

### Phase 2: evaluate retention

- build AB listening tests
- score similarity, intelligibility, accent drift, and emotional consistency
- compare single-reference vs multi-reference prompt sets

### Phase 3: decide whether fine-tuning is necessary

Only consider speaker-specific adaptation if prompt packs are still insufficient after:

- clean sample curation
- transcript correction
- multi-reference coverage
- language/style segmentation

## Guardrails you should keep

- only admit speakers with explicit authorization
- keep a registry of consent scope and expiration
- watermark or disclose synthesized output where appropriate
- block public figures, minors, or ambiguous-rights recordings by default
- keep prompt files and raw source audio auditable and separable

## Sources

- Upstream Space: https://hf.co/spaces/PingKuei/Qwen3-TTS
- Official Base model: https://hf.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base
- Official CustomVoice model: https://hf.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
- Mega-TTS 2 paper: https://arxiv.org/abs/2307.07218
- DINO-VITS paper: https://huggingface.co/papers/2311.09770
- Speaker poisoning / protection perspective: https://hf.co/papers/2603.07551
