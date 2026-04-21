# Round-Trip Experiment Spec

## Scope

This spec is for consent-based voice preservation in a fixed or semi-fixed playback environment.

The goal is to separate two problems before optimization:

- speaker identity preservation
- speaker to room to microphone channel coloration

Do not fold those two into one prompt-generation loop.

## Core decision

Before the first speaker sample is captured, run a session-level calibration pass for:

- speaker response
- room response
- microphone coloration
- latency and synchronization
- noise floor

This is a session-scoped channel model, not a speaker model.

The calibration output may influence:

- playback pre-emphasis or EQ
- record-side normalization
- latency compensation
- dereverb or decolor filtering
- round-trip score normalization

The calibration output must not be written back into:

- `ref_audio`
- `ref_text`
- saved speaker prompt packs
- speaker-specific model weights

## Design rule

Keep two paths separate.

### Path A: speaker identity path

Inputs:

- approved reference speech
- corrected transcript
- optional speaker metadata

Outputs:

- transcript-backed ICL prompt pack
- speaker provenance metadata

This path should remain as clean and original as possible.

### Path B: acoustic channel path

Inputs:

- sweep, chirp, MLS, or pink noise
- playback device position
- target microphone position
- room context

Outputs:

- transfer-function estimate
- latency estimate
- noise estimate
- session compensation profile

This path models the environment, not the person.

## Why pre-calibration comes first

If you skip pre-calibration, the first round-trip sample mixes together:

- TTS prompt quality
- room reflections
- speaker EQ bias
- microphone response
- OS-level AGC, NS, or AEC

That makes the first optimization result ambiguous.

If you calibrate first, the first speaker sample can be interpreted as:

- voice identity capture

instead of:

- voice identity plus environment contamination

## First-pass system flow

### Phase 0: environment pre-check

- verify playback device is fixed
- verify microphone device is fixed
- disable OS or driver AGC, AEC, and noise suppression where possible
- record idle room noise
- store session metadata

### Phase 1: pre-calibration

- play calibration signal
- record returned signal
- align playback and capture
- estimate latency
- estimate end-to-end frequency response
- estimate impulse response or a lighter approximation
- estimate noise floor
- save session calibration profile

### Phase 2: prompt capture

- capture approved speaker reference audio
- run ASR
- require human transcript correction
- build transcript-backed ICL prompt pack
- save prompt pack and metadata

### Phase 3: round-trip synthesis test

- synthesize the same sentence or a controlled target sentence
- apply optional playback compensation from session profile
- play through the target speaker
- record with the target microphone
- align and normalize the returned recording
- score the returned recording against the reference

### Phase 4: outer-loop optimization

- update generation parameters
- update playback compensation
- update post-filter parameters
- run next round

Do not update the prompt pack in this phase.

## Optimization target for the first experiment

The first experiment should test only outer-loop feedback optimization.

Allowed adjustments:

- prompt-pack selection
- generation sampling parameters
- playback compensation filter
- record-side cleanup
- output loudness normalization

Disallowed adjustments in the first experiment:

- rewriting the speaker prompt from round-trip audio
- adding round-trip audio back into `ref_audio`
- speaker-specific fine-tuning
- any weight update on the TTS model

## Scoring functions

Use at least three score families.

### 1. speaker similarity

Compare:

- clean approved reference audio
- round-trip captured synthesized audio

Candidate metric:

- cosine similarity over speaker embeddings

Purpose:

- detect whether identity survives playback and recapture

### 2. intelligibility

Compare:

- intended synthesis text
- ASR transcript of round-trip recorded audio

Candidate metrics:

- WER
- CER

Purpose:

- ensure optimization does not preserve timbre while damaging content

### 3. prosody drift

Compare:

- pitch contour
- speaking rate
- energy envelope

Purpose:

- detect flattening, over-brightening, or timing distortion from channel or compensation

### 4. optional channel residual

Compare:

- expected compensated output
- actual recorded return

Candidate metrics:

- spectral distance
- log-mel distance
- bandwise error

Purpose:

- measure how well the calibration profile is compensating the environment

## Controller policy for v1

Use a bounded controller, not open-ended self-improvement.

Recommended v1 policy:

- max rounds: `3`
- early stop when:
  - speaker similarity stops improving
  - intelligibility starts degrading
  - channel residual improvement becomes marginal

Suggested optimization priority:

1. playback compensation
2. output loudness and normalization
3. prompt-pack selection
4. generation parameters

Do not let the controller mutate all axes at once.

## Data products

### Session calibration profile

Store in:

- `artifacts/calibration_profiles/<session-id>.json`

Fields:

- device ids
- room label
- playback gain
- capture gain
- latency estimate
- frequency-response summary
- noise-floor summary
- compensation settings

### Prompt pack

Store in:

- `artifacts/voice_prompts/<speaker-id>/<prompt-id>.pt`

Fields:

- upstream prompt payload
- speaker id
- transcript hash
- language
- recording condition
- consent scope

### Round-trip run log

Store in:

- `artifacts/roundtrip_runs/<session-id>/<run-id>.json`

Fields:

- prompt id
- calibration profile id
- target text
- generation parameters
- score bundle
- stop decision

## Decision on fine-tuning

Do not introduce speaker-specific fine-tuning until you can answer this clearly:

- after compensation and prompt-pack selection, is the main failure still speaker identity retention

If the answer is no, fine-tuning is the wrong lever.

If the answer is yes, open a separate branch of work for:

- consent review
- training-data size and quality review
- overfitting risk
- anti-misuse controls

That should not be mixed into the first feedback-loop experiment.

## v1 deliverable

The first deliverable should be a controller that can run one full session:

1. calibrate the playback path
2. build one transcript-backed ICL prompt pack
3. run one to three round-trip optimization rounds
4. output score reports and best-known settings

That is enough to decide whether the next investment belongs in:

- better prompt assets
- better channel compensation
- better post-processing
- or speaker-specific adaptation
