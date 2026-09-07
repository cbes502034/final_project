# 這個主題有哪些網站可以參考

查證日期 2026-09-07。下面標「**已實測**」的，是我實際打過 API 或讀過回應的；
標「搜尋所見」的，只確認過網頁存在與內容摘要，還沒深入讀。

---

## 一、會直接改變你們設計的兩個（先看這兩個）

這兩個都是**免費、免申請金鑰**，而且會讓優先序公式從「憑感覺加權」變成「有業界依據」。

### 1. EPSS — 這個漏洞未來 30 天被實際利用的機率

- 網站：<https://www.first.org/epss/>
- API：`https://api.first.org/data/v1/epss?cve=CVE-2026-10931`
- 由 FIRST（事故應變組織的國際協會）維護，用機器學習預測**未來 30 天被實際利用的機率**

**已實測**，回傳長這樣：

```json
{ "cve": "CVE-2026-10931", "epss": "0.00325", "percentile": "0.25202" }
```

`epss` 是機率（0.33%），`percentile` 是在所有 CVE 裡的百分位（前 25%）。

**為什麼這對你們很重要**：CVSS 衡量的是「萬一被利用會多嚴重」，
EPSS 衡量的是「到底會不會被利用」。這是兩件不同的事，而業界近年的共識是
**只看 CVSS 排序會排錯**。

我把 EPSS 套進你們現在的公式試算過（再乘上 `0.5 + EPSS百分位`）：

| 原排名 | CVE | 資產 | EPSS 百分位 | 新排名 |
|---|---|---|---|---|
| #1 | CVE-2026-10931 | Chrome × 34 | 25% | #1 　— |
| #2 | CVE-2026-13050 | Firebox × 2 | 49% | #2 　— |
| #5 | CVE-2026-13706 | MediaWiki × 1 | 40% | **#3 ↑2** |
| #3 | CVE-2026-53488 | containerd × 3 | 6% | #4 ↓1 |
| #4 | CVE-2026-53330 | Ubuntu × 6 | 6% | #5 ↓1 |

MediaWiki 升兩名，containerd 與 Ubuntu 掉下去 —— 因為後兩者被實際利用的機率
落在最低的 6% 百分位。**這是一個可以在報告裡展示的具體改進**，而且是實測不是引用。

### 2. CISA KEV — 已知正在被實際利用的漏洞清單

- 網站：<https://www.cisa.gov/known-exploited-vulnerabilities-catalog>
- 資料：`https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json`
- 美國 CISA 維護，**不是預測，是已經確認在野外被攻擊的**

**已實測**：目前 **1,695 筆**，最後更新 2026-09-04。每筆欄位包括：

| 欄位 | 意思 |
|---|---|
| `dateAdded` | 何時被列入 |
| `requiredAction` | 該做什麼 |
| `dueDate` | 美國聯邦機關必須修補的期限 |
| `knownRansomwareCampaignUse` | **是否確認被勒索軟體使用**（1,695 筆裡有 354 筆是，佔 21%） |

**建議用法**：KEV 不該當成一個加權係數，該當成**一票否決的置頂條件** ——
只要命中 KEV，不管 CVSS 多低都直接排到最前面。因為它已經不是「可能」而是「正在發生」。

> 註：你們現在資料集裡的 5 條 CVE **都不在 KEV**（我查過），這很正常，
> 因為它們都是 2026 年 7–8 月剛公開的新漏洞。這反而是個好教材：
> 可以在報告裡說明「新漏洞不在 KEV 不代表安全，KEV 是落後指標」。

---

## 二、最接近的既有產品：OWASP Dependency-Track

- 網站：<https://dependencytrack.org/>
- OWASP 專案頁：<https://owasp.org/www-project-dependency-track/>
- Apache 2.0 授權，免費開源，**超過 20,000 個組織在用**

**這是必須誠實面對的事**：它做的事跟你們**高度重疊** ——
維護一份元件清單、持續比對多個漏洞資料源（NVD、OSV、GitHub Advisory 等）、
**而且已經用 EPSS 做優先排序**。

### 那你們還剩下什麼

差異在**輸入端**，而且這個差異剛好就是需要 LLM 的地方：

| | Dependency-Track | 你們的題目 |
|---|---|---|
| 清單怎麼來 | **SBOM**，由建置流程自動產生（CycloneDX 格式） | **人手寫的自由文字**（「WatchGuard Firebox T145」甚至「防火牆」） |
| 追蹤對象 | 應用程式裡的**軟體元件與函式庫** | 組織裡的 **IT 資產**（防火牆、端點、伺服器） |
| 漏洞資料 | 消費**已經結構化**的漏洞饋送 | **把英文散文公告抽成結構化欄位** |
| 使用者 | 有 CI/CD 建置流程的開發團隊 | 沒有建置流程的中小企業 IT／校園網管 |

**講白一點**：Dependency-Track 解決的是「已經有結構化資料之後，怎麼比對與排序」；
你們解決的是「公告是散文、清單是人隨手寫的，怎麼把它們變成能比對的東西」。
中小企業與校園網管**根本沒有 SBOM**，也不會為了裝防火牆去產一份 CycloneDX。

**但這也是你們必須在報告裡主動說清楚的一段。** 評審如果知道 Dependency-Track，
第一個問題一定是「這跟它差在哪」。與其被問，不如自己先講，而且要講得比對方想得更細。
研究筆記裡「與既有商業產品差異不足」本來就是降權理由之一，這題能留下來就是因為
輸入端的差異，這條論證要站得住。

---

## 三、漏洞資料源

| 來源 | 網址 | 適合什麼 |
|---|---|---|
| **NVD**（你們正在用） | <https://nvd.nist.gov/developers/vulnerabilities> | 主力。CPE 結構化版本區間、CVSS |
| **CVE Program** | <https://www.cve.org/> | CVE 編號的權威來源，比 NVD 更早收到 |
| **OSV.dev**（Google） | <https://osv.dev/> | 開源套件漏洞，查詢用套件名＋版本而非 CPE |
| **GitHub Advisory** | <https://github.com/advisories> | 開源生態系，有 GraphQL API |

**OSV 我試打過**，用套件名＋版本查詢（不是 CPE），介面比 NVD 簡單，
但涵蓋範圍偏開源套件，對「防火牆韌體」這類 IT 資產幫助不大。你們主力還是該用 NVD。

---

## 四、優先序的方法論

| 名稱 | 網址 | 一句話 |
|---|---|---|
| **SSVC** | <https://www.cisa.gov/ssvc> | CISA／CMU 的決策樹式分類法，不給分數而是給「立即修／排程修／延後」的建議 |
| **CVSS v4.0** | <https://www.first.org/cvss/> | 分數怎麼算的官方定義。你們用的 vector 字串就是這個 |
| **EPSS** | <https://www.first.org/epss/> | 見上面第一節 |

**SSVC 值得看一眼**：它的立場是「不要給一個分數，要給一個決定」。
你們的優先度目前是一個數字（139.2），SSVC 的做法是輸出「立即處理／本週處理／可延後」。
兩種各有道理，但如果評審問「139.2 到底代表什麼」，SSVC 提供了另一種回答方式。

---

## 五、相關論文（搜尋所見，還沒細讀）

| 論文 | 網址 | 為什麼相關 |
|---|---|---|
| Prompting the Priorities: A First Look at Evaluating LLMs for Vulnerability Triage and Prioritization | <https://arxiv.org/pdf/2510.18508> | **直接就是你們在做的事**：用 LLM 做漏洞分流與優先排序的評估 |
| Vulnerability Management Chaining: An Integrated Framework for Efficient Cybersecurity Risk Prioritization | <https://arxiv.org/pdf/2506.01220> | 把多種評分系統串起來的框架 |
| Conflicting Scores, Confusing Signals: An Empirical Study of Vulnerability Scoring Systems | <https://arxiv.org/pdf/2508.13644> | 實證研究：不同評分系統彼此矛盾 |

第一篇建議明樺優先讀，因為它可能已經有現成的評測方法可以借用，
省下自己設計評測指標的時間。第三篇適合寫進報告的「為什麼不能只信 CVSS」那一段。

---

## 六、台灣本地

| 來源 | 網址 | 備註 |
|---|---|---|
| **TWCERT/CC** | <https://www.twcert.org.tw/> | 台灣電腦網路危機處理暨協調中心，有中文漏洞警訊 |
| **國家資通安全研究院** | <https://www.nics.nat.gov.tw/> | 政府資安公告 |

這兩個的價值在**中文公告**。如果之後要展示「中文情資也能處理」，
這是取得中文語料的地方。但主力資料源還是 NVD，因為只有它有結構化的 CPE 版本區間。

---

## 七、看完之後建議做的三件事

1. **把 EPSS 加進優先序公式。** 免費、免金鑰、一支 API 就好，
   而且能產出「加了之後排序怎麼變」的對照表 —— 這種前後對照最適合寫進期末報告。

2. **把 CISA KEV 做成置頂條件。** 命中就無條件排第一。實作成本極低
   （下載一個 JSON、比對 CVE 編號），但它是整套系統裡唯一「確定正在被攻擊」的訊號。

3. **在報告裡主動寫一段「與 Dependency-Track 的差異」。** 不要等被問。
   重點放在輸入端：對方吃 SBOM，你們吃人手寫的自由文字，而後者才需要語言模型。

前兩件事會讓 `js/api.js` 多兩支路由（`/api/epss/{cve}`、`/api/kev`），
資料模型多兩個欄位（`epss`、`kev`）。這算小改動，建議第 2 週就加進去，
不要留到最後 —— 它是這個系統從「作業」變成「有業界依據的作品」的關鍵。

> This product uses data from the NVD API but is not endorsed or certified by the NVD.
