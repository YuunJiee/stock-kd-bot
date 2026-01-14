# Stock KD Signal Bot (台股 KD 訊號偵測機器人) v2.0

[![Stock KD Monitor](https://github.com/yuunjee/stock-kd-bot/actions/workflows/monitor.yml/badge.svg)](https://github.com/yuunjee/stock-kd-bot/actions/workflows/monitor.yml)

這是一個基於 Python 的自動化機器人，用於監測台股的 KD 指標訊號，並透過 LINE Bot 發送專業的買賣通知。

## 🌟 核心功能 (v2.0 升級版)

### 1. 智慧策略監測 (Smart Strategy)
本機器人不只是單純的 KD 交叉，更加入了 **趨勢濾網** 與 **鈍化處理**，大幅提高勝率。

*   **📈 買進訊號 (Strong Buy)**
    *   **條件 A**：$K < 20$ 且 $K$ 向上突破 $D$ (黃金交叉)。
    *   **條件 B (趨勢保護)**：收盤價必須 **大於 60日均線 (季線)**，避開空頭接刀。
*   **📉 賣出訊號 (Sell / Hold)**
    *   **條件**：$K > 80$ 且 $K$ 向下跌破 $D$ (死亡交叉)。
    *   **濾網 (高檔鈍化)**：若 **RSI > 70**，視為強勢鈍化，**不發送賣出訊號** (改為 **HOLD** 續抱通知)，吃到主升段。

### 2. 進階基本面與籌碼資訊
通知訊息卡片 (Flex Message) 包含：
*   **基本面數據**：即時顯示本益比 (PE)、每股盈餘 (EPS)、殖利率 (Yield)。
*   **爆量警示**：若當日成交量 > 5日均量的 2倍，顯示 `🔥 爆量攻擊` 標籤。

### 3. 自動化與回測
*   **backtest.py**：內建回測腳本，可驗證不同個股在過去一年的策略表現。
*   **GitHub Actions**：每日 13:10 自動執行爬蟲與分析。

---

## 技術棧

*   **語言**：Python 3.12
*   **數據來源**：`yfinance`
*   **技術指標**：`pandas-ta` (KD, RSI, MA, MACD)
*   **資料庫**：Google Sheets (`gspread`)
*   **通知**：LINE Messaging API (`line-bot-sdk`)

## 安裝與執行

### 1. 環境設定

建議使用 Conda 或 venv 建立獨立的 Python 3.12 環境：

```bash
conda create -n stock-bot python=3.12 -y
conda activate stock-bot
pip install -r requirements.txt
```

### 2. 設定檔

請複製範例檔案並填入您的金鑰：

```bash
cp .env.example .env
```

`service-account.json` (Google Service Account Key) 也需放在專案根目錄。

### 3. 本地執行

**執行主程式 (發送訊號)**：
```bash
python main.py
```

**執行策略除錯 (測試版)**：
```bash
python debug_strategy.py
```

**執行歷史回測**：
```bash
python backtest.py
```

## GitHub Actions 部署

本專案已設定好 `.github/workflows/monitor.yml`，需在 GitHub Repository Settings 中設定以下 Secrets：

*   `GOOGLE_CREDS`: Google Service Account JSON 內容
*   `LINE_CHANNEL_ACCESS_TOKEN`
*   `LINE_CHANNEL_SECRET`
*   `GOOGLE_SHEET_URL`

## License

MIT
