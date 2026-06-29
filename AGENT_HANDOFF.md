# Oikonomia — Grok Build Handoff（新 Tab 必讀）

> **本檔給 Grok Build**（實作 Agent）。用戶會開新 tab 繼續開發；請**直接執行**，唔好只係話用戶點做。  
> **你的責任**：改 code → 驗證 → commit/push GitHub → **確保 PythonAnywhere 同 local 版本一致**（見 Deploy 一節）。  
> 最後更新：2026-06-29 · local/GitHub：`56fc2bf` · PA：`0c43e04`（待 deploy）

| 角色 | 文檔 | 職責 |
|------|------|------|
| **Grok** | `README.md` | 方向、優先級、架構取捨（唔改 repo） |
| **Grok Build（你）** | **本文** | 實作、測試、push、備份、部署 |
| **Gemini** | `GEMINI_REVIEW.md` | 第三方 review / debug（唔改 repo） |

**本檔副本**：`Documents/oikonomia/AGENT_HANDOFF.md` 與 Google Drive `My Drive/oikonomia/AGENT_HANDOFF.md` 應保持同步。

---

## 版本狀態（開 tab 第一件事要核對）

| 環境 | Commit | 狀態 |
|------|--------|------|
| **Local** | `56fc2bf` | ✅ |
| **GitHub `main`** | `56fc2bf` | ✅ |
| **PythonAnywhere** | `0c43e04` | ⏳ 待 deploy |

```bash
# 本地
cd /Users/mingtakyau/Documents/oikonomia && git rev-parse --short HEAD

# 遠端（應回 JSON；若見 "Something went wrong" 即 PA 未修好）
curl -s https://takjai.pythonanywhere.com/api/version | python3 -m json.tool
```

兩邊 `version` 必須相同才算部署完成。

### 本地測試

```bash
./venv/bin/python3 scripts/test_combat_flow.py           # 預期：93 通過 / 0 失敗
./venv/bin/python3 scripts/test_encounter_cache.py       # 預期：3 通過 / 0 失敗
./venv/bin/python3 scripts/test_combat_concurrency.py    # 併發結算 smoke test（需 venv）
```

---

## 專案概覽

| 項目 | 值 |
|------|-----|
| 專案路徑 | `/Users/mingtakyau/Documents/oikonomia` |
| Google Drive 備份 | `~/Library/CloudStorage/GoogleDrive-ymtwill@gmail.com/My Drive/oikonomia` |
| 主檔 | `app.py`（~980 行：Flask init、DB migrate、`register_blueprints`） |
| 玩家 UI | `templates/index.html`（~6200 行 JS/HTML） |
| 主角狀態 | `models/protagonist.py` + `protagonist_states` 表 |
| 資料庫 | `oikonomia.db`（本地）；PA 上在 `data/oikonomia.db` |
| GitHub | https://github.com/Takjai18/oikonomia |
| 正式環境 | https://takjai.pythonanywhere.com |
| GM 後台 | https://takjai.pythonanywhere.com/gm （PIN: `gm2026` 或 env `GM_PIN`；session 8 小時過期） |
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
  combat.py               # 戰鬥核心（~1450 行；含 phase resolve 鎖）
  protagonist.py          # 主角 HP/trauma/參戰/結局
  encounter_outcomes.py   # 勝利/失敗獎勵 + encounter logs（canonical）
  encounter.py, squad.py, team.py, item.py, settings.py
services/                 # 跨 route 服務
  announcements.py, global_events.py, session_auth.py
  gm_auth.py              # GM session 8h 過期驗證
  story.py, teams_overview.py, ...
utils/
  db_tx.py                # immediate_transaction() + with_db_retry()
  qr.py, uploads.py, helpers.py, deploy.py, app_state.py
data/                     # 靜態配置
  locations.py, story_config.py, narrative_stories.py
encounters/*.json         # encounter 定義（生產：enc_iggy_01/02、enc_marah_01 + test_*）
deploy/pa-update.sh       # PA 標準部署
scripts/test_combat_flow.py           # 戰鬥 smoke test（66 項）
scripts/test_encounter_cache.py
scripts/test_combat_concurrency.py    # 併發 submit/resolve smoke test
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

## 本輪已完成（2026-06-29 最新）

### P4 生產 Encounter JSON（本輪）

| 檔案 | 路線 | Stage | 說明 |
|------|------|-------|------|
| `enc_iggy_02_boundary.json` | Iggy | 2 | 界線崩壞／共生寄生；precheck 韌性≥45 或裂縫碎片 |
| `enc_marah_01_whisper.json` | Marah | 1 | 深淵低語；precheck 智力≥50 或記憶之瓶 |

- `scripts/test_combat_flow.py` → `test_encounter_catalog()` 驗證生產 encounter 載入

### Gemini Review 安全修復（`3cdb207`）

| 項目 | 說明 |
|------|------|
| **戰鬥 double-resolve 鎖** | `resolve_player_phase()` 原子 `player_phase → resolving`；失敗回滾；45s stale 恢復 |
| **DB locked retry** | `utils/db_tx.py` → `with_db_retry()`；`upsert_combat_action` 使用 |
| **QR claim 事務** | `grant_item_to_squad()` 全部檢查 + INSERT 喺 `immediate_transaction` 內 |
| **Legacy QR 關閉** | production 預設 `ALLOW_LEGACY_QR=0`（`utils/qr.py`） |
| **Route SSOT** | `official_squad_route()`；`get_squad` / `get_all_squads` / 戰鬥參與者以 `teams.route` 為準 |
| **瀕死狀態** | 瀕死期間禁止道具補血；HP→0 先設 `near_death_until`；HP≤0 唔攻擊/暴走 |
| **GM auth** | `services/gm_auth.py`：PIN 登入後 **8 小時** session 過期 |
| **GM dashboard N+1** | submission count 改 bulk `GROUP BY` |
| **Story views** | `GET /api/story/views`；登入後 server 資料同步覆蓋 localStorage |
| **併發測試** | `scripts/test_combat_concurrency.py` |

### GM 調整 stat 被壓返 100（`6f81430`）

| 問題 | 根因 | 修正 |
|------|------|------|
| Rice 力量 3000 → 100 | 全營事件 `MIN(100, power+?)` 壓死 GM 值 | `clamped_stat_delta_expr()`：>100 唔再 cap；已套用到 `global_events.py` + `item.py` |

### Encounter 日誌（`da1f6e6`）

| 項目 | 說明 |
|------|------|
| **API** | `GET /encounter_logs` — 隊伍 encounter 結果 + 獎勵記錄 |
| **後端** | `models/encounter_outcomes.py` → `get_team_encounter_logs()` |
| **UI** | `templates/index.html` → encounter logs 列表 |
| **marker** | `encounter_logs` |

### 主角參戰 + Trauma 陰影結局（`c4713d6`–`f6c9701`）

| 項目 | 說明 |
|------|------|
| **`protagonist_states` 表** | HP / sanity / trauma 跨戰鬥持久化 |
| **普通戰鬥** | 主角自動 AI 參戰 |
| **瀕死** | +1 trauma；累計 **>3** → `bad_ending` 鎖定 |
| **戰鬥勝利** | trauma 過深時無獎勵、陰影 narrative、`teams.ending_type` |
| **API** | `/status`、`/team` 回傳 `ending`；`/api/version` → `trauma_ending` |

### Phase 5 玩家控制主角 + UI（`b6b91c3`）

| 項目 | 說明 |
|------|------|
| **觸發** | `story_stage >= 3` 或 encounter `combat_settings.protagonist_player_control: true` |
| **API** | `POST /combat/submit_action` 加 `as_protagonist: true`；`preview_action` 同步支援 |
| **UI** | `#protagonist-control-bar` 切換；主角模式顯示主角數值、禁用物品 |
| **提交規則** | `as_protagonist` 代替自己一個回合；否則主角結算時自動 AI fallback |
| **測試** | `encounters/test_protagonist_control.json` + `test_protagonist_player_control()` |

### 玩家 `confirm()` → 自訂 Modal（`b6b91c3`）

- `showConfirmModal()` + `#confirm-modal-overlay`；`index.html` **0** 個 native `confirm()`
- marker：`confirm_modal`

### Encounter cache mtime（`4971fc9`）

- `load_encounter()` 檔案改動自動失效；`SKIP_ENCOUNTER_CACHE=1` 強制讀碟

### 早前：戰鬥結算免 reload（`187afca`）、Defend 全隊 buff（`dba1548`）、`player_max_hp`

---

## 早前已完成（至 `fc53d73`）

### 架構重構

| 變更 | 說明 |
|------|------|
| **Routes blueprints** | 所有 HTTP route 拆去 `routes/` |
| **Models 層** | 戰鬥、隊伍、物品等邏輯去 `models/` |
| **Templates** | 玩家 UI 搬去 `templates/index.html` |
| **Services** | announcements、global_events、session_auth 等 |

### 安全與可靠性（累積）

| 項目 | 實作 |
|------|------|
| **伺服器擲骰** | `roll_combat_dice()` in `routes/combat.py`；客戶端 `dice_result` 被忽略 |
| **戰鬥 race** | `combat_actions` UNIQUE + `upsert_combat_action()` + **`resolve` 原子鎖（`3cdb207`）** |
| **GM PIN / QR** | `GM_PIN` env；`utils/qr.py` HMAC signed QR；**production 禁 legacy QR** |
| **QR 一次性** | `qr_code_uses` 表（`item_id UNIQUE`）+ 同隊重複檢查 |
| **上傳安全** | PIL verify、8MB cap；server 生成檔名（`utils/uploads.py`） |
| **Path traversal** | `secure_filename` + realpath in `utils/helpers.py` |
| **DB 事務** | `utils/db_tx.py` `immediate_transaction()` + `with_db_retry()` |
| **多 worker 公告** | `services/announcements.py` 讀 `global_events` table |
| **GM UX** | `showGmToast`/`showGmInputModal`；**8h session 過期（`gm_auth.py`）** |
| **玩家 UX** | `showToast`/`showInputModal`/`showConfirmModal`（無 native dialog） |
| **SQL 安全** | 動態 SQL 只用 whitelist column；user input 一律 parameterized |

### 戰鬥系統（沿用 + 強化）

| 功能 | 說明 |
|------|------|
| **本回合戰況預覽 Modal** | `#combat-action-modal` in `templates/index.html` |
| **`POST /combat/preview_action`** | 伺服器預覽 |
| **統一攻擊** | `max(力量, 智力)` |
| **傷害公式** | `(攻擊×1.5 + 10) × 骰倍率 − 敵韌性×0.8`，最低 1 |
| **玩家卡片** | HP/神智 有比例 + 條；力量/智力/韌性 只顯示數值 |
| **勝利結算** | `models/encounter_outcomes.py`（canonical） |

### GM 強制結算（已存在）

`gm_templates.py` 有「**強制結算 Phase**」按鈕 → `POST /gm/combat/resolve_phase`。結算中（`resolving`）會回 409。

### 部署工具

- `deploy/pa-update.sh` — venv、`pip install`、wsgi import smoke test
- `deploy/pa-check-error.sh` — 診斷 wsgi import + `DB_INIT_ERROR`
- `deploy/pa-diagnose.sh` — git / 路徑問題
- `deploy/pa-ensure-secret.sh` — `data/.secret_key` for Web worker

---

## Combat API 速查

| 端點 | 用途 |
|------|------|
| `POST /combat/start` | 開始戰鬥 + precheck |
| `GET /combat/status` | 輪詢；`my_state` 含 hp/sanity/power/intellect/resilience/avatar |
| `POST /combat/preview_action` | 本回合戰況預覽 |
| `POST /combat/submit_action` | 提交行動（**骰子由伺服器擲**）；`as_protagonist: true` 代替主角；結算中回 409 |
| `POST /combat/resolve_phase` | 強制結算 player phase |
| `POST /combat/rescue_near_death` | 禱告救援 |
| `POST /gm/combat/resolve_phase` | GM 強制結算 |
| `GET /encounters` | encounter 列表 |
| `GET /encounter_logs` | 隊伍 encounter 結果日誌 |
| `GET /api/version` | 部署驗證 |
| `GET /api/story/views` | 已讀劇情 ID 列表（server authoritative） |
| `GET /available_portraits` | NPC 頭像 |

### 後端結算核心（`models/combat.py`）

```
resolve 鎖：player_phase → resolving（BEGIN IMMEDIATE）→ 結算 → enemy_phase/ended
傷害：calculate_damage_simple / calculate_damage
骰子倍率：0→0, 1→1.0, 2→1.5, 3→2.0（伺服器 roll_combat_dice）
Zoo：神智 ≥70/80/90/100 → ×1.3/1.4/1.5/1.8
暴走：神智 <10→90%, <20→50%, <40→20%（HP≤0 唔觸發）
敵人反擊：攻擊全隊韌性最低者；任一同隊 Defend → 反擊傷害減半
瀕死：HP≤0 → near_death_until +15 分鐘；瀕死期間禁止道具補血
GM stat：>100 唔被全營事件/item cap 壓返 100
```

### 前端戰鬥 UI（`templates/index.html`）

- `#combat-screen` / `#player-panel` / `#enemy-panel`
- `combat-hp-value`、`combat-hp-pct`、`updateCombatPlayerStats`、`CAPPED_SQUAD_STATS`
- `setStatBar()` — Dashboard + 戰鬥共用
- 輪詢 ~8 秒

---

## 尚未完成（用戶刻意延後 — 等劇情／任務設計好先做）

| 優先 | 項目 | 說明 |
|------|------|------|
| **內容** | Salvio 最終 Boss encounter | 用戶未寫好劇情 |
| **內容** | Marah 線 / 各 Stage 任務 + encounter | 同上 |
| **內容** | Good Ending 完整演出 | 只得 `bad_ending` 鎖定；正面結局 narrative 待寫 |
| **系統** | 主角瀕死禱告救援 | 用戶未設定好祈禱規則；現只支援玩家 squad |
| **系統** | 祈禱系統整體 | 延後 |

## 技術債（非阻營會，有空再做）

| 項目 | 說明 |
|------|------|
| 刪除 `squads.route` 欄位 | 讀取層已 SSOT（`official_squad_route`）；DB 欄位可之後 migration 移除 |
| 瀕死 background timer | 靠 polling + `near_death_until` |
| `apply_item_effect_to_squad()` | 仍喺 `grant_item` commit 後獨立連線（低風險） |
| 部分 `routes/gm.py` DB ops | 未統一 `immediate_transaction()` |
| `gm_users` table | 營會規模用 PIN + 8h session 已夠；可之後加 |
| Tailwind CDN、大 `index.html` | 可之後拆 JS/CSS |
| 20 人 full load test | 有 `test_combat_concurrency.py`；可擴展為 HTTP 層壓測 |

---

## Deploy 流程（PythonAnywhere）— Agent 必須執行

### 標準流程（GitHub → PA）

```bash
# 1. 本地：驗證 + commit + push
cd /Users/mingtakyau/Documents/oikonomia
./venv/bin/python3 scripts/test_combat_flow.py   # 預期 66/66
git add -A && git commit -m "描述改動" && git push origin main

# 2. PA Bash console（用戶帳號 takjai）— Agent 無 SSH 時請用戶代跑
FORCE=1 bash ~/oikonomia/deploy/pa-update.sh

# 3. PA Web tab → Reload takjai.pythonanywhere.com

# 4. 驗證（必須與 git rev-parse --short HEAD 相同）
curl -s https://takjai.pythonanywhere.com/api/version | python3 -m json.tool
```

### `/api/version` 重要 markers

`combat_system`, `server_combat_dice`, `defend_team_buff`, `combat_round_continue`, `player_max_hp`, `protagonist_combat`, `trauma_ending`, `confirm_modal`, `protagonist_player_control`, `upload_path_hardened`, `encounter_logs`, `qr_signed_v2`

Reload Web worker 後 markers 先會更新（`version` 可能已新但 markers 仍舊）。

`deploy/pa-update.sh` 會檢查 `templates/index.html` 含 `combat-action-modal`，並做 wsgi import smoke test。

### Agent 無法 SSH 時

1. 完成 `git push`
2. 明確請用戶：PA Bash → `FORCE=1 bash ~/oikonomia/deploy/pa-update.sh` → Web Reload
3. 你再 `curl /api/version` 確認 `version` 已更新且 `success: true`

### PA 重要設定

- **WSGI 檔案**（Web tab → WSGI configuration）必須係：
  ```python
  import sys
  sys.path.insert(0, '/home/takjai/oikonomia')
  from wsgi import application
  ```
  **唔好用** `from app import app as application`（會跳過 `wsgi.py` 嘅 `DATA_DIR` 設定，且可能用錯 Python）
- **Virtualenv**：`~/oikonomia/venv`（**必須**設喺 Web tab；否則 `ModuleNotFoundError: No module named 'PIL'`）
- **Environment**：`SECRET_KEY`（必須）、`GM_PIN`、`DATA_DIR=data`
- **Static files**：**唔好** map `/uploads/`（交俾 Flask route）
- **DB migration**：`init_db()` → `migrate_db()` 自動跑

### PA 常見錯誤（2026-06-29 實例）

| 錯誤 | 原因 | 修法 |
|------|------|------|
| `No module named 'PIL'` | Web tab 未指向 venv | 跑 `pa-update.sh` → Web tab Virtualenv = `~/oikonomia/venv` → Reload |
| `SECRET_KEY ... required` | Web tab 未設 env | Web tab → Environment variables → 加 `SECRET_KEY` |
| WSGI import `from app import app` | 舊 WSGI 設定 | 改為 `from wsgi import application`（見上） |

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
| GM session | 登入後 8 小時過期（`services/gm_auth.py`） |
| 重置遊戲 | `reset2026` |
| 清空上傳 | 確認碼 `CLEAR_IMAGES` |
| 測試帳號 | `test_squad_01` |

---

## 關鍵符號速查（用 grep，行號會漂移）

| 檔案 / 符號 | 用途 |
|-------------|------|
| `app.py` → `migrate_db()` | DB schema |
| `models/combat.py` → `resolve_player_phase()` | 戰鬥結算（含 resolving 鎖） |
| `models/combat.py` → `build_combat_round_preview()` | 預覽 API |
| `models/encounter_outcomes.py` | 勝利/失敗獎勵 + encounter logs |
| `models/team.py` → `official_squad_route()` | Route SSOT |
| `services/global_events.py` → `apply_global_effect()` | 全營事件（GM stat >100 唔 cap） |
| `services/gm_auth.py` → `gm_session_valid()` | GM 8h session |
| `routes/combat.py` → `roll_combat_dice()` | 伺服器擲骰 |
| `utils/db_tx.py` → `immediate_transaction()` | BEGIN IMMEDIATE 事務 |
| `utils/helpers.py` → `clamped_stat_delta_expr()` | GM-boosted stat cap 邏輯 |
| `templates/index.html` → `updateCombatPlayerStats()` | 戰鬥玩家卡片 UI |
| `templates/index.html` → `syncStoryViewsFromServer()` | 劇情已讀 server 同步 |

---

## 近期 commit（參考）

```
3cdb207 fix(security): address Gemini review — combat locks, QR, GM auth
6f81430 fix(stats): preserve GM-boosted values above 100 cap
da1f6e6 feat(log): record encounter outcomes and rewards in journal
b6b91c3 feat(ui): confirm modal + Phase 5 protagonist player control
4971fc9 fix(encounter): invalidate JSON cache on file mtime change
f6c9701 feat(ending): Phase 4 trauma bad ending judgment and UI
dba1548 feat(combat): Defend grants team-wide counter-attack damage reduction
fc53d73 fix: combat victory crash + stable smoke test + PA deploy checks
```

---

## 新 Tab 開場白（複製貼上）

```
請讀 @AGENT_HANDOFF.md，繼續開發 Oikonomia（/Users/mingtakyau/Documents/oikonomia）。

你的責任：
1. 自己執行（改 code、測試、commit、push），唔好只出 instruction
2. 確保 GitHub 同 PythonAnywhere 版本同 local 一致

開工前先核對版本：
- local: git rev-parse --short HEAD（應為 4c14e8d）
- PA: curl https://takjai.pythonanywhere.com/api/version

PA 若 500 或 version 落後：請我跑 FORCE=1 bash ~/oikonomia/deploy/pa-update.sh + Web Reload，你再 curl 確認。

然後做我指定嘅任務：[在這裡寫你的任務]
```

若不確定下一個任務，可先：

```
…然後做 P0：curl 確認 /api/version 為 3cdb207，跑 test_combat_flow.py（66/66），再實機測試全營事件唔會壓 GM stat。
```