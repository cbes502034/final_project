# report/：期末報告簡報

成品：**`家庭記帳_期末報告.pptx`**（每一頁都有講者備註；封面與結尾有網站的 QR code）；
**`qa/家庭記帳_完整流程.mp4`**（在本機從空帳號開始走一遍的影片，約 6 分鐘；線上站也能錄，見下面）。

簡報上的數字都不是手打的，是從程式與結果檔算出來的。模型評測跑完、測試重跑之後，照下面重新產生，數字就會更新。

## 重新產生

```bash
python report/collect.py                 # 數字 → report/data/facts.json（會跑 pytest --collect-only）
cd report && npm install && node build_deck.js          # 重點版（18 頁）：開場 3、四個領域各 3、結語 3
node build_deck.js --demo                                  # 產品展示（13 頁）：照完整流程影片用一輪，畫面為主 → 家庭記帳_產品展示.pptx
node build_deck.js --full                                  # 完整版：每個畫面、評測細節、每一輪測試都有 → 家庭記帳_期末報告_完整版.pptx
```

模型的成績：在 `backend/` 底下跑 `python tools/eval_nlp.py --label <名稱>`，結果會存到 `backend/eval/results/`；
再跑上面兩行，「評測結果」那一頁會自動多一欄，「錯誤分析」會改成看模型錯在哪。

## 檔案

| 檔案 | 做什麼 |
|---|---|
| `collect.py` | 收集數字：路由數、資料表數、測試數、留出集題型、評測結果、端到端結果 |
| `build_deck.js` | 用 pptxgenjs 產生簡報（版型、配色、圖表都在這裡） |
| `screenshot.py` | 用本機 Chrome（無頭模式）截畫面到 `assets/`；用 API 登入本機帳號拿權杖，不在畫面上打密碼 |
| `qa/record_demo.py` | 完整流程影片：在線上站現場註冊一個家長、邀請一個子女，逐步錄影加字幕；`--trial` 只截圖試跑 |
| `data/e2e.json` | `backend/tools/e2e_check.py` 的結果 |
| `data/facts.json` | `collect.py` 的輸出 |
| `assets/` | 畫面截圖 |
| `lib/apply_theme.js` | 把配色寫進簡報的佈景主題（pptxgenjs 本身做不到） |

## 截圖怎麼重拍

不用示範資料：截圖的帳上資料是錄影腳本在本機從空帳號走一遍留下來的。

```bash
# 1. 本機開後端（127.0.0.1:8010）與前端（python -m http.server 5195 --directory frontend）
# 2. 準備帳密 JSON（只給本機用，放暫存資料夾、不要進 repo）：
#    {"parent": {"name", "email", "password"}, "kid": {"email", "password"}, "admin": {"email", "password"}}
#    kid 先用 /api/auth/register 建好；admin 建好之後跑 python -m app.cli make-admin <email>
# 3. 本機走一遍完整流程，帳上才有資料
python report/qa/record_demo.py --target local --accounts <帳密 JSON>
# 4. 截圖（段落記帳那張要真模型，預設不重截）
python report/screenshot.py --accounts <帳密 JSON>
```

## 影片怎麼錄（線上站）

```bash
python report/qa/record_demo.py            # 終端機會問兩個帳號的 email 與密碼（密碼不顯示、不存檔）
```

- 家長：一個還沒註冊過的 email，影片裡現場註冊；註冊後到信箱打開驗證信，把連結貼回終端機。
- 子女：事先註冊好、點過驗證信、還沒加入家庭的空帳號。
- Gmail 可以用「名字+任意字@gmail.com」，信都寄到同一個信箱。
- 會在網站上留下兩個帳號與它們的資料，錄完可以到「個人資料 › 刪除帳號」刪掉。
