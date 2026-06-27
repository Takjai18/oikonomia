# Oikonomia — Agent Handoff（新 Tab 必讀）

> **給下一個 AI Agent**：用戶會開新 tab 繼續開發。請**直接執行**，唔好只係話用戶點做。  
> **你的責任**：改 code → 驗證 → commit/push GitHub → **確保 PythonAnywhere 同 local 版本一致**（見 Deploy 一節）。  
> 最後更新：2026-06-28 · local/GitHub：`5e47b52`（功能 commit `3e84702`）

---

## 版本狀態（開 tab 第一件事要核對）

| 環境 | Commit | 狀態 |
|------|--------|------|
| **Local** | `5e47b52` | ✅ 最新 |
| **GitHub `main`** | `5e47b52` | ✅ 已 push |
| **PythonAnywhere** | `3e84702` | ⚠️ **落後 2 commits**（docs only）— 需部署令 version 一致 |

```bash
# 本地
cd /Users/mingtakyau/Documents/oikonomia && git rev-parse --short HEAD

# 遠端
curl -s https://takjai.pythonanywhere.com/api/version | python3 -m json.tool
```

兩邊 `version` 必須相同才算部署完成。PA 已含 `3e84702` 戰鬥玩家卡片功能；落後嘅 `a70e07a` / `5e47b52` 僅 AGENT_HANDOFF 文檔更新。

### P1 實機驗證（2026-06-28，`test_squad_01` @ PA `3e84702`）

- HTML 含 `combat-hp-value` / `combat-hp-pct` / `updateCombatPlayerStats` / `CAPPED_SQUAD_STATS` 等標記 ✅
- `enc_iggy_01_leech` → precheck → `confirm: fight` → `player_phase` ✅
- `my_state`：`HP 100/100 (100%)`、`神智 50/100 (50%)`、`力量/智力/韌性 100`（純數值）✅

---

## 專案概覽

| 項目 | 值 |
|------|-----|
| 專案路徑 | `/Users/mingtakyau/Documents/oikonomia` |
| 主檔 | `app.py`（單體 Flask + 內嵌 HTML/JS，~9900 行） |
| 資料庫 | `oikonomia.db`（本地）；PA 上在 `data/oikonomia.db` |
| GitHub | https://github.com/Takjai18/oikonomia |
| 正式環境 | https://takjai.pythonanywhere.com |
| GM 後台 | https://takjai.pythonanywhere.com/gm （PIN: `gm2026`） |
| 本地開發 | `source venv/bin/activate && python3 app.py` → http://localhost:5001 |
| 測試帳號 | `test_squad_01`（開發／實機測試用） |

**主題**：Summer Camp 2026 ARG（Oikonomia 青年營會），Iggy / Marah 雙主角路線。

---

## 用戶期望（重要）

1. **Agent 要自己執行** — 改 code、跑測試、`git commit`、`git push`、更新 PA；唔好淨係出 instruction。
2. **每次有 code 改動都要同步三處** — local → GitHub → PythonAnywhere；用 `/api/version` 驗證。
3. **Agent 通常無法 SSH 上 PA** — 若 `ssh takjai@ssh.pythonanywhere.com` 失敗，請用戶在 PA Bash 跑 `deploy/pa-update.sh` + Web Reload，然後你再 `curl` 確認。
4. **唔好亂改無關檔案** — `app.py` 係核心；`encounters/*.json` 係 encounter 定義。
5. **唔好 commit `*.db`** — 已在 `.gitignore`。

---

## 本輪已完成（至 `3e84702`）

### 戰鬥系統

| 功能 | 說明 |
|------|------|
| **本回合戰況預覽 Modal** | `#combat-action-modal` 放喺 body；擲骰 → 停留 → 預覽 → 確認 |
| **擲骰節奏** | 14 格 × 75ms；結果停留 1.4s（爆擊 1.8s） |
| **`POST /combat/preview_action`** | 伺服器預覽；API 失敗時前端 `buildClientPreviewFallback()` |
| **統一攻擊** | `max(力量, 智力)`；單一「攻擊」按鈕 |
| **傷害公式（現行）** | `(攻擊×1.5 + 10) × 骰倍率 − 敵韌性×0.8`，最低 1 |
| **玩家頭像** | 戰鬥讀 `my_state.avatar`；`updateCombatPlayerAvatar()` |
| **戰鬥玩家卡片數值** | HP/神智：`目前/100 (n%)` + 進度條；力量/智力/韌性：只顯示數值 |

### Dashboard 玩家狀態卡片（`722f81d`）

- 同戰鬥規則：HP/神智 有比例 + 條；力量/智力/韌性 只顯示數值
- `setStatBar()` + `CAPPED_SQUAD_STATS`（`hp`, `sanity`）
- `updateDashboardAttackHint()` 顯示攻擊力來源

### 靜態資源

| 目錄 | 用途 |
|------|------|
| `static/avatars/` | **玩家**可選頭像 |
| `static/portraits/` | **NPC／敵人**頭像（6 張 archetype） |
| `GET /available_portraits` | NPC 頭像列表 API |

### 部署工具

- `deploy/pa-update.sh` — 標準更新（`FORCE=1` 強制 reset）
- `deploy/pa-diagnose.sh` — 診斷 git / 路徑問題

### 後端（沿用）

- **中文屬性**：生命值、神智、力量、智力、韌性
- **Encounter**：`encounters/enc_iggy_01_leech.json` 等
- **DB**：`combats`、`encounter_completions`；`squads` 有 `trauma_*`、`near_death_until`、`current_combat_id` 等
- **`migrate_db()`** — PA reload 後第一次 request 自動跑

---

## Combat API 速查

| 端點 | 用途 |
|------|------|
| `POST /combat/start` | 開始戰鬥 + precheck |
| `GET /combat/status` | 輪詢；`my_state` 含 hp/sanity/power/intellect/resilience/avatar |
| `POST /combat/preview_action` | 本回合戰況預覽（擲骰後） |
| `POST /combat/submit_action` | 提交行動 + 骰子 0–3 |
| `POST /combat/resolve_phase` | 強制結算 player phase |
| `POST /combat/rescue_near_death` | 禱告救援（縮短瀕死 5 分鐘） |
| `POST /encounters/<id>/start` | alias → `/combat/start` |
| `GET /encounters` | encounter 列表 |
| `GET /api/version` | 部署驗證（見下） |
| `GET /available_portraits` | NPC 頭像 |

### `resolve_player_phase` 核心（後端結算）

```
傷害：見 calculate_damage_simple / calculate_damage
骰子倍率：0→0, 1→1.0, 2→1.5, 3→2.0
Zoo：神智 ≥70/80/90/100 → ×1.3/1.4/1.5/1.8
暴走：神智 <10→90%, <20→50%, <40→20%
敵人反擊：攻擊全隊韌性最低者；defend 減傷 50%
瀕死：HP≤0 → near_death_until +15 分鐘
```

### 前端戰鬥 UI 重點（`app.py` HTML_TEMPLATE 內）

- `#combat-screen` / `#player-panel` / `#enemy-panel`
- 玩家屬性 element：`combat-hp-value`、`combat-hp-pct`、`combat-hp-bar` 等（`combat-` 前綴）
- `updateCombatPlayerStats(me, squad)` — 戰鬥玩家卡片更新
- `setStatBar(prefix, stat, value, { showRatio })` — Dashboard + 戰鬥共用
- 輪詢 ~8 秒；Iggy 酒紅 / Marah 海軍藍 accent

---

## 尚未完成（下一個 Agent 可優先做）

| 優先 | 項目 | 說明 |
|------|------|------|
| **P0** | **部署 PA 至 `5e47b52`** | 見下方；`curl /api/version` 必須同 local |
| ~~P1~~ | ~~實機測試 combat~~ | ✅ 2026-06-28 已驗證（見版本狀態一節） |
| P2 | GM 強制結算按鈕 | `/combat/resolve_phase` 已有 API，GM UI 未做 |
| P3 | Defend 全隊 buff | 目前只對「被反擊目標」減傷 50% |
| P4 | 更多 encounter JSON | Marah 線、stage 2+ |
| P5 | 瀕死 background timer | 目前靠 polling + `near_death_until` |

---

## Deploy 流程（PythonAnywhere）— Agent 必須執行

### 標準流程（GitHub → PA）

```bash
# 1. 本地：驗證 + commit + push
cd /Users/mingtakyau/Documents/oikonomia
./venv/bin/python3 -m py_compile app.py
# 有 venv 時可跑：./venv/bin/python3 scripts/test_combat_flow.py
git add -A && git commit -m "描述改動" && git push origin main

# 2. PA Bash console（用戶帳號 takjai）— Agent 無 SSH 時請用戶代跑
bash ~/oikonomia/deploy/pa-update.sh
# 若 pull 失敗：
# FORCE=1 bash ~/oikonomia/deploy/pa-update.sh

# 3. PA Web tab → Reload takjai.pythonanywhere.com

# 4. 驗證（必須與 git rev-parse --short HEAD 相同）
curl -s https://takjai.pythonanywhere.com/api/version
```

### `/api/version` 預期（`3e84702` 起）

```json
{
  "success": true,
  "version": "3e84702",
  "markers": {
    "combat_system": true,
    "combat_preview": true,
    "combat_modal": true,
    "show_only_protagonist": true
  },
  "avatar_count": 6,
  "portrait_count": 6
}
```

`deploy/pa-update.sh` 會檢查 `combat-action-modal` 是否存在。

### Agent 無法 SSH 時

1. 完成 `git push`
2. 明確請用戶：PA Bash → `bash ~/oikonomia/deploy/pa-update.sh` → Web Reload
3. 你再 `curl /api/version` 確認 `version` 已更新

### PA 重要設定

- **WSGI**：import `wsgi.application`
- **Static files**：**唔好** map `/uploads/`（交俾 Flask route）
- **DATA_DIR**：`wsgi.py` 設為 `~/oikonomia/data`
- **DB migration**：`init_db()` → `migrate_db()` 自動跑

---

## 本地開發速查

```bash
cd /Users/mingtakyau/Documents/oikonomia
source venv/bin/activate
python3 app.py                    # → :5001
./venv/bin/python3 -m py_compile app.py
./venv/bin/python3 scripts/test_combat_flow.py   # 需 venv + flask
```

| 用途 | 值 |
|------|-----|
| GM PIN | `gm2026` |
| 重置遊戲 | `reset2026` |
| 清空上傳 | 確認碼 `CLEAR_IMAGES` |
| 測試帳號 | `test_squad_01` |

---

## 關鍵檔案地圖

```
oikonomia/
├── app.py                          # 全部邏輯 + UI
├── wsgi.py                         # PA 入口
├── deploy/pa-update.sh             # PA 更新腳本
├── deploy/pa-diagnose.sh           # PA 診斷
├── scripts/test_combat_flow.py     # 戰鬥流程測試
├── encounters/enc_iggy_01_leech.json
├── static/avatars/                 # 玩家頭像
├── static/portraits/               # NPC 頭像
├── static/images/items/*.svg
├── requirements.txt
└── AGENT_HANDOFF.md                # 本檔（新 tab 必讀）
```

### `app.py` 重要符號（行號會漂移，用 grep）

| 符數 / 函數 | 用途 |
|-------------|------|
| `init_db()` / `migrate_db()` | DB schema |
| `resolve_player_phase()` | 戰鬥結算 |
| `build_combat_round_preview()` | 預覽 API |
| `calculate_damage_simple()` | 現行傷害公式 |
| `build_combat_status_response()` | 輪詢 payload（含 `my_state`） |
| `setStatBar()` / `updateCombatPlayerStats()` | Dashboard + 戰鬥屬性 UI |
| `load_encounter()` | 讀 `encounters/*.json` |

---

## 近期 commit（參考）

```
3e84702 戰鬥畫面玩家卡片顯示完整能力數值
722f81d fix(dashboard): 力量/智力/韌性只顯示數值
bb22794 ui(dashboard): 玩家狀態卡片對齊戰鬥畫面風格
99686db feat(combat): 統一攻擊為 max(力量, 智力) 並簡化傷害公式
2c6b07d feat(combat): 戰況預覽改為置中 Modal
```

---

## 新 Tab 開場白（複製貼上）

```
請讀 @AGENT_HANDOFF.md，繼續開發 Oikonomia Flask app（路徑 /Users/mingtakyau/Documents/oikonomia）。

你的責任：
1. 自己執行（改 code、測試、commit、push），唔好只出 instruction
2. 確保 GitHub 同 PythonAnywhere 版本同 local 一致

開工前先核對版本：
- local: git rev-parse --short HEAD（應為 5e47b52）
- PA: curl https://takjai.pythonanywhere.com/api/version（目前可能仍係 3e84702）

若 PA 落後，請 push 後請我喺 PA Bash 跑 deploy/pa-update.sh + Web Reload，你再 curl 確認。

然後做我指定嘅任務：[在這裡寫你的任務]
```

若不確定下一個任務，可先：

```
…然後做 P0：部署 PA 至最新 commit，再 P1 實機測試戰鬥玩家卡片數值顯示。
```