# report/：期末報告簡報

成品：**`家庭記帳_期末報告.pptx`**（20 頁，每一頁都有講者備註）。

簡報上的數字都不是手打的，是從程式與結果檔算出來的。模型評測跑完、測試重跑之後，照下面重新產生，數字就會更新。

## 重新產生

```bash
python report/collect.py                 # 數字 → report/data/facts.json（會跑 pytest --collect-only）
cd report && npm install && node build_deck.js
```

模型的成績：在 `backend/` 底下跑 `python tools/eval_nlp.py --label <名稱>`，結果會存到 `backend/eval/results/`；
再跑上面兩行，「評測結果」那一頁會自動多一欄，「錯誤分析」會改成看模型錯在哪。

## 檔案

| 檔案 | 做什麼 |
|---|---|
| `collect.py` | 收集數字：路由數、資料表數、測試數、留出集題型、評測結果、端到端結果 |
| `build_deck.js` | 用 pptxgenjs 產生簡報（版型、配色、圖表都在這裡） |
| `screenshot.py` | 用本機 Chrome（無頭模式）截畫面到 `assets/`，要先跑 `backend/tools/demo_seed.py` 拿示範帳號的權杖 |
| `data/e2e.json` | `backend/tools/e2e_check.py` 的結果 |
| `data/facts.json` | `collect.py` 的輸出 |
| `assets/` | 畫面截圖 |
| `lib/apply_theme.js` | 把配色寫進簡報的佈景主題（pptxgenjs 本身做不到） |

## 截圖怎麼重拍

```bash
# 1. 本機開一台用全新 SQLite 的後端（見 backend/tools/e2e_check.py 開頭）與前端（python -m http.server 5195 --directory frontend）
# 2. 建示範資料，權杖寫到暫存資料夾（不要放進 repo）
python backend/tools/demo_seed.py --base http://localhost:8010 --tokens %TEMP%\demo_tokens.json
# 3. 截圖
python report/screenshot.py --tokens %TEMP%\demo_tokens.json
```
