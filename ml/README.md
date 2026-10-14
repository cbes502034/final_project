# ml/：微調自己的記帳解析模型（加分項）

**上線用的是商業 API**（Claude 或 OpenAI，見 `docs/03-LLM實作規劃.md`），這個資料夾不跑也不影響系統。
它是報告裡的對照組：「通用大模型＋prompt」跟「微調過的小模型」在同一份留出集上差多少。

## 流程

```
make_data.py ──► data/train.jsonl ──► build_sft.py ──► data/sft.jsonl ＋ data/tools.json
                                                              │
                                     train_colab.ipynb（Colab T4，免費） ◄┘
                                              │ QLoRA 微調 Qwen2.5-1.5B-Instruct → GGUF q4_k_m
                                              ▼
                                     Hugging Face Hub（模型檔）
                                              │
                                     space/（Hugging Face Space，llama-server）
                                              │ OpenAI 相容 /v1/chat/completions
                                              ▼
                       backend/.env 的 MODEL_BASE_URL → tools/eval_nlp.py 量成績
```

| 檔案 | 做什麼 |
|---|---|
| `make_data.py` | 用模板組 1500 題句子，答案在組的時候就知道（日期用 `toolkit/dates.py` 換算） |
| `build_sft.py` | 轉成對話格式。**system／user 直接用後端的 `parse.build_prompt()`**，訓練跟上線一字不差 |
| `train_colab.ipynb` | Unsloth QLoRA 訓練、試一題、轉 GGUF、推上 Hugging Face |
| `space/` | Hugging Face Space 的 Dockerfile 與說明 |
| `data/` | 產生好的資料（已經放進 repo，Colab 直接 clone 就有） |

## 要準備的帳號

- Google 帳號（Colab）
- Hugging Face 帳號，以及一組 **write** token：放在 Colab 左邊 🔑 Secrets 的 `HF_TOKEN`，**不要貼進程式碼、不要 commit**

## 跑法

```bash
python ml/make_data.py        # 改了模板才要重跑
python ml/build_sft.py        # 改了 backend/app/services/llm/parse.py 的 build_prompt 一定要重跑
```

然後把 `train_colab.ipynb` 上傳到 Colab（檔案 → 上傳筆記本），照第一格的說明做。

## 設計重點（報告可以寫）

- **分類 id 每題打亂、偶爾多一兩個家庭自訂分類**：模型要學的是「從 prompt 的清單裡挑 id」，不是背「餐飲＝1」。
  上線時每個家庭的自訂分類 id 都不一樣，背答案的模型一換家庭就錯。
- **只學回答（train_on_responses_only）**：prompt 很長（規則＋分類清單＋工具定義），不讓 loss 花在背 prompt。
- **日期不完全靠模型**：上線時 `postprocess()` 會用 `toolkit/dates.py` 依 span 重算，模型差一天也救得回來。
- **留出集不是這裡產生的**：`backend/eval/heldout.jsonl` 另外寫，`make_data.py` 也會剔掉跟它一模一樣的句子。
  但兩者都是 AI 寫的、句型相近——報告要寫出這個限制，並列出人工抽查了幾題。

## 已知限制

- 訓練資料是模板產生的，口語變化比真人少（例如「欸今天又去全家」這種語氣詞）。
- 免費 Space 是 CPU，一段話要 10～40 秒，展示時建議用商業 API。
