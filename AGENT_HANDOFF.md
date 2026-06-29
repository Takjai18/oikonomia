# Oikonomia — Agent Handoff（新 Tab 必讀）

> **給下一個 AI Agent**：用戶會開新 tab 繼續開發。請**直接執行**，唔好只係話用戶點做。  
> **你的責任**：改 code → 驗證 → commit/push GitHub → **確保 PythonAnywhere 同 local 版本一致**（見 Deploy 一節）。  
> 最後更新：2026-06-29 · local/GitHub：`fc53d73`

**本檔副本**：`Documents/oikonomia/AGENT_HANDOFF.md` 與 Google Drive `My Drive/oikonomia/AGENT_HANDOFF.md` 應保持同步。

---

## 版本狀態（開 tab 第一件事要核對）

| 環境 | Commit | 狀態 |
|------|--------|------|
| **Local** | `fc53d73` | ✅ 最新 |
| **GitHub `main`** | `fc53d73` | ✅ 已 push |
| **PythonAnywhere** | 未知（500） | 🔴 **網站掛咗** — `/api/version` 回 HTML error page，唔係 JSON |

```bash
# 本地
cd /Users/mingtakyau/Documents/oikonomia && git rev-parse --short HEAD

# 遠端（應回 JSON；若見 "Something went wrong" 即 PA 未修好）
curl -s https://takjai.pythonanywhere.com/api/version | python3 -m json.tool
```

兩邊 `version` 必須相同才算部署完成。

### PA 500 根因（已修但未部署）

`fc53d73` 修咗 **`models/combat.py` 重複定義** `apply_encounter_success` 等函數，shadow 咗 `models/encounter_outcomes.py` 嘅 import，導致戰鬥勝利時 `NameError: add_insight_fragments` → 全站 500。  
**P0：請用戶部署 `fc53d73` 到 PA 並 Web Reload。**

### 本地測試（`fc53d73`）

```bash
./venv/bin/python3 scripts/test_combat_flow.py
# 預期：17 通過 / 0 失敗
```

---

## 專案概覽

| 項目 | 值 |
|------|-----|
| 專案路徑 | `/Users/mingtakyau/Documents/oikonomia` |
| Google Drive 備份 | `~/Library/CloudStorage/GoogleDrive-ymtwill@gmail.com/My Drive/oikonomia` |
| 主檔 | `app.py`（~940 行：Flask init、DB migrate、middleware） |
| 玩家 UI | `templates/index.html`（~5800 行 JS/HTML） |
| 資料庫 | `oikonomia.db`（本地）；PA 上在 `data/oikonomia.db` |
| GitHub | https://github.com/Takjai18/oikonomia |
| 正式環境 | https://takjai.pythonanywhere.com |
| GM 後台 | https://takjai.pythonanywhere.com/gm （PIN: `gm2026` 或 env `GM_PIN`） |
| 本地開發 | `source venv/bin/activate && python3 app.py` → http://localhost:5001 |
| 測試帳號 | `test_squad_01`（開發／實機測試用） |

**主題**：Summer Camp 2026 ARG（Oikonomia 青年營會），Iggy / Marah 雙主角路線。

---

## 架構（2026-06-29 重構後）

```
app.py                    # Flask init, migrate_db(), register blueprints
wsgi.py                   # PA 入口；設 DATA_DIR=data/
templates/
  index.html              # 玩家 UI + 戰鬥 JS（唔再喺 app.py）
  claim_item.html
routes/                   # HTTP blueprints
  auth.py, player.py, team.py, combat.py, encounters.py
  items.py, story.py, misc.py, gm.py, gm_templates.py
models/                   # 業務邏輯
  combat.py               # 戰鬥核心（~1100 行）
  encounter_outcomes.py   # 勝利/失敗獎勵（canonical）
  encounter.py, squad.py, team.py, item.py, settings.py
services/                 # 跨 route 服務
  announcements.py, global_events.py, session_auth.py, ...
utils/
  db_tx.py, qr.py, uploads.py, helpers.py, deploy.py, app_state.py
data/                     # 靜態配置
  locations.py, story_config.py, narrative_stories.py
encounters/*.json         # encounter 定義
deploy/pa-update.sh       # PA 標準部署
scripts/test_combat_flow.py # 戰鬥 smoke test（17 項）
GEMINI_REVIEW.md          # 外部 code review 指引
```

**重要**：戰鬥 UI 喺 `templates/index.html`，**唔係** `app.py` 內嵌 HTML。用 `grep` 搵符號，唔好靠舊 handoff 行號。

---

## 用戶期望（重要）

1. **Agent 要自己執行** — 改 code、跑測試、`git commit`、`git push`、更新 PA；唔好淨係出 instruction。
2. **每次有 code 改動都要同步三處** — local → GitHub → PythonAnywhere；用 `/api/version` 驗證。
3. **Agent 通常無法 SSH 上 PA** — 若 `ssh takjai@ssh.pythonanywhere.com` 失敗，請用戶在 PA Bash 跑 `deploy/pa-update.sh` + Web Reload，然後你再 `curl` 確認。
4. **唔好亂改無關檔案** — `encounters/*.json` 係 encounter 定義；改架構前先 grep 確認檔案位置。
5. **唔好 commit `*.db`** — 已在 `.gitignore`。

---

## 本輪已完成（至 `fc53d73`）

### 架構重構

| 變更 | 說明 |
|------|------|
| **Routes blueprints** | 所有 HTTP route 拆去 `routes/` |
| **Models 層** | 戰鬥、隊伍、物品等邏輯去 `models/` |
| **Templates** | 玩家 UI 搬去 `templates/index.html` |
| **Services** | announcements、global_events、session_auth 等 |

### 安全與可靠性

| 項目 | 實作 |
|------|------|
| **伺服器擲骰** | `roll_combat_dice()` in `routes/combat.py`；客戶端 `dice_result` 被忽略 |
| **戰鬥 race** | `combat_actions` table + `upsert_combat_action()` |
| **GM PIN / QR** | `GM_PIN` env；`utils/qr.py` HMAC signed QR |
| **上傳安全** | PIL verify、8MB cap、`utils/uploads.py` |
| **Path traversal** | `secure_filename` + realpath in `utils/helpers.py` |
| **DB 事務** | `utils/db_tx.py` `immediate_transaction()`（BEGIN IMMEDIATE） |
| **多 worker 公告** | `services/announcements.py` 讀 `global_events` table（唔再 in-memory） |
| **GM UX** | `alert()`/`prompt()` → `showGmToast`/`showGmInputModal` in `gm_templates.py` |
| **玩家 UX** | `showToast`/`showInputModal` in `index.html`（仍有 ~8 處 native `confirm()`） |

### 戰鬥系統（沿用 + 強化）

| 功能 | 說明 |
|------|------|
| **本回合戰況預覽 Modal** | `#combat-action-modal` in `templates/index.html` |
| **`POST /combat/preview_action`** | 伺服器預覽 |
| **統一攻擊** | `max(力量, 智力)` |
| **傷害公式** | `(攻擊×1.5 + 10) × 骰倍率 − 敵韌性×0.8`，最低 1 |
| **玩家卡片** | HP/神智 有比例 + 條；力量/智力/韌性 只顯示數值 |
| **勝利結算** | `models/encounter_outcomes.py`（canonical）；`fc53d73` 移除 combat.py 重複定義 |

### GM 強制結算（已存在）

`gm_templates.py` 有「**強制結算 Phase**」按鈕 → `POST /gm/combat/resolve_phase`。舊 handoff 話「未做」係錯嘅。

### 部署工具

- `deploy/pa-update.sh` — venv、`pip install`、wsgi import smoke test；檢查 `templates/index.html` 含 `combat-action-modal`
- `deploy/pa-check-error.sh` — 診斷 wsgi import + `DB_INIT_ERROR`
- `deploy/pa-diagnose.sh` — git / 路徑問題

---

## Combat API 速查

| 端點 | 用途 |
|------|------|
| `POST /combat/start` | 開始戰鬥 + precheck |
| `GET /combat/status` | 輪詢；`my_state` 含 hp/sanity/power/intellect/resilience/avatar |
| `POST /combat/preview_action` | 本回合戰況預覽 |
| `POST /combat/submit_action` | 提交行動（**骰子由伺服器擲**） |
| `POST /combat/resolve_phase` | 強制結算 player phase |
| `POST /combat/rescue_near_death` | 禱告救援 |
| `POST /gm/combat/resolve_phase` | GM 強制結算 |
| `GET /encounters` | encounter 列表 |
| `GET /api/version` | 部署驗證 |
| `GET /available_portraits` | NPC 頭像 |

### 後端結算核心（`models/combat.py`）

```
傷害：calculate_damage_simple / calculate_damage
骰子倍率：0→0, 1→1.0, 2→1.5, 3→2.0（伺服器 roll_combat_dice）
Zoo：神智 ≥70/80/90/100 → ×1.3/1.4/1.5/1.8
暴走：神智 <10→90%, <20→50%, <40→20%
敵人反擊：攻擊全隊韌性最低者；defend 減傷 50%（只對被反擊目標）
瀕死：HP≤0 → near_death_until +15 分鐘
```

### 前端戰鬥 UI（`templates/index.html`）

- `#combat-screen` / `#player-panel` / `#enemy-panel`
- `combat-hp-value`、`combat-hp-pct`、`updateCombatPlayerStats`、`CAPPED_SQUAD_STATS`
- `setStatBar()` — Dashboard + 戰鬥共用
- 輪詢 ~8 秒

---

## 尚未完成（下一個 Agent 可優先做）

| 優先 | 項目 | 說明 |
|------|------|------|
| **P0** | **部署 PA 至 `fc53d73`** | PA 目前 500；見 Deploy 一節 |
| P1 | 部署後實機驗證 | 戰鬥勝利流程、`/api/version` markers |
| P3 | Defend 全隊 buff | 目前只對「被反擊目標」減傷 50% |
| P4 | 更多 encounter JSON | Marah 線、stage 2+ |
| P5 | 瀕死 background timer | 目前靠 polling + `near_death_until` |
| 中 | `grant_item_to_squad` | item INSERT 有事務，但 `apply_item_effect_to_squad()` 喺 commit 後跑 |
| 中 | 部分 `routes/gm.py` DB ops | 未用 `immediate_transaction()` |
| 中 | `ALLOW_LEGACY_QR=1` 預設 | 玩家 UI 仍有 `confirm()` |
| 低 | Tailwind CDN、大 `index.html`、PA venv path |

---

## Deploy 流程（PythonAnywhere）— Agent 必須執行

### 標準流程（GitHub → PA）

```bash
# 1. 本地：驗證 + commit + push
cd /Users/mingtakyau/Documents/oikonomia
./venv/bin/python3 scripts/test_combat_flow.py   # 預期 17/17
git add -A && git commit -m "描述改動" && git push origin main

# 2. PA Bash console（用戶帳號 takjai）— Agent 無 SSH 時請用戶代跑
FORCE=1 bash ~/oikonomia/deploy/pa-update.sh

# 3. PA Web tab → Reload takjai.pythonanywhere.com

# 4. 驗證（必須與 git rev-parse --short HEAD 相同）
curl -s https://takjai.pythonanywhere.com/api/version | python3 -m json.tool
```

### `/api/version` 預期（`fc53d73`）

```json
{
  "success": true,
  "version": "fc53d73",
  "markers": {
    "combat_system": true,
    "combat_preview": true,
    "combat_modal": true,
    "server_combat_dice": true,
    "combat_actions_table": true,
    "qr_signed_v2": true,
    "task_photo_validation": true,
    "routes_refactored": true,
    "upload_path_hardened": true,
    "input_modal": true,
    "model_combat_layer": true
  }
}
```

`deploy/pa-update.sh` 會檢查 `templates/index.html` 含 `combat-action-modal`，並做 wsgi import smoke test。

### Agent 無法 SSH 時

1. 完成 `git push`
2. 明確請用戶：PA Bash → `FORCE=1 bash ~/oikonomia/deploy/pa-update.sh` → Web Reload
3. 你再 `curl /api/version` 確認 `version` 已更新且 `success: true`

### PA 重要設定

- **WSGI**：import `wsgi.application`
- **Virtualenv**：`~/oikonomia/venv`（deploy script 會建立）
- **Environment**：`SECRET_KEY`（必須）、`GM_PIN`、`DATA_DIR=data`
- **Static files**：**唔好** map `/uploads/`（交俾 Flask route）
- **DB migration**：`init_db()` → `migrate_db()` 自動跑

---

## 本地開發速查

```bash
cd /Users/mingtakyau/Documents/oikonomia
source venv/bin/activate
python3 app.py                    # → :5001
./venv/bin/python3 scripts/test_combat_flow.py
```

| 用途 | 值 |
|------|-----|
| GM PIN | `gm2026`（或 env `GM_PIN`） |
| 重置遊戲 | `reset2026` |
| 清空上傳 | 確認碼 `CLEAR_IMAGES` |
| 測試帳號 | `test_squad_01` |

---

## 關鍵符號速查（用 grep，行號會漂移）

| 檔案 / 符號 | 用途 |
|-------------|------|
| `app.py` → `migrate_db()` | DB schema |
| `models/combat.py` → `resolve_player_phase()` | 戰鬥結算 |
| `models/combat.py` → `build_combat_round_preview()` | 預覽 API |
| `models/encounter_outcomes.py` | 勝利/失敗獎勵（canonical） |
| `routes/combat.py` → `roll_combat_dice()` | 伺服器擲骰 |
| `utils/db_tx.py` → `immediate_transaction()` | BEGIN IMMEDIATE 事務 |
| `templates/index.html` → `updateCombatPlayerStats()` | 戰鬥玩家卡片 UI |

---

## 近期 commit（參考）

```
fc53d73 fix: combat victory crash + stable smoke test + PA deploy checks
5d195c6 fix: BEGIN IMMEDIATE transactions + upload secure_filename
92b4cbb fix: persist announcements to DB for multi-worker safety
6120373 docs: add GEMINI_REVIEW.md instructions for external code review
54eb415 fix: Gemini review items 1-4 (transactions, routes, GM UX, upload security)
38982bc Refactor: extract full combat layer to models/combat.py
47edc3d Security: PIL-validated task photo uploads (8MB cap)
```

---

## 新 Tab 開場白（複製貼上）

```
請讀 @AGENT_HANDOFF.md，繼續開發 Oikonomia（/Users/mingtakyau/Documents/oikonomia）。

你的責任：
1. 自己執行（改 code、測試、commit、push），唔好只出 instruction
2. 確保 GitHub 同 PythonAnywhere 版本同 local 一致

開工前先核對版本：
- local: git rev-parse --short HEAD（應為 fc53d73）
- PA: curl https://takjai.pythonanywhere.com/api/version

PA 若 500 或 version 落後：請我跑 FORCE=1 bash ~/oikonomia/deploy/pa-update.sh + Web Reload，你再 curl 確認。

然後做我指定嘅任務：[在這裡寫你的任務]
```

若不確定下一個任務，可先：

```
…然後做 P0：部署 PA 至 fc53d73，curl 確認 /api/version，再跑戰鬥勝利實機測試。
```