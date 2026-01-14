# Stock KD Signal Bot (台股 KD 訊號偵測機器人)

[![Stock KD Monitor](https://github.com/yuunjee/stock-kd-bot/actions/workflows/monitor.yml/badge.svg)](https://github.com/yuunjee/stock-kd-bot/actions/workflows/monitor.yml)

這是一個基於 Python 的自動化機器人，用於監測台股的 KD 指標訊號，並透過 LINE Bot 發送買賣通知。設計用於部署在 GitHub Actions 上每日自動執行。

## 核心功能

*   **自動監測**：每日盤後自動抓取指定股票數據。
*   **策略判斷**：使用 Stochastic Oscillator KD (14, 3) 指標。
    *   🔴 **買入訊號**：$K < 20$ 且 $K$ 向上突破 $D$。
    *   🟢 **賣出訊號**：$K > 80$ 且 $K$ 向下跌破 $D$。
*   **LINE 通知**：偵測到訊號時，自動推播訊息給訂閱該股票的使用者。
*   **雲端管理**：透過 Google Sheets 管理訂閱者名單 (`userId`, `ticker`)。
*   **自動化部署**：整合 GitHub Actions，於每個交易日 (週一至週五) 台北時間 13:10 自動執行。

## 技術棧

*   **語言**：Python 3.12
*   **數據來源**：`yfinance`
*   **技術指標**：`pandas-ta`
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

```bash
python main.py
```

## GitHub Actions 部署

本專案已設定好 `.github/workflows/monitor.yml`，需在 GitHub Repository Settings 中設定以下 Secrets：

*   `GOOGLE_CREDS`: Google Service Account JSON 內容
*   `LINE_CHANNEL_ACCESS_TOKEN`
*   `LINE_CHANNEL_SECRET`
*   `GOOGLE_SHEET_URL`

## 詳細操作手冊

更多關於環境建置 (WSL/Conda) 與 Git 操作的細節，請參閱 [MANUAL.md](./MANUAL.md)。

## License

MIT
