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

# ======= Constants Configuration =======
DEFAULT_TARGET_MODEL = "qwen3-tts-vc-realtime-2025-11-27"
DEFAULT_PREFERRED_NAME = "custom_voice"
DEFAULT_AUDIO_MIME_TYPE = "audio/wav"
DEFAULT_CN_HTTP_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
DEFAULT_INTL_HTTP_URL = "https://dashscope-us.aliyuncs.com/compatible-mode/v1"
DEFAULT_CN_WS_URL = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"
DEFAULT_INTL_WS_URL = "wss://dashscope-us.aliyuncs.com/api-ws/v1/realtime"

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

.hero-inner {
  display: flex;
  align-items: stretch;
  min-height: 360px;
}

.hero-illustration {
  flex: 0 0 44%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in oklab, var(--accent) 6%, transparent);
  border-right: 1px solid var(--panel-border);
  padding: 20px 12px 20px 20px;
}

.hero-illustration svg {
  width: 100%;
  max-width: 330px;
  height: auto;
  filter: drop-shadow(0 8px 20px color-mix(in oklab, var(--accent) 18%, transparent));
}

.hero-content {
  flex: 1;
  padding: 32px 32px 28px 28px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0;
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

.panel h3, .section-title {
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

@media (max-width: 860px) {
  .hero-inner { flex-direction: column; }
  .hero-illustration {
    flex: 0 0 auto;
    border-right: none;
    border-bottom: 1px solid var(--panel-border);
    padding: 18px;
  }
  .hero-illustration svg { max-width: 220px; }
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
                            language: str = "Auto"):
    """
    Main function for speech synthesis (Voice Clone mode).

    Args:
        audio_file: Path to the reference audio file.
        reference_text: Transcript of the reference audio (skipped when use_xvector_only=True).
        text_input: Target text to synthesize with the cloned voice.
        use_xvector_only: If True, skip reference_text and use x-vector only (lower quality).
        language: Target language hint (Auto / Chinese / English / …).

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

        # Initialize API Key
        init_dashscope_api_key()

        endpoint_candidates = get_dashscope_endpoint_candidates()
        last_error = None
        voice_id = None
        qwen_tts_realtime = None
        callback = None

        for idx, (customization_url, ws_url) in enumerate(endpoint_candidates, start=1):
            endpoint_hint = f"{customization_url} | {ws_url}"
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


def synthesize_speech_local(text_input):
    """Local offline TTS synthesis without remote API."""
    try:
        normalized_text = normalize_segment_text(text_input or "")
        if not normalized_text:
            return None, "❌ 請先輸入要合成的文字"

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

        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            output_path = tmp_file.name

        engine.save_to_file(normalized_text, output_path)
        engine.runAndWait()

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            return None, "❌ 本地端模型未產生音訊檔案，請確認系統語音引擎可用"

        return output_path, "✅ 本地端模型合成完成（離線）"
    except Exception as e:
        error_msg = f"❌ 本地端合成失敗：{str(e)}"
        print(error_msg)
        return None, error_msg


def synthesize_speech(audio_file, reference_text, text_input,
                     execution_mode, use_xvector_only, language):
    """Dispatch synthesis to local or remote runtime."""
    if execution_mode and execution_mode.startswith("本地端"):
        return synthesize_speech_local(text_input)
    return synthesize_speech_remote(
        audio_file, reference_text, text_input,
        use_xvector_only=bool(use_xvector_only),
        language=language or "Auto"
    )

# ======= Fox Mascot SVG (Design by SubAgent) =======
_FOX_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 380 420" width="380" height="420">
  <defs>
    <linearGradient id="bodyGrad" x1="20%" y1="0%" x2="80%" y2="100%">
      <stop offset="0%" stop-color="#d4ba8c"/>
      <stop offset="100%" stop-color="#b89868"/>
    </linearGradient>
    <linearGradient id="headGrad" x1="25%" y1="0%" x2="75%" y2="100%">
      <stop offset="0%" stop-color="#d2b680"/>
      <stop offset="100%" stop-color="#c4a87a"/>
    </linearGradient>
    <linearGradient id="tailGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#c8ae7a"/>
      <stop offset="100%" stop-color="#a07848"/>
    </linearGradient>
    <linearGradient id="micGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#8e8c84"/>
      <stop offset="100%" stop-color="#6a6860"/>
    </linearGradient>
    <linearGradient id="handsetGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#8e8c84"/>
      <stop offset="100%" stop-color="#686660"/>
    </linearGradient>
  </defs>
  <!-- Tail -->
  <ellipse cx="256" cy="335" rx="42" ry="23" fill="url(#tailGrad)" transform="rotate(-28,256,335)"/>
  <ellipse cx="274" cy="352" rx="27" ry="17" fill="#c4a87a" transform="rotate(-20,274,352)"/>
  <ellipse cx="280" cy="358" rx="18" ry="12" fill="#e8dcc4" transform="rotate(-14,280,358)"/>
  <!-- Legs -->
  <path d="M165,325 Q160,358 158,393" stroke="#c4a87a" stroke-width="28" stroke-linecap="round" fill="none"/>
  <path d="M215,325 Q220,358 222,393" stroke="#c4a87a" stroke-width="28" stroke-linecap="round" fill="none"/>
  <ellipse cx="157" cy="397" rx="23" ry="12" fill="#c4a87a"/>
  <ellipse cx="223" cy="397" rx="23" ry="12" fill="#c4a87a"/>
  <ellipse cx="145" cy="399" rx="7" ry="5" fill="#b09060"/>
  <ellipse cx="157" cy="402" rx="7" ry="5" fill="#b09060"/>
  <ellipse cx="170" cy="399" rx="7" ry="5" fill="#b09060"/>
  <ellipse cx="211" cy="399" rx="7" ry="5" fill="#b09060"/>
  <ellipse cx="223" cy="402" rx="7" ry="5" fill="#b09060"/>
  <ellipse cx="236" cy="399" rx="7" ry="5" fill="#b09060"/>
  <!-- Body -->
  <ellipse cx="190" cy="268" rx="56" ry="72" fill="url(#bodyGrad)"/>
  <ellipse cx="190" cy="278" rx="34" ry="54" fill="#e8dcc4"/>
  <!-- Left arm (mic side) -->
  <path d="M142,240 Q118,252 108,276" stroke="#c4a87a" stroke-width="22" stroke-linecap="round" fill="none"/>
  <path d="M108,276 Q100,292 102,312" stroke="#c4a87a" stroke-width="20" stroke-linecap="round" fill="none"/>
  <ellipse cx="102" cy="318" rx="14" ry="11" fill="#c4a87a" transform="rotate(-8,102,318)"/>
  <ellipse cx="91" cy="313" rx="6" ry="5" fill="#b09060"/>
  <ellipse cx="99" cy="309" rx="6" ry="5" fill="#b09060"/>
  <ellipse cx="109" cy="311" rx="6" ry="5" fill="#b09060"/>
  <!-- Microphone (話筒) -->
  <rect x="96" y="270" width="12" height="50" rx="6" fill="url(#micGrad)"/>
  <circle cx="102" cy="258" r="20" fill="url(#micGrad)"/>
  <circle cx="102" cy="258" r="17" fill="none" stroke="#aaa89e" stroke-width="1.2" opacity="0.45"/>
  <circle cx="102" cy="258" r="12" fill="none" stroke="#aaa89e" stroke-width="1" opacity="0.35"/>
  <circle cx="102" cy="258" r="6" fill="none" stroke="#aaa89e" stroke-width="0.8" opacity="0.3"/>
  <line x1="102" y1="239" x2="102" y2="277" stroke="#aaa89e" stroke-width="0.9" opacity="0.35"/>
  <line x1="83" y1="258" x2="121" y2="258" stroke="#aaa89e" stroke-width="0.9" opacity="0.35"/>
  <rect x="91" y="318" width="22" height="8" rx="4" fill="#5a5248"/>
  <!-- Right arm (handset side) -->
  <path d="M238,240 Q260,218 270,196" stroke="#c4a87a" stroke-width="22" stroke-linecap="round" fill="none"/>
  <path d="M270,196 Q278,175 274,153" stroke="#c4a87a" stroke-width="20" stroke-linecap="round" fill="none"/>
  <ellipse cx="272" cy="146" rx="14" ry="11" fill="#c4a87a" transform="rotate(12,272,146)"/>
  <ellipse cx="264" cy="138" rx="6" ry="5" fill="#b09060"/>
  <ellipse cx="274" cy="135" rx="6" ry="5" fill="#b09060"/>
  <ellipse cx="282" cy="140" rx="6" ry="5" fill="#b09060"/>
  <!-- Telephone Handset (聽筒) -->
  <path d="M258,102 Q286,88 302,110 Q315,130 306,155 Q295,175 274,170 Q258,164 252,145 Q244,122 258,102 Z" fill="url(#handsetGrad)"/>
  <ellipse cx="285" cy="103" rx="13" ry="11" fill="#5a5248" transform="rotate(-18,285,103)"/>
  <ellipse cx="285" cy="103" rx="8" ry="7" fill="#3a3028" transform="rotate(-18,285,103)"/>
  <ellipse cx="263" cy="165" rx="11" ry="9" fill="#5a5248" transform="rotate(-18,263,165)"/>
  <ellipse cx="263" cy="165" rx="7" ry="5" fill="#3a3028" transform="rotate(-18,263,165)"/>
  <ellipse cx="279" cy="135" rx="7" ry="18" fill="#9a9890" opacity="0.25" transform="rotate(-18,279,135)"/>
  <!-- Curly coiled cord (話筒 → 聽筒) -->
  <path d="M114,326 C116,338 126,338 128,326 C130,314 140,314 142,326 C144,338 154,338 156,326 C158,314 168,314 170,326 C172,338 182,338 184,326 C186,314 196,314 198,326 C200,338 210,338 212,326 C214,314 224,316 230,324 C238,336 248,336 254,322 C259,310 260,288 262,258 C263,228 263,198 260,172" stroke="#5a5248" stroke-width="2.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <!-- Ears -->
  <polygon points="148,92 133,46 172,74" fill="#c4a87a"/>
  <polygon points="150,89 140,54 168,74" fill="#b8806e"/>
  <polygon points="232,92 247,46 208,74" fill="#c4a87a"/>
  <polygon points="230,89 240,54 212,74" fill="#b8806e"/>
  <!-- Head -->
  <ellipse cx="190" cy="128" rx="58" ry="60" fill="url(#headGrad)"/>
  <!-- Muzzle -->
  <ellipse cx="186" cy="156" rx="32" ry="23" fill="#e8dcc4"/>
  <line x1="186" y1="143" x2="186" y2="169" stroke="#cbb88a" stroke-width="1.2" opacity="0.5"/>
  <!-- Eyes -->
  <ellipse cx="167" cy="120" rx="11" ry="12" fill="white"/>
  <ellipse cx="169" cy="122" rx="8" ry="9" fill="#3a3028"/>
  <circle cx="172" cy="118" r="2.8" fill="white"/>
  <path d="M157,109 Q167,104 178,109" stroke="#3a3028" stroke-width="2.8" fill="none" stroke-linecap="round"/>
  <ellipse cx="213" cy="120" rx="11" ry="12" fill="white"/>
  <ellipse cx="215" cy="122" rx="8" ry="9" fill="#3a3028"/>
  <circle cx="218" cy="118" r="2.8" fill="white"/>
  <path d="M202,109 Q213,104 224,109" stroke="#3a3028" stroke-width="2.8" fill="none" stroke-linecap="round"/>
  <!-- Cheek blush -->
  <ellipse cx="155" cy="138" rx="13" ry="8" fill="#c87050" opacity="0.13"/>
  <ellipse cx="225" cy="138" rx="13" ry="8" fill="#c87050" opacity="0.13"/>
  <!-- Nose -->
  <ellipse cx="186" cy="147" rx="9" ry="6.5" fill="#3a3028"/>
  <ellipse cx="184" cy="145" rx="3.5" ry="2.2" fill="#5a5248" opacity="0.4"/>
  <!-- Mouth (open, speaking) -->
  <path d="M173,161 Q186,174 199,161" fill="#b8806e" stroke="#3a3028" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
  <rect x="179" y="161" width="14" height="7" rx="2" fill="white" opacity="0.9"/>
  <!-- Whiskers left -->
  <line x1="157" y1="153" x2="124" y2="147" stroke="#3a3028" stroke-width="1.4" stroke-linecap="round" opacity="0.7"/>
  <line x1="157" y1="158" x2="124" y2="158" stroke="#3a3028" stroke-width="1.4" stroke-linecap="round" opacity="0.7"/>
  <line x1="157" y1="163" x2="126" y2="169" stroke="#3a3028" stroke-width="1.4" stroke-linecap="round" opacity="0.7"/>
  <!-- Whiskers right -->
  <line x1="215" y1="153" x2="248" y2="147" stroke="#3a3028" stroke-width="1.4" stroke-linecap="round" opacity="0.7"/>
  <line x1="215" y1="158" x2="250" y2="158" stroke="#3a3028" stroke-width="1.4" stroke-linecap="round" opacity="0.7"/>
  <line x1="215" y1="163" x2="246" y2="169" stroke="#3a3028" stroke-width="1.4" stroke-linecap="round" opacity="0.7"/>
</svg>"""

# ======= Gradio Interface =======
def create_gradio_interface():
    """Create Gradio interface — Voice Clone (Base) feature set."""

    _LANGUAGES = [
        "Auto", "Chinese", "English", "Japanese", "Korean",
        "French", "German", "Spanish", "Portuguese", "Russian"
    ]

    with gr.Blocks(
        title="Voice Mimic — 聲音克隆工作台",
        theme=gr.themes.Base(),
        css=UI_CSS,
        head=UI_HEAD
    ) as demo:

        # ── Hero Section ──────────────────────────────────────────────
        gr.HTML(f"""
        <section class="hero-wrap">
          <button id="theme-toggle" type="button">切換暗色</button>
          <div class="hero-inner">
            <div class="hero-illustration">
              {_FOX_SVG}
            </div>
            <div class="hero-content">
              <p class="hero-kicker">Voice Clone · Qwen TTS · DashScope</p>
              <h1 class="hero-title">Voice Mimic<br>聲音克隆工作台</h1>
              <p class="hero-subtitle">
                上傳或錄製參考聲音，即可複製任何聲線風格，<br>
                以截然不同的語音重新說出你想說的一切。
              </p>
              <div class="hero-badges">
                <span class="hero-badge">🎙️ 麥克風錄製 / 檔案上傳</span>
                <span class="hero-badge">📝 逐字稿輔助克隆</span>
                <span class="hero-badge">🔀 X‑vector 純音色模式</span>
                <span class="hero-badge">🌐 10 種語言</span>
                <span class="hero-badge">⚡ 遠端 API / 本地端</span>
              </div>
            </div>
          </div>
        </section>
        """)

        # ── Main Panels ───────────────────────────────────────────────
        with gr.Row(elem_classes=["panel-grid"]):

            # Left panel: Reference voice inputs
            with gr.Column(scale=1, elem_classes=["panel"]):
                gr.Markdown("### 🎤 參考聲音", elem_classes=["section-title"])
                gr.HTML("<p class='section-note'>上傳或錄製 10–30 秒參考聲音。環境越安靜，克隆效果越接近原聲。</p>")
                audio_input = gr.Audio(
                    sources=["microphone", "upload"],
                    type="filepath",
                    label="參考聲音（上傳 / 錄製）",
                    format="wav"
                )

                gr.Markdown("### 📋 參考聲音逐字稿", elem_classes=["section-title"])
                gr.HTML("<p class='section-note'>輸入參考音檔中人物說話的文字，可大幅提升克隆相似度。<br>若勾選下方選項，此欄位可留空。</p>")
                reference_text_input = gr.Textbox(
                    label="參考文字（Transcript）",
                    placeholder="請輸入參考音檔中說話的文字內容…",
                    lines=3
                )
                xvector_only = gr.Checkbox(
                    label="僅使用 X-vector（不需逐字稿，品質較低）",
                    value=False,
                    info="勾選後不需提供逐字稿，直接以聲紋向量克隆聲音"
                )

            # Right panel: Synthesis target + controls
            with gr.Column(scale=1, elem_classes=["panel"]):
                gr.Markdown("### ✍️ 合成目標文字", elem_classes=["section-title"])
                gr.HTML("<p class='section-note'>輸入要以克隆聲音說出的文字內容。</p>")
                text_input = gr.Textbox(
                    label="目標合成文字",
                    placeholder="輸入要合成的文字…",
                    lines=5,
                    value="你好，這是使用聲音克隆技術合成的語音示範。"
                )

                with gr.Row():
                    language_selector = gr.Dropdown(
                        label="語言",
                        choices=_LANGUAGES,
                        value="Auto",
                        interactive=True,
                        scale=1
                    )
                    execution_mode = gr.Radio(
                        choices=["遠端 API（DashScope 聲音分身）", "本地端模型（離線 TTS）"],
                        value="遠端 API（DashScope 聲音分身）",
                        label="執行模式",
                        info="遠端 API 需 DASHSCOPE_API_KEY；本地端不需金鑰",
                        scale=2
                    )

                submit_btn = gr.Button(
                    "🎧 開始克隆合成",
                    variant="primary",
                    size="lg",
                    elem_classes=["synthesize-btn"]
                )

        # ── Output Section ────────────────────────────────────────────
        with gr.Row(elem_classes=["panel-grid"]):
            with gr.Column(elem_classes=["panel"]):
                gr.Markdown("### 📢 合成結果", elem_classes=["section-title"])
                status_output = gr.Textbox(
                    label="系統訊息",
                    interactive=False,
                    lines=2
                )
                audio_output = gr.Audio(
                    label="克隆合成語音",
                    type="filepath"
                )

        # ── Event binding ─────────────────────────────────────────────
        submit_btn.click(
            fn=synthesize_speech,
            inputs=[
                audio_input,
                reference_text_input,
                text_input,
                execution_mode,
                xvector_only,
                language_selector
            ],
            outputs=[audio_output, status_output]
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
    # Set share to True for public access
    demo.launch(
        share=True,
        server_name="0.0.0.0",
        server_port=7860,
        ssr_mode=False
    )
