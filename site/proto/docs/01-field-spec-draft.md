# 欄位定義書 — 草稿（給囷洧接手）

這份不是定稿，是**起頭用的草稿**。定稿是囷洧的工作，因為版本寫法的判斷屬於領域規則，
不是程式問題。這份文件做的事是：先從 **300 則真實 NVD 公告**裡把實際存在的寫法統計出來，
讓你不必對著空白文件想像。

> 統計基礎：2026 年 7–8 月間公開的 300 則 CVE，取自 NVD CVE API 2.0 的實際回應。
> 其中 2 則是被撤回的記錄（Rejected），統計時已排除。

---

## 一、先講結論：不要重新發明結構

NVD 的 CPE 資料裡**已經有一套結構化的版本區間**，只用三個欄位：

| 欄位 | 意思 | 300 則中出現次數 |
|------|------|-----------------|
| `versionStartIncluding` | 下界，**含**這個版本 | 118 |
| `versionEndExcluding` | 上界，**不含**這個版本 | 138 |
| `versionEndIncluding` | 上界，**含**這個版本 | 105 |

還有第四個 `versionStartExcluding`（下界不含），但在 300 則裡**一次都沒出現**。

最常見的組合是 `versionStartIncluding + versionEndExcluding`（37 次），
也就是數學上的半開區間 `[start, end)`。

**建議：抽取欄位直接照抄這三個名字。** 理由有三個：

1. 不必自己想結構，也不必說服別人這個結構合理
2. 對已經被 NVD 分析過的公告，CPE 欄位就是**現成的正確答案**，可以拿來驗證抽取對不對
3. 之後如果要跟其他資安工具交換資料，用同一套欄位名不必再轉換

---

## 二、版本寫法有幾種（實際統計）

以下八類是從 300 則裡歸納出來的。百分比會加總超過 100%，因為一則公告可能同時命中多類。

### A. 單一上界，不含 — **87 則（29%）**

最常見。關鍵字：`before` / `prior to` / `earlier than`

```
The Bit Form WordPress plugin before 3.1.4 does not sanitise ...
                                    ^^^^^
```

→ `versionEndExcluding = "3.1.4"`，不設下界

---

### B. 單一上界，含 — **81 則（27%）**

關鍵字：`up to and including` / `through`

```
... in all versions up to, and including, 2.2.5 due to insufficient input sanitization
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^
```

→ `versionEndIncluding = "2.2.5"`，不設下界

**注意 A 與 B 的差別是「含不含那個版本」，差一個版本就是誤判。**
`before 3.1.4` 代表 3.1.4 已經修好了；`up to and including 3.1.4` 代表 3.1.4 還有問題。

---

### C. `X and earlier` — **3 則（1%）**

```
FreeRDP versions 3.28.0 and earlier contain a heap buffer overflow ...
                 ^^^^^^^^^^^^^^^^^
```

→ `versionEndIncluding = "3.28.0"`（跟 B 同一種結構，只是寫法不同）

---

### D. 明確區間 `from A to B` — **2 則（1%）**

```
This issue affects Apache Lucene.Net.Replicator: from 4.8.0-beta00005 through 4.8.0-beta00017.
                                                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
```

→ `versionStartIncluding = "4.8.0-beta00005"`, `versionEndIncluding = "4.8.0-beta00017"`

---

### E. 多分支列舉 — **4 則（1%）**

```
containerd ... In versions prior to 1.7.33, 2.3.2, 2.2.5, 2.1.9, and 2.0.10 the CRI plugin ...
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
```

→ **要拆成五組區間**，不是一組。每個維護分支各自有自己的上界：

```
{ versionStartIncluding: "1.7.0",  versionEndExcluding: "1.7.33" }
{ versionStartIncluding: "2.0.0",  versionEndExcluding: "2.0.10" }
{ versionStartIncluding: "2.1.0",  versionEndExcluding: "2.1.9"  }
...
```

**這一類最難標，也最容易出錯。** 建議第一輪標註時把它獨立標記出來，先不要求標得完美，
但一定要記下來有幾則，因為它會直接影響評測時的「完全正確率」怎麼算。

---

### F. 分支各自寫上界 — **1 則（0.3%）**

```
n8n before 1.123.61, 2.x before 2.27.4, and 2.28.x before 2.28.1 contains a SQL ...
```

→ 跟 E 同樣拆成多組，但這種寫法把分支名寫出來了，反而比 E 好判斷

---

### G. `all versions ...` — **56 則（19%）**

```
... is vulnerable to Directory Traversal in all versions up to, and including, 2.9.0
                                             ^^^^^^^^^^^^
```

→ 跟 B 同一種結構。`all versions` 這三個字的意思是**沒有下界**，不是「全部版本都有問題」。
這點要寫進標註準則，很容易被誤解。

---

### H. `fixed in X` — **1 則（0.3%）⚠ 陷阱**

```
Wazuh 5.0.0-beta1 (fixed in 5.0.0-beta3) does not validate or override the cluster_name ...
      ^^^^^^^^^^^        ^^^^^^^^^^^^^^
      受影響版本          修補版本 ← 不同欄位！
```

→ 這裡有**兩個**版本號，分屬不同欄位：
- `versionEndIncluding = "5.0.0-beta1"`（受影響）
- `fixed = "5.0.0-beta3"`（修補版本）

**這是最容易標錯的一類。** 標成受影響版本 = 5.0.0-beta3 的話，
系統會告訴使用者「你已經是安全版本」，實際上他還在受影響範圍內。

---

## 三、有 43% 的公告，這八類規則全部抓不到

八條規則合起來只涵蓋 **171 / 298（57%）**。剩下的 127 則長這樣：

| NVD 分析狀態 | 則數 | 意思 |
|---|---|---|
| `Received` | 70 | 剛收到，NVD 還沒分析，**通常也還沒有 CPE** |
| `Analyzed` | 41 | 已分析，但描述文字就是沒寫版本 |
| `Deferred` | 8 | NVD 決定不深入分析 |
| `Modified` | 5 | 曾修改過 |

典型例子：

```
[Analyzed] CVE-2026-2411
Zephyr's Bluetooth host declares a GATT characteristic as two consecutive attributes ...
（整段講技術細節，一個版本號都沒有）

[Received] CVE-2026-68455
In the Linux kernel, the following vulnerability has been resolved: liveupdate: validate ...
（Linux kernel 的公告幾乎從不寫版本區間）
```

### 這 43% 要怎麼處理

**一律標成「原文未提供」，不要猜。**

這條規則會直接寫進 prompt，也是抽取模型最重要的一項行為。
猜一個看起來合理的版本號造成的傷害比空著大得多 —— 使用者會升級到不存在的版本，
或以為自己不受影響。

**但有一半可以救**：這 127 則裡有 **35 則的 CPE 已經帶了結構化邊界**。
也就是說「人從描述文字看不出來，但 NVD 已經幫你標好了」。

→ 建議的處理順序：
1. 描述文字抽得到 → 用抽取結果
2. 抽不到但 CPE 有邊界 → 用 CPE 的值，並標記來源為 `cpe`
3. 兩邊都沒有 → 「原文未提供」

---

## 四、為什麼不能用正則表示式硬幹（這段是給整組看的）

我做了一個對照實驗：

| 規則寫法 | 涵蓋率 |
|---|---|
| 嚴格正則（`up to and including X`） | **32%** |
| 寬鬆正則（多容許幾個逗號：`up to, and including, X`） | **56%** |

**只是多容許幾個逗號，涵蓋率就從 32% 跳到 56%。**

真實的公告寫法是這樣的：

```
up to and including 2.2.5        ← 嚴格版抓得到
up to, and including, 2.2.5      ← 嚴格版抓不到，只差兩個逗號
in all versions up to, and including, 2.9.0
versions 3.28.0 and earlier
```

每多一種寫法就要多一條規則，而寫法是**開放的** —— 每個廠商、每個 CNA 的習慣都不一樣，
永遠有下一種你沒見過的寫法。這就是這一題必須用語言模型而不是規則的具體理由，
也是報告裡「LLM 是主軸」這句話的實際依據。

（順帶一提：這個 32% → 56% 的數字很適合放進期末報告，它是實測出來的，不是引用來的。）

---

## 五、建議的標註流程

### 第一批：20 則試標（第 1 週要做完）

目的**不是**標資料，是**驗證結構夠不夠用**。

1. 從上面八類各挑 2–3 則，湊滿 20 則
2. 囷洧與另一個人**分別獨立標**同樣這 20 則
3. 比對兩人結果，計算一致率
4. 不一致的地方 → 準則寫得不夠清楚 → 改準則，不是改答案
5. **一致率達到 85% 才算結構定稿**，之後才開始標 200 則

### 一致率怎麼算

以欄位為單位，不是以公告為單位：

```
一致率 = 兩人標的值完全相同的欄位數 ÷ 總欄位數
```

八個欄位 × 20 則 = 160 個欄位。兩人有 136 個以上相同就達標。

**「原文未提供」也算一個值** —— 一個人標了版本、另一個標「未提供」，就是不一致，
而且這種不一致最值得檢討，因為它代表準則對「什麼情況算抽不到」講得不夠清楚。

### 為什麼要兩人標

一個人自己標，永遠不會發現自己的準則有歧義。
兩人不一致的地方就是準則的漏洞所在，這比標得快重要得多。

---

## 六、還沒決定、需要囷洧拍板的事

1. **多分支列舉（E 類）第一輪要不要標？**
   它只佔 1%，但標起來最花時間。建議：標，但獨立記號，評測時分開算。

2. **beta / rc / -SNAPSHOT 這種版本號怎麼比大小？**
   `5.0.0-beta1` 和 `5.0.0` 誰比較新？這會影響比對引擎，要跟冠文一起決定。

3. **被撤回的公告（Rejected）怎麼辦？**
   300 則裡有 2 則。建議：同步時直接跳過，不進資料庫。

4. **同一則公告影響多個產品時怎麼標？**
   例如一則公告同時影響 Windows 與 Linux 版本，區間可能不同。

5. **八個欄位的最終名單**
   目前原型用的是：產品、弱點類型、受影響版本、修補版本、攻擊途徑、所需權限、
   使用者互動、緩解措施。要不要增減由你決定，但**第 1 週結束前必須定案**，
   因為明樺要照這個做訓練資料、冠文要照這個寫綱要約束。

---

## 附：資料怎麼重新產生

本文的統計來自 NVD CVE API 2.0 的實際回應。要重跑：

```bash
curl "https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=100&pubStartDate=2026-08-01T00:00:00.000&pubEndDate=2026-08-15T00:00:00.000"
```

注意無金鑰限流是每 30 秒 5 次，連續抓取要自行間隔。

> This product uses data from the NVD API but is not endorsed or certified by the NVD.
