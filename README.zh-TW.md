# voice-mimic

以 Colab Notebook 為基礎的語音模擬專案。

## 專案結構
- `notebooks/voice-mimic-colab.ipynb`：原始流程 Notebook
- `src/app.py`：從 Notebook `%writefile` 抽出的可維護程式碼
- `requirements.txt`：Python 依賴

## 本機執行
```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
python src/app.py
```

## 執行模式
介面中可切換兩種模式：

1. **遠端 API（DashScope 聲音分身）**
	- 需要 `DASHSCOPE_API_KEY`（或 `API_KEY`）
	- 支援參考音訊建立聲音分身

2. **本地端模型（離線 TTS）**
	- 不需要 API Key
	- 使用本機語音引擎（`pyttsx3`）離線合成
	- 此模式不使用聲音分身（僅文字轉語音）

### 遠端模式環境變數
- `DASHSCOPE_API_KEY`：DashScope API Key
- `DASHSCOPE_HTTP_URL`：可選，自訂 HTTP 端點
- `DASHSCOPE_WS_URL`：可選，自訂 WebSocket 端點

### 本地模式可選環境變數
- `LOCAL_TTS_RATE`：語速（整數）
- `LOCAL_TTS_VOICE_NAME`：語音名稱關鍵字（例如 `zira`、`huihui`）

## Colab 使用
1. 上傳 `notebooks/voice-mimic-colab.ipynb` 到 Colab
2. （若用遠端 API）在 Colab Secrets 設定 `DASHSCOPE_API_KEY`
3. 依序執行儲存格
