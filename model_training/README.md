# 恢復後的模型開發程式

原模型權重、評測報告仍保留。缺失的 Python 原始碼是依先前實作及保留快取重建，並非從 Git 取回逐字相同的檔案。恢復訓練資料的 SHA-256 與原訓練紀錄相同；提示詞與保留的快取相同。

## 單獨測試

在 `E:\LLM\topic\final_project` 執行：

```powershell
.\.venv\Scripts\python.exe model_training\inference.py "午餐100 晚餐200"
```

預設是模型生成後再由程式驗證。要觀察原始 LLM 答案，加入 `--raw`：

```powershell
.\.venv\Scripts\python.exe model_training\inference.py "午餐100 晚餐200" --raw
```

使用原模型：加 `--base-only`。使用完整合併模型：加 `--merged model_training/artifacts/expense-merged`。

## 學習順序

1. `inference.py`：載入模型、生成文字、原始結果與驗證結果。
2. `backend/app/services/llm/expense_rules.py`：提示詞、固定分類、金額證據。
3. `backend/app/services/llm/expenses.py`：JSON 欄位與原文品項驗證。
4. `build_dataset.py`：150 筆訓練、90 筆驗證、91 筆測試如何產生。
5. `train.py`：assistant labels 遮罩與 LoRA 訓練。
6. `evaluate.py`：JSON、分類、品項、金額與完整正確率。
7. `serve.py`：提供模型服務並轉成現有專題的 items 契約。

## 繼續訓練

```powershell
.\.venv\Scripts\python.exe model_training\train.py --local-only --steps 120
```

恢復版預設寫到 `artifacts/expense-lora-retrained`，不覆蓋原有 `expense-lora`。輸出資料夾已經有權重時會拒絕覆蓋，可另指定 `--output`。重新訓練後測試新權重：

```powershell
.\.venv\Scripts\python.exe model_training\inference.py "午餐100 晚餐200" --adapter model_training/artifacts/expense-lora-retrained
```

重新評測時另存新報告：

```powershell
.\.venv\Scripts\python.exe model_training\evaluate.py --output model_training/artifacts/new-evaluation.json
```

`export_model.py` 預設另存 `expense-merged-restored`；`revalidate_reports.py` 另存 `.revalidated.json`。原訓練報告和權重不會因恢復而改動。

## 模型服務

模型服務會優先載入本機 `artifacts/expense-merged/` 完整模型；沒有合併模型時才使用原始 Qwen 與 `artifacts/expense-lora/`。兩種方式都不會重新訓練。

```powershell
.\.venv\Scripts\python.exe -m uvicorn serve:app --app-dir model_training --host 127.0.0.1 --port 8081
```

在 `backend/.env` 設定以下項目，再重新啟動後端：

```dotenv
MODEL_BASE_URL=http://127.0.0.1:8081
MODEL_NAME=expense-qwen-0.5b-lora
MODEL_TIMEOUT_SECONDS=90
```

第一次解析會載入模型，CPU 模式可能需要較長時間。`GET http://127.0.0.1:8081/healthz` 回傳服務是否存活，以及 `modelLoaded` 是否已載入模型；`modelLoaded=false` 在第一次解析前屬於正常情況。

部署時可把完整模型放在其他磁碟或掛載目錄，使用 PowerShell 指定：

```powershell
$env:EXPENSE_MERGED_DIR = 'E:\models\expense-merged'
.\.venv\Scripts\python.exe -m uvicorn serve:app --app-dir model_training --host 127.0.0.1 --port 8081
```

請傳送整個模型資料夾，包括 config、tokenizer 與權重。指定的資料夾不存在或無法載入時，服務回傳 503，前端會顯示規則備援，解析結果仍需確認後才寫入。若採用原始模型＋LoRA，可用 `EXPENSE_ADAPTER_DIR` 指定 adapter，並確保沒有選到合併模型。

模型服務應由後端透過內部網路呼叫；範例只監聽本機。部署到不同主機時，將後端的 `MODEL_BASE_URL` 改為模型服務的內部位址。

沿用專題的模型 HTTP 介面。恢復版服務可將三欄結果轉成現有後端的 items，未回退或覆寫目前的 `parse.py`、`nlp.py`、登入或資料庫程式。

模型只訓練支出。出現日期時轉接結果會請使用者補上日期；缺少分類也留空，不造分類 ID。財務建議與收入需另用合適的模型。
