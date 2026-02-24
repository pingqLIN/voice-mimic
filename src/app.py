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
  --bg-a: #f6f3ea;
  --bg-b: #e9e4d6;
  --panel-bg: rgba(255, 253, 248, 0.86);
  --panel-border: rgba(159, 92, 44, 0.26);
  --title: #241d16;
  --text: #2f2922;
  --muted: #695f54;
  --primary: #9f5c2c;
  --primary-strong: #8b4d21;
  --accent: #1f7a77;
  --shadow: 0 16px 36px rgba(115, 83, 58, 0.14);
}

:root.theme-dark {
  --bg-a: #111827;
  --bg-b: #0f172a;
  --panel-bg: rgba(17, 24, 39, 0.8);
  --panel-border: rgba(103, 232, 249, 0.22);
  --title: #f8f3e8;
  --text: #e8e6dc;
  --muted: #b7c2d0;
  --primary: #f8b259;
  --primary-strong: #f59e0b;
  --accent: #67e8f9;
  --shadow: 0 18px 42px rgba(0, 0, 0, 0.38);
}

body,
.gradio-container {
  font-family: \"Noto Sans TC\", \"PingFang TC\", \"Microsoft JhengHei\", sans-serif !important;
  color: var(--text) !important;
  background:
    radial-gradient(circle at 14% 12%, color-mix(in oklab, var(--accent) 28%, transparent) 0%, transparent 48%),
    radial-gradient(circle at 82% 18%, color-mix(in oklab, var(--primary) 30%, transparent) 0%, transparent 52%),
    linear-gradient(145deg, var(--bg-a), var(--bg-b)) !important;
}

.gradio-container {
  max-width: 1140px !important;
  margin: 0 auto !important;
  padding: 22px 16px 24px !important;
}

.hero-shell {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--panel-border);
  border-radius: 22px;
  background: linear-gradient(135deg, color-mix(in oklab, var(--panel-bg) 84%, transparent), color-mix(in oklab, var(--panel-bg) 60%, transparent));
  box-shadow: var(--shadow);
  padding: 24px 22px;\n  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  animation: rise-in .28s ease-out both;
}

.hero-shell::after {
  content: \"\";
  position: absolute;
  width: 230px;
  height: 230px;
  right: -72px;
  top: -78px;
  border-radius: 999px;
  background: radial-gradient(circle at center, color-mix(in oklab, var(--accent) 35%, transparent), transparent 72%);
  pointer-events: none;
}

.hero-kicker {
  margin: 0 0 8px;
  font-size: 12px;
  letter-spacing: .09em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 700;
}

.hero-title {
  margin: 0;
  font-family: \"Noto Serif TC\", serif;
  color: var(--title);
  font-size: clamp(30px, 5vw, 46px);
  line-height: 1.1;
  letter-spacing: .01em;
}

.hero-subtitle {
  margin: 10px 0 0;
  color: var(--muted);
  font-size: 15px;
  max-width: 720px;
}

#theme-toggle {
  position: relative;
  z-index: 2;
  border: 1px solid color-mix(in oklab, var(--primary) 55%, var(--panel-border));
  color: var(--title);
  background: color-mix(in oklab, var(--panel-bg) 74%, transparent);
  border-radius: 999px;
  padding: 10px 16px;
  font-weight: 700;
  font-size: 13px;
  cursor: pointer;
  transition: transform .16s ease, box-shadow .2s ease, background .2s ease;
}

#theme-toggle:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px color-mix(in oklab, var(--primary) 24%, transparent);
}

#theme-toggle:active {
  transform: translateY(0);
}

.guide-card {
  margin-top: 14px;
  border: 1px solid color-mix(in oklab, var(--panel-border) 72%, transparent);
  border-radius: 18px;
  padding: 12px 16px;
  background: color-mix(in oklab, var(--panel-bg) 90%, transparent);
}

.guide-card ol {
  margin: 8px 0 0 18px;
  padding: 0;
  color: var(--text);
}

.guide-card li {
  margin: 5px 0;
}

.panel-grid {
  margin-top: 12px;
  animation: rise-in .26s ease-out both;
}

.panel {
  border: 1px solid color-mix(in oklab, var(--panel-border) 76%, transparent);
  border-radius: 18px;
  background: color-mix(in oklab, var(--panel-bg) 92%, transparent);
  box-shadow: var(--shadow);
  padding: 14px;
}

.panel h3,
.section-title {
  margin-top: 0 !important;
  margin-bottom: 8px !important;
  color: var(--title) !important;
  font-family: \"Noto Serif TC\", serif !important;
}

.segment-note {
  margin-top: 7px;
  margin-bottom: 8px;
  color: var(--muted);
  font-size: 12px;
}

.footer-tip {
  margin-top: 12px;
  color: var(--muted);
  font-size: 13px;
}

.gradio-container textarea,
.gradio-container input,
.gradio-container .wrap {
  font-family: \"Noto Sans TC\", \"PingFang TC\", \"Microsoft JhengHei\", sans-serif !important;
}

.gradio-container textarea,
.gradio-container input[type=\"text\"] {
  background: color-mix(in oklab, var(--panel-bg) 88%, transparent) !important;
  color: var(--text) !important;
  border: 1px solid color-mix(in oklab, var(--panel-border) 72%, transparent) !important;
}

.gradio-container button.primary,
.gradio-container .synthesize-btn button {
  background: linear-gradient(120deg, var(--primary-strong), var(--primary)) !important;
  border: none !important;
  color: #fff7ef !important;
  font-weight: 800 !important;
  letter-spacing: .01em;
  box-shadow: 0 10px 22px color-mix(in oklab, var(--primary) 34%, transparent);
  transition: transform .16s ease, box-shadow .22s ease;
}

.gradio-container button.primary:hover,
.gradio-container .synthesize-btn button:hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 28px color-mix(in oklab, var(--primary) 44%, transparent);
}

.gradio-container .label-wrap span,
.gradio-container .label-wrap {
  color: var(--title) !important;
}

@keyframes rise-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 900px) {
  .hero-shell {
    flex-direction: column;
    align-items: flex-start;
  }
  #theme-toggle {
    align-self: flex-end;
  }
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

def synthesize_speech(audio_file, reference_text, text_input):
    """
    Main function for speech synthesis

    Args:
        audio_file: Path to the recorded audio file (from Gradio audio component)
        reference_text: Transcript of the reference audio.
        text_input: Text to synthesize

    Returns:
        Path to the synthesized audio file
    """
    try:
        if not audio_file:
            return None, "❌ 請先錄製參考聲音"

        normalized_text = normalize_segment_text(text_input or "")
        if not normalized_text:
            return None, "❌ 請先輸入要合成的文字"

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
        qwen_tts_realtime.update_session(
            voice=voice_id,
            reference_text=reference_text,
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

# ======= Gradio Interface =======
def create_gradio_interface():
    """Create Gradio interface"""

    with gr.Blocks(
        title="Qwen 聲音分身工作台",
        theme=gr.themes.Base(),
        css=UI_CSS,
        head=UI_HEAD
    ) as demo:
        gr.HTML("""
        <section class=\"hero-shell\">
            <div>
                <p class=\"hero-kicker\">Qwen TTS Clone Demo</p>
                <h1 class=\"hero-title\">Qwen 聲音分身工作台</h1>
                <p class=\"hero-subtitle\">
                    錄製參考聲音，輸入要合成的文字，快速合成可播放與下載的語音。
                </p>
            </div>
            <button id=\"theme-toggle\" type=\"button\">切換暗色</button>
        </section>
        """)
        gr.HTML("""
        <section class=\"guide-card\">
            <strong>使用流程</strong>
            <ol>
                <li>按麥克風錄製 10 到 30 秒參考聲音，環境越安靜越好。</li>
                <li>在文字輸入框輸入要合成的內容。</li>
                <li>點擊「開始合成」，等待完成後可直接播放或下載。</li>
            </ol>
        </section>
        """)
        gr.HTML("""
        <section class=\"guide-card\">
            <strong>目前執行內容（已整理）</strong>
            <ol>
                <li>執行環境：Google Colab 終端機，前端使用 Gradio 介面。</li>
                <li>服務流程：先建立聲音分身，再使用即時 TTS 合成語音。</li>
                <li>端點策略：自動嘗試中國與國際端點，SSL/連線異常時會自動切換重試。</li>
                <li>金鑰規則：需使用 DashScope API Key，`LTAI...:...` 格式不可直接使用。</li>
            </ol>
        </section>
        """)

        with gr.Row(elem_classes=["panel-grid"]):
            with gr.Column(scale=1, elem_classes=["panel"]):
                gr.Markdown("### 步驟 1：錄製參考聲音", elem_classes=["section-title"])
                audio_input = gr.Audio(
                    sources=["microphone"],
                    type="filepath",
                    label="錄音區",
                    format="wav"
                )
                # Add new reference_text_input here
                reference_text_input = gr.Textbox(
                    label="Reference Text (Transcript of the reference audio)",
                    placeholder="Enter the transcript of the reference audio here...",
                    lines=3
                )
                gr.Markdown("### Step 2: Enter Text to Synthesize", elem_classes=["section-title"])
                text_input = gr.Textbox(
                    label="Text to Synthesize",
                    placeholder="Please enter the text content to synthesize...",
                    lines=5,
                    value="Hello, this is a voice synthesized using voice cloning technology."
                )

                submit_btn = gr.Button("開始合成", variant="primary", size="lg", elem_classes=["synthesize-btn"])

            with gr.Column(scale=1, elem_classes=["panel"]):
                gr.Markdown("### 合成結果", elem_classes=["section-title"])
                status_output = gr.Textbox(
                    label="系統訊息",
                    interactive=False,
                    lines=3
                )
                audio_output = gr.Audio(
                    label="合成語音",
                    type="filepath"
                )

        # Bind events
        submit_btn.click(
            fn=synthesize_speech,
            inputs=[audio_input, reference_text_input, text_input],
            outputs=[audio_output, status_output]
        )

        gr.HTML("<p class='footer-tip'>提示：請確認已設定 <code>DASHSCOPE_API_KEY</code>，並使用自然語速錄音以獲得更好的聲音相似度。</p>")

    return demo

if __name__ == "__main__":
    # Check API Key
    try:
        init_dashscope_api_key()
        print("✅ API 金鑰驗證成功")
    except ValueError as e:
        print(f"⚠️  警告：{e}")
        print(
            "請先設定環境變數：export DASHSCOPE_API_KEY='your-api-key'，"
            "或在 Colab Secrets 設定 DASHSCOPE_API_KEY。"
        )

    demo = create_gradio_interface()
    # Set share to True for public access
    demo.launch(
        share=True,
        server_name="0.0.0.0",
        server_port=7860,
        ssr_mode=False
    )
