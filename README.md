# 股癌 (Gooaye) 自動影片分析 & 股票推薦系統

自動監控股癌 YouTube/Podcast 更新，使用 AI 分析內容中提及的股票，結合即時市場數據生成完整投資建議報告，並在 Web Dashboard 上持續追蹤推薦標的的績效。

## 🚀 快速開始

### 前置需求

- Python 3.9+
- NVIDIA GPU（有 CUDA 支援，推薦 6GB+ VRAM）
- FFmpeg（語音轉文字需要）
- Google Gemini API Key（免費）

### 安裝

```bash
# 1. 安裝 Python 套件
pip install -r requirements.txt

# 2. 安裝 FFmpeg（如尚未安裝）
winget install Gyan.FFmpeg

# 3. 設定 API Key
# 編輯 config.json，填入你的 Gemini API Key
```

### 使用方式

```bash
# 檢查新影片並分析（首次使用建議先執行這個）
python main.py analyze

# 更新所有推薦標的的最新股價
python main.py update-prices

# 啟動 Web Dashboard 查看報告
python main.py dashboard
```

## 📊 功能介紹

### 自動分析流程
1. 監控股癌 YouTube 頻道 RSS，偵測新影片
2. 下載音訊，優先使用字幕，否則用 Whisper 轉錄
3. 使用 Gemini AI 分析內容，提取個股、產業趨勢、總經觀點
4. 查詢即時股票數據（台股 + 美股）
5. 生成短中長期投資建議（目標價、買入價、停損價）

### Web Dashboard
- 📺 **最新報告**：最新一集的完整分析
- 📈 **標的追蹤**：所有推薦標的的績效走勢圖
- 📋 **歷史報告**：所有歷史分析記錄
- 🏭 **產業分布**：推薦標的的產業和情緒分布

## ⚠️ 免責聲明

本系統產出的報告僅供參考，不構成任何投資建議。所有投資決策應由使用者自行評估風險後做出。
