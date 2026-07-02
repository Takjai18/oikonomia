# Oikonomia - Summer Camp 2026

Oikonomia 青年營會 ARG（另類實境遊戲）Web App。雙主角路線（Iggy / Marah），含任務提交、遭遇戰、故事階段、GM 後台。

## 功能

- 玩家 Dashboard（HP / 神智 / 力量 / 智力 / 韌性、隊伍、物品、故事）
- GPS 定位驗證、影相上傳（PIL 驗證、8MB 上限）
- Team 協作、任務提交、故事階段解鎖
- Encounter 遭遇戰（**Combat V2** 預設開啟；GM 可關閉維護、precheck、多回合 player phase、瀕死救援）
- GM 後台（隊伍管理、戰鬥監控、公告、重置 PIN、下載隊伍圖片）

## 專案結構（重構後）

```
app.py              # Flask 入口 + DB migrate（~940 行）
wsgi.py             # Production 入口（Render gunicorn / PA WSGI）
render.yaml         # Render Blueprint（Starter、Singapore、/data 持久碟）
templates/          # index.html（玩家 UI）、claim_item.html

models/             # 資料層：squad, team, item, encounter, combat
routes/             # Blueprint：auth, player, team, combat, encounters, items, story, misc, gm
services/           # 業務邏輯：story, teams_overview, global_events, gm_admin…
utils/              # helpers, uploads（PIL）, qr, validators, env, deploy
data/               # 靜態遊戲資料：locations, story_config, narrative_stories

encounters/         # Encounter JSON 定義
static/             # 頭像、物品圖、portraits；`js/combat/avatar_urls.js` 戰鬥頭像 fallback
uploads/            # 玩家上傳相片（不 commit）
deploy/             # Render（主）+ PythonAnywhere（後備）部署腳本
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

**Gemini 建議唔盲目跟從**：先對照 **[UPDATE_LOG.md](./UPDATE_LOG.md)** 同 **GEMINI_REVIEW.md §29**（已修／已拒絕項）。常見誤判包括：重複建議已 ship 嘅 `_attach_round_settlement`、指向 repo 唔存在嘅 fallback 檔名、或把 Linux 大小寫當根因而忽略 API 回傳裸檔名。Grok Build 應 **curl 驗證靜態 URL**、**讀現行 code** 再決定做唔做。

**避免**：三個角色同時改同一功能；Gemini review 應對準已 push 嘅 commit，唔好對未落地嘅計劃 review。

### Context 管理協議（防溢出 · 全角色必守）

長對話唔需要開新 Chat，但**唔好再貼整份大 Bundle**。穩固 Baseline 已封存於 repo，後續只交局部範圍。

| Baseline（只讀引用，唔貼全文） | 用途 |
|-------------------------------|------|
| **`COMBAT_V2_AUDIT_BUNDLE.md` v15** | Combat V2 SSOT（首次 onboarding） |
| **`COMBAT_V2_PARTIAL_INDEX.md`** | 選 R11 / R12-A～D Partial Bundle |
| **`COMBAT_V2_R11_PARTIAL_BUNDLE.md`** | 營會現場高風險 A/B/C |
| **`COMBAT_V2_R12_*_*.md`** | 大廳橋接 / DB / 編排 / INV 局部審計 |
| `combat_greenfield_final.md` | 綠地架構規格 |
| `AGENT_HANDOFF.md` / `GEMINI_REVIEW.md` | 實作／審計流程 |

**局部交付**：每次只處理**一個** Python 檔／路由函數，或**一個**前端 JS View；附專項測試即可。  
**重新生成 Bundle**：
```bash
python3 scripts/build_combat_v2_audit_bundle.py       # v14 全文 SSOT + R11 partial
python3 scripts/build_combat_v2_partial_bundles.py  # 索引 + R11 + R12 A–D
```

**進門對齊模式**（用戶或 Agent 在訊息**最開頭**標註）：

| 模式 | 回應要求 |
|------|----------|
| **【開發模式】** | 零前言 → 100% 可 Copy-and-Paste 的生產級代碼 + 專項單元測試 |
| **【審計模式】** | 依標準結構輸出 **【Critical】→【High/Medium】→【Low】→ 健康度總評** |

**建議提交範本**：

```
【開發模式】
目標：<一句話>
檔案：<path 或單一函數>
約束：<不變式 / 不可動 API>
```

```
【審計模式】
範圍：<單檔 / 單函數>
焦點：<例如 INV-D、GM session>
Baseline：COMBAT_V2_AUDIT_BUNDLE v14（已讀，唔貼全文）· 或貼 COMBAT_V2_PARTIAL_INDEX 所指 Partial
```

詳見 **[AGENT_HANDOFF.md](./AGENT_HANDOFF.md)**（Grok Build）與 **[GEMINI_REVIEW.md](./GEMINI_REVIEW.md)**（Gemini）。

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

### 戰鬥系統 V2（預設開啟）

| 項目 | 說明 |
|------|------|
| **預設** | **開啟** — 玩家進入遭遇戰頁會載入 Greenfield 戰鬥 UI |
| **GM 開關** | GM 後台 → **戰鬥監控** 分頁 →「開啟／關閉戰鬥系統」 |
| **持久化** | `data/.combat_v2`（`1` 開、`0` 關）；`pa-update.sh` 首次會建立 `1` |
| **緊急覆寫** | 環境變數 `COMBAT_V2=0` 可強制關閉（優先於檔案） |
| **驗證** | `curl -s …/api/version` → `"combat_v2": true` |

關閉時玩家端戰鬥區顯示維護提示（唔影響登入、任務、劇情等其他功能）。

## 正式環境

### Render.com（現行 · Starter / Singapore）

| 用途 | 網址 |
|------|------|
| 玩家端 | https://oikonomia.onrender.com |
| GM 後台 | https://oikonomia.onrender.com/gm |
| Dashboard | [Render 服務](https://dashboard.render.com) · Service ID `srv-d8v8i7cvikkc73fbsv0g` |

**架構約束（之後改 code 必須考慮）**

| 項目 | 設定 |
|------|------|
| 程序 | **gunicorn** `wsgi:application`（唔用 `python3 app.py`） |
| 持久資料 | `DATA_DIR=/data`（1GB Persistent Disk） |
| 資料庫 | `/data/oikonomia.db` |
| 相片上傳 | `/data/uploads/` |
| 密鑰 | `/data/.secret_key`、`.gm_pin`（或 Dashboard `SECRET_KEY` / `GM_PIN`） |
| 戰鬥 V2 | `/data/.combat_v2`（預設 `1`） |
| 環境標記 | `RENDER=true`、`FLASK_ENV=production` |
| 版本 SSOT | 見下方「版本核對」；**勿 commit** `.deploy-version` |

Blueprint：`render.yaml` · `preDeployCommand` + `startCommand` 均會跑 `deploy/render-predeploy.sh`。

**版本核對（避免假陽性）**

| 優先 | 來源 | 說明 |
|------|------|------|
| 1 | `.deploy-version` | `preDeploy` / 啟動時由 `render-predeploy.sh` 寫入（**僅 deploy 產物，在 `.gitignore`**） |
| 2 | `RENDER_GIT_COMMIT` | Render 自動注入；`utils/deploy.py` 在無 `.deploy-version` 時取前 7 字元 |
| 3 | `/api/version` → `git_commit` | 完整 SHA，用於對照 Dashboard deploy 的 commit |

```bash
LOCAL=$(git rev-parse --short HEAD)
curl -s https://oikonomia.onrender.com/api/version | python3 -c "
import sys, json
d = json.load(sys.stdin)
v, gc = d.get('version'), (d.get('git_commit') or '')[:7]
print('version:', v, 'git_commit[:7]:', gc, 'render:', d.get('render'))
assert v == '$LOCAL', f'version mismatch: {v} != $LOCAL'
"
```

**Deploy 陷阱（2026-07-02 實例 — 勿重犯）**

| 陷阱 | 後果 | 預防 |
|------|------|------|
| **commit `.deploy-version`** | `/api/version` 長期顯示舊 hash（曾卡 `3017e16`） | 已在 `.gitignore`；`git status` 見到即 **勿 add** |
| **Dashboard 未跑 preDeploy** | log 無 `=== Render pre-deploy ===`；DB bootstrap／secrets 可能漏跑 | Settings 設 Pre-deploy **或** Start Command 含 `render-predeploy.sh`（見 `render.yaml`） |
| **只睇 `version` 以為未 deploy** | code 可能已新，只是 version 字串舊 | 對照 `git_commit` 與 Render Events log |

**Dashboard 建議設定**（Settings → Build & Deploy，與 `render.yaml` 對齊）：

| 欄位 | 值 |
|------|-----|
| Pre-deploy command | `bash deploy/render-predeploy.sh` |
| Start command | `bash -c 'bash deploy/render-predeploy.sh && exec gunicorn wsgi:application …'`（全文見 `render.yaml`） |
| Branch | `main` · Auto-Deploy **Yes** |

**每次 code 改動後同步 Render（Grok Build 必做）**

```
改 code → pre_deploy_checks.sh → git push main
→ CI 測試通過 → POST Deploy Hook → 等 deploy 完成
→ curl https://oikonomia.onrender.com/api/version 確認 version 與 main 一致
```

Deploy Hook URL 存於 GitHub Secret `RENDER_DEPLOY_HOOK`（**勿 commit 到 repo**）。本機手動觸發：

```bash
RENDER_DEPLOY_HOOK='…' bash deploy/render-trigger-deploy.sh
# 或
bash deploy/render-sync.sh   # push 後觸發 + 輪詢 /api/version
```

驗證：

```bash
bash deploy/render-check.sh https://oikonomia.onrender.com
curl -s https://oikonomia.onrender.com/api/version | python3 -m json.tool
```

預期：`render: true`、`data_dir: "/data"`、`db_path: "/data/oikonomia.db"`、`version` 與 `git rev-parse --short HEAD` 相同，`git_commit` 前 7 字元與 `version` 一致。Deploy log 應見 `=== Render pre-deploy ===`。

### PythonAnywhere（後備）

| 用途 | 網址 |
|------|------|
| 玩家端 | https://takjai.pythonanywhere.com |
| GM 後台 | https://takjai.pythonanywhere.com/gm |

僅在 Render 故障或 rollback 時使用。部署：

```bash
FORCE=1 bash ~/oikonomia/deploy/pa-update.sh
# Web tab → Reload takjai.pythonanywhere.com
curl -s https://takjai.pythonanywhere.com/api/version | python3 -m json.tool
```

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
| **Grok Build**（實作） | **[AGENT_HANDOFF.md](./AGENT_HANDOFF.md)** → **Context 管理協議** → **UPDATE_LOG.md** → **bug_log**（若改緊相關模組） |
| **Gemini**（review / debug） | **GEMINI_REVIEW.md** §Context 管理 → **UPDATE_LOG.md** → **bug_log/cases/…/REPORT.md**；局部檔案 only |