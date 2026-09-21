# 03 — CI/CD：推上去之後自己跑測試、自己部署

> 推 `main` → GitHub 跑 570 多個測試 → **測試過了才部署** → 部署完自動確認站台活著。
> 設定檔在 [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)，結果看 repo 的 **Actions** 分頁。

---

## 現在是什麼狀態

| | 誰做 | 要不要設定 |
|---|---|---|
| 推上去跑測試 | GitHub Actions | **不用**，已經會動了 |
| 測試過了才部署 | GitHub Actions 打 Render 的 Deploy Hook | 要，見下面「一次性設定」 |
| 部署完確認站台活著 | GitHub Actions | 要，設一個變數 |
| 服務本身（前端、後端、資料庫） | Render，定義在 [`render.yaml`](../render.yaml) | 第一次要在 Render 後台建立 |

**還沒做設定也不會壞**：部署那一段會自己跳過，測試照跑。

---

## 為什麼不直接用 Render 的 Auto-Deploy

Render 連上 GitHub 之後，預設是「推上去就部署」。問題是**它不管測試有沒有過**——
有人推了一個會讓 70 支路由全掛的改動，Render 一樣照部署，線上就壞了。

所以這裡的作法是：

```
推 main ─→ GitHub Actions 跑測試 ─→ 過了 ─→ 打 Render 的 Deploy Hook ─→ 部署
                                └→ 沒過 ─→ 停在這裡，線上維持原樣
```

要這樣做，**Render 後台那邊的 Auto-Deploy 要關掉**，否則兩邊會各部署各的。

---

## 一次性設定

### 第 1 步　在 Render 建立服務（如果還沒建）

Render 後台 → **New** → **Blueprint** → 選這個 repo。
它會讀 [`render.yaml`](../render.yaml)，一次建好三個東西：

| 名稱 | 是什麼 |
|---|---|
| `fambudget-web` | 前端（純靜態） |
| `fambudget-backend` | 後端（FastAPI） |
| `fambudget-db` | PostgreSQL |

接著到 `fambudget-backend` 的 **Environment** 把這幾個機密填進去
（`render.yaml` 裡標了 `sync: false`，不會寫在 repo 裡）：

`JWT_SECRET`、`BREVO_API_KEY`、`MAIL_FROM`、`MODEL_BASE_URL`、`MODEL_API_KEY`、`ADMIN_EMAILS`

> ⚠️ 後端的服務名稱**不可以**叫 `fambudget-api`——`fambudget-api.onrender.com`
> 已經是別人的服務了，指過去會把使用者的資料送到陌生人的伺服器。

### 第 2 步　關掉 Render 的 Auto-Deploy

兩個服務都要：**Settings** → **Build & Deploy** → **Auto-Deploy** → 改成 **No**。

### 第 3 步　拿 API 金鑰與服務 ID

**API 金鑰**：右上角頭像 → **Account Settings** → **API Keys** → **Create API Key**。
⚠️ 那把金鑰等同你的 Render 帳號權限，只能放進 GitHub Secrets，不要貼進 repo 或群組。

**服務 ID**：打開那個服務，看網址最後一段：

```
https://dashboard.render.com/web/srv-d1abc2de3fg4h5i6j7k0
                                  ^^^^^^^^^^^^^^^^^^^^^^^ 這一段
```

前端、後端各一個。

### 第 4 步　放進 GitHub

repo → **Settings** → **Secrets and variables** → **Actions**

**Secrets** 分頁按 **New repository secret**，加一個：

| 名字 | 值 |
|---|---|
| `RENDER_API_KEY` | 第 3 步那把金鑰 |

**Variables** 分頁按 **New repository variable**，加四個（這四個不是機密）：

| 名字 | 值 |
|---|---|
| `RENDER_BACKEND_SERVICE_ID` | 後端的 `srv-...` |
| `RENDER_WEB_SERVICE_ID` | 前端的 `srv-...` |
| `BACKEND_URL` | `https://fambudget-backend.onrender.com` |
| `WEB_URL` | `https://fambudget-web.onrender.com` |

設完就好了。下一次推 `main` 就會自己跑完整套。

---

## 四個人都看得到 Render 的 log

Render 後台的 log **只有那個 workspace 的成員進得去**——四個人裡只有一個人有
Render 帳號的話，另外三個人等於看不到部署結果。

所以部署不是用 Deploy Hook（打完就結束、什麼都看不到），而是走 Render 的 API：
[`.github/scripts/render_deploy.py`](../.github/scripts/render_deploy.py)
一邊等一邊把 Render 的 log 抓下來印出來，**原封不動、不加前綴、不改字**：

```
==> Cloning from https://github.com/cbes502034/final_project
==> Checking out commit a15ced4 in branch main
==> Running build command 'pip install -r requirements.txt'...
...
==> Build successful 🎉
==> Deploying...
INFO  [alembic.runtime.migration] Running upgrade  -> 0001
INFO:     Uvicorn running on http://0.0.0.0:10000
==> Your service is live 🎉
```

這些字會進 GitHub Actions 的 log 與 Summary，**那兩個地方是公開的**，
所以不用 Render 帳號也看得到同一份 log。

> 如果那個方案的 API 不開放 `/v1/logs`，程式會印一行「拿不到 log」然後繼續，
> 部署狀態照樣會有，完整的 log 就得進 Render 後台看。

---

## 怎麼看結果

**GitHub → Actions 分頁。** 每一次推送一列：

| 看到什麼 | 意思 |
|---|---|
| 🟡 黃點 | 正在跑 |
| ✅ 綠勾 | 測試過了、部署也打出去了 |
| ❌ 紅叉 | 點進去看是哪一個 job |

三個 job 各自的意思：

| Job | 紅了代表 |
|---|---|
| **測試** | 程式壞了。點進去看是哪一個測試，**線上沒有被動到** |
| **部署到 Render** | Render 那邊建置或上線失敗。**Render 的 log 就印在那個 job 裡面**，直接往下看 |
| **部署後確認** | Render 說上線了，但我們的 `/healthz` 叫不動。看上一個 job 的 Render log |

每次跑完，Actions 頁面下面的 **Summary** 會直接寫結果與網址。

### 自己手動跑一次

Actions 分頁 → 左邊點 **CI** → 右邊 **Run workflow**。

---

## 每個人平常會遇到的

**我推自己的分支，也會跑嗎**
會。`on.push.branches: ["**"]` ——每個人的分支推上去都會跑測試，
不用等合併才發現壞了。**但只有 `main` 會部署。**

**連續推好幾次**
只有最後一次會跑完，前面的會被取消（`concurrency`），不會排隊。

**測試在我電腦上是綠的，CI 卻紅了**
最常見是這兩個：

| | |
|---|---|
| 少 commit 檔案 | `git status` 看看有沒有漏加。CI 只看得到推上去的東西 |
| 文件跟程式走散 | `test_consistency.py` 會檢查。跑 `python backend/tools/sync_spec.py`、`sync_devguide.py` 重新產生，再推一次 |

**部署完第一次開很慢**
Render 免費方案沒人用就會休眠，第一次請求要等 30～60 秒叫醒它。
「部署後確認」那個 job 最多等 10 分鐘，就是為了這件事。

---

## 踩過的坑

**`secrets` 不可以寫在 `if:` 裡面。**
GitHub 的 `if` 只認得 `github`、`needs`、`vars`、`env`、`steps` 這幾個 context。
寫了 `if: ${{ secrets.X != '' }}` 的話，**整個 workflow 會被拒絕解析、一個 job 都不會建立**，
Actions 分頁上只會看到一列紅的、點進去什麼都沒有。

正確的寫法是先用一個步驟把「有沒有設定」轉成 output，再拿 output 去判斷——
`ci.yml` 的 `deploy` job 裡那個 `看設定好了沒` 步驟就是在做這件事。

---

## 相關檔案

| 檔案 | 做什麼 |
|---|---|
| [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | 這一整套 |
| [`.github/scripts/render_deploy.py`](../.github/scripts/render_deploy.py) | 叫 Render 部署，並把它的 log 原樣印出來 |
| [`render.yaml`](../render.yaml) | Render 上三個服務長什麼樣 |
| [`backend/.python-version`](../backend/.python-version) | CI 與 Render 用哪個 Python（同一個來源） |
| [`backend/requirements.txt`](../backend/requirements.txt) | CI 與 Render 裝的套件 |
