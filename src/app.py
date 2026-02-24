import gradio as gr
import os
import requests
import base64
import pathlib
import threading
import tempfile
import certifi
from dashscope.audio.qwen_tts_realtime import QwenTtsRealtime, QwenTtsRealtimeCallback, AudioFormat
import dashscope
import wave

try:
    import pyttsx3
except Exception:
    pyttsx3 = None

try:
    import edge_tts as _edge_tts_module
except Exception:
    _edge_tts_module = None


def _run_edge_tts(text: str, voice: str, output_path: str):
    """Run edge-tts synthesis in an isolated thread+event loop (Gradio-safe)."""
    import asyncio
    import threading
    import edge_tts

    async def _synth():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)

    exc_holder = []

    def _worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_synth())
        except Exception as e:
            exc_holder.append(e)
        finally:
            loop.close()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=90)
    if t.is_alive():
        raise TimeoutError("edge-tts 合成逾時（90 秒）")
    if exc_holder:
        raise exc_holder[0]

# ======= Constants Configuration =======
DEFAULT_TARGET_MODEL = "qwen3-tts-vc-realtime-2025-11-27"
DEFAULT_PREFERRED_NAME = "custom_voice"
DEFAULT_AUDIO_MIME_TYPE = "audio/wav"
DEFAULT_CN_HTTP_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
DEFAULT_INTL_HTTP_URL = "https://dashscope-us.aliyuncs.com/compatible-mode/v1"
DEFAULT_CN_WS_URL = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"
DEFAULT_INTL_WS_URL = "wss://dashscope-us.aliyuncs.com/api-ws/v1/realtime"

# ── Standard TTS（非 Realtime） ──
QWEN3_TTS_FLASH_MODEL    = "qwen3-tts-flash"
QWEN3_TTS_INSTRUCT_MODEL = "qwen3-tts-instruct-flash"
QWEN3_TTS_VD_MODEL       = "qwen3-tts-vd"
QWEN_VOICE_DESIGN_MODEL  = "qwen-voice-design"

# Base hosts for standard (non-compatible-mode) API
_TTS_API_HOST_CN   = "https://dashscope-intl.aliyuncs.com"
_TTS_API_HOST_INTL = "https://dashscope-us.aliyuncs.com"
_TTS_GENERATION_PATH     = "/api/v1/services/aigc/multimodal-generation/generation"
_TTS_CUSTOMIZATION_PATH  = "/api/v1/services/audio/tts/customization"

# Preset voices (Qwen3-TTS CustomVoice – 9 timbres)
_PRESET_VOICES = [
    "Serena — 溫柔少女音",
    "Vivian — 清爽少女音",
    "Ryan — 活力英語男聲",
    "Aiden — 陽光美式男聲",
    "Eric — 活力成都男聲",
    "Dylan — 青春北京男聲",
    "Uncle_Fu — 渾厚中年男聲",
    "Ono_Anna — 俏皮日語女聲",
    "Sohee — 韓語女聲",
]

# Local TTS model options shown in the UI dropdown
_LOCAL_TTS_MODELS = [
    "espeak-ng（離線）",
    "edge-tts — zh-TW-HsiaoChenNeural（繁中女）",
    "edge-tts — zh-TW-YunJheNeural（繁中男）",
    "edge-tts — zh-CN-XiaoxiaoNeural（普通話女）",
    "edge-tts — zh-CN-YunxiNeural（普通話男）",
    "edge-tts — en-US-JennyNeural（英文女）",
]

UI_HEAD = """
<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">
<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>
<link href=\"https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&family=Noto+Serif+TC:wght@600;700&display=swap\" rel=\"stylesheet\">
<script>
(() => {
  const KEY = \"qwen_tts_theme_mode\";
  const root = document.documentElement;
  const systemMode = () => window.matchMedia(\"(prefers-color-scheme: dark)\").matches ? \"dark\" : \"light\";

  const applyMode = (mode) => {
    root.classList.remove(\"theme-light\", \"theme-dark\");
    root.classList.add(mode === \"dark\" ? \"theme-dark\" : \"theme-light\");
    const toggle = document.getElementById(\"theme-toggle\");
    if (!toggle) return;
    if (mode === \"dark\") {
      toggle.textContent = \"切換亮色\";
      toggle.setAttribute(\"aria-label\", \"目前暗色主題，點擊切換亮色\");
    } else {
      toggle.textContent = \"切換暗色\";
      toggle.setAttribute(\"aria-label\", \"目前亮色主題，點擊切換暗色\");
    }
  };

  const initMode = () => {
    const savedMode = localStorage.getItem(KEY);
    const mode = savedMode === \"dark\" || savedMode === \"light\" ? savedMode : systemMode();
    applyMode(mode);
  };

  const bindToggle = () => {
    const toggle = document.getElementById(\"theme-toggle\");
    if (!toggle || toggle.dataset.bound === \"1\") return;
    toggle.dataset.bound = \"1\";
    toggle.addEventListener(\"click\", () => {
      const current = root.classList.contains(\"theme-dark\") ? \"dark\" : \"light\";
      const next = current === \"dark\" ? \"light\" : \"dark\";
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

  if (document.readyState === \"loading\") {
    document.addEventListener(\"DOMContentLoaded\", start);
  } else {
    start();
  }
})();
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
  font-family: \"Noto Sans TC\", \"PingFang TC\", \"Microsoft JhengHei\", sans-serif !important;
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

/* ── Hero wrap ── */
.hero-wrap {
  position: relative;
  border: 1px solid var(--panel-border);
  border-radius: 20px;
  background: color-mix(in oklab, var(--panel-bg) 92%, transparent);
  box-shadow: var(--shadow);
  overflow: hidden;
  margin-bottom: 14px;
  animation: rise-in .30s ease-out both;
}

.hero-content {
  padding: 32px 36px 28px;
}

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
  font-family: \"Noto Serif TC\", serif;
  color: var(--title);
  font-size: clamp(24px, 4vw, 38px);
  line-height: 1.12;
  letter-spacing: .01em;
}

.hero-subtitle {
  margin: 10px 0 20px;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.7;
}

.hero-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

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
  letter-spacing: .015em;
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
  transition: transform .15s ease, box-shadow .20s ease;
}

#theme-toggle:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px color-mix(in oklab, var(--accent) 22%, transparent);
}

#theme-toggle:active { transform: translateY(0); }

/* ── Panels ── */
.panel-grid { margin-top: 12px; gap: 12px !important; }

.panel {
  border: 1px solid color-mix(in oklab, var(--panel-border) 80%, transparent);
  border-radius: 16px;
  background: color-mix(in oklab, var(--panel-bg) 94%, transparent);
  box-shadow: var(--shadow);
  padding: 18px;
  animation: rise-in .26s ease-out both;
}

.panel h3, .section-title, .section-title h3, .section-title p {
  margin-top: 0 !important;
  margin-bottom: 8px !important;
  color: var(--title) !important;
  font-family: \"Noto Serif TC\", serif !important;
  font-size: 15px !important;
}

.section-note {
  margin: 2px 0 10px;
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.55;
}

/* ── Audio tab buttons (mic / upload) ── */
.gradio-container [role=\"tab\"] {
  color: var(--text) !important;
  font-weight: 600 !important;
}
.gradio-container [role=\"tab\"][aria-selected=\"true\"] {
  color: var(--primary-strong) !important;
  border-bottom-color: var(--primary-strong) !important;
}

.footer-tip {
  margin-top: 14px;
  color: var(--muted);
  font-size: 12.5px;
  text-align: center;
}

/* ── Forms ── */
.gradio-container textarea,
.gradio-container input,
.gradio-container .wrap {
  font-family: \"Noto Sans TC\", \"PingFang TC\", \"Microsoft JhengHei\", sans-serif !important;
}

.gradio-container textarea,
.gradio-container input[type=\"text\"] {
  background: color-mix(in oklab, var(--panel-bg) 90%, transparent) !important;
  color: var(--text) !important;
  border: 1px solid color-mix(in oklab, var(--panel-border) 80%, transparent) !important;
  transition: border-color .18s ease, box-shadow .18s ease !important;
}

.gradio-container textarea:focus,
.gradio-container input[type=\"text\"]:focus {
  border-color: color-mix(in oklab, var(--primary) 60%, var(--panel-border)) !important;
  box-shadow: 0 0 0 3px color-mix(in oklab, var(--primary) 12%, transparent) !important;
  outline: none !important;
}

/* ── Buttons ── */
.gradio-container button.primary,
.gradio-container .synthesize-btn button {
  background: linear-gradient(120deg, var(--primary-strong), var(--primary)) !important;
  border: none !important;
  color: color-mix(in oklab, white 90%, var(--primary)) !important;
  font-weight: 700 !important;
  letter-spacing: .02em;
  box-shadow: 0 8px 20px color-mix(in oklab, var(--primary) 28%, transparent);
  transition: transform .15s ease, box-shadow .20s ease !important;
}

.gradio-container button.primary:hover,
.gradio-container .synthesize-btn button:hover {
  transform: translateY(-1px) !important;
  box-shadow: 0 12px 28px color-mix(in oklab, var(--primary) 38%, transparent) !important;
}

.gradio-container button.primary:active,
.gradio-container .synthesize-btn button:active {
  transform: translateY(0) !important;
}

.gradio-container .label-wrap span,
.gradio-container .label-wrap { color: var(--title) !important; font-weight: 600 !important; }

/* ── Animations ── */
@keyframes rise-in {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ── Tabs ── */
.gradio-container .tab-nav {
  border-bottom: 1px solid color-mix(in oklab, var(--panel-border) 120%, transparent) !important;
  gap: 4px !important;
  padding: 0 4px !important;
}
.gradio-container .tab-nav button {
  color: var(--muted) !important;
  font-weight: 600 !important;
  font-size: 13px !important;
  border-radius: 8px 8px 0 0 !important;
  padding: 8px 18px !important;
  transition: color .15s ease, background .15s ease !important;
  border: none !important;
  background: transparent !important;
}
.gradio-container .tab-nav button:hover {
  color: var(--text) !important;
  background: color-mix(in oklab, var(--primary) 8%, transparent) !important;
}
.gradio-container .tab-nav button.selected {
  color: var(--primary-strong) !important;
  background: color-mix(in oklab, var(--primary) 10%, transparent) !important;
  border-bottom: 2px solid var(--primary-strong) !important;
}

@media (max-width: 860px) {
  .hero-content { padding: 20px 20px 24px; }
  #theme-toggle { position: static; margin: 10px 16px 0 auto; display: block; }
}
"""

def get_dashscope_api_key_from_colab() -> str:
    """Try loading DashScope API key from Colab Secrets."""
    try:
        from google.colab import userdata
    except Exception:
        return ""

    configured_name = os.getenv("DASHSCOPE_SECRET_NAME", "DASHSCOPE_API_KEY")
    candidates = [configured_name, "DASHSCOPE_API_KEY", "API_KEY", "secretName"]
    seen = set()
    for secret_name in candidates:
        if secret_name in seen:
            continue
        seen.add(secret_name)
        try:
            value = userdata.get(secret_name)
        except Exception:
            value = None
        if value:
            return value.strip()
    return ""

def get_dashscope_api_key() -> str:
    """Read DashScope API key from env vars, then Colab Secrets."""
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("API_KEY")
    if not api_key:
        api_key = get_dashscope_api_key_from_colab()
        if api_key:
            # Reuse the same key for downstream libs expecting env vars.
            os.environ["DASHSCOPE_API_KEY"] = api_key
            os.environ["API_KEY"] = api_key
    if not api_key:
        raise ValueError(
            "請設定 DASHSCOPE_API_KEY（或 API_KEY），"
            "或在 Colab Secrets 建立對應鍵名（預設 DASHSCOPE_API_KEY）。"
            "若是 Colab 終端機直接啟動，請優先使用 export 設定環境變數。"
        )
    # Common confusion: Alibaba AccessKey pair is not DashScope API Key.
    if api_key.startswith("LTAI") and ":" in api_key:
        raise ValueError(
            "偵測到 AccessKeyId:AccessKeySecret 格式（LTAI...:...）。"
            "請改用 DashScope API Key（通常在百鍊/Model Studio 的 API-KEY 頁建立）。"
        )
    return api_key

def init_dashscope_api_key():
    """Initialize the API key for dashscope SDK"""
    api_key = get_dashscope_api_key()
    dashscope.api_key = api_key
    return api_key

def get_dashscope_endpoint_candidates():
    """Return endpoint candidates in fallback order."""
    custom_http = os.getenv("DASHSCOPE_HTTP_URL")
    custom_ws = os.getenv("DASHSCOPE_WS_URL")
    candidates = []
    if custom_http:
        candidates.append((custom_http, custom_ws or DEFAULT_CN_WS_URL))
    elif custom_ws:
        candidates.append((DEFAULT_CN_HTTP_URL, custom_ws))
    candidates.extend([
        (DEFAULT_CN_HTTP_URL, DEFAULT_CN_WS_URL),
        (DEFAULT_INTL_HTTP_URL, DEFAULT_INTL_WS_URL),
    ])

    dedup = []
    seen = set()
    for http_url, ws_url in candidates:
        key = (http_url, ws_url)
        if key in seen:
            continue
        seen.add(key)
        dedup.append(key)
    return dedup

def is_ssl_or_transport_error(err: Exception) -> bool:
    """Identify transient SSL/transport errors worth retrying on another endpoint."""
    text = str(err).lower()
    keywords = [
        "ssl",
        "tls",
        "eof occurred in violation of protocol",
        "ssleoferror",
        "proxyerror",
        "connection reset",
        "max retries exceeded",
        "network is unreachable",
    ]
    return any(k in text for k in keywords)


def is_endpoint_fallback_error(err: Exception) -> bool:
    """Errors that should trigger trying another DashScope endpoint."""
    if is_ssl_or_transport_error(err):
        return True
    text = str(err).lower()
    return "401 invalidapikey" in text or "dashscope 驗證失敗" in text

def create_voice(file_path: str,
                 target_model: str = DEFAULT_TARGET_MODEL,
                 preferred_name: str = DEFAULT_PREFERRED_NAME,
                 audio_mime_type: str = DEFAULT_AUDIO_MIME_TYPE,
                 customization_url: str = DEFAULT_CN_HTTP_URL) -> str:
    """Create voice and return the voice parameter"""
    api_key = get_dashscope_api_key()

    file_path_obj = pathlib.Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"找不到音訊檔案：{file_path}")

    base64_str = base64.b64encode(file_path_obj.read_bytes()).decode()
    data_uri = f"data:{audio_mime_type};base64,{base64_str}"

    payload = {
        "model": "qwen-voice-enrollment",
        "input": {
            "action": "create",
            "target_model": target_model,
            "preferred_name": preferred_name,
            "audio": {"data": data_uri}
        }
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Connection": "close",
    }

    # Create session and configure retry and SSL
    session = requests.Session()
    session.verify = certifi.where()

    # Configure retry strategy
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    try:
        resp = session.post(customization_url, json=payload, headers=headers, timeout=(15, 60))
        if resp.status_code != 200:
            if resp.status_code == 401:
                raise RuntimeError(
                    "DashScope 驗證失敗（401 InvalidApiKey）。"
                    "請確認你設定的是 DashScope API Key，而不是 AccessKeyId:AccessKeySecret。"
                )
            raise RuntimeError(f"建立聲音分身失敗：{resp.status_code}, {resp.text}")

        return resp.json()["output"]["voice"]
    except requests.exceptions.SSLError as e:
        raise RuntimeError(f"SSL 連線錯誤：{e}")
    except requests.exceptions.Timeout as e:
        raise RuntimeError(f"請求逾時：{e}")
    except (KeyError, ValueError) as e:
        raise RuntimeError(f"解析聲音分身回應失敗：{e}")
    finally:
        session.close()

class TTSCallback(QwenTtsRealtimeCallback):
    """TTS streaming callback for collecting audio data"""
    def __init__(self):
        self.complete_event = threading.Event()
        self.audio_chunks = []
        self.error_msg = None

    def on_open(self) -> None:
        print('[TTS] 已建立連線')

    def on_close(self, close_status_code, close_msg) -> None:
        print(f'[TTS] 連線關閉 code={close_status_code}, msg={close_msg}')

    def on_event(self, response: dict) -> None:
        try:
            event_type = response.get('type', '')
            if event_type == 'session.created':
                print(f'[TTS] 工作階段開始：{response["session"]["id"]}')
            elif event_type == 'response.audio.delta':
                audio_data = base64.b64decode(response['delta'])
                self.audio_chunks.append(audio_data)
            elif event_type == 'response.done':
                print('[TTS] 回應完成')
            elif event_type == 'session.finished':
                print('[TTS] 工作階段結束')
                self.complete_event.set()
        except Exception as e:
            self.error_msg = str(e)
            print(f'[錯誤] 處理 callback event 發生例外：{e}')
            self.complete_event.set()

    def wait_for_finished(self):
        self.complete_event.wait()

    def get_audio_data(self):
        """Return the synthesized audio data"""
        return b''.join(self.audio_chunks)

def normalize_segment_text(text_input: str) -> str:
    """Normalize segment editor content by trimming empty lines."""
    segments = [line.strip() for line in text_input.splitlines() if line.strip()]
    return "\n".join(segments)

def synthesize_speech_remote(audio_file, reference_text, text_input,
                            use_xvector_only: bool = False,
                            language: str = "Auto",
                            api_key_override: str = ""):
    """
    Main function for speech synthesis (Voice Clone mode).

    Args:
        audio_file: Path to the reference audio file.
        reference_text: Transcript of the reference audio (skipped when use_xvector_only=True).
        text_input: Target text to synthesize with the cloned voice.
        use_xvector_only: If True, skip reference_text and use x-vector only (lower quality).
        language: Target language hint (Auto / Chinese / English / …).
        api_key_override: API key entered directly in UI; overrides env var if provided.

    Returns:
        Tuple of (audio_path, status_message)
    """
    try:
        if not audio_file:
            return None, "❌ 請先上傳或錄製參考聲音"

        normalized_text = normalize_segment_text(text_input or "")
        if not normalized_text:
            return None, "❌ 請先輸入要合成的文字"

        if not use_xvector_only and (not reference_text or not reference_text.strip()):
            return None, "❌ 請輸入參考聲音逐字稿（或勾選『僅使用 X-vector』以跳過）"

        # API key: UI input takes priority over env var
        if api_key_override and api_key_override.strip():
            key = api_key_override.strip()
            dashscope.api_key = key
            os.environ["DASHSCOPE_API_KEY"] = key
        else:
            init_dashscope_api_key()

        endpoint_candidates = get_dashscope_endpoint_candidates()
        last_error = None
        voice_id = None
        qwen_tts_realtime = None
        callback = None

        for idx, (customization_url, ws_url) in enumerate(endpoint_candidates, start=1):
            try:
                # Create voice clone
                status_msg = f"🎤 正在建立聲音分身（端點 {idx}/{len(endpoint_candidates)}）..."
                print(status_msg)
                voice_id = create_voice(
                    audio_file,
                    audio_mime_type="audio/wav",
                    customization_url=customization_url
                )

                # Initialize TTS
                status_msg = f"🔊 正在合成語音（端點 {idx}/{len(endpoint_candidates)}）..."
                print(status_msg)
                callback = TTSCallback()
                qwen_tts_realtime = QwenTtsRealtime(
                    model=DEFAULT_TARGET_MODEL,
                    callback=callback,
                    url=ws_url
                )
                qwen_tts_realtime.connect()
                break
            except Exception as e:
                last_error = e
                if is_endpoint_fallback_error(e):
                    print(f"⚠️ 端點連線異常，改試下一個端點：{endpoint_hint} | {e}")
                    continue
                return None, f"❌ 發生錯誤：{str(e)}"

        if qwen_tts_realtime is None or callback is None or voice_id is None:
            return None, f"❌ 所有 DashScope 端點連線失敗：{str(last_error)}"

        # Update session configuration
        effective_ref_text = None if use_xvector_only else (reference_text or None)
        qwen_tts_realtime.update_session(
            voice=voice_id,
            reference_text=effective_ref_text,
            response_format=AudioFormat.PCM_24000HZ_MONO_16BIT,
            mode='server_commit'
        )

        # Send text
        qwen_tts_realtime.append_text(normalized_text)
        qwen_tts_realtime.finish()

        # Wait for completion
        callback.wait_for_finished()

        if callback.error_msg:
            return None, f"❌ 合成失敗：{callback.error_msg}"

        # Get audio data and save as WAV file
        audio_data = callback.get_audio_data()

        if not audio_data:
            return None, "❌ 沒有產生音訊資料"

        # Create temporary file to save audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            output_path = tmp_file.name

            # Write WAV file header
            with wave.open(output_path, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16bit
                wav_file.setframerate(24000)  # 24kHz
                wav_file.writeframes(audio_data)

        success_msg = f"✅ 合成完成！Session ID：{qwen_tts_realtime.get_session_id()}"
        print(success_msg)
        return output_path, success_msg

    except Exception as e:
        error_msg = f"❌ 發生錯誤：{str(e)}"
        print(error_msg)
        return None, error_msg


def synthesize_speech_local(text_input, local_model: str = ""):
    """Local offline TTS synthesis without remote API.

    local_model: one of _LOCAL_TTS_MODELS, e.g. 'espeak-ng（離線）' or
                 'edge-tts — zh-TW-HsiaoChenNeural（繁中女）'.
    """
    import sys
    import shutil
    import subprocess

    try:
        normalized_text = normalize_segment_text(text_input or "")
        if not normalized_text:
            return None, "❌ 請先輸入要合成的文字"

        model = (local_model or "espeak-ng（離線）").strip()

        # ── edge-tts path ─────────────────────────────────────────────
        if model.startswith("edge-tts"):
            if _edge_tts_module is None:
                return None, "❌ edge-tts 套件未安裝，請 pip install edge-tts"
            # Parse voice name: "edge-tts — zh-TW-HsiaoChenNeural（繁中女）"
            #                              ↑ after "— ", before "（"
            try:
                voice = model.split("—")[1].strip().split("（")[0].strip()
            except IndexError:
                voice = "zh-TW-HsiaoChenNeural"

            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                output_path = f.name

            _run_edge_tts(normalized_text, voice, output_path)

            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path, f"✅ edge-tts 合成完成（{voice}）"
            return None, "❌ edge-tts 未產生音訊"

        # ── espeak-ng path (Linux / default) ──────────────────────────
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
            output_path = f.name

        if sys.platform != 'win32' and shutil.which('espeak-ng'):
            cmd = ['espeak-ng', '-w', output_path]
            rate = os.getenv("LOCAL_TTS_RATE", "").strip()
            if rate:
                cmd += ['-s', rate]
            cmd.append(normalized_text)
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path, "✅ espeak-ng 合成完成（離線）"
            stderr = result.stderr.decode(errors='replace').strip()
            return None, f"❌ espeak-ng 合成失敗：{stderr or result.returncode}"

        # ── pyttsx3 fallback (Windows / SAPI5) ────────────────────────
        if pyttsx3 is None:
            return None, "❌ 尚未安裝本地端 TTS 套件 pyttsx3，請先 pip install pyttsx3"

        engine = pyttsx3.init()

        rate_value = os.getenv("LOCAL_TTS_RATE", "").strip()
        if rate_value:
            try:
                engine.setProperty("rate", int(rate_value))
            except ValueError:
                pass

        preferred_voice_name = os.getenv("LOCAL_TTS_VOICE_NAME", "").strip().lower()
        if preferred_voice_name:
            for voice in engine.getProperty("voices") or []:
                voice_name = (getattr(voice, "name", "") or "").lower()
                voice_id = (getattr(voice, "id", "") or "").lower()
                if preferred_voice_name in voice_name or preferred_voice_name in voice_id:
                    engine.setProperty("voice", voice.id)
                    break

        engine.save_to_file(normalized_text, output_path)
        engine.runAndWait()

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            return None, "❌ 本地端模型未產生音訊檔案，請確認系統語音引擎可用"

        return output_path, "✅ 本地端模型合成完成（離線）"
    except Exception as e:
        error_msg = f"❌ 本地端合成失敗：{str(e)}"
        print(error_msg)
        return None, error_msg


def _make_tts_session(api_key: str):
    """Build a requests.Session with retry strategy for standard TTS calls."""
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    session = requests.Session()
    session.verify = certifi.where()
    retry = Retry(total=3, backoff_factor=1,
                  status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["POST", "GET"])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })
    return session


def _download_audio(session, audio_url: str) -> bytes:
    """Download audio from a DashScope-issued URL."""
    resp = session.get(audio_url, timeout=(10, 60))
    resp.raise_for_status()
    return resp.content


def _save_audio_to_tmp(data: bytes, suffix: str = ".wav") -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(data)
        return f.name


def synthesize_speech_preset(text_input: str,
                              voice_label: str,
                              language: str = "Auto",
                              instructions: str = "",
                              api_key_override: str = "") -> tuple:
    """
    Standard TTS with a preset voice (Qwen3-TTS CustomVoice).

    Returns (audio_path, status_message).
    """
    try:
        normalized = normalize_segment_text(text_input or "")
        if not normalized:
            return None, "❌ 請輸入要合成的文字"
        if not voice_label:
            return None, "❌ 請選擇預設聲線"

        # Parse voice ID from label "Serena — 溫柔少女音" → "Serena"
        voice_id = voice_label.split("—")[0].strip()

        # Resolve API key
        if api_key_override and api_key_override.strip():
            api_key = api_key_override.strip()
            os.environ["DASHSCOPE_API_KEY"] = api_key
        else:
            api_key = get_dashscope_api_key()

        model = QWEN3_TTS_INSTRUCT_MODEL if (instructions and instructions.strip()) else QWEN3_TTS_FLASH_MODEL

        payload = {
            "model": model,
            "input": {
                "text": normalized,
                "voice": voice_id,
                "language_type": language,
            },
            "parameters": {
                "response_format": "wav",
                "sample_rate": 24000,
            },
        }
        if instructions and instructions.strip():
            payload["input"]["instructions"] = instructions.strip()

        hosts = [_TTS_API_HOST_CN, _TTS_API_HOST_INTL]
        session = _make_tts_session(api_key)
        last_err = None

        for idx, host in enumerate(hosts, start=1):
            url = host + _TTS_GENERATION_PATH
            try:
                print(f"[preset TTS] 端點 {idx}/{len(hosts)}: {url}")
                resp = session.post(url, json=payload, timeout=(15, 90))
                if resp.status_code == 401:
                    return None, "❌ DashScope 驗證失敗（401），請確認 API Key 正確"
                resp.raise_for_status()
                body = resp.json()

                # Try audio_url first, then base64 audio data
                audio_url = (body.get("output") or {}).get("audio_url")
                if audio_url:
                    audio_bytes = _download_audio(session, audio_url)
                else:
                    # Some endpoints return audio as base64 in output.audio
                    b64 = (body.get("output") or {}).get("audio")
                    if b64:
                        audio_bytes = base64.b64decode(b64)
                    else:
                        return None, f"❌ API 回應未含音訊資料：{body}"

                path = _save_audio_to_tmp(audio_bytes, ".wav")
                return path, f"✅ 預設聲線合成完成（{voice_id}）"

            except Exception as e:
                last_err = e
                if is_ssl_or_transport_error(e):
                    print(f"⚠️ 端點異常，改試下一個：{e}")
                    continue
                return None, f"❌ 發生錯誤：{e}"

        return None, f"❌ 所有端點連線失敗：{last_err}"

    except Exception as e:
        return None, f"❌ 預設聲線合成失敗：{e}"


def synthesize_speech_voice_design(voice_prompt: str,
                                   preview_text: str,
                                   text_input: str,
                                   language: str = "Auto",
                                   api_key_override: str = "") -> tuple:
    """
    Two-step voice design:
      1. Create a custom voice from natural-language description.
      2. Synthesize text with the created voice.

    Returns (audio_path, status_message).
    """
    try:
        if not voice_prompt or not voice_prompt.strip():
            return None, "❌ 請輸入聲線描述"
        normalized = normalize_segment_text(text_input or "")
        if not normalized:
            return None, "❌ 請輸入要合成的文字"

        if api_key_override and api_key_override.strip():
            api_key = api_key_override.strip()
            os.environ["DASHSCOPE_API_KEY"] = api_key
        else:
            api_key = get_dashscope_api_key()

        # Language code mapping
        lang_map = {
            "Chinese": "zh", "English": "en", "Japanese": "ja",
            "Korean": "ko", "French": "fr", "German": "de",
            "Spanish": "es", "Portuguese": "pt", "Russian": "ru",
        }
        lang_code = lang_map.get(language, "zh")

        hosts = [_TTS_API_HOST_CN, _TTS_API_HOST_INTL]
        session = _make_tts_session(api_key)
        last_err = None

        # ── Step 1: Create voice ──────────────────────────────────────
        create_payload = {
            "model": QWEN_VOICE_DESIGN_MODEL,
            "input": {
                "action": "create",
                "target_model": QWEN3_TTS_VD_MODEL,
                "voice_prompt": voice_prompt.strip(),
                "preview_text": (preview_text or "").strip() or normalized[:50],
                "preferred_name": "custom_vd",
                "language": lang_code,
            },
        }

        voice_id = None
        for idx, host in enumerate(hosts, start=1):
            url = host + _TTS_CUSTOMIZATION_PATH
            try:
                print(f"[voice design] 建立聲線 端點 {idx}/{len(hosts)}: {url}")
                resp = session.post(url, json=create_payload, timeout=(15, 90))
                if resp.status_code == 401:
                    return None, "❌ DashScope 驗證失敗（401），請確認 API Key 正確"
                resp.raise_for_status()
                body = resp.json()
                voice_id = (body.get("output") or {}).get("voice_id") or \
                           (body.get("output") or {}).get("voice")
                if voice_id:
                    break
                return None, f"❌ 建立聲線失敗，API 回應：{body}"
            except Exception as e:
                last_err = e
                if is_ssl_or_transport_error(e):
                    continue
                return None, f"❌ 建立聲線時發生錯誤：{e}"

        if not voice_id:
            return None, f"❌ 所有端點連線失敗（建立聲線）：{last_err}"

        print(f"[voice design] 聲線建立成功 voice_id={voice_id}")

        # ── Step 2: Synthesize with created voice ─────────────────────
        synth_payload = {
            "model": QWEN3_TTS_VD_MODEL,
            "input": {
                "text": normalized,
                "voice": voice_id,
                "language_type": language,
            },
            "parameters": {
                "response_format": "wav",
                "sample_rate": 24000,
            },
        }

        for idx, host in enumerate(hosts, start=1):
            url = host + _TTS_GENERATION_PATH
            try:
                print(f"[voice design] 合成 端點 {idx}/{len(hosts)}: {url}")
                resp = session.post(url, json=synth_payload, timeout=(15, 120))
                resp.raise_for_status()
                body = resp.json()

                audio_url = (body.get("output") or {}).get("audio_url")
                if audio_url:
                    audio_bytes = _download_audio(session, audio_url)
                else:
                    b64 = (body.get("output") or {}).get("audio")
                    if b64:
                        audio_bytes = base64.b64decode(b64)
                    else:
                        return None, f"❌ 合成 API 回應未含音訊：{body}"

                path = _save_audio_to_tmp(audio_bytes, ".wav")
                return path, f"✅ 聲線設計合成完成（voice_id: {voice_id}）"

            except Exception as e:
                last_err = e
                if is_ssl_or_transport_error(e):
                    continue
                return None, f"❌ 合成時發生錯誤：{e}"

        return None, f"❌ 所有端點連線失敗（合成）：{last_err}"

    except Exception as e:
        return None, f"❌ 聲線設計失敗：{e}"


def synthesize_speech(audio_file, reference_text, text_input,
                     execution_mode, use_xvector_only, language,
                     api_key_override, local_model):
    """Dispatch synthesis to local or remote runtime."""
    if execution_mode and execution_mode.startswith("本地端"):
        return synthesize_speech_local(text_input, local_model=local_model or "")
    return synthesize_speech_remote(
        audio_file, reference_text, text_input,
        use_xvector_only=bool(use_xvector_only),
        language=language or "Auto",
        api_key_override=api_key_override or ""
    )

# ======= Gradio Interface =======
def create_gradio_interface():
    """Create Gradio interface — Voice Clone / Preset Voice / Voice Design."""

    _LANGUAGES = [
        "Auto", "Chinese", "English", "Japanese", "Korean",
        "French", "German", "Spanish", "Portuguese", "Russian"
    ]

    with gr.Blocks(
        title="Voice Mimic — 三種說話方式",
        theme=gr.themes.Base(),
        css=UI_CSS,
        head=UI_HEAD
    ) as demo:

        # ── Hero Section ──────────────────────────────────────────────
        gr.HTML("""
        <section class="hero-wrap">
          <button id="theme-toggle" type="button">切換暗色</button>
          <div class="hero-content">
            <p class="hero-kicker">Voice Clone · Preset Voice · Voice Design · DashScope</p>
            <h1 class="hero-title">Voice Mimic　三種說話方式</h1>
            <p class="hero-subtitle">
              克隆任何聲線、選用九種預設音色，或以一句話描述你想要的聲音風格——讓文字用你選擇的聲音說出口。
            </p>
            <div class="hero-badges">
              <span class="hero-badge">🎙️ 聲音克隆</span>
              <span class="hero-badge">🔊 九種預設聲線</span>
              <span class="hero-badge">🎨 自訂聲線設計</span>
              <span class="hero-badge">📝 情感指令控制</span>
              <span class="hero-badge">🌐 10 種語言</span>
              <span class="hero-badge">⚡ 遠端 API / 本地端</span>
            </div>
          </div>
        </section>
        """)

        # ── Three Tabs ────────────────────────────────────────────────
        with gr.Tabs():

            # ════════════════════════════════════════════════════════
            # Tab 1 — 聲音克隆（現有功能）
            # ════════════════════════════════════════════════════════
            with gr.Tab("① 聲音克隆"):
                with gr.Row(elem_classes=["panel-grid"]):

                    # Left panel: ① Who is speaking + ② Transcript
                    with gr.Column(scale=1, elem_classes=["panel"]):
                        gr.Markdown("### ① 誰在說話？", elem_classes=["section-title"])
                        gr.HTML("<p class='section-note'>上傳或錄製 10–30 秒參考聲音。環境越安靜，克隆效果越接近原聲。</p>")
                        audio_input = gr.Audio(
                            sources=["microphone", "upload"],
                            type="filepath",
                            label="參考聲音（上傳 / 錄製）",
                            format="wav"
                        )

                        gr.Markdown("### ② 他說了什麼？", elem_classes=["section-title"])
                        gr.HTML("<p class='section-note'>輸入參考音檔中說話的文字，可大幅提升克隆相似度。<br>若勾選下方選項，此欄位可留空。</p>")
                        reference_text_input = gr.Textbox(
                            label="參考逐字稿（Transcript）",
                            placeholder="請輸入參考音檔中說話的文字內容…",
                            lines=3
                        )
                        xvector_only = gr.Checkbox(
                            label="僅使用 X-vector（不需逐字稿，品質較低）",
                            value=False,
                            info="勾選後不需提供逐字稿，直接以聲紋向量克隆聲音"
                        )

                    # Right panel: ③ Target text → ④ Output
                    with gr.Column(scale=1, elem_classes=["panel"]):
                        gr.Markdown("### ③ 你想說什麼？", elem_classes=["section-title"])
                        gr.HTML("<p class='section-note'>輸入要以克隆聲音說出的文字內容。</p>")
                        vc_text_input = gr.Textbox(
                            label="目標合成文字",
                            placeholder="輸入要合成的文字…",
                            lines=5,
                            value="今天二零二六年二月二十四號，我從家裡出門，先去巷口買一杯少冰微糖的紅茶。捷運到站，我刷悠遊卡，站在月台邊等門開。"
                        )

                        with gr.Row():
                            vc_language = gr.Dropdown(
                                label="語言",
                                choices=_LANGUAGES,
                                value="Auto",
                                interactive=True,
                                scale=1
                            )
                            vc_execution_mode = gr.Radio(
                                choices=["遠端 API（DashScope 聲音分身）", "本地端模型（離線 TTS）"],
                                value="遠端 API（DashScope 聲音分身）",
                                label="執行模式",
                                info="遠端 API 需 DASHSCOPE_API_KEY；本地端不需金鑰",
                                scale=2
                            )

                        vc_api_key = gr.Textbox(
                            label="DashScope API Key（選填）",
                            placeholder="貼上 API Key，優先於環境變數 DASHSCOPE_API_KEY",
                            type="password",
                            visible=True
                        )
                        vc_local_model = gr.Dropdown(
                            label="本地端 TTS 模型",
                            choices=_LOCAL_TTS_MODELS,
                            value=_LOCAL_TTS_MODELS[0],
                            info="espeak-ng 完全離線；edge-tts 需網路但語音品質更自然",
                            visible=False
                        )

                        vc_submit_btn = gr.Button(
                            "🎧 開始克隆合成",
                            variant="primary",
                            size="lg",
                            elem_classes=["synthesize-btn"]
                        )

                        gr.Markdown("### ④ 合成結果", elem_classes=["section-title"])
                        vc_status = gr.Textbox(label="系統訊息", interactive=False, lines=2)
                        vc_audio_output = gr.Audio(label="克隆合成語音", type="filepath")

                def _vc_mode_change(mode):
                    is_remote = mode.startswith("遠端")
                    return gr.update(visible=is_remote), gr.update(visible=not is_remote)

                vc_execution_mode.change(
                    fn=_vc_mode_change,
                    inputs=[vc_execution_mode],
                    outputs=[vc_api_key, vc_local_model]
                )
                vc_submit_btn.click(
                    fn=synthesize_speech,
                    inputs=[audio_input, reference_text_input, vc_text_input,
                            vc_execution_mode, xvector_only, vc_language,
                            vc_api_key, vc_local_model],
                    outputs=[vc_audio_output, vc_status]
                )

            # ════════════════════════════════════════════════════════
            # Tab 2 — 預設聲線
            # ════════════════════════════════════════════════════════
            with gr.Tab("② 預設聲線"):
                with gr.Row(elem_classes=["panel-grid"]):

                    with gr.Column(scale=1, elem_classes=["panel"]):
                        gr.Markdown("### ① 選擇聲線", elem_classes=["section-title"])
                        gr.HTML("<p class='section-note'>從 Qwen3-TTS 九種精選音色中選擇一個預設聲線。</p>")
                        preset_voice = gr.Dropdown(
                            label="預設聲線",
                            choices=_PRESET_VOICES,
                            value=_PRESET_VOICES[0],
                            interactive=True
                        )

                        gr.Markdown("### ② 情感指令（選填）", elem_classes=["section-title"])
                        gr.HTML("<p class='section-note'>以自然語言描述說話風格或情緒，僅限中英文。<br>例：「說話語速稍慢，帶有溫柔關懷的語氣」</p>")
                        preset_instructions = gr.Textbox(
                            label="情感 / 風格指令",
                            placeholder="例：語速稍慢，帶有溫柔的語氣…（選填）",
                            lines=3
                        )

                    with gr.Column(scale=1, elem_classes=["panel"]):
                        gr.Markdown("### ③ 輸入文字", elem_classes=["section-title"])
                        gr.HTML("<p class='section-note'>輸入要以選定聲線說出的文字（最多 600 字）。</p>")
                        preset_text = gr.Textbox(
                            label="合成文字",
                            placeholder="輸入要合成的文字…",
                            lines=5,
                            value="歡迎使用 Voice Mimic 預設聲線功能，現在你可以不需要參考音檔，直接選擇喜歡的聲音風格來合成語音。"
                        )

                        with gr.Row():
                            preset_language = gr.Dropdown(
                                label="語言",
                                choices=_LANGUAGES,
                                value="Auto",
                                interactive=True,
                                scale=1
                            )
                            preset_api_key = gr.Textbox(
                                label="DashScope API Key（選填）",
                                placeholder="貼上 API Key…",
                                type="password",
                                scale=2
                            )

                        preset_submit_btn = gr.Button(
                            "🔊 開始合成",
                            variant="primary",
                            size="lg",
                            elem_classes=["synthesize-btn"]
                        )

                        gr.Markdown("### ④ 合成結果", elem_classes=["section-title"])
                        preset_status = gr.Textbox(label="系統訊息", interactive=False, lines=2)
                        preset_audio_output = gr.Audio(label="合成語音", type="filepath")

                preset_submit_btn.click(
                    fn=synthesize_speech_preset,
                    inputs=[preset_text, preset_voice, preset_language,
                            preset_instructions, preset_api_key],
                    outputs=[preset_audio_output, preset_status]
                )

            # ════════════════════════════════════════════════════════
            # Tab 3 — 聲線設計
            # ════════════════════════════════════════════════════════
            with gr.Tab("③ 聲線設計"):
                with gr.Row(elem_classes=["panel-grid"]):

                    with gr.Column(scale=1, elem_classes=["panel"]):
                        gr.Markdown("### ① 描述你的聲線", elem_classes=["section-title"])
                        gr.HTML("<p class='section-note'>以自然語言描述想要的聲音特質，中英文均可。<br>可描述性別、年齡、音色、語速、口音、情緒等。</p>")
                        vd_prompt = gr.Textbox(
                            label="聲線描述",
                            placeholder=(
                                "例（中）：一位三十歲左右的女性，聲音溫柔清亮，說話速度平穩，帶有輕微台灣腔調。\n"
                                "例（英）：A calm middle-aged male narrator with a deep, rich voice "
                                "and clear articulation, suitable for documentary narration."
                            ),
                            lines=5
                        )

                        gr.Markdown("### ② 預覽文字（選填）", elem_classes=["section-title"])
                        gr.HTML("<p class='section-note'>建立聲線時用於預覽的短句，留空則使用合成文字前 50 字。</p>")
                        vd_preview_text = gr.Textbox(
                            label="預覽文字",
                            placeholder="例：大家好，我是你的語音助理。",
                            lines=2
                        )

                    with gr.Column(scale=1, elem_classes=["panel"]):
                        gr.Markdown("### ③ 輸入合成文字", elem_classes=["section-title"])
                        gr.HTML("<p class='section-note'>輸入要以設計聲線說出的文字。</p>")
                        vd_text = gr.Textbox(
                            label="合成文字",
                            placeholder="輸入要合成的文字…",
                            lines=5,
                            value="這是一段由自訂聲線說出的語音，聲線的風格完全由你的描述所決定。你可以嘗試不同的描述方式，創造出獨一無二的聲音。"
                        )

                        with gr.Row():
                            vd_language = gr.Dropdown(
                                label="語言",
                                choices=_LANGUAGES,
                                value="Chinese",
                                interactive=True,
                                scale=1
                            )
                            vd_api_key = gr.Textbox(
                                label="DashScope API Key（選填）",
                                placeholder="貼上 API Key…",
                                type="password",
                                scale=2
                            )

                        vd_submit_btn = gr.Button(
                            "🎨 設計並合成",
                            variant="primary",
                            size="lg",
                            elem_classes=["synthesize-btn"]
                        )

                        gr.Markdown("### ④ 合成結果", elem_classes=["section-title"])
                        vd_status = gr.Textbox(label="系統訊息", interactive=False, lines=2)
                        vd_audio_output = gr.Audio(label="合成語音", type="filepath")

                vd_submit_btn.click(
                    fn=synthesize_speech_voice_design,
                    inputs=[vd_prompt, vd_preview_text, vd_text, vd_language, vd_api_key],
                    outputs=[vd_audio_output, vd_status]
                )

        gr.HTML("<p class='footer-tip'>提示：請確認已設定 <code>DASHSCOPE_API_KEY</code>，並使用自然語速錄音以獲得最佳聲音相似度。</p>")

    return demo

if __name__ == "__main__":
    # Check API Key for remote mode (optional when using local mode)
    try:
        init_dashscope_api_key()
        print("✅ API 金鑰驗證成功（可使用遠端 API 模式）")
    except ValueError as e:
        print(f"⚠️  遠端 API 模式警告：{e}")
        print(
            "若要使用遠端 API 模式，請設定 DASHSCOPE_API_KEY；"
            "未設定仍可使用本地端模型（離線 TTS）模式。"
        )

    demo = create_gradio_interface()

    PORT = 7860
    print()
    print("=" * 54)
    print("  Voice Mimic — 聲音克隆工作台")
    print("=" * 54)
    print(f"  本機位址 (Local) : http://localhost:{PORT}")
    print("  公開位址 (Public): 啟動後顯示於下方 ↓")
    print("=" * 54)
    print()

    demo.launch(
        share=True,
        server_name="0.0.0.0",
        server_port=PORT,
        ssr_mode=False
    )
