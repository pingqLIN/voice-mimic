# voice-mimic

[中文版](README.zh-TW.md)

A Colab Notebook-based voice cloning / TTS project supporting both remote API (DashScope voice clone) and local offline TTS modes.

## Project Structure

- `notebooks/voice-mimic-colab.ipynb` — Original workflow notebook (run in Colab)
- `src/app.py` — Maintainable code extracted from the notebook
- `requirements.txt` — Python dependencies

## Quick Start (Local)

```bash
python -m venv .venv
. .venv/Scripts/activate   # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
python src/app.py
```

## Run Modes

The UI lets you switch between two modes:

### 1. Remote API (DashScope Voice Clone)

- Requires `DASHSCOPE_API_KEY` (or `API_KEY`)
- Supports reference audio for voice cloning

### 2. Local Model (Offline TTS)

- No API key required
- Uses local TTS engine (`pyttsx3`) for offline synthesis
- Does not use voice cloning (text-to-speech only)

## Environment Variables

| Variable | Mode | Description |
| --- | --- | --- |
| `DASHSCOPE_API_KEY` | Remote | DashScope API Key |
| `DASHSCOPE_HTTP_URL` | Remote | Custom HTTP endpoint (optional) |
| `DASHSCOPE_WS_URL` | Remote | Custom WebSocket endpoint (optional) |
| `LOCAL_TTS_RATE` | Local | Speech rate (integer, optional) |
| `LOCAL_TTS_VOICE_NAME` | Local | Voice name keyword e.g. `zira`, `huihui` (optional) |

## Colab Usage

1. Open the notebook directly:
   [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/pingqLIN/voice-mimic/blob/main/notebooks/voice-mimic-colab.ipynb)
2. _(Remote API only)_ Set `DASHSCOPE_API_KEY` in Colab Secrets
3. Run cells in order

## License

[MIT License](https://opensource.org/licenses/MIT)

## 🤖 AI-Assisted Development

This project was developed with AI assistance.

**AI Models/Services Used:**

- Claude Sonnet 4.6 (Anthropic)

> ⚠️ **Disclaimer:** While the author has made every effort to review and validate the AI-generated code, no guarantee can be made regarding its correctness, security, or fitness for any particular purpose. Use at your own risk.
