# Instructions for Gemini — Oikonomia Review & Debug

> **用途**：畀 **Gemini** 做第三方 Engineer 的 **Code Review** 同 **Debug** 時，請**先讀本文**，再按指引睇檔案。  
> **專案**：Summer Camp 2026 ARG · Flask + SQLite · 玩家 ~20 人 · 營會現場 3 日  
> **最後更新**：2026-07-02 · **§31 Safari 登入 audit**（已修對照 §18–§31）
> **正式環境**：https://oikonomia.onrender.com（Render Starter · Singapore；PA 僅後備）

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
4. 已修復項對照本文 §9、§10、**§29**，**唔好重複報**。
5. **唔盲目跟從自己舊建議**：先讀 `UPDATE_LOG.md`；若與 §29–§30 已拒絕項矛盾，須說明點解仍要改。
6. **Grok Build 會批判性審視你嘅每份 audit**（見 README「Gemini Audit 批判性審視」、§30）— 輸出建議時請附**可驗證證據**（檔名＋符號＋重現步驟），避免與已 ship 項重複。

```
Grok（方向） → Grok Build（實作） → Gemini（review / debug） → Grok Build（修復）
```

---

## 0.5 Context 管理協議（Gemini 必守 · 2026-06-30）

> **目的**：防 context 溢出導致 review 腰斬或幻覺。長對話**唔使**開新 Chat。

### Baseline（假設已讀，用戶唔會再貼全文）

| 檔案 | 版本 | 說明 |
|------|------|------|
| **`COMBAT_V2_AUDIT_BUNDLE.md`** | **v15** | Combat V2 SSOT（首次 onboarding 貼全文） |
| **`COMBAT_V2_PARTIAL_INDEX.md`** | — | 選 R11 / R12-A～D / **R15 Zoo** Partial |
| **`COMBAT_V2_R15_ZOO_PARTIAL_BUNDLE.md`** | R15 | Zoo 規格對齊（任何神智可發動 · >70/>80/>90 加成） |
| **`COMBAT_V2_R11_PARTIAL_BUNDLE.md`** | R11 | 營會現場風險 A/B/C |
| **`COMBAT_V2_R12_*_*.md`** | R12 | 大廳橋接 / DB / 編排 / INV |
| `combat_greenfield_final.md` | — | 綠地 FSM／INV 規格 |
| `GEMINI_REVIEW.md` | 本文 | Review 格式與已修對照（§18–§29；含 Render 戰鬥 audit 取捨） |

用戶提交 **【審計模式】** 時，範圍通常係**單一檔案或單一函數** — 唔期待你掃描成個 repo。

### 進門對齊模式

| 模式 | Gemini 輸出 |
|------|-------------|
| **【審計模式】**（預設） | **【Critical】→【High/Medium】→【Low】→ 健康度總評**（1–10）；每項附檔名＋符號＋ exploit／重現步驟 |
| **【開發模式】** | 唔係你嘅主戰場；若用戶誤標，提醒交 Grok Build，並只給架構／風險備註 |

### 局部審計規則

1. **一次一個 scope** — 例如只審 `routes/gm.py` 嘅 `gm_override_trauma_ending_api`，或只審 `victory_view.js` `showFailed`。
2. **唔要求** 用戶貼 `COMBAT_V2_AUDIT_BUNDLE.md` v15 全文 — 用 `COMBAT_V2_PARTIAL_INDEX.md` 所指 **一個** Partial 或單檔即可。
3. **戰鬥 V2** 前端已遷至 `static/js/combat/` — 審計 legacy `index.html` 戰鬥區前，先確認 `COMBAT_V2=1` 是否為現場配置。
4. **Bug case** 仍用 `bash scripts/build_gemini_packet.sh` 生成**局部** packet（`GEMINI_PACKET.md`），唔與 v10 Bundle 混貼。

### 【審計模式】輸出範本（複製結構）

```markdown
## 健康度總評：X/10

### 【Critical】
- （無則寫「無」）

### 【High/Medium】
- [High] 檔案:符號 — 問題 — 重現 — 建議修復

### 【Low】
- …

### 已確認安全（本 scope）
- …
```

### 用戶開場白範本（審計局部 scope）

```
【審計模式】
Baseline：COMBAT_V2_AUDIT_BUNDLE v15（已讀，唔貼全文）· 或貼 COMBAT_V2_PARTIAL_INDEX 所指 Partial
範圍：static/js/combat/views/victory_view.js — showFailed + GM 嵌入式面板
焦點：gm_session 403、team_id 來源、COMBAT_RESET from COMBAT_FAILED
請依 GEMINI_REVIEW.md §0.5 輸出。
```

---

## 1. Review 前必讀（5 分鐘）

| 檔案 | 用途 |
|------|------|
| `README.md` | 專案概覽、**三角色分工**、**Context 管理協議** |
| `AGENT_HANDOFF.md` | Grok Build 實作交接；戰鬥公式、API、部署、待辦 |
| `COMBAT_V2_AUDIT_BUNDLE.md` v15 | SSOT Baseline（**首次貼全文**；其後引用唔貼） |
| `COMBAT_V2_R11_PARTIAL_BUNDLE.md` | R11 局部審計（**日常貼呢個**） |
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
wsgi.py                 # Production 入口（Render gunicorn / PA WSGI）；DATA_DIR=/data on Render
render.yaml             # Render Blueprint（Starter、持久碟 /data）
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
deploy/render-predeploy.sh, deploy/render-check.sh
deploy/pa-update.sh（後備）
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
curl -s https://oikonomia.onrender.com/api/version | python3 -m json.tool
```

`/api/version` 的 `markers` 可確認部署功能開關，例如：
`server_combat_dice`, `task_photo_validation`, `qr_signed_v2`, `upload_path_hardened`, `protagonist_combat`, `trauma_ending`, `confirm_modal`, `protagonist_player_control`, `encounter_logs`, `defend_team_buff`

**Render 正式環境**預期 `version` 與 GitHub `main` 一致；`git_commit` 前 7 字元應與 `version` 相同；另核對 `render: true`、`data_dir: "/data"`、`db_path: "/data/oikonomia.db"`。

**Review deploy 相關改動時**（見 §28）：唔好建議 commit `.deploy-version`；若 `version` 舊但 `git_commit` 新，先查 UPDATE_LOG § version 假陽性，唔好當成 code 未 deploy。

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
| **Production（Render）** | https://oikonomia.onrender.com · Service `srv-d8v8i7cvikkc73fbsv0g` |
| 後備（PA） | https://takjai.pythonanywhere.com |
| 本地 | http://localhost:5001 |
| 版本核對 | `curl https://oikonomia.onrender.com/api/version` 應與 GitHub `main` 一致 |
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

**下一步（Gemini 建議）**：進入「心臟地帶」— `models/combat.py`、`routes/combat.py`、`templates/index.html` 戰鬥 UI 全棧 review（見 §13）。

---

## 14. Gemini 第四輪 Review 對照表（routes/combat.py）

> 修復 commit：見 `git log --oneline -1`（Grok Build 落地）。

| Gemini 項目 | 嚴重度 | 現況 | 備註 |
|-------------|--------|------|------|
| 瀕死救援 `rescue_type=item` 無限復活 | 🔴 High | ✅ **已修** | `apply_near_death_item_rescue()`：驗證 `player_items`、白名單 `hp_up`/`near_death_rescue`、`immediate_transaction` 消耗道具 |
| 開戰 TOCTOU 雙重 combat | 🔴 High | ✅ **已修** | `create_combat_record()` 內 `BEGIN IMMEDIATE` 再查 active combat；`ActiveCombatExistsError` → HTTP 409 |
| 盲目接受未知 `rescue_type` | 🟡 Medium | ✅ **已修** | 白名單 `prayer` / `item`；其餘 400 |
| 多 client 同時 `resolve_player_phase` | 🟡 Medium | ✅ **已確認** | `_claim_player_phase_resolution` 原子 `UPDATE … WHERE status='player_phase'`；路由層並發可接受 |
| Preview 固定 dice=1 | 🟢 Low | ✅ **安全** | 結算用 `roll_combat_dice()` |

---

## 13. Combat Review 檔案包（Full Stack）

> **基準 commit**：`d649903`（或 `git rev-parse --short HEAD`）  
> **範圍**：戰鬥結算、多人 phase、前端 polling、GM 強制結算  
> **唔使提供**：`*.db`、`uploads/`、`venv/`、`static/avatars/` 二進制

### 13.1 三層檔案包

#### 🎯 標準集（推薦 — 全棧 combat review）

```
# 必讀文檔
GEMINI_REVIEW.md          # 本文 §4 High 清單、§9–§12 已修對照
AGENT_HANDOFF.md          # 戰鬥公式、狀態機、API 速查
CURRENT_STRUCTURE.md      # 模組職責快照

# 後端核心（心臟）
models/combat.py          # ~1470 行：resolve、preview、status、resolving 鎖
routes/combat.py          # ~503 行：/combat/* HTTP 層
utils/db_tx.py            # immediate_transaction、with_db_retry

# 戰鬥相關依賴（抽查）
models/encounter.py       # encounter JSON 載入
models/encounter_outcomes.py  # 勝利/失敗、trauma ending
models/protagonist.py     # 主角 HP、瀕死、參戰
models/squad.py           # squad enrich、max_hp 正規化
models/team.py            # official_squad_route、隊伍成員
models/item.py            # 戰鬥道具使用（submit action item_id）

# GM 戰鬥監控
routes/gm.py              # /gm/combat/resolve_phase
routes/gm_templates.py    # GM 戰鬥 tab（~1130–1200 行 JS）

# 前端（大檔 — 可按 §13.2 行號抽查，唔使全讀）
templates/index.html      # ~6370 行；戰鬥 UI + JS

# 測試（驗證 reviewer 建議）
scripts/test_combat_flow.py       # ~503 行；API 煙霧 + 回歸
scripts/test_combat_concurrency.py  # 併發 submit/resolve

# 樣本 encounter（平衡參考，非 security 主戰場）
encounters/test_combat_01.json
encounters/test_lose_trauma.json
encounters/test_protagonist_control.json
```

#### 🔴 最小集（只做 Security / API）

```
models/combat.py
routes/combat.py
utils/db_tx.py
routes/gm.py              # 只睇 /gm/combat/resolve_phase
scripts/test_combat_concurrency.py
```

#### 🟢 加選集（完整 UX / 邊界）

```
標準集 +
routes/encounters.py      # encounter 列表、logs
routes/player.py          # /status 戰鬥欄位
services/player_status.py
services/teams_overview.py  # GM active combats overview
templates/index.html      # 全檔
routes/gm_templates.py      # 全檔
encounters/*.json           # 全部 encounter 定義
```

### 13.2 `index.html` 戰鬥區塊（唔使由頭讀）

| 區塊 | 約略行號 | 重點 |
|------|----------|------|
| 戰鬥 HTML（lobby + screen + modal） | 830–1100 | DOM 結構、HP 條、隊伍列 |
| 戰鬥狀態變數 | 1465–1490 | `combatEnemyHpSeen`、`effectiveCombatStatus` |
| Polling / 回合結算 | 1500–1660 | `startCombatPolling`、`handleCombatRoundResolved` |
| Modal / Preview | 1779–2180 | `openCombatModal`、`fetchAndShowCombatPreview` |
| 戰鬥頁載入 | 2216–2320 | `showCombatScreen`、`loadCombatPage` |
| **提交行動** | **2910–3000** | `submitAction` → `/combat/submit_action` |
| **UI 更新核心** | **2715–2900** | `updateCombatUI`、`loadCombatStatus` |
| 玩家/敵方 HP 顯示 | 3810–3920 | `effectivePlayerMaxHp`、`updateEnemyCombatStats` |
| 戰鬥結果 | 2659–2710 | `showCombatResult` |

**快速 grep**（在 `index.html`）：
```
combatEnemyHpSeen
submitAction
updateCombatUI
loadCombatStatus
handleCombatRoundResolved
effectiveCombatStatus
fetch('/combat
round_resolved
```

### 13.3 `models/combat.py` 閱讀順序

```
1. resolve_player_phase()      # resolving 鎖、多人等待
2. _resolve_player_phase_body()
3. upsert_combat_action()      # UNIQUE(combat_id,squad_id,phase)
4. build_combat_status_response()
5. build_combat_round_preview() / submit 相關傷害計算
6. _end_combat()               # 勝利時 enemy_hp=0
7. get_combat_participants()   # 隊伍成員 SSOT
8. apply_damage_to_player()    # 瀕死、暴走
```

### 13.4 Review 重點（本輪專屬）

| 檢查項 | 睇邊度 | 背景 |
|--------|--------|------|
| 敵方 HP 延遲更新 | `index.html` `combatEnemyHpSeen`；`models/combat.py` `_end_combat` | 曾出現第一擊後 UI 仍滿血 |
| 多人 phase 等待 | `resolve_player_phase`；`index.html` polling | 第一人 submit 後敵 HP 唔變屬正常 |
| Client 信任 | `routes/combat.py` `submit_action` | 骰子必須 server-side `roll_combat_dice` |
| Double-resolve | `models/combat.py` resolving 鎖 | §10 已修，確認無 regression |
| round_resolved 語意 | `index.html` `effectiveCombatStatus` | UI status vs backend status 不一致 |
| GM 強制結算 | `routes/gm.py`、`gm_templates.py` | 未提交隊員處理 |
| Defend 全隊 buff | `models/combat.py` `defend_team_buff` | 任一同隊 Defend → 反擊減半 |
| 瀕死/救援 | `rescue_near_death` route；`protagonist.py` | HP≤0 行動限制 |
| max_hp 顯示 | `squad.py` `squad_max_hp`；`effectivePlayerMaxHp` | GM 調整 HP 後 UI 上限 |

### 13.5 驗證指令（Reviewer 可建議跑）

```bash
cd /path/to/oikonomia
./venv/bin/python3 scripts/test_combat_flow.py
./venv/bin/python3 scripts/test_combat_concurrency.py
python3 -m py_compile models/combat.py routes/combat.py
```

### 13.6 Copy-paste 開場白（Combat Full Stack）

```
你是 Oikonomia 第三方 Engineer（Gemini）。Grok 負責方向，Grok Build 負責實作；你負責 review，唔改 repo。

請讀 GEMINI_REVIEW.md §13（Combat 檔案包）同 §4 High 清單。
基準 commit：d649903
範圍：Full stack combat（models/combat.py、routes/combat.py、templates/index.html 戰鬥區塊）

我已附上檔案：[貼 repo path 或 zip]

請跟 §5 Code Review 格式輸出。
§13.4 各檢查項要逐項回覆（✅ 無問題 / ⚠️ 風險 / 🔴 需修）。
已修項對照 §9–§12，唔好重複報。
High 項要寫清 exploit 或 bug 重現步驟，同具體修復建議（交 Grok Build）。
```

---

## 15. Gemini 第五輪 Review 對照表（前端同步 + 結算事務）

> 範圍：`templates/index.html` §13.4、`models/encounter_outcomes.py`、routes 防禦性檢查。

| Gemini 項目 | 嚴重度 | 現況 | 備註 |
|-------------|--------|------|------|
| `resolving` 期間 UI 誤判敵方 HP | 🟡 Medium | ✅ **已修** | `combatPhaseLocked` + resolving panel；凍結 HP 顯示；`round_resolved` 時用 server `enemy.hp` |
| 結算中仍可提交行動 | 🟡 Medium | ✅ **已修** | 禁用按鈕；`submitAction` 擋 resolving；409 觸發 1s polling |
| Polling 太慢 | 🟢 Low | ✅ **已修** | `resolving` → 1s；等待隊友 4s；一般 3s |
| 敵方 HP 視覺突兀 | 🟢 Low | ✅ **已修** | `animateCombatNumber()` 過渡；嚴格跟 server 值（防 stale 回升） |
| `apply_encounter_success/failure` 事務 | 🟡 Medium | ✅ **已修** | insight + completion + 全隊 failure 副作用包 `immediate_transaction` |
| `get_combat_participants` None | 🟢 Low | ✅ **已防護** | routes 用 `or []`；model 本身回 `[]` |
| Double-resolve 鎖 | — | ✅ **已確認** | §14 維持；`payload.resolving=true` 輔助前端 |

**Reviewer 結論（Grok Build）**：戰鬥模組在 `main` 上可視為 **Production Ready**；部署後請實機驗證 resolving spinner 與敵 HP 動畫。

---

## 16. Combat UX Review — Delay 殘留 + Settlement v10（2026-06-30）

> **Active case**：BUG-2026-001 · `fix_in_progress` / **monitoring**  
> **基準 commit**：`6391b22`（或 `git rev-parse --short HEAD`）  
> **背景**：`combat_instant_settlement` 已移除人工 modal／HP delay；v8–v10 修 settlement duplicate + final-hit stuck。  
> **實機**：Henry instant checklist OK，但 **delay 體感仍未完全解決**（擲骰動畫、deferEnemyHp、戶外 poll）。

### 16.1 俾 Gemini 嘅檔案（按優先）

#### ① 必讀文檔（Copy 貼上 — 最可靠）

| 檔案 | 用途 |
|------|------|
| **`bug_log/cases/2026-06-29_combat_enemy_hp_settlement/GEMINI_PACKET.md`** | **自包含包**（摘要 + JS/Python 摘錄）— `bash scripts/build_gemini_packet.sh` 生成 |
| `bug_log/cases/.../GEMINI_CONSULT.md` | Phase 3 一頁題目（delay + v10） |
| `bug_log/cases/.../REPORT.md` §13–§19 | 完整調查時間線 |
| `decisions_log.md` § instant settlement · § Combat Settlement Modal Bug | 架構決策（唔好建議恢復 1500ms delay） |
| `UPDATE_LOG.md` § BUG-2026-001 / combat_flow_v8–v10 | 已知陷阱 |

#### ② 後端（API 合約 — 確認問題喺 frontend）

| 檔案 | 行數級 |
|------|--------|
| `routes/combat.py` | `submit_action`、`combat/status` |
| `models/combat.py` | `resolve_player_phase`、`build_victory_outcome_response`、`_round_settlement_from_logs` |
| `services/combat_engine.py` | 純計算（Step 1；與 delay 無關） |
| `scripts/test_combat_flow.py` | 回歸基線（應全綠） |

#### ③ 前端（核心 — delay + settlement）

| 檔案 | 重點符號（grep） |
|------|------------------|
| **`templates/index.html`** | `DICE_ROLL_PRESETS`, `showFullRoundSettlement`, `finishCombatVictoryFromPayload`, `loadCombatStatus`, `handleCombatRoundResolved`, `isFinalHitOrVictory`, `resolveEnemyHpAfter`, `settlementModalShown`, `syncEnemyHpDisplay`, `applyPendingSettlementHp`, `combatAwaitingSettlementAck` |

**唔使**全檔 7000+ 行 — 用 `GEMINI_PACKET.md` §D 摘錄 + 上表 grep 補充即可。

#### ④ 唔使俾

- `*.db`、`venv/`、`uploads/`、`attachments/`（可能過時快照）
- Drive **資料夾**連結（Gemini 讀唔到）
- 成個 repo zip（除非 Gemini 支援且你有 quota）

### 16.2 `index.html` 戰鬥區塊（2026-06-30 約略行號）

| 區塊 | 行號 | 重點 |
|------|------|------|
| 擲骰 preset | ~1238–1271 | `pauseMs: 0`；`intervalMs`×`maxRolls` = 提交前延遲 |
| HP sync | ~1832–1900 | `syncEnemyHpDisplay`、`applySettlementEnemyHp` |
| Settlement guard | ~2065–2290 | `settlementModalShown`、`showFullRoundSettlement` |
| Victory 過渡 | ~2336–2420 | `finishCombatVictoryFromPayload`、`finalizeCombatVictoryFromPayload` |
| Final hit | ~2445–2475 | `isFinalHitOrVictory`、`resolveEnemyHpAfter` |
| Round resolved | ~2478–2520 | `handleCombatRoundResolved` |
| Poll | ~3641–3720 | `loadCombatStatus` early return、`syncHpOnlyFromPoll` |
| Submit | ~3768–3820 | `submitAction` |

### 16.3 請 Gemini 回答（Phase 3）

1. 在 **instant settlement 已上線** 前提下，剩餘 delay 最可能來自邊 1–2 條 path？量化每段 ms。
2. `deferEnemyHp`（modal 期間主畫面舊 HP）係咪主要 UX 誤判來源？建議改法？
3. v10 final-hit 流程有無 race（submit vs poll）仍會 stuck 或 duplicate modal？
4. 最低風險 patch 順序（營會前 3 日）？
5. 可自動化嘅延遲／modal 回歸測試建議。

### 16.4 Copy-paste 開場白（Combat Delay + Settlement）

```
你是 Oikonomia 第三方 Engineer（Gemini）。Grok 方向、Grok Build 實作；你 review/debug，唔改 repo。

請讀我附上嘅 GEMINI_PACKET.md（BUG-2026-001 Phase 3）同 GEMINI_REVIEW.md §16。
基準 commit：6391b22
範圍：戰鬥 UX — 殘留 delay（instant settlement 後）+ settlement/v10 穩健性

後端 API／CI 已全綠；問題集中在 templates/index.html timing。
唔好建議恢復 COMBAT_SETTLEMENT_DELAY_MS 或 1500ms modal 人工等待。

請跟 §5 Debug 格式：根因 → 重現步驟 → 最小修復建議（交 Grok Build）→ 建議測試。
```

### 16.5 GitHub Raw（若 Gemini 支援 URL）

將 `6391b22` 換成實際 commit：

- Packet：`https://raw.githubusercontent.com/Takjai18/oikonomia/6391b22/bug_log/cases/2026-06-29_combat_enemy_hp_settlement/GEMINI_PACKET.md`
- Consult：`https://raw.githubusercontent.com/Takjai18/oikonomia/6391b22/bug_log/cases/2026-06-29_combat_enemy_hp_settlement/GEMINI_CONSULT.md`
- `index.html`（大檔）：`https://raw.githubusercontent.com/Takjai18/oikonomia/6391b22/templates/index.html`

---

## 17. BUG-2026-001 Phase 4（Safari 0 傷害 + Chrome 勝利後重複結算 · 2026-06-30）

### 17.1 俾 Gemini 嘅檔案

| 檔案 | 用途 |
|------|------|
| **`GEMINI_PACKET.md`** | `bash scripts/build_gemini_packet.sh` — 含 v12 摘錄 |
| **`GEMINI_CONSULT.md`** | Phase 4 題目（§21–§22） |
| **`REPORT.md` §21–§23** | 實機回報 + code review 根因 + v12 |

### 17.2 重點符號（grep `templates/index.html`）

| 符號 | 議題 |
|------|------|
| `combatVictorySequenceCompleteId` | §22 勝利後重複結算 |
| `showCombatResult` + `keepVictoryLock` | §22 reset 清空 guard |
| `enrichRoundSettlementData` | §21 Safari 0 傷害 |
| `buildSettlementBreakdown` breakdown early return | §21 空 breakdown |
| `loadCombatStatus` poll `round_settlement` 路徑 | §22 觸發點 |

### 17.3 Copy-paste 開場白（Phase 4）

```
你是 Oikonomia 第三方 Engineer（Gemini）。Grok 方向、Grok Build 實作；你 review/debug，唔改 repo。

請讀 GEMINI_PACKET.md（BUG-2026-001 Phase 4）同 GEMINI_REVIEW.md §17。
基準：40a2c53（v11）→ v12 patch 描述見 REPORT §21–§23。

新症狀：
1. Vini Safari — practice_iggy_04_marathon 結算顯示 0 傷害（骰子非 0）
2. Henry Chrome — 勝利畫面後再彈傷害結算

請確認 v12 修復是否覆蓋根因；指出 race／edge case；建議自動化 assert。
格式：根因 → 重現 → 最小修復 → 測試。
```

---

## 18. R11/R12 Combat V2 審計封頂（2026-07-01 · `0e2fa93`）

> **用途**：下一輪 Gemini **唔好重複報**以下已落地修復。新審計請用 `COMBAT_V2_PARTIAL_INDEX.md` 選 **單一** Partial（regression / 新 scope only）。

### 18.1 已修對照表（唔重複報）

| 審計輪次 | 議題 | 狀態 | 主要檔案 / commit |
|----------|------|------|-------------------|
| **R11-A** | GM 特權 `team_id` 客戶端篡改 | ✅ | `victory_view.js` `resolveAuthoritativeTeamId` · `routes/gm.py` `gm_operator` 403 · `7823a95` |
| **R11-B** | 超時自動防禦 double-submit | ✅ | `index.js` `triggerTimeoutAutomaticDefense` + `performActionDirectly` · `7823a95` |
| **R11-C** | Co-op 同秒 resolve 重複結算 | ✅ | `models/combat.py` `_wait_after_peer_resolve` monotonic · `7823a95` |
| **R12-A** | 大廳 3s poll 與 V2 FSM 競爭 | ✅ | `OIKONOMIA_COMBAT_V2_LOCK` sessionStorage · `finishSessionRestore` DOM-first · `b931b37` |
| **R12-B** | `_end_combat` 多連線 lock / 髒 actions | ✅ | atomic `_end_combat` + `reconcile` purge · `database.py` `get_db_connection` · `3bd8d36` |
| **R12-C** | outcome 外層 retry race / piercing / failed_escape | ✅ | `combat_outcomes.py` · `combat_engine.py` · `_resolve_player_phase_body` · `0e2fa93` |
| **R12-D** | settlement monotonic / entrySyncPending | ✅ | `state_machine.js` · `settlement.js`（早前 `7029bfd`+） |

### 18.2 測試基線（`0e2fa93`）

```bash
./venv/bin/python3 scripts/test_combat_flow.py              # 267/267
./venv/bin/python3 scripts/test_db_hardening.py             # 11/11
./venv/bin/python3 scripts/test_combat_engine.py            # 17/17
./venv/bin/python3 scripts/test_combat_flow_orchestrator.py # 4/4
npm run test:combat                                         # 17/17
./venv/bin/python3 scripts/test_combat_concurrency.py
```

### 18.3 下一輪審計建議 scope

| 優先 | 方向 | Bundle |
|------|------|--------|
| 1 | 新 encounter / 劇情內容接入 | 單檔 + `test_encounter_catalog` |
| 2 | PA 部署後實機弱網重連 | R12-A regression |
| 3 | 20 人 HTTP 壓測擴展 | 新腳本（非現有 smoke） |
| 4 | `get_team_protagonists` 常數化（Low） | `models/team.py` |

### 18.4 Copy-paste 開場白（R12 後下一輪）

```
你是 Oikonomia 第三方 Engineer（Gemini）。Grok 方向、Grok Build 實作；你 review/debug，唔改 repo。

Baseline：COMBAT_V2_AUDIT_BUNDLE v12（已讀，唔貼全文）
已修對照：GEMINI_REVIEW.md §18（R11/R12 唔重複報）
本次範圍：<貼 COMBAT_V2_PARTIAL_INDEX 所指單一 Partial 或單檔>
基準 commit：0e2fa93

輸出：【Critical】→【High/Medium】→【Low】→ 健康度 X/10
```

---

## 19. R13 後端安全硬化（2026-07-01）

| 議題 | 狀態 | 修復 |
|------|------|------|
| **R13-A** `combat_start_api` body `squad_id` IDOR | ✅ | 預設 `session["squad_id"]`；僅 `COMBAT_E2E=1` 允許 body override · `routes/combat.py` |
| **R13-B** `purge_combat_actions` 缺 db_path | ✅ | `immediate_transaction(settings.db_path)` · `models/combat.py` |
| **R13-C** `rescue_near_death` 無法指定對象 | ✅ | 可選 `target_squad_id`（同隊 + 瀕死驗證）· `routes/combat.py` |
| **R13-D** `gm_operator` 匿名 fallback | ⛔ 刻意不做 | R11 已改為無 operator 則 403（審計追溯） |

測試：`test_combat_start_rejects_body_squad_id_spoof` · `test_rescue_near_death_target_squad_id` · `test_combat_flow.py` **274/274**

---

## 20. R14 西貢營會前審計封頂（2026-07-01 · `5ea4cf8`）

> **用途**：R11～R13 + 二輪 Partial 審計已落地；下一輪 Gemini **唔好重複報**以下項。請用 `COMBAT_V2_PARTIAL_INDEX.md` 選 **新 scope** 或 **回歸驗證**（標明 commit 差異）。

### 20.1 已修對照表（唔重複報）

| 輪次 | 議題 | 狀態 | commit / 檔案 |
|------|------|------|----------------|
| **R12-D₂** | Stale victory poll 單調熔斷 + SETTLEMENT 不跳級 | ✅ | `b94b31f` `state_machine.js` |
| **R12-D₃** | SETTLEMENT poll 終端晉升 + `HIDE_SETTLEMENT` 強制拆解 | ✅ | `5ea4cf8` `state_machine.js` |
| **R12-D₃** | `near_death_until` → `isMemberCollapsed` (INV-D) | ✅ | `5ea4cf8` |
| **R12-A₂** | `finishSessionRestore` rAF 重繪 + 雙次 `revealCombatV2Surface` | ✅ | `e0a10bf` `index.html` |
| **R12-A₂** | `exitCombatScreen` → `combatV2.destroy()` 生命週期 | ✅ | `e0a10bf` `bootstrap.js` |
| **R12-B₂** | `reconcile` 原子 purge orphan `combat_actions` | ✅ | `1320992` `models/combat.py` |
| **R12-B₂** | `get_team_protagonists` → `get_db_connection` (WAL) | ✅ | `1320992` `models/team.py` |
| **R12-C₂** | Solo 完結志 `SOLO:` scope 隔離 + 冪等 | ✅ | `647886a` `combat_outcomes.py` |
| **R12-C₂** | `dice_multiplier` 異常回退 2→1（中性 1.0x） | ✅ | `647886a` `combat_engine.py` |
| **R11₂** | `gm_operator` 正則清洗 | ✅ | `649526a` `routes/gm.py` |
| **R11₂** | `DICE_CONFIRM` 超時強制 defend | ✅ | `649526a` `index.js` |
| **R13** | `combat_start` IDOR · `purge` db_path · `target_squad_id` | ✅ | `52f7753` / `a861773` |
| **Low** | 主角 key 常數 `combat/constants.js` | ✅ | `649526a` |

### 20.2 測試基線（`adf54a8` · PA 驗證通過）

```bash
./venv/bin/python3 scripts/test_combat_flow.py      # 280/280
./venv/bin/python3 scripts/test_db_hardening.py     # 12/12
./venv/bin/python3 scripts/test_combat_engine.py    # 17/17
npm run test:combat                                 # 23/23
bash scripts/pre_deploy_checks.sh
```

### 20.3 下一輪建議 scope（新審計）

| 優先 | 方向 | 建議 Bundle / 檔案 |
|------|------|-------------------|
| 1 | **實機弱網** F5 重連 + 打字機 0px 回歸 | R12-A + 現場錄影對照 |
| 2 | **20 人 HTTP 壓測** `/combat/status` 併發 | 新腳本（非 smoke） |
| 3 | **Encounter 內容接入** 新路線劇情 | `encounters/` + `test_encounter_catalog` |
| 4 | **Playwright T8–T14** PA 部署後 E2E | `tests/combat_v2.spec.js` |
| 5 | **GM 後台** 非 override 路徑 | `routes/gm.py` 其餘 API |

### 20.4 Copy-paste 開場白（R14 下一輪）

```
你是 Oikonomia 第三方 Engineer（Gemini）。Grok 方向、Grok Build 實作；你 review/debug，唔改 repo。

Baseline：COMBAT_V2_AUDIT_BUNDLE v13（已讀，唔貼全文）
已修對照：GEMINI_REVIEW.md §18–§21（唔重複報）
本次範圍：<貼 COMBAT_V2_PARTIAL_INDEX 單一 Partial 或 §20.3 新 scope>
基準 commit：adf54a8

輸出：【Critical】→【High/Medium】→【Low】→ 健康度 X/10
```

---

## 21. PA 部署 hotfix — 漏 ship 補齊（2026-07-01 · `adf54a8`）

> **性質**：v13 bundle 生成時本機已有完整碼，但 `5ea4cf8` 未 push 至 main，導致 PA pre-deploy 500。  
> **唔係** 新安全議題；Gemini **唔好重複報**「缺模組」，只可做回歸確認。

### 21.1 已修對照表

| commit | 議題 | 狀態 | 檔案 |
|--------|------|------|------|
| **e675244** | `build_combat_item_consume_batch` 等未在 main | ✅ | `models/item.py` |
| **e675244** | 戰鬥物品 picker `/api/inventory` | ✅ | `routes/items.py` |
| **e675244** | `escape` 加入 `COMBAT_ACTION_TYPES` | ✅ | `app.py` |
| **e675244** | `combat_v2` version markers | ✅ | `routes/misc.py` |
| **adf54a8** | `services.narrative_orchestrator` 未 commit | ✅ | `services/narrative_orchestrator.py` |
| **adf54a8** | `services.trauma_service` 未 commit | ✅ | `services/trauma_service.py` |

### 21.2 測試基線（`adf54a8` · PA pre-deploy）

```bash
./venv/bin/python3 scripts/test_combat_flow.py      # 280/280
./venv/bin/python3 scripts/test_db_hardening.py     # 12/12
./venv/bin/python3 scripts/test_combat_engine.py    # 17/17
npm run test:combat                                 # 23/23
bash scripts/pre_deploy_checks.sh
```

### 21.3 Copy-paste 開場白（PA 部署後審計）

```
你是 Oikonomia 第三方 Engineer（Gemini）。Grok 方向、Grok Build 實作；你 review/debug，唔改 repo。

Baseline：COMBAT_V2_AUDIT_BUNDLE v13（已讀，唔貼全文）
已修對照：GEMINI_REVIEW.md §18–§21（唔重複報漏 ship hotfix）
基準 commit：adf54a8（PA 可部署）
本次範圍：<§20.3 新 scope 或單一 Partial 回歸>

輸出：【Critical】→【High/Medium】→【Low】→ 健康度 X/10
```

---

## 22. R12-C/D 第三輪審計落地（2026-07-01 · `eb4f1e2`）

> **性質**：Gemini R12-C Step4（INV-E / 戰後編排）+ R12-D（INV-A 終端轉移）第三輪 findings；下一輪 **唔好重複報** 以下項。

### 22.1 已修對照表

| 輪次 | 議題 | 狀態 | commit / 檔案 |
|------|------|------|----------------|
| **R12-C₃** | `failed_escape` 破壞敵方反擊 targeting 優先級 (INV-E) | ✅ | `eb4f1e2` `combat_engine.py` · `models/combat.py` |
| **R12-C₃** | `execute_post_combat_success_pipeline` 巢狀 TX 防禦 (`conn=` 參數) | ✅ | `eb4f1e2` `narrative_orchestrator.py` |
| **R12-D₄** | `handleAnyDeath` → `terminalModalTeardownEffects`（含 `HIDE_SETTLEMENT`） | ✅ | `eb4f1e2` `state_machine.js` |
| **R12-D₄** | SETTLEMENT 期 defeat poll → `pendingSettlement/Id` 清零 | ✅ | 早前已有 · `eb4f1e2` 測試補強 |
| **Low** | `calculate_incoming_damage` piercing 順序微擾 | ⛔ 刻意不做 | 非安全 · 單測已綠 |
| **Low** | `parseCombatHp` 字串容錯 | ⛔ 刻意不做 | 現行 `parseInt` 足夠 |

### 22.2 測試基線（`eb4f1e2`）

```bash
./venv/bin/python3 scripts/test_combat_flow.py      # 283/283
./venv/bin/python3 scripts/test_combat_engine.py    # 18/18
./venv/bin/python3 scripts/test_combat_flow_orchestrator.py  # 4/4
npm run test:combat                                 # 24/24
bash scripts/pre_deploy_checks.sh
```

### 22.3 Copy-paste 開場白（R12-C/D 後下一輪）

```
你是 Oikonomia 第三方 Engineer（Gemini）。Grok 方向、Grok Build 實作；你 review/debug，唔改 repo。

Baseline：COMBAT_V2_AUDIT_BUNDLE v14（已讀，唔貼全文）
已修對照：GEMINI_REVIEW.md §18–§22（唔重複報）
基準 commit：28601b3
本次範圍：<§20.3 新 scope 或單一 Partial 回歸>

輸出：【Critical】→【High/Medium】→【Low】→ 健康度 X/10
```

---

## 23. 全棧戰鬥審計落地（2026-07-01 · `28601b3`）

> **性質**：Gemini v14 全棧 onboarding（8.8/10）High/Medium 痛點 + PA deploy 硬化；下一輪 **唔好重複報** 以下項。

### 23.1 已修對照表

| 輪次 | 議題 | 狀態 | commit / 檔案 |
|------|------|------|----------------|
| **R15** | resolve-phase 道具 TOCTOU（`consume_dry_run` + 單一 TX） | ✅ | `28601b3` `models/combat.py` · `models/item.py` |
| **R15** | 弱網重連 `bootstrap.js` 同步 skeleton + `isInitComplete` | ✅ | `28601b3` `bootstrap.js` · `index.html` |
| **R15** | `protagonist_states` 併發 create 競態 (INSERT OR IGNORE) | ✅ | `a1e9de4` `models/protagonist.py` |
| **R15** | PA deploy `COMBAT_V2` marker / `combat-root-v2` 辨識 | ✅ | `a1e9de4` `deploy/pa-update.sh` |
| **Low** | DICE_CONFIRM 超時 disable confirm 鈕 | ✅ | `28601b3` `dice_modal_view.js` |
| **Low** | combat logs 獨立表 | ⛔ 刻意不做 | 20 人規模足夠 |

### 23.2 測試基線（`28601b3`）

```bash
./venv/bin/python3 scripts/test_combat_flow.py      # 283/283
./venv/bin/python3 scripts/test_combat_engine.py    # 18/18
./venv/bin/python3 scripts/test_combat_flow_orchestrator.py  # 5/5
./venv/bin/python3 scripts/test_db_hardening.py     # 13/13
./venv/bin/python3 scripts/test_combat_concurrency.py
npm run test:combat                                 # 24/24
bash scripts/pre_deploy_checks.sh
```

### 23.3 Copy-paste 開場白（全棧審計後下一輪）

```
你是 Oikonomia 第三方 Engineer（Gemini）。Grok 方向、Grok Build 實作；你 review/debug，唔改 repo。

Baseline：COMBAT_V2_AUDIT_BUNDLE v14（已讀，唔貼全文）
已修對照：GEMINI_REVIEW.md §18–§23（唔重複報）
基準 commit：28601b3
本次範圍：<§20.3 新 scope 或單一 Partial 回歸>

輸出：【Critical】→【High/Medium】→【Low】→ 健康度 X/10
```

---

## 24. 弱網提交鎖與 TERMINAL_PHASES SSOT（2026-07-01 · `d41f23a`）

> **性質**：Gemini v14 第二輪（8.8/10）前端 Polling 競態 + 終端 Phase 常數化；下一輪 **唔好重複報** 以下項。

### 24.1 已修對照表

| 輪次 | 議題 | 狀態 | commit / 檔案 |
|------|------|------|----------------|
| **R16** | `submittingActive` 飛行期 poll 降級（hpOnly HUD） | ✅ | `d41f23a` `index.js` · `render.js` |
| **R16** | `TERMINAL_PHASES` SSOT（`state_machine.js` → views） | ✅ | `d41f23a` `action_view.js` |
| **Low** | `get_protagonists_states_bulk` N+1 | ⛔ 刻意不做 | 20 人規模足夠 |

### 24.2 測試基線（`d41f23a`）

```bash
./venv/bin/python3 scripts/test_combat_flow.py      # 283/283
./venv/bin/python3 scripts/test_combat_engine.py    # 18/18
./venv/bin/python3 scripts/test_combat_flow_orchestrator.py  # 5/5
./venv/bin/python3 scripts/test_db_hardening.py     # 13/13
npm run test:combat                                 # 25/25
bash scripts/pre_deploy_checks.sh
```

### 24.3 Copy-paste 開場白（R16 後下一輪）

```
你是 Oikonomia 第三方 Engineer（Gemini）。Grok 方向、Grok Build 實作；你 review/debug，唔改 repo。

Baseline：COMBAT_V2_AUDIT_BUNDLE v14（已讀，唔貼全文）
已修對照：GEMINI_REVIEW.md §18–§24（唔重複報）
基準 commit：d41f23a
本次範圍：<§20.3 新 scope 或單一 Partial 回歸>

輸出：【Critical】→【High/Medium】→【Low】→ 健康度 X/10
```

---

## 25. Greenfield Zoo 規格修正（2026-07-01 · `137dfa9`）

> **性質**：糾正舊誤「神智 >70 才能發動 Zoo」；下一輪 **唔好重複報** 以下項。

### 25.1 權威規格（`combat_greenfield_final.md` v1.1）

| 項目 | 規格 |
|------|------|
| 發動條件 | **任何神智值均可發動**；僅 `combat_settings.allow_zoo === false` 禁止 |
| 加成乘數 | **見 §26**（R18 改為 ≥70/≥80/≥90/≥100） |
| UI | **唔應**因神智不足 disable Zoo 按鈕 |
| 暴走 | 與攻擊相同（神智 <10/20/40 → 90%/50%/20%） |

### 25.2 已修對照表

| 輪次 | 議題 | 狀態 | commit / 檔案 |
|------|------|------|----------------|
| **R17** | 移除 FSM `sanity >= 70` Zoo guard | ✅ | `048adba` `state_machine.js` |
| **R17** | UI 低神智仍可點 Zoo；提示無加成 | ✅ | `048adba` `action_view.js` |
| **R17** | 後端／前端乘數（初版誤用 `>`） | ⚠️ 已 supersede | `137dfa9` → §26 改 `>=` |
| **R17** | Greenfield 文件 v1.1 權威表 | ✅ | `137dfa9` `combat_greenfield_final.md` |
| **R17** | 單元測試 sanity 55 可 `ACTION_USE_ZOO` | ✅ | `048adba` `combat_state_machine.test.js` |

### 25.3 測試基線（`137dfa9`）

```bash
npm run test:combat                                 # 26/26
./venv/bin/python3 scripts/test_combat_flow.py      # 283/283
bash scripts/pre_deploy_checks.sh
```

### 25.4 Copy-paste 開場白（Zoo 規格審計）

```
【審計模式】
你是 Oikonomia 第三方 Engineer（Gemini）。Grok 方向、Grok Build 實作；你 review/debug，唔改 repo。

Baseline：COMBAT_V2_AUDIT_BUNDLE v15（已讀，唔貼全文）
本次範圍：貼 COMBAT_V2_R15_ZOO_PARTIAL_BUNDLE.md 全文
已修對照：GEMINI_REVIEW.md §18–§25（唔重複報）
基準 commit：137dfa9
焦點：Zoo 任何神智可發動；≥70/≥80/≥90 加成；前後端邊界一致

輸出：【Critical】→【High/Medium】→【Low】→ 健康度 X/10
```

---

## 26. Zoo 乘數邊界 ≥ 與 AI 低神智發動（2026-07-02 · Gemini R15 審計後）

> **性質**：Gemini R15 審計（7.5/10）— 邊界 `>` 改 `>=`；AI 主角放開低神智 Zoo；下一輪 **唔好重複報**。

### 26.1 權威規格（`combat_greenfield_final.md` v1.1 更新）

| 神智 | Zoo 傷害乘數 |
|------|-------------|
| <70 | ×1.0（可發動） |
| ≥70 | ×1.3 |
| ≥80 | ×1.4 |
| ≥90 | ×1.5 |
| ≥100 | ×1.8 |

### 26.2 已修對照表

| 輪次 | 議題 | 狀態 | 檔案 |
|------|------|------|------|
| **R18** | `zoo_bonus_multiplier` 邊界 `>=70/80/90/100` | ✅ | `models/combat.py` · `action_view.js` |
| **R18** | AI `choose_protagonist_auto_action` 放開 sanity gate | ✅ | `models/combat.py`（35% 隨機 Zoo） |
| **R18** | UI 提示「≥70 才有加成」 | ✅ | `action_view.js` |
| **R18** | 邊界單元測試 69/70/80/90/100 | ✅ | `test_combat_flow.py` |

### 26.3 Copy-paste 開場白（R18 後回歸）

```
【審計模式】
Baseline：COMBAT_V2_AUDIT_BUNDLE v15（已讀，唔貼全文）
已修對照：GEMINI_REVIEW.md §18–§26（唔重複報）
基準 commit：<HEAD>
本次範圍：R15 Zoo 回歸或 §20.3 新 scope
```

---

## 27. Render.com 遷移（2026-07-02 · Starter / Singapore）

> **性質**：正式環境由 PythonAnywhere 遷至 **Render Starter**；之後 code review 要假設 **Render 架構**，唔好再當 PA 為主機。

### 27.1 正式環境

| 項目 | 值 |
|------|-----|
| URL | https://oikonomia.onrender.com |
| Service ID | `srv-d8v8i7cvikkc73fbsv0g` |
| Plan | Starter · Singapore |
| 程序 | gunicorn `wsgi:application` |
| 持久資料 | `/data`（`oikonomia.db`、`uploads/`、`.secret_key`、`.gm_pin`、`.combat_v2`） |
| Env | `DATA_DIR=/data`、`RENDER=true`、`FLASK_ENV=production` |
| PA | **後備** — https://takjai.pythonanywhere.com |

### 27.2 Review 時要考慮的 Render 約束

| 檢查項 | 說明 |
|--------|------|
| 持久化路徑 | DB／上傳／secrets 必須在 `/data`；唔好寫死 `project/src/` 或 `data/`（redeploy 會清） |
| 多 worker | gunicorn 多進程；遊戲狀態必須在 SQLite（已有）；避免 in-memory 狀態 |
| 啟動方式 | 唔建議 `python3 app.py` 作 production；用 `wsgi:application` |
| Deploy 同步 | push `main` → CI tests → Deploy Hook → `/api/version` 與 commit 一致 |
| Secrets | Deploy Hook URL 存 GitHub Secret；**勿** commit 到 repo |
| `.deploy-version` | **勿** commit（`.gitignore`）；誤 commit 會令 `version` 假陽性（§28） |
| preDeploy | Events log 應見 `=== Render pre-deploy ===`；否則 Dashboard 未對齊 `render.yaml` |

### 27.3 驗證指令

```bash
LOCAL=$(git rev-parse --short HEAD)
curl -s https://oikonomia.onrender.com/api/version | python3 -m json.tool
bash deploy/render-check.sh https://oikonomia.onrender.com
```

預期：`render: true`、`data_dir: "/data"`、`success: true`、`version` == `$LOCAL`，`git_commit[:7]` == `version`。

---

## 28. Render `/api/version` 假陽性（2026-07-02 · `2dc4c47`）

> **用途**：Gemini review deploy／infra 改動時 **唔好重複報** 以下已修項；新 audit 應識別同類回歸。

### 28.1 已發生過的問題

| 項目 | 說明 | 狀態 |
|------|------|------|
| **誤 commit `.deploy-version`** | 檔內容卡 `3017e16`，`/api/version` 長期舊 hash | ✅ 已從 repo 移除 + `.gitignore` |
| **Dashboard 無 preDeploy** | Build 成功但 log 跳過 `render-predeploy.sh` | ✅ `startCommand` 補跑；文檔要求 Dashboard 對齊 |
| **`RENDER_GIT_COMMIT` fallback** | 無 `.deploy-version` 時仍顯示正確 hash | ✅ `utils/deploy.py` |
| **`git_commit` 欄位** | `/api/version` 暴露完整 SHA 方便對照 | ✅ `routes/misc.py` |

### 28.2 Review 檢查清單（deploy／infra scope）

| 檢查 | 通過標準 |
|------|----------|
| `.deploy-version` 不在 git | `git ls-files .deploy-version` 為空 |
| `.gitignore` 含 `.deploy-version` | 已列 |
| `read_deploy_version()` | 有 `RENDER_GIT_COMMIT` fallback |
| `render.yaml` | `preDeployCommand` + `startCommand` 均含 `render-predeploy.sh` |
| 文檔 | README / AGENT_HANDOFF 有「Deploy 陷阱」一節 |

### 28.3 診斷步驟（用戶報 version 唔啱時）

1. `curl /api/version` → 比較 `version` vs `git_commit[:7]` vs `git rev-parse --short HEAD`
2. Render Events → 有無 `=== Render pre-deploy ===`
3. `git ls-files .deploy-version` → 唔應有輸出
4. 若 hook Accepted 但 version 未變 → 等 2–5 分或查 Failed deploy

### 28.4 Copy-paste 開場白（deploy 回歸審計）

```
【審計模式】
Baseline：GEMINI_REVIEW.md §27–§28（Render deploy SSOT，唔重複報已修項）
範圍：utils/deploy.py、render.yaml、deploy/render-predeploy.sh、.gitignore
基準 commit：2dc4c47
焦點：.deploy-version 唔入 git、preDeploy 必跑、version/git_commit 一致

輸出：【Critical】→【High/Medium】→【Low】→ 健康度 X/10
```

---

## 29. Render 死圖 + 勝利卡死（2026-07-02 · Gemini 戰鬥 audit · `df5acea`）

> **性質**：Gemini 報 Render 上「破圖」同「勝利後無畫面」。Grok Build **驗證後取捨** — 下一輪 **唔好重複報** 已拒絕／已 ship 項。

### 29.1 症狀與真實根因

| 症狀 | Gemini 假設 | 驗證後根因 |
|------|-------------|------------|
| 戰鬥 HUD 破圖 | `static/` 路徑錯、Linux 大小寫、`parasite_shadow.svg` 404 | **主因**：API 回傳裸檔名（`Mike.jpg`、`guardian_male_01.png`），V2 `hud_view` 直接設 `src` → 404。預設敵圖線上 **200 OK** |
| 勝利後卡死 | 勝利 payload 缺 `round_settlement` | **部分已修**（`5e8b3b6` `_json_victory_outcome`）。**殘餘**：FSM `skipModal` 跳過 VICTORY；SUBMITTING poll 釘死 phase |

### 29.2 Gemini 建議取捨表（審計時必讀）

| Gemini 建議 | 判斷 | 實際處理 | commit |
|-------------|------|----------|--------|
| `combat_status_api` / `combat_submit_action_api` 三處手動 `_attach_round_settlement` | ❌ **重複** | 已統一 `_json_victory_outcome()` | `5e8b3b6` |
| fallback `/static/images/default-enemy.svg`、`default-avatar.svg` | ❌ **檔案不存在** | 用 `parasite_shadow.svg` + `default.png` | `df5acea` |
| 檢查 `static/images/enemies/` 有無 SVG | ⚪ 無害但非主因 | 目錄正常；問題在 URL 組裝 | — |
| `combat_screen.html` / `hud_view` 加 `onerror` | ✅ **適用** | `avatar_urls.js` + `bindAvatarImage` | `df5acea` |
| `setupAvatarDefensiveCounters` 放 bootstrap | ⚪ 可選 | 整合入 `hud_view.update` 即可 | `df5acea` |
| Clear Build Cache & Deploy | ❌ **非必須** | 正常 CI Deploy Hook | — |
| `OIKONOMIA_ENDING_ENABLED=1` | ⚪ **無關卡死** | 結局功能開關；與 settlement/victory FSM 分開 | — |
| Persistent Disk + `DATA_DIR=/data` | ❌ **已配置** | `render.yaml` + `/api/version` 已驗證 | 見 §27、UPDATE_LOG |
| `combat/status` 減少 `advance` 呼叫 | ❌ **已做** | 僅 `player_phase`/`resolving` 才 advance | 見 UPDATE_LOG |

### 29.3 已修對照表

| 項目 | 狀態 | 檔案 |
|------|------|------|
| 勝利 JSON 必含 `round_settlement` + `settlement_id` | ✅ | `routes/combat.py` `_json_victory_outcome` |
| 玩家／主角頭像 URL 正規化 | ✅ | `models/combat.py` `_combat_player_avatar_url` |
| 敵人預設頭像 URL | ✅ | `models/combat.py` `_combat_enemy_avatar_url` |
| 前端 `onerror` + 路徑前綴 | ✅ | `static/js/combat/avatar_urls.js`、`views/hud_view.js` |
| 最後一擊已看結算 → 仍進 VICTORY | ✅ | `state_machine.js` `skipToVictory` |
| SUBMITTING poll 可推進 SETTLEMENT/VICTORY | ✅ | `state_machine.js` SUBMITTING `POLL_TICK` |

### 29.4 測試基線（`df5acea`）

```bash
npm run test:combat                                 # 29/29
./venv/bin/python3 scripts/test_combat_flow.py      # 297/297
```

### 29.5 實機驗證（Render）

1. 硬刷新或 `sessionStorage.clear()`
2. `practice_iggy_01_quick` 秒殺 → **傷害結算 Modal** → **勝利畫面**
3. `curl -s https://oikonomia.onrender.com/api/version` → `version` == `df5acea`
4. 靜態抽查：`curl -I …/static/images/enemies/parasite_shadow.svg` → 200

### 29.6 Copy-paste 開場白（Render 戰鬥回歸）

```
【審計模式】
Baseline：GEMINI_REVIEW.md §29（唔重複報已拒絕／已修項）
範圍：static/js/combat/state_machine.js + views/hud_view.js + routes/combat.py _json_victory_outcome
基準 commit：df5acea
焦點：最後一擊 settlement→victory 鏈、頭像 URL、唔建議 default-enemy.svg

輸出：【Critical】→【High/Medium】→【Low】→ 健康度 X/10
```

---

## 30. Gemini df5acea 跟進 audit（2026-07-02 · Grok Build 批判性審視）

> **用途**：示範當 Tak 提交 Gemini Audit Report 時，**Grok Build 點樣審視而唔盲目跟從**。Gemini 本輪 health **9.5/10** 大致認可 `df5acea`；以下係逐項取捨。

### 30.1 審視流程（永久協議）

| 步驟 | 負責 | 動作 |
|------|------|------|
| 1 | Tak | 提交 Gemini audit 全文或摘要 |
| 2 | Grok Build | 對照 `UPDATE_LOG`、§29、現行 code |
| 3 | Grok Build | `curl` / `grep` / 測試驗證每項主張 |
| 4 | Grok Build | 分類：採用／已 ship／拒絕／延後；**只改缺口** |
| 5 | Grok Build | 更新 §30 取捨表 + `UPDATE_LOG` + push |

### 30.2 本輪 audit 逐項取捨

#### 【Critical】頭像 URL SSOT（`models/combat.py`）

| Gemini 說法 | 審視 | 決定 |
|-------------|------|------|
| V1 用 `avatarSrc()` 拼接，V2 API 裸檔名致 `/Mike.jpg` 404 | ✅ **正確**（與 §29 一致） | 已在 `df5acea` 修 |
| 需審計等冪性與防呆 | ✅ 合理 | 後端 `_combat_*_avatar_url` **等冪**；前端 `avatar_urls.js` 雙重防呆 |
| 範例用 `enemy_avatar` 頂層 key、`avatar_url` 欄位 | ❌ **唔適用本 repo** | **拒絕** — schema 為 `encounter.enemy.avatar`；API 欄位 `avatar` |
| 範例只處理 `static/images/enemies/` | ❌ 不完整 | 已實作 avatars / portraits / enemies 三路徑 |

**結論**：唔改用 Gemini 範例 code；維持 `_combat_player_avatar_url` / `_combat_enemy_avatar_url`。

#### 【High/Medium】FSM `skipToVictory`（`state_machine.js`）

| Gemini 說法 | 審視 | 決定 |
|-------------|------|------|
| `skipModal` 導致卡 IDLE、進唔到 VICTORY | ✅ **正確**（submit 路徑） | `df5acea` 已加 `skipToVictory` |
| poll 時 `shownSettlementIds.has` 應直接 VICTORY | ✅ **已覆蓋** | `syncState` fallthrough → `Phase.VICTORY`（L315–329） |
| SUBMITTING poll 釘 phase | ✅ 已修 | `df5acea` SUBMITTING `POLL_TICK` |

**測試**：`poll victory with already-shown settlement → VICTORY`、`skipToVictory` 路徑（30/30）。

#### 【Low】靜態 JS 快取（`bootstrap.js`）

| Gemini 說法 | 審視 | 決定 |
|-------------|------|------|
| 手機易 cache 舊 V2 JS | ✅ 合理 | **採用改良版** |
| 硬編碼 `?v=df5acea` | ❌ 每次 deploy 要手改 | **拒絕** |
| Grok Build 改良 | ✅ | `bootstrap.js?v={{ deploy_version }}`（`read_deploy_version()`） |

#### 【Ops】實機驗證（非 code）

| 建議 | 決定 |
|------|------|
| 核對 `/api/version` == 當前 commit | ✅ 營會 SOP |
| 測試前 `sessionStorage.clear()` | ✅ §29.5 |

### 30.3 Gemini 輸出質量備註

- 認可 Grok 修復係好現象；但仍夾帶 **唔合 schema 嘅範例 code** — 以 repo 為準。
- 審計前自問：建議是否已在 §29 標為已 ship？

### 30.4 Copy-paste（Tak 提交新 audit 時俾 Grok Build）

```
Tak 提交咗 Gemini Audit Report。
請依 README「Gemini Audit 批判性審視」+ GEMINI_REVIEW §30：
逐項驗證、分類、只實作缺口、更新文檔，唔盲目 copy Gemini 範例 code。
```

---

## 31. iPhone Safari「登入失敗／檢查網絡」audit（2026-07-02）

> **症狀**：iPhone Safari 顯示「登入失敗，請重試或檢查網絡連線」，Wi‑Fi/5G 正常。  
> **審視**：Gemini 歸因 Cookie + DB lock + 10s 超時；**須 curl 驗證後取捨**。

### 31.1 逐項取捨

| Gemini 建議 | 審視 | 決定 |
|-------------|------|------|
| **根因 A**：Safari 吞 Cookie（缺 Secure/SameSite） | ❌ **不成立** | `app.py` L40–47 **已有** `Secure`+`Lax`+`HttpOnly`（`RENDER=true`）；`curl -D - POST /login` 見 `Set-Cookie: … Secure; SameSite=Lax` |
| 用 `DATA_DIR` 判定生產環境加 Cookie | ❌ **錯誤條件** | 應用 `RENDER` / `FLASK_ENV`（已用） |
| **根因 B**：SQLite `database is locked` | ⚠️ **部分成立** | `/login` 曾用裸 `sqlite3.connect`（無 WAL/busy_timeout）→ **已改** `get_db_connection` + `with_db_retry` |
| **10s → 25s** session 超時 | ✅ **採用** | `SESSION_FETCH_TIMEOUT_MS` / boot safety 25–28s |
| 登入表單 `fetch` 無超時 | ✅ **補充** | 改 `fetchWithTimeout` + 非 JSON/502/503 **具體錯誤**（唔再一律「網絡連線」） |
| 清除 Safari 網站資料 | ✅ **Ops SOP** | 舊 ghost cookie／快取時有效 |
| CORS 問題 | ❌ **不成立** | 同源 `credentials: 'same-origin'` |

### 31.2 真實根因（綜合）

1. **誤導性 UI**：`login()` `catch` 將逾時、502 HTML、JSON 解析失敗統稱「網絡連線」  
2. **登入 DB 路徑未硬化**：熱寫入競爭時 `/login` 可能 503（現回「伺服器忙碌」）  
3. **Render cold start**：偶發 502/503 → 應提示「伺服器喚醒」  
4. Cookie 配置 **非** 本輪缺口（已 ship）

### 31.3 驗證

```bash
curl -s -D - -o /dev/null -X POST https://oikonomia.onrender.com/login -d "squad_id=test&pin="
# 預期：HTTP 200；Set-Cookie 含 Secure; SameSite=Lax
./venv/bin/python3 scripts/test_combat_flow.py   # 297/297
```

**iPhone SOP**：設定 → Safari → 進階 → 網站資料 → 刪除 `onrender.com` → 重開 → 登入。

---

## 32. Android Chrome 登入 audit（2026-07-02 · 批判性審視）

> **症狀**：與 iOS 類似「登入失敗／網絡錯誤」。Gemini 歸因 DB lock、Ghost Cache、In-App Browser SameSite。

### 32.1 逐項取捨

| Gemini 建議 | 審視 | 決定 |
|-------------|------|------|
| SQLite `timeout=30` + busy wait | ❌ **重複** | `utils/db_tx.py` `get_db_connection` 已有 `timeout=30` + `PRAGMA busy_timeout=30000` + WAL；`database.py` 已用 |
| 在 `database.py` 另寫 `get_db_connection` | ❌ **拒絕** | SSOT 係 `utils/db_tx.py`，唔複製 |
| `/login` WAL + retry | ✅ **已 ship** | `a4a1248` `routes/auth.py` |
| `/login` 加 `Cache-Control: no-store` | ✅ **採用** | `auth_bp.after_request`（含 `/session/restore` 等） |
| `/status` 防快取 | ✅ **已 ship** + 補強 | `player_bp` 已有；`fallbackToNormalSession` 補 `appendCacheBust` |
| `bootstrap.js` ghost cache | ✅ **已 ship** | `?v={{ deploy_version }}`（`de27bfe`） |
| 10s 超時 | ❌ **已改** | `a4a1248` → 25s |
| WhatsApp/LINE 內建瀏覽器 Cookie | ⚠️ **環境限制** | 指引「在 Chrome 中開啟」；`restore_token` + localStorage 為 fallback |
| SameSite 改動 | ❌ **唔改** | 已 `Lax`；改 `None` 無助 In-App sandbox |

### 32.2 本輪實作缺口

| 項目 | 檔案 |
|------|------|
| Auth JSON 禁快取 | `routes/auth.py` `auth_dynamic_no_cache` |
| 登入後 `get_squad` 讀取走 WAL | `models/squad.py` |
| Session restore `/status` cache bust | `templates/index.html` `fallbackToNormalSession` |

### 32.3 Android 營會 SOP

1. Chrome → 網址列鎖頭 → **網站設定** → **清除並重設**
2. **勿用** WhatsApp/LINE 內建瀏覽器 →「在 Chrome 中開啟」
3. 核對 `/api/version` 為最新 commit
4. 仍失敗 → 具體 toast（喚醒／逾時／忙碌）唔再一律怪 Wi‑Fi

---

## 33. allocate_stats「分配失敗」audit（2026-07-02 · 批判性審視）

> **症狀**：配點畫面 toast「分配失敗，請稍後再試」。Gemini 先後給兩份矛盾報告。

### 33.1 逐項取捨（兩份 Gemini 報告對照）

| Gemini 說法 | 審視 | 決定 |
|-------------|------|------|
| **路由在 `player.py` 完全缺失 → 404** | ❌ **錯誤** | 路由在 **`routes/auth.py`** `@auth_bp.route("/allocate_stats")`；`grep` 可證；**唔**複製到 `player.py` |
| DB lock 導致 500 | ⚠️ **部分成立** | `update_squad()` 曾用裸 `sqlite3.connect`（無 WAL retry） |
| 應在 `player.py` 底部貼 Gemini 範例 | ❌ **拒絕** | 範例用裸 connect + `true` 小寫 bug；應用 `immediate_transaction` + `with_db_retry` |
| 前端應顯示 `data.error` | ⚠️ **半已做** | `!data.success` 已有；`catch` 仍模糊 → **已改** |
| 確認按鈕 `animate-pulse` | ✅ **採用**（Low） | 剩餘 0 點且已選頭像時 |

### 33.2 本輪修復

| 項目 | 檔案 |
|------|------|
| 配點寫入 `BEGIN IMMEDIATE` + `with_db_retry` | `routes/auth.py` `allocate_stats` |
| lock 時 503「伺服器忙碌，請再點一次」 | 同上 |
| 前端 timeout + JSON 錯誤分流 | `templates/index.html` `submitStatAllocation` |
| Smoke：`allocate_stats route (auth.py)` | `scripts/test_combat_flow.py` |

### 33.3 審計提醒（俾 Gemini）

- **`/allocate_stats` 從未在 `player.py`**；審計前應 `rg allocate_stats routes/`。
- 健康度 5/10（路由缺失）**不成立** — 實際為寫入路徑未硬化。

---

## 34. 戰鬥 HP 0 卡死 + HUD 空白 + 劇情破圖 audit（2026-07-02 · 批判性審視）

> **症狀**：進入戰鬥敵人 HP 顯示 0 且無法行動；HUD 能力值空白；劇情 Iggy 頭像藍色問號。

### 34.1 逐項取捨

| Gemini 說法 | 審視 | 決定 |
|-------------|------|------|
| **Critical**：`determineSettlementRoute` + 舊 `enemy_hp:0` 快照鎖死 FSM | ✅ **部分正確** | `syncState` 用 `snapshot.enemy \|\| ctx.hud.enemy` 在 entry 時可保留殘留 HP；`isKillingBlow` 曾把 `enemy.hp<=0` 當勝利信號 → **已修** `buildHudFromSnapshot` + 僅 `outcome/winner` 判定 killing |
| `createInitialContext` 加 `entrySyncPending: true` | ⚠️ **半重複** | `index.js` `onCombatStarted` 已設；維持 `false` 預設，由 entry 事件開啟 |
| **Critical**：`power_value` / `hp_value` 欄位不一致 | ❌ **不成立** | `grep` 全 repo 無此欄位；後端仍用 `hp`/`max_hp`/`sanity` |
| HUD 空白真因：`/combat/start` 缺 `my_state` | ✅ **正確** | start 只回 `enemy` → 首屏 `me: null`；**已修** start 附 `my_state` + `member_states` |
| `renderPlayerStatsSafely` 讀 `hp_value` | ❌ **拒絕** | 改 `hud_view` 用 `parseCombatHp` 防禦性解析既有欄位 |
| **High**：劇情 `line.portrait` 無正規化 / onerror | ✅ **正確** | `showCurrentStoryLine` 直接賦 `src` → **已修** 路徑拼接 + `onerror` 降級 `default.png` |
| **Low**：練習模式「離開戰鬥」 | ✅ **採用** | `combat_screen.html` `practice_*` 顯示 ⚙ 離開 → `exitCombatScreen({fromV2:true})` |

### 34.2 本輪修復

| 項目 | 檔案 |
|------|------|
| Entry HUD 嚴格覆蓋（唔 merge 舊 enemy） | `state_machine.js` `buildHudFromSnapshot` |
| `isKillingBlow` 僅勝利信號；`skipModal` 清 `isKillingBlow` | 同上 `determineSettlementRoute` / `SUBMIT_SUCCESS` |
| 開局先 `/combat/status` 再渲染 | `index.js` `onCombatStarted` |
| start API 附 `my_state` | `routes/combat.py` |
| HP bar `parseCombatHp` | `views/hud_view.js` |
| 劇情肖像 fallback | `templates/index.html` |
| 練習離開按鈕 | `combat_screen.html` + `hud_view.js` |
| FSM 測試 +2 | `tests/combat_state_machine.test.js`（32/32） |

### 34.3 審計提醒（俾 Gemini）

- V2 HUD **只渲染 HP 條**（非 dashboard 全屬性條）；神智等顯示在 dashboard／隊伍面板，唔係本輪 schema 錯位。
- 唔建議再引入 `hp_value`/`power_value` 平行欄位 — 會加劇前後端摩擦。

---

## 35. 41b9da1 跟進：HP 0 需 F5 + ES module 快取 audit（2026-07-02）

> **症狀**：部署 `41b9da1` 後，首進戰鬥仍見敵人 HP 0；**F5 後正常**。Gemini 建議硬編碼 `?v=41b9da1`。

### 35.1 逐項取捨

| Gemini 說法 | 審視 | 決定 |
|-------------|------|------|
| 手動 `bootstrap.js?v=41b9da1` | ❌ **拒絕硬編碼** | 已有 `?v={{ deploy_version }}`（`read_deploy_version()`） |
| ES module 子圖快取導致舊 `state_machine.js` | ✅ **正確根因** | 只 bust entry 唔 bust `./index.js` 依賴鏈 → **動態 `import(\`./index.js?v=\`)`** + `/static/js/combat/*.js` `no-store` |
| entry 時 poller 與手動 status 競態 | ✅ **正確** | **先** `await status` + `mergeEntryCombatPayload`，**後** `poller.start` |
| status 覆蓋 start 的 0 HP snapshot | ✅ **邊界** | `mergeEntryCombatPayload`：active `player_phase` 無 outcome 時保留 start HP |
| practice 重開 `shownSettlementIds` 隔離 | ✅ 已覆蓋 | `COMBAT_RESET` 清空 Set；殭屍戰鬥 **後端** 練習關卡 `enemy_hp<=0` 自動 `ended` |
| skipModal 鞭屍 | ⚪ **延後** | 需實機連點驗證；本輪先修 entry 0 HP |
| `/combat/start` 抽離 `combat_flow.py` | ⚪ **Phase 1.5** | 合理，非營會 hotfix |

### 35.2 本輪修復

| 項目 | 檔案 |
|------|------|
| Entry merge + poller 延後啟動 | `index.js` |
| `mergeEntryCombatPayload` | `settlement.js` |
| 動態 versioned import | `bootstrap.js` + `data-combat-bootstrap` |
| Combat JS `no-store` | `app.py` |
| 新戰 phase≤1 防 0 HP | `models/combat.py` `build_enemy_combat_stats` |
| 練習殭屍戰自動結束 | `routes/combat.py` |

### 35.3 現場 SOP（仍有效）

1. 核對 `/api/version` == 最新 commit  
2. 異常時 Safari/Chrome **清除網站資料**（唔止 `sessionStorage.clear()`）  
3. 練習關用 HUD「⚙ 離開戰鬥」後可再開；後端會清 `enemy_hp<=0` 殭屍紀錄

---

## 36. 戰鬥畫面能力值空白 audit（2026-07-02 · 批判性審視）

> **症狀**：V2 戰鬥介面完全無玩家能力值（神智／力量／智力／韌性）。Gemini 歸因快取 + `hp_value` fallback。

### 36.1 逐項取捨

| Gemini 說法 | 審視 | 決定 |
|-------------|------|------|
| 根因 1：CDN 快取舊 `hud_view.js` | ⚠️ **次要** | `43e9706` 已有 `deploy_version` + combat JS `no-store`；**非主因** |
| 根因 2：`isHpOnlyPhase` 鎖死能力值更新 | ❌ **不成立** | 即使 UPDATE_HUD 觸發，**DOM 節點根本不存在** |
| 硬編碼 `?v=41b9da1` | ❌ **拒絕** | 用 `deploy_version` |
| `hp_value` / `squad.power` fallback | ❌ **拒絕** | 後端 `my_state` 已有 `hp`/`sanity`/`power`/`intellect`/`resilience` |
| `renderPlayerStatsSafely` 範例 | ⚠️ **方向對、實作錯** | 需先 **補 `combat_screen.html` 節點** 再渲染 |

### 36.2 真實根因

**Greenfield V2 `combat_screen.html` 只實作了 HP 條**（`combat-v2-player-hp`），從未遷移 V1 的 `combat-player-sanity`／`combat-m-power` 等面板。後端資料齊全，前端缺 UI + `hud_view` 繪製邏輯。

### 36.3 本輪修復

| 項目 | 檔案 |
|------|------|
| 玩家神智條 + 三維值列 | `templates/combat_screen.html` |
| 敵人能力值列 | 同上 |
| `resolveCombatStats` + vitals 永遠更新（含 `hpOnly` poll） | `stats.js` + `hud_view.js` |
| entry 保留 `my_state` | `settlement.js` `mergeEntryCombatPayload` |
| marker `combat_stats_v2` | `routes/misc.py` → `combat-v2-player-power` |

---

## 37. 大廳 /status 髒快照 + 終端 poll 重複 audit（2026-07-02 · 批判性審視）

> **背景**：`9d31b63` 已釋放終端 stale guard 與 `releaseCombatBridgeLock()`。Gemini 擔心 SQLite 多 worker 下 `/status` 讀到未 COMMIT 的 `current_combat_id`，導致大廳/戰場閃爍死鎖。

### 37.1 逐項取捨

| Gemini 說法 | 審視 | 決定 |
|-------------|------|------|
| **Critical**：`/status` 回傳 ended 戰鬥的 `current_combat_id` | ✅ **正確** | `build_player_status` 直接 `**squad` 展開；`/session/restore` 與 `/encounters` 已有 reconcile，**`/status` 缺** → **已修** |
| 應強制清空 ended 的 `current_combat_id` | ✅ **採用** | `reconcile_status_combat_fields()` + `with_db_retry` 於 `GET /status` |
| Gunicorn worker Session 分裂 | ❌ **不成立**（本輪） | Flask signed cookie session；非本輪根因 |
| **High**：`syncState` 需 TERMINAL_PHASES 頂層攔截 | ✅ **已出貨** | `state_machine.js` L199 `ABSORBING.has(ctx.phase)` → `{ ctx, effects: [] }`；測試 `R12-D` |
| **Low**：大廳 `/status` fallback 加錯誤代碼 | ✅ **採用** | `describeStatusFetchError` + `[ERR_STATUS_*]` / `[ERR_DB_LOCK]` toast |

### 37.2 本輪修復

| 項目 | 檔案 |
|------|------|
| `/status` reconcile（與 restore/encounters 同 SSOT） | `services/player_status.py` + `routes/player.py` |
| Smoke：`test_status_reconcile_stale_current_combat_id` | `scripts/test_combat_flow.py` |
| Fallback 錯誤代碼 toast | `templates/index.html` |

### 37.3 審計提醒（俾 Gemini）

- 大廳 3s poll **唔會**因 `current_combat_id` 單獨重設 `COMBAT_V2_LOCK`；鎖重設主要經 `finishSessionRestore`。後端清空 ID 即可切斷污染鏈。
- `isPlayerInActiveCombatV2` 仍會在 `combat-root-v2` 可見時自保鎖定；`exitCombatScreen` 會 hide root + `clearActiveCombatBridge`。

---

## 38. GET /status 寫入飢餓 + SUBMITTING poll 搶占 audit（2026-07-02 · 批判性審視）

> **背景**：`81acdf1` 在 3s 大廳 poll 嵌入 `reconcile_finished_active_combat` 寫入。Gemini 擔心多 worker 併發 UPDATE → SQLite 飢餓 → `[ERR_DB_LOCK]`。

### 38.1 逐項取捨

| Gemini 說法 | 審視 | 決定 |
|-------------|------|------|
| **Critical**：GET /status 不應觸發寫入事務 | ✅ **正確** | 高頻 GET 改 **唯讀過濾** payload；DB heal 留在 end combat / restore / encounters |
| 唯讀 `_combat_is_finished_for_reconcile` 檢查 | ✅ **採用** | `reconcile_status_combat_fields` 僅 SELECT + 記憶體抹除 `current_combat_id` |
| **High**：SETTLEMENT 時 poll 不可搶占 SHOW_VICTORY | ✅ **已 ship**（`9d31b63`） | L299 `ctx.phase === SETTLEMENT`；測試 R12-D |
| SUBMITTING 關鍵幀 poll 搶占結算 | ✅ **部分正確** | 無 `round_settlement` 時 poll 曾直跳 VICTORY → **已修** SUBMITTING/WAITING hpOnly 護欄 |
| **Low**：Toast 錯誤代碼小字附註 | ✅ **採用** | `formatToastContent` + `text-[10px]` 第二行 |

### 38.2 本輪修復

| 項目 | 檔案 |
|------|------|
| `/status` 唯讀 reconcile（移除 `with_db_retry` 寫入） | `services/player_status.py` + `routes/player.py` |
| SUBMITTING/WAITING poll 不跳 VICTORY | `state_machine.js` |
| 測試 +1 | `combat_state_machine.test.js` |
| Toast 代碼附註樣式 | `templates/index.html` |

### 38.3 審計提醒（俾 Gemini）

- 唯讀 `/status` **唔清** `squads.current_combat_id` 實體列；僅防前端重鎖。寫入 heal 仍由 `/encounters`、`/session/restore`、戰鬥結束管線負責。
- `81acdf1` smoke test 已改為驗證 **response payload**，唔再要求 GET 清 DB 列。