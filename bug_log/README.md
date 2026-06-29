# Oikonomia Bug Log

> **SSOT（單一真相來源）**：Google Drive `My Drive/oikonomia/bug_log/`  
> **Repo 副本**：`bug_log/`（與 Drive 同步，方便 Grok Build / CI 引用）

## Purpose（用途）

記錄**難以一次修妥**、或**反覆出現／CI 綠但實機仍紅**的 production bug。目標係：

1. **唔重複踩同一條路** — 下次 Grok / Gemini / Grok Build 開新 tab 時，唔使由零再猜。
2. **保留完整脈絡** — 症狀、根因、試過咩、點解失敗、最終點解 work。
3. **附帶當時相關檔案** — 每個 case 有 `attachments/`，避免 context window 塞爆成個 `index.html`。
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
        └── attachments/      ← 當時相關檔案快照（可選但建議）
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

## 工作流程（Grok 建議）

```
玩家回報 → Grok 假設根因 → 開 case 草稿（Drive）
         → 附 attachments + PROMPT 俾 Gemini
         → Grok Build 實作 + test
         → 更新 case 狀態（resolved / monitoring）
         → 短摘要寫入 UPDATE_LOG.md
```

## 給 AI 嘅讀法

| 角色 | 點讀 |
|------|------|
| **Grok** | `INDEX.md` → 打開 active case 嘅 `REPORT.md`；大檔去 `attachments/` |
| **Gemini** | 同上；review 時對照 `attachments/` 與 GitHub commit diff |
| **Grok Build** | 實作前讀 case；完成後更新 `INDEX.md` + `REPORT.md` 狀態欄 |

## Drive 路徑

```
~/Library/CloudStorage/GoogleDrive-ymtwill@gmail.com/My Drive/oikonomia/bug_log/
```

Google Drive folder ID（oikonomia 根）：`1myt0Ulh1a4DB4caFBhnLmF4abx2S8sfe`

---

*建立：2026-06-29 · 第一個 case：combat enemy HP / settlement（killing blow）*