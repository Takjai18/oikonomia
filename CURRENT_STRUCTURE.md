# Oikonomia — Current Structure

> 最後更新：2026-07-02 · Git：`c3252df`（Render Starter 遷移）  
> 路徑：`/Users/mingtakyau/Documents/oikonomia`  
> 備份：`Google Drive/My Drive/oikonomia`

Summer Camp 2026 ARG Web App（Flask）。雙主角路線 Iggy / Marah，含玩家 Dashboard、遭遇戰 Combat V2、故事、GM 後台。

---

## 目錄總覽

```
oikonomia/
├── app.py                    # Flask 入口、configure_models、register blueprints
├── database.py               # DB bootstrap（get_db_connection）、migrate_db、safe_init_db
├── wsgi.py                   # Production WSGI（Render gunicorn / PA）
├── render.yaml               # Render Blueprint（Starter、Singapore、/data disk）
├── requirements.txt          # 含 gunicorn（Render production）
├── oikonomia.db              # 本地預設 SQLite（開發用）
│
├── README.md                 # 專案入口 + AI 分工 + Context 協議
├── AGENT_HANDOFF.md          # Grok Build 交接（部署、測試、符號表）
├── GEMINI_REVIEW.md          # Gemini review/debug 指引 + 已修對照 §18
├── CURRENT_STRUCTURE.md      # 本檔
├── COMBAT_V2_AUDIT_BUNDLE.md # v12 全文 SSOT（Gemini Baseline）
├── COMBAT_V2_PARTIAL_INDEX.md
├── COMBAT_V2_R11_PARTIAL_BUNDLE.md
├── COMBAT_V2_R12_A_FRONTEND_BRIDGE.md
├── COMBAT_V2_R12_B_DB_HARDENING.md
├── COMBAT_V2_R12_C_STEP4_ORCHESTRATION.md
├── COMBAT_V2_R12_D_INV_MONOTONIC.md
├── combat_greenfield_final.md
│
├── models/                   # 資料層 & 核心業務邏輯
├── routes/                   # HTTP Blueprints
├── services/                 # 跨 route 服務（編排、結局、戰後管線）
├── utils/                    # db_tx、上傳、QR、helpers
├── data/                     # 靜態遊戲設定
│
├── templates/
│   ├── index.html            # 玩家 UI + 大廳橋接（~4800 行）
│   ├── combat_screen.html    # Combat V2 DOM 骨架
│   └── claim_item.html
├── static/js/combat/         # Combat V2 Greenfield 模組
├── encounters/               # Encounter JSON
│
├── deploy/                   # Render（主）+ PA（後備）部署
│   ├── render-predeploy.sh   # preDeploy：secrets、DB bootstrap、.deploy-version
│   ├── render-check.sh       # 驗證 /api/version
│   ├── render-trigger-deploy.sh  # POST Deploy Hook
│   ├── render-sync.sh        # push 後觸發 + 輪詢 version
│   ├── render-import-data.sh # Shell 匯入 /data
│   └── pa-update.sh          # PA 後備
├── scripts/                  # 測試 + audit bundle 生成
├── tests/                    # Playwright + Node combat tests
├── bug_log/                  # 難解 bug 長篇調查
│
├── uploads/                  # 玩家上傳（不 commit）
└── venv/                     # Python 虛擬環境（不 commit）
```

---

## Combat V2 前端（`static/js/combat/`）

| 檔案 | 職責 |
|------|------|
| `bootstrap.js` | Feature flag → `window.combatV2` / `CombatV2App` |
| `index.js` | `CombatApp`、poll、timeout defense、`exitToLobby` |
| `state_machine.js` | Phase FSM、INV-A～E、`entrySyncPending` |
| `settlement.js` | `settlement_id`、monotonic guard、`extractHud` |
| `api_client.js` | `CombatApi`、`ResilientPollingManager` |
| `render.js` / `selectors.js` / `toast.js` | 渲染與 DOM ID |
| `views/*.js` | hud、action、dice、settlement、victory、item_select… |

大廳橋接（`templates/index.html`）：

| 符號 | 職責 |
|------|------|
| `OIKONOMIA_COMBAT_V2_LOCK` | sessionStorage — 暫停全局 3s `/status` poll |
| `isPlayerInActiveCombatV2()` | lock + FSM/DOM fallback |
| `finishSessionRestore` | DOM-first → `onCombatStarted` fast-forward |
| `exitCombatScreen` | 單向 `destroy()` + 清 lock |

---

## models/ — 資料 & 核心邏輯

| 檔案 | 職責 |
|------|------|
| `combat.py` | 戰鬥核心：CAS resolve、`_end_combat` 原子收尾、`advance_combat_from_poll` |
| `protagonist.py` | 主角 HP/trauma、`protagonist_states` SSOT |
| `encounter_outcomes.py` | 勝敗獎勵、`encounter_completions` |
| `squad.py` / `team.py` | 玩家小隊、隊伍、主角聚合 |
| `item.py` | 物品、QR、戰鬥消耗 batch |
| `encounter.py` | 載入 `encounters/*.json` |
| `settings.py` | 全域常數 |

---

## services/ — 編排與計算

| 檔案 | 職責 |
|------|------|
| `combat_engine.py` | 純計算：`calculate_incoming_damage`（10% piercing）、dice、defend |
| `combat_flow.py` | INV-E：`normalize_failed_escape_actions`、`process_mixed_round_actions` |
| `combat_outcomes.py` | `resolve_combat_outcome`（Pipeline 冪等，無外層 retry race） |
| `narrative_orchestrator.py` | `execute_post_combat_success_pipeline`（`immediate_transaction`） |
| `trauma_service.py` | 創傷能帶管線 |
| `ending.py` | `judge_ending`、`apply_ending` |
| `player_status.py` | `/status` 組裝 |
| `gm_auth.py` | GM session 8h |

---

## utils/

| 檔案 | 職責 |
|------|------|
| `db_tx.py` | `get_db_connection`（WAL + 30s busy_timeout）、`immediate_transaction`、`with_db_retry` |

---

## routes/ — HTTP 層

| 檔案 | 前綴 | 職責 |
|------|------|------|
| `auth.py` | `/` | 登入、PIN、`/session/restore` + `current_combat_id` |
| `combat.py` | `/combat` | start、submit、status、summon_gm |
| `gm.py` | `/gm` | GM API + `override_trauma_ending`（需 `gm_operator`） |
| `encounters.py` | `/` | Encounter 列表 |
| `player.py` / `team.py` / `items.py` / `story.py` / `misc.py` | — | 其餘玩家 API |
| `gm_templates.py` | — | GM Dashboard HTML |

---

## scripts/ — 測試與審計

| 腳本 | 用途 |
|------|------|
| `test_combat_flow.py` | 戰鬥全流程（**267/267**） |
| `test_db_hardening.py` | WAL、purge、reconcile、SSOT（**11/11**） |
| `test_combat_engine.py` | 計算層單元（**17/17**） |
| `test_combat_flow_orchestrator.py` | INV-E 編排（**4/4**） |
| `test_combat_concurrency.py` | Co-op 併發 smoke |
| `build_combat_v2_audit_bundle.py` | 生成 v12 全文 SSOT |
| `build_combat_v2_partial_bundles.py` | 生成 Partial 索引 + R11/R12 A–D |
| `pre_deploy_checks.sh` | 部署閘門 |

```bash
npm run test:combat          # 17/17
npm run test:e2e:v2          # Playwright T8–T14
```

---

## 執行時資料路徑

| 環境 | `DATA_DIR` | 資料庫 |
|------|------------|--------|
| 本地開發 | 專案根目錄 | `./oikonomia.db` |
| **Render（正式）** | `/data`（Persistent Disk） | `/data/oikonomia.db` |
| PythonAnywhere（後備） | `data/` | `data/oikonomia.db` |

正式環境：https://oikonomia.onrender.com · GM `/gm` · 後備 PA https://takjai.pythonanywhere.com

---

## 架構關係（Combat V2）

```
templates/index.html（大廳橋接）
    └── bootstrap.js → CombatApp (index.js)
            ├── state_machine.js（FSM）
            ├── api_client.js（poll）
            └── views/*.js

POST /combat/submit_action → models/combat.py
    ├── maybe_resolve_player_phase（CAS + monotonic phase）
    └── _end_combat（atomic TX）
            └── resolve_combat_outcome → narrative_orchestrator
```

---

*End of CURRENT_STRUCTURE · 2026-07-02 · `c3252df`*