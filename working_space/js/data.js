/* data.js — 前端原型的模擬資料集
   CVE 內容取自 NVD 真實資料；資產清單與判定結果為虛構，用來展示版面。
   欄位結構即為之後後端 API 的契約草案。 */
window.DATA = {
 "meta": {
  "org": "示範組織",
  "synced": "2026-09-07 09:12",
  "quota": {
   "used": 7,
   "limit": 50,
   "window": "30 秒"
  },
  "source": "CVE 內容取自 NVD 真實資料；資產清單與判定結果為模擬。"
 },
 "assets": [
  {
   "id": "A01",
   "name": "WatchGuard Firebox T145",
   "vendor": "watchguard",
   "product": "fireware",
   "version": "12.10.2",
   "cpe": "cpe:2.3:o:watchguard:fireware:12.10.2:*:*:*:*:*:*:*",
   "count": 2,
   "exposure": "對外",
   "owner": "網管組",
   "tag": "防火牆",
   "clarity": "ok"
  },
  {
   "id": "A02",
   "name": "Ubuntu 24.04 LTS 伺服器",
   "vendor": "linux",
   "product": "linux_kernel",
   "version": "6.8.0",
   "cpe": "cpe:2.3:o:linux:linux_kernel:6.8.0:*:*:*:*:*:*:*",
   "count": 6,
   "exposure": "內網",
   "owner": "系統組",
   "tag": "伺服器",
   "clarity": "ok"
  },
  {
   "id": "A03",
   "name": "Google Chrome（員工端點）",
   "vendor": "google",
   "product": "chrome",
   "version": "149.0.7827.41",
   "cpe": "cpe:2.3:a:google:chrome:149.0.7827.41:*:*:*:*:*:*:*",
   "count": 34,
   "exposure": "對外",
   "owner": "資訊室",
   "tag": "端點",
   "clarity": "ok"
  },
  {
   "id": "A04",
   "name": "containerd 容器主機",
   "vendor": "linuxfoundation",
   "product": "containerd",
   "version": "1.7.22",
   "cpe": "cpe:2.3:a:linuxfoundation:containerd:1.7.22:*:*:*:*:*:*:*",
   "count": 3,
   "exposure": "內網",
   "owner": "系統組",
   "tag": "容器",
   "clarity": "ok"
  },
  {
   "id": "A05",
   "name": "MediaWiki 內部知識庫",
   "vendor": "mediawiki",
   "product": "mediawiki",
   "version": "1.43.0",
   "cpe": "cpe:2.3:a:mediawiki:mediawiki:1.43.0:*:*:*:*:*:*:*",
   "count": 1,
   "exposure": "內網",
   "owner": "資訊室",
   "tag": "網站",
   "clarity": "ok"
  },
  {
   "id": "A06",
   "name": "PostgreSQL 資料庫",
   "vendor": "postgresql",
   "product": "postgresql",
   "version": "16.4",
   "cpe": "cpe:2.3:a:postgresql:postgresql:16.4:*:*:*:*:*:*:*",
   "count": 2,
   "exposure": "內網",
   "owner": "系統組",
   "tag": "資料庫",
   "clarity": "ok"
  },
  {
   "id": "A07",
   "name": "nginx 反向代理",
   "vendor": "f5",
   "product": "nginx",
   "version": "1.24.0",
   "cpe": "cpe:2.3:a:f5:nginx:1.24.0:*:*:*:*:*:*:*",
   "count": 2,
   "exposure": "對外",
   "owner": "網管組",
   "tag": "網頁伺服器",
   "clarity": "ok"
  },
  {
   "id": "A08",
   "name": "防火牆",
   "vendor": "",
   "product": "",
   "version": "",
   "cpe": "",
   "count": 1,
   "exposure": "對外",
   "owner": "網管組",
   "tag": "未分類",
   "clarity": "vague",
   "hint": "沒有廠牌與型號，組不出 CPE。需要補「廠牌 + 型號 + 韌體版本」才查得動。"
  },
  {
   "id": "A09",
   "name": "公司網站主機",
   "vendor": "",
   "product": "",
   "version": "",
   "cpe": "",
   "count": 1,
   "exposure": "對外",
   "owner": "資訊室",
   "tag": "未分類",
   "clarity": "vague",
   "hint": "「網站主機」可能指作業系統、網頁伺服器、或應用框架。需要指明追蹤哪一層。"
  }
 ],
 "advisories": [
  {
   "id": "CVE-2026-10931",
   "published": "2026-06-04",
   "modified": "2026-07-22",
   "status": "Analyzed",
   "score": 9.6,
   "sev": "CRITICAL",
   "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:H/I:H/A:H",
   "desc": "Use after free in FileSystem in Google Chrome prior to 149.0.7827.53 allowed a remote attacker to potentially perform a sandbox escape via a crafted HTML page. (Chromium security severity: High)",
   "cpe": [
    {
     "c": "cpe:2.3:a:google:chrome:*:*:*:*:*:*:*:*",
     "lt": "149.0.7827.53",
     "le": null,
     "ge": null
    }
   ],
   "refs": [
    "https://chromereleases.googleblog.com/2026/06/stable-channel-update-for-desktop.html",
    "https://issues.chromium.org/issues/501115599"
   ],
   "extracted": {
    "product": "Chrome",
    "vendor": "Google",
    "kind": "Use after free（FileSystem）→ 沙箱逃逸",
    "affected": "< 149.0.7827.53",
    "fixed": "149.0.7827.53",
    "av": "網路（造訪特製網頁）",
    "priv": "不需權限",
    "ui": "需使用者互動",
    "patch": "已釋出",
    "work": "原文未提供",
    "conf": {
     "product": 0.99,
     "affected": 0.96,
     "patch": 0.96,
     "work": 0
    }
   },
   "matched": "A03"
  },
  {
   "id": "CVE-2026-53488",
   "published": "2026-07-01",
   "modified": "2026-07-03",
   "status": "Analyzed",
   "score": 8.8,
   "sev": "HIGH",
   "vector": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H",
   "desc": "containerd is an open-source container runtime. In versions prior to 1.7.33, 2.3.2, 2.2.5, 2.1.9, and 2.0.10 the CRI plugin propagates labels from an image config (LABEL instruction in Dockerfile) to a container without validation. This may result in executing an arbitrary command on the host, via a plugin that consumes container labels for some operations. This issue has been fixed in versions 1.7.33, 2.3.2, 2.2.5, 2.1.9, and 2.0.10.",
   "cpe": [
    {
     "c": "cpe:2.3:a:linuxfoundation:containerd:*:*:*:*:*:*:*:*",
     "lt": "1.7.33",
     "le": null,
     "ge": "1.7.0"
    },
    {
     "c": "cpe:2.3:a:linuxfoundation:containerd:*:*:*:*:*:*:*:*",
     "lt": "2.0.10",
     "le": null,
     "ge": "2.0.0"
    },
    {
     "c": "cpe:2.3:a:linuxfoundation:containerd:*:*:*:*:*:*:*:*",
     "lt": "2.1.9",
     "le": null,
     "ge": "2.1.0"
    }
   ],
   "refs": [
    "https://github.com/containerd/containerd/security/advisories/GHSA-xhf5-7wjv-pqxp"
   ],
   "extracted": {
    "product": "containerd",
    "vendor": "Linux Foundation",
    "kind": "CRI plugin 未驗證映像標籤 → 於主機執行任意指令",
    "affected": "< 1.7.33 / < 2.0.10 / < 2.1.9 / < 2.2.5 / < 2.3.2",
    "fixed": "1.7.33（1.7.x 分支）",
    "av": "本機（透過惡意映像檔的 LABEL）",
    "priv": "需能提供映像",
    "ui": "不需使用者互動",
    "patch": "已釋出",
    "work": "原文未提供",
    "conf": {
     "product": 0.98,
     "affected": 0.93,
     "patch": 0.91,
     "work": 0
    }
   },
   "matched": "A04"
  },
  {
   "id": "CVE-2026-13706",
   "published": "2026-07-01",
   "modified": "2026-07-09",
   "status": "Analyzed",
   "score": 8.8,
   "sev": "HIGH",
   "vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H",
   "desc": "Improper input validation vulnerability in Wikimedia Foundation UrlShortener.\n\n This vulnerability is associated with program files includes/UrlShortenerUtils.Php.",
   "cpe": [
    {
     "c": "cpe:2.3:a:mediawiki:mediawiki:*:*:*:*:*:*:*:*",
     "lt": "1.43.9",
     "le": null,
     "ge": "1.43.0"
    },
    {
     "c": "cpe:2.3:a:mediawiki:mediawiki:*:*:*:*:*:*:*:*",
     "lt": "1.44.6",
     "le": null,
     "ge": "1.44.0"
    },
    {
     "c": "cpe:2.3:a:mediawiki:mediawiki:*:*:*:*:*:*:*:*",
     "lt": "1.45.4",
     "le": null,
     "ge": "1.45.0"
    }
   ],
   "refs": [
    "https://phabricator.wikimedia.org/T418533"
   ],
   "extracted": {
    "product": "UrlShortener 擴充（非 MediaWiki 核心）",
    "vendor": "Wikimedia Foundation",
    "kind": "輸入驗證不當，位於 includes/UrlShortenerUtils.php",
    "affected": "原文未提供",
    "fixed": "原文未提供",
    "av": "網路",
    "priv": "原文未提供",
    "ui": "原文未提供",
    "patch": "未提供",
    "work": "原文未提供",
    "conf": {
     "product": 0.88,
     "affected": 0,
     "patch": 0,
     "work": 0
    }
   },
   "matched": "A05"
  },
  {
   "id": "CVE-2026-13050",
   "published": "2026-07-03",
   "modified": "2026-08-28",
   "status": "Analyzed",
   "score": 7.2,
   "sev": "HIGH",
   "vector": "CVSS:3.1/AV:N/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:H",
   "desc": "An Out-of-bounds Write vulnerability in WatchGuard Fireware OS networkd process could allow an authenticated privileged user to execute arbitrary code via a specially crafted requests to the Management Web UI.",
   "cpe": [
    {
     "c": "cpe:2.3:o:watchguard:fireware:*:*:*:*:*:*:*:*",
     "lt": "2026.2.1",
     "le": null,
     "ge": "2025.1"
    },
    {
     "c": "cpe:2.3:o:watchguard:fireware:*:*:*:*:*:*:*:*",
     "lt": "12.5.19",
     "le": null,
     "ge": "12.5"
    },
    {
     "c": "cpe:2.3:o:watchguard:fireware:*:*:*:*:*:*:*:*",
     "lt": "11.12.4",
     "le": null,
     "ge": "11.0.0"
    }
   ],
   "refs": [
    "https://psirt.watchguard.com/CVE-2026-13050",
    "https://www.watchguard.com/wgrd-psirt/advisory/wgsa-2026-00029"
   ],
   "extracted": {
    "product": "Fireware OS（networkd 程序）",
    "vendor": "WatchGuard",
    "kind": "Out-of-bounds Write，經管理 Web UI 觸發",
    "affected": "原文未提供",
    "fixed": "原文未提供",
    "av": "網路（管理 Web UI）",
    "priv": "需已驗證的特權使用者",
    "ui": "不需使用者互動",
    "patch": "未提供",
    "work": "限制管理介面的對外存取（依攻擊途徑推論，非原文明載）",
    "conf": {
     "product": 0.95,
     "affected": 0,
     "patch": 0,
     "work": 0.44
    }
   },
   "matched": "A01"
  },
  {
   "id": "CVE-2026-53330",
   "published": "2026-07-01",
   "modified": "2026-07-23",
   "status": "Analyzed",
   "score": 7.1,
   "sev": "HIGH",
   "vector": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:H",
   "desc": "In the Linux kernel, the following vulnerability has been resolved:\n\ndrm/amd/display: Fix out-of-bounds read in dp_get_eq_aux_rd_interval()\n\n[Why & How]\nThe aux_rd_interval array in struct dc_lttpr_caps is declared with\nMAX_REPEATER_CNT - 1 (7) elements, indexed 0..6. However, the offset\nparameter passed to dp_get_eq_aux_rd_interval() can be as large as\nMAX_REPEATER_CNT (8) when a sink reports 8 LTTPR repeaters via DPCD.\nThis leads to an out-of-bounds read of aux_rd_interval[7] when offset\nis 8.\n\nFix this by growing aux_rd_interval to MAX_REPEATER_CNT elements to\naccommodate the full range of valid repeater counts defined by the DP\nspec.\n\n(cherry picked from commit a55a458a8df37a65ffda5cf721",
   "cpe": [
    {
     "c": "cpe:2.3:o:linux:linux_kernel:*:*:*:*:*:*:*:*",
     "lt": "6.18.36",
     "le": null,
     "ge": "5.6"
    },
    {
     "c": "cpe:2.3:o:linux:linux_kernel:*:*:*:*:*:*:*:*",
     "lt": "7.0.13",
     "le": null,
     "ge": "6.19"
    },
    {
     "c": "cpe:2.3:o:linux:linux_kernel:7.1:rc1:*:*:*:*:*:*",
     "lt": null,
     "le": null,
     "ge": null
    }
   ],
   "refs": [
    "https://git.kernel.org/stable/c/454d3b3d499c18373f8960d31aea48338a3ca9e0",
    "https://git.kernel.org/stable/c/dc1490927d79fe9621e29f4a4f5d7b5ccb6aea3e"
   ],
   "extracted": {
    "product": "Linux Kernel（drm/amd/display）",
    "vendor": "Linux",
    "kind": "dp_get_eq_aux_rd_interval() 陣列越界讀取",
    "affected": "原文未提供",
    "fixed": "已於上游修正，隨發行版更新",
    "av": "本機",
    "priv": "需一般使用者權限",
    "ui": "不需使用者互動",
    "patch": "已釋出",
    "work": "原文未提供",
    "conf": {
     "product": 0.97,
     "affected": 0,
     "patch": 0.72,
     "work": 0
    }
   },
   "matched": "A02"
  }
 ],
 "unmatched": [
  {
   "id": "CVE-2026-10611",
   "published": "2026-06-02",
   "score": 10.0,
   "sev": "CRITICAL",
   "product": "misp-project misp",
   "desc": "An authentication bypass vulnerability exists in MISP when LDAP mixed authentication is enabled with OTP enforcement. In deployments configured with LdapAuth.mixedAuth=true and Security.require_otp=true, users authentica",
   "matched": null
  },
  {
   "id": "CVE-2026-42074",
   "published": "2026-06-02",
   "score": 9.8,
   "sev": "CRITICAL",
   "product": "gitlawb openclaude",
   "desc": "OpenClaude is an open-source coding-agent command line interface for cloud and local model providers. Prior to version 0.5.1, the dangerouslyDisableSandbox parameter is exposed as part of the BashTool input schema, meani",
   "matched": null
  },
  {
   "id": "CVE-2026-5241",
   "published": "2026-06-03",
   "score": 9.6,
   "sev": "CRITICAL",
   "product": "huggingface transformers",
   "desc": "A vulnerability in the LightGlue model loading path of huggingface/transformers version 5.2.0 allows an attacker-controlled model repository to execute arbitrary code during model initialization. The issue arises because",
   "matched": null
  },
  {
   "id": "CVE-2026-22872",
   "published": "2026-06-01",
   "score": 9.1,
   "sev": "CRITICAL",
   "product": "projectcapsule capsule",
   "desc": "Capsule is a multi-tenancy and policy-based framework for Kubernetes. The Capsule Controller runs with cluster-admin privileges. Although the TenantResource RawItems processing logic forcibly sets the namespace, this is ",
   "matched": null
  },
  {
   "id": "CVE-2026-44825",
   "published": "2026-06-01",
   "score": 8.1,
   "sev": "HIGH",
   "product": "apache solr",
   "desc": "Hardcoded credentials in the Basic Authentication setup tool (bin/solr auth enable) in Apache Solr versions 9.4.0 through 9.10.1 and 10.0.0 allows a remote attacker to gain full administrative access to the cluster via p",
   "matched": null
  },
  {
   "id": "CVE-2026-49121",
   "published": "2026-06-01",
   "score": 8.1,
   "sev": "HIGH",
   "product": "amd aiter",
   "desc": "AI Tensor Engine for ROCm (AITER) through 0.1.14 contains an unauthenticated remote code execution vulnerability in the MessageQueue.recv() function within shm_broadcast.py that allows unauthenticated remote attackers to",
   "matched": null
  },
  {
   "id": "CVE-2026-35482",
   "published": "2026-06-02",
   "score": 8.0,
   "sev": "HIGH",
   "product": "alf alf",
   "desc": "alf.io is an open source ticket reservation system for conferences, trade shows, workshops, and meetups. Prior to version 2.0-M5-2606, a sandbox escape vulnerability in the alf.io extension script engine allows an authen",
   "matched": null
  }
 ],
 "queue": [
  {
   "cve": "CVE-2026-10931",
   "asset": "A03",
   "priority": 139.2,
   "f": {
    "cvss": 9.6,
    "expo": 1.0,
    "cnt": 1.45,
    "patch": 1.0
   },
   "action": "升級到 149.0.7827.53",
   "rank": 1,
   "sla": 3,
   "elapsed": 2,
   "left": 1,
   "owner": "資訊室",
   "status": "open",
   "sev": "CRITICAL",
   "score": 9.6,
   "title": "Google Chrome（員工端點）",
   "count": 34,
   "exposure": "對外",
   "fixed": "149.0.7827.53",
   "patchable": true
  },
  {
   "cve": "CVE-2026-13050",
   "asset": "A01",
   "priority": 66.2,
   "f": {
    "cvss": 7.2,
    "expo": 1.0,
    "cnt": 1.15,
    "patch": 0.8
   },
   "action": "公告未提供修補版本——先確認廠商公告，必要時套用緩解",
   "rank": 2,
   "sla": 7,
   "elapsed": 1,
   "left": 6,
   "owner": "網管組",
   "status": "open",
   "sev": "HIGH",
   "score": 7.2,
   "title": "WatchGuard Firebox T145",
   "count": 2,
   "exposure": "對外",
   "fixed": "原文未提供",
   "patchable": false
  },
  {
   "cve": "CVE-2026-53488",
   "asset": "A04",
   "priority": 60.7,
   "f": {
    "cvss": 8.8,
    "expo": 0.6,
    "cnt": 1.15,
    "patch": 1.0
   },
   "action": "升級到 1.7.33（1.7.x 分支）",
   "rank": 3,
   "sla": 7,
   "elapsed": 4,
   "left": 3,
   "owner": "系統組",
   "status": "open",
   "sev": "HIGH",
   "score": 8.8,
   "title": "containerd 容器主機",
   "count": 3,
   "exposure": "內網",
   "fixed": "1.7.33（1.7.x 分支）",
   "patchable": true
  },
  {
   "cve": "CVE-2026-53330",
   "asset": "A02",
   "priority": 55.4,
   "f": {
    "cvss": 7.1,
    "expo": 0.6,
    "cnt": 1.3,
    "patch": 1.0
   },
   "action": "升級到 已於上游修正，隨發行版更新",
   "rank": 4,
   "sla": 7,
   "elapsed": 6,
   "left": 1,
   "owner": "系統組",
   "status": "open",
   "sev": "HIGH",
   "score": 7.1,
   "title": "Ubuntu 24.04 LTS 伺服器",
   "count": 6,
   "exposure": "內網",
   "fixed": "已於上游修正，隨發行版更新",
   "patchable": true
  },
  {
   "cve": "CVE-2026-13706",
   "asset": "A05",
   "priority": 42.2,
   "f": {
    "cvss": 8.8,
    "expo": 0.6,
    "cnt": 1.0,
    "patch": 0.8
   },
   "action": "公告未提供修補版本——先確認廠商公告，必要時套用緩解",
   "rank": 5,
   "sla": 7,
   "elapsed": 9,
   "left": -2,
   "owner": "資訊室",
   "status": "open",
   "sev": "HIGH",
   "score": 8.8,
   "title": "MediaWiki 內部知識庫",
   "count": 1,
   "exposure": "內網",
   "fixed": "原文未提供",
   "patchable": false
  }
 ],
 "trace": [
  {
   "s": 1,
   "tool": "list_assets",
   "args": "{}",
   "res": "回傳 9 項資產，其中 2 項名稱不夠明確",
   "ms": 12,
   "cache": "本地",
   "quota": "0 / 50"
  },
  {
   "s": 2,
   "tool": "check_clarity",
   "args": "{\"names\": [\"防火牆\", \"公司網站主機\"]}",
   "res": "兩項都組不出 CPE → 產生追問，不消耗查詢額度",
   "ms": 430,
   "cache": "—",
   "quota": "0 / 50"
  },
  {
   "s": 3,
   "tool": "search_cve",
   "args": "{\"cpe\": \"cpe:2.3:o:watchguard:fireware:12.10.2\"}",
   "res": "命中 1 筆（CVE-2026-13050，CVSS 7.2）",
   "ms": 880,
   "cache": "未命中 → 已回寫",
   "quota": "1 / 50"
  },
  {
   "s": 4,
   "tool": "search_cve",
   "args": "{\"cpe\": \"cpe:2.3:a:google:chrome:149.0.7827.41\"}",
   "res": "命中 1 筆（CVE-2026-10931，CVSS 9.6）",
   "ms": 910,
   "cache": "未命中 → 已回寫",
   "quota": "2 / 50"
  },
  {
   "s": 5,
   "tool": "search_cve",
   "args": "{\"cpe\": \"cpe:2.3:o:linux:linux_kernel:6.8.0\"}",
   "res": "命中 1 筆（CVE-2026-53330，CVSS 7.1）",
   "ms": 1240,
   "cache": "未命中 → 已回寫",
   "quota": "3 / 50"
  },
  {
   "s": 6,
   "tool": "search_cve",
   "args": "{\"cpe\": \"cpe:2.3:a:linuxfoundation:containerd:1.7.22\"}",
   "res": "命中 1 筆（CVE-2026-53488，CVSS 8.8）",
   "ms": 760,
   "cache": "未命中 → 已回寫",
   "quota": "4 / 50"
  },
  {
   "s": 7,
   "tool": "search_cve",
   "args": "{\"cpe\": \"cpe:2.3:a:mediawiki:mediawiki:1.43.0\"}",
   "res": "命中 1 筆（CVE-2026-13706，CVSS 8.8）",
   "ms": 690,
   "cache": "未命中 → 已回寫",
   "quota": "5 / 50"
  },
  {
   "s": 8,
   "tool": "search_cve",
   "args": "{\"cpe\": \"cpe:2.3:a:postgresql:postgresql:16.4\"}",
   "res": "無命中——這批情資與這項資產無關",
   "ms": 640,
   "cache": "未命中 → 已回寫",
   "quota": "6 / 50"
  },
  {
   "s": 9,
   "tool": "search_cve",
   "args": "{\"cpe\": \"cpe:2.3:a:f5:nginx:1.24.0\"}",
   "res": "無命中",
   "ms": 580,
   "cache": "未命中 → 已回寫",
   "quota": "7 / 50"
  },
  {
   "s": 10,
   "tool": "rank_actions",
   "args": "{\"hits\": 5}",
   "res": "依 CVSS × 暴露面 × 資產數 × 修補可得性 排序，產生 5 筆待辦",
   "ms": 1520,
   "cache": "—",
   "quota": "7 / 50"
  }
 ],
 "trend": [
  {
   "d": "08-25",
   "new": 3,
   "closed": 1
  },
  {
   "d": "08-26",
   "new": 7,
   "closed": 4
  },
  {
   "d": "08-27",
   "new": 2,
   "closed": 3
  },
  {
   "d": "08-28",
   "new": 9,
   "closed": 2
  },
  {
   "d": "08-29",
   "new": 4,
   "closed": 6
  },
  {
   "d": "08-30",
   "new": 1,
   "closed": 2
  },
  {
   "d": "08-31",
   "new": 0,
   "closed": 1
  },
  {
   "d": "09-01",
   "new": 6,
   "closed": 3
  },
  {
   "d": "09-02",
   "new": 11,
   "closed": 5
  },
  {
   "d": "09-03",
   "new": 5,
   "closed": 8
  },
  {
   "d": "09-04",
   "new": 3,
   "closed": 4
  },
  {
   "d": "09-05",
   "new": 8,
   "closed": 2
  },
  {
   "d": "09-06",
   "new": 4,
   "closed": 7
  },
  {
   "d": "09-07",
   "new": 12,
   "closed": 0
  }
 ],
 "weekly": {
  "opened": 38,
  "closed": 26,
  "mttr": 4.2,
  "backlog": 17
 },
 "owners": [
  "網管組",
  "系統組",
  "資訊室"
 ]
};
