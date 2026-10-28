# report/：專案報告

成品：**`家庭記帳_專案報告.pptx`**（26 頁，產品介紹：照完整流程影片用一輪，最後是接下來上線的兩件事；
每一頁的畫面是那一步的**影片片段**，一進到那一頁就自動播放、播完停在最後一格，有編號的頁 ①②③ 在停格時浮出來；
每一頁都有講者備註，封面與結尾有網站的 QR code）；
**`qa/家庭記帳_完整流程.mp4`**（在本機從空帳號開始走一遍的影片，接 Claude，約 6 分鐘；字幕在畫面下方的字幕帶，不遮網頁；線上站也能錄，見下面）。

簡報上的數字都不是手打的，是從程式與結果檔算出來的。模型評測跑完、測試重跑之後，照下面重新產生，數字就會更新。

## 重新產生

```bash
python report/collect.py                 # 數字 → report/data/facts.json（會跑 pytest --collect-only）
cd report && npm install && node build_deck.js            # 專案報告 → 家庭記帳_專案報告.pptx
```

模型的成績：在 `backend/` 底下跑 `python tools/eval_nlp.py --label <名稱>`，結果會存到 `backend/eval/results/`；
再跑上面兩行，「AI 記帳：準、快」那一頁就換成新的成績（取名稱含 live 的那一份）。

自動播放是借這台電腦的 PowerPoint 設定的（`lib/autoplay.ps1`，build_deck.js 最後會自己跑）；沒有 PowerPoint 就是點一下影片才播。
PowerPoint 開著這份簡報時存不進去：先關掉，或在後面帶一個新檔名（`node build_deck.js 新檔名.pptx`）。

## 檔案

| 檔案 | 做什麼 |
|---|---|
| `collect.py` | 收集數字：路由數、資料表數、測試數、留出集題型、評測結果、端到端結果 |
| `build_deck.js` | 用 pptxgenjs 產生簡報（版型、配色、圖表都在這裡） |
| `qa/record_demo.py` | 完整流程影片：現場註冊一個家長、邀請一個子女，逐步錄影加字幕帶；同時切出簡報每一頁的片段（`assets/clips/`）；`--trial` 只截圖試跑 |
| `data/e2e.json` | `backend/tools/e2e_check.py` 的結果 |
| `data/facts.json` | `collect.py` 的輸出 |
| `assets/clips/` | 簡報每一頁的影片片段（`.mp4`）與封面（`.png`，停格那一格、編號已畫上）；錄影時一起產生 |
| `assets/qr_site.png` | 網站的 QR code |
| `lib/apply_theme.js` | 把配色寫進簡報的佈景主題（pptxgenjs 本身做不到） |
| `lib/autoplay.ps1` | 用 PowerPoint 把影片設成一進到那一頁就自動播放（pptxgenjs 本身做不到） |

## 影片與簡報畫面怎麼重錄（本機）

不用示範資料：錄影腳本在本機從空帳號走一遍，完整流程影片和簡報每一頁的片段是同一輪錄的。

```bash
# 1. 本機開後端（127.0.0.1:8010）與前端（python -m http.server 5195 --directory frontend）
# 2. 準備帳密 JSON（只給本機用，放暫存資料夾、不要進 repo）：
#    {"parent": {"name", "email", "password"}, "kid": {"email", "password"}}
#    kid 先用 /api/auth/register 建好（本機寄不出信，帳號直接算驗證過）
# 3. 錄影：產出 qa/家庭記帳_完整流程.mp4 與 assets/clips/（每跑一次都會現場註冊家長，要一個沒註冊過的 email；
#    AI 那幾步要 backend/.env 接上模型、加 --ai）。先加 --trial 試跑：不錄影，每一步存一張截圖到 qa/trial/
python report/qa/record_demo.py --target local --ai --accounts <帳密 JSON>
# 4. 重新產生簡報
cd report && node build_deck.js
```

## 影片怎麼錄（線上站）

```bash
python report/qa/record_demo.py            # 終端機會問兩個帳號的 email 與密碼（密碼不顯示、不存檔）
```

- 家長：一個還沒註冊過的 email，影片裡現場註冊；註冊後到信箱打開驗證信，把連結貼回終端機。
- 子女：事先註冊好、點過驗證信、還沒加入家庭的空帳號。
- Gmail 可以用「名字+任意字@gmail.com」，信都寄到同一個信箱。
- 會在網站上留下兩個帳號與它們的資料，錄完可以到「個人資料 › 刪除帳號」刪掉。
