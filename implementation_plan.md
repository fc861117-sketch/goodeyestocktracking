# [股癌自動分析系統] 靜態網頁發布與族群輪動分析計畫

為了讓您的分析結果能順利在 GitHub 網站上顯示，並追蹤 5 月份以來的市場輪動狀況，我們需要對系統架構做一些升級。

## User Review Required

> [!WARNING]
> 系統將會使用 CPU 進行 5 月份以來所有影片的語音辨識。因為您的 CUDA 驅動較舊，這可能會需要相當長的時間（約十幾個小時的運作時間）。我們將設計一個批次處理機制，讓您可以分批執行。

## Open Questions

> [!IMPORTANT]
> 1. 您希望歷史影片的分析是「一次全部處理完」還是「從最新的開始，一天自動處理幾部」？（建議後者，避免您的電腦短時間內負載過大）
> 2. 關於「族群輪動」，您有希望看到特定格式的圖表嗎？例如：雷達圖、每週板塊熱度變化圖？還是只要一個依照產業分門別類的推薦清單即可？

## Proposed Changes

### 1. 靜態網頁生成器 (Static Site Generation for GitHub Pages)
GitHub Pages 不支援動態的 Python (Flask) 伺服器，所以我們需要把目前動態生成的 Dashboard 轉為靜態網頁（Static HTML/JSON）。

#### [MODIFY] [main.py](file:///C:/Users/YU%20HSUAN/.gemini/antigravity-ide/scratch/gooaye-stock-analyzer/main.py)
- 新增 `generate-static` 命令。
- 在每次 `analyze` 完成後，自動觸發靜態網頁生成，並使用 git 推送到 GitHub。

#### [NEW] [modules/static_generator.py](file:///C:/Users/YU%20HSUAN/.gemini/antigravity-ide/scratch/gooaye-stock-analyzer/modules/static_generator.py)
- 讀取 SQLite 資料庫，將所有的股票推薦、分析報告匯出成 `data.json`。
- 複製現有的 `dashboard.html`，並改成純前端渲染（使用 JavaScript 讀取 `data.json`）。
- 產出檔案放置於 `docs/` 資料夾，方便啟用 GitHub Pages。

### 2. 歷史影片回溯功能 (Historical Video Processing)
目前的 RSS 來源最多只能抓到最新的 15 部影片，無法追溯到 5 月份。我們將改用 `yt-dlp` 的功能來過濾日期。

#### [MODIFY] [modules/youtube_monitor.py](file:///C:/Users/YU%20HSUAN/.gemini/antigravity-ide/scratch/gooaye-stock-analyzer/modules/youtube_monitor.py)
- 新增 `fetch_videos_since(date_string)` 函式，使用 `yt-dlp` 搭配 `--dateafter 20260501` 指令，抓取 5 月份以後的所有影片。
- 修改 `main.py` 加入歷史回溯模式指令。

### 3. 族群輪動追蹤 (Sector Rotation Tracking)
強化 AI 分析模組，強制提取「產業板塊」標籤，並在網頁端呈現板塊熱度隨時間的變化。

#### [MODIFY] [modules/ai_analyzer.py](file:///C:/Users/YU%20HSUAN/.gemini/antigravity-ide/scratch/gooaye-stock-analyzer/modules/ai_analyzer.py)
- 修改給 Gemini 的系統提示詞（Prompt），要求對每一檔股票加上精確的「所屬產業/概念板塊」。
- 提取主委對整個大盤板塊輪動的觀點，並記錄到報告中。

#### [MODIFY] [static/app.js](file:///C:/Users/YU%20HSUAN/.gemini/antigravity-ide/scratch/gooaye-stock-analyzer/static/app.js)
- 新增「族群輪動圖表（Sector Trend Chart）」。
- 根據 `published_at`（發布時間）來繪製各個產業在不同集數被提及次數與推薦強度的趨勢變化。

## Verification Plan

### 自動化測試
- 執行指令測試 `yt-dlp` 能否正確列出 5 月份至今的影片 ID。
- 模擬分析 2 部影片，確認靜態 `docs/index.html` 生成成功。

### 手動驗證
- 開啟 `docs/index.html` 確保純靜態環境下圖表能正常顯示。
- 觸發 Git 推送，前往您的 GitHub Repo，於 Settings > Pages 開啟 `docs` 資料夾的發布功能。
- 等待約 2 分鐘後，前往 `https://fc861117-sketch.github.io/goodeyestocktracking/` 驗證上線狀況。
