# Oikonomia — Grok Build Handoff（新 Tab 必讀）

> **本檔給 Grok Build**（實作 Agent）。用戶會開新 tab 繼續開發；請**直接執行**，唔好只係話用戶點做。  
> **你的責任**：改 code → 驗證 → commit/push GitHub → **確保 Render.com 同 local 版本一致**（見 Deploy 一節）。PA 僅後備。  
> 最後更新：2026-07-02 · **commit 見 `/api/version`**（重開戰鬥 remount + entry merge 修復）· BUG-2026-001 **monitoring**

| 角色 | 文檔 | 職責 |
|------|------|------|
| **Grok** | `README.md` | 方向、優先級、架構取捨（唔改 repo） |
| **Grok Build（你）** | **本文** | 實作、測試、push、備份、部署 |
| **Gemini** | `GEMINI_REVIEW.md` | 第三方 review / debug（唔改 repo） |

**本檔副本**：`Documents/oikonomia/AGENT_HANDOFF.md` 與 Google Drive `My Drive/oikonomia/AGENT_HANDOFF.md` 應保持同步。

---

## Gemini Audit 批判性審視（Grok Build 必守 · 永久）

> **觸發**：Tak 貼上 Gemini Audit Report、Critical Issues 清單、或「請照 Gemini 做」。

**禁止**：未驗證就 copy-paste Gemini 範例 code、未讀 SSOT 就重複已 ship 修復。

### 審視流程（每份 audit 必跑）

```
收到 Gemini 建議
  → 讀 UPDATE_LOG + GEMINI_REVIEW §29–§30
  → 逐項 grep / curl / 跑測試驗證
  → 分類：採用 | 已 ship | 拒絕 | 延後
  → 只實作缺口 + 更新文檔取捨表
  → commit / push / 驗證 /api/version
```

### 分類標準

| 標記 | 意思 | 例子 |
|------|------|------|
| ✅ 採用 | 驗證後確實缺失 | `avatar_urls.js` onerror |
| ✅ 已 ship | repo 已有，Gemini 重複報 | `_json_victory_outcome`（`5e8b3b6`） |
| ❌ 拒絕 | 錯因、錯 schema、檔案不存在 | `default-enemy.svg`；`encounter.enemy_avatar` 頂層 key |
| ⚪ 延後 | 合理但非本輪／有更好的做法 | 硬編碼 `?v=df5acea` → 改用 `deploy_version` |

### 最新範例（Gemini df5acea 跟進 audit · 見 §30）

| Gemini 項 | 審視結果 |
|-----------|----------|
| Critical：後端頭像 URL SSOT | ✅ **已 ship**（`_combat_*_avatar_url`）；❌ 拒絕其範例（`avatar_url` 欄位名、`enemy_avatar` schema 錯） |
| High：skipToVictory / poll→VICTORY | ✅ **已 ship**（`df5acea`）；`syncState` poll 路徑已覆蓋已看結算 |
| Low：bootstrap.js cache bust | ✅ **採用改良版**：`?v={{ deploy_version }}`（`routes/misc.py`），唔硬編碼 commit |
| Ops：`/api/version` + `sessionStorage.clear()` | ✅ 記入文檔；唔改 code |

### 戰鬥 HP 0 卡死 + HUD + 劇情破圖（Gemini audit · §34）

| Gemini 項 | 審視 |
|-----------|------|
| FSM 殘留 `enemy_hp:0` + `skipModal` | ✅ `buildHudFromSnapshot`；`isKillingBlow` 僅 `outcome/winner` |
| `power_value` / `hp_value` mismatch | ❌ 欄位不存在；真因係 `/combat/start` 缺 `my_state` |
| 劇情 portrait 404 | ✅ `showCurrentStoryLine` 路徑 + `onerror` |
| 練習離開戰鬥 | ✅ `practice_*` HUD 按鈕 |

### Safari / Android 登入（Gemini audit · §31–§32）

| Gemini 項 | 審視 |
|-----------|------|
| Cookie Secure/SameSite | ❌ **已 ship**（`app.py`） |
| SQLite timeout=30 / WAL | ❌ **已 ship**（`utils/db_tx.py`）；唔在 `database.py` 複製 |
| `/login` WAL + retry | ✅ `a4a1248` |
| Auth `/login` no-cache headers | ✅ `auth_bp.after_request` |
| `get_squad` 登入後讀取 | ✅ 改 `get_db_connection` |
| Android ghost cache | ✅ `deploy_version` + `fetchNoCache` / fallback cache bust |
| In-App Browser（WhatsApp） | ⚪ SOP：用 Chrome 開啟 |

---

## Context 管理協議（Grok Build 必守 · 2026-06-30）

> **目的**：防 context 溢出、代碼腰斬、幻覺。長對話**唔使**開新 Chat，但必須嚴格局部交付。

### Baseline（只引用，唔貼全文）

| 檔案 | 版本 | 生成 |
|------|------|------|
| `COMBAT_V2_AUDIT_BUNDLE.md` | **v12**（SSOT · R11/R12 封頂） | `python3 scripts/build_combat_v2_audit_bundle.py` |
| `COMBAT_V2_PARTIAL_INDEX.md` | R11 + R12-A～D 導航 | `python3 scripts/build_combat_v2_partial_bundles.py` |
| `COMBAT_V2_R11_PARTIAL_BUNDLE.md` | R11 局部審計 A/B/C | （同上腳本一併生成） |
| `combat_greenfield_final.md` | 綠地規格 | repo 內建 |

新功能（遭遇戰 JSON、GPS 任務路由、物品發放等）開發時：**假設 Baseline 已讀**，只貼本次改動嘅**單一檔案或單一函數**。

### 進門對齊模式（訊息最開頭）

用戶會標 **【開發模式】** 或 **【審計模式】**。未標時，預設 **【開發模式】**。

| 模式 | Grok Build 回應 |
|------|-----------------|
| **【開發模式】** | **零前言** → 100% 完整、可 Copy-and-Paste 的生產級代碼 + 專項單元測試（唔擴散無關檔案） |
| **【審計模式】** | **【Critical】→【High/Medium】→【Low】→ 健康度總評**（1–10）；唔輸出大段代碼除非指出具體行號 |

### 局部交付規則

1. **一次一個 scope**：一個 `routes/*.py` 函數、一個 `services/*.py` 模組、或一個 `static/js/combat/views/*.js`。
2. **唔貼** `COMBAT_V2_AUDIT_BUNDLE.md` 全文、`index.html` 全文、`models/combat.py` 全文。
3. **改完必跑** 與 scope 對應嘅測試（見下方測試速查）；全量 regression 僅在 Phase 封頂或 deploy 前。
4. **引用 Baseline** 用檔名＋符號名，例如：`api_client.overrideTraumaEnding`、`routes/gm.py` `gm_override_trauma_ending_api`。

### 建議用戶提交範本

```
【開發模式】
目標：新增 enc_marah_02 JSON 並接上 precheck
檔案：encounters/enc_marah_02_*.json + models/encounter.py（load 驗證）
約束：唔改 combat FSM；test_encounter_catalog 必過
```

### 測試速查（按 scope）

| Scope | 最低驗證 |
|-------|----------|
| Combat 後端 | `./venv/bin/python3 scripts/test_combat_flow.py`（302/302） |
| DB 併發/SSOT | `./venv/bin/python3 scripts/test_db_hardening.py`（14/14） |
| 計算層/編排 | `./venv/bin/python3 scripts/test_combat_engine.py` + `test_combat_flow_orchestrator.py` |
| Combat 前端 | `npm run test:combat`（42/42）+ `npm run test:e2e:v2` |
| Co-op 併發 | `./venv/bin/python3 scripts/test_combat_concurrency.py` |
| GM override | `test_phase2_gm_override_gateway`（在 combat_flow 內） |
| Encounter JSON | `test_encounter_catalog()` |
| Deploy 前 | `bash scripts/pre_deploy_checks.sh` |

---

### Bug Log（難解 bug — Drive SSOT）

| 路徑 | 用途 |
|------|------|
| **Drive** `My Drive/oikonomia/bug_log/` | 長篇調查檔 + attachments（**SSOT**） |
| **Repo** `bug_log/` | 與 Drive 同步副本，方便 commit 引用 |

- 先讀 **`bug_log/README.md`**（Purpose、幾時開 case）
- 活躍 case 見 **`bug_log/INDEX.md`**
- 與 `UPDATE_LOG.md`（短）、`decisions_log.md`（決策）分工

**現有 case**：BUG-2026-001 戰鬥敵 HP／settlement → **monitoring**（legacy `12e1edd` Henry solo 已過；V2 重構 `af30b2b` 後需營會實機封頂 — 見 `bug_log/INDEX.md` · `UPDATE_LOG.md` §37–40）

---

## 版本狀態（開 tab 第一件事要核對）

| 環境 | Commit | 狀態 |
|------|--------|------|
| **Local** | `git rev-parse --short HEAD` | 開工前核對 |
| **GitHub `main`** | 同上 | push 後應一致 |
| **Render（正式）** | 核對 `/api/version` | 必須與 `main` 相同；`render: true`、`data_dir: /data` |
| **PythonAnywhere（後備）** | 可選核對 | 非主線；僅 rollback 時更新 |

```bash
# 本地
cd /Users/mingtakyau/Documents/oikonomia && git rev-parse --short HEAD

# Render 正式環境（應回 JSON；502 多為 deploy 重啟中，等 1–2 分鐘再試）
curl -s https://oikonomia.onrender.com/api/version | python3 -m json.tool

# PA 後備（可選）
curl -s https://takjai.pythonanywhere.com/api/version | python3 -m json.tool
```

**Local、GitHub `main`、Render 三邊 `version` 必須相同**才算部署完成。同時核對 `git_commit` 前 7 字元與 `version` 一致。每次 push 後 CI 會觸發 Deploy Hook；若落後可手動 `bash deploy/render-sync.sh`。

**若 `version` 舊但 `render: true`**：先讀下方「Render Deploy 陷阱」— 可能係誤 commit `.deploy-version` 或 Dashboard 未跑 preDeploy，唔好誤判 code 未上線。

### 本地測試

```bash
bash scripts/pre_deploy_checks.sh                        # 部署／CI 閘門（188+ 項）
./venv/bin/python3 scripts/test_combat_flow.py           # 戰鬥 smoke（含 settlement breakdown）
./venv/bin/python3 scripts/test_encounter_cache.py       # 預期：3 通過 / 0 失敗
```

---

## 本輪已完成（2026-07-02 — Render 死圖 + 勝利卡死 · `df5acea`）

> **背景**：Gemini Render 戰鬥 audit 報「破圖」同「勝利後卡死」。Grok Build **先驗證再改** — 見 `GEMINI_REVIEW.md` §29、`UPDATE_LOG.md` 同章。

| Commit | Scope | 摘要 |
|--------|-------|------|
| `5e8b3b6` | 後端 | `_json_victory_outcome` 統一附 `round_settlement`（**Gemini 三處 patch 已涵蓋**） |
| `9e6dca9` | Infra | `ProxyFix`（`RENDER=true`）；Persistent Disk **早已有** |
| `df5acea` | 前後端 + FSM | 頭像 URL 正規化 + `onerror`；`skipToVictory`；SUBMITTING poll 唔再釘死 phase |

### Gemini 建議取捨（本輪）

| 建議 | 判斷 | 處理 |
|------|------|------|
| 三處 `build_victory_outcome_response` 後加 `_attach_round_settlement` | ❌ **重複**（`5e8b3b6` 已有 `_json_victory_outcome`） | 唔改 |
| fallback `default-enemy.svg` / `default-avatar.svg` | ❌ **路徑錯**（repo 無檔） | 用 `/static/avatars/default.png`、`/static/images/enemies/parasite_shadow.svg` |
| `parasite_shadow.svg` 在 Render 404 | ❌ **不成立**（線上 HTTP 200） | 唔改靜態目錄 |
| V2 缺 `onerror` + API 裸檔名 | ✅ **根因** | `avatar_urls.js` + `models/combat.py` 正規化 |
| FSM：`skipModal` 殺死最後一擊勝利 | ✅ **補充根因**（Gemini 未點名） | `determineSettlementRoute` → `skipToVictory` |
| Clear Build Cache & Deploy | ⚪ **非必須** | 正常 `git push` + CI hook 即可 |
| `OIKONOMIA_ENDING_ENABLED=1` | ⚪ **與戰鬥卡死無直接關係** | 結局功能要開先設 |

**測試基線（`df5acea`）**：`test_combat_flow` 297/297 · `npm run test:combat` 29/29

**實機驗證**：硬刷新或 `sessionStorage.clear()` → `practice_iggy_01_quick` 秒殺 → 結算 Modal → 勝利畫面；`curl …/api/version` → `df5acea`

---

## 本輪已完成（2026-07-02 — 大廳鎖 + Breakdown 等冪 · `af30b2b`）

> **背景**：Gemini §37–40 audit。詳見 `GEMINI_REVIEW.md` §37–40、`UPDATE_LOG.md` 同日期條目。

| Commit | Scope | 摘要 |
|--------|-------|------|
| `9d31b63` | FSM + 大廳 | 終端 outcome bypass stale guard；`releaseCombatBridgeLock` on SHOW_VICTORY 等 |
| `81acdf1` | `/status` | `reconcile_status_combat_fields` 清 payload 髒 `current_combat_id` |
| `2e3d00e` | `/status` | 高頻 GET 改**唯讀**過濾（移除 reconcile 寫入）；`[ERR_STATUS_*]` toast |
| `9debc8d` | FSM + start + UI | killing blow `skipToVictory` 修正；`absorbStaleSettlementOnEntry`；start 顯式 `active`；`#my-team-card` |
| `af30b2b` | FSM 等冪 | `determineSettlementRoute` phase-aware：VICTORY/TERMINAL 已 ack → `skipModal`；僅 `SUBMITTING` 假陽性可重開 SETTLEMENT |

**測試基線（`af30b2b`）**：`test_combat_flow` **302/302** · `npm run test:combat` **40/40**

**Render 核對**：`curl -s https://oikonomia.onrender.com/api/version` → `version` / `git_commit` 前 7 字 = **`af30b2b`**

---

## 營會前實機驗收清單（終極防禦版 · `af30b2b`+）

> **前置（現場技術人員）**：Safari/Chrome 清除網站資料，或控制台執行：
>
> ```javascript
> sessionStorage.clear();
> localStorage.removeItem('oikonomia_restore_token'); // 可選；全清用 localStorage.clear()
> ```
>
> 確認 `curl -s https://oikonomia.onrender.com/api/version` → `version` ≥ **`af30b2b`**（doc commit 可能為 `3fc065e`）。

| # | 場景 | 操作 | 通過標準 |
|---|------|------|----------|
| 1 | 秒殺時序鏈 | 力量 ≥40 進 `practice_iggy_01_quick` 一輪擊殺 | **先** Breakdown（Rice/Iggy 輸出統計）→ 確定 → **再**勝利 → 回大廳 Dashboard 對齊；**唔**直跳勝利／大廳 |
| 2 | ACK 暴力等冪 | 結算 Modal 用**三指連點確定 5+ 次**，或點擊瞬間切 Wi-Fi/5G | 唔卡死、唔重複彈窗、唔拋 `[ERR_STATUS_*]`；完成後才進勝利 |
| 3 | 連續開局重置 | **唔關頁**，同一練習關完成並重開 **5 次** | 第 2–5 次首屏敵 HP 為滿血；能力值唔顯示 `—`；全程**唔需 F5** |
| 4 | 戰後大廳同步 | 隊長最後一擊 → 結算 → 勝利 → 回大廳 | 3s 內 Dashboard／遭遇列表更新；無「進行中」；**唔需 F5** |
| 5 | 雙人同隊併發 | 兩台手機同 Team，倒數 **3-2-1 同時按攻擊** | 一台成功提交；另一台 **400「本回合行動已提交」** 或「等待隊友」；**唔** 500／SQLite 鎖死 |
| 5b | 隊長先退、隊員跟隨 | 隊長勝利離開後，隊員**唔 F5** 等 3s poll | 隊員大廳自動解鎖、Dashboard 對齊（`/status` 唯讀過濾） |
| 6 | 弱網重連 | 戰鬥中斷網 5s 再連 | 唔重複 settlement；唔閃爍大廳／戰場 |

**失敗時記錄**：`/api/version`、encounter_id、Network 中 `/combat/submit` + `/combat/status` JSON、HTTP 狀態（400 vs 500）、`[ERR_STATUS_*]` / `[ERR_DB_LOCK]` toast。

### 後端併發 SSOT（審計備忘 · 唔使再 patch 除非實機 500）

| 機制 | 位置 | 行為 |
|------|------|------|
| 重複提交攔截 | `routes/combat.py` L461 | `combat_action_already_submitted` → **400**「本回合行動已提交」 |
| 行動 upsert 等冪 | `models/combat.py` `upsert_combat_action` | `ON CONFLICT(combat_id, squad_id, phase) DO UPDATE` — 同玩家同回合唔會雙行 |
| 結算 resolve 護欄 | `maybe_resolve_player_phase` | 回合已前進則跳過重複 settlement（見 `models/combat.py` 註解） |
| 大廳髒 combat id | `reconcile_status_combat_fields` | `/status` **唯讀**清 payload；DB heal：`/encounters`、`/session/restore`、`_end_combat` |

**網路超時**：`SESSION_FETCH_TIMEOUT_MS` 已為 **25000**（`templates/index.html`）— 高於 Gemini 建議的 20s，唔使再改。

---

## 已知邊界／待觀察（非 code 缺口 · 文檔 SSOT）

| 項目 | 狀態 | 說明 |
|------|------|------|
| `squads.current_combat_id` DB 殘留 | ⚪ 已知邊界 | `/status` 唯讀只清 payload；實體列由 `/encounters`、`/session/restore`、戰鬥結束 heal |
| `/combat/start` COMMIT 慢於 status SELECT | ⚪ 已知邊界 | `mergeEntryCombatPayload` + start 顯式覆蓋已緩解 |
| Render 高併發 `[ERR_DB_LOCK]` | ⚪ 監控 | `/status` 已唯讀；login／配點等寫入仍可能撞鎖 |
| `skipModal` 鞭屍（極端連點） | ⚪ 延後 | §35；需實機連點驗證 |
| 雙人隊／主線 encounter | ⚪ 覆蓋不足 | Henry 主測 solo；清單 **#5 / #5b** 為營會封頂必跑 |
| 同隊雙擊攻擊 race | ✅ code 已有 | `ON CONFLICT` + 400 攔截；實機用清單 #5 驗證 |
| WhatsApp 內建瀏覽器 | ⚪ SOP | 改用 Chrome 開啟 |

---

## 專案概覽

| 項目 | 值 |
|------|-----|
| 專案路徑 | `/Users/mingtakyau/Documents/oikonomia` |
| Google Drive 備份 | `~/Library/CloudStorage/GoogleDrive-ymtwill@gmail.com/My Drive/oikonomia` |
| 主檔 | `app.py`（~980 行：Flask init、DB migrate、`register_blueprints`） |
| 玩家 UI | `templates/index.html`（~6200 行 JS/HTML） |
| 主角狀態 | `models/protagonist.py` + `protagonist_states` 表 |
| 資料庫 | 本地 `./oikonomia.db`；Render `/data/oikonomia.db`；PA `data/oikonomia.db` |
| GitHub | https://github.com/Takjai18/oikonomia |
| **正式環境** | https://oikonomia.onrender.com（Render Starter · Singapore · `srv-d8v8i7cvikkc73fbsv0g`） |
| GM 後台 | https://oikonomia.onrender.com/gm （PIN: `gm2026` 或 env `GM_PIN`；session 8 小時過期） |
| 後備環境 | https://takjai.pythonanywhere.com（僅 rollback） |
| 本地開發 | `source venv/bin/activate && python3 app.py` → http://localhost:5001 |
| 測試帳號 | `test_squad_01`（開發）；**Henry** `PLAYER-75406`（Iggy solo 實機主測） |

**主題**：Summer Camp 2026 ARG（Oikonomia 青年營會），Iggy / Marah 雙主角路線。

---

## 架構（2026-06-29 重構後）

```
app.py                    # Flask init, migrate_db(), register blueprints
wsgi.py                   # Production 入口（Render gunicorn / PA WSGI）
render.yaml               # Render Blueprint（Starter、/data 持久碟）
deploy/render-*.sh        # Render 部署、檢查、觸發 hook
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

1. **Agent 要自己執行** — 改 code、跑測試、`git commit`、`git push`、觸發 Render deploy、驗證 `/api/version`；唔好淨係出 instruction。
2. **每次有 code 改動都要同步三處** — local → GitHub → **Render**；用 `https://oikonomia.onrender.com/api/version` 驗證 `version` 與 commit 一致。
3. **改 code 要考慮 Render 架構** — `DATA_DIR=/data` 持久碟、gunicorn 多 worker、`RENDER=true`；上傳／DB／secrets 唔好寫死 repo 路徑。
4. **Agent 通常無法 SSH Render/PA** — push 後靠 CI Deploy Hook 或 `deploy/render-sync.sh`；PA 僅 rollback 時請用戶跑 `pa-update.sh` + Reload。
5. **唔好亂改無關檔案** — `encounters/*.json` 係 encounter 定義；改架構前先 grep 確認檔案位置。
6. **唔好 commit `*.db`** — 已在 `.gitignore`。
7. **唔好 commit `.deploy-version`** — 部署產物（`.gitignore`）；commit 會令 `/api/version` 長期顯示舊 hash（見 UPDATE_LOG § 2026-07-02 version 假陽性）。

---

## Render Deploy 陷阱（必讀 · 2026-07-02）

> **教訓**：曾誤將 `.deploy-version`（內容 `3017e16`）commit 入 git，加上 Dashboard 未執行 `preDeployCommand`，導致 `/api/version` 長期與 `main` 不符，但服務其實已跑較新 code。

### 版本 SSOT 鏈（`utils/deploy.py`）

```
1. 專案根 .deploy-version（preDeploy / start 時 render-predeploy.sh 寫入）
2. 若無檔案 → 環境變數 RENDER_GIT_COMMIT 前 7 字元
3. 否則 → "unknown"
```

`/api/version` 另回傳 **`git_commit`**（完整 SHA）供對照 Render Dashboard 的 deploy commit。

### Agent push 前檢查

```bash
git status   # 唔應出現 .deploy-version、*.db、deploy/artifacts/
git diff --cached --name-only | grep -E '^\.deploy-version$' && echo 'BLOCKED' && exit 1
```

### Deploy 後驗證（必做）

```bash
LOCAL=$(git rev-parse --short HEAD)
curl -s https://oikonomia.onrender.com/api/version | python3 -m json.tool
# version == LOCAL；git_commit[:7] == version；render: true；data_dir: /data
bash deploy/render-check.sh https://oikonomia.onrender.com
```

### Render Events log 應見

```
=== Render pre-deploy (DATA_DIR=/data) ===
deploy-version: <git short hash>
...
=== Render pre-deploy done ===
```

若 **Build successful** 後直接 **Running gunicorn**、無上述字樣 → Dashboard 未設 Pre-deploy，且 Start Command 未含 `render-predeploy.sh`。請對齊 `render.yaml` 或請用戶改 Dashboard。

### 常見假陽性

| 現象 | 可能原因 | 處理 |
|------|----------|------|
| `version` 舊、`git_commit` 新 | 已修（`2dc4c47`）；舊環境仍有 commit 的 `.deploy-version` | 確保 repo 無 `.deploy-version`；redeploy |
| `version` 舊、`git_commit` 缺 | 極舊 code 或 env 未注入 | 確認 GitHub 連接 + Manual Deploy latest |
| Hook Accepted 但 version 唔變 | Deploy 進行中（等 2–5 分）或 build 失敗 | 查 Events；`bash deploy/render-sync.sh` |

---

## 本輪已完成（2026-07-01 — R11/R12 審計封頂 · `0e2fa93`）

### R11 現場風險 + R12 四向修復（`7823a95` → `0e2fa93`）

| Commit | Scope | 摘要 |
|--------|-------|------|
| `7823a95` | **R11 A/B/C** | GM `resolveAuthoritativeTeamId` 人工核對；`gm_operator` 403；timeout mutex + `performActionDirectly`；`_wait_after_peer_resolve` monotonic |
| `b931b37` | **R12-A** | `OIKONOMIA_COMBAT_V2_LOCK` + `ACTIVE_COMBAT_ID` sessionStorage；`finishSessionRestore` DOM-first；單向 `exitCombatScreen` |
| `3bd8d36` | **R12-B** | `get_db_connection` in `init_db`；atomic `_end_combat` / `reconcile_finished_active_combat` + purge actions |
| `0e2fa93` | **R12-C** | `resolve_combat_outcome` 移除外層 retry race；piercing floor；`failed_escape` 零傷害 guard |

**測試基線（`0e2fa93`）**：`test_combat_flow` 267/267 · `test_db_hardening` 11/11 · `test_combat_engine` 17/17 · `npm run test:combat` 17/17 · `test_combat_concurrency` OK

**下一輪 Gemini 審計**：貼 `COMBAT_V2_PARTIAL_INDEX.md` + **單一** R12/R11 Partial（regression / 新功能 only）；對照 `GEMINI_REVIEW.md` §18 唔重複報已修項。

### Combat V2 前端模組化（`7029bfd` → `15f2c37`+）

| Commit | 摘要 |
|--------|------|
| `7029bfd` | Entry sync monotonic align — `entrySyncPending` 防幽靈 settlement modal |
| `bf490f6` | Lobby reconcile ended combat + `fetchNoCache`；修 `current_combat_id=NULL` |
| `f267cec` | Atomic start gate、`advance_combat_from_poll`、rescuer validation |
| `ee9a691` | INV-D defeat roster、INV-E escape、monotonic FSM、engine targeting |
| `15f2c37` | `services/combat_flow.py`、victory `settlement_id`、piercing damage、outcome 冪等 |
| `223f8c6` | `index.html` V2 橋接：`isPlayerInActiveCombatV2()` 隔離 3s poll；`exitCombatScreen({fromV2})`；HP bar `transition:none` |
| *latest* | P0 DB hardening：SQLite WAL、`purge_combat_actions`、session restore fast-forward、protagonist SSOT |

**架構**：

```
templates/index.html          # 大廳橋接（startEncounter / exitCombatScreen / loadEncounters）
templates/combat_screen.html  # V2 DOM 骨架（combat-v2-* ID）
static/js/combat/
  bootstrap.js                # COMBAT_V2 feature flag → window.combatV2
  index.js                    # CombatApp + ResilientPollingManager
  state_machine.js            # Phase FSM + INV-A/C/D/E + skipToVictory
  avatar_urls.js              # 頭像 URL 正規化 + onerror fallback
  settlement.js               # settlement_id / monotonic guard
  api_client.js               # Passive poll（IDLE 1200ms / WAITING 800ms）
  views/*.js                  # escape_result / failed_panel / settlement / victory
```

**關鍵前端符號**（`static/js/combat/`）：

| 符號 | 用途 |
|------|------|
| `entrySyncPending` | 進入戰鬥首輪 poll 吸收殘留 settlement（INV-C） |
| `determineSettlementRoute` | Monotonic guard — 拒絕 stale `settled_round_index` |
| `deriveSettlementId` | `{combat_id}:{settled_round_index}` |
| `ResilientPollingManager` | 動態 poll；取代舊 inline 3s timer（戰鬥中） |
| `isPlayerInActiveCombatV2()` | `index.html` — sessionStorage lock + DOM fallback；暫停全局 3s `/status` poll |
| `OIKONOMIA_COMBAT_V2_LOCK` | sessionStorage 權威鎖（F5 / 斷線重連空窗期） |
| `exitCombatScreen` | 單向清理：`destroy()` + 清除 lock；`exitToLobby` 委派 `{fromV2:true}` |

**後端 Step 4**（`services/combat_flow.py` + `combat_outcomes.py`）：

| 符號 | 用途 |
|------|------|
| `normalize_failed_escape_actions` | INV-E — 逃跑失敗者留分母、零輸出 |
| `process_mixed_round_actions` | 純編排（單元測試）；生產路徑仍用 `models/combat.py` resolve body |
| `build_victory_outcome_payload` | 含 `settlement_id` + `settled_round_index` |
| `resolve_combat_outcome` | Pipeline 內建 `immediate_transaction` 冪等；**無**外層 `with_db_retry` race |
| `_end_combat` | 單一 `immediate_transaction`：ended + purge actions + clear squad locks |

**戰鬥 V2**：預設開啟（`utils/combat_v2_flag.py` · `data/.combat_v2`）；GM `/gm/api/combat_v2` 開關；`/api/version` → `combat_v2`。

**Henry 實機待驗**（V2 · `af30b2b` 後 — 見上方「營會前實機驗收清單」）：

| 場景 | 預期 | 清單 # |
|------|------|--------|
| 秒殺 Breakdown → 勝利 | 結算先於勝利 Modal | 1 |
| ACK 後等冪（連點／切網） | 唔重複結算彈窗 | 2 |
| 進戰首屏 HP | 唔要 F5 | 3 |
| 勝利後回大廳 | Dashboard 同步；無進行中戰鬥 | 4 |
| 弱網重連 | 唔重複 settlement（INV-C） | 6 |
| A 逃跑失敗 + B 攻擊 | B 傷害正常結算（INV-E） | 5（雙人延伸） |
| COMBAT_FAILED | `failed_panel.js` 獨佔；舊 overlay 唔疊加 | — |

### 戰鬥流程重構（`387c89b` → `12e1edd` · legacy inline）

| Commit | Marker | 摘要 |
|--------|--------|------|
| `66f70c6` | `enemy_hp_sync_v7` | Practice fast settlement；poll HP 同步 |
| `d061aa2` | — | 移除人工 delay（instant settlement；marker 字串已移除） |
| `387c89b` | `combat_flow_v2` | 精簡結算 modal；按「確定」先扣主畫面 HP |
| `03cf917` | `combat_flow_v3` | **取消**「本回合預計傷害」預覽（唔再 call `preview_action`） |
| `46cc3a5` | `combat_flow_v4` | 勝利不重複結算；已確認回合可進下一輪 |
| `c621354` | `settlement_breakdown_v1` | 結算畫面：Player／主角／隊友 輸出＋承受＋敵人總計 |
| `cc5671d` | `combat_flow_v5` | 按「確定，查看勝利」後唔再彈 1～2 次結算（victory flow lock） |
| `ebe49ff` | `combat_flow_v6` | 一輪擊殺必出 settlement modal |
| `12e1edd` | `combat_flow_v7` | 勝利結算期停 poll；確認後唔重彈結算 |

**現行玩家流程（`combat_flow_v7`）**：

```
選行動 → 擲骰（攻擊/Zoo）→ 確認並結束本回合 → (等隊友) → 傷害結算 modal → 確定 → 主畫面扣血 → 下一輪
擊殺回合 → 結算 modal（確定，查看勝利）→ 勝利畫面（只應出現一次結算）
```

**關鍵前端符號**（`templates/index.html`）：

| 符號 | 用途 |
|------|------|
| `showCombatConfirmStep()` | 擲骰後直接出確認掣（無預計傷害） |
| `showFullRoundSettlement()` | 顯示結算 modal；`deferEnemyHp` 主畫面暫唔扣血 |
| `applyPendingSettlementHp()` | 按「確定」後即刻扣血 |
| `renderSettlementBreakdown()` | Player／主角／隊友／敵人 分類傷害 |
| `isVictoryFlowLocked()` | 勝利確認後鎖，防 poll 重彈結算 |
| `victorySettlementAcknowledgedCombatId` | 已確認勝利結算嘅 combat_id |
| `resetCombatSessionState()` | 新 encounter／離開戰鬥時清狀態 |

**後端** `models/combat.py` → `_round_settlement_from_logs()` 回傳 `breakdown.dealt/taken/enemy` + `player_hits[].role`。

**Henry 實機**（2026-06-30 · **通過** · Safari 硬刷新 · `PLAYER-75406`）：

| 場景 | 結果 |
|------|------|
| `practice_iggy_04_marathon` 長戰打到贏 | ✅ 結算只 1 次 → 勝利 |
| `practice_iggy_03_boundary` 多回合 | ✅ R2 攻擊有反應；再開同一 encounter 正常 |
| 結算 breakdown | ✅ Player／主角／隊友 輸出＋承受＋敵人總計 |
| 勝利後 | ✅ 唔再彈重複傷害結算 |

### Henry instant settlement 專項（線 A · ✅ checklist OK · v8 deploy 驗殘留）

主 checklist（§16）已 pass；Architect 另開 **instant 專項** — 詳見 `bug_log/.../REPORT.md` §17。

| Encounter | 測咩 |
|-----------|------|
| `practice_iggy_01_quick` | 一輪殺 + killing blow settlement 即時 |
| `practice_iggy_03_boundary` | 多回合 HP 即時 + modal <1.5s |

**通過標準**：HP 即時 · modal <1.5s · 無 flicker/race · 體感「打完有反應」

### Phase 1.5 — Pure Domain Math + Step 4 編排（線 B · ✅ Step 1 + 4 已實作）

| Step | 狀態 | 說明 |
|------|------|------|
| 1 `combat_engine.py` | ✅ | 純計算；piercing 10% 保底傷害 |
| 2 `trauma_service.py` | ⏳ | 營會後 |
| 3 `narrative_orchestrator.py` | ✅ | post-combat pipeline |
| 4 `combat_flow.py` | ✅ | INV-E 純編排；`normalize_failed_escape_actions` 已接入 resolve body |

**下一步**：將 `_resolve_player_phase_body` 傷害 loop 漸進委派 `process_mixed_round_actions`；PA deploy V2。

---

## 早前已完成（2026-06-29）

### P4 生產 Encounter JSON

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
| **戰鬥行動 Modal** | `#combat-action-modal` — 擲骰 + 確認（**已移除**預計傷害預覽，`combat_flow_v3`） |
| **`POST /combat/preview_action`** | 後端仍存在；前端戰鬥流程**唔再呼叫** |
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
Zoo：任何神智可發動；加成 tier ≥70/≥80/≥90/≥100 → ×1.3/1.4/1.5/1.8（<70 為 ×1.0）
暴走：神智 <10→90%, <20→50%, <40→20%（HP≤0 唔觸發）
敵人反擊：攻擊全隊韌性最低者；任一同隊 Defend → 反擊傷害減半
瀕死：HP≤0 → near_death_until +15 分鐘；瀕死期間禁止道具補血
GM stat：>100 唔被全營事件/item cap 壓返 100
```

### 前端戰鬥 UI

**V2（`COMBAT_V2=1`）** — `static/js/combat/` + `templates/combat_screen.html`：

- `#combat-root-v2` — V2 根節點；`combat-v2-*` ID 與舊大廳隔離
- Poll：`ResilientPollingManager`（IDLE 1200ms / WAITING 800ms）
- 全局 `/status` 3s poll 在 V2 戰鬥中**暫停**（`OIKONOMIA_COMBAT_V2_LOCK` + `isPlayerInActiveCombatV2`）

**Legacy inline（`12e1edd` · 已移除主路徑）** — `templates/index.html` 仍保留大廳橋接：

- `#combat-lobby` / `#combat-result-panel` / `#combat-near-death-overlay`（V2 時隱藏）
- `startEncounter` / `exitCombatScreen` / `loadEncounters` — 橋接至 `window.combatV2`

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

## Deploy 流程（Render.com）— Agent 必須執行

### 標準流程（GitHub → Render）

```bash
# 1. 本地：驗證 + commit + push
cd /Users/mingtakyau/Documents/oikonomia
bash scripts/pre_deploy_checks.sh
git add -A && git commit -m "描述改動" && git push origin main

# 2. CI 自動觸發 Deploy Hook（main push + tests 通過）
#    或手動：RENDER_DEPLOY_HOOK='…' bash deploy/render-trigger-deploy.sh
#    或：bash deploy/render-sync.sh

# 3. 驗證（必須與 git rev-parse --short HEAD 相同）
LOCAL=$(git rev-parse --short HEAD)
curl -s https://oikonomia.onrender.com/api/version | python3 -m json.tool
# 預期：version == $LOCAL；git_commit[:7] == version
#       render: true, data_dir: "/data", db_path: "/data/oikonomia.db"
bash deploy/render-sync.sh   # 可選：觸發 hook 並輪詢直到 version 一致
```

**Render 架構約束**：生產用 gunicorn（`render.yaml`）；持久資料只在 `/data`；**`render-predeploy.sh` 必須執行**（Pre-deploy 或 Start Command）；寫 `.deploy-version` 但 **勿 commit 該檔**。Deploy Hook → GitHub Secret `RENDER_DEPLOY_HOOK`，**勿 commit**。

**禁止 commit 清單**：`*.db`、`deploy/artifacts/`、`.deploy-version`、`data/.secret_key`、`data/.gm_pin`。

### PA 後備流程（僅 rollback）

```bash
# PA Bash（用戶帳號 takjai）
FORCE=1 bash ~/oikonomia/deploy/pa-update.sh
# Web tab → Reload takjai.pythonanywhere.com
curl -s https://takjai.pythonanywhere.com/api/version | python3 -m json.tool
```

### `/api/version` 重要 markers

`combat_system`, `server_combat_dice`, `defend_team_buff`, `combat_round_continue`, `player_max_hp`, `protagonist_combat`, `trauma_ending`, `confirm_modal`, `protagonist_player_control`, `upload_path_hardened`, `encounter_logs`, `qr_signed_v2`

**BUG-2026-001 戰鬥 UX（2026-06-30 · resolved）** — legacy markers：`enemy_hp_sync_v7`, `combat_flow_v7`, `settlement_breakdown_v1`

**Combat V2** — deploy 後核對 `markers.combat_v2`（Render：`/data/.combat_v2` 或 `COMBAT_V2=1`）

Render deploy 完成後 markers 即更新；若 `version` 落後，手動 POST Deploy Hook 或等 CI job。

### Agent 無法 SSH / Dashboard 時

1. 完成 `git push origin main`
2. 確認 GitHub Actions `pre-deploy-checks` + `deploy-render` 全綠
3. `curl https://oikonomia.onrender.com/api/version` 確認 `version` 已更新且 `success: true`
4. 若 CI hook 失敗：本機 `RENDER_DEPLOY_HOOK=… bash deploy/render-trigger-deploy.sh`
5. PA rollback 才請用戶：PA Bash → `pa-update.sh` → Web Reload

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
| `static/js/combat/bootstrap.js` → `window.combatV2` | V2 feature flag 掛載 |
| `static/js/combat/state_machine.js` → `determineSettlementRoute` | INV-C monotonic guard |
| `static/js/combat/index.js` → `exitToLobby` | V2 退出 → `exitCombatScreen({fromV2})` |
| `templates/index.html` → `isPlayerInActiveCombatV2` | 隔離全局 3s poll |
| `templates/index.html` → `fetchNoCache` / `loadEncounters` | 大廳 cache-bust |
| `services/combat_flow.py` → `normalize_failed_escape_actions` | INV-E |
| `services/combat_outcomes.py` → `build_victory_outcome_payload` | settlement_id |
| `models/combat.py` → `advance_combat_from_poll` | poll 觸發結算 CAS |

---

## 近期 commit（參考）

```
223f8c6 fix(combat-v2): isolate global poll from V2 FSM, instant HP bars, handoff
15f2c37 feat(combat): Step 4 flow orchestrator, piercing damage, victory settlement_id
ee9a691 feat(combat): Greenfield corner cases — INV-D/E, monotonic FSM
f267cec fix(combat): atomic start gate, poll CAS resolve, rescuer validation
bf490f6 fix(lobby): reconcile ended combat + cache-bust encounters on exit
7029bfd fix(combat): entry sync monotonic align — block ghost settlement modal
12e1edd combat_flow_v7: stop poll on victory settlement (legacy inline)
3cdb207 fix(security): Gemini review — combat locks, QR, GM auth
```

---

## 新 Tab 開場白（複製貼上）

### 通用模板

```
請讀 @AGENT_HANDOFF.md（含 Context 管理協議），繼續開發 Oikonomia（/Users/mingtakyau/Documents/oikonomia）。

Baseline：v11 SSOT 已在 repo，唔貼全文；日常審計貼 R11_PARTIAL；本次只處理局部 scope。

【開發模式】  ← 或 【審計模式】

你的責任：
1. 自己執行（改 code、測試、commit、push、觸發 Render deploy），唔好只出 instruction
2. 確保 GitHub 同 Render 版本同 local 一致；改 code 要考慮 Render 架構（/data、gunicorn）

開工前先核對版本：
- local: cd /Users/mingtakyau/Documents/oikonomia && git rev-parse --short HEAD
- Render: curl -s https://oikonomia.onrender.com/api/version | python3 -m json.tool
  確認 version 與 local 相同；git_commit 前 7 字元與 version 一致；render: true；data_dir: /data
- push 前：git status 唔好有 .deploy-version（見本文「Render Deploy 陷阱」）

Render 若落後：push main（CI 觸發 hook）或 bash deploy/render-sync.sh；查 Events log 有無 === Render pre-deploy ===。

然後做我指定嘅任務：[在這裡寫你的任務]
```

### 若不確定任務（健康檢查）

```
…然後做 P0：curl 確認 Render version 與 local 一致；跑 pre_deploy_checks.sh 全綠；讀 UPDATE_LOG.md + bug_log/INDEX.md 了解已知問題。
```