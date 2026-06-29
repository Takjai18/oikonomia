# Oikonomia Bug Log

> **SSOT（單一真相來源）**：Google Drive `My Drive/oikonomia/bug_log/`  
> **Repo 副本**：`bug_log/`（與 Drive 同步，方便 Grok Build / CI 引用）

## Purpose（用途）

記錄**難以一次修妥**、或**反覆出現／CI 綠但實機仍紅**的 production bug。目標係：

1. **唔重複踩同一條路** — 下次 Grok / Gemini / Grok Build 開新 tab 時，唔使由零再猜。
2. **保留完整脈絡** — 症狀、根因、試過咩、點解失敗、最終點解 work。
3. **附帶當時相關檔案** — 每個 case 有 `attachments/`（快照）；**最新 code 以 GitHub main 為準**。
4. **與其他文檔分工**：
   - `UPDATE_LOG.md` — 短條目：設定陷阱、假陽性、已修復一語帶過
   - `decisions_log.md` — 架構決策（做咩、唔做咩）
   - **`bug_log/`** — 長篇調查檔：多輪修復仍搞唔掂嘅 case

## 幾時開新 case？

符合**任一**條就應開檔（唔好只寫 Slack／對話）：

- 同一類 bug **≥2 次** deploy 後玩家仍回報
- **Automated tests 全綠**但 **實機／營會 Wi‑Fi** 仍錯
- 需要 **Grok + Gemini 協作**先搵到根因
- 修復橫跨 **backend + frontend + 測試缺口**，難用一句 commit message 講清

## 檔案結構

```
bug_log/
├── README.md                 ← 你而家讀緊呢份
├── INDEX.md                  ← 所有 case 一覽（狀態、commit、連結）
└── cases/
    └── YYYY-MM-DD_short_slug/
        ├── REPORT.md         ← 主報告（必填）
        ├── GEMINI_CONSULT.md ← 俾 Gemini 嘅一頁摘要（可選）
        ├── GEMINI_PACKET.md  ← 【重要】自包含 code + 摘要，俾 Gemini 貼上（由 script 生成）
        └── attachments/      ← 當時相關檔案快照（可過時；以 GitHub 為準）
```

### `REPORT.md` 建議章節

1. **摘要**（3–5 句）
2. **症狀**（邊個玩家、邊個 encounter、重現步驟）
3. **根因**（backend / frontend / race / 測試缺口）
4. **做過咩**（按時間 commit 表）
5. **困難／誤判**（以為係 X 其實係 Y）
6. **最終修復**（方案、trade-off、驗證 commit）
7. **回歸測試**（邊個 script、邊個 case 名）
8. **實機 checklist**（營會前必跑）
9. **相關文檔**（`decisions_log.md` section、Gemini prompt 等）

---

## 如何俾 Gemini 讀檔（重要）

> **Gemini 多數讀唔到** Google Drive `oikonomia/` 資料夾內嘅 `.md`、`bug_log/`、`templates/index.html`（API 只索引到部分 PDF/PPT）。**唔好只俾資料夾連結。**

### 推薦做法（按優先）

| 方法 | 步驟 | 適用 |
|------|------|------|
| **① 貼 GEMINI_PACKET** | 打開 case 入面 `GEMINI_PACKET.md` → 全選 Copy → 貼到 Gemini chat | **最可靠** |
| **② GitHub Raw URL** | 俾單檔 raw link，例如 `https://raw.githubusercontent.com/Takjai18/oikonomia/main/bug_log/cases/.../GEMINI_PACKET.md` | Gemini 支援 URL 時 |
| **③ Google Doc 單檔** | 將 `GEMINI_PACKET.md` 內容貼入新 Google Doc → 分享「知道連結者可檢視」→ 俾**該 Doc 連結** | Drive 協作習慣 |
| **④ GitHub PR / commit link** | `https://github.com/Takjai18/oikonomia/blob/main/templates/index.html` | 對照最新 code |

### 唔推薦

- ❌ 只俾 Drive **資料夾**連結（`My Drive/oikonomia/`）
- ❌ 只俾 `attachments/`（可能係舊 commit 快照）
- ❌ 假設 Gemini 讀到 repo 本機路徑

### 更新 GEMINI_PACKET（Grok Build / 你）

每次改完 `templates/index.html` 或 combat 相關 code、準備再問 Gemini 前：

```bash
cd ~/Documents/oikonomia   # 或 PA clone 路徑
bash scripts/build_gemini_packet.sh
# 輸出：bug_log/cases/2026-06-29_combat_enemy_hp_settlement/GEMINI_PACKET.md
```

然後 Copy 新 `GEMINI_PACKET.md` 俾 Gemini。順便 `git add` + push，等 GitHub Raw link 同步。

### 當前 active case 快速入口

- 摘要：`cases/2026-06-29_combat_enemy_hp_settlement/GEMINI_CONSULT.md`
- **完整包（貼 Gemini）**：`cases/2026-06-29_combat_enemy_hp_settlement/GEMINI_PACKET.md`
- 主報告：`cases/2026-06-29_combat_enemy_hp_settlement/REPORT.md` §12

---

## 工作流程（Grok 建議）

```
玩家回報 → Grok 假設根因 → 開 case 草稿（Drive + repo）
         → bash scripts/build_gemini_packet.sh
         → Copy GEMINI_PACKET.md 俾 Gemini（唔靠 Drive 資料夾）
         → Grok Build 實作 + test
         → 更新 case 狀態（resolved / monitoring）
         → 短摘要寫入 UPDATE_LOG.md
```

## 給 AI 嘅讀法

| 角色 | 點讀 |
|------|------|
| **Grok** | `INDEX.md` → `REPORT.md`；code 用 GitHub main |
| **Gemini** | **`GEMINI_PACKET.md`（貼上）** 或 GitHub Raw；唔依賴 Drive 資料夾 |
| **Grok Build** | 實作前讀 case；完成後 `build_gemini_packet.sh` + 更新 `INDEX.md` |

## Drive 路徑

```
~/Library/CloudStorage/GoogleDrive-ymtwill@gmail.com/My Drive/oikonomia/bug_log/
```

Google Drive folder ID（oikonomia 根）：`1myt0Ulh1a4DB4caFBhnLmF4abx2S8sfe`

> Drive 仍作 SSOT 備份；**Gemini 諮詢以 repo 內 `GEMINI_PACKET.md` 為準**。

---

*建立：2026-06-29 · 更新：2026-06-29 — 新增 Gemini 讀檔指引 + build_gemini_packet.sh*