---
title: FamBudget Parser
emoji: 🧾
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# 家庭記帳：記帳解析模型服務

把 `ml/train_colab.ipynb` 微調出來的 Qwen2.5-1.5B（GGUF q4_k_m）跑成 OpenAI 相容的 API。
後端的 `services/llm/client.py` 用 `MODEL_PROVIDER=openai` 直接打它，程式不用改。

## 開 Space（10 分鐘）

1. huggingface.co → 右上角 **New Space**
   - Space name：`fambudget-parser`
   - SDK：**Docker** → Blank
   - Hardware：**CPU basic（免費）**
2. 把這個資料夾的 `Dockerfile` 跟 `README.md` 上傳到 Space（Files → Add file → Upload files）
3. Settings → **Variables and secrets**
   - New variable：`MODEL_REPO` = `你的帳號/qwen2.5-1.5b-fambudget-GGUF:Q4_K_M`
   - （可選）New secret：`API_KEY` = 自己編一串，設了別人就不能白用你的 Space
4. 等它 Build 完（Logs 出現 `server is listening`）

## 接到後端

`backend/.env`（Render 上是 Environment 頁面）：

```
MODEL_PROVIDER=openai
MODEL_BASE_URL=https://你的帳號-fambudget-parser.hf.space
MODEL_API_KEY=上面的 API_KEY（沒設就留空）
MODEL_NAME=qwen2.5-1.5b-fambudget
MODEL_TIMEOUT_SECONDS=90
```

確認接上：在 `backend/` 底下跑 `python -m app.cli check-config`，再跑 `python tools/eval_nlp.py --limit 3`。

## 要知道的事

- **免費 CPU 很慢**：一段話大約 10～40 秒（看切出幾筆）。所以逾時要放寬，展示時建議還是用商業 API。
- **會睡著**：48 小時沒人用 Space 會休眠，第一次叫醒要幾分鐘（重新下載約 1 GB 的模型）。
  展示前先打開 Space 的網頁把它叫醒。
- 這個服務只負責解析；財務建議可以繼續用商業 API（`ADVICE_PROVIDER`、`ADVICE_API_KEY`）。
