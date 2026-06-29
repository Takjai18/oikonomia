# Instructions for Gemini — Oikonomia Review & Debug

> **用途**：畀 **Gemini** 做第三方 Engineer 的 **Code Review** 同 **Debug** 時，請**先讀本文**，再按指引睇檔案。  
> **專案**：Summer Camp 2026 ARG · Flask + SQLite · 玩家 ~20 人 · 營會現場 3 日  
> **最後更新**：2026-06-29 · 現行 docs commit `41b7630`（以 `git rev-parse --short HEAD` 為準）

---

## 0. 你在專案裡的角色

本專案由三個 AI 分工；**Gemini 唔負責寫入 code**，負責獨立把關。

| 角色 | 職責 |
|------|------|
| **Grok** | 方向：需求、優先級、架構取捨、根因假設 |
| **Grok Build** | 實作：改 code、測試、commit/push、備份、部署 |
| **Gemini（你）** | **Review & Debug**：安全、邏輯、併發、邊界情況；輸出可執行修復建議 |

### 建議介入時機

| 時機 | Gemini 做咩 |
|------|----------------|
| Grok Build push 新 commit 後 | Security / full-stack review（跟本文 §4–§5） |
| 用戶報現場 bug | Debug：重現路徑、根因、最小修復建議（交 Grok Build 落地） |
| 營會前 | 最後一輪 High 項清零確認 |

### 交接規則

1. Review 基準 = **`main` 上已 push 的 commit**（用戶提供 hash 或 `git rev-parse --short HEAD`）。
2. 修復由 **Grok Build** 執行；Gemini 只出報告，唔直接改 repo。
3. 方向性改動（例如重構範圍）先經 **Grok** 同用戶確認，再交 Grok Build。
4. 已修復項對照本文 §9、§10，**唔好重複報**。

```
Grok（方向） → Grok Build（實作） → Gemini（review / debug） → Grok Build（修復）
```

---

## 1. Review 前必讀（5 分鐘）

| 檔案 | 用途 |
|------|------|
| `README.md` | 專案概覽、**三角色分工**、本地／PA 網址 |
| `AGENT_HANDOFF.md` | Grok Build 實作交接；戰鬥公式、API、部署、待辦 |
| `CURRENT_STRUCTURE.md` | 目錄樹、模組職責快照 |
| **本文** `GEMINI_REVIEW.md` | Review / Debug 範圍、優先級、輸出格式、已修復對照 |

**威脅模型（重要）**：玩家係中學生，會開 DevTools、改 API payload、試 bypass 機制。Security review 要假設 **client 不可信**，唔好只係檢查「happy path」。

**語言**：UI／錯誤訊息多為繁體中文；backend docstring 中英混合屬正常。

**重要**：請以 **`main` 分支現行檔案**為準。唔好引用已刪除嘅 `app_3.py` 或舊版 in-memory 狀態。

---

## 2. 建議閱讀順序（由外到內）

唔使由頭讀晒 `templates/index.html`（~6200 行）。按層次睇：

### Layer 0 — 入口與設定
```
wsgi.py                 # PA 入口；DATA_DIR=data/
app.py                  # Flask init、migrate_db、register_blueprints（~980 行，無 @app.route）
models/settings.py      # configure_models() 注入的 runtime config
requirements.txt
```

### Layer 1 — HTTP 路由（Blueprint）
```
routes/auth.py          # /login, /set_pin, /allocate_stats, session restore
routes/player.py        # /submit_task, /status, /verify_gps, avatar
routes/team.py          # /team/*, join/create/transfer_leadership
routes/combat.py        # /combat/*（start, status, submit_action, preview…）
routes/encounters.py    # /encounters, /encounter_logs
routes/items.py         # /my_items, /add_item, /claim_qr
routes/story.py         # /story_progress, /api/story/*, /api/story/views
routes/misc.py          # /, /api/version, /uploads, /locations
routes/gm.py            # /gm/*（GM 後台 API）
routes/gm_templates.py  # GM HTML + JS（inline templates）
```

### Layer 2 — 業務邏輯
```
models/combat.py        # 戰鬥結算、preview、status（~1450 行；含 resolving 鎖）
models/squad.py         # squads CRUD、near_death 輔助、route enrich
models/team.py          # teams、join、official_squad_route()（SSOT）
models/item.py          # 物品、grant（全事務）、QR 關聯
models/encounter.py     # encounter JSON 載入（mtime cache）
models/encounter_outcomes.py  # 勝利/失敗獎勵 + encounter logs
services/story.py       # 故事階段、story_views
services/player_status.py
services/session_auth.py
services/gm_auth.py     # GM 8h session 過期
services/teams_overview.py
services/global_events.py  # 全營事件（GM stat >100 唔 cap）
services/gm_admin.py
```

### Layer 3 — 安全與工具
```
utils/qr.py             # QR HMAC 簽名；production 預設禁 legacy unsigned QR
utils/uploads.py        # PIL 驗證、resize、8MB 上限；server 生成檔名
utils/helpers.py        # resolve_upload_disk_path、clamped_stat_delta_expr
utils/db_tx.py          # immediate_transaction()、with_db_retry()
utils/env.py            # is_production_env
```

### Layer 4 — 前端（按需抽查）
```
templates/index.html    # 玩家 Dashboard + 戰鬥 UI + JS（大檔，用 grep 搜函數名）
templates/claim_item.html
encounters/*.json       # 遭遇戰定義（數值平衡，非 security 主戰場）
```

### 快速 grep 起點（前端）
在 `templates/index.html` 搜：`submitAction`, `updateCombatUI`, `showToast`, `syncStoryViewsFromServer`, `fetch('/combat`  
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
scripts/test_combat_concurrency.py
```

**完整集（含 UI / UX）**：以上 + `templates/index.html`, `templates/claim_item.html`, `routes/gm_templates.py`

**唔使提供**：`*.db`, `uploads/`, `venv/`, `__pycache__/`, `static/avatars/` 二進制

---

## 4. Review 檢查清單（按優先級）

### 🔴 High — 營會前必須無漏洞

| 檢查項 | 睇邊度 | 已修復／現行設計 |
|--------|--------|------------------|
| **Multi-worker 狀態** | `services/announcements.py`, `models/encounter.py` | 遊戲狀態全在 SQLite；公告讀寫 `global_events`；Encounter JSON mtime cache |
| **Client 信任** | `routes/combat.py` `submit_action` | 骰子由 `roll_combat_dice()` 後端產生；client `dice_result` 忽略 |
| **戰鬥 double-resolve** | `models/combat.py` `resolve_player_phase()` | ✅ `player_phase → resolving` 原子鎖（`BEGIN IMMEDIATE`）；45s stale 恢復；`with_db_retry()` on `upsert_combat_action` |
| **戰鬥 action 重複** | `combat_actions` 表 | `UNIQUE(combat_id,squad_id,phase)` + `upsert_combat_action()` |
| **GM 認證** | `routes/gm.py`, `services/gm_auth.py` | Production 要 `GM_PIN` env；PIN 登入後 **8 小時** session 過期 |
| **QR 偽造** | `utils/qr.py` | v2 HMAC `token`；**production 預設 `ALLOW_LEGACY_QR=0`** |
| **QR replay** | `models/item.py` `grant_item_to_squad()` | `qr_code_uses`（`item_id UNIQUE`）+ 同隊重複檢查；**全檢查喺 `immediate_transaction` 內** |
| **上傳濫用** | `utils/uploads.py` | PIL verify + 8MB + resize；**唔信任 client filename**（server 生成 `{squad_id}_{ts}.jpg`） |
| **Path traversal** | `utils/helpers.py` `resolve_upload_disk_path` | `secure_filename` + realpath + 拒絕 `..` |
| **SQL injection** | 全 repo `conn.execute` | 動態 SQL 只用 **whitelist column**；user input 一律 `?` parameterized；`teams_overview.py` 為靜態 SQL |
| **多語句 SQL 一致性** | `utils/db_tx.py`, `models/team.py`, `models/item.py` | `BEGIN IMMEDIATE` + rollback；join、轉讓、建隊、設路線、grant item |
| **Session / PIN** | `routes/auth.py`, `services/session_auth.py` | 登入、restore token、PIN 驗證 |
| **GM stat 被事件清零** | `services/global_events.py`, `utils/helpers.py` | ✅ `clamped_stat_delta_expr()`：stat ≤100 仍 cap 100；**>100（GM 調整）唔再被壓返 100** |

### 🟡 Medium — 技術債／架構

| 檢查項 | 說明 |
|--------|------|
| **Route 雙重狀態** | ⚠️ **已緩解**：`official_squad_route()` 以 `teams.route` 為準；`get_squad` / 戰鬥參與者 enrich。DB 欄位 `squads.route` 仍存在（可之後 migration 刪除） |
| **瀕死狀態機** | ✅ 瀕死期間禁止道具補血；HP→0 先設 `near_death_until`；HP≤0 唔攻擊/暴走；救援用 `/combat/rescue_near_death` |
| **Story 已讀同步** | ✅ `story_views` 表 + `GET /api/story/views`；前端 `syncStoryViewsFromServer()` 以 server 為準 |
| **N+1 查詢** | ✅ `build_teams_overview()` bulk query；✅ GM dashboard submission count bulk `GROUP BY`。`get_active_combat_for_team()` 仍 loop members（20 人可接受） |
| **半重構殘留** | ✅ `app.py` 只剩 init + migrate + blueprints |
| **原生 dialog** | ✅ 玩家端 0 個 `alert()`/`prompt()`/`confirm()`；GM 用 `showGmToast` / `showGmInputModal` |
| **Defend 機制** | ✅ 全隊 buff：任一同隊 Defend → 反擊減半（`defend_team_buff`） |
| **Encounter logs** | ✅ `GET /encounter_logs`；`get_team_encounter_logs()` |

### 🟢 Low — 可記錄、唔阻營會

| 檢查項 | 說明 |
|--------|------|
| Tailwind CDN | 原型階段刻意用 CDN |
| `templates/index.html` 體積 | 可之後拆 JS/CSS |
| `squads.route` DB 欄位 | 讀取層已 SSOT，欄位可之後刪 |
| `gm_users` table | 營會規模 PIN + 8h session 已夠 |
| Encounter JSON 平衡 | 遊戲設計問題，非 code bug |
| 20 人 HTTP load test | 有 `scripts/test_combat_concurrency.py`；可擴展 |

---

## 5. 輸出格式（請 Gemini 跟此結構）

### Code Review 模式

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
- 重報本文 §9、§10 已標 ✅ 的項目

### Debug 模式（用戶報 bug 時）

```markdown
## Bug 摘要
（一句話描述現象）

## 重現步驟
1. …

## 根因分析
- **位置**：`path/to/file.py` — `function` / route
- **機制**：（為何第一次攻擊後 UI 仍滿血等）
- **信心**：High / Medium / Low

## 建議修復（交 Grok Build）
- （具體改法；可附 pseudo-code）
- **建議驗證**：測試指令或手動步驟

## 非根因（已排除）
- …
```

Debug 報告同樣**唔直接改 repo**；修復交 Grok Build，並建議補 regression test（如 `scripts/test_combat_flow.py`）。

---

## 6. 驗證指令（Reviewer 可建議跑）

```bash
cd /path/to/oikonomia
python3 -m py_compile app.py models/*.py routes/*.py services/*.py utils/*.py
./venv/bin/python3 scripts/test_combat_flow.py           # 戰鬥 API 煙霧測試（66 項）
./venv/bin/python3 scripts/test_encounter_cache.py       # Encounter mtime cache（3 項）
./venv/bin/python3 scripts/test_combat_concurrency.py    # 併發 submit/resolve smoke test
curl -s https://takjai.pythonanywhere.com/api/version | python3 -m json.tool
```

`/api/version` 的 `markers` 可確認部署功能開關，例如：
`server_combat_dice`, `task_photo_validation`, `qr_signed_v2`, `upload_path_hardened`, `protagonist_combat`, `trauma_ending`, `confirm_modal`, `protagonist_player_control`, `encounter_logs`, `defend_team_buff`

正式環境預期 `version` 與 GitHub `main` 一致（`curl /api/version` 核對）。

---

## 7. 已知待辦（Review 時唔重複當新 bug）

見 `AGENT_HANDOFF.md`「尚未完成」一節，例如：
- Salvio 最終 Boss encounter（劇情未寫）
- Marah 線 / 各 Stage 任務 + encounter
- Good Ending 完整演出
- 主角瀕死禱告救援、祈禱系統整體（延後）

已解決、**唔好再報**：
- ~~GM UI 強制結算~~（已有 `POST /gm/combat/resolve_phase`）
- ~~Defend 全隊 buff~~
- ~~confirm() 換 modal~~
- ~~全營事件壓 GM stat 返 100~~（`6f81430`）
- ~~戰鬥 double-resolve~~（`3cdb207`）
- ~~QR grant TOCTOU~~（`3cdb207`）
- ~~ALLOW_LEGACY_QR production 預設開~~（`3cdb207`）

---

## 8. 給用戶的開場白模板（Copy-paste 畀 Gemini）

### Code Review

```
你是 Oikonomia 的第三方 Engineer（Gemini）。Grok 負責方向，Grok Build 負責實作；你負責 review，唔改 repo。

請讀 GEMINI_REVIEW.md，然後做 code review。
範圍：[Security only / Full stack / 指定模組]
基準 commit：<git rev-parse --short HEAD>
Repo：GitHub Takjai18/oikonomia 或我附上的檔案

跟 GEMINI_REVIEW.md §5 Code Review 格式輸出。
High 項要寫清 exploit 場景同具體修復建議（交 Grok Build 落地）。
已修復項對照 §9、§10，唔好重複報。
```

### Debug

```
你是 Oikonomia 的第三方 Engineer（Gemini）。請讀 GEMINI_REVIEW.md §0、§5 Debug 模式。

Bug 描述：<用戶描述>
基準 commit：<hash>
相關檔案：<如 templates/index.html, models/combat.py>

請分析根因並給可執行修復建議（交 Grok Build）；建議 regression test。
```

---

## 9. Gemini 第一輪 Review 對照表（2026-06 初）

> 回應 Gemini 對**舊版 snapshot**（`app_3.py`、`ANNOUNCEMENTS = []`）嘅評價。

| Gemini 項目 | 嚴重度 | 現況（`main`） | 備註 |
|-------------|--------|----------------|------|
| In-memory `ANNOUNCEMENTS` | 🔴 Critical | ✅ **已修** | `global_events` 表 |
| 重複 `@app.route` / `app_3.py` | 🔴 Critical | ✅ **已修** | 路由全在 `routes/*` Blueprint |
| Team API 無 `rollback` | 🟠 High | ✅ **已修** | `immediate_transaction()` |
| `_encounter_cache` 熱更新 | 🟡 Medium | ✅ **已修** | mtime 自動失效 |
| `alert()` / `prompt()` / `confirm()` | 🟡 Medium | ✅ **已修** | 自訂 modal |
| `HTML_TEMPLATE` in Python | 🟢 Low | ✅ **已修** | `templates/index.html` |

---

## 10. Gemini 第二輪 Review 對照表（2026-06-29 Senior Backend）

> 回應用戶轉述嘅第二份 review（健康度 6.5/10）。以下為 **`3cdb207` 修復後**現況。

| Gemini 項目 | 嚴重度 | 現況 | 備註 |
|-------------|--------|------|------|
| 戰鬥結算 Race / 無 Transaction | 🔴 Critical | ✅ **已修** | `resolve_player_phase` 原子 `resolving` 鎖 + stale 恢復 + `with_db_retry` |
| SQL Injection（字串拼接） | 🔴 Critical | ✅ **唔成立／已防護** | `teams_overview` 靜態 SQL；動態 column 用 whitelist；參數化 `?` |
| QR Replay Attack | 🔴 Critical | ✅ **已修** | 全事務 grant；`qr_code_uses`；production 禁 legacy QR |
| Team/Squad route 雙重 SSOT | 🟠 High | ⚠️ **已緩解** | `official_squad_route()`；未刪 DB 欄位 |
| 瀕死/暴走邊緣情況 | 🟠 High | ✅ **已加強** | 瀕死禁補血；HP≤0 唔行動；救援 endpoint 保留 |
| 上傳 Directory Traversal | 🟠 High | ✅ **本來已修** | server 檔名 + `resolve_upload_disk_path` |
| N+1 Query | 🟡 Medium | ✅ **大部分已修** | teams overview + GM dashboard bulk；少數 loop 可接受 |
| story_views vs localStorage | 🟡 Medium | ✅ **已修** | `/api/story/views` + 前端 sync |
| GM 只靠 `session['is_gm']` | 🟡 Medium | ✅ **已加強** | `gm_auth.py` 8h 過期；production 要 `GM_PIN` |
| JSON 反覆 parse / God Object | 🟢 Low | ℹ️ **技術債** | 可記錄，唔阻營會 |
| Magic Number | 🟢 Low | ℹ️ **技術債** | 部分在 `settings` / encounter JSON |
| Load test 建議 | 🟢 Low | ✅ **已加** | `scripts/test_combat_concurrency.py` |

**整體健康度（`3cdb207` 後）**：約 **8–8.5 / 10**（20 人營會 ARG）。Gemini 第二輪 6.5/10 合理反映修復前狀態；多項 Critical/High 已處理。

**第二輪 Top 3 優先項 — 現時狀態**：

1. 戰鬥結算 DB Transaction → ✅ 已完成（resolving 鎖）  
2. SQL 字串拼接 → ✅ 已核實無 exploit 路徑  
3. Team/Squad Route SSOT → ⚠️ 讀取層完成；DB migration 可之後做  

**仍值得做（非阻營會）**：刪 `squads.route` 欄位；20 人 HTTP 層壓測；Salvio Boss encounter；拆 `index.html` JS。

---

## 11. 聯絡脈絡

| 項目 | 值 |
|------|-----|
| GitHub | https://github.com/Takjai18/oikonomia |
| Production | https://takjai.pythonanywhere.com |
| 本地 | http://localhost:5001 |
| 版本核對 | `curl /api/version` 應與 GitHub `main` 一致 |
| Grok（方向） | `README.md` § AI 開發分工 |
| Grok Build（實作） | `AGENT_HANDOFF.md` |
| Gemini（你） | 本文 `GEMINI_REVIEW.md` |

---

## 12. Gemini 第三輪 Review 對照表（2026-06-29 基礎架構）

> 範圍：`app.py`、`wsgi.py`、`test_combat.py`（Gemini 健康度 **8.0/10**）。  
> 修復 commit：見 `git log --oneline -1`（Grok Build 落地）。

| Gemini 項目 | 嚴重度 | 現況 | 備註 |
|-------------|--------|------|------|
| 多 Worker 啟動競爭（`init_db` / `migrate_upload_files`） | 🔴 High | ✅ **已修** | Production worker 跳過 auto-bootstrap；`deploy/pa-update.sh` 部署前單次 `bootstrap_app_data()`（fcntl 鎖） |
| `migrate_db()` `OperationalError` 被吞 | 🟡 Medium | ✅ **已修** | `_add_column_if_missing()`；已檢查欄位則直接 `ALTER`，fail fast |
| `wsgi.py` 預設 `GM_PIN=gm2026` | 🟡 Medium | ✅ **已修** | 移除 `setdefault`；`app.py` production 啟動檢查 `GM_PIN`（同 `SECRET_KEY`） |
| `app.py` God file | 🟢 Low | ℹ️ **技術債** | 可之後抽 `database.py` / `migrations.py` |
| `test_combat.py` 從 `app` import | 🟢 Low | ✅ **已修** | 改為 `from models.combat import ...` |

**第三輪 Top 3 — 現時狀態**：

1. 多 Worker DB migration 競爭 → ✅ 部署腳本單次 bootstrap + worker 跳過  
2. `migrate_db` exception masking → ✅ 已移除多餘 try-except  
3. 預設 GM PIN → ✅ production 必須 env 注入  

**下一步（Gemini 建議）**：進入「心臟地帶」— `models/combat.py`、`routes/combat.py`、`templates/index.html` 戰鬥 UI 全棧 review。