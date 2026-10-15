# LLM 實作規劃

> **前提**：系統已經串接好——70 支路由能動、關掉 mock 畫面照常。這份只處理**模型線**。
>
> **依據**：[`frontend/docs/model.html`](../frontend/docs/model.html)（記帳模型設計）是「為什麼這樣選」；
> 這份是「接下來每一步做什麼、誰做、做完怎麼算過關」。兩份對不上的地方，第 2 節列出來一起改。

---

## 0. 兩個 AI 功能，一張表看完

| | 段落記帳解析 | 財務建議 |
|---|---|---|
| 路由 | `POST /api/nlp/parse-batch`（`parse` 單句版共用） | `POST /api/advices/generate` |
| 負責 | 成員2 | 成員3 |
| 任務性質 | **抽取**：一段話 → 結構化的好幾筆 | **生成**：算好的數字 → 一段人話 |
| 有沒有標準答案 | 有（日期、金額、收支、分類） | 沒有 |
| 要不要微調 | **要**，這是專題的主要成果 | **不要**，沒有訓練資料、也沒有標準答案可以評 |
| 模型 | Qwen2.5-1.5B-Instruct **＋ 我們的 LoRA** | 同一顆 Qwen2.5-1.5B-Instruct，**不掛 LoRA** |
| 模型產生什麼 | 一次 `record_transactions` 工具呼叫 | `title`、`body`、`suggest` 三個欄位 |
| Python 負責什麼 | 日期換算、分類對照、金額核對、可信度 | 所有數字、燈號、依據（basis） |
| 怎麼評 | 留出集 200 段，五個指標 | 規則檢查三項 ＋ 四人盲評 |
| 叫不動時 | 503 → 前端規則解析頂著（寫入仍走後端） | 503 → 前端用同一批數字寫幾則（不存） |

**整份規劃的骨架只有一句話：模型只做語意判斷，凡是能用程式確定的東西都不交給模型。**

---

## 1. 先定案的五個決定

### D1　段落解析用「單輪工具呼叫」，不做兩輪

`model.html` 第 05 節原本設計成兩輪：第一輪模型呼叫 `resolve_date`、`lookup_category` 問事實，
後端執行完再丟回去，第二輪模型才交 `record_transactions`。

改成單輪的理由：

| | 兩輪 | 單輪（本規劃） |
|---|---|---|
| 模型要做的語意判斷 | 抽出「昨天」、判斷「全家是店名」、切分 | **一模一樣** |
| 日期由誰換算 | `resolve_date`（Python） | `resolve_date`（Python） |
| 分類由誰對照 | `lookup_category`（Python） | `lookup_category`（Python） |
| 推論次數 | **2 次** | 1 次 |
| CPU 上的等待 | 加倍 | 一半 |
| 1.5B 要學的格式 | 多輪對話 ＋ 工具結果回填 | 一次工具呼叫 |

兩輪設計裡，模型第一輪做的事其實是「把『昨天』這幾個字抽出來交給工具」——
這跟單輪裡「把 `date_expr: "昨天"` 寫在工具參數裡、由後端換算」是**同一件事**，資訊量完全相同。
差別只在要不要多付一次推論的時間，讓模型「問」一個它其實不需要問的問題。
分類清單只有十幾個，直接放進 prompt 比繞一圈工具便宜。

**這仍然是 function calling**：模型用 Qwen 原生的工具呼叫格式交出 `record_transactions`，
參數受 JSON schema 約束，後端的 `resolve_date`、`lookup_category` 是真的在跑的工具。
「為什麼需要工具」的答案沒有變——日期、分類交給模型會錯。

### D2　日期與分類永遠由 Python 決定

現在的 `parse.py` 讓模型自己把「昨天」換成 `2026-09-16`，回分類 **id**。兩件都要改：

- 模型回 `date_expr`（`"昨天"`、`"9/17"`、`"上禮拜三"`、`null`），由 `resolve_date(expr, today)` 換算
  ——`model.html` 寫得很清楚：「模型算日期會錯，而且錯得很難發現」
- 模型回分類**名稱**（`"餐飲"`），由 `lookup_category(name, catalog, kind)` 對回 id
  ——id 是資料庫流水號，沒有語意；系統分類是 1～12，家庭自訂的分類每一家都不一樣。
  讓 1.5B 背數字，不如讓它挑名字。

### D3　一顆基底模型 ＋ 一個 LoRA，兩個功能共用一台服務

免費 Hugging Face Space 是 2 vCPU、16 GB RAM、沒有 GPU，而且 **llama-server 一個行程只能載入一顆模型**。
所以不開兩顆，改成：

```
llama-server
  ├── 基底：Qwen2.5-1.5B-Instruct q4_k_m（約 1 GB）
  └── LoRA：我們訓練的記帳 adapter（幾十 MB）
        解析的請求  → LoRA 開（scale = 1）
        建議的請求  → LoRA 關（scale = 0）＝ 原本的通用模型
```

llama-server 支援用 `--lora` 載入 adapter、並在**每一個請求**指定這次掛不掛。
好處是建議不會被「只會吐 JSON」的微調影響，又不用多開一台服務、多管一組網址。

> ⚠️ **這一條要在 P0 實測**（第 10 節）。如果你們用的 llama.cpp 版本不支援逐請求切換，
> 退路是把 LoRA 合併進基底只給解析用，建議改用同一顆合併後的模型 ＋ 明確的「不要回 JSON」prompt，
> 並把「建議的格式合格率」列進評測盯著。

### D4　格式保證用 llama-server 內建的兩層

商業 API 的 structured output 我們沒有，要自己補：

1. **原生工具呼叫**：`llama-server --jinja` 會讀 Qwen2.5 的 chat template，
   請求帶 OpenAI 格式的 `tools` 與 `tool_choice: "required"`，回應直接是解析好的 `tool_calls`
2. **文法約束**：工具參數依 JSON schema 轉成文法，生成時就不可能寫出壞掉的 JSON；
   建議走 `response_format` 帶 schema，效果一樣

`model.html` 寫的 XGrammar／outlines 是另外裝一套；llama-server 內建就有，不用多一個套件。
微調讓它「想對」，約束讓它「寫對」——兩層都要，這一點沒變。

### D5　財務建議不微調，數字一個都不讓模型碰

`generate_advices` 的規格已經寫好「數字由 analytics 算、模型只做敘述」。再往前推一步：

- `level`（ok／info／warn）**由 Python 依燈號決定**，不讓模型判斷
- `basis`（依據）**由 Python 從數字直接寫成句子**，例如「餐飲 4,820 元，占支出 38%」
- 模型只寫 `title`、`body`、`suggest`
- 寫回來之後做**數字忠實度檢查**：`title`、`body`、`suggest` 裡出現的每一個數字，
  都必須在這次餵進去的數字裡找得到，找不到的那一則整則丟掉

這樣模型就算幻覺，也只能幻覺在措辭上，不可能編出一個錯的金額讓使用者做錯決定。

---

## 2. 現有設計與程式碼對不上的地方（要一起改）

| # | 位置 | 現況 | 改成 |
|---|---|---|---|
| 1 | `model.html` 第 05 節 | 兩輪工具呼叫 | 單輪（D1） |
| 2 | `model.html` 第 06 節 | 「四人各寫 100 段種子」**又寫**「留出集交給成員4，因為他不寫種子」——互相矛盾 | **成員1～3 寫種子**（每人約 130 段），**成員4 標留出集**（第 5 節） |
| 3 | `model.html` 第 04 節 | 建議用 `get_month_summary`、`get_savings_status` 兩個工具 | 建議的規格已經改成直接把算好的數字放進 prompt，比讓模型呼叫工具少一次推論、也少一個出錯點。文件跟上規格 |
| 4 | `services/llm/parse.py` | 模型自己換算日期、回分類 id、自己報 confidence | 回 `date_expr` 與分類名稱；可信度由 Python 算（第 3-4 節） |
| 5 | `services/llm/client.py` | 只會送純文字 prompt | 要能帶 `tools`、`tool_choice`、`response_format`、逐請求 LoRA（第 9 節） |
| 6 | `toolkit/config.py` | 有 `advice_model_name` 但沒有任何程式讀它 | 改成「建議要不要掛 LoRA」的設定（第 9 節） |
| 7 | `toolkit/` | 沒有日期換算工具 | 新增 `dates.resolve(expr, today)` ＋ 測試 |

> 2、3 是文件問題，4～7 是程式問題。程式那幾個都在 `@stub` 已經拿掉的檔案裡，
> **要誰改、怎麼改由那個人決定**（第 9 節列了建議的負責人）。

---

## 3. 段落記帳解析：完整流程

### 3-1　一次請求走過的路

```
使用者：「早上買早餐55，中午在全家買咖啡，昨天加油1200」
   │
   ▼  routers/ledger/nlp.py  parse_batch
   │   1. 查分類清單（系統 ＋ 這一家自訂）、算台灣的今天
   │
   ▼  services/llm/parse.py  parse_batch
   │   2. 組訊息：system（規則）＋ tools（record_transactions）＋ 分類清單 ＋ 使用者那段話
   │   3. client.complete(..., tools=…, tool_choice="required", lora=on)
   │
   ▼  Hugging Face Space：llama-server（基底 ＋ LoRA）
   │   4. 回一次 record_transactions(items=[…])，參數受 schema 約束
   │
   ▼  services/llm/parse.py（後處理，全部是 Python）
   │   5. resolve_date(date_expr, today)        → "2026-09-16"
   │   6. lookup_category(name, catalog, kind)   → "1"
   │   7. 金額核對、收支核對、可信度、missing、hint
   │
   ▼  回傳形狀完全不變（docs/02 的 POST /api/nlp/parse-batch）
      前端、路由、測試一行都不用改
```

最後一行很重要：**改的是 parse.py 裡面，對外的形狀不動**，前端與另外三個人完全不受影響。

### 3-2　工具定義（模型唯一要交的東西）

```json
{
  "type": "function",
  "function": {
    "name": "record_transactions",
    "description": "把使用者的一段話切成一筆一筆的收支交出來。抽不到的欄位填 null，不要猜。",
    "parameters": {
      "type": "object",
      "required": ["items"],
      "properties": {
        "items": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["span", "date_expr", "amount", "kind", "category", "merchant", "note"],
            "properties": {
              "span":      { "type": "string",           "description": "原句裡對應這一筆的那一段，一字不改" },
              "date_expr": { "type": ["string", "null"], "description": "原句裡的時間詞，例如 昨天、9/17、上禮拜三；沒講就 null" },
              "amount":    { "type": ["number", "null"], "description": "正數；中文數字要換成阿拉伯數字；沒講就 null" },
              "kind":      { "enum": ["expense", "income", null] },
              "category":  { "type": ["string", "null"], "description": "只能從分類清單裡挑一個名稱，挑不出來就 null" },
              "merchant":  { "type": ["string", "null"], "description": "店家，例如 全家、全聯；沒有就 null" },
              "note":      { "type": ["string", "null"], "description": "買了什麼，例如 早餐、加油" }
            }
          }
        }
      }
    }
  }
}
```

每一個欄位都 `required` 但允許 `null`——這是刻意的：**強迫模型對每一欄表態，「沒講」要明確寫 null**，
而不是乾脆省略。訓練資料裡「該 null 的地方是 null」就是在教這件事。

### 3-3　Prompt 的排法：不變的放前面

CPU 上最貴的是讀 prompt。llama-server 會快取「跟上一次開頭一樣」的部分，所以：

```
[system]   規則（固定）
[tools]    record_transactions 的定義（固定）
[system]   分類清單（同一家不變）
[user]     使用者那段話（每次不同）← 一定放最後
```

今天日期**不放進 prompt**——模型不需要知道今天幾號，因為它不換算日期（D2）。
這也讓開頭那一大段每一天都一樣，快取命中率更高。

### 3-4　後處理：五個 Python 工具

| 工具 | 放哪裡 | 做什麼 | 失敗時 |
|---|---|---|---|
| `dates.resolve(expr, today)` | `toolkit/dates.py`（新） | 今天／昨天／前天／大前天、上禮拜三、這週五、9/17、9月17日、17號（大於今天就算上個月） | 認不得 → `None`、放進 `missing` |
| `lookup_category(name, catalog, kind)` | `parse.py` | 名稱完全相符 → id；不在清單、或收支對不上 → `None` | 放進 `missing` |
| `check_amount(amount, span)` | `parse.py` | `span` 裡有阿拉伯數字時，`amount` 必須等於其中一個 | 不符 → 金額可信度降低（標黃，不清掉） |
| `money.to_decimal(...)` | 已存在 | 轉 Decimal、不准負數 | → `None`、`missing` |
| `confidence(item)` | `parse.py` | 依上面四項核對結果給每一欄 0～1 | — |

`date_expr` 是 `null` 時用今天、可信度 0.9（多數人記帳講的就是今天的事）。

**可信度不讓模型自己報。** 1.5B 對每一欄都會寫 0.95，那個數字沒有資訊。
改成由能驗證的事實決定：金額在原句裡找得到 → 高；分類名稱完全相符 → 高；日期詞認得出來 → 高。
前端「低於 0.85 標黃」的規則不用改，標黃的意義反而變得更準。

### 3-5　這一塊的驗收

- `pytest tests/routes -k "parse_batch and u4f60"` 全過（形狀不變，舊測試照樣要過）
- 新增 `toolkit/dates.py` 的單元測試：每一種時間詞至少兩個例子，含跨月（今天 10/2，「28號」→ 9/28）
- 新增後處理的單元測試：餵一個假的 `tool_calls`，不用真的模型就能測

---

## 4. 財務建議：完整流程

```
routers/analytics/advices.py  generate_advices
   1. analytics.summary() ＋ savings_status()     ← 所有數字（已在規格裡）
   2. level 由燈號決定、basis 由數字寫成句子      ← 新增，Python
   3. 理財習慣 to_prompt_block()（標成資料，不是指令）
   │
services/llm/advice.py  write_advices
   4. system：格式 ＋ catalog.ADVICE_RULES（不給投資、保險、稅務建議）
      user：  算好的數字（JSON）＋ 依據句子 ＋ 理財背景
   5. client.complete(..., response_format=schema, lora=off)
   │
   6. 驗證（Python）
        AdviceItem 格式
        數字忠實度：文字裡每一個數字都要在第 1 步的數字裡找得到
        邊界詞：出現「股票、基金、保險、報稅…」→ 丟掉
   7. 存進 advices，basis_json 存 {lines, numbers}，事後可以驗算
```

### 4-1　模型只寫的三個欄位

```json
{ "title": "餐飲花得比上個月多", "body": "…", "suggest": ["…", "…"] }
```

一次產生 2～3 則，每則對應 Python 先挑好的一個主題（超支的分類、存款進度、預算快用完的）。
**主題由 Python 挑，模型只負責把那個主題講成人話**——這樣三則不會講成同一件事，也不會漏掉真的要提醒的。

### 4-2　數字忠實度怎麼檢查

```python
import re

def grounded(text, numbers):
    """文字裡的每一個數字都要在 numbers 裡出現過。"""
    allowed = {normalize(n) for n in numbers}           # 4820、38、38%、4,820 視為同一個
    for raw in re.findall(r"\d[\d,]*(?:\.\d+)?%?", text):
        if normalize(raw) not in allowed:
            return False
    return True
```

這一條是建議這邊**最重要的一道防線**，也是報告裡最能說明「我們知道 LLM 會幻覺、也知道怎麼擋」的地方。

### 4-3　品質不夠時的升級路徑

1.5B 寫中文段落會偏生硬，但因為主題、數字、依據都由 Python 決定，它要做的事很窄。
如果四人盲評真的太差，依序試：

1. 加 few-shot：每個主題放一則寫得好的範例（成本最低）
2. 改用 Qwen2.5-3B-Instruct 只給建議用
   ⚠️ 3B 是 Qwen Research 授權（限非商用），校內專題可以，要在報告裡寫明
3. 7B 在 CPU 上太慢（一則可能要一分鐘以上），不建議

---

## 5. 資料

### 5-1　標註格式（一行一段話，JSONL）

```json
{"id": "s-m1-0042",
 "text": "早上買早餐55，中午在全家買咖啡，昨天加油1200",
 "items": [
   {"span": "早上買早餐55", "date_expr": null, "amount": 55, "kind": "expense",
    "category": "餐飲", "merchant": null, "note": "早餐"},
   {"span": "中午在全家買咖啡", "date_expr": null, "amount": null, "kind": "expense",
    "category": "餐飲", "merchant": "全家", "note": "咖啡"},
   {"span": "昨天加油1200", "date_expr": "昨天", "amount": 1200, "kind": "expense",
    "category": "交通", "merchant": null, "note": "加油"}
 ]}
```

標註的就是**模型要交的工具參數**，所以訓練時直接包成 tool call，不用再轉一次格式。

### 5-2　三份資料，三個不同的人

| 資料 | 量 | 誰 | 用途 | 規則 |
|---|---|---|---|---|
| 種子 | 約 400 段 | **成員1～3**，每人約 130 段 | 訓練 | 寫自己真實的講法；三個人的語言習慣不同，正是要的多樣性 |
| 擴增 | 3,000～5,000 段 | 程式（`ml/augment.py`） | 訓練 | 台灣店家 × 金額寫法 × 時間詞 × 句型組合；難例過取樣 |
| 留出集 | 200 段 | **成員4**，100% 人工 | **只拿來評測** | 永遠不進訓練、不給商業模型碰、不給寫種子的人看 |

> 第 2 節的矛盾在這裡解掉：**標訓練集的人不標測試集**，同一個人標會用同一套判斷，評測會偏樂觀。

### 5-3　難例清單（擴增時刻意多做）

| 類型 | 例子 | 該怎麼標 | 占擴增 |
|---|---|---|---|
| 店名與家人歧義 | 「在全家買咖啡」「跟全家去吃飯」 | 前者 merchant=全家；後者沒有店家 | 15% |
| 金額沒講 | 「晚上加油」 | `amount: null` ← **最重要** | 15% |
| 收支方向 | 「爸給我零用錢500」「退貨退了300」 | income | 10% |
| 一段多筆 | 三到五筆串在一起、用「然後」「還有」接 | 切對數量 | 20% |
| 中文數字 | 「三百五」「兩千一」「一千二百」 | 換成 350、2100、1200 | 10% |
| 時間詞 | 前天、上禮拜三、9/17、17號 | 照原文放進 `date_expr` | 15% |
| 合計語意 | 「三個人一起吃了900」 | 一筆 900，不要拆成三筆 | 5% |
| 不是記帳 | 「今天好累」「明天要記得繳費」 | `items: []` | 5% |
| 一般句子 | 其餘 | — | 5% |

### 5-4　標註規則（寫在 `ml/GUIDELINE.md`，三個人照同一份標）

- 金額**沒講就是 null**，就算「常識上」咖啡大概 60 元也一樣
- `span` 一字不改從原句複製；各筆的 `span` 不重疊
- `date_expr` 照原文抄，不要自己換算（「昨天」就寫昨天）
- 分類只能用系統的 12 個名稱（餐飲、交通、居住、日用品、娛樂、教育、醫療、其他、薪資、獎金、零用金、其他收入）
- 拿不準的寫進 `ml/data/questions.md`，週會一起定，定完回頭全部改成一致

### 5-5　商業 LLM 可以當標註助手，但有兩條線（沿用 `model.html`）

1. **留出集絕對不能碰**——否則量到的是「多像那個老師」，不是「多正確」
2. 候選標註要**人逐筆看過**——老師的錯剛好集中在最難的那幾類

報告裡明寫標註流程用了什麼輔助。

### 5-6　資料飛輪：使用者的修正變成第二輪的訓練資料

`POST /api/nlp/confirm-batch` 已經把每一筆的原句、模型原始輸出、使用者改過的欄位存進 `nlp_parses`。
缺的是**匯出工具**：

```bash
python -m app.cli export-nlp --since 2026-10-15 --out ml/data/corrections.jsonl
```

只匯出 `user_corrected` 有值的（模型錯了、人改過的），轉成 5-1 的格式。
⚠️ `model_ver = "rules"` 的要濾掉——那是前端規則解析的結果，不是模型的錯。

---

## 6. 訓練

設定沿用 `model.html` 第 06 節（Unsloth ＋ TRL、QLoRA 4-bit、r=16、fp16、只算 assistant 的 loss…），
這裡只補**落地時一定會踩的三件事**：

### 6-1　訓練與上線的 prompt 必須逐字相同

訓練資料用 `tokenizer.apply_chat_template(messages, tools=[record_transactions])` 組，
system、工具定義、分類清單的寫法要跟 `parse.py` 上線時**一模一樣**。
差一個換行，模型學到的格式就跟上線看到的不一樣——這是小模型微調最常見、也最難查的失敗原因。

做法：把組訊息的函式寫在 `services/llm/parse.py`，**訓練 notebook 直接 import 同一支**，不要複製貼上。

### 6-2　輸出兩個檔，不要合併

```
merged 版（給 7B 對照、給 Colab 展示用）
adapter 版 → convert_lora_to_gguf.py → fambudget-lora-r1.gguf（給 Space 用，D3）
```

兩個都推到 Hugging Face Hub 的私有 model repo，Space 啟動時下載。檔名帶輪次（`-r1`、`-r2`），
`MODEL_NAME` 也跟著改，`nlp_parses.model_ver` 才分得出是哪一輪的成績。

### 6-3　兩輪的定義

| | 第一輪（R1） | 第二輪（R2） |
|---|---|---|
| 資料 | 種子 ＋ 擴增 | R1 的資料 ＋ 四人用 R1 幾天後匯出的真實修正（過取樣 ×3） |
| 目的 | 證明管線通、找出哪類錯最多 | **主要成果** |
| 看什麼 | 錯誤案例分類 → 回頭補那一類的擴增 | 對照表 |

---

## 7. 評測

### 7-1　指標（沿用 `model.html` 第 08 節，加一項延遲）

| 指標 | 怎麼算 | 目標 |
|---|---|---|
| 工具呼叫格式合法率 | 解析得出 `record_transactions` 且通過 schema 的比例 | > 0.98 |
| 段落切分正確率 | 預測筆數 = 標準答案筆數，且每一筆都配對得上（下面說明） | > 0.85 |
| **一次輸入完全正確率**（主指標） | 整段話每一筆的日期、金額、收支、分類**全對** | > 0.70 |
| 分類 Macro-F1 | 配對上的那些筆，分類的 macro F1 | > 0.80 |
| 該留空卻硬猜的比率 | 標準答案 `amount` 是 null，模型卻填了數字的比例 | < 0.05 |
| 延遲 p50／p95 | Space 上實測，含網路 | p95 < 模型逾時（30 秒） |

**配對方法**：預測的每一筆跟標準答案的每一筆算 `span` 的字元重疊率（IoU），
大於 0.5 且最大的配成一對，每一筆只能配一次。配不上的算切分錯。
日期比的是 `resolve_date` **換算後**的日期，不是 `date_expr` 字串——上線看的是結果。

### 7-2　對照表的欄位

| 規則解析 | 1.5B 零樣本 | 1.5B few-shot | 1.5B R1 | **1.5B R2** | 7B 零樣本 |
|---|---|---|---|---|---|

- **規則解析**是前端 `api.js` 的 `parseLine()`——不用任何模型的基準線。它能回答評分裡「LLM 核心性」那一項：
  沒有模型能做到幾分、有模型多了多少
- **7B 零樣本**在 Colab T4 上跑同一個 llama-server，換一顆模型而已，**同一支評測腳本**
- 每一欄都要實際跑出來。基線用猜的，整張表就沒有意義

最想看到的一格沒變：**1.5B R2 那一欄全面高於 7B 零樣本**。

### 7-3　評測腳本走上線的同一條路

```bash
cd backend
python -m tools.eval_nlp --set ../ml/data/heldout.jsonl --model-url $URL --label "1.5B-R1" \
       --out ../ml/results/r1.json
```

腳本直接呼叫 `services/llm/parse.parse_batch()`——**跟使用者走的是同一支函式**，
後處理、日期換算、分類對照全部算在內。另外寫一份腳本自己組 prompt 的話，量到的就不是上線的東西。

輸出：上面那張表的一欄 ＋ 每一筆錯誤案例（原句、預測、答案、錯在哪一欄），報告的「失敗案例分析」直接從這裡挑。

`services/evaluation.py` 已經有 `exact_match_rate`、`macro_f1`，補上 `split_accuracy`、`null_hallucination_rate`、`match_items`。

### 7-4　財務建議怎麼評（沒有標準答案）

| 指標 | 怎麼算 | 目標 |
|---|---|---|
| 格式合格率 | 通過 `AdviceItem` 的比例 | > 0.95 |
| 數字忠實率 | 通過 4-2 `grounded()` 的比例 | **= 1.0**（不合格的已經被丟掉，這裡量的是丟掉前） |
| 邊界違規率 | 出現投資、保險、稅務字眼的比例 | 0 |
| 有用程度（盲評） | 30 組數字 × 2 個版本，四人看不到是哪一版，1～5 分 | 比較版本用，不設門檻 |

盲評是拿來決定「few-shot 值不值得加」「要不要換 3B」，不是拿來證明什麼——報告裡就照這樣寫。

---

## 8. 部署

### 8-1　Hugging Face Space（常駐）

```
ml/space/
  Dockerfile        以 llama.cpp 官方 server 映像為底
  start.sh          從 Hub 下載基底與 LoRA 的 GGUF，啟動 llama-server
  README.md         Space 的設定頁（sdk: docker、app_port: 7860）
```

`start.sh` 的核心只有一行：

```bash
llama-server -m base-q4_k_m.gguf --lora fambudget-lora-r2.gguf --lora-init-without-apply \
             --jinja -c 4096 -t 2 --host 0.0.0.0 --port 7860
```

| 旗標 | 為什麼 |
|---|---|
| `--lora … --lora-init-without-apply` | 載入 adapter 但預設不套用，每個請求自己決定（D3） |
| `--jinja` | 讀 Qwen 的 chat template，才有原生工具呼叫（D4） |
| `-t 2` | 免費 Space 只有 2 vCPU |

後端（Render）的環境變數：

| 變數 | 值 |
|---|---|
| `MODEL_BASE_URL` | Space 的網址 |
| `MODEL_API_KEY` | Space 設成私有時填 HF token（**不可以 commit**） |
| `MODEL_NAME` | `qwen2.5-1.5b-fambudget-r2`（會寫進 `model_ver`） |

### 8-2　三層退路（沿用 `model.html` 第 07 節）

| 層 | 什麼時候用 |
|---|---|
| Space（CPU） | 平常 |
| Colab T4 ＋ cloudflared，同一個 llama-server | 展示當天，求快 |
| 前端規則解析 | 模型全掛，畫面照常能記帳 |

⚠️ 免費 Space **48 小時沒人用會休眠**，醒來要等。展示前一小時先打一次喚醒。

### 8-3　延遲要在 P0 先量

CPU 上的 1.5B 一段話要幾秒，**目前沒有實測數字**，不要先寫進文件。
P0 量出 p50／p95 之後再決定：要不要縮短工具定義的說明文字、`max_tokens` 開多少、逾時設多久。

---

## 9. 程式要改的地方

| 檔案 | 改什麼 | 建議負責 |
|---|---|---|
| `services/llm/client.py` | `complete()` 多收 `tools`、`tool_choice`、`response_format`、`lora`；有 `tool_calls` 時回傳它 | 成員1（共用元件） |
| `toolkit/config.py` | `advice_model_name` 換成 `advice_use_lora: bool = False`（D3） | 成員1 |
| `toolkit/dates.py`（新） | `resolve(expr, today)` ＋ 單元測試 | 成員2 |
| `services/llm/parse.py` | 單輪工具呼叫、後處理五個工具、組訊息函式給訓練共用 | 成員2 |
| `services/llm/advice.py` | 只寫三欄、`grounded()`、邊界詞檢查 | 成員3 |
| `routers/analytics/advices.py` | level 與 basis 改由 Python 決定（D5） | 成員3 |
| `services/evaluation.py` | 補配對、切分、硬猜率 | 成員4 |
| `tools/eval_nlp.py`（新） | 評測腳本（7-3） | 成員4 |
| `app/cli.py` | `export-nlp` 指令（5-6） | 成員2 |
| `ml/`（新資料夾） | `GUIDELINE.md`、`data/`、`augment.py`、`train_qlora.ipynb`、`space/` | 四人 |
| `frontend/docs/model.html` | 第 2 節的 1～3 | 寫這份規劃的人 |

> `parse.py`、`advice.py` 對外的回傳形狀**都不變**，所以前端、路由說明字串、`tests/routes` 都不用動。

---

## 10. 排程：六個階段，每段有過關條件

不用週次寫死，因為每一組剩下的時間不一樣。**每一段沒過關就不進下一段**，下一段的退路寫在旁邊。

| 階段 | 做什麼 | 過關條件 | 沒過關的退路 | 預估 |
|---|---|---|---|---|
| **P0 驗證前提** | Space 起基底模型；實測 `--jinja` 工具呼叫、逐請求 LoRA、延遲 | 三件都確認、p95 有數字 | 工具呼叫不行 → 改 `response_format` 約束 JSON；LoRA 切換不行 → D3 的退路 | 1～2 天 |
| **P1 資料與基線** | 標註種子、擴增腳本、留出集、評測腳本；跑規則／零樣本／few-shot／7B 四欄 | 留出集 200 段、對照表四欄有實測數字 | 標註落後 → 先用 150 段種子 ＋ 擴增開訓 | 4～6 天（與 P2 並行） |
| **P2 管線改寫** | `client.py`、`dates.py`、`parse.py` 單輪工具呼叫；`advice.py` | 舊的路由測試全過、新單元測試全過、few-shot 版接上 Space 能用 | — | 3～4 天 |
| **P3 第一輪微調** | Colab 跑 R1、轉 GGUF、上 Space、評測 | R1 那一欄有數字、錯誤案例分好類 | **R1 沒比 few-shot 好** → 停在 few-shot 版，把負面結果寫進報告 | 2～3 天 |
| **P4 第二輪微調** | 四人用 R1 記帳 3～4 天 → `export-nlp` → 補弱項擴增 → R2 | R2 那一欄有數字 | 時間不夠 → 用 R1 收尾 | 4～5 天 |
| **P5 凍結與報告** | 最後評測、建議盲評、對照表與失敗案例 | 報告的表格全部有實測數字 | — | 2～3 天 |

**三條硬線**（跟 `docs/01` 的精神一樣）：

1. **P0 沒過不寫任何訓練程式**——前提錯了，後面全部白做
2. **P3 結束沒有 R1 的數字，就放棄 R2**——穩定的 few-shot ＋ 完整評測，勝過訓練到一半的系統
3. **展示前兩天不換模型**——只留給「接回去、確認沒壞」

---

## 11. 風險與退路

| 風險 | 徵兆 | 退路 |
|---|---|---|
| Space 上太慢 | P0 量到 p95 接近 30 秒 | 縮工具說明文字、prompt 快取、降 `max_tokens`；展示改 Colab GPU |
| 逐請求 LoRA 不支援 | P0 切了 scale 輸出沒變 | 合併權重只給解析用，建議用同一顆 ＋ 明確 prompt，盯格式合格率 |
| 1.5B 學不會留空 | 硬猜率 > 0.1 | 擴增「金額沒講」再加一倍；後處理 `check_amount` 把對不上原句的金額標黃 |
| 標註標得不一致 | 錯誤案例裡同一種句子答案不同 | 停下來對 `GUIDELINE.md`，全部改一致再訓練 |
| 微調沒變好 | R1 ≈ few-shot | 負面結果照實寫——「試過、量過、為什麼沒用」本身就是成果 |
| Colab 斷線 | 晚上常見 | 每 50 步存 Drive；Kaggle 備援（每週 30 小時） |
| 建議幻覺數字 | 數字忠實率 < 1 | `grounded()` 丟掉那一則；全部丟光 → 503，前端頂著 |

---

## 12. 報告最後要交出的東西

1. **對照表**（7-2）：六欄 × 六個指標，全部實測
2. **失敗案例分析**：R2 還錯的那些，按類型分（店名歧義、留空、收支、切分）各舉例
3. **資料流程**：種子 → 擴增 → 留出 → 飛輪，以及**用了哪些商業模型輔助、在哪裡**
4. **兩個設計決定的理由**：為什麼單輪（D1）、為什麼建議不微調（D5）
5. **延遲與部署**：Space 上的 p50／p95、三層退路
6. **做不到的事**：一個月內資料飛輪只轉了一圈、使用者只有我們四個——講清楚，不要把設計講成已驗證的成果
