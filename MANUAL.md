# 台股 KD 訊號自動偵測機器人操作手冊

## 1. WSL 環境設定 (Conda)

### 1.1 初始化 Conda 環境
假設您已經安裝好 Conda (Miniconda 或 Anaconda)，請在 WSL Terminal 中執行：

```bash
# 建立環境 (指定 Python 3.12)
conda create -n stock-bot python=3.12 -y

# 啟用環境
conda activate stock-bot

# 安裝套件
pip install -r requirements.txt
```

### 1.2 本地測試執行
執行前請確保您已經：
1. 將 Google Service Account 金鑰檔案放在專案根目錄，命名為 `service-account.json`。
2. 建立 `.env` 檔案並填入 LINE Token 和 Sheet URL。

```bash
# 執行主程式
python main.py
```

## 2. GitHub 部署與推送

### 2.1 Git 初始化與推送
當您準備好將程式碼推送到 GitHub 時：

```bash
# 1. 初始化 Git (如果尚未初始化)
git init

# 2. 加入所有檔案 (會自動排除 .gitignore 中的檔案)
git add .

# 3. 提交變更
git commit -m "Initial commit of Stock KD Bot"

# 4. 設定遠端倉庫 (請將 URL 替換為您的 Repo URL)
# git remote add origin https://github.com/your-username/your-repo.git

# 5. 推送
# git push -u origin main
```

### 2.2 GitHub Repositories Secrets 設定
在 GitHub Repo 的 **Settings > Secrets and variables > Actions** 中新增以下 Secrets：

1. `GOOGLE_CREDS`: 將 `service-account.json` 的 **內容 (完整 JSON 字串)** 貼入。
2. `LINE_CHANNEL_ACCESS_TOKEN`: LINE Bot Channel Access Token。
3. `LINE_CHANNEL_SECRET`: LINE Bot Channel Secret.
4. `GOOGLE_SHEET_URL`: Google Sheets 的網址。

## 3. Google Sheets 設定
1. 建立一個 Google Sheet。
2. 將工作表名稱改為 `Subscribers`。
3. 第一列設定欄位名稱：`userId`, `ticker`。
4. **重要**：將 Service Account 的 Email 加入共用 (Share)，並給予編輯權限。
