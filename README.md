# 廣東話粗口生成器

這是一個 Flask 應用程式，會使用 Cloudflare Workers AI 將使用者輸入改寫成更自然的廣東話，並插入廣東話粗口。

## 必填環境變數

請在你的部署平台設定以下環境變數：

- `CLOUDFLARE_API_TOKEN`：具有 Workers AI 權限的 Cloudflare API Token
- `CLOUDFLARE_ACCOUNT_ID`：你的 Cloudflare Account ID
- `CLOUDFLARE_MODEL`：可選，預設值為 `@cf/google/gemma-4-26b-a4b-it`

## 部署方式

這個專案已經設定好可用 `Procfile` 方式部署。

- 啟動指令：`gunicorn app:app`
- Python 相依套件：`requirements.txt`
- Web Process 設定檔：`Procfile`

### Render

請使用以下設定：

- Build Command：`pip install -r requirements.txt`
- Start Command：`gunicorn app:app`

然後在 Render 後台加入上面列出的環境變數。

### Railway

Railway 一般可直接使用現有的 `Procfile`。如果需要手動填寫啟動指令，請設為：

- `gunicorn app:app`

然後在 Railway 的 Variables 頁面加入上面列出的環境變數。

### Heroku

請以 Python 應用程式方式部署，並設定必要的 Config Vars。

- `heroku config:set CLOUDFLARE_API_TOKEN=...`
- `heroku config:set CLOUDFLARE_ACCOUNT_ID=...`
- `heroku config:set CLOUDFLARE_MODEL=@cf/google/gemma-4-26b-a4b-it`

## 本機執行

在 Windows PowerShell 中：

```powershell
$env:CLOUDFLARE_API_TOKEN="your_token"
$env:CLOUDFLARE_ACCOUNT_ID="your_account_id"
$env:CLOUDFLARE_MODEL="@cf/google/gemma-4-26b-a4b-it"
c:/Users/cgadmin/cantonese/.venv/Scripts/python.exe app.py
```