# 🌅 美股近一週波動分析與每日推薦交易標的推播系統

每天早上 **08:00（台灣時間 UTC+8，美股收盤後）** 透過 **GitHub Actions** 自動抓取最新美股數據，分析過去 5 個交易日（近一週）的大盤體溫、11 大板塊資金輪動、波動異常個股，並透過多因子量化模型篩選出**每日推薦交易標的**，自動推播至 **LINE（支援精美 Flex 輪播卡片 + 結構化文字戰報）**。

---

## ✨ 核心功能

1. **📊 大盤與跨資產近一週波動總覽**
   - 追蹤四大指數（`SPY`, `QQQ`, `DIA`, `IWM`）與費半（`SOXX`）的單日漲跌、近 5 日累積漲跌、週振幅、日均真實波動率 (`NATR`) 與 `RSI(14)`。
   - 同步監控跨資產風險指標：`VIX 恐慌指數`、`10年期美債殖利率 (^TNX)`、`黃金 (GLD)`、`比特幣 (BTC-USD)`。
   - 自動判讀市場狀態（🟢 **多頭順勢進攻 Risk-On** / 🟡 **震盪輪動選股 Neutral** / 🔴 **高波動避險 Risk-Off**）。

2. **🔄 11 大產業板塊輪動排行 (Sector Rotation)**
   - 計算 SPDR 11 大板塊 ETF 近 5 日表現與相對標普 500 的超額報酬 (Relative Strength)，快速鎖定領漲強勢族群與資金流出板塊。

3. **⚡ 近一週個股波動異常 & 爆量雷達**
   - 自動偵測 5 日歷史波動率放大比 (`HV5 / HV20`)、週振幅、單日成交量爆發 (`Vol / 20MA`) 與跳空缺口 (`Gap`)。

4. **🎯 每日量化推薦交易標的（三大策略 + ATR 動態風控卡）**
   - **🚀 順勢突破型 (Momentum Breakout)**：股價站上 20MA/50MA、突破或逼近 20 日高點、帶量攻擊且具強勢板塊加持。
   - **🔄 強勢股拉回買點 (Pullback in Uptrend)**：中長期多頭排列（站上 50MA/200MA），近一週隨大盤拉回測試 20MA 支撐、量縮且 RSI 降溫止穩。
   - **⚠️ 空方避險 / 破位警示 (Bearish Breakdown)**：跌破 20MA/50MA 重要均線、放量下殺或波動擴張破底，供放空對沖或多單避開風險參考。
   - **每檔標的皆自動計算**：
     - **量化評分 (0~100 分)** 與 **入選理由標籤**
     - **參考進場區間**
     - **動態停損價 (Stop Loss)**：以 `1.5 × ATR(14)` 計算，避免被日內正常波動洗出場
     - **分批停利目標價 (Take Profit)**：`T1 (2.0 × ATR)` 與 `T2 (3.0 × ATR，風報比 1:2)`

---

## 🛠️ 3 分鐘設定教學（GitHub Actions + LINE Messaging API）

由於 LINE Notify 已終止服務，本專案採用官方標準 **LINE Messaging API**（免費額度即足夠每日晨報推播，且支援精美 Flex 輪播卡片）。

### 步驟一：取得 LINE Channel Access Token
1. 前往 [LINE Developers Console](https://developers.line.biz/) 並登入你的 LINE 帳號。
2. 建立一個 **Provider**（名稱任意，例如 `StockBot`），接著點選 **Create a new channel** → 選擇 **Messaging API**。
3. 建立完成後，進入該 Channel 的 **Messaging API** 分頁：
   - 用手機 LINE 掃描頁面上的 **QR Code**，將這個機器人加為好友。
   - 捲動到最下方找到 **Channel access token (long-lived)**，點擊 **Issue** 產生一組長效 Token 並複製起來。
4. *(選填)* 若你只想推播給特定個人或群組，可在 **Basic settings** 分頁最下方複製你的 **Your user ID**（`U` 開頭字串）。**若不填寫 `LINE_USER_ID`，程式會自動使用 Broadcast 模式推播給所有加入該機器人的好友！**

### 步驟二：在 GitHub 設定 Repository Secrets
1. 打開你的 GitHub Repository (`Hongyu0409/stock`)。
2. 點選上方選單 **Settings** → 左側欄 **Secrets and variables** → **Actions**。
3. 點擊 **New repository secret** 新增以下變數：
   - `LINE_CHANNEL_ACCESS_TOKEN`：貼上剛才複製的 Channel Access Token *(必填)*
   - `LINE_USER_ID`：貼上你的 `U...` User ID *(選填，留空則自動廣播給所有機器人好友)*

### 步驟三：測試手動觸發 & 每日 08:00 自動推播
1. 點選 GitHub 上方選單的 **Actions** → 左側點選 **Daily 08:00 US Stock Volatility & Trading Picks Push**。
2. 點擊右側 **Run workflow** 按鈕即可立即測試推播到你的手機 LINE，同時在 GitHub Actions 頁面下方會直接生成完整的 Markdown 戰報表格！
3. 之後每天早上 **08:00（台灣時間）** 系統就會自動執行並推播。

---

## 💻 本地端執行與自訂選股池

```bash
# 1. 安裝套件
pip install -r requirements.txt

# 2. 預覽報表與 LINE 訊息（使用模擬資料測試，不發送 API）
python main.py --demo --dry-run

# 3. 抓取真實最新美股收盤資料並輸出至 reports/latest_report.md
python main.py --dry-run

# 4. 設定 .env 後實際推播至 LINE
cp .env.example .env
python main.py
```

如需新增或調整自選股、ETF 或 ATR 停損倍數，直接編輯 [`config.yaml`](config.yaml) 即可。
