# Oikonomia - Summer Camp 2026

Oikonomia 青年營會 ARG（另類實境遊戲）Web App。雙主角路線（Iggy / Marah），含任務提交、遭遇戰、故事階段、GM 後台。

## 功能

- 玩家 Dashboard（HP / 神智 / 力量 / 智力 / 韌性、隊伍、物品、故事）
- GPS 定位驗證、影相上傳（PIL 驗證、8MB 上限）
- Team 協作、任務提交、故事階段解鎖
- Encounter 遭遇戰（precheck、多回合 player phase、瀕死救援）
- GM 後台（隊伍管理、戰鬥監控、公告、重置 PIN、下載隊伍圖片）

## 專案結構（重構後）

```
app.py              # Flask 入口 + DB migrate（~940 行）
wsgi.py             # PythonAnywhere 入口
templates/          # index.html（玩家 UI）、claim_item.html

models/             # 資料層：squad, team, item, encounter, combat
routes/             # Blueprint：auth, player, team, combat, encounters, items, story, misc, gm
services/           # 業務邏輯：story, teams_overview, global_events, gm_admin…
utils/              # helpers, uploads（PIL）, qr, validators, env, deploy
data/               # 靜態遊戲資料：locations, story_config, narrative_stories

encounters/         # Encounter JSON 定義
static/             # 頭像、物品圖、portraits
uploads/            # 玩家上傳相片（不 commit）
deploy/             # PythonAnywhere 部署腳本
```

詳細架構、戰鬥公式、部署狀態見 **[AGENT_HANDOFF.md](./AGENT_HANDOFF.md)**。  
目錄快照見 **[CURRENT_STRUCTURE.md](./CURRENT_STRUCTURE.md)**。  
**已知問題、設定陷阱、已修復假陽性**見 **[UPDATE_LOG.md](./UPDATE_LOG.md)**（Grok／Gemini 必讀，避免重複錯誤建議）。  
**難解、多輪修復嘅 production bug**見 **[bug_log/](./bug_log/)**（SSOT 同步至 Google Drive `oikonomia/bug_log/`）。

## AI 開發分工

本專案由三個 AI 角色協作；用戶（Tak）做最終決策同營會現場把關。

| 角色 | 工具 | 職責 |
|------|------|------|
| **Grok** | Grok（對話） | 提供方向：需求釐清、優先級、架構取捨、bug 根因假設、下一步計劃 |
| **Grok Build** | Grok Build（Agent） | 實際寫入：改 code、跑測試、commit/push、備份、部署指引 |
| **Gemini** | Gemini | 第三方 Engineer：**Code Review** 同 **Debug**（獨立視角，假設 client 不可信） |

### 建議工作流

```
Grok（方向） → Grok Build（實作 + 驗證 + push） → Gemini（review / debug） → Grok Build（修復） → …
```

1. **Grok** 定義「做咩、點解、邊度改」；唔直接改 repo。
2. **Grok Build** 讀 `AGENT_HANDOFF.md`，執行改動並更新版本狀態；**修復 production 問題後更新 [UPDATE_LOG.md](./UPDATE_LOG.md)**。
3. **Gemini** 按 **[GEMINI_REVIEW.md](./GEMINI_REVIEW.md)** 做 review 或追查 bug；輸出 High/Medium/Low 清單。
4. 修復項交回 **Grok Build**；重大方向改動再諮詢 **Grok**。

**避免**：三個角色同時改同一功能；Gemini review 應對準已 push 嘅 commit，唔好對未落地嘅計劃 review。

### Update Log（必讀）

**[UPDATE_LOG.md](./UPDATE_LOG.md)** 記錄：

- 邊啲 **設定／環境變數** 曾導致 PA 掛站、登入失敗、測試誤入等問題  
- 邊啲 **玩家回報** 其實係 UI 假陽性（例如永恆崩壞影「打唔入」）  
- 邊啲係 **刻意設計**（測試 encounter、骰 0 無傷害等），唔應當 bug 修  

若 Grok 或 Gemini 嘅意見與 Update Log 矛盾，用戶可以話：**「請先讀 UPDATE_LOG.md 再答」**——佢哋應引用相關章節，並說明點解仍建議改動。

## 本地運行

```bash
cd oikonomia
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

macOS 預設 5000 port 常被佔用，本地預設用 **5001**（`PORT=5002 python3 app.py` 可改）。

## 本地開發網址

| 用途 | 網址 |
|------|------|
| 玩家端 | http://localhost:5001 |
| GM 後台 | http://localhost:5001/gm |
| API 版本 | http://localhost:5001/api/version |

本地預設憑證（非 production）：

| 項目 | 值 |
|------|-----|
| GM PIN | `gm2026` |
| 重置遊戲密碼 | `reset2026`（可用 `RESET_GAME_PASSWORD` 覆寫） |
| 清空上傳圖片確認碼 | `CLEAR_IMAGES` |

Production 必須設定環境變數：`SECRET_KEY`、`GM_PIN`。

## 正式環境（PythonAnywhere）

| 用途 | 網址 |
|------|------|
| 玩家端 | https://takjai.pythonanywhere.com |
| GM 後台 | https://takjai.pythonanywhere.com/gm |

部署（GitHub 有更新後，在 PA Bash console）：

```bash
FORCE=1 bash ~/oikonomia/deploy/pa-update.sh
```

請**一律**用 `FORCE=1`：PA 上常有本地改動（例如 `.deploy-version`），一般 `git pull` 可能失敗或 code 與磁碟不一致。

然後到 **Web** tab → **Reload** `takjai.pythonanywhere.com`（只跑腳本不會重啟 worker；`version` 可能已更新但 `markers` 仍舊，直到 Reload）。

驗證：

```bash
curl -s https://takjai.pythonanywhere.com/api/version | python3 -m json.tool
```

確認 `success: true`，`version` 與 GitHub 最新 commit 一致，且 `markers` 含 `protagonist_combat`、`trauma_ending` 等（代表 running code 已重載）。

## 測試

```bash
python3 -m py_compile app.py models/*.py routes/*.py services/*.py utils/*.py
python3 test_combat.py          # 需本地 DB / 環境
```

## Bug Log（難解 bug 專檔）

當同一類 bug **修咗幾次仍實機出錯**，或 **CI 綠但玩家仍回報**，唔好只靠對話記憶 — 開 case 寫入 **[bug_log/](./bug_log/)**：

- **[bug_log/README.md](./bug_log/README.md)** — 用途、幾時開 case、檔案結構
- **[bug_log/INDEX.md](./bug_log/INDEX.md)** — 所有 case 一覽
- **Drive SSOT**：`~/Library/CloudStorage/GoogleDrive-ymtwill@gmail.com/My Drive/oikonomia/bug_log/`

每個 case 含 `REPORT.md`（症狀、根因、試過咩、困難、最終修復）+ `attachments/` 相關檔案快照。  
與 `UPDATE_LOG.md`（短條目）、`decisions_log.md`（架構決策）分工，避免大檔一次 dump 入 AI context。

## 文檔索引（各角色入口）

| 角色 | 先讀 |
|------|------|
| **Grok**（方向） | `README.md` → **[UPDATE_LOG.md](./UPDATE_LOG.md)** → **[bug_log/INDEX.md](./bug_log/INDEX.md)**（若有 active case）→ `ARCHITECTURE_ROADMAP.md` |
| **Grok Build**（實作） | **[AGENT_HANDOFF.md](./AGENT_HANDOFF.md)** → **UPDATE_LOG.md** → **bug_log**（若改緊相關模組） |
| **Gemini**（review / debug） | **UPDATE_LOG.md** → **bug_log/cases/…/REPORT.md** + `attachments/` → **GEMINI_REVIEW.md** |