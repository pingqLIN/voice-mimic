# coding=utf-8
# Qwen3-TTS Gradio Demo for HuggingFace Spaces with Zero GPU
# Supports: Voice Design, Voice Clone (Base), TTS (CustomVoice)
#import subprocess
#subprocess.run('pip install flash-attn==2.7.4.post1', shell=True)
import os
import threading
import spaces
import gradio as gr
import numpy as np
import torch
from huggingface_hub import snapshot_download, login
from qwen_tts import Qwen3TTSModel

# HF_TOKEN = os.environ.get('HF_TOKEN')
# login(token=HF_TOKEN)

# Model size options
MODEL_SIZES = ["0.6B", "1.7B"]

# Speaker and language choices for CustomVoice model
SPEAKERS = [
    "Aiden", "Dylan", "Eric", "Ono_anna", "Ryan", "Serena", "Sohee", "Uncle_fu", "Vivian"
]
LANGUAGES = ["Auto", "Chinese", "English", "Japanese", "Korean", "French", "German", "Spanish", "Portuguese", "Russian"]

UI_HEAD = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&family=Noto+Serif+TC:wght@600;700&display=swap" rel="stylesheet">
<script>
(() => {
  const KEY = "qwen3_tts_theme_mode";
  const root = document.documentElement;
  const systemMode = () => window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  const applyMode = (mode) => {
    root.classList.remove("theme-light", "theme-dark");
    root.classList.add(mode === "dark" ? "theme-dark" : "theme-light");
    const toggle = document.getElementById("theme-toggle");
    if (!toggle) return;
    toggle.textContent = mode === "dark" ? "切換亮色" : "切換暗色";
  };
  const initMode = () => {
    const savedMode = localStorage.getItem(KEY);
    const mode = savedMode === "dark" || savedMode === "light" ? savedMode : systemMode();
    applyMode(mode);
  };
  const bindToggle = () => {
    const toggle = document.getElementById("theme-toggle");
    if (!toggle || toggle.dataset.bound === "1") return;
    toggle.dataset.bound = "1";
    toggle.addEventListener("click", () => {
      const current = root.classList.contains("theme-dark") ? "dark" : "light";
      const next = current === "dark" ? "light" : "dark";
      localStorage.setItem(KEY, next);
      applyMode(next);
    });
  };
  const start = () => {
    initMode();
    bindToggle();
    const observer = new MutationObserver(() => bindToggle());
    observer.observe(document.body, { childList: true, subtree: true });
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
</script>
"""

UI_CSS = """
:root,
:root.theme-light {
  --bg-a: #f2efe9;
  --bg-b: #e9e6de;
  --panel-bg: rgba(255, 253, 249, 0.93);
  --panel-border: rgba(88, 76, 62, 0.14);
  --title: #1e1b18;
  --text: #2e2b26;
  --muted: #706860;
  --primary: #5a7870;
  --primary-strong: #486862;
  --accent: #7a6a52;
  --shadow: 0 8px 28px rgba(72, 62, 48, 0.10);
}

:root.theme-dark {
  --bg-a: #131210;
  --bg-b: #1a1814;
  --panel-bg: rgba(26, 24, 20, 0.92);
  --panel-border: rgba(168, 152, 126, 0.14);
  --title: #f0ece4;
  --text: #ddd8cc;
  --muted: #9a9086;
  --primary: #7a9e92;
  --primary-strong: #8ab0a4;
  --accent: #c4a87a;
  --shadow: 0 10px 34px rgba(0, 0, 0, 0.38);
}

body,
.gradio-container {
  font-family: "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif !important;
  color: var(--text) !important;
  background:
    radial-gradient(ellipse at 15% 18%, color-mix(in oklab, var(--accent) 16%, transparent) 0%, transparent 50%),
    radial-gradient(ellipse at 85% 20%, color-mix(in oklab, var(--primary) 18%, transparent) 0%, transparent 52%),
    linear-gradient(155deg, var(--bg-a), var(--bg-b)) !important;
}

.gradio-container {
  max-width: 1200px !important;
  margin: 0 auto !important;
  padding: 18px 14px 28px !important;
}

.hero-wrap {
  position: relative;
  border: 1px solid var(--panel-border);
  border-radius: 20px;
  background: color-mix(in oklab, var(--panel-bg) 92%, transparent);
  box-shadow: var(--shadow);
  overflow: hidden;
  margin-bottom: 14px;
}

.hero-content { padding: 30px 34px 26px; }
.hero-kicker {
  margin: 0 0 10px;
  font-size: 11px;
  letter-spacing: .14em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 700;
}
.hero-title {
  margin: 0;
  font-family: "Noto Serif TC", serif;
  color: var(--title);
  font-size: clamp(24px, 4vw, 38px);
  line-height: 1.12;
}
.hero-subtitle {
  margin: 10px 0 20px;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.7;
}
.hero-badges { display: flex; flex-wrap: wrap; gap: 7px; }
.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 11px;
  border-radius: 999px;
  border: 1px solid color-mix(in oklab, var(--panel-border) 130%, transparent);
  background: color-mix(in oklab, var(--panel-bg) 75%, transparent);
  color: var(--muted);
  font-size: 11.5px;
  font-weight: 600;
}

#theme-toggle {
  position: absolute;
  top: 14px;
  right: 16px;
  z-index: 10;
  border: 1px solid color-mix(in oklab, var(--accent) 38%, var(--panel-border));
  color: var(--title);
  background: color-mix(in oklab, var(--panel-bg) 80%, transparent);
  border-radius: 999px;
  padding: 8px 16px;
  font-weight: 700;
  font-size: 12px;
  cursor: pointer;
}

.panel-grid { margin-top: 12px; gap: 12px !important; }
.panel {
  border: 1px solid color-mix(in oklab, var(--panel-border) 80%, transparent);
  border-radius: 16px;
  background: color-mix(in oklab, var(--panel-bg) 94%, transparent);
  box-shadow: var(--shadow);
  padding: 18px;
}

.section-title {
  color: var(--title) !important;
  font-family: "Noto Serif TC", serif !important;
}

.section-note {
  margin: 2px 0 10px;
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.55;
}

.footer-tip {
  margin-top: 14px;
  color: var(--muted);
  font-size: 12.5px;
  text-align: center;
}

.gradio-container button.primary,
.gradio-container .synthesize-btn button {
  background: linear-gradient(120deg, var(--primary-strong), var(--primary)) !important;
  border: none !important;
  color: color-mix(in oklab, white 90%, var(--primary)) !important;
  font-weight: 700 !important;
  letter-spacing: .02em;
}

.gradio-container textarea,
.gradio-container input[type="text"] {
  background: color-mix(in oklab, var(--panel-bg) 90%, transparent) !important;
  color: var(--text) !important;
  border: 1px solid color-mix(in oklab, var(--panel-border) 80%, transparent) !important;
}

.gradio-container .tab-nav button.selected {
  color: var(--primary-strong) !important;
  border-bottom: 2px solid var(--primary-strong) !important;
}

@media (max-width: 860px) {
  .hero-content { padding: 20px 20px 24px; }
  #theme-toggle { position: static; margin: 10px 16px 0 auto; display: block; }
}
"""


def get_model_path(model_type: str, model_size: str) -> str:
    """Get model path based on type and size."""
    return snapshot_download(f"Qwen/Qwen3-TTS-12Hz-{model_size}-{model_type}")


# ============================================================================
# LAZY MODEL LOADING - Load models on first use
# ============================================================================
MODEL_LOAD_LOCK = threading.Lock()
VOICE_DESIGN_MODEL = None
BASE_MODELS = {}
CUSTOM_VOICE_MODELS = {}


def _load_model(model_type: str, model_size: str):
    model_id = f"{model_type}:{model_size}"
    print(f"Loading model on demand -> {model_id}")
    return Qwen3TTSModel.from_pretrained(
        get_model_path(model_type, model_size),
        device_map="cuda",
        dtype=torch.bfloat16,
        # token=HF_TOKEN,
        attn_implementation="kernels-community/flash-attn3",
    )


def get_voice_design_model():
    global VOICE_DESIGN_MODEL
    if VOICE_DESIGN_MODEL is None:
        with MODEL_LOAD_LOCK:
            if VOICE_DESIGN_MODEL is None:
                VOICE_DESIGN_MODEL = _load_model("VoiceDesign", "1.7B")
    return VOICE_DESIGN_MODEL


def get_base_model(model_size: str):
    if model_size not in MODEL_SIZES:
        raise ValueError(f"Unsupported model size: {model_size}")
    if model_size not in BASE_MODELS:
        with MODEL_LOAD_LOCK:
            if model_size not in BASE_MODELS:
                BASE_MODELS[model_size] = _load_model("Base", model_size)
    return BASE_MODELS[model_size]


def get_custom_voice_model(model_size: str):
    if model_size not in MODEL_SIZES:
        raise ValueError(f"Unsupported model size: {model_size}")
    if model_size not in CUSTOM_VOICE_MODELS:
        with MODEL_LOAD_LOCK:
            if model_size not in CUSTOM_VOICE_MODELS:
                CUSTOM_VOICE_MODELS[model_size] = _load_model("CustomVoice", model_size)
    return CUSTOM_VOICE_MODELS[model_size]

# ============================================================================


def _normalize_audio(wav, eps=1e-12, clip=True):
    """Normalize audio to float32 in [-1, 1] range."""
    x = np.asarray(wav)

    if np.issubdtype(x.dtype, np.integer):
        info = np.iinfo(x.dtype)
        if info.min < 0:
            y = x.astype(np.float32) / max(abs(info.min), info.max)
        else:
            mid = (info.max + 1) / 2.0
            y = (x.astype(np.float32) - mid) / mid
    elif np.issubdtype(x.dtype, np.floating):
        y = x.astype(np.float32)
        m = np.max(np.abs(y)) if y.size else 0.0
        if m > 1.0 + 1e-6:
            y = y / (m + eps)
    else:
        raise TypeError(f"Unsupported dtype: {x.dtype}")

    if clip:
        y = np.clip(y, -1.0, 1.0)

    if y.ndim > 1:
        y = np.mean(y, axis=-1).astype(np.float32)

    return y


def _audio_to_tuple(audio):
    """Convert Gradio audio input to (wav, sr) tuple."""
    if audio is None:
        return None

    if isinstance(audio, tuple) and len(audio) == 2 and isinstance(audio[0], int):
        sr, wav = audio
        wav = _normalize_audio(wav)
        return wav, int(sr)

    if isinstance(audio, dict) and "sampling_rate" in audio and "data" in audio:
        sr = int(audio["sampling_rate"])
        wav = _normalize_audio(audio["data"])
        return wav, sr

    return None


@spaces.GPU(duration=300)
def generate_voice_design(text, language, voice_description, progress=gr.Progress(track_tqdm=True)):
    """Generate speech using Voice Design model (1.7B only)."""
    if not text or not text.strip():
        return None, "Error: Text is required."
    if not voice_description or not voice_description.strip():
        return None, "Error: Voice description is required."

    try:
        tts = get_voice_design_model()
        wavs, sr = tts.generate_voice_design(
            text=text.strip(),
            language=language,
            instruct=voice_description.strip(),
            non_streaming_mode=True,
            max_new_tokens=2048,
        )
        return (sr, wavs[0]), "Voice design generation completed successfully!"
    except Exception as e:
        return None, f"Error: {type(e).__name__}: {e}"


@spaces.GPU(duration=300)
def generate_voice_clone(ref_audio, ref_text, target_text, language, use_xvector_only, model_size, progress=gr.Progress(track_tqdm=True)):
    """Generate speech using Base (Voice Clone) model."""
    if not target_text or not target_text.strip():
        return None, "Error: Target text is required."

    audio_tuple = _audio_to_tuple(ref_audio)
    if audio_tuple is None:
        return None, "Error: Reference audio is required."

    if not use_xvector_only and (not ref_text or not ref_text.strip()):
        return None, "Error: Reference text is required when 'Use x-vector only' is not enabled."

    try:
        tts = get_base_model(model_size)
        wavs, sr = tts.generate_voice_clone(
            text=target_text.strip(),
            language=language,
            ref_audio=audio_tuple,
            ref_text=ref_text.strip() if ref_text else None,
            x_vector_only_mode=use_xvector_only,
            max_new_tokens=2048,
        )
        return (sr, wavs[0]), "Voice clone generation completed successfully!"
    except Exception as e:
        return None, f"Error: {type(e).__name__}: {e}"


@spaces.GPU(duration=300)
def generate_custom_voice(text, language, speaker, instruct, model_size, progress=gr.Progress(track_tqdm=True)):
    """Generate speech using CustomVoice model."""
    if not text or not text.strip():
        return None, "Error: Text is required."
    if not speaker:
        return None, "Error: Speaker is required."

    try:
        tts = get_custom_voice_model(model_size)
        wavs, sr = tts.generate_custom_voice(
            text=text.strip(),
            language=language,
            speaker=speaker.lower().replace(" ", "_"),
            instruct=instruct.strip() if instruct else None,
            non_streaming_mode=True,
            max_new_tokens=2048,
        )
        return (sr, wavs[0]), "Generation completed successfully!"
    except Exception as e:
        return None, f"Error: {type(e).__name__}: {e}"


# Build Gradio UI
def build_ui():
    with gr.Blocks(
        theme=gr.themes.Base(),
        css=UI_CSS,
        head=UI_HEAD,
        title="Qwen3-TTS Voice Mimic Edition",
    ) as demo:
        gr.HTML(
            """
        <section class="hero-wrap">
          <button id="theme-toggle" type="button">切換暗色</button>
          <div class="hero-content">
            <p class="hero-kicker">Qwen3-TTS · Voice Design · Clone · CustomVoice</p>
            <h1 class="hero-title">Qwen3-TTS　Voice Mimic 風格版</h1>
            <p class="hero-subtitle">
              套用 voice-mimic 設計語言的新介面版本
              支援三種模式：聲線設計、聲音克隆、預設角色 TTS
            </p>
            <div class="hero-badges">
              <span class="hero-badge">🎨 Voice Design</span>
              <span class="hero-badge">🎙️ Voice Clone</span>
              <span class="hero-badge">🔊 CustomVoice</span>
              <span class="hero-badge">⚡ Lazy Loading</span>
            </div>
          </div>
        </section>
        """
        )

        with gr.Tabs():
            with gr.Tab("Voice Design"):
                with gr.Row(elem_classes=["panel-grid"]):
                    with gr.Column(scale=1, elem_classes=["panel"]):
                        gr.Markdown("### ① 聲線描述", elem_classes=["section-title"])
                        gr.HTML("<p class='section-note'>以自然語言描述你想要的說話音色與情緒。</p>")
                        design_text = gr.Textbox(
                            label="Text to Synthesize",
                            lines=4,
                            placeholder="Enter the text you want to convert to speech...",
                            value="It's in the top drawer... wait, it's empty? No way, that's impossible! I'm sure I put it there!"
                        )
                        design_language = gr.Dropdown(
                            label="Language",
                            choices=LANGUAGES,
                            value="Auto",
                            interactive=True,
                        )
                        design_instruct = gr.Textbox(
                            label="Voice Description",
                            lines=3,
                            placeholder="Describe the voice characteristics you want...",
                            value="Speak in an incredulous tone, but with a hint of panic beginning to creep into your voice."
                        )
                        design_btn = gr.Button("Generate with Custom Voice", variant="primary", elem_classes=["synthesize-btn"])

                    with gr.Column(scale=1, elem_classes=["panel"]):
                        gr.Markdown("### ② 產生結果", elem_classes=["section-title"])
                        design_audio_out = gr.Audio(label="Generated Audio", type="numpy")
                        design_status = gr.Textbox(label="Status", lines=2, interactive=False)

                design_btn.click(
                    generate_voice_design,
                    inputs=[design_text, design_language, design_instruct],
                    outputs=[design_audio_out, design_status],
                )

            with gr.Tab("Voice Clone (Base)"):
                with gr.Row(elem_classes=["panel-grid"]):
                    with gr.Column(scale=1, elem_classes=["panel"]):
                        gr.Markdown("### ① 參考聲音", elem_classes=["section-title"])
                        gr.HTML("<p class='section-note'>上傳參考音檔並輸入逐字稿，可提升克隆品質。</p>")
                        clone_ref_audio = gr.Audio(
                            label="Reference Audio (Upload a voice sample to clone)",
                            type="numpy",
                        )
                        clone_ref_text = gr.Textbox(
                            label="Reference Text (Transcript of the reference audio)",
                            lines=2,
                            placeholder="Enter the exact text spoken in the reference audio...",
                        )
                        clone_xvector = gr.Checkbox(
                            label="Use x-vector only (No reference text needed, but lower quality)",
                            value=False,
                        )

                    with gr.Column(scale=1, elem_classes=["panel"]):
                        gr.Markdown("### ② 目標文字與結果", elem_classes=["section-title"])
                        clone_target_text = gr.Textbox(
                            label="Target Text (Text to synthesize with cloned voice)",
                            lines=4,
                            placeholder="Enter the text you want the cloned voice to speak...",
                        )
                        with gr.Row():
                            clone_language = gr.Dropdown(
                                label="Language",
                                choices=LANGUAGES,
                                value="Auto",
                                interactive=True,
                            )
                            clone_model_size = gr.Dropdown(
                                label="Model Size",
                                choices=MODEL_SIZES,
                                value="1.7B",
                                interactive=True,
                            )
                        clone_btn = gr.Button("Clone & Generate", variant="primary", elem_classes=["synthesize-btn"])
                        clone_audio_out = gr.Audio(label="Generated Audio", type="numpy")
                        clone_status = gr.Textbox(label="Status", lines=2, interactive=False)

                clone_btn.click(
                    generate_voice_clone,
                    inputs=[clone_ref_audio, clone_ref_text, clone_target_text, clone_language, clone_xvector, clone_model_size],
                    outputs=[clone_audio_out, clone_status],
                )

            with gr.Tab("TTS (CustomVoice)"):
                with gr.Row(elem_classes=["panel-grid"]):
                    with gr.Column(scale=1, elem_classes=["panel"]):
                        gr.Markdown("### ① 選擇角色與語氣", elem_classes=["section-title"])
                        gr.HTML("<p class='section-note'>選擇內建說話者，並可加入風格指令。</p>")
                        tts_text = gr.Textbox(
                            label="Text to Synthesize",
                            lines=4,
                            placeholder="Enter the text you want to convert to speech...",
                            value="Hello! Welcome to Text-to-Speech system. This is a demo of our TTS capabilities."
                        )
                        with gr.Row():
                            tts_language = gr.Dropdown(
                                label="Language",
                                choices=LANGUAGES,
                                value="English",
                                interactive=True,
                            )
                            tts_speaker = gr.Dropdown(
                                label="Speaker",
                                choices=SPEAKERS,
                                value="Ryan",
                                interactive=True,
                            )
                        with gr.Row():
                            tts_instruct = gr.Textbox(
                                label="Style Instruction (Optional)",
                                lines=2,
                                placeholder="e.g., Speak in a cheerful and energetic tone",
                            )
                            tts_model_size = gr.Dropdown(
                                label="Model Size",
                                choices=MODEL_SIZES,
                                value="1.7B",
                                interactive=True,
                            )
                        tts_btn = gr.Button("Generate Speech", variant="primary", elem_classes=["synthesize-btn"])

                    with gr.Column(scale=1, elem_classes=["panel"]):
                        gr.Markdown("### ② 產生結果", elem_classes=["section-title"])
                        tts_audio_out = gr.Audio(label="Generated Audio", type="numpy")
                        tts_status = gr.Textbox(label="Status", lines=2, interactive=False)

                tts_btn.click(
                    generate_custom_voice,
                    inputs=[tts_text, tts_language, tts_speaker, tts_instruct, tts_model_size],
                    outputs=[tts_audio_out, tts_status],
                )

        gr.HTML(
            "<p class='footer-tip'>提示：首次請求每種模型大小時會進行 lazy loading，等待時間會較長</p>"
        )

    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch()
