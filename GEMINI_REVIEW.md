# Instructions for Gemini — Oikonomia Code Review

> **用途**：畀 Gemini（或其他外部 Engineer）做 code review 時，請**先讀本文**，再按指引睇檔案。  
> **專案**：Summer Camp 2026 ARG · Flask + SQLite · 玩家 ~20 人 · 營會現場 3 日  
> **最後更新**：2026-06-29 · 架構 commit `54eb415` 起

---

## 1. Review 前必讀（5 分鐘）

| 檔案 | 用途 |
|------|------|
| `README.md` | 專案概覽、本地／PA 網址、測試指令 |
| `AGENT_HANDOFF.md` | 戰鬥公式、API 速查、部署流程、已知待辦 |
| **本文** `GEMINI_REVIEW.md` | Review 範圍、優先級、輸出格式 |

**威脅模型（重要）**：玩家係中學生，會開 DevTools、改 API payload、試 bypass 機制。Security review 要假設 **client 不可信**，唔好只檢查「happy path」。

**語言**：UI／錯誤訊息多為繁體中文；backend docstring 中英混合屬正常。

---

## 2. 建議閱讀順序（由外到內）

唔使由頭讀晒 `templates/index.html`（~5800 行）。按層次睇：

### Layer 0 — 入口與設定
```
wsgi.py                 # PA 入口；DATA_DIR=data/
app.py                  # Flask init、migrate_db、register_blueprints（~940 行）
models/settings.py      # configure_models() 注入的 runtime config
requirements.txt
```

### Layer 1 — HTTP 路由（Blueprint）
```
routes/auth.py          # /login, /set_pin, /allocate_stats, session restore
routes/player.py        # /submit_task, /status, /verify_gps, avatar
routes/team.py          # /team/*, join/create/transfer_leadership
routes/combat.py        # /combat/*（start, status, submit_action, preview…）
routes/encounters.py    # /encounters, legacy /encounters/<id>/start
routes/items.py         # /my_items, /add_item, /claim_qr
routes/story.py         # /story_progress, /api/story/*
routes/misc.py          # /, /api/version, /uploads, /locations
routes/gm.py            # /gm/*（GM 後台 API）
routes/gm_templates.py  # GM HTML + JS（inline templates）
```

### Layer 2 — 業務邏輯
```
models/combat.py        # 戰鬥結算、preview、status（最複雜，~1200 行）
models/squad.py         # squads CRUD、隊員查詢
models/team.py          # teams、join、transfer_leadership（留意 transaction）
models/item.py          # 物品、grant、QR 關聯
models/encounter.py     # encounter JSON 載入
models/encounter_outcomes.py
services/story.py       # 故事階段、任務計數
services/player_status.py
services/session_auth.py
services/teams_overview.py
services/gm_admin.py
```

### Layer 3 — 安全與工具
```
utils/qr.py             # QR HMAC 簽名、resolve_item_from_qr_payload
utils/uploads.py        # PIL 驗證、resize、8MB 上限
utils/helpers.py        # resolve_upload_disk_path（path traversal）
utils/env.py            # is_production_env
```

### Layer 4 — 前端（按需抽查）
```
templates/index.html    # 玩家 Dashboard + 戰鬥 UI + JS（大檔，用 grep 搜函數名）
templates/claim_item.html
encounters/*.json       # 遭遇戰定義（數值平衡，非 security 主戰場）
```

### 快速 grep 起點（前端）
在 `templates/index.html` 搜：`submitAction`, `updateCombatUI`, `showToast`, `fetch('/combat`  
在 `routes/gm_templates.py` 搜：`showGmToast`, `fetch('/gm`

---

## 3. 建議提供俾 Gemini 的檔案包

**最小集（Security / API review）**：
```
app.py, wsgi.py, requirements.txt
routes/*.py（除 __pycache__）
models/*.py
services/*.py
utils/*.py
deploy/pa-update.sh
```

**完整集（含 UI / UX）**：以上 + `templates/index.html`, `templates/claim_item.html`, `routes/gm_templates.py`

**唔使提供**：`*.db`, `uploads/`, `venv/`, `__pycache__/`, `static/avatars/` 二進制

---

## 4. Review 檢查清單（按優先級）

### 🔴 High — 營會前必須無漏洞

| 檢查項 | 睇邊度 | 已修復／現行設計 |
|--------|--------|------------------|
| **Multi-worker 狀態** | `services/announcements.py`, `models/encounter.py` | 遊戲狀態（戰鬥、隊伍、物品、global_events）全在 SQLite；公告已改讀 `global_events` 表（唔再用 in-memory list）。`_encounter_cache` 只 cache 靜態 `encounters/*.json`，各 worker 內容一致，可安全共用 |
| **Client 信任** | `routes/combat.py` `submit_action` | 骰子由 `roll_combat_dice()` 後端產生；client `dice_result` 忽略 |
| **Race condition** | `models/combat.py` `upsert_combat_action` | `combat_actions` 表 + `UNIQUE(combat_id,squad_id,phase)` |
| **GM 認證** | `routes/gm.py` | Production 要 `GM_PIN` env；唔好 hardcode 喺 production |
| **QR 偽造** | `utils/qr.py` | v2 含 HMAC `token`；`ALLOW_LEGACY_QR=1` 時舊 QR 仍可用 |
| **上傳濫用** | `utils/uploads.py`, `app.py` MAX_CONTENT_LENGTH | PIL verify + 8MB + resize；413 handler |
| **Path traversal** | `utils/helpers.py` `resolve_upload_disk_path` | `secure_filename` + URL decode + realpath + 拒絕 `..`（marker: `upload_path_hardened`） |
| **多語句 SQL 一致性** | `models/team.py`, `models/item.py` `grant_item_to_squad`, `services/global_events.py` | transaction + `rollback()`；join 用 `join_squad_to_team()`；轉讓用 `transfer_team_leadership()` |
| **Session / PIN** | `routes/auth.py`, `services/session_auth.py` | 登入、restore token、PIN 驗證 |

### 🟡 Medium — 技術債／架構

| 檢查項 | 說明 |
|--------|------|
| **半重構殘留** | `app.py` 應只剩 init + migrate；新 route 放 `routes/` |
| **Circular import** | `routes/*` 唔好 `from app import ...`；用 `models/` / `services/` |
| **變數遮蔽** | `models/combat.py` 內 `combat_settings` vs `settings`（ModelSettings） |
| **N+1 查詢** | `get_team_members`、GM overview 大量 squad 時 |
| **原生 alert** | 玩家端 `showToast` / `showInputModal`（`templates/index.html`）；GM 用 `showGmToast` / `showGmInputModal`（`gm_templates.py`，0 個 `alert()`） |
| **Render 持久化** | `render.yaml` | 已設 `disk` mount `/data`；Free tier 無 persistent disk，營會正式環境用 PA |
| **Defend 機制** | 目前只對被反擊目標減傷 50%，唔係全隊 buff（已知設計差距） |

### 🟢 Low — 可記錄、唔阻營會

| 檢查項 | 說明 |
|--------|------|
| Tailwind CDN | 原型階段刻意用 CDN；production 可之後 build |
| `templates/index.html` 體積 | 已抽出 `templates/`；進一步可拆 JS/CSS |
| PA 用 `--user` pip | 理想係 venv；見 `deploy/pa-update.sh` |
| Encounter JSON 平衡 | 遊戲設計問題，非 code bug |

---

## 5. 輸出格式（請 Gemini 跟此結構）

用**繁體中文**（可夾英文術語），分三級：

```markdown
## 🔴 High Priority
### [標題]
- **位置**：`path/to/file.py` — `function_name` 或 route
- **問題**：（1–3 句，講清 exploit 場景）
- **建議**：（具體改法或 pseudo-code，唔好只講「要驗證」）

## 🟡 Medium Priority
…

## 🟢 Low Priority / Deployment
…

## ✅ 已確認無問題（Optional）
列出你檢查過且符合現行設計的項目，避免重複報已修復 issue。
```

**避免**：
- 建議「改用 React / 微服務」等大重構（除非用戶明確要求）
- 把 `encounters/*.json` 數值當 security critical
- 忽略營會規模（20 人）而過度設計 infra

---

## 6. 驗證指令（Reviewer 可建議跑）

```bash
cd /path/to/oikonomia
python3 -m py_compile app.py models/*.py routes/*.py services/*.py utils/*.py
./venv/bin/python3 scripts/test_combat_flow.py   # 戰鬥 API 煙霧測試
curl -s http://localhost:5001/api/version | python3 -m json.tool
```

`/api/version` 的 `markers` 可確認部署功能開關，例如：
`server_combat_dice`, `task_photo_validation`, `qr_signed_v2`, `routes_refactored`, `upload_path_hardened`

---

## 7. 已知待辦（Review 時唔重複當新 bug）

見 `AGENT_HANDOFF.md`「尚未完成」一節，例如：
- GM UI 強制結算戰鬥按鈕
- Defend 全隊 buff
- 更多 encounter / Marah 線
- 瀕死 background timer（目前靠 polling）

---

## 8. 給用戶的開場白模板（Copy-paste 畀 Gemini）

```
請讀 @GEMINI_REVIEW.md，然後對 Oikonomia 做 code review。

範圍：[Security only / Full stack / 指定 PR 或 commit]
我已附上檔案：[列出 zip 或 repo path]

請跟 GEMINI_REVIEW.md 第 5 節輸出格式；
High 項要寫清 exploit 場景同具體修復建議。
已修復項目（server dice、combat_actions 表、PIL upload、QR 簽名）請標為 ✅ 或跳過。
```

---

## 9. 聯絡脈絡

| 項目 | 值 |
|------|-----|
| GitHub | https://github.com/Takjai18/oikonomia |
| Production | https://takjai.pythonanywhere.com |
| 本地 | http://localhost:5001 |
| 開發交接 | `AGENT_HANDOFF.md`（給 Cursor / Grok Agent，唔係給 Gemini 必讀） |