# voice-mimic

以 Colab Notebook 為基礎的語音模擬專案

## 專案結構
- 
otebooks/voice-mimic-colab.ipynb 原始流程 Notebook
- src/app.py 從 Notebook %%writefile 抽出的可維護程式碼
- equirements.txt Python 依賴

## 本機執行
`ash
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
python src/app.py
`

## Colab 使用
1. 上傳 
otebooks/voice-mimic-colab.ipynb 到 Colab
2. 在 Colab 設定 DASHSCOPE_API_KEY Secret
3. 依序執行儲存格
