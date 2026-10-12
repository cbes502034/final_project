---
base_model: C:\Users\wdv56\.cache\huggingface\hub\models--Qwen--Qwen2.5-0.5B-Instruct\snapshots\7ae557604adf67be50417f59c2c2f167def9a775
library_name: peft
license: apache-2.0
language:
- zh
pipeline_tag: text-generation
tags:
- lora
- expense-extraction
---
# 專題支出模型第一版

以 Qwen2.5-0.5B-Instruct 為基底，使用 150 筆合成訓練資料進行 CPU LoRA 微調。
基底 revision：7ae557604adf67be50417f59c2c2f167def9a775。
訓練 120 步，q_proj / v_proj，rank 8，學習率 0.0003，種子 42。
實際訓練 540,672 個參數，96 個參數張量有變動。adapter 必須搭配原模型載入。

輸出：`{"expenses":[{"category":"食","item":"早餐","amount":50}]}`。
分類只能是食、衣、住、行、育、樂、其他。購買周邊轉成其他／娛樂。

同一組 91 筆合成測試：原模型原始完整正確率 33.0%，微調後 87.9%。
同一版程式驗證後：原模型 60.4%，微調後 98.9%。JSON 語法有效率兩者皆為 100%。
程式驗證曾針對測試發現的問題修正，因此其成績不是盲測模型成績。
未做真實使用者測試；保留人工確認。只支援支出，不適用財務建議或收入解析。

原始模型：[官方模型卡](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct)。
基底採 Apache-2.0 授權。本地模型與資料沒有自動上傳或發布。
### Framework versions

- PEFT 0.13.2