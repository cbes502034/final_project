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

### 第 3 步　拿 Deploy Hook

一樣在 **Settings** → **Build & Deploy** → **Deploy Hook**，複製那個網址
（長得像 `https://api.render.com/deploy/srv-xxxx?key=yyyy`）。兩個服務各一個。

> 那個網址**等同部署權限**，不要貼進 repo、不要貼進群組。

### 第 4 步　放進 GitHub

repo → **Settings** → **Secrets and variables** → **Actions**

**Secrets** 分頁按 **New repository secret**，加兩個：

| 名字 | 值 |
|---|---|
| `RENDER_BACKEND_HOOK` | `fambudget-backend` 的 Deploy Hook |
| `RENDER_WEB_HOOK` | `fambudget-web` 的 Deploy Hook |

**Variables** 分頁按 **New repository variable**，加兩個（這兩個不是機密）：

| 名字 | 值 |
|---|---|
| `BACKEND_URL` | `https://fambudget-backend.onrender.com` |
| `WEB_URL` | `https://fambudget-web.onrender.com` |

設完就好了。下一次推 `main` 就會自己跑完整套。

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
| **部署到 Render** | Deploy Hook 打不出去（secret 填錯、或 Render 那邊刪掉了） |
| **部署後確認** | 部署上去了但站台叫不動。到 Render 後台看 **Logs** |

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

## 相關檔案

| 檔案 | 做什麼 |
|---|---|
| [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | 這一整套 |
| [`render.yaml`](../render.yaml) | Render 上三個服務長什麼樣 |
| [`backend/.python-version`](../backend/.python-version) | CI 與 Render 用哪個 Python（同一個來源） |
| [`backend/requirements.txt`](../backend/requirements.txt) | CI 與 Render 裝的套件 |
