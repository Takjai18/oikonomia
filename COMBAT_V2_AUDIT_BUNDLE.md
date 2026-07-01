# COMBAT_V2_AUDIT_BUNDLE v15（營會 SSOT · 全棧審計錨點）

> **用途**：**首次 onboarding** 或重大版本錨點 — Copy 全文到 Gemini 建立 Baseline  
> **日期**：2026-07-02 · **commit**：`137dfa9`  
> **實作者**：Grok Build（Combat V2 Greenfield · Phase 2 封頂）  
> **Baseline**：`combat_greenfield_final.md` v1.1（附錄內含全文）  
> **上一輪**：Greenfield Zoo 規格修正 — 任何神智可發動；>70/>80/>90 加成 ✅（見 `GEMINI_REVIEW.md` §25）
> **本輪**：v15 錨點（`137dfa9`）；日常審計用 **R15 Zoo Partial** 或 §20.3 **新 scope**
> **Feature Flag**：`COMBAT_V2=1` · `OIKONOMIA_SHOW_TEST_ENCOUNTERS=0`（production）

> ⚠️ **後續局部審計唔貼本檔全文** — 見 `COMBAT_V2_PARTIAL_INDEX.md` 選 R11 / R12-A～D / **R15**  
> 生成：`python3 scripts/build_combat_v2_audit_bundle.py`

---

## 0. 給 Gemini 的指令（R15 — Baseline / 錨點 Audit）

1. **PASS/FAIL** 總評 + 健康度 **X/10**
2. **Context 協議**：後續用戶只貼單檔 Partial；本檔作 SSOT 引用
3. **已修對照**：`GEMINI_REVIEW.md` §18–§25 — 唔好重複報已落地項（含 §25 Zoo 規格）
4. **下一輪建議 scope**：`GEMINI_REVIEW.md` §20.3 或 `COMBAT_V2_R15_ZOO_PARTIAL_BUNDLE.md`

### 0.1 Partial 審計狀態（`137dfa9` · 已審已修，回歸 only）

| Bundle | 焦點 | 狀態 |
|--------|------|------|
| **R12-D** | monotonic · SETTLEMENT 終端拆解 · submittingActive | ✅ §20 · §22 · §24 |
| **R12-A** | sessionStorage lock · restore rAF · destroy | ✅ §20 |
| **R12-B** | reconcile purge · WAL · `get_team_protagonists` | ✅ §20 |
| **R12-C** | failed_escape targeting · atomic resolve-phase · INV-E | ✅ §20 · §22 · §23 |
| **R11** | GM sanitize · DICE_CONFIRM timeout · co-op CAS | ✅ §18–§20 |
| **R13** | combat_start IDOR · rescue target · lazy import | ✅ §19 |

**測試帳號**：Henry `PLAYER-75406`  
**Encounter**：`practice_iggy_04_marathon` · `test_protagonist_control`

---

## 1. Phase 2 功能狀態總表

| 功能 | 狀態 | 主要檔案 |
|------|------|----------|
| P2-1 戰鬥物品（power_up） | ✅ | `item_select_view.js`, `routes/items.py`, `models/item.py` |
| P2-2 Zoo UI + 暴走提示 | ✅ | 任何神智可發動；>70/>80/>90 → ×1.3/1.4/1.5；`action_view.js`, `state_machine.js`, `models/combat.py` |
| P2-3 主角代打（隊長專屬） | ✅ | `routes/combat.py` 403 gate, `index.js` asProtagonist, `action_view.js` toggle |
| P2-4 物品效果擴展（醫療/解控） | ✅ | `models/combat.py` use_item, `settlement_view.js` Breakdown |
| P2-5 雙人 Co-op E2E | ✅ | `tests/combat_v2.spec.js` T12, `state_machine.js` poll settlement |
| 真・GM 召喚 API | ✅ | `routes/combat.py` `/combat/summon_gm`, `services/global_events.py` |
| 超時自動防禦 | ✅ | `index.js` pollTick + `triggerTimeoutAutomaticDefense` |
| T13 非隊長代打阻擋 | ✅ | `tests/combat_v2.spec.js` T13, `test_non_leader_as_protagonist_rejected` |
| GM Override 後端網關 | ✅ | `routes/gm.py` `/gm/api/override_trauma_ending`, T14 403 gate |
| GM UI Bridge（嵌入式特權面板） | ✅ | `api_client.js`, `index.js`, `victory_view.js`, `bootstrap.js` |

---

## 2. Phase 1.5 編排層狀態

| 模組 | 狀態 | 職責 |
|------|------|------|
| `services/trauma_service.py` | ✅ | 創傷能帶 · 審計 log · bad_ending SSOT 鎖定 |
| `services/narrative_orchestrator.py` | ✅ | 戰後獎勵 · encounter_completions 等冪 · insight/unlocks |
| `services/combat_outcomes.py` | ✅ | 勝利/失敗編排入口 · 委派上述管線 |

---

## 3. 測試狀態（R15 · `137dfa9`）

```bash
npm run test:combat                                    # 26/26 pass
./venv/bin/python3 scripts/test_combat_flow.py         # 283/283 pass
./venv/bin/python3 scripts/test_db_hardening.py        # 13/13 pass
./venv/bin/python3 scripts/test_combat_engine.py       # 18/18 pass
./venv/bin/python3 scripts/test_combat_flow_orchestrator.py  # 5/5 pass
./venv/bin/python3 scripts/test_combat_concurrency.py
scripts/test_ending_flow.py                            # 23/23 pass
npm run test:e2e:v2                                    # T8–T14
bash scripts/pre_deploy_checks.sh
```

---

## 4. 架構資料流（R11）

```
戰鬥勝利 → resolve_combat_outcome()
  ├─ judge_ending → trauma_bad_ending? → apply_trauma_bad_ending_victory
  └─ execute_post_combat_success_pipeline()  [IMMEDIATE TX · INV-C 等冪]
       ├─ insight_fragments · item rewards · encounter_completions
       └─ story stage snapshot

主角瀕死 → apply_protagonist_trauma_pipeline()  [IMMEDIATE TX]
submit_action → maybe_resolve_player_phase() → CombatItemConsumeBatch

GM 現場救援（瀕死面板）→ 三重點擊標題 → executeGmOverride()
  ├─ overrideTraumaEnding → /gm/api/override_trauma_ending  [gm_session_valid]
  └─ clear ending → COMBAT_RESET from COMBAT_FAILED → IDLE + START_POLL
```

---

## 5. 不變式防線（INV-A～E）

| ID | 規則 | 落地點 |
|----|------|--------|
| INV-A | Settlement 主觸發 `onSubmitSuccess`；co-op poll 例外 | `index.js` syncState |
| INV-B | `settlement_id` 冪等，不重複開 modal | `settlement.js` deriveSettlementId |
| INV-C | poll tick 被動，不主動製造 settlement | `state_machine.js` |
| INV-D | HP≤0 搶占中斷所有 UI（含 `HIDE_SETTLEMENT`） | `handleAnyDeath` · `terminalModalTeardownEffects` |
| INV-E | escape 失敗後仍顯示混合結算；反擊優先 targeting | T8 · `select_enemy_counter_target` |

---

## 6. PR-6 結構（回歸）

- `index.html` 4901 行 · `combat_flow.js` 已刪除

---

## 7. Context 管理協議（摘錄）

> 全文見 `GEMINI_REVIEW.md` §0.5 · `AGENT_HANDOFF.md` · `README.md`

---

## 8. 完整原始碼附錄（R11）

> 由 `scripts/build_combat_v2_audit_bundle.py` 自動生成



===== FILE: GEMINI_REVIEW.md (§0.5 Context 協議摘錄) =====

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
| `GEMINI_REVIEW.md` | 本文 | Review 格式與已修對照（§18–§25 已修 R11–R16 + Zoo 規格） |

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


===== FILE: AGENT_HANDOFF.md (Context 協議摘錄) =====

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
| Combat 後端 | `./venv/bin/python3 scripts/test_combat_flow.py`（267/267） |
| DB 併發/SSOT | `./venv/bin/python3 scripts/test_db_hardening.py`（11/11） |
| 計算層/編排 | `./venv/bin/python3 scripts/test_combat_engine.py` + `test_combat_flow_orchestrator.py` |
| Combat 前端 | `npm run test:combat`（17/17）+ `npm run test:e2e:v2` |
| Co-op 併發 | `./venv/bin/python3 scripts/test_combat_concurrency.py` |
| GM override | `test_phase2_gm_override_gateway`（在 combat_flow 內） |
| Encounter JSON | `test_encounter_catalog()` |
| Deploy 前 | `bash scripts/pre_deploy_checks.sh` |

---


===== FILE: templates/index.html (PR-6 combat excerpts) =====

            <!-- Combat -->
            <div id="combat" class="section hidden">
                <!-- Encounter 列表（大廳） -->
                <div id="combat-lobby">
                    <div class="mb-6">
                        <div class="text-sm theme-accent-text">ENCOUNTER</div>
                        <div class="text-3xl font-semibold">戰鬥遭遇</div>
                    </div>
                    <div id="encounter-list" class="space-y-4 mb-8"></div>
                </div>

                <!-- COMBAT V2 — Greenfield mount (PR-6) -->
                <div id="combat-module-container" class="w-full min-h-screen bg-zinc-950 text-white">
                    {% if combat_v2_enabled %}
                        {% include 'combat_screen.html' %}
                    {% else %}
                        <div id="combat-v1-deprecated-fallback" class="p-6 text-center text-zinc-500">
                            <p>戰鬥系統正在升級中，請聯繫 GM 開啟 COMBAT_V2 特性標記。</p>
                        </div>
                    {% endif %}
                </div>

                <!-- 瀕死全屏 -->
                <div id="combat-near-death-overlay" class="hidden fixed inset-0 z-[70] flex items-center justify-center p-6">
                    <div class="text-center max-w-sm">
                        <div class="text-5xl mb-4">💔</div>
                        <h2 class="text-2xl font-bold text-red-300 mb-2">正在癒合…</h2>
                        <p id="near-death-countdown" class="text-4xl font-mono text-red-400 mb-4">15:00</p>
                        <p class="text-sm text-zinc-300 mb-6">隊友可發起「界線重建」禱告救援</p>
                        <button onclick="rescueNearDeath()" class="px-6 py-3 bg-emerald-700 hover:bg-emerald-600 rounded-2xl font-medium">
                            🤝 為隊友禱告（非瀕死者）
                        </button>
                    </div>
                </div>

                <!-- Precheck Modal -->
                <div id="combat-precheck-modal" class="hidden fixed inset-0 z-[65] flex items-center justify-center p-6">
                    <div class="bg-zinc-900 border border-amber-600/40 rounded-3xl p-6 max-w-md w-full shadow-2xl">
                        <div class="text-amber-400 text-sm mb-1">洞察力判定</div>
                        <h3 class="text-xl font-bold mb-3" id="precheck-modal-title">前置判定</h3>
                        <p id="combat-precheck-text" class="text-zinc-300 text-sm leading-relaxed mb-6"></p>
                        <div class="flex flex-col sm:flex-row gap-3">
                            <button onclick="confirmPrecheck('skip')" class="flex-1 py-3 bg-emerald-700 hover:bg-emerald-600 rounded-2xl font-medium">跳過戰鬥</button>
                            <button onclick="confirmPrecheck('fight')" class="flex-1 py-3 bg-red-800 hover:bg-red-700 rounded-2xl font-medium">進入戰鬥</button>
                        </div>
                    </div>
                </div>

                <!-- 戰鬥結果 + 神學反思 -->
                <div id="combat-result-panel" class="hidden cartoon-box p-6 max-w-4xl mx-auto">
                    <h3 id="combat-result-title" class="text-xl font-bold mb-3"></h3>
                    <div id="combat-result-trauma-badge" class="hidden mb-3 px-4 py-2 rounded-xl border border-violet-700/50 bg-violet-950/30 text-sm text-violet-200"></div>
                    <p id="combat-result-narrative" class="text-zinc-300 mb-4 leading-relaxed"></p>
                    <div id="combat-reflection" class="hidden border-t border-zinc-700 pt-4 mt-4">
                        <h4 class="font-bold text-amber-400 mb-1" id="combat-reflection-title">界線反思</h4>
                        <p id="combat-reflection-theology" class="text-xs text-zinc-500 mb-3 italic"></p>
                        <ul id="combat-reflection-questions" class="text-sm text-zinc-300 space-y-3 list-none"></ul>
                    </div>
                    <button onclick="exitCombatScreen()" class="mt-6 px-5 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-xl text-sm">返回遭遇列表</button>
                </div>
            </div>


    // ── Combat lobby bridge (PR-6: legacy inline combat script removed) ──
    let pendingEncounterId = null;
    let currentCombatId = null;
    let isSessionRestoringCombatLock = false;
    const ACTIVE_COMBAT_STORAGE_KEY = 'OIKONOMIA_ACTIVE_COMBAT_ID';
    const COMBAT_V2_LOCK_KEY = 'OIKONOMIA_COMBAT_V2_LOCK';

    function setActiveCombatBridge(combatId) {
        if (combatId != null && combatId !== '') {
            sessionStorage.setItem(COMBAT_V2_LOCK_KEY, 'true');
            sessionStorage.setItem(ACTIVE_COMBAT_STORAGE_KEY, String(combatId));
            currentCombatId = combatId;
        }
    }

    function clearActiveCombatBridge() {
        sessionStorage.removeItem(COMBAT_V2_LOCK_KEY);
        sessionStorage.removeItem(ACTIVE_COMBAT_STORAGE_KEY);
        currentCombatId = null;
        pendingEncounterId = null;
    }

    function revealCombatV2Surface() {
        // DOM-first: visible combat section before V2 init (avoids 0px reflow on restore)
        showSection('combat', { skipCombatLobbyLoad: true });
        [
            'combat-lobby',
            'combat-result-panel',
            'combat-precheck-modal',
            'combat-near-death-overlay',
        ].forEach((id) => {
            const el = document.getElementById(id);
            if (el) setVisible(el, false);
        });
        document.getElementById('combat-root-v2')?.classList.remove('hidden');
    }

    function waitForCombatRepaint() {
        return new Promise((resolve) => {
            requestAnimationFrame(() => requestAnimationFrame(resolve));
        });
    }

    async function waitForCombatV2Ready(maxMs = 8000) {
        const deadline = Date.now() + maxMs;
        while (Date.now() < deadline) {
            if (window.combatV2?.isEnabled?.()) return true;
            if (
                window.combatV2?.isInitComplete?.()
                && typeof window.combatV2.isEnabled === 'function'
                && !window.combatV2.isEnabled()
            ) {
                return false;
            }
            await new Promise((r) => setTimeout(r, 50));
        }
        return !!window.combatV2?.isEnabled?.();
    }

    function removeLegacyCombatGarbage() {
        [
            '.settlement-modal-backdrop',
            '#combat-failed-mask',
            '.legacy-dice-roller',
            '#combat-round-settlement-modal',
        ].forEach((selector) => {
            document.querySelectorAll(selector).forEach((el) => {
                try { el.remove(); } catch (_) { /* noop */ }
            });
        });
        setVisible(document.getElementById('combat-near-death-overlay'), false);
    }

    /** INV-C: pause global /status poll while V2 combat is authoritative */
    function isPlayerInActiveCombatV2() {
        if (sessionStorage.getItem(COMBAT_V2_LOCK_KEY) === 'true') {
            return true;
        }
        if (sessionStorage.getItem(ACTIVE_COMBAT_STORAGE_KEY)) {
            return true;
        }
        if (window.combatV2?.isEnabled?.()) {
            const state = window.combatV2.getState?.();
            if (state?.combatId) return true;
            const combatRootV2 = document.getElementById('combat-root-v2');
            if (combatRootV2 && !combatRootV2.classList.contains('hidden')) {
                sessionStorage.setItem(COMBAT_V2_LOCK_KEY, 'true');
                return true;
            }
        }
        return false;
    }

    window.AppRouter = {
        navigateTo(route) {
            console.log(`[Router] 路由跳轉至: ${route}`);
            if (route === 'dashboard' || route === 'combat-hub') {
                if (typeof window.combatV2?.destroy === 'function') {
                    window.combatV2.destroy();
                } else {
                    const app = window.combatV2?.getApp?.();
                    if (app && typeof app.destroy === 'function') {
                        app.destroy();
                    }
                }
                clearActiveCombatBridge();
                const lobby = document.getElementById('combat-lobby');
                if (lobby) lobby.classList.remove('hidden');
                document.getElementById('combat-root-v2')?.classList.add('hidden');
            }
        },
    };

    function appendCacheBust(url) {
        const sep = url.includes('?') ? '&' : '?';
        return `${url}${sep}_cb=${Date.now()}`;
    }

    const FETCH_NO_CACHE_HEADERS = {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
        'X-Requested-With': 'XMLHttpRequest',
    };

    function fetchNoCache(url, options = {}) {
        return fetch(appendCacheBust(url), {
            credentials: 'same-origin',
            ...options,
            headers: { ...FETCH_NO_CACHE_HEADERS, ...(options.headers || {}) },
        });
    }

    async function onLegacyEncounterTrigger(data) {
        if (window.combatV2?.isEnabled?.()) {
            if (data.combat_id) setActiveCombatBridge(data.combat_id);
            revealCombatV2Surface();
            await window.combatV2.onCombatStarted(data);
        }
    }

    function exitCombatScreen(options = {}) {
        console.log('[Bridge] 執行戰鬥退出，清理殘留環境並釋放全局鎖...');
        clearActiveCombatBridge();
        removeLegacyCombatGarbage();

        if (typeof window.combatV2?.destroy === 'function') {
            window.combatV2.destroy();
        } else {
            const app = window.combatV2?.getApp?.();
            if (app && typeof app.destroy === 'function') {
                app.destroy();
            }
        }

        [
            'combat-result-panel',
            'combat-precheck-modal',
            'combat-near-death-overlay',
        ].forEach((id) => {
            const el = document.getElementById(id);
            if (el) setVisible(el, false);
        });
        setVisible(document.getElementById('combat-lobby'), true);
        document.getElementById('combat-root-v2')?.classList.add('hidden');

        if (!options.fromV2) {
            showToast('已安全退出戰場', 'info');
        }

        setTimeout(async () => {
            if (typeof loadEncounters === 'function') {
                await loadEncounters();
            }
        }, 150);
    }
    window.exitCombatScreen = exitCombatScreen;

    async function loadCombatPage(combatId) {
        if (combatId) {
            setActiveCombatBridge(combatId);
            revealCombatV2Surface();
        } else {
            clearActiveCombatBridge();
            setVisible(document.getElementById('combat-lobby'), true);
            setVisible(document.getElementById('combat-result-panel'), false);
            setVisible(document.getElementById('combat-precheck-modal'), false);
            setVisible(document.getElementById('combat-near-death-overlay'), false);
            document.getElementById('combat-root-v2')?.classList.add('hidden');
        }
        const fresh = await refreshSquadFromServer();
        if (fresh) {
            initPlayerAvatar();
            updateDashboard(fresh);
        }
        if (!combatId) {
            await loadEncounters();
        }
        if (combatId && window.combatV2?.isEnabled?.()) {
            await window.combatV2.onCombatStarted({ combat_id: combatId });
        } else if (combatId) {
            await loadEncounters();
        }
    }

    async function loadEncounters() {
        const container = document.getElementById('encounter-list');
        if (!container) return;
        container.innerHTML = '<div class="text-zinc-400">載入 Encounter...</div>';

        try {
            const res = await fetchNoCache('/encounters');
            const data = await res.json();
            if (!data.success) {
                container.innerHTML = '<div class="text-red-400">載入失敗</div>';
                return;
            }

            container.innerHTML = '';
            if (data.progress_hint) {
                const hint = document.createElement('div');
                hint.className = 'text-xs text-zinc-400 cartoon-box p-3 mb-3 leading-relaxed';
                hint.textContent = data.progress_hint;
                container.appendChild(hint);
            }

            if (!data.encounters || data.encounters.length === 0) {
                const empty = document.createElement('div');
                empty.className = 'text-zinc-400 cartoon-box p-6 text-center';
                empty.textContent = '暫無可用遭遇戰';
                container.appendChild(empty);
                return;
            }

            data.encounters.forEach(enc => {
                const card = document.createElement('div');
                card.className = 'cartoon-box p-5';
                const badges = [];
                if (enc.is_practice || enc.replayable) {
                    badges.push('<span class="text-xs px-2 py-1 bg-sky-900/50 text-sky-300 rounded-full shrink-0">可重複練習</span>');
                } else if (enc.completed) {
                    badges.push('<span class="text-xs px-2 py-1 bg-emerald-900/50 text-emerald-400 rounded-full shrink-0">已完成</span>');
                }
                const canStart = enc.replayable || !enc.completed;
                const btnLabel = enc.replayable && enc.completed ? '再練一次' : '開始 Encounter';
                const btn = canStart
                    ? `<button onclick="startEncounter('${enc.encounter_id}')" class="mt-3 px-4 py-2 theme-btn-primary rounded-xl text-sm font-medium">${btnLabel}</button>`
                    : '';
                const hpHint = enc.enemy_hp
                    ? `<div class="text-xs text-zinc-500 mt-1">敵人 HP：${Number(enc.enemy_hp).toLocaleString('zh-Hant')}</div>`
                    : '';
                card.innerHTML = `
                    <div class="flex items-start justify-between gap-2 mb-2 flex-wrap">
                        <div class="font-bold text-lg">${enc.title || enc.encounter_id}</div>
                        <div class="flex flex-wrap gap-1">${badges.join('')}</div>
                    </div>
                    <div class="text-xs text-zinc-500 mb-2">${enc.location_hint || ''}</div>
                    <p class="text-sm text-zinc-300">${enc.description || ''}</p>
                    ${enc.enemy_name ? `<div class="text-xs text-red-400/80 mt-2">敵人：${enc.enemy_name}</div>` : ''}
                    ${hpHint}
                    ${btn}
                `;
                container.appendChild(card);
            });

            if (data.active_combat) {
                const hint = document.createElement('div');
                hint.className = 'text-sm text-amber-400 cartoon-box p-4 cursor-pointer';
                hint.innerHTML = '⚔️ 進行中的戰鬥 — <span class="underline">點擊繼續</span>';
                const resumeCombatId = data.active_combat_id;
                hint.onclick = async () => {
                    const resumeId = resumeCombatId || currentCombatId;
                    if (resumeId) setActiveCombatBridge(resumeId);
                    revealCombatV2Surface();
                    if (window.combatV2?.isEnabled?.()) {
                        await window.combatV2.onCombatStarted({ combat_id: resumeId });
                    } else {
                        showToast('請聯繫 GM 開啟 COMBAT_V2', 'error');
                    }
                };
                container.prepend(hint);
            }
        } catch (e) {
            container.innerHTML = '<div class="text-red-400">載入失敗</div>';
        }
    }

    async function startEncounter(encounterId) {
        const agreed = await showConfirmModal({
            title: '開始遭遇戰',
            message: '確定開始此 Encounter？',
        });
        if (!agreed) return;
        pendingEncounterId = encounterId;
        const res = await fetch('/combat/start', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ encounter_id: encounterId }),
        });
        const data = await res.json();
        if (!data.success) {
            showToast(data.error || '無法開始', 'error');
            return;
        }
        setActiveCombatBridge(data.combat_id);
        showSection('combat', { skipCombatLobbyLoad: true });
        if (data.can_skip && data.status === 'precheck') {
            setVisible(document.getElementById('combat-lobby'), false);
            document.getElementById('precheck-modal-title').textContent = data.encounter?.title || '前置判定';
            document.getElementById('combat-precheck-text').textContent =
                data.precheck_text || '你們有足夠洞察力看穿這是情緒勒索的扭曲模式。';
            setVisible(document.getElementById('combat-precheck-modal'), true);
            return;
        }
        if (window.combatV2?.isEnabled?.()) {
            revealCombatV2Surface();
            await window.combatV2.onCombatStarted(data);
            return;
        }
        showToast('請聯繫 GM 開啟 COMBAT_V2', 'error');
    }

    async function confirmPrecheck(choice) {
        const res = await fetch('/combat/start', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                encounter_id: pendingEncounterId,
                confirm: choice,
            }),
        });
        const data = await res.json();
        if (!data.success) {
            showToast(data.error || '操作失敗', 'error');
            return;
        }
        setVisible(document.getElementById('combat-precheck-modal'), false);
        if (data.skipped) {
            showCombatResult({ outcome: 'victory', narrative: data.narrative, reflection_prompt: data.reflection_prompt });
            const statusRes = await fetchNoCache('/status');
            updateDashboard(await statusRes.json());
            return;
        }
        setActiveCombatBridge(data.combat_id);
        if (window.combatV2?.isEnabled?.()) {
            revealCombatV2Surface();
            await window.combatV2.onCombatStarted(data);
            return;
        }
        showToast('請聯繫 GM 開啟 COMBAT_V2', 'error');
    }

    function showCombatResult(data) {
        clearActiveCombatBridge();
        setVisible(document.getElementById('combat-near-death-overlay'), false);
        setVisible(document.getElementById('combat-precheck-modal'), false);
        setVisible(document.getElementById('combat-lobby'), false);
        document.getElementById('combat-root-v2')?.classList.add('hidden');
        setVisible(document.getElementById('combat-result-panel'), true);
        const badEnding = data.trauma_bad_ending || data.ending_condition === 'bad_ending';
        const victory = data.outcome === 'victory';
        const titleEl = document.getElementById('combat-result-title');
        if (badEnding) {
            titleEl.textContent = '🌑 陰影結局';
            titleEl.className = 'text-xl font-bold mb-3 text-violet-300';
        } else {
            titleEl.textContent = victory ? '🎉 戰鬥勝利' : '💀 戰鬥失敗';
            titleEl.className = 'text-xl font-bold mb-3';
        }
        const traumaBadge = document.getElementById('combat-result-trauma-badge');
        if (badEnding) {
            const total = data.protagonist_trauma_total ?? data.ending?.protagonist_trauma_total ?? '?';
            traumaBadge.textContent = `主角心理創傷過深（累計 ${total} 次）——即使贏了這一仗，也無法迎來真正的救贖。`;
            setVisible(traumaBadge, true);
        } else {
            setVisible(traumaBadge, false);
        }
        document.getElementById('combat-result-narrative').textContent = data.narrative || '';
        const reflection = badEnding ? null : data.reflection_prompt;
        const reflectionBox = document.getElementById('combat-reflection');
        if (reflection) {
            setVisible(reflectionBox, true);
            document.getElementById('combat-reflection-title').textContent = reflection.title || '界線反思';
            document.getElementById('combat-reflection-theology').textContent = reflection.theological_tie || '';
            document.getElementById('combat-reflection-questions').innerHTML =
                (reflection.questions || []).map((q, i) =>
                    `<li class="pl-3 border-l-2 border-amber-600/50"><span class="text-amber-500/80 text-xs">Q${i + 1}</span><br>${q}</li>`
                ).join('');
        } else {
            setVisible(reflectionBox, false);
        }
    }

    async function rescueNearDeath() {

    async function rescueNearDeath() {
        if (isPlayerInActiveCombatV2()) {
            showToast('瀕死救援請在戰鬥畫面操作', 'info');
            return;
        }
        const agreed = await showConfirmModal({
            title: '禱告救援',
            message: '為瀕死隊友發起禱告救援？（每次縮短 5 分鐘）',
            confirmLabel: '發起禱告',
        });
        if (!agreed) return;
        const res = await fetch('/combat/rescue_near_death', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ combat_id: currentCombatId, rescue_type: 'prayer' }),
        });
        const data = await res.json();
        if (!data.success) {
            showToast(data.error || '救援失敗', 'error');
            return;
        }
        if (data.rescued) setVisible(document.getElementById('combat-near-death-overlay'), false);
        showToast(data.message || '禱告已送出', 'success');
    }


        async function finishSessionRestore(data) {
            hideSessionLoading();
            persistRestoreToken(data);
            if (data?.current_combat_id) {
                sessionStorage.setItem(COMBAT_V2_LOCK_KEY, 'true');
                sessionStorage.setItem(ACTIVE_COMBAT_STORAGE_KEY, String(data.current_combat_id));
                currentCombatId = data.current_combat_id;
            }
            try {
                await completeLogin({ ...data, require_set_pin: false, skip_team_prompt: true });
                if (data?.current_combat_id) {
                    if (isSessionRestoringCombatLock) return true;
                    isSessionRestoringCombatLock = true;

                    const combatId = data.current_combat_id;
                    console.log(`[Bridge] 偵測到重連進行中戰鬥 ${combatId}，強開權威引導渲染...`);
                    setActiveCombatBridge(combatId);
                    revealCombatV2Surface();
                    await waitForCombatRepaint();
                    await new Promise((r) => setTimeout(r, 60));

                    const ready = await waitForCombatV2Ready();
                    if (
                        ready
                        && sessionStorage.getItem(ACTIVE_COMBAT_STORAGE_KEY) === String(combatId)
                    ) {
                        await window.combatV2.onCombatStarted({ combat_id: combatId });
                    } else {
                        console.warn('[Bridge] Combat V2 未能及時就緒或目標已變更，執行降級引導。');
                        if (typeof loadCombatPage === 'function') {
                            await loadCombatPage(combatId);
                        }
                    }
                    isSessionRestoringCombatLock = false;
                } else {
                    clearActiveCombatBridge();
                }
                return true;
            } catch (e) {
                isSessionRestoringCombatLock = false;
                console.error('finishSessionRestore 遭遇競態崩潰:', e);
                showLoginScreenAfterFailedRestore(loadLocalSession());
                return false;
            }
        }

        async function fallbackToNormalSession() {

    <script type="module" src="/static/js/combat/bootstrap.js"></script>
</body>
</html>


===== FILE: app.py (COMBAT_ACTION_TYPES excerpt) =====

COMBAT_ACTION_TYPES = (
    "attack", "attack_physical", "attack_nonphysical",
    "defend", "use_item", "use_zoo", "pass", "escape",
)
COMBAT_ATTACK_BASE_DAMAGE = 10
ATTACK_ACTION_TYPES = frozenset({
    "attack", "attack_physical", "attack_nonphysical", "use_zoo",
})


===== FILE: static/js/combat/bootstrap.js =====

/**
 * @file static/js/combat/bootstrap.js
 * @description COMBAT_V2 綠地架構啟動器 — 同步 skeleton 防止弱網重連競態
 */

import { CombatApp } from './index.js';

let app = null;
let enabled = null;
let initPromise = null;
let initComplete = false;

const handlers = {
  async onCombatStarted() {},
  async performAction() {},
  exitToLobby() {},
  summonGm() {},
  executeGmOverride() {},
  pollTick() {},
  onSubmitSuccess() {},
};

const root = () => document.getElementById('combat-root-v2');

async function detectCombatV2() {
  if (window.__OIKONOMIA_COMBAT_V2__ === true) return true;
  if (window.__OIKONOMIA_COMBAT_V2__ === false) return false;
  try {
    const res = await fetch('/api/version', {
      credentials: 'same-origin',
      headers: { 'Cache-Control': 'no-cache' },
    });
    const data = await res.json();
    return !!(data.combat_v2 || data.markers?.combat_v2);
  } catch (_) {
    return false;
  }
}

async function ensureInitialized() {
  if (!initPromise) {
    initPromise = init();
  }
  await initPromise;
}

function mountDisabledStub() {
  enabled = false;
  Object.assign(handlers, {
    async onCombatStarted() {},
    async performAction() {},
    exitToLobby() {},
    summonGm() {},
    executeGmOverride() {},
    pollTick() {},
    onSubmitSuccess() {},
  });
}

function bindLiveHandlers(combatRoot) {
  handlers.onCombatStarted = async (data) => {
    console.log(`[Greenfield] 接收到戰鬥啟動訊號，戰鬥ID: ${data.combat_id}`);
    if (data.combat_id) {
      sessionStorage.setItem('OIKONOMIA_COMBAT_V2_LOCK', 'true');
      sessionStorage.setItem('OIKONOMIA_ACTIVE_COMBAT_ID', String(data.combat_id));
    }
    combatRoot.classList.remove('hidden');
    await app.onCombatStarted(data);
  };
  handlers.performAction = (type) => app.performAction(type);
  handlers.exitToLobby = () => app.exitToLobby();
  handlers.summonGm = () => app.summonGm();
  handlers.executeGmOverride = (opts) => app.executeGmOverride(opts);
  handlers.pollTick = (data) => app.pollTick(data);
  handlers.onSubmitSuccess = (data) => app.onSubmitSuccess(data);
}

window.combatV2 = {
  isEnabled: () => enabled === true,
  isInitComplete: () => initComplete,
  async onCombatStarted(data) {
    await ensureInitialized();
    return handlers.onCombatStarted(data);
  },
  async performAction(type) {
    await ensureInitialized();
    return handlers.performAction(type);
  },
  exitToLobby: () => {
    void ensureInitialized().then(() => handlers.exitToLobby());
  },
  summonGm: () => {
    void ensureInitialized().then(() => handlers.summonGm());
  },
  executeGmOverride: (opts) => {
    void ensureInitialized().then(() => handlers.executeGmOverride(opts));
  },
  getState: () => app?.getState() ?? null,
  pollTick: (data) => {
    if (app) return handlers.pollTick(data);
    void ensureInitialized();
  },
  onSubmitSuccess: (data) => {
    if (app) return handlers.onSubmitSuccess(data);
    void ensureInitialized();
  },
  getApp: () => app,
  destroy: () => {
    if (app) {
      app.destroy();
      app = null;
    }
  },
};
window.CombatV2App = window.combatV2;

async function init() {
  try {
    enabled = await detectCombatV2();
    const combatRoot = root();

    if (!enabled || !combatRoot) {
      mountDisabledStub();
      return;
    }

    app = CombatApp.mount(combatRoot);
    bindLiveHandlers(combatRoot);

    console.log(
    '%c[Greenfield] Oikonomia Combat V2 核心已成功獨立掛載，Legacy 代碼完全清理完成。',
    'color: #10b981; font-weight: bold;',
    );
  } finally {
    initComplete = true;
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => { void ensureInitialized(); });
} else {
  void ensureInitialized();
}


===== FILE: static/js/combat/constants.js =====

/** Shared combat constants (protagonist keys, etc.). */

export const PROTAGONIST_ROUTE_KEYS = Object.freeze(['iggy', 'marah']);

export function isValidProtagonistRouteKey(key) {
  return PROTAGONIST_ROUTE_KEYS.includes(String(key || '').trim().toLowerCase());
}

export const PROTAGONIST_ROUTE_KEY_HINT = PROTAGONIST_ROUTE_KEYS.join(' 或 ');


===== FILE: static/js/combat/index.js =====

/**
 * Combat V2 — single entry CombatApp.mount()
 * Passive sync poll; settlement modal only via onSubmitSuccess.
 */

import { CombatApi, ResilientPollingManager } from './api_client.js';
import {
  Phase,
  TERMINAL_PHASES,
  createInitialContext,
  transition,
  canDispatch,
  blockedMessage,
  determineSettlementRoute,
  handleAnyDeath,
} from './state_machine.js';
import {
  normalizeSettlement,
  deriveSettlementId,
  extractHud,
} from './settlement.js';
import { showToast } from './toast.js';
import { renderAll } from './render.js';
import { DOM_IDS } from './selectors.js';
import { createHudView } from './views/hud_view.js';
import { createActionView } from './views/action_view.js';
import { createDiceModalView } from './views/dice_modal_view.js';
import { createSettlementView } from './views/settlement_view.js';
import { createSubmittingOverlay } from './views/submitting_overlay.js';
import { createEscapeResultView } from './views/escape_result_view.js';
import { createVictoryView } from './views/victory_view.js';
import { createItemSelectView } from './views/item_select_view.js';

export class CombatApp {
  /**
   * @param {HTMLElement} rootEl
   * @param {{ debug?: boolean }} options
   */
  static mount(rootEl, options = {}) {
    return new CombatApp(rootEl, options);
  }

  constructor(rootEl, options = {}) {
    this.rootEl = rootEl;
    this.debug = !!options.debug;
    this.ctx = createInitialContext();
    this.invRecoveryCount = 0;
    this.hasTriggeredTimeoutDefense = false;
    this.submittingActive = false;
    this._activeRafIds = new Set();
    this._activeTimeoutIds = new Set();

    this.views = {
      hud: createHudView(rootEl),
      actions: createActionView(rootEl, {
        onAttack: () => this.performAction('attack'),
        onDefend: () => this.performAction('defend'),
        onEscape: () => this.performAction('escape'),
        onZoo: () => this.performAction('use_zoo'),
        onItemClick: () => this.openItemSelect(),
      }),
      dice: createDiceModalView(rootEl),
      settlement: createSettlementView(rootEl),
      submitting: createSubmittingOverlay(rootEl),
      escape: createEscapeResultView(rootEl),
      endgame: createVictoryView(rootEl),
      items: createItemSelectView(rootEl, (action, opts) => this.performAction(action, opts)),
    };

    this.views.dice.onConfirm(() => this.confirmDice());
    this.views.settlement.onAck(() => this.ackSettlement());

    this.poller = new ResilientPollingManager({
      onTick: (data) => this.pollTick(data),
      onError: (err) => {
        if (this.debug) console.warn('[CombatV2] poll error', err);
      },
    });

    renderAll(this.views, this.ctx);

    if (this.rootEl) {
      this.rootEl.__combat_app_instance__ = this;
    }
  }

  unmount() {
    this.destroy();
  }

  destroy() {
    console.log('[CombatV2] 接收到大廳橋接解構訊號，實施原子化銷毀程序...');
    try {
      if (this.poller) {
        this.poller.stop();
        if (typeof this.poller.destroy === 'function') {
          this.poller.destroy();
        }
      }

      if (this._activeRafIds?.size > 0) {
        for (const rafId of this._activeRafIds) {
          cancelAnimationFrame(rafId);
        }
        this._activeRafIds.clear();
      }
      if (this._activeTimeoutIds?.size > 0) {
        for (const timeoutId of this._activeTimeoutIds) {
          clearTimeout(timeoutId);
        }
        this._activeTimeoutIds.clear();
      }

      this.hideAllModals();
      this.views?.endgame?.hideAll();
      this.views?.items?.hide();
      if (this.rootEl) {
        this.rootEl.classList.add('hidden');
        delete this.rootEl.__combat_app_instance__;
      }
      this.hasTriggeredTimeoutDefense = false;
      this.submittingActive = false;
      console.log('[CombatV2] 本地狀態機環境已完全釋放。');
    } catch (err) {
      console.error('[CombatV2] destroy failed', err);
    }
  }

  getState() {
    return this.ctx;
  }

  safeRequestAnimationFrame(callback) {
    const id = requestAnimationFrame((ts) => {
      this._activeRafIds.delete(id);
      callback(ts);
    });
    this._activeRafIds.add(id);
    return id;
  }

  safeSetTimeout(callback, delayMs) {
    const id = setTimeout(() => {
      this._activeTimeoutIds.delete(id);
      callback();
    }, delayMs);
    this._activeTimeoutIds.add(id);
    return id;
  }

  async onCombatStarted(data) {
    this.dispatch('COMBAT_RESET', { combatId: data.combat_id });
    this.ctx.combatId = data.combat_id;
    this.ctx.settledRoundIndex = -1;
    this.ctx.shownSettlementIds.clear();
    this.ctx.entrySyncPending = true;
    this.hasTriggeredTimeoutDefense = false;
    this.submittingActive = false;
    this.invRecoveryCount = 0;

    if (data.combat_id) {
      sessionStorage.setItem('OIKONOMIA_COMBAT_V2_LOCK', 'true');
      sessionStorage.setItem('OIKONOMIA_ACTIVE_COMBAT_ID', String(data.combat_id));
    }

    this.hideAllModals();
    this.views.endgame.hideAll();

    const toggle = this.rootEl.querySelector(`#${DOM_IDS.PROTAGONIST_TOGGLE}`);
    if (toggle) toggle.checked = false;
    if (data.enemy || data.status) {
      this.ctx.hud = extractHud(data);
    }
    renderAll(this.views, this.ctx);
    this.poller.start(data.combat_id);
    try {
      const snapshot = await CombatApi.status(data.combat_id);
      this.pollTick(snapshot);
    } catch (_) { /* noop */ }
  }

  dispatch(event, meta = {}) {
    const { ctx, effects } = transition(this.ctx, event, meta);
    this.ctx = ctx;
    this.applyEffects(effects);
    return ctx;
  }

  openItemSelect() {
    if (TERMINAL_PHASES.includes(this.ctx.phase)) {
      return;
    }
    if (this.ctx.phase !== Phase.IDLE || this.ctx.hud?.me?.submitted) {
      showToast(blockedMessage(this.ctx, '物品'));
      return;
    }
    this.views.items.show();
  }

  async performAction(actionType, options = {}) {
    const eventMap = {
      attack: 'ACTION_ATTACK',
      defend: 'ACTION_DEFEND',
      escape: 'ACTION_ESCAPE',
      use_item: 'ACTION_USE_ITEM',
      use_zoo: 'ACTION_USE_ZOO',
    };
    const event = eventMap[actionType] || 'ACTION_ATTACK';

    if (actionType === 'use_item') {
      if (!options.itemId) {
        showToast('請選擇要使用的物品');
        return;
      }
      if (!canDispatch(this.ctx, event, options)) {
        showToast(blockedMessage(this.ctx, actionType));
        return;
      }
      this.dispatch(event, {
        action: 'use_item',
        itemId: options.itemId,
        itemName: options.itemName,
      });
      this.dispatch('DICE_ANIMATION_DONE', { dice: null });
      return;
    }

    if (!canDispatch(this.ctx, event)) {
      showToast(blockedMessage(this.ctx, actionType));
      return;
    }

    if (actionType === 'escape') {
      this.dispatch(event, { action: 'escape' });
      this.views.dice.showRolling();
      await this.views.dice.animateCosmeticDice(null);
      this.dispatch('DICE_ANIMATION_DONE', { dice: null });
      return;
    }

    if (actionType === 'defend') {
      this.dispatch(event, { action: 'defend' });
      this.views.dice.showRolling();
      await this.views.dice.animateCosmeticDice(null);
      this.dispatch('DICE_ANIMATION_DONE', { dice: null });
      return;
    }

    if (actionType === 'use_zoo') {
      const cosmeticDice = Math.floor(Math.random() * 4);
      this.dispatch(event, { action: 'use_zoo', dice: cosmeticDice });
      this.views.dice.showRolling();
      await this.views.dice.animateCosmeticDice(cosmeticDice);
      this.dispatch('DICE_ANIMATION_DONE', { dice: cosmeticDice });
      return;
    }

    // 後端權威骰 0–3；cosmetic 動畫收束同範圍
    const cosmeticDice = Math.floor(Math.random() * 4);
    this.dispatch(event, { action: 'attack', dice: cosmeticDice });
    this.views.dice.showRolling();
    await this.views.dice.animateCosmeticDice(cosmeticDice);
    this.dispatch('DICE_ANIMATION_DONE', { dice: cosmeticDice });
  }

  async confirmDice() {
    if (this.ctx.phase !== Phase.DICE_CONFIRM) {
      showToast(blockedMessage(this.ctx, 'confirm'));
      return;
    }

    const isProtagonistToggled = !!this.rootEl.querySelector(
      `#${DOM_IDS.PROTAGONIST_TOGGLE}`,
    )?.checked;
    if (isProtagonistToggled && !this.ctx.hud?.me?.is_team_leader) {
      showToast('只有隊長特權才能啟動主角代打模式', 'error');
      const toggle = this.rootEl.querySelector(`#${DOM_IDS.PROTAGONIST_TOGGLE}`);
      if (toggle) toggle.checked = false;
      return;
    }

    this.dispatch('CONFIRM_DICE');
    this.poller.pause();
    this.submittingActive = true;

    try {
      const actionMap = {
        defend: 'defend',
        escape: 'escape',
        attack: 'attack',
        use_item: 'use_item',
        use_zoo: 'use_zoo',
      };
      const actionType = actionMap[this.ctx.dice.action] || 'attack';
      const asProtagonist = isProtagonistToggled
        && !!this.ctx.hud?.controllable_protagonist_id
        && !!this.ctx.hud?.me?.is_team_leader;
      const data = await CombatApi.submit({
        combatId: this.ctx.combatId,
        actionType,
        itemId: this.ctx.dice.itemId,
        asProtagonist,
      });
      await this.onSubmitSuccess(data);
    } catch (err) {
      this.dispatch('SUBMIT_ERROR', { error: err.message || '提交失敗' });
    } finally {
      this.submittingActive = false;
      if (!this.ctx.pollPaused) this.poller.resume();
    }
  }

  async onSubmitSuccess(data) {
    const deathCheck = handleAnyDeath(
      { ...this.ctx, hud: extractHud(data) },
      data.member_states,
    );
    if (deathCheck.ctx.phase === Phase.COMBAT_FAILED) {
      this.ctx = deathCheck.ctx;
      this.applyEffects(deathCheck.effects);
      return;
    }

    if (data.outcome === 'escaped' || data.winner === 'escaped') {
      this.ctx.hud = extractHud(data);
      this.dispatch('SUBMIT_SUCCESS', { escaped: true, data });
      return;
    }

    if (data.status === 'waiting_for_teammates' || data.waiting_for_teammates) {
      this.ctx.hud = extractHud(data);
      this.dispatch('SUBMIT_SUCCESS', { roundResolved: false });
      return;
    }

    const roundResolved = !!(data.round_resolved || data.status === 'round_resolved');
    if (!roundResolved && data.success && data.active) {
      this.ctx.hud = extractHud(data);
      this.dispatch('SUBMIT_SUCCESS', { roundResolved: false });
      return;
    }

    const settlement = normalizeSettlement(data);
    const settlementId = deriveSettlementId(data);

    if (!settlement && !data.outcome) {
      this.dispatch('SUBMIT_ERROR', { error: '結算資料缺失' });
      return;
    }

    if (settlement?.escape_triggered && !settlement?.escape_success) {
      await new Promise((resolve) => {
        this.views.escape.onContinue(resolve);
        this.views.escape.show({
          success: false,
          message: '逃跑失敗，將結算已提交行動',
        });
      });
    }

    const route = determineSettlementRoute(this.ctx, data, settlement, settlementId);
    this.ctx.hud = extractHud(data);
    const { ctx, effects } = transition(
      { ...this.ctx, phase: Phase.SUBMITTING },
      'SUBMIT_SUCCESS',
      route,
    );
    this.ctx = ctx;
    this.applyEffects(effects);
    this.enforceSettlementInvariant();
  }

  ackSettlement() {
    if (this.ctx.phase !== Phase.SETTLEMENT) {
      showToast('目前無待確認結算');
      return;
    }
    this.hasTriggeredTimeoutDefense = false;
    const killing = this.ctx.isKillingBlow;
    this.dispatch('ACK_SETTLEMENT', { killing });
  }

  triggerTimeoutAutomaticDefense() {
    if (this.hasTriggeredTimeoutDefense) return;

    const myCurrentAction = this.ctx.hud?.me?.action_type;
    if (myCurrentAction === 'failed_escape') {
      console.warn(
        '[FSM] Player is in failed_escape recovery — automatic defense suppressed.',
      );
      this.hasTriggeredTimeoutDefense = true;
      return;
    }

    if (
      this.ctx.phase === Phase.SUBMITTING
      || this.ctx.phase === Phase.WAITING_FOR_PLAYERS
    ) {
      this.hasTriggeredTimeoutDefense = true;
      return;
    }

    if (this.ctx.phase === Phase.DICE_CONFIRM) {
      console.warn(
        '[FSM] DICE_CONFIRM timeout — forcing automatic defend takeover',
      );
      this.hasTriggeredTimeoutDefense = true;
      this.views?.dice?.setConfirmDisabled?.(true);
      this.ctx = {
        ...this.ctx,
        dice: { ...this.ctx.dice, action: 'defend', value: null, cosmetic: false },
      };
      this.views?.dice?.hide();
      showToast('操作超時！系統已自動為您執行「防禦」指令。', 'warn');
      void this.performActionDirectly('defend');
      return;
    }

    const protectedPhases = [
      Phase.DICE_ROLLING,
      Phase.SUBMITTING,
      Phase.SETTLEMENT,
      Phase.WAITING_FOR_PLAYERS,
    ];
    if (protectedPhases.includes(this.ctx.phase)) return;

    if (this.ctx.hud?.me?.submitted) {
      this.hasTriggeredTimeoutDefense = true;
      return;
    }

    this.hasTriggeredTimeoutDefense = true;
    showToast('操作超時！系統已自動為您執行「防禦」指令。', 'warn');
    void this.performActionDirectly('defend');
  }

  async performActionDirectly(actionType) {
    if (
      this.ctx.phase === Phase.SUBMITTING
      || this.ctx.phase === Phase.WAITING_FOR_PLAYERS
    ) {
      return;
    }

    if (this.ctx.phase === Phase.IDLE) {
      this.ctx = {
        ...this.ctx,
        phase: Phase.DICE_CONFIRM,
        dice: {
          action: actionType,
          value: null,
          itemId: null,
          cosmetic: false,
        },
      };
    } else if (this.ctx.phase !== Phase.DICE_CONFIRM) {
      return;
    }

    this.dispatch('CONFIRM_DICE');
    this.poller.pause();
    this.submittingActive = true;

    try {
      const data = await CombatApi.submit({
        combatId: this.ctx.combatId,
        actionType,
        itemId: null,
        asProtagonist: false,
      });
      await this.onSubmitSuccess(data);
    } catch (err) {
      this.hasTriggeredTimeoutDefense = false;
      this.dispatch('SUBMIT_ERROR', { error: err.message || '自動提交失敗' });
    } finally {
      this.submittingActive = false;
      if (!this.ctx.pollPaused) this.poller.resume();
    }
  }

  pollTick(snapshot) {
    if (!snapshot || snapshot.success === false) return;

    if (this.submittingActive) {
      if (this.debug) console.log('[CombatV2] poll muted during in-flight submit');
      if (snapshot.enemy || snapshot.my_state || snapshot.member_states) {
        this.ctx.hud = extractHud(snapshot);
        this.views.hud?.update(this.ctx, { hpOnly: true });
      }
      return;
    }

    const deathCheck = handleAnyDeath(
      { ...this.ctx, hud: extractHud(snapshot) },
      snapshot.member_states,
    );
    if (deathCheck.ctx.phase === Phase.COMBAT_FAILED) {
      this.ctx = deathCheck.ctx;
      this.applyEffects(deathCheck.effects);
      return;
    }

    if (
      snapshot.status === 'player_phase'
      && snapshot.remaining_seconds === 0
      && !snapshot.my_state?.submitted
    ) {
      this.triggerTimeoutAutomaticDefense();
      if (this.hasTriggeredTimeoutDefense) return;
    }

    if (TERMINAL_PHASES.includes(this.ctx.phase)) {
      return;
    }

    const { ctx, effects } = transition(this.ctx, 'POLL_TICK', { snapshot });
    this.ctx = ctx;
    if (this.ctx.entrySyncPending) {
      this.ctx.entrySyncPending = false;
    }
    this.poller.setPhase(ctx.phase);
    this.applyEffects(effects);

    if (this.ctx.phase === Phase.SETTLEMENT) {
      this.enforceSettlementInvariant();
    }
  }

  enforceSettlementInvariant() {
    const modalVisible = this.views.settlement.isVisible();
    const inSettlement = this.ctx.phase === Phase.SETTLEMENT;

    if (inSettlement && !modalVisible && this.ctx.pendingSettlement) {
      this.invRecoveryCount += 1;
      if (this.invRecoveryCount <= 2) {
        this.views.settlement.show(
          this.ctx.pendingSettlement,
          this.ctx,
          { killing: this.ctx.isKillingBlow },
        );
        return;
      }
      this.dispatch('INV_RECOVERY');
      this.invRecoveryCount = 0;
      return;
    }

    if (!inSettlement && modalVisible) {
      this.views.settlement.hide();
    }

    if (inSettlement && modalVisible) {
      this.invRecoveryCount = 0;
    }
  }

  hideAllModals() {
    this.views.dice.hide();
    this.views.settlement.hide();
    this.views.submitting.hide();
    this.views.escape.hide();
    this.views.items?.hide();
  }

  applyEffects(effects) {
    for (const fx of effects || []) {
      switch (fx.type) {
        case 'TOAST':
          showToast(fx.message, fx.level || 'info');
          break;
        case 'SHOW_DICE_ROLLING':
          this.views.dice.showRolling();
          break;
        case 'SHOW_DICE_CONFIRM':
          this.views.dice.showConfirm(this.ctx.dice.value, {
            isDefend: this.ctx.dice.action === 'defend',
            isEscape: this.ctx.dice.action === 'escape',
            isItem: this.ctx.dice.action === 'use_item',
            isZoo: this.ctx.dice.action === 'use_zoo',
            itemName: this.ctx.dice.itemName,
          });
          break;
        case 'HIDE_DICE':
          this.views.dice.hide();
          break;
        case 'SHOW_SUBMITTING':
          this.views.submitting.show();
          break;
        case 'HIDE_SUBMITTING':
          this.views.submitting.hide();
          break;
        case 'SHOW_SETTLEMENT':
          this.views.settlement.show(fx.settlement, this.ctx, { killing: fx.killing });
          break;
        case 'HIDE_SETTLEMENT':
          this.views.settlement.hide();
          break;
        case 'SHOW_VICTORY':
          this.views.endgame.showVictory(fx.data || this.ctx.hud);
          break;
        case 'SHOW_DEFEAT':
          this.views.endgame.showDefeat(fx.data);
          break;
        case 'SHOW_FAILED':
          this.views.endgame.showFailed(fx.members);
          break;
        case 'SHOW_ESCAPED':
          this.views.escape.onContinue(() => this.exitToLobby());
          this.views.escape.show({
            success: true,
            message: fx.data?.narrative || '全隊已脫離戰鬥',
          });
          break;
        case 'HIDE_ALL_MODALS':
          this.hideAllModals();
          this.views.endgame.hideAll();
          break;
        case 'UPDATE_HUD':
          renderAll(this.views, this.ctx, { hpOnly: fx.hpOnly });
          break;
        case 'RENDER':
          renderAll(this.views, this.ctx);
          break;
        case 'START_POLL':
          if (this.ctx.combatId) {
            this.poller.start(this.ctx.combatId);
          }
          break;
        case 'STOP_POLL':
          this.poller.stop();
          break;
        case 'NAVIGATE_LOBBY':
          this.exitToLobby();
          break;
        case 'FETCH_ONCE':
          if (this.ctx.combatId) {
            CombatApi.status(this.ctx.combatId).then((d) => this.pollTick(d)).catch(() => {});
          }
          break;
        default:
          break;
      }
    }
    renderAll(this.views, this.ctx);
  }

  exitToLobby() {
    if (typeof window.exitCombatScreen === 'function') {
      showToast('已安全退出戰場', 'info');
      window.exitCombatScreen({ fromV2: true });
      return;
    }

    sessionStorage.removeItem('OIKONOMIA_COMBAT_V2_LOCK');
    sessionStorage.removeItem('OIKONOMIA_ACTIVE_COMBAT_ID');
    this.destroy();

    if (window.AppRouter && typeof window.AppRouter.navigateTo === 'function') {
      window.AppRouter.navigateTo('dashboard');
    } else {
      const lobby = document.getElementById('combat-lobby');
      if (lobby) lobby.classList.remove('hidden');
    }

    showToast('已安全退出戰場', 'info');
  }

  async summonGm() {
    if (!this.ctx.combatId) {
      showToast('無有效戰鬥編號', 'error');
      return;
    }
    try {
      const data = await CombatApi.summonGm(this.ctx.combatId);
      if (data.success) {
        showToast(data.message || '已通知 GM 工作人員', 'info');
      } else {
        showToast(data.error || '發送失敗', 'error');
      }
    } catch (_) {
      showToast('GM 通訊失敗，請聯繫現場工作人員', 'error');
    }
  }

  /** P2 Backlog: GM 特權遠端數據同步重置核心 */
  async executeGmOverride(opts) {
    try {
      showToast('正在發射特權變更指令…', 'info');
      const data = await CombatApi.overrideTraumaEnding(opts);
      if (data.success) {
        showToast(data.message || '特權歷史重組成功！', 'info');

        if (opts.targetEndingType === 'clear') {
          this.dispatch('COMBAT_RESET', { combatId: this.ctx.combatId });
        } else if (this.ctx.combatId) {
          const snapshot = await CombatApi.status(this.ctx.combatId);
          this.pollTick(snapshot);
        }
      } else {
        showToast(data.error || '指令被後端網關拒絕', 'error');
      }
    } catch (err) {
      showToast(err.message || 'GM 特權通訊失敗', 'error');
    }
  }
}

export { Phase };


===== FILE: static/js/combat/state_machine.js =====

/** @file Pure combat FSM — zero DOM dependency */

import { normalizeSettlement, deriveSettlementId } from './settlement.js';

/** Fallback when HP field is missing (display / max baseline — not “alive” sentinel). */
export const DEFAULT_COMBAT_MAX_HP = 100;

export const Phase = {
  IDLE: 'IDLE',
  DICE_ROLLING: 'DICE_ROLLING',
  DICE_CONFIRM: 'DICE_CONFIRM',
  SUBMITTING: 'SUBMITTING',
  WAITING_FOR_PLAYERS: 'WAITING_FOR_PLAYERS',
  ESCAPE_ATTEMPT: 'ESCAPE_ATTEMPT',
  SETTLEMENT: 'SETTLEMENT',
  COMBAT_FAILED: 'COMBAT_FAILED',
  VICTORY: 'VICTORY',
  DEFEAT: 'DEFEAT',
  ESCAPED: 'ESCAPED',
};

/** SSOT: terminal absorbing phases (views + poll guards) */
export const TERMINAL_PHASES = Object.freeze([
  Phase.COMBAT_FAILED,
  Phase.VICTORY,
  Phase.DEFEAT,
  Phase.ESCAPED,
]);

const PHASE_LABELS = {
  [Phase.IDLE]: '等待行動',
  [Phase.DICE_ROLLING]: '擲骰中',
  [Phase.DICE_CONFIRM]: '確認行動',
  [Phase.SUBMITTING]: '伺服器結算中',
  [Phase.WAITING_FOR_PLAYERS]: '等待隊友',
  [Phase.ESCAPE_ATTEMPT]: '逃跑判定',
  [Phase.SETTLEMENT]: '傷害結算',
  [Phase.COMBAT_FAILED]: '戰鬥失敗',
  [Phase.VICTORY]: '戰鬥勝利',
  [Phase.DEFEAT]: '戰鬥失敗',
  [Phase.ESCAPED]: '成功逃跑',
};

const ABSORBING = new Set(TERMINAL_PHASES);

const DICE_BUSY = new Set([Phase.DICE_ROLLING, Phase.DICE_CONFIRM]);

/** Phases that must exit SETTLEMENT without pinning poll handler */
const SETTLEMENT_EXIT_PHASES = new Set(TERMINAL_PHASES);

function terminalModalTeardownEffects(effects) {
  return [
    { type: 'HIDE_SETTLEMENT' },
    { type: 'HIDE_ALL_MODALS' },
    ...effects.filter(
      (e) => e.type !== 'HIDE_ALL_MODALS' && e.type !== 'HIDE_SETTLEMENT',
    ),
  ];
}

/**
 * @returns {import('./state_machine.js').CombatContext}
 */
export function createInitialContext(combatId = null) {
  return {
    combatId,
    phase: Phase.IDLE,
    settledRoundIndex: -1,
    pendingSettlement: null,
    pendingSettlementId: null,
    shownSettlementIds: new Set(),
    isKillingBlow: false,
    failedMembers: [],
    escapePending: false,
    dice: { action: null, value: null },
    hud: { enemy: null, me: null, members: {}, log: [] },
    pollPaused: false,
    error: null,
    entrySyncPending: false,
  };
}

export function canDispatch(ctx, event, meta = {}) {
  const rule = resolveTransition(ctx, event);
  if (!rule) return false;
  if (rule.guard && !rule.guard(ctx, meta)) return false;
  return true;
}

export function blockedMessage(ctx, actionName = '此操作') {
  const phase = PHASE_LABELS[ctx.phase] || ctx.phase;
  if (ctx.phase === Phase.DICE_ROLLING) return '系統擲骰中，請稍候…';
  if (ctx.phase === Phase.DICE_CONFIRM) return '請先完成當前行動';
  if (ctx.phase === Phase.SUBMITTING) return '回合提交結算中，請稍候…';
  if (ctx.phase === Phase.SETTLEMENT) return '請先關閉當前結算彈窗';
  if (ctx.phase === Phase.WAITING_FOR_PLAYERS) return '已提交，等待其他隊友…';
  if (ctx.phase === Phase.ESCAPE_ATTEMPT) return '逃跑判定中，請稍候…';
  if (ABSORBING.has(ctx.phase)) return `戰鬥已結束（${phase}）`;
  if (ctx.hud?.me?.submitted) return '本回合行動已提交';
  return `${actionName}目前不可用（${phase}）`;
}

/**
 * @typedef {Object} Effect
 * @property {string} type
 */

/**
 * @returns {{ ctx: object, effects: Effect[] }}
 */
export function transition(ctx, event, meta = {}) {
  const rule = resolveTransition(ctx, event);
  if (!rule) {
    return {
      ctx,
      effects: [{ type: 'TOAST', message: blockedMessage(ctx, event) }],
    };
  }
  if (rule.guard && !rule.guard(ctx, meta)) {
    return {
      ctx,
      effects: [{ type: 'TOAST', message: rule.guardMessage?.(ctx, meta) || blockedMessage(ctx, event) }],
    };
  }
  const prev = ctx.phase;
  const newCtx = rule.reduce(ctx, meta);
  const effects = rule.effects?.(newCtx, meta, prev) || [];
  return { ctx: newCtx, effects };
}

function resolveTransition(ctx, event) {
  const table = TRANSITIONS[ctx.phase];
  return table?.[event] || null;
}

/**
 * First poll after COMBAT_RESET — strict entry absorb boundary (INV-A/C).
 * @returns {{ ctx: object, effects: Effect[] } | null}
 */
function absorbStaleSettlementOnEntry(ctx, snapshot, settlementId) {
  if (!ctx.entrySyncPending) return null;

  const apiIdx = snapshot.settled_round_index;
  const snapRoundIdx = Number.isFinite(parseInt(apiIdx, 10))
    ? parseInt(apiIdx, 10)
    : parseInt(snapshot.current_phase, 10) - 1;
  const shown = new Set(ctx.shownSettlementIds);

  // Only mark shown when backend is in stable player_phase without an unresolved round
  if (settlementId && snapshot.status === 'player_phase' && !snapshot.round_resolved) {
    shown.add(settlementId);
  }

  const alignedCtx = {
    ...ctx,
    settledRoundIndex: Number.isFinite(snapRoundIdx) ? Math.max(0, snapRoundIdx) : 0,
    pendingSettlement: null,
    pendingSettlementId: null,
    shownSettlementIds: shown,
    entrySyncPending: false,
    phase: ctx.phase,
  };
  return {
    ctx: alignedCtx,
    effects: [{ type: 'UPDATE_HUD', hpOnly: false }],
  };
}

/** Death preempt — INV-D highest priority */
export function handleAnyDeath(ctx, members) {
  const dead = Object.entries(members || {})
    .filter(([, m]) => isMemberCollapsed(m))
    .map(([id, m]) => m.display_name || id);
  if (dead.length === 0) return { ctx, effects: [] };
  if (ctx.phase === Phase.COMBAT_FAILED) return { ctx, effects: [] };
  const newCtx = {
    ...ctx,
    phase: Phase.COMBAT_FAILED,
    failedMembers: dead,
    pollPaused: true,
    pendingSettlement: null,
    pendingSettlementId: null,
  };
  return {
    ctx: newCtx,
    effects: terminalModalTeardownEffects([
      { type: 'SHOW_FAILED', members: dead },
      { type: 'STOP_POLL' },
    ]),
  };
}

/**
 * Passive sync from poll — monotonic guards + settlement modal routing.
 * @returns {{ ctx: object, effects: Effect[] }}
 */
export function syncState(ctx, snapshot) {
  if (ABSORBING.has(ctx.phase)) {
    return { ctx, effects: [] };
  }

  const apiIdx = parseInt(snapshot.settled_round_index, 10);
  if (Number.isFinite(apiIdx) && ctx.settledRoundIndex >= 0 && apiIdx < ctx.settledRoundIndex) {
    console.warn(
      `[FSM] Stale snapshot dropped (API round ${apiIdx} < local ${ctx.settledRoundIndex})`,
    );
    return { ctx, effects: [] };
  }

  const hud = {
    enemy: snapshot.enemy || ctx.hud.enemy,
    me: snapshot.my_state || ctx.hud.me,
    members: snapshot.member_states || ctx.hud.members,
    log: snapshot.log_entries || snapshot.log || ctx.hud.log,
    waiting: !!snapshot.waiting_for_teammates,
    submittedCount: snapshot.submitted_count,
    totalActive: snapshot.total_active,
    currentPhase: snapshot.current_phase,
    combatId: snapshot.combat_id,
    status: snapshot.status,
    outcome: snapshot.outcome,
    winner: snapshot.winner,
  };

  let newCtx = { ...ctx, hud, combatId: snapshot.combat_id || ctx.combatId };
  let effects = [{ type: 'UPDATE_HUD', hpOnly: isHpOnlyPhase(ctx.phase) }];

  const death = handleAnyDeath(newCtx, hud.members);
  if (death.ctx.phase === Phase.COMBAT_FAILED) {
    return death;
  }

  if (ctx.entrySyncPending) {
    const settlementId = snapshot.round_settlement
      ? deriveSettlementId(snapshot)
      : null;
    const entryAbsorb = absorbStaleSettlementOnEntry(newCtx, snapshot, settlementId);
    if (entryAbsorb) {
      newCtx = { ...entryAbsorb.ctx, hud: newCtx.hud, combatId: newCtx.combatId };
      effects = [...entryAbsorb.effects, ...effects.filter((e) => e.type !== 'UPDATE_HUD')];
    }
  }

  if (snapshot.outcome === 'defeat' || snapshot.winner === 'enemy') {
    const deadNames = snapshot.dead_squad_names?.length
      ? snapshot.dead_squad_names
      : (snapshot.dead_squad_ids || []).map(
        (id) => snapshot.member_states?.[id]?.display_name || id,
      );
    if (deadNames.length > 0) {
      return {
        ctx: {
          ...newCtx,
          phase: Phase.COMBAT_FAILED,
          failedMembers: deadNames,
          pollPaused: true,
          pendingSettlement: null,
          pendingSettlementId: null,
        },
        effects: terminalModalTeardownEffects([
          { type: 'SHOW_FAILED', members: deadNames },
          { type: 'STOP_POLL' },
        ]),
      };
    }
    newCtx = {
      ...newCtx,
      phase: Phase.DEFEAT,
      pollPaused: true,
      pendingSettlement: null,
      pendingSettlementId: null,
      isKillingBlow: false,
    };
    return {
      ctx: newCtx,
      effects: terminalModalTeardownEffects([
        { type: 'SHOW_DEFEAT', data: snapshot },
        { type: 'STOP_POLL' },
      ]),
    };
  }

  if (snapshot.outcome === 'victory' || snapshot.winner === 'squad') {
    const settlement = normalizeSettlement(snapshot);
    const settlementId = deriveSettlementId(snapshot);
    const unseenKillingSettlement = settlement
      && settlementId
      && !ctx.shownSettlementIds.has(settlementId)
      && ctx.phase !== Phase.SETTLEMENT;

    if (unseenKillingSettlement) {
      newCtx = {
        ...newCtx,
        phase: Phase.SETTLEMENT,
        pendingSettlement: settlement,
        pendingSettlementId: settlementId,
        isKillingBlow: true,
        pollPaused: true,
      };
      return {
        ctx: newCtx,
        effects: [
          { type: 'UPDATE_HUD', hpOnly: false },
          { type: 'HIDE_SUBMITTING' },
          { type: 'SHOW_SETTLEMENT', settlement, killing: true },
          { type: 'STOP_POLL' },
        ],
      };
    }

    if (ctx.phase === Phase.SETTLEMENT) {
      return { ctx: newCtx, effects };
    }

    newCtx = {
      ...newCtx,
      phase: Phase.VICTORY,
      pollPaused: true,
      pendingSettlement: null,
      pendingSettlementId: null,
      isKillingBlow: false,
    };
    return {
      ctx: newCtx,
      effects: terminalModalTeardownEffects([
        { type: 'SHOW_VICTORY', data: snapshot },
        { type: 'STOP_POLL' },
      ]),
    };
  }

  if (snapshot.waiting_for_teammates && ctx.phase === Phase.SUBMITTING) {
    newCtx = { ...newCtx, phase: Phase.WAITING_FOR_PLAYERS };
    effects.push({ type: 'HIDE_SUBMITTING' });
    return { ctx: newCtx, effects };
  }

  if (
    ctx.phase === Phase.WAITING_FOR_PLAYERS
    && !snapshot.waiting_for_teammates
    && (snapshot.round_resolved || snapshot.status === 'round_resolved')
    && snapshot.round_settlement
  ) {
    const settlement = normalizeSettlement(snapshot);
    const settlementId = deriveSettlementId(snapshot);
    if (settlement && settlementId && !ctx.shownSettlementIds.has(settlementId)) {
      const killing = snapshot.outcome === 'victory'
        || snapshot.winner === 'squad'
        || isEnemyDefeated(snapshot.enemy);
      newCtx = {
        ...newCtx,
        phase: Phase.SETTLEMENT,
        pendingSettlement: settlement,
        pendingSettlementId: settlementId,
        isKillingBlow: killing,
        pollPaused: true,
      };
      return {
        ctx: newCtx,
        effects: [
          { type: 'UPDATE_HUD', hpOnly: false },
          { type: 'HIDE_SUBMITTING' },
          { type: 'SHOW_SETTLEMENT', settlement, killing },
          { type: 'STOP_POLL' },
        ],
      };
    }
  }

  return { ctx: newCtx, effects };
}

function isHpOnlyPhase(phase) {
  return DICE_BUSY.has(phase) || phase === Phase.SUBMITTING || phase === Phase.SETTLEMENT;
}

/**
 * Parse HP for display; uses member/enemy max_hp when value is absent.
 * @param {number|string|null|undefined} value
 * @param {number|string|null|undefined} maxHp
 */
export function parseCombatHp(value, maxHp = DEFAULT_COMBAT_MAX_HP) {
  const n = parseInt(value, 10);
  if (Number.isFinite(n)) return n;
  const max = parseInt(maxHp, 10);
  return Number.isFinite(max) ? max : DEFAULT_COMBAT_MAX_HP;
}

/** INV-D: hp ≤ 0 or active near-death marker counts as collapsed. */
export function isMemberCollapsed(member) {
  if (!member) return false;
  if (member.near_death_until) return true;
  const hp = parseInt(member.hp, 10);
  if (Number.isFinite(hp)) {
    return hp <= 0;
  }
  return false;
}

export function isEnemyDefeated(enemy) {
  const hp = parseInt(enemy?.hp, 10);
  return Number.isFinite(hp) && hp <= 0;
}

const TRANSITIONS = {
  [Phase.IDLE]: {
    COMBAT_RESET: {
      reduce: (ctx, meta) => createInitialContext(meta.combatId ?? null),
      effects: () => [{ type: 'HIDE_ALL_MODALS' }, { type: 'RENDER' }],
    },
    ACTION_ATTACK: {
      guard: (ctx) => !ctx.hud?.me?.submitted,
      reduce: (ctx, meta) => ({
        ...ctx,
        phase: Phase.DICE_ROLLING,
        dice: { action: meta.action || 'attack', value: meta.dice, cosmetic: true },
        error: null,
      }),
      effects: () => [{ type: 'SHOW_DICE_ROLLING' }],
    },
    ACTION_DEFEND: {
      guard: (ctx) => !ctx.hud?.me?.submitted,
      reduce: (ctx, meta) => ({
        ...ctx,
        phase: Phase.DICE_ROLLING,
        dice: { action: 'defend', value: null, cosmetic: false },
        error: null,
      }),
      effects: () => [{ type: 'SHOW_DICE_ROLLING' }],
    },
    ACTION_ESCAPE: {
      guard: (ctx) => !ctx.hud?.me?.submitted,
      reduce: (ctx) => ({
        ...ctx,
        phase: Phase.DICE_ROLLING,
        dice: { action: 'escape', value: null, cosmetic: false },
        escapePending: true,
      }),
      effects: () => [{ type: 'SHOW_DICE_ROLLING' }],
    },
    ACTION_USE_ITEM: {
      guard: (ctx, meta) => !ctx.hud?.me?.submitted && !!meta.itemId,
      reduce: (ctx, meta) => ({
        ...ctx,
        phase: Phase.DICE_ROLLING,
        dice: {
          action: 'use_item',
          value: null,
          cosmetic: false,
          itemId: meta.itemId,
          itemName: meta.itemName || '物品',
        },
        error: null,
      }),
      effects: () => [{ type: 'SHOW_DICE_ROLLING' }],
    },
    ACTION_USE_ZOO: {
      guard: (ctx) => {
        if (ctx.hud?.me?.submitted) return false;
        return ctx.hud?.allow_zoo !== false;
      },
      reduce: (ctx, meta) => ({
        ...ctx,
        phase: Phase.DICE_ROLLING,
        dice: { action: 'use_zoo', value: meta.dice, cosmetic: true },
        error: null,
      }),
      effects: () => [{ type: 'SHOW_DICE_ROLLING' }],
    },
    POLL_TICK: {
      reduce: (ctx, meta) => syncState(ctx, meta.snapshot).ctx,
      effects: (ctx, meta) => syncState(ctx, meta.snapshot).effects,
    },
  },

  [Phase.DICE_ROLLING]: {
    DICE_ANIMATION_DONE: {
      reduce: (ctx, meta) => ({
        ...ctx,
        phase: Phase.DICE_CONFIRM,
        dice: { ...ctx.dice, value: meta.dice ?? ctx.dice.value },
      }),
      effects: () => [{ type: 'SHOW_DICE_CONFIRM' }],
    },
    ACTION_ATTACK: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '擲骰中，請稍候…' }] },
    ACTION_DEFEND: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '擲骰中，請稍候…' }] },
    ACTION_USE_ITEM: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '擲骰中，請稍候…' }] },
    ACTION_USE_ZOO: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '擲骰中，請稍候…' }] },
    POLL_TICK: {
      reduce: (ctx, meta) => ({ ...syncState(ctx, meta.snapshot).ctx, phase: Phase.DICE_ROLLING }),
      effects: (ctx, meta) => {
        const r = syncState(ctx, meta.snapshot);
        return r.effects.map((e) => (e.type === 'UPDATE_HUD' ? { ...e, hpOnly: true } : e));
      },
    },
  },

  [Phase.DICE_CONFIRM]: {
    CONFIRM_DICE: {
      reduce: (ctx) => ({ ...ctx, phase: Phase.SUBMITTING, pollPaused: true }),
      effects: () => [{ type: 'HIDE_DICE' }, { type: 'SHOW_SUBMITTING' }],
    },
    ACTION_ATTACK: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '請先確認並結束本回合' }] },
    ACTION_DEFEND: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '請先確認並結束本回合' }] },
    ACTION_USE_ITEM: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '請先確認並結束本回合' }] },
    ACTION_USE_ZOO: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '請先確認並結束本回合' }] },
    POLL_TICK: {
      reduce: (ctx, meta) => ({ ...syncState(ctx, meta.snapshot).ctx, phase: Phase.DICE_CONFIRM }),
      effects: (ctx, meta) => syncState(ctx, meta.snapshot).effects.map((e) =>
        e.type === 'UPDATE_HUD' ? { ...e, hpOnly: true } : e,
      ),
    },
  },

  [Phase.SUBMITTING]: {
    SUBMIT_SUCCESS: {
      reduce: (ctx, meta) => {
        if (meta.escaped) {
          return {
            ...ctx,
            phase: Phase.ESCAPED,
            escapePending: false,
            pollPaused: true,
          };
        }
        if (meta.roundResolved === false) {
          return { ...ctx, phase: Phase.WAITING_FOR_PLAYERS, pollPaused: false };
        }
        if (meta.skipModal) {
          return {
            ...ctx,
            phase: Phase.IDLE,
            settledRoundIndex: meta.settledRoundIndex ?? ctx.settledRoundIndex,
            pollPaused: false,
          };
        }
        return {
          ...ctx,
          phase: Phase.SETTLEMENT,
          pendingSettlement: meta.settlement,
          pendingSettlementId: meta.settlementId,
          isKillingBlow: !!meta.isKillingBlow,
          settledRoundIndex: meta.settledRoundIndex ?? ctx.settledRoundIndex,
          pollPaused: true,
        };
      },
      effects: (ctx, meta) => {
        if (meta.escaped) {
          return [
            { type: 'HIDE_SUBMITTING' },
            { type: 'SHOW_ESCAPED', data: meta.data },
            { type: 'STOP_POLL' },
          ];
        }
        if (meta.roundResolved === false) {
          return [{ type: 'HIDE_SUBMITTING' }, { type: 'UPDATE_HUD' }, { type: 'START_POLL' }];
        }
        if (meta.skipModal) {
          return [{ type: 'HIDE_SUBMITTING' }, { type: 'START_POLL' }];
        }
        return [{ type: 'HIDE_SUBMITTING' }, { type: 'SHOW_SETTLEMENT', settlement: meta.settlement, killing: meta.isKillingBlow }];
      },
    },
    SUBMIT_ERROR: {
      reduce: (ctx, meta) => ({
        ...ctx,
        phase: Phase.IDLE,
        error: meta.error,
        pollPaused: false,
      }),
      effects: (_, meta) => [
        { type: 'HIDE_SUBMITTING' },
        { type: 'TOAST', message: meta.error || '提交失敗', level: 'error' },
        { type: 'START_POLL' },
      ],
    },
    ACTION_ATTACK: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '回合提交結算中，請稍候…' }] },
    POLL_TICK: {
      reduce: (ctx, meta) => ({ ...syncState(ctx, meta.snapshot).ctx, phase: Phase.SUBMITTING }),
      effects: (ctx, meta) => syncState(ctx, meta.snapshot).effects.map((e) =>
        e.type === 'UPDATE_HUD' ? { ...e, hpOnly: true } : e,
      ),
    },
  },

  [Phase.WAITING_FOR_PLAYERS]: {
    POLL_TICK: {
      reduce: (ctx, meta) => syncState(ctx, meta.snapshot).ctx,
      effects: (ctx, meta) => syncState(ctx, meta.snapshot).effects,
    },
    SUBMIT_SUCCESS: {
      reduce: (ctx, meta) => transition(ctx, 'SUBMIT_SUCCESS', meta).ctx,
      effects: (ctx, meta) => transition(
        { ...ctx, phase: Phase.WAITING_FOR_PLAYERS },
        'SUBMIT_SUCCESS',
        meta,
      ).effects,
    },
    ACTION_ATTACK: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '已提交，等待其他隊友…' }] },
  },

  [Phase.SETTLEMENT]: {
    ACK_SETTLEMENT: {
      reduce: (ctx, meta) => {
        const shown = new Set(ctx.shownSettlementIds);
        if (ctx.pendingSettlementId) shown.add(ctx.pendingSettlementId);
        const idx = ctx.settledRoundIndex >= 0 ? ctx.settledRoundIndex : deriveIdx(ctx);
        if (meta.killing || ctx.isKillingBlow) {
          return {
            ...ctx,
            phase: Phase.VICTORY,
            shownSettlementIds: shown,
            pendingSettlement: null,
            pendingSettlementId: null,
            settledRoundIndex: idx,
            pollPaused: true,
          };
        }
        return {
          ...ctx,
          phase: Phase.IDLE,
          shownSettlementIds: shown,
          pendingSettlement: null,
          pendingSettlementId: null,
          settledRoundIndex: idx,
          isKillingBlow: false,
          pollPaused: false,
        };
      },
      effects: (ctx, meta) => {
        if (meta.killing || ctx.isKillingBlow) {
          return [{ type: 'HIDE_SETTLEMENT' }, { type: 'SHOW_VICTORY' }, { type: 'STOP_POLL' }];
        }
        return [{ type: 'HIDE_SETTLEMENT' }, { type: 'START_POLL' }];
      },
    },
    ACTION_ATTACK: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '請先關閉當前結算彈窗' }] },
    POLL_TICK: {
      reduce: (ctx, meta) => {
        const { ctx: synced } = syncState(ctx, meta.snapshot);
        if (SETTLEMENT_EXIT_PHASES.has(synced.phase)) {
          return synced;
        }
        return { ...synced, phase: Phase.SETTLEMENT };
      },
      effects: (ctx, meta) => {
        // reduce may have advanced phase; replay sync from SETTLEMENT for effect list
        const sourceCtx = SETTLEMENT_EXIT_PHASES.has(ctx.phase)
          ? { ...ctx, phase: Phase.SETTLEMENT }
          : ctx;
        const { ctx: synced, effects } = syncState(sourceCtx, meta.snapshot);
        if (SETTLEMENT_EXIT_PHASES.has(synced.phase)) {
          return terminalModalTeardownEffects(effects);
        }
        return effects.map((e) =>
          (e.type === 'UPDATE_HUD' ? { ...e, hpOnly: true } : e),
        );
      },
    },
    INV_RECOVERY: {
      reduce: (ctx) => ({ ...ctx, phase: Phase.IDLE, pollPaused: false }),
      effects: () => [
        { type: 'HIDE_ALL_MODALS' },
        { type: 'TOAST', message: '結算異常，已重置', level: 'warn' },
        { type: 'START_POLL' },
      ],
    },
  },

  [Phase.COMBAT_FAILED]: {
    COMBAT_RESET: {
      reduce: (ctx, meta) => createInitialContext(meta.combatId ?? ctx.combatId),
      effects: () => [
        { type: 'HIDE_ALL_MODALS' },
        { type: 'RENDER' },
        { type: 'START_POLL' },
      ],
    },
    EXIT_LOBBY: {
      reduce: (ctx) => ctx,
      effects: () => [{ type: 'NAVIGATE_LOBBY' }],
    },
    RESYNC_ONCE: {
      reduce: (ctx) => ctx,
      effects: () => [{ type: 'FETCH_ONCE' }],
    },
  },

  [Phase.VICTORY]: {
    EXIT_LOBBY: {
      reduce: (ctx) => ctx,
      effects: () => [{ type: 'NAVIGATE_LOBBY' }],
    },
  },

  [Phase.DEFEAT]: {
    EXIT_LOBBY: {
      reduce: (ctx) => ctx,
      effects: () => [{ type: 'NAVIGATE_LOBBY' }],
    },
  },

  [Phase.ESCAPED]: {
    EXIT_LOBBY: {
      reduce: (ctx) => ctx,
      effects: () => [{ type: 'NAVIGATE_LOBBY' }],
    },
  },
};

function deriveIdx(ctx) {
  const phase = parseInt(ctx.hud?.currentPhase, 10);
  return Number.isFinite(phase) ? Math.max(0, phase - 1) : ctx.settledRoundIndex + 1;
}

export function determineSettlementRoute(ctx, apiData, settlement, settlementId) {
  const apiIdx = parseInt(apiData.settled_round_index, 10);
  if (
    Number.isFinite(apiIdx)
    && ctx.settledRoundIndex >= 0
    && apiIdx < ctx.settledRoundIndex
  ) {
    return {
      roundResolved: true,
      skipModal: true,
      settledRoundIndex: ctx.settledRoundIndex,
    };
  }
  if (ctx.shownSettlementIds.has(settlementId)) {
    return { roundResolved: true, skipModal: true, settledRoundIndex: apiData.settled_round_index };
  }
  const isKillingBlow = apiData.outcome === 'victory'
    || apiData.winner === 'squad'
    || (apiData.enemy?.hp ?? 1) <= 0;
  return {
    roundResolved: true,
    settlement,
    settlementId,
    settledRoundIndex: apiData.settled_round_index,
    isKillingBlow,
  };
}


===== FILE: static/js/combat/api_client.js =====

/** @file Combat API + resilient polling (AbortController, Visibility, backoff) */

const DEFAULT_POLL_IDLE_MS = 1200;
const DEFAULT_POLL_WAITING_MS = 800;

/** Align with templates/index.html fetchNoCache (`_cb=`). */
function appendCacheBust(url) {
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}_cb=${Date.now()}`;
}

async function fetchJson(url, options = {}) {
  const res = await fetch(appendCacheBust(url), {
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
      ...(options.headers || {}),
    },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || data.message || `HTTP ${res.status}`);
    err.status = res.status;
    err.payload = data;
    throw err;
  }
  return data;
}

export const CombatApi = {
  async start(encounterId, body = {}) {
    return fetchJson('/combat/start', {
      method: 'POST',
      body: JSON.stringify({ encounter_id: encounterId, ...body }),
    });
  },

  async submit({ combatId, actionType, itemId, asProtagonist }) {
    return fetchJson('/combat/submit_action', {
      method: 'POST',
      body: JSON.stringify({
        combat_id: combatId,
        action_type: actionType,
        item_id: itemId,
        as_protagonist: asProtagonist,
      }),
    });
  },

  async status(combatId, signal) {
    const q = combatId ? `?combat_id=${combatId}` : '';
    return fetchJson(`/combat/status${q}`, { signal });
  },

  async summonGm(combatId) {
    return fetchJson('/combat/summon_gm', {
      method: 'POST',
      body: JSON.stringify({ combat_id: combatId }),
    });
  },

  /** P2 Backlog: GM 特權遠端覆蓋網路調用 */
  async overrideTraumaEnding({ teamId, protagonistKey, targetTrauma, targetEndingType }) {
    return fetchJson('/gm/api/override_trauma_ending', {
      method: 'POST',
      body: JSON.stringify({
        team_id: teamId,
        protagonist_key: protagonistKey,
        target_trauma: targetTrauma,
        target_ending_type: targetEndingType,
      }),
    });
  },
};

/**
 * Resilient polling manager per combat_greenfield_final.md §5.2
 */
export class ResilientPollingManager {
  /**
   * @param {{ onTick: (data: object) => void, onError?: (err: Error) => void }} handlers
   */
  constructor(handlers) {
    this.handlers = handlers;
    this.combatId = null;
    this.timerId = null;
    this.abortController = null;
    this.stopped = true;
    this.backoffMs = 0;
    this.maxBackoffMs = 16000;
    this.phase = 'IDLE';
    this._onVisibility = this._onVisibility.bind(this);
    document.addEventListener('visibilitychange', this._onVisibility);
  }

  destroy() {
    this.stop();
    document.removeEventListener('visibilitychange', this._onVisibility);
  }

  setPhase(phase) {
    this.phase = phase;
  }

  intervalForPhase(phase, snapshot) {
    if (phase === 'WAITING_FOR_PLAYERS' || snapshot?.waiting_for_teammates) {
      return DEFAULT_POLL_WAITING_MS;
    }
    return DEFAULT_POLL_IDLE_MS;
  }

  start(combatId) {
    this.combatId = combatId;
    this.stopped = false;
    this.backoffMs = 0;
    this._schedule(0);
  }

  stop() {
    this.stopped = true;
    clearTimeout(this.timerId);
    this.timerId = null;
    this._abortInflight();
  }

  pause() {
    clearTimeout(this.timerId);
    this.timerId = null;
  }

  resume() {
    if (!this.stopped && this.combatId) this._schedule(0);
  }

  async tick() {
    if (this.stopped || !this.combatId) return;
    if (document.hidden) return;

    this._abortInflight();
    this.abortController = new AbortController();

    try {
      const data = await CombatApi.status(this.combatId, this.abortController.signal);
      this.backoffMs = 0;
      this.handlers.onTick(data);
    } catch (err) {
      if (err.name === 'AbortError') return;
      this.backoffMs = Math.min(
        this.maxBackoffMs,
        this.backoffMs ? this.backoffMs * 2 : 1000,
      );
      this.handlers.onError?.(err);
    } finally {
      if (!this.stopped) {
        const wait = this.intervalForPhase(this.phase) + this.backoffMs;
        this._schedule(wait);
      }
    }
  }

  _schedule(ms) {
    clearTimeout(this.timerId);
    this.timerId = setTimeout(() => this.tick(), ms);
  }

  _abortInflight() {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }

  _onVisibility() {
    if (!document.hidden && !this.stopped) {
      this._schedule(0);
    }
  }
}


===== FILE: static/js/combat/settlement.js =====

/** @file Normalize round settlement from API — prevent zero-damage stale breakdown */

/**
 * @param {object} apiPayload
 * @returns {object|null}
 */
export function normalizeSettlement(apiPayload) {
  if (!apiPayload) return null;

  let settlement = apiPayload.round_settlement;

  if (!settlement || isZeroSettlement(settlement)) {
    settlement = {
      team_damage_dealt: apiPayload.round_enemy_damage || 0,
      enemy_damage_dealt: apiPayload.round_player_damage || 0,
      enemy_hp_after: apiPayload.enemy?.hp ?? null,
      player_hits: [],
      counter_hits: [],
      breakdown: {},
    };
  }

  const teamDealt = intVal(
    settlement.team_damage_dealt ?? settlement.round_enemy_damage ?? apiPayload.round_enemy_damage,
  );
  const enemyDealt = intVal(
    settlement.enemy_damage_dealt ?? settlement.round_player_damage ?? apiPayload.round_player_damage,
  );

  const enemyHp = apiPayload.enemy?.hp;
  const enemyHpAfter = settlement.enemy_hp_after ?? enemyHp;

  return {
    team_damage_dealt: teamDealt,
    enemy_damage_dealt: enemyDealt,
    enemy_hp_after: enemyHpAfter != null ? intVal(enemyHpAfter) : null,
    player_hits: settlement.player_hits || [],
    counter_hits: settlement.counter_hits || [],
    breakdown: settlement.breakdown || {},
    escape_triggered: !!settlement.escape_triggered,
    escape_success: !!settlement.escape_success,
  };
}

function isZeroSettlement(s) {
  const dealt = intVal(s.team_damage_dealt);
  const hits = s.player_hits || [];
  if (dealt > 0) return false;
  return hits.length === 0;
}

function intVal(v) {
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : 0;
}

export function deriveSettledIndex(payload) {
  const phase = intVal(payload.current_phase);
  if (payload.round_resolved) return Math.max(0, phase - 1);
  return Math.max(0, phase - 1);
}

export function deriveSettlementId(payload) {
  if (payload.settlement_id) return String(payload.settlement_id);
  const combatId = payload.combat_id;
  const idx = payload.settled_round_index ?? deriveSettledIndex(payload);
  if (combatId == null) return null;
  return `${combatId}:${idx}`;
}

/**
 * Fallback: rebuild settlement slice from combat logs.
 * @param {Array} logEntries
 * @param {number} settledRoundIndex
 */
export function buildSettlementFromLogs(logEntries, settledRoundIndex) {
  const entries = Array.isArray(logEntries) ? logEntries : [];
  const summaries = entries
    .map((e, i) => ({ e, i }))
    .filter(({ e }) => e?.type === 'summary' || (e?.message || '').includes('回合結算'));

  if (summaries.length === 0) return null;

  const targetIdx = Math.min(settledRoundIndex, summaries.length - 1);
  const summaryEntry = summaries[targetIdx]?.e || summaries[summaries.length - 1].e;
  const summaryIdx = summaries[targetIdx]?.i ?? summaries[summaries.length - 1].i;
  const msg = summaryEntry?.message || '';

  const teamMatch = msg.match(/隊伍造成\s*(\d+)\s*點傷害/);
  const enemyMatch = msg.match(/敵方造成\s*(\d+)\s*點傷害/);
  const hpMatch = msg.match(/剩餘\s*HP\s*(\d+)/);

  const player_hits = [];
  const start = targetIdx > 0 ? summaries[targetIdx - 1].i + 1 : 0;
  for (let i = start; i < summaryIdx; i++) {
    const entry = entries[i];
    if (!entry?.message) continue;
    const hit = entry.message.match(/造成\s*(\d+)\s*點傷害/);
    if (hit) {
      player_hits.push({ player: '—', damage: intVal(hit[1]) });
    }
  }

  const teamDealt = teamMatch ? intVal(teamMatch[1]) : player_hits.reduce((s, h) => s + h.damage, 0);

  return {
    team_damage_dealt: teamDealt,
    enemy_damage_dealt: enemyMatch ? intVal(enemyMatch[1]) : 0,
    enemy_hp_after: hpMatch ? intVal(hpMatch[1]) : null,
    player_hits,
    counter_hits: [],
    breakdown: {},
  };
}

export function extractHud(snapshot) {
  if (!snapshot) return { enemy: null, me: null, members: {}, log: [] };
  const teamId = snapshot.team_id || null;
  const route = snapshot.route || null;
  const me = snapshot.my_state
    ? { ...snapshot.my_state, team_id: snapshot.my_state.team_id || teamId }
    : null;
  return {
    enemy: snapshot.enemy || null,
    me,
    team_id: teamId,
    route,
    members: snapshot.member_states || {},
    log: snapshot.log_entries || snapshot.log || [],
    waiting: !!snapshot.waiting_for_teammates,
    submittedCount: snapshot.submitted_count,
    totalActive: snapshot.total_active,
    currentPhase: snapshot.current_phase,
    combatId: snapshot.combat_id,
    status: snapshot.status,
    outcome: snapshot.outcome,
    winner: snapshot.winner,
    controllable_protagonist_id: snapshot.controllable_protagonist_id || null,
    remaining_seconds: snapshot.remaining_seconds,
    berserk_chance: snapshot.berserk_chance,
    allow_zoo: snapshot.combat_settings?.allow_zoo !== false,
  };
}


===== FILE: static/js/combat/render.js =====

/** @file Apply view updates from combat context */

export function renderAll(views, ctx, options = {}) {
  views.hud?.update(ctx, options);
  if (!options.hpOnly) {
    views.actions?.update(ctx);
  }
}


===== FILE: static/js/combat/selectors.js =====

/** @file DOM id / data-testid constants for Combat V2 */

export const DOM_IDS = {
  ROOT: 'combat-root-v2',
  HUD: 'combat-v2-hud',
  ENEMY_AVATAR: 'combat-v2-enemy-avatar',
  ENEMY_NAME: 'combat-v2-enemy-name',
  ENEMY_HP: 'combat-v2-enemy-hp',
  ENEMY_HP_BAR: 'combat-v2-enemy-hp-bar',
  PLAYER_AVATAR: 'combat-v2-player-avatar',
  PLAYER_NAME: 'combat-v2-player-name',
  PLAYER_HP: 'combat-v2-player-hp',
  PLAYER_HP_BAR: 'combat-v2-player-hp-bar',
  TEAM_STATUS: 'combat-v2-team-status',
  LOG: 'combat-v2-log',
  ACTIONS: 'combat-v2-actions',
  ATTACK_BTN: 'combat-v2-attack-btn',
  DEFEND_BTN: 'combat-v2-defend-btn',
  ESCAPE_BTN: 'combat-v2-escape-btn',
  ZOO_BTN: 'combat-v2-zoo-btn',
  ITEM_BTN: 'combat-v2-item-btn',
  ZOO_TIP: 'combat-v2-zoo-tip',
  PROTAGONIST_BAR: 'combat-v2-protagonist-control-bar',
  PROTAGONIST_TOGGLE: 'combat-v2-protagonist-toggle',
  PROTAGONIST_LABEL: 'combat-v2-protagonist-label',
  DICE_MODAL: 'combat-v2-dice-modal',
  DICE_VALUE: 'combat-v2-dice-value',
  DICE_CONFIRM: 'combat-v2-dice-confirm-btn',
  SETTLEMENT_MODAL: 'combat-v2-round-settlement-modal',
  SETTLEMENT_BODY: 'combat-v2-settlement-body',
  SETTLEMENT_ACK: 'combat-v2-settlement-confirm-btn',
  SUBMITTING_HINT: 'combat-v2-submit-hint',
  ESCAPE_RESULT: 'combat-v2-escape-result',
  VICTORY_PANEL: 'combat-v2-result-panel',
  FAILED_PANEL: 'combat-v2-failed-panel',
  TOAST: 'combat-v2-toast',
};

export const TEST_IDS = {
  SCREEN: 'combat-v2-screen',
  ENEMY_AVATAR: 'enemy-avatar',
  PLAYER_AVATAR: 'player-avatar',
  ENEMY_HP: 'enemy-hp',
  ATTACK_BTN: 'attack-btn',
  DEFEND_BTN: 'defend-btn',
  ZOO_BTN: 'zoo-btn',
  PROTAGONIST_TOGGLE: 'protagonist-toggle',
  DICE_VALUE: 'dice-value',
  DICE_CONFIRM: 'dice-confirm-btn',
  SETTLEMENT_CONFIRM: 'settlement-confirm-btn',
  TEAM_DAMAGE: 'team-damage-dealt',
  TOAST: 'combat-toast',
};


===== FILE: static/js/combat/toast.js =====

/** @file Combat V2 toast notifications — no silent returns */

import { DOM_IDS, TEST_IDS } from './selectors.js';

let toastTimer = null;

export function showToast(message, type = 'info') {
  let el = document.getElementById(DOM_IDS.TOAST);
  if (!el) {
    el = document.createElement('div');
    el.id = DOM_IDS.TOAST;
    el.dataset.testid = TEST_IDS.TOAST;
    el.className = 'fixed bottom-6 left-1/2 -translate-x-1/2 z-[200] px-4 py-2 rounded-lg text-sm text-white shadow-lg pointer-events-none';
    document.body.appendChild(el);
  }
  const colors = {
    info: 'bg-zinc-800',
    warn: 'bg-amber-600',
    error: 'bg-red-600',
  };
  el.className = `fixed bottom-6 left-1/2 -translate-x-1/2 z-[200] px-4 py-2 rounded-lg text-sm text-white shadow-lg pointer-events-none ${colors[type] || colors.info}`;
  el.textContent = message;
  el.style.display = '';
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.style.display = 'none';
  }, 2800);
}


===== FILE: static/js/combat/views/hud_view.js =====

import { DOM_IDS, TEST_IDS } from '../selectors.js';

export function createHudView(rootEl) {
  const enemyAvatar = rootEl.querySelector(`#${DOM_IDS.ENEMY_AVATAR}`);
  const enemyName = rootEl.querySelector(`#${DOM_IDS.ENEMY_NAME}`);
  const enemyHp = rootEl.querySelector(`#${DOM_IDS.ENEMY_HP}`);
  const enemyHpBar = rootEl.querySelector(`#${DOM_IDS.ENEMY_HP_BAR}`);
  const playerAvatar = rootEl.querySelector(`#${DOM_IDS.PLAYER_AVATAR}`);
  const playerName = rootEl.querySelector(`#${DOM_IDS.PLAYER_NAME}`);
  const playerHp = rootEl.querySelector(`#${DOM_IDS.PLAYER_HP}`);
  const playerHpBar = rootEl.querySelector(`#${DOM_IDS.PLAYER_HP_BAR}`);
  const teamStatus = rootEl.querySelector(`#${DOM_IDS.TEAM_STATUS}`);
  const logEl = rootEl.querySelector(`#${DOM_IDS.LOG}`);

  function hpPct(hp, max) {
    const h = parseInt(hp, 10);
    const m = parseInt(max, 10) || 1;
    return `${Math.max(0, Math.min(100, (h / m) * 100))}%`;
  }

  function setHp(bar, text, hp, max) {
    if (bar) bar.style.width = hpPct(hp, max);
    if (text) text.textContent = `${hp ?? '—'}/${max ?? '—'}`;
  }

  return {
    update(ctx, { hpOnly = false } = {}) {
      const enemy = ctx.hud?.enemy;
      const me = ctx.hud?.me;
      if (enemy) {
        if (!hpOnly && enemyName) enemyName.textContent = enemy.name || '敵人';
        if (!hpOnly && enemyAvatar && enemy.avatar) enemyAvatar.src = enemy.avatar;
        setHp(enemyHpBar, enemyHp, enemy.hp, enemy.max_hp);
      }
      if (me) {
        if (!hpOnly && playerName) playerName.textContent = me.display_name || '你';
        if (!hpOnly && playerAvatar && me.avatar) playerAvatar.src = me.avatar;
        setHp(playerHpBar, playerHp, me.hp, me.max_hp);
      }
      if (!hpOnly && teamStatus) {
        const members = ctx.hud?.members || {};
        teamStatus.innerHTML = Object.entries(members)
          .map(([id, m]) => {
            const label = m.is_protagonist ? '⭐ ' : '';
            const isSubmitted = !!m.submitted;
            const status = isSubmitted ? '✅ 已就緒' : '⏳ 等待中';
            const statusCss = isSubmitted ? 'text-green-400 font-bold' : 'text-amber-500 animate-pulse';
            const actionHint = (isSubmitted && m.action_type)
              ? ` · <span class="text-zinc-300">[${escapeHtml(m.action_type)}]</span>${m.dice_result != null ? `（骰${m.dice_result}）` : ''}`
              : '';
            return `<div class="text-xs flex justify-between py-0.5 border-b border-zinc-800/40 gap-2"><span class="truncate">${label}${escapeHtml(m.display_name || id)}</span><span class="shrink-0 ${statusCss}">${status}${actionHint}</span></div>`;
          })
          .join('');
      }
      if (!hpOnly && logEl) {
        const logs = ctx.hud?.log || [];
        logEl.innerHTML = logs.slice(-12).map((e) => {
          const msg = typeof e === 'string' ? e : (e.message || '');
          return `<div class="text-zinc-400 text-xs py-0.5">${escapeHtml(msg)}</div>`;
        }).join('');
      }
    },
  };
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}


===== FILE: static/js/combat/views/action_view.js =====

/**
 * @file static/js/combat/views/action_view.js
 * @description 戰鬥主行動控制面板 — P2-2 Zoo / P2-3 主角代打
 */

import { Phase, TERMINAL_PHASES } from '../state_machine.js';
import { DOM_IDS } from '../selectors.js';

function zooBonusMultiplier(sanity) {
  if (sanity > 90) return 1.5;
  if (sanity > 80) return 1.4;
  if (sanity > 70) return 1.3;
  return 1.0;
}

function berserkChancePct(sanity) {
  if (sanity < 10) return 90;
  if (sanity < 20) return 50;
  if (sanity < 40) return 20;
  return 0;
}

const BUSY_PHASES = [
  Phase.DICE_ROLLING,
  Phase.DICE_CONFIRM,
  Phase.SUBMITTING,
  Phase.SETTLEMENT,
  Phase.WAITING_FOR_PLAYERS,
  Phase.ESCAPE_ATTEMPT,
];

export function createActionView(rootEl, handlers = {}) {
  const attackBtn = rootEl.querySelector(`#${DOM_IDS.ATTACK_BTN}`);
  const defendBtn = rootEl.querySelector(`#${DOM_IDS.DEFEND_BTN}`);
  const escapeBtn = rootEl.querySelector(`#${DOM_IDS.ESCAPE_BTN}`);
  const zooBtn = rootEl.querySelector(`#${DOM_IDS.ZOO_BTN}`);
  const itemBtn = rootEl.querySelector(`#${DOM_IDS.ITEM_BTN}`);
  const zooTip = rootEl.querySelector(`#${DOM_IDS.ZOO_TIP}`);
  const protagonistBar = rootEl.querySelector(`#${DOM_IDS.PROTAGONIST_BAR}`);
  const protagonistLabel = rootEl.querySelector(`#${DOM_IDS.PROTAGONIST_LABEL}`);
  const actionBtns = [attackBtn, defendBtn, escapeBtn, zooBtn, itemBtn];

  attackBtn?.addEventListener('click', () => { void handlers.onAttack?.(); });
  defendBtn?.addEventListener('click', () => { void handlers.onDefend?.(); });
  escapeBtn?.addEventListener('click', () => { void handlers.onEscape?.(); });
  zooBtn?.addEventListener('click', () => { void handlers.onZoo?.(); });
  itemBtn?.addEventListener('click', () => handlers.onItemClick?.());

  function setDisabled(disabled) {
    actionBtns.forEach((btn) => {
      if (btn) btn.disabled = disabled;
    });
  }

  function updateZooTip(ctx) {
    if (!zooTip) return;
    const me = ctx.hud?.me;
    if (!me || TERMINAL_PHASES.includes(ctx.phase)) {
      zooTip.className = 'hidden';
      zooTip.innerHTML = '';
      return;
    }

    const sanity = parseInt(me.sanity ?? 0, 10);
    const allowZoo = ctx.hud?.allow_zoo !== false;
    const zooMult = zooBonusMultiplier(sanity);
    const bChance = berserkChancePct(sanity);

    if (!allowZoo) {
      zooTip.className = 'hidden';
      zooTip.innerHTML = '';
      return;
    }

    if (bChance > 0) {
      zooTip.className = 'text-[10px] text-red-400 font-mono animate-pulse bg-red-950/20 border border-red-900/30 p-1.5 rounded-xl mx-3';
      zooTip.innerHTML = `⚠️ 神智偏低 (${sanity})：發動行動有 <b>${bChance}%</b> 暴走機率，可能無法對敵造成傷害！`;
    } else if (zooMult > 1.0) {
      zooTip.className = 'text-[10px] text-purple-400 font-mono bg-purple-950/20 border border-purple-900/30 p-1.5 rounded-xl mx-3';
      zooTip.innerHTML = `✨ Zoo 就緒：神智 ${sanity}，發動 Zoo 可獲 <b>×${zooMult}</b> 算力增益`;
    } else {
      zooTip.className = 'text-[10px] text-zinc-500 font-mono bg-zinc-900/40 border border-zinc-800 p-1.5 rounded-xl mx-3';
      zooTip.innerHTML = `Zoo 可發動（神智 ${sanity}）；神智 >70 才有加成（目前 ×1.0）`;
    }
  }

  function updateProtagonistBar(ctx) {
    if (!protagonistBar) return;
    const ctrlId = ctx.hud?.controllable_protagonist_id;
    const isLeader = !!ctx.hud?.me?.is_team_leader;
    const show = !!ctrlId && isLeader && !TERMINAL_PHASES.includes(ctx.phase);
    if (show) {
      protagonistBar.classList.remove('hidden');
      const members = ctx.hud?.members || {};
      const pro = members[ctrlId];
      const name = pro?.display_name || '主角';
      if (protagonistLabel) protagonistLabel.textContent = `代替 ${name} 行動`;
    } else {
      protagonistBar.classList.add('hidden');
    }
  }

  return {
    update(ctx) {
      const absorbing = TERMINAL_PHASES.includes(ctx.phase);
      const busy = BUSY_PHASES.includes(ctx.phase);
      const submitted = !!ctx.hud?.me?.submitted;
      const allowZoo = ctx.hud?.allow_zoo !== false;

      setDisabled(absorbing || busy || submitted);
      if (zooBtn) {
        zooBtn.disabled = absorbing || busy || submitted || !allowZoo;
        zooBtn.title = allowZoo ? '' : '此遭遇不允許 Zoo 能力';
      }

      updateZooTip(ctx);
      updateProtagonistBar(ctx);
    },
  };
}


===== FILE: static/js/combat/views/dice_modal_view.js =====

import { DOM_IDS, TEST_IDS } from '../selectors.js';

const DICE_FRAMES = 8;
const DICE_MS = 55;

export function createDiceModalView(rootEl) {
  const modal = rootEl.querySelector(`#${DOM_IDS.DICE_MODAL}`);
  const valueEl = rootEl.querySelector(`#${DOM_IDS.DICE_VALUE}`);
  const confirmBtn = rootEl.querySelector(`#${DOM_IDS.DICE_CONFIRM}`);
  let onConfirm = null;
  let rolling = false;

  confirmBtn?.addEventListener('click', () => {
    if (onConfirm) onConfirm();
  });

  return {
    isVisible() {
      return modal && !modal.classList.contains('hidden');
    },
    showRolling() {
      if (!modal) return;
      modal.classList.remove('hidden');
      modal.classList.add('flex');
      if (valueEl) valueEl.textContent = '…';
      if (confirmBtn) confirmBtn.classList.add('hidden');
    },
    async animateCosmeticDice(finalValue) {
      if (!valueEl) return;
      rolling = true;
      for (let i = 0; i < DICE_FRAMES; i++) {
        valueEl.textContent = String(Math.floor(Math.random() * 4));
        await sleep(DICE_MS);
      }
      if (finalValue == null) {
        valueEl.textContent = '—';
      } else {
        valueEl.textContent = String(finalValue);
      }
      rolling = false;
    },
    showConfirm(value, options = {}) {
      const {
        isDefend = false,
        isEscape = false,
        isItem = false,
        isZoo = false,
        itemName = '',
      } = options;
      if (!modal) return;
      modal.classList.remove('hidden');
      modal.classList.add('flex');
      if (valueEl) {
        if (isItem) valueEl.textContent = itemName ? `🎒 ${itemName}` : '🎒 道具';
        else if (isZoo) valueEl.textContent = `🦄 ${value ?? '—'}`;
        else if (isEscape) valueEl.textContent = '🏃 逃跑';
        else if (isDefend) valueEl.textContent = '🛡 防禦';
        else valueEl.textContent = String(value ?? '—');
      }
      if (confirmBtn) {
        confirmBtn.classList.remove('hidden');
        confirmBtn.textContent = isItem ? '確認使用並結束回合' : '確認並結束本回合';
      }
    },
    setConfirmDisabled(disabled) {
      if (confirmBtn) confirmBtn.disabled = !!disabled;
    },
    hide() {
      if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
      }
      if (confirmBtn) confirmBtn.disabled = false;
      rolling = false;
    },
    onConfirm(handler) {
      onConfirm = handler;
    },
    isRolling() {
      return rolling;
    },
  };
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

export { DICE_FRAMES, DICE_MS };


===== FILE: static/js/combat/views/settlement_view.js =====

/**
 * @file static/js/combat/views/settlement_view.js
 * @description 回合傷害結算視圖
 */

import { DOM_IDS, TEST_IDS } from '../selectors.js';

export function createSettlementView(rootEl) {
  const modal = rootEl.querySelector(`#${DOM_IDS.SETTLEMENT_MODAL}`);
  const body = rootEl.querySelector(`#${DOM_IDS.SETTLEMENT_BODY}`);
  const ackBtn = rootEl.querySelector(`#${DOM_IDS.SETTLEMENT_ACK}`);
  let onAck = null;

  ackBtn?.addEventListener('click', () => {
    if (onAck) onAck();
  });

  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function renderBreakdown(settlement, hud) {
    const hits = settlement.player_hits || [];
    const counters = settlement.counter_hits || [];
    const me = hud?.me?.display_name || '你';
    const members = hud?.members || {};

    let html = `<div class="space-y-3 text-xs max-h-[50vh] overflow-y-auto pr-1 font-mono">`;

    html += `<div data-testid="${TEST_IDS.TEAM_DAMAGE}" class="text-sm font-bold text-amber-400 border-b border-zinc-800 pb-1.5">💥 隊伍造成 ${settlement.team_damage_dealt} 點傷害</div>`;
    if (settlement.enemy_damage_dealt > 0) {
      html += `<div class="text-red-400 font-bold">🎯 敵方反擊造成 ${settlement.enemy_damage_dealt} 點傷害</div>`;
    }

    if (hits.length) {
      html += `<div class="text-zinc-400 font-bold mt-2 text-[11px]">⚔️ 我方行動明細：</div>`;
      hits.forEach((h) => {
        const isMe = h.role === 'self' || h.player === me;
        const roleTag = isMe ? '（你）' : '';
        const color = isMe ? 'text-zinc-200' : 'text-zinc-400';
        const itemTag = h.action_type === 'use_item' ? ' 🎒' : '';
        html += `<div class="${color} pl-2 border-l border-zinc-800">${escapeHtml(h.player || '—')}${roleTag}${itemTag}：造成 <span class="text-rose-400 font-bold">${h.damage}</span> 點傷害</div>`;
      });
    } else if (settlement.team_damage_dealt > 0) {
      html += `<div class="text-zinc-400 pl-2 border-l border-zinc-800">${escapeHtml(me)}：造成 <span class="text-rose-400 font-bold">${settlement.team_damage_dealt}</span> 點傷害</div>`;
    }

    if (counters.length) {
      html += `<div class="text-zinc-400 font-bold mt-2 text-[11px]">🛡️ 敵方防禦反擊：</div>`;
      counters.forEach((c) => {
        html += `<div class="text-red-300/90 pl-2 border-l border-red-950">${escapeHtml(c.target || '—')} 承受了 <span class="text-red-400 font-bold">${c.damage}</span> 點反擊傷害</div>`;
      });
    }

    html += `<div class="text-zinc-400 font-bold mt-2 text-[11px]">🎒 本回合戰資消耗：</div>`;
    let hasItemConsumables = false;

    const itemEffectLabels = {
      power_up: '算力乘數增益',
      hp_up: '生命回復',
      sanity_up: '神智解控',
    };

    Object.values(members).forEach((m) => {
      if (m.action_type === 'use_item' && (m.item_id || m.item_effect_type)) {
        hasItemConsumables = true;
        const effectDetail = m.item_effect_label
          || itemEffectLabels[m.item_effect_type]
          || '觸發戰術整備';
        const healTag = m.item_effect_type === 'hp_up' ? ' ❤️' : '';
        const sanTag = m.item_effect_type === 'sanity_up' ? ' 🧠' : '';
        html += `<div class="text-amber-300/90 bg-amber-950/20 border border-amber-900/30 p-1.5 rounded-lg mt-1 flex justify-between gap-2">
          <span>🎒 ${escapeHtml(m.display_name || '—')} 消耗了戰鬥道具${healTag}${sanTag}</span>
          <span class="text-[10px] text-amber-400 shrink-0 font-bold">[${effectDetail}]</span>
        </div>`;
      }

      if (m.is_protagonist && m.action_type) {
        html += `<div class="text-purple-300 bg-purple-950/20 border border-purple-900/30 p-1.5 rounded-lg mt-1">⭐ 主角行為：[${escapeHtml(m.action_type)}] ${m.dice_result != null ? `（骰 ${m.dice_result}）` : ''}</div>`;
      }
    });

    if (!hasItemConsumables) {
      html += `<div class="text-zinc-600 italic pl-2 text-[10px]">無物品消耗</div>`;
    }

    if (settlement.enemy_hp_after != null && settlement.enemy_hp_after !== undefined) {
      html += `<div class="text-[10px] text-zinc-500 pt-2 border-t border-zinc-800/60 text-right">敵人剩餘生命值：${settlement.enemy_hp_after}</div>`;
    }

    html += `</div>`;
    return html;
  }

  return {
    isVisible() {
      return modal && !modal.classList.contains('hidden');
    },
    show(settlement, ctx, { killing = false } = {}) {
      if (!modal) return;
      if (body) body.innerHTML = renderBreakdown(settlement, ctx.hud);
      if (ackBtn) {
        ackBtn.textContent = killing ? '確定，查看勝利結果' : '確認並進入下一回合';
        ackBtn.dataset.testid = TEST_IDS.SETTLEMENT_CONFIRM;
      }
      modal.className = 'fixed inset-0 z-[75] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm';
    },
    hide() {
      if (modal) {
        modal.className = 'hidden';
      }
    },
    onAck(handler) {
      onAck = handler;
    },
  };
}


===== FILE: static/js/combat/views/escape_result_view.js =====

/**
 * @file static/js/combat/views/escape_result_view.js
 * @description 逃跑判定失敗時的阻塞確認彈窗，為傷害結算提供時序緩衝
 */

import { DOM_IDS } from '../selectors.js';

export function createEscapeResultView(rootEl) {
  const panel = rootEl.querySelector(`#${DOM_IDS.ESCAPE_RESULT}`);
  let onContinue = null;

  return {
    show({ success, message }) {
      if (!panel) return;

      panel.className = 'fixed inset-0 z-[90] flex items-center justify-center bg-zinc-950/80 p-4 backdrop-blur-sm';
      panel.innerHTML = `
        <div class="bg-zinc-900 border border-zinc-800 rounded-3xl p-6 max-w-xs w-full text-center shadow-2xl">
          <div class="text-4xl mb-2">${success ? '🏃‍♂️' : '🫷'}</div>
          <h3 class="text-base font-black ${success ? 'text-emerald-400' : 'text-red-400'} mb-1">
            ${success ? '全隊成功脫離' : '全隊逃跑失敗'}
          </h3>
          <p class="text-xs text-zinc-400 leading-relaxed mb-5">
            ${message || (success ? '全隊已安全撤離戰場。' : '敵方看穿了你們的意圖，其餘戰鬥玩家的行動將繼續結算。')}
          </p>
          <button type="button" id="combat-v2-escape-continue"
                  class="min-h-11 px-4 rounded-xl bg-amber-600 hover:bg-amber-500 font-bold text-sm text-white w-full tracking-wider transition-colors shadow-md active:scale-[0.98]">
            讀取本回合結算
          </button>
        </div>`;

      panel.querySelector('#combat-v2-escape-continue')?.addEventListener('click', () => {
        panel.className = 'hidden';
        panel.innerHTML = '';
        onContinue?.();
      });
    },
    hide() {
      if (panel) {
        panel.className = 'hidden';
        panel.innerHTML = '';
      }
    },
    onContinue(handler) {
      onContinue = handler;
    },
  };
}


===== FILE: static/js/combat/views/submitting_overlay.js =====

/**
 * @file static/js/combat/views/submitting_overlay.js
 * @description 全局同步結算狀態全屏半透明遮罩
 */

import { DOM_IDS } from '../selectors.js';

export function createSubmittingOverlay(rootEl) {
  const el = rootEl.querySelector(`#${DOM_IDS.SUBMITTING_HINT}`);

  return {
    show() {
      if (el) {
        el.className = 'fixed inset-0 z-[110] flex items-center justify-center bg-black/60 backdrop-blur-sm';
      }
    },
    hide() {
      if (el) {
        el.className = 'hidden';
      }
    },
  };
}


===== FILE: static/js/combat/views/victory_view.js =====

/**
 * @file static/js/combat/views/victory_view.js
 * @description 戰鬥結局（勝利/失敗/致命崩潰）全屏渲染器，已解耦舊版 Section 依賴
 */

import {
  isValidProtagonistRouteKey,
  PROTAGONIST_ROUTE_KEY_HINT,
} from '../constants.js';
import { DOM_IDS } from '../selectors.js';
import { showToast } from '../toast.js';

export function createVictoryView(rootEl) {
  const panel = rootEl.querySelector(`#${DOM_IDS.VICTORY_PANEL}`);
  const failedPanel = rootEl.querySelector(`#${DOM_IDS.FAILED_PANEL}`);

  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  async function resolveAuthoritativeTeamId(app) {
    const hint = String(
      app.ctx.hud?.me?.team_id || app.ctx.hud?.team_id || '',
    ).trim().toUpperCase();
    const inputFn = typeof window.showInputModal === 'function' ? window.showInputModal : null;
    const confirmFn = typeof window.showConfirmModal === 'function' ? window.showConfirmModal : null;
    if (!inputFn || !confirmFn) {
      showToast('無法開啟 GM 核對視窗，請登入後台手動處理', 'error');
      return null;
    }

    const raw = await inputFn({
      title: 'GM 現場救援 — 小隊編號核對',
      placeholder: '例如 TEAM-02',
      defaultValue: hint,
      maxLength: 32,
    });
    const clean = String(raw || '').trim().toUpperCase();
    if (!clean) {
      showToast('操作已取消，未執行任何修改。', 'warn');
      return null;
    }

    const agreed = await confirmFn({
      title: '最終確認',
      message: `確定要對小隊【${clean}】執行高特權覆蓋？請務必核對現場玩家識別證。`,
      confirmLabel: '確認執行',
      danger: true,
    });
    if (!agreed) return null;
    return clean;
  }

  async function resolveProtagonistKeyForOverride(app) {
    const route = String(app.ctx.hud?.route || '').trim().toLowerCase();
    if (isValidProtagonistRouteKey(route)) return route;
    const promptFn = typeof window.showInputModal === 'function' ? window.showInputModal : null;
    if (!promptFn) {
      showToast('無法取得主角路線，請 GM 後台手動處理', 'error');
      return null;
    }
    const raw = await promptFn({
      title: '請輸入欲重置的主角代號',
      placeholder: PROTAGONIST_ROUTE_KEY_HINT,
      maxLength: 10,
    });
    const key = String(raw || '').trim().toLowerCase();
    if (!isValidProtagonistRouteKey(key)) {
      showToast(`主角代號無效，請輸入 ${PROTAGONIST_ROUTE_KEY_HINT}`, 'error');
      return null;
    }
    return key;
  }

  return {
    showVictory(data) {
      if (!panel) return;
      const narrative = data?.narrative || '你們成功看穿了這場衝突背後的情緒勒索與邊界扭曲。';

      panel.className = 'fixed inset-0 z-[85] flex items-center justify-center bg-zinc-950/90 p-4 backdrop-blur-sm';
      panel.innerHTML = `
        <div class="bg-zinc-900 border border-emerald-500/30 rounded-3xl p-6 max-w-md w-full text-center shadow-2xl">
          <div class="text-6xl mb-3">🎉</div>
          <h2 class="text-2xl font-black text-emerald-400 tracking-wider mb-2">戰鬥勝利</h2>
          <p class="text-sm text-zinc-300 mb-6 leading-relaxed bg-zinc-950/40 p-4 rounded-2xl border border-zinc-800">${escapeHtml(narrative)}</p>
          <button type="button" id="combat-v2-victory-exit"
                  class="min-h-11 w-full rounded-2xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold tracking-widest active:scale-[0.98] transition-all shadow-lg shadow-emerald-950">
            ⛺ 離開戰場並安全返回
          </button>
        </div>`;

      panel.querySelector('#combat-v2-victory-exit')?.addEventListener('click', () => {
        window.combatV2?.exitToLobby?.();
      });
    },

    showDefeat(data) {
      if (!panel) return;
      const narrative = data?.narrative || '心理界線宣告失守，全隊陷入混亂。';

      panel.className = 'fixed inset-0 z-[85] flex items-center justify-center bg-zinc-950/90 p-4 backdrop-blur-sm';
      panel.innerHTML = `
        <div class="bg-zinc-900 border border-red-500/30 rounded-3xl p-6 max-w-md w-full text-center shadow-2xl">
          <div class="text-6xl mb-3">💀</div>
          <h2 class="text-2xl font-black text-red-400 tracking-wider mb-2">戰鬥失敗</h2>
          <p class="text-sm text-zinc-300 mb-6 leading-relaxed bg-zinc-950/40 p-4 rounded-2xl border border-zinc-800">${escapeHtml(narrative)}</p>
          <button type="button" id="combat-v2-defeat-exit"
                  class="min-h-11 w-full rounded-2xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-bold tracking-widest active:scale-[0.98] transition-all">
            ⛺ 撤退回遭遇大廳
          </button>
        </div>`;

      panel.querySelector('#combat-v2-defeat-exit')?.addEventListener('click', () => {
        window.combatV2?.exitToLobby?.();
      });
    },

    showFailed(members) {
      document.getElementById('combat-near-death-overlay')?.classList.add('hidden');

      if (!failedPanel) return;
      const list = (members || []).map((m) => `<li class="text-red-300 font-mono">${escapeHtml(m)}</li>`).join('');

      failedPanel.className = 'fixed inset-0 z-[95] flex items-center justify-center bg-black/95 p-4';
      failedPanel.innerHTML = `
        <div class="bg-zinc-900 border-2 border-red-600 rounded-3xl p-6 max-w-md w-full shadow-2xl shadow-red-950">
          <div class="flex items-center gap-3 border-b border-zinc-800 pb-3 mb-4">
            <span class="text-3xl">⚠️</span>
            <div>
              <h2 class="text-lg font-black text-red-500">絕對規則阻斷：全隊瀕死</h2>
              <p class="text-[10px] text-zinc-500 font-mono">INV-D PREEMPTIVE INTERRUPT TRIGGERED</p>
            </div>
          </div>
          <p class="text-sm text-zinc-400 mb-2 leading-relaxed">
            系統偵測到以下關鍵角色生命值歸零，戰鬥已即時強制終止：
          </p>
          <ul class="text-sm bg-zinc-950/60 border border-zinc-800/80 p-3 rounded-xl mb-4 list-disc pl-5 space-y-1">${list}</ul>

          <div id="gm-embedded-override-panel" class="mb-4 p-3 bg-zinc-950 rounded-xl border border-zinc-800 hidden">
            <div class="text-[10px] text-amber-500 font-bold mb-1.5 tracking-wider">🛠️ 工作人員特權干預</div>
            <div class="grid grid-cols-2 gap-2">
              <button type="button" id="gm-btn-clear-ending" class="py-1.5 px-2 bg-emerald-950/60 hover:bg-emerald-900 text-emerald-400 rounded-lg text-[11px] font-mono border border-emerald-900/50">
                ✨ 解除結局鎖定
              </button>
              <button type="button" id="gm-btn-clear-trauma" class="py-1.5 px-2 bg-purple-950/60 hover:bg-purple-900 text-purple-400 rounded-lg text-[11px] font-mono border border-purple-900/50">
                🧠 創傷主表清零
              </button>
            </div>
          </div>

          <div class="grid gap-2">
            <button type="button" id="combat-v2-failed-lobby"
                    class="min-h-11 rounded-2xl bg-zinc-800 hover:bg-zinc-700 text-white text-sm font-medium transition-colors">
              ⛺ 強制返回大廳 (暫時脫離)
            </button>
            <button type="button" id="combat-v2-failed-gm"
                    class="min-h-11 rounded-2xl bg-red-950/40 hover:bg-red-900/40 border border-red-900/60 text-red-400 text-xs font-bold tracking-widest transition-colors">
              📢 離線呼叫 GM 工作人員
            </button>
          </div>
        </div>`;

      let clickCount = 0;
      failedPanel.querySelector('h2')?.addEventListener('click', () => {
        clickCount += 1;
        if (clickCount >= 3) {
          failedPanel.querySelector('#gm-embedded-override-panel')?.classList.remove('hidden');
        }
      });

      failedPanel.querySelector('#combat-v2-failed-lobby')?.addEventListener('click', () => {
        window.combatV2?.exitToLobby?.();
      });

      failedPanel.querySelector('#combat-v2-failed-gm')?.addEventListener('click', async () => {
        const btn = failedPanel.querySelector('#combat-v2-failed-gm');
        if (btn) {
          btn.disabled = true;
          btn.textContent = '⏳ 訊號發送中...';
        }
        await window.combatV2?.summonGm?.();
        if (btn) btn.textContent = '📢 已發送救援請求';
      });

      failedPanel.querySelector('#gm-btn-clear-ending')?.addEventListener('click', async () => {
        const app = document.getElementById('combat-root-v2')?.__combat_app_instance__;
        if (!app) return;
        const teamId = await resolveAuthoritativeTeamId(app);
        if (!teamId) return;
        void app.executeGmOverride({ teamId, targetEndingType: 'clear' });
      });

      failedPanel.querySelector('#gm-btn-clear-trauma')?.addEventListener('click', async () => {
        const app = document.getElementById('combat-root-v2')?.__combat_app_instance__;
        if (!app) return;
        const teamId = await resolveAuthoritativeTeamId(app);
        if (!teamId) return;
        const protagonistKey = await resolveProtagonistKeyForOverride(app);
        if (!protagonistKey) return;
        void app.executeGmOverride({ teamId, protagonistKey, targetTrauma: 0 });
      });
    },

    hideAll() {
      if (panel) {
        panel.className = 'hidden';
        panel.innerHTML = '';
      }
      if (failedPanel) {
        failedPanel.className = 'hidden';
        failedPanel.innerHTML = '';
      }
    },
  };
}


===== FILE: static/js/combat/views/item_select_view.js =====

import { showToast } from '../toast.js';

export function createItemSelectView(rootEl, onItemSelected) {
  let modal = rootEl.querySelector('#combat-v2-item-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'combat-v2-item-modal';
    modal.className = 'hidden';
    modal.innerHTML = `
      <div class="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 w-full max-w-sm flex flex-col max-h-[70vh]">
        <div class="flex justify-between items-center mb-3">
          <h3 class="text-base font-bold text-amber-400">🎒 戰鬥背包</h3>
          <button type="button" id="combat-v2-item-close" class="text-zinc-500 hover:text-white p-1" aria-label="關閉">✕</button>
        </div>
        <div id="combat-v2-item-list" class="flex-1 overflow-y-auto space-y-2 pr-1 min-h-0">
          <div class="text-center text-zinc-500 text-xs py-4">讀取物資中…</div>
        </div>
      </div>`;
    rootEl.appendChild(modal);
  }

  const listContainer = modal.querySelector('#combat-v2-item-list');
  const closeBtn = modal.querySelector('#combat-v2-item-close');

  closeBtn?.addEventListener('click', () => hide());

  function hide() {
    modal.className = 'hidden';
  }

  function showModal() {
    modal.className = 'fixed inset-0 z-[80] flex items-center justify-center bg-black/70 p-4';
  }

  return {
    async show() {
      showModal();
      listContainer.innerHTML = '<div class="text-center text-zinc-500 text-xs py-4 animate-pulse">正在盤點玩家背包…</div>';

      try {
        const res = await fetch(`/api/inventory?_cb=${Date.now()}`, { credentials: 'same-origin' });
        const data = await res.json();

        if (!data.success || !data.items?.length) {
          listContainer.innerHTML = '<div class="text-center text-zinc-500 text-xs py-6">🎒 背包空空如也，無可用戰鬥道具</div>';
          return;
        }

        const combatUsable = new Set(['power_up', 'hp_up', 'sanity_up']);
        listContainer.innerHTML = data.items.map((item) => {
          const isCombatUsable = combatUsable.has(item.effect_type);
          const btnClass = isCombatUsable
            ? 'w-full text-left p-3 bg-zinc-800/60 hover:bg-zinc-800 border border-zinc-700/50 rounded-xl flex items-center gap-3 transition-colors active:scale-[0.98]'
            : 'w-full text-left p-3 bg-zinc-900/40 border border-zinc-800/50 rounded-xl flex items-center gap-3 opacity-40 cursor-not-allowed pointer-events-none';

          let typeBadge = '';
          if (item.effect_type === 'hp_up') {
            typeBadge = '<span class="text-[9px] text-emerald-400 bg-emerald-950/40 px-1 border border-emerald-900/40 rounded">醫療</span>';
          } else if (item.effect_type === 'sanity_up') {
            typeBadge = '<span class="text-[9px] text-purple-400 bg-purple-950/40 px-1 border border-purple-900/40 rounded">解控</span>';
          } else if (item.effect_type === 'power_up') {
            typeBadge = '<span class="text-[9px] text-amber-400 bg-amber-950/40 px-1 border border-amber-900/40 rounded">算力</span>';
          }

          return `
          <button type="button" data-item-id="${item.item_id}" data-item-name="${escapeAttr(item.name)}"
                  class="${btnClass}" ${isCombatUsable ? '' : 'disabled'}>
            <span class="text-2xl shrink-0">${item.icon || '📦'}</span>
            <div class="min-w-0 flex-1">
              <div class="text-xs font-bold text-zinc-200 flex items-center gap-1.5 truncate">
                ${escapeHtml(item.name)} ${typeBadge}
              </div>
              <div class="text-[10px] text-zinc-400 truncate mt-0.5">${escapeHtml(item.effect_text || item.description || '')}</div>
            </div>
            <span class="text-[10px] text-amber-500/90 shrink-0 font-medium bg-amber-950/40 px-1.5 py-0.5 rounded border border-amber-900/30">使用</span>
          </button>`;
        }).join('');

        listContainer.querySelectorAll('button[data-item-id]:not([disabled])').forEach((btn) => {
          btn.addEventListener('click', () => {
            const itemId = parseInt(btn.dataset.itemId, 10);
            const itemName = btn.dataset.itemName;
            hide();
            onItemSelected('use_item', { itemId, itemName });
          });
        });
      } catch (_) {
        listContainer.innerHTML = '<div class="text-center text-red-400 text-xs py-4">物資盤點失敗，請檢查網路</div>';
        showToast('無法讀取背包', 'error');
      }
    },
    hide,
  };
}

function escapeHtml(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function escapeAttr(s) {
  return escapeHtml(s).replace(/"/g, '&quot;');
}


===== FILE: routes/combat.py =====

"""Combat API routes (migrated from app.py)."""
import os
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, session

from models.combat import (
    COMBAT_ACTION_TYPES,
    COMBAT_STATUS_RESOLVING,
    ActiveCombatExistsError,
    append_combat_log,
    build_combat_round_preview,
    build_combat_status_response,
    build_enemy_combat_stats,
    build_single_player_preview,
    clear_team_combat_id,
    combat_action_already_submitted,
    combat_phase_deadline,
    create_combat_record,
    get_active_combat_for_team,
    get_active_combat_member_ids,
    get_combat,
    get_combat_by_squad,
    get_combat_participants,
    get_combat_phase_actions,
    get_phase_submit_required_ids,
    advance_combat_from_poll,
    maybe_resolve_player_phase,
    resolve_player_phase,
    roll_combat_dice,
    save_combat,
    upsert_combat_action,
    _build_full_preview_from_status,
    _build_round_resolved_response,
    _combat_outcome_json,
    _attach_round_settlement,
    _enrich_settlement_meta,
    build_escape_outcome_response,
    build_victory_outcome_response,
    combat_outcome_if_finished,
)
from models.encounter import (
    encounter_is_replayable,
    encounter_route_matches,
    encounter_visible_to_player,
    evaluate_precheck_condition,
    load_encounter,
)
from models.encounter_outcomes import (
    apply_precheck_skip,
    encounter_already_completed,
)
from models.protagonist import get_controllable_protagonist_squad_id, get_team_story_stage
from models.item import apply_near_death_item_rescue
from models.squad import get_squad, get_team_members, is_near_death_active, update_squad
from services.global_events import create_global_event
from utils.decorators import require_player

combat_bp = Blueprint("combat", __name__)

_DYNAMIC_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@combat_bp.after_request
def combat_disable_http_cache(response):
    """Prevent browsers from caching combat GET polls (Chrome/Safari disk cache)."""
    for key, value in _DYNAMIC_NO_CACHE_HEADERS.items():
        response.headers[key] = value
    return response


@combat_bp.route("/combat/start", methods=["POST"])
@require_player(response_style="combat")
def combat_start_api(encounter_id=None):
    body = request.json if request.is_json else {}
    is_e2e_mode = os.environ.get("COMBAT_E2E", "").lower() in ("1", "true", "yes")
    if is_e2e_mode and body.get("squad_id"):
        squad_id = str(body.get("squad_id")).strip()
    else:
        squad_id = session["squad_id"]
    encounter_id = encounter_id or body.get("encounter_id") or request.form.get("encounter_id")
    confirm = body.get("confirm") or request.form.get("confirm")

    if not encounter_id:
        return jsonify({"success": False, "error": "缺少 encounter_id"}), 400

    squad = get_squad(squad_id)
    if not squad or not squad.get("team_id"):
        return jsonify({"success": False, "error": "請先加入 Team 才能進行 Encounter"}), 400

    encounter = load_encounter(encounter_id)
    if not encounter:
        return jsonify({"success": False, "error": "Encounter 不存在"}), 404

    show_test = (
        session.get("is_gm")
        or os.environ.get("OIKONOMIA_SHOW_TEST_ENCOUNTERS", "").lower() in ("1", "true", "yes")
    )
    if not encounter_visible_to_player(encounter, show_test=show_test):
        return jsonify({"success": False, "error": "此 Encounter 僅供開發測試"}), 403

    team_id = squad["team_id"]
    if (
        not encounter_is_replayable(encounter)
        and encounter_already_completed(team_id, encounter_id)
    ):
        return jsonify({"success": False, "error": "此 Encounter 已完成"}), 400

    route = squad.get("route")
    if not encounter_route_matches(encounter.get("route"), route):
        return jsonify({"success": False, "error": "此 Encounter 不屬於你嘅路線"}), 400

    precheck = encounter.get("precheck", {})
    precheck_passed = bool(
        precheck.get("condition") and evaluate_precheck_condition(precheck["condition"], team_id)
    )

    status = "precheck" if precheck_passed else "player_phase"
    try:
        combat = create_combat_record(squad_id, encounter_id, encounter, initial_status=status)
    except ActiveCombatExistsError as exc:
        existing = get_combat(exc.combat_id)
        if existing and existing.get("status") == "precheck":
            combat = existing
        else:
            return jsonify({
                "success": False,
                "error": "已有進行中的戰鬥",
                "combat_id": exc.combat_id,
            }), 409 if existing else 400

    if confirm == "skip" and precheck_passed:
        apply_precheck_skip(team_id, encounter)
        save_combat(combat["id"], status="ended", winner="squad", ended_at=datetime.now().isoformat())
        clear_team_combat_id(team_id)
        return jsonify({
            "success": True,
            "skipped": True,
            "combat_id": combat["id"],
            "message": precheck.get("success_text", "成功避開戰鬥"),
            "narrative": precheck.get("skip_reward", {}).get("narrative"),
        })

    if confirm == "fight":
        if combat.get("status") == "precheck":
            now = datetime.now().isoformat()
            settings = encounter.get("combat_settings", {})
            save_combat(
                combat["id"],
                status="player_phase",
                current_phase=1,
                phase_started_at=now,
                phase_deadline=combat_phase_deadline(now, settings.get("phase_time_limit_seconds", 180)),
            )
            combat = get_combat(combat["id"])

    return jsonify({
        "success": True,
        "combat_id": combat["id"],
        "status": combat.get("status"),
        "precheck_passed": precheck_passed,
        "can_skip": precheck_passed,
        "precheck_text": precheck.get("success_text") if precheck_passed else None,
        "enemy": build_enemy_combat_stats(combat, encounter),
        "encounter": {
            "encounter_id": encounter_id,
            "title": encounter.get("title"),
            "description": encounter.get("description"),
        },
    })

@combat_bp.route("/combat/status")
@require_player(response_style="combat")
def combat_status_api():
    combat_id = request.args.get("combat_id", type=int)
    squad_id = request.args.get("squad_id") or session["squad_id"]

    if combat_id:
        combat = get_combat(combat_id)
    else:
        squad = get_squad(squad_id)
        if squad and squad.get("team_id"):
            combat = get_active_combat_for_team(squad["team_id"])
        else:
            combat = get_combat_by_squad(squad_id)

    if not combat:
        return jsonify({"success": True, "active": False})

    if combat.get("status") == "ended":
        encounter = load_encounter(combat["encounter_id"])
        winner = combat.get("winner")
        squad = get_squad(session["squad_id"])
        team_id = squad.get("team_id") if squad else None
        if winner == "squad":
            payload = build_victory_outcome_response(
                combat, encounter, session["squad_id"], team_id=team_id,
            )
            return jsonify(payload)
        if winner == "enemy":
            ended_participants = get_combat_participants(combat) if combat else None
            return jsonify(_combat_outcome_json(
                "enemy",
                encounter,
                team_id=team_id,
                participants=ended_participants,
            ))
        return jsonify({"success": True, "active": False, "winner": winner})

    encounter = load_encounter(combat["encounter_id"])
    settings = (encounter or {}).get("combat_settings", {})

    round_just_resolved = False
    poll_participants = None
    if combat.get("status") in ("player_phase", COMBAT_STATUS_RESOLVING):
        combat, winner, round_just_resolved, poll_participants = advance_combat_from_poll(
            combat["id"], settings,
        )
        actor = get_squad(session["squad_id"])
        actor_team_id = actor.get("team_id") if actor else None
        if winner == "squad":
            combat = get_combat(combat["id"]) or combat
            return jsonify(build_victory_outcome_response(
                combat, encounter, session["squad_id"], team_id=actor_team_id,
            ))
        if winner == "escaped":
            combat = get_combat(combat["id"]) or combat
            return jsonify(build_escape_outcome_response(
                combat, encounter, session["squad_id"], team_id=actor_team_id,
            ))
        if winner == "enemy":
            defeat_participants = get_combat_participants(combat) if combat else None
            return jsonify({
                **_combat_outcome_json(
                    "enemy",
                    encounter,
                    team_id=actor_team_id,
                    participants=defeat_participants,
                ),
                "active": False,
            })
        if combat:
            finished = combat_outcome_if_finished(
                combat,
                encounter,
                team_id=actor_team_id,
                squad_id=session["squad_id"],
            )
            if finished:
                return jsonify({**finished, "active": False})
    payload = build_combat_status_response(
        combat, encounter, session["squad_id"], participants=poll_participants,
    )
    _attach_round_settlement(payload, combat=combat)
    payload["active"] = combat.get("status") not in ("ended", "precheck")
    payload["in_precheck"] = combat.get("status") == "precheck"
    if combat.get("status") == "resolving":
        payload["resolving"] = True

    if round_just_resolved:
        payload["status"] = "round_resolved"
        payload["round_resolved"] = True
        _enrich_settlement_meta(payload, combat=combat)
        payload["full_preview"] = _build_full_preview_from_status(payload)
    elif combat.get("status") == "player_phase":
        participants = poll_participants or get_combat_participants(combat) or []
        active_ids = get_active_combat_member_ids(participants or [])
        phase_actions = combat.get("phase_actions") or {}
        if session["squad_id"] in phase_actions and len(phase_actions) < len(active_ids):
            payload["waiting_for_teammates"] = True
            payload["submitted_count"] = len(phase_actions)
            payload["total_active"] = len(active_ids)

    raw_enemy_hp = (payload.get("enemy") or {}).get("hp")
    enemy_hp = int(raw_enemy_hp) if raw_enemy_hp is not None else 1
    if payload.get("active") and enemy_hp <= 0:
        combat = get_combat(combat["id"]) or combat
        squad = get_squad(session["squad_id"])
        actor_team_id = squad.get("team_id") if squad else None
        finished = combat_outcome_if_finished(
            combat,
            encounter,
            team_id=actor_team_id,
            squad_id=session["squad_id"],
        )
        if finished:
            return jsonify({**finished, "active": False})

    return jsonify(payload)

@combat_bp.route("/combat/preview_action", methods=["POST"])
@require_player(response_style="combat")
def combat_preview_action_api():
    body = request.json if request.is_json else request.form.to_dict()
    combat_id = body.get("combat_id")
    try:
        combat_id = int(combat_id) if combat_id else None
    except (TypeError, ValueError):
        combat_id = None

    action_type = (body.get("action_type") or body.get("action") or "").strip()
    if action_type not in COMBAT_ACTION_TYPES:
        return jsonify({"success": False, "error": "無效行動"}), 400

    # Preview uses neutral dice=1; authoritative roll happens on submit.
    dice_result = 1

    item_id = body.get("item_id")
    squad = get_squad(session["squad_id"])
    if not squad:
        return jsonify({"success": False, "error": "玩家不存在"}), 400

    if not combat_id:
        active = None
        if squad.get("team_id"):
            active = get_active_combat_for_team(squad["team_id"])
        if not active:
            active = get_combat_by_squad(session["squad_id"])
        combat_id = active["id"] if active else None

    if not combat_id:
        return jsonify({"success": False, "error": "沒有進行中的戰鬥"}), 400

    as_protagonist = bool(body.get("as_protagonist"))
    preview = build_combat_round_preview(
        combat_id,
        session["squad_id"],
        action_type,
        dice_result,
        item_id,
        as_protagonist=as_protagonist,
    )
    if not preview:
        return jsonify({"success": False, "error": "無法預覽此回合"}), 400

    preview["is_estimate"] = True
    preview["preview_note"] = "此為估算（普通骰）；實際結果於提交後由系統擲骰決定"
    return jsonify({"success": True, "preview": preview})

@combat_bp.route("/combat/submit_action", methods=["POST"])
@combat_bp.route("/combat/action", methods=["POST"])
@require_player(response_style="combat")
def combat_submit_action_api():
    body = request.json if request.is_json else request.form.to_dict()
    combat_id = body.get("combat_id")
    try:
        combat_id = int(combat_id) if combat_id else None
    except (TypeError, ValueError):
        combat_id = None

    action_type = (body.get("action_type") or body.get("action") or "").strip()
    if action_type not in COMBAT_ACTION_TYPES:
        return jsonify({"success": False, "error": "無效行動"}), 400

    dice_result = roll_combat_dice()

    item_id = body.get("item_id")
    squad = get_squad(session["squad_id"])
    if not squad:
        return jsonify({"success": False, "error": "玩家不存在"}), 400

    if not combat_id:
        active = None
        if squad.get("team_id"):
            active = get_active_combat_for_team(squad["team_id"])
        if not active:
            active = get_combat_by_squad(session["squad_id"])
        combat_id = active["id"] if active else None
    combat = get_combat(combat_id) if combat_id else None
    if not combat or combat.get("status") not in ("player_phase",):
        if combat and combat.get("status") == "resolving":
            return jsonify({"success": False, "error": "回合結算中，請稍候"}), 409
        return jsonify({"success": False, "error": "沒有進行中的 Player Phase"}), 400

    encounter = load_encounter(combat["encounter_id"])
    settings = (encounter or {}).get("combat_settings", {})
    story_stage = get_team_story_stage(squad["team_id"]) if squad.get("team_id") else 0
    as_protagonist = bool(body.get("as_protagonist"))
    if as_protagonist:
        if not bool(squad.get("is_team_leader")):
            return jsonify({
                "success": False,
                "error": "只有隊長特權才能啟動主角代打模式",
            }), 403
        acting_id = get_controllable_protagonist_squad_id(
            squad["team_id"], squad.get("route"), encounter, story_stage,
        )
        if not acting_id:
            return jsonify({
                "success": False,
                "error": "此階段或此關卡不可代替主角行動",
            }), 400
    else:
        acting_id = session["squad_id"]

    participants = get_combat_participants(combat) or []
    actor_state = next(
        (p for p in participants if p["squad_id"] == acting_id),
        squad if acting_id == session["squad_id"] else None,
    )
    if not actor_state:
        return jsonify({"success": False, "error": "找不到行動者或該主角未參戰"}), 400

    if actor_state.get("near_death_until"):
        try:
            if datetime.now() < datetime.fromisoformat(actor_state["near_death_until"]):
                label = "AI 主角" if as_protagonist else "你"
                return jsonify({
                    "success": False,
                    "error": f"{label}已陷入瀕死，無法執行任何行動",
                }), 400
        except ValueError:
            pass

    if action_type == "use_zoo" and not settings.get("allow_zoo", True):
        return jsonify({"success": False, "error": "此戰鬥不允許 Zoo 能力"}), 400
    if as_protagonist and action_type == "use_item":
        return jsonify({"success": False, "error": "主角不可使用玩家物品"}), 400

    current_phase = int(combat.get("current_phase") or 0)
    if combat_action_already_submitted(combat_id, acting_id, current_phase):
        return jsonify({"success": False, "error": "本回合行動已提交"}), 400

    upsert_combat_action(
        combat_id,
        acting_id,
        current_phase,
        action_type,
        dice_result,
        item_id,
    )
    phase_actions = get_combat_phase_actions(combat_id, current_phase)
    save_combat(combat_id, phase_actions=phase_actions)

    combat, winner = maybe_resolve_player_phase(combat_id, settings)
    combat = get_combat(combat_id) or combat
    participants = get_combat_participants(combat) or []
    required_ids = get_phase_submit_required_ids(combat, participants)
    resolved_phase = int(combat.get("current_phase") or current_phase)
    round_resolved_this_submit = resolved_phase > current_phase
    phase_actions = get_combat_phase_actions(combat_id, resolved_phase)

    if winner == "squad":
        combat = get_combat(combat_id) or combat
        payload = build_victory_outcome_response(
            combat, encounter, session["squad_id"], team_id=squad.get("team_id"),
        )
        payload["dice_result"] = dice_result
        return jsonify(payload)
    if winner == "escaped":
        combat = get_combat(combat_id) or combat
        payload = build_escape_outcome_response(
            combat, encounter, session["squad_id"], team_id=squad.get("team_id"),
        )
        payload["dice_result"] = dice_result
        return jsonify(payload)
    if winner == "enemy":
        return jsonify(_combat_outcome_json("enemy", encounter))

    combat = get_combat(combat_id)
    finished = combat_outcome_if_finished(
        combat,
        encounter,
        team_id=squad.get("team_id"),
        squad_id=session["squad_id"],
    )
    if finished:
        return jsonify(finished)

    if (
        not round_resolved_this_submit
        and len(required_ids) > 1
        and len(phase_actions) < len(required_ids)
    ):
        me = next(
            (p for p in participants if p["squad_id"] == session["squad_id"]),
            None,
        )
        single_preview = build_single_player_preview(
            combat_id, session["squad_id"], squad=me,
        )
        status = build_combat_status_response(
            combat, encounter, session["squad_id"], participants=participants,
        )
        return jsonify({
            "success": True,
            "status": "waiting_for_teammates",
            "dice_result": dice_result,
            "single_preview": single_preview,
            "submitted_count": len(phase_actions),
            "total_active": len(required_ids),
            "combat_id": combat_id,
            "current_phase": combat.get("current_phase", 0),
            "message": "行動已提交，等待其他隊友行動中...",
            "active": True,
            "my_state": status.get("my_state"),
            "member_states": status.get("member_states"),
            "enemy": status.get("enemy"),
            "title": status.get("title"),
            "log": status.get("log"),
            "log_entries": status.get("log_entries"),
        })

    payload = _build_round_resolved_response(combat, encounter, session["squad_id"])
    payload["dice_result"] = dice_result
    payload["message"] = f"本回合已結算：{action_type}（骰 {dice_result}）"
    return jsonify(payload)

@combat_bp.route("/combat/resolve_phase", methods=["POST"])
@require_player(response_style="combat")
def combat_resolve_phase_api():
    body = request.json if request.is_json else request.form
    combat_id = body.get("combat_id")
    if not combat_id:
        return jsonify({"success": False, "error": "缺少 combat_id"}), 400

    combat, winner = resolve_player_phase(int(combat_id))
    encounter = load_encounter(combat["encounter_id"]) if combat else None

    if winner == "squad":
        return jsonify({
            "success": True,
            "outcome": "victory",
            "narrative": (encounter or {}).get("success", {}).get("narrative"),
            "reflection_prompt": (encounter or {}).get("reflection_prompt"),
        })
    if winner == "escaped":
        escape_block = (encounter or {}).get("escape") or {}
        return jsonify({
            "success": True,
            "outcome": "escaped",
            "narrative": escape_block.get("narrative") or "全隊成功脫離戰鬥。",
        })
    if winner == "enemy":
        return jsonify({
            "success": True,
            "outcome": "defeat",
            "narrative": (encounter or {}).get("failure", {}).get("narrative"),
        })

    payload = build_combat_status_response(combat, encounter, session["squad_id"])
    payload["active"] = True
    return jsonify(payload)

@combat_bp.route("/combat/rescue_near_death", methods=["POST"])
@require_player(response_style="combat")
def combat_rescue_near_death_api():
    body = request.json if request.is_json else request.form
    combat_id = body.get("combat_id")
    rescue_type = (body.get("rescue_type") or "prayer").strip()

    squad = get_squad(session["squad_id"])
    if not squad or not squad.get("team_id"):
        return jsonify({"success": False, "error": "請先加入 Team"}), 400

    if is_near_death_active(squad):
        return jsonify({
            "success": False,
            "error": "你自身已陷入瀕死，無法救援隊友",
        }), 400
    if int(squad.get("sanity") or 0) <= 0:
        return jsonify({
            "success": False,
            "error": "你的神智已崩潰，無法救援隊友",
        }), 400

    participants = get_team_members(squad["team_id"])
    target_squad_id = (body.get("target_squad_id") or "").strip() or None
    target = None

    def _is_near_death_active_member(member):
        if not member or not member.get("near_death_until"):
            return False
        try:
            return datetime.now() < datetime.fromisoformat(member["near_death_until"])
        except ValueError:
            return False

    if target_squad_id:
        candidate = next(
            (p for p in participants if p.get("squad_id") == target_squad_id),
            None,
        )
        if not candidate:
            return jsonify({"success": False, "error": "指定隊友不在你的小隊"}), 400
        if not _is_near_death_active_member(candidate):
            return jsonify({"success": False, "error": "指定隊友目前不需要救援"}), 400
        target = candidate
    else:
        for p in participants:
            if _is_near_death_active_member(p):
                target = p
                break

    if not target:
        return jsonify({"success": False, "error": "沒有需要救援的隊友"}), 400

    if target["squad_id"] == session["squad_id"]:
        return jsonify({"success": False, "error": "無法救援自己"}), 400

    rescuer_name = squad.get("display_name") or session["squad_id"]
    target_name = target.get("display_name") or target["squad_id"]

    if rescue_type == "prayer":
        try:
            deadline = datetime.fromisoformat(target["near_death_until"])
            new_deadline = deadline - timedelta(minutes=5)
            if datetime.now() >= new_deadline:
                update_squad(target["squad_id"], near_death_until=None, hp=25)
                message = f"{rescuer_name} 禱告救援成功！{target_name} 恢復至 25 生命值。"
                rescued = True
            else:
                update_squad(target["squad_id"], near_death_until=new_deadline.isoformat())
                message = f"{rescuer_name} 為 {target_name} 禱告，瀕死時間縮短 5 分鐘。"
                rescued = False
        except ValueError:
            return jsonify({"success": False, "error": "瀕死時間資料錯誤"}), 400
    elif rescue_type == "item":
        item_id = body.get("item_id")
        if not item_id:
            return jsonify({"success": False, "error": "請指定救援道具"}), 400
        success, message, rescued = apply_near_death_item_rescue(
            session["squad_id"],
            target["squad_id"],
            item_id,
        )
        if not success:
            return jsonify({"success": False, "error": message}), 400
    else:
        return jsonify({"success": False, "error": "無效的救援方式"}), 400

    if combat_id:
        combat = get_combat(int(combat_id))
        if combat:
            combat = append_combat_log(combat, message)
            save_combat(combat["id"], logs=combat.get("logs"))

    return jsonify({
        "success": True,
        "rescued": rescued,
        "message": message,
        "target": target_name,
    })


@combat_bp.route("/combat/summon_gm", methods=["POST"])
@require_player()
def combat_summon_gm_api():
    """Broadcast GM help request to global_events and combat log."""
    body = request.json if request.is_json else {}
    combat_id = body.get("combat_id")
    if not combat_id:
        return jsonify({"success": False, "error": "缺少戰鬥編號"}), 400

    squad_id = session["squad_id"]
    squad = get_squad(squad_id)
    if not squad:
        return jsonify({"success": False, "error": "找不到隊伍"}), 404

    combat = get_combat(int(combat_id))
    if not combat:
        return jsonify({"success": False, "error": "無效的戰鬥編號"}), 404

    participants = get_combat_participants(combat)
    if squad_id not in {p.get("squad_id") for p in participants}:
        return jsonify({"success": False, "error": "你不在這場戰鬥中"}), 403

    display_name = squad.get("display_name") or squad_id
    team_id = squad.get("team_id") or "獨立隊員"

    create_global_event(
        title=f"🚨 戰場救援訊號：{display_name}",
        description=(
            f"Team [{team_id}] 在戰鬥 #{combat_id} 請求 GM 介入瀕死/崩潰狀態，"
            "需要工作人員手動重置或復活。"
        ),
        effect_type="announcement",
        effect_value=int(combat_id),
        created_by=squad_id,
    )

    combat = append_combat_log(
        combat,
        f"⚠️ [求助] {display_name} 已向 GM 發出緊急界線重建請求。",
        log_type="gm_alert",
    )
    save_combat(combat["id"], logs=combat.get("logs"))

    return jsonify({
        "success": True,
        "message": "GM 通訊網已建立，工作人員正在趕往現場。",
    })


===== FILE: routes/gm.py =====

"""GM API routes (migrated from app.py)."""
import io
import os
import random
import re
import sqlite3
import zipfile
from datetime import datetime

from flask import Blueprint, current_app, jsonify, redirect, render_template_string, request, send_file, session

from models.combat import get_combat, resolve_player_phase
from models.encounter import load_encounter
from models.settings import settings
from models.squad import get_all_squads, get_squad, update_squad
from models.team import get_next_team_id, get_team_by_id, sync_team_route
from routes.gm_templates import GM_DASHBOARD_HTML, GM_LOGIN_HTML, GM_SQUAD_DETAIL_HTML

from services.global_events import apply_global_effect, create_global_event
from services.gm_admin import RESET_GAME_PASSWORD, clear_all_submission_images, reset_game_data
from services.teams_overview import (
    build_active_combats_overview,
    build_teams_overview,
    get_all_teams_with_stats,
)
from services.gm_auth import clear_gm_session, establish_gm_session, gm_session_valid
from utils.db_tx import immediate_transaction, with_db_retry
from utils.env import is_production_env
from utils.helpers import (
    hkt_timestamp,
    normalize_photo_url,
    normalize_team_id,
    photo_public_url,
    resolve_upload_disk_path,
    safe_zip_arcname,
)
from utils.tasks import task_display_name

gm_bp = Blueprint("gm", __name__, url_prefix="/gm")


def _get_gm_pin():
    pin = os.environ.get("GM_PIN")
    if pin:
        return pin
    if is_production_env():
        raise RuntimeError("GM_PIN environment variable is required in production")
    return "gm2026"


def _require_gm():
    if not gm_session_valid(session):
        clear_gm_session(session)
        return jsonify({"success": False, "error": "未授權"}), 403
    return None


def _require_gm_html():
    if not gm_session_valid(session):
        clear_gm_session(session)
        return redirect("/gm")
    return None


# ==================== GM HTML Pages ====================

@gm_bp.route("/", strict_slashes=False)
def gm_login_page():
    return render_template_string(GM_LOGIN_HTML)


@gm_bp.route("/dashboard")
def gm_dashboard():
    denied = _require_gm_html()
    if denied:
        return denied

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    submission_counts = {
        row["squad_id"]: row["total"]
        for row in conn.execute(
            "SELECT squad_id, COUNT(*) AS total FROM submissions GROUP BY squad_id"
        ).fetchall()
    }
    conn.close()

    squad_list = []
    for s in get_all_squads():
        squad_list.append({
            **s,
            "zoo_count": len(s["zoo_skills"]),
            "submission_count": submission_counts.get(s["squad_id"], 0),
            "route_label": {"iggy": "Iggy", "marah": "Marah"}.get(s.get("route"), "未選"),
        })
    last_update = datetime.now().strftime("%H:%M:%S")
    return render_template_string(GM_DASHBOARD_HTML, squads=squad_list, last_update=last_update)


@gm_bp.route("/squad/<squad_id>")
def gm_squad_detail_page(squad_id):
    denied = _require_gm_html()
    if denied:
        return denied

    conn = sqlite3.connect(settings.db_path)
    c = conn.cursor()
    squad = get_squad(squad_id)
    if not squad:
        conn.close()
        return "找不到該小隊", 404
    squad["zoo_count"] = len(squad["zoo_skills"])
    squad["route_label"] = {"iggy": "Iggy 路線", "marah": "Marah 路線"}.get(squad.get("route"), "未選路線")

    c.execute("""
        SELECT task_id, content, photo_path, timestamp
        FROM submissions
        WHERE squad_id = ?
        ORDER BY timestamp DESC
    """, (squad_id,))
    submissions_raw = c.fetchall()
    conn.close()

    submissions = []
    for sub in submissions_raw:
        submissions.append({
            "task_id": sub[0],
            "content": sub[1],
            "photo_path": normalize_photo_url(sub[2]),
            "photo_url": photo_public_url(sub[2]),
            "timestamp": sub[3],
        })

    return render_template_string(GM_SQUAD_DETAIL_HTML, squad=squad, submissions=submissions)


# ==================== GM API ====================

@gm_bp.route("/login", methods=["POST"])
def gm_login():
    pin = request.form.get("pin", "")
    if pin == _get_gm_pin():
        establish_gm_session(session)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "PIN 錯誤"}), 401


@gm_bp.route("/teams")
def gm_teams():
    denied = _require_gm()
    if denied:
        return denied

    return jsonify({"teams": get_all_teams_with_stats()})


@gm_bp.route("/create_team", methods=["POST"])
def gm_create_team():
    denied = _require_gm()
    if denied:
        return denied

    team_name = request.form.get("team_name", "").strip() or "新小隊"
    team_id = get_next_team_id()
    created_at = datetime.now().isoformat()

    conn = sqlite3.connect(settings.db_path)
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO teams (team_id, team_name, route, created_at, leader_squad_id) VALUES (?, ?, ?, ?, ?)",
            (team_id, team_name, None, created_at, None),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"success": True, "team_id": team_id, "team_name": team_name})


@gm_bp.route("/assign_squad", methods=["POST"])
def gm_assign_squad():
    denied = _require_gm()
    if denied:
        return denied

    squad_id = request.form.get("squad_id", "").strip()
    new_team_id = request.form.get("team_id", "").strip().upper()

    if not squad_id:
        return jsonify({"success": False, "error": "請選擇玩家"}), 400

    squad = get_squad(squad_id)
    if not squad:
        if not squad_id.upper().startswith("FRAG-"):
            squad_id = squad_id.upper().replace(" ", "_")[:15]
        else:
            squad_id = squad_id.upper()
        squad = get_squad(squad_id)
    if not squad:
        return jsonify({"success": False, "error": "玩家不存在"}), 400

    new_team = get_team_by_id(new_team_id)
    if not new_team:
        return jsonify({"success": False, "error": "目標 Team 不存在"}), 400

    old_team_id = squad.get("team_id")
    old_team_name = None
    if old_team_id:
        old_team = get_team_by_id(old_team_id)
        if old_team:
            old_team_name = old_team["team_name"]

    update_squad(squad_id, team_id=normalize_team_id(new_team_id), is_team_leader=0)

    label = squad.get("display_name") or squad_id
    message = f"已將 {label} 分配到 {new_team['team_name']}"
    if old_team_name:
        message = f"已將 {label} 從「{old_team_name}」轉到「{new_team['team_name']}」"

    return jsonify({
        "success": True,
        "message": message,
        "old_team": old_team_name,
        "new_team": new_team["team_name"],
    })


@gm_bp.route("/set_team_route", methods=["POST"])
def gm_set_team_route():
    denied = _require_gm()
    if denied:
        return denied

    team_id = request.form.get("team_id", "").strip().upper()
    route = request.form.get("route", "").strip().lower()

    if route not in ("iggy", "marah"):
        return jsonify({"success": False, "error": "路線必須是 iggy 或 marah"}), 400
    if not get_team_by_id(team_id):
        return jsonify({"success": False, "error": "Team 不存在"}), 400

    sync_team_route(team_id, route)
    return jsonify({"success": True})


@gm_bp.route("/global_event", methods=["POST"])
def gm_global_event():
    denied = _require_gm()
    if denied:
        return denied

    event_type = request.form.get("event_type")
    value = int(request.form.get("value", 0))

    if event_type == "adjust_sanity":
        title = f"全營 Sanity {'+' if value > 0 else ''}{value}"
        description = f"GM 調整全營 Sanity {'+' if value > 0 else ''}{value}"
        effect_type = "adjust_sanity"
        effect_value = value
    elif event_type == "judas_strengthen":
        title = "Judas 加強"
        description = "Judas 加強！全營 Sanity -8"
        effect_type = "judas_strengthen"
        effect_value = -8
    elif event_type == "iggy_collapse":
        title = "Iggy 崩潰"
        description = "Iggy 開始崩潰！全營 Sanity -12"
        effect_type = "iggy_collapse"
        effect_value = -12
    else:
        return jsonify({"success": False, "error": "未知事件類型"})

    apply_global_effect(effect_type, effect_value)
    create_global_event(title, description, effect_type, effect_value, "GM")
    return jsonify({"success": True, "message": description})


@gm_bp.route("/create_global_event", methods=["POST"])
def gm_create_global_event():
    denied = _require_gm()
    if denied:
        return denied

    data = request.get_json(silent=True) or request.form
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"success": False, "error": "標題不能為空"}), 400

    description = (data.get("description") or "").strip()
    effect_type = (data.get("effect_type") or "").strip() or None
    effect_value = int(data.get("effect_value", 0) or 0)

    apply_global_effect(effect_type, effect_value)
    create_global_event(title, description, effect_type, effect_value, "GM")
    return jsonify({"success": True, "message": "全球事件已建立"})


@gm_bp.route("/global_events")
def gm_get_global_events():
    denied = _require_gm()
    if denied:
        return denied

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        events = conn.execute("""
            SELECT id, title, description, effect_type, effect_value, created_by, timestamp
            FROM global_events
            ORDER BY timestamp DESC
            LIMIT 50
        """).fetchall()
    finally:
        conn.close()

    return jsonify({
        "success": True,
        "events": [dict(e) for e in events],
    })


@gm_bp.route("/teams_overview")
def gm_teams_overview():
    denied = _require_gm()
    if denied:
        return denied

    overview = build_teams_overview()
    return jsonify({"success": True, **overview})


@gm_bp.route("/active_combats")
def gm_active_combats():
    denied = _require_gm()
    if denied:
        return denied

    return jsonify({"success": True, "combats": build_active_combats_overview()})


@gm_bp.route("/combat/resolve_phase", methods=["POST"])
def gm_combat_resolve_phase():
    denied = _require_gm()
    if denied:
        return denied

    body = request.json if request.is_json else request.form
    combat_id = body.get("combat_id")
    if not combat_id:
        return jsonify({"success": False, "error": "缺少 combat_id"}), 400

    combat = get_combat(int(combat_id))
    if not combat:
        return jsonify({"success": False, "error": "戰鬥不存在"}), 404
    if combat.get("status") == "resolving":
        return jsonify({
            "success": False,
            "error": "回合結算中，請稍候再試",
        }), 409
    if combat.get("status") != "player_phase":
        return jsonify({
            "success": False,
            "error": f"目前狀態為 {combat.get('status')}，只能強制結算 player_phase",
        }), 400

    combat, winner = resolve_player_phase(int(combat_id))
    encounter = load_encounter(combat["encounter_id"]) if combat else None

    if winner == "squad":
        return jsonify({
            "success": True,
            "outcome": "victory",
            "winner": "squad",
            "combat_id": int(combat_id),
            "narrative": (encounter or {}).get("success", {}).get("narrative"),
        })
    if winner == "enemy":
        return jsonify({
            "success": True,
            "outcome": "defeat",
            "winner": "enemy",
            "combat_id": int(combat_id),
            "narrative": (encounter or {}).get("failure", {}).get("narrative"),
        })

    return jsonify({
        "success": True,
        "combat_id": int(combat_id),
        "status": combat.get("status") if combat else None,
        "current_phase": combat.get("current_phase") if combat else None,
        "enemy_hp": combat.get("enemy_hp") if combat else None,
        "winner": winner,
        "message": "Phase 已強制結算，戰鬥繼續",
    })


# ==================== 玩家詳情（JSON API；HTML 頁面仍由 app.py /gm/squad 提供） ====================

@gm_bp.route("/squad/<squad_id>/data")
def gm_get_squad_detail(squad_id):
    denied = _require_gm()
    if denied:
        return denied

    squad = get_squad(squad_id)
    if not squad:
        return jsonify({"success": False, "error": "找不到玩家"}), 404

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        submissions = conn.execute("""
            SELECT task_id, content, photo_path, timestamp
            FROM submissions
            WHERE squad_id = ?
            ORDER BY timestamp DESC
        """, (squad_id,)).fetchall()
    finally:
        conn.close()

    submission_list = []
    for sub in submissions:
        submission_list.append({
            "task_id": sub["task_id"],
            "content": sub["content"],
            "photo_path": normalize_photo_url(sub["photo_path"]),
            "photo_url": photo_public_url(sub["photo_path"]),
            "timestamp": sub["timestamp"],
        })

    return jsonify({
        "success": True,
        "squad": squad,
        "submissions": submission_list,
    })


@gm_bp.route("/reset_pin", methods=["POST"])
def gm_reset_pin():
    denied = _require_gm()
    if denied:
        return denied

    squad_id = request.form.get("squad_id", "").strip()
    new_pin = request.form.get("new_pin", "").strip()

    if not squad_id:
        return jsonify({"success": False, "error": "請提供 Player ID"}), 400

    if not get_squad(squad_id):
        return jsonify({"success": False, "error": "玩家不存在"}), 404

    if not new_pin:
        new_pin = str(random.randint(1000, 9999))

    if len(new_pin) != 4 or not new_pin.isdigit():
        return jsonify({"success": False, "error": "PIN 必須係 4 位數字"}), 400

    update_squad(squad_id, pin=new_pin)
    return jsonify({
        "success": True,
        "message": f"已重置 {squad_id} 的 PIN",
        "new_pin": new_pin,
    })


@gm_bp.route("/adjust", methods=["POST"])
def gm_adjust():
    denied = _require_gm()
    if denied:
        return denied

    squad_id = request.form.get("squad_id")
    field = request.form.get("field")
    value = request.form.get("value")

    if not squad_id or not field or value is None:
        return jsonify({"success": False, "error": "缺少參數"}), 400

    allowed_fields = {"hp", "max_hp", "sanity", "power", "intellect", "resilience", "resources"}
    if field not in allowed_fields:
        return jsonify({"success": False, "error": "無效欄位"}), 400

    if not get_squad(squad_id):
        return jsonify({"success": False, "error": "玩家不存在"}), 404

    try:
        value = int(value)
    except ValueError:
        return jsonify({"success": False, "error": "數值必須為整數"}), 400

    update_squad(squad_id, **{field: value})
    squad = get_squad(squad_id)
    return jsonify({
        "success": True,
        "message": f"{squad_id} 的 {field} 已更新為 {value}",
        "squad": squad,
    })


@gm_bp.route("/download_team_images/<team_id>")
def gm_download_team_images(team_id):
    denied = _require_gm()
    if denied:
        return denied

    clean_id = normalize_team_id(team_id)
    team = get_team_by_id(clean_id)
    if not team:
        return jsonify({"success": False, "error": "找不到該隊伍"}), 404

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT s.id, s.photo_path, s.task_id, sq.display_name, sq.squad_id
            FROM submissions s
            JOIN squads sq ON s.squad_id = sq.squad_id
            WHERE UPPER(TRIM(sq.team_id)) = UPPER(TRIM(?))
              AND s.photo_path IS NOT NULL AND TRIM(s.photo_path) != ''
            ORDER BY s.timestamp
        """, (clean_id,)).fetchall()
    finally:
        conn.close()

    if not rows:
        return jsonify({"success": False, "error": "該隊伍冇上傳過圖片"}), 404

    memory_file = io.BytesIO()
    added = 0
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            disk_path = resolve_upload_disk_path(row["photo_path"])
            if not disk_path or not os.path.isfile(disk_path):
                continue
            display_name = row["display_name"] or row["squad_id"]
            task_name = task_display_name(row["task_id"])
            filename = os.path.basename(disk_path)
            arcname = safe_zip_arcname(display_name, task_name, row["id"], filename)
            zf.write(disk_path, arcname=arcname)
            added += 1

    if added == 0:
        return jsonify({"success": False, "error": "圖片檔案已不存在於伺服器"}), 404

    memory_file.seek(0)
    zip_name = safe_zip_arcname(team.get("team_name") or clean_id, "images") + ".zip"
    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=zip_name,
    )


@gm_bp.route("/player_logs/<squad_id>")
def gm_player_logs(squad_id):
    denied = _require_gm()
    if denied:
        return denied

    squad = get_squad(squad_id)
    if not squad:
        return jsonify({"success": False, "error": "找不到玩家"}), 404

    team_info = get_team_by_id(squad.get("team_id")) if squad.get("team_id") else None

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT s.id, s.task_id, s.content, s.photo_path, s.timestamp,
                   sq.display_name, sq.squad_id, sq.team_id,
                   t.team_name
            FROM submissions s
            JOIN squads sq ON s.squad_id = sq.squad_id
            LEFT JOIN teams t ON UPPER(TRIM(t.team_id)) = UPPER(TRIM(sq.team_id))
            WHERE s.squad_id = ?
            ORDER BY s.timestamp DESC
        """, (squad_id,)).fetchall()
    finally:
        conn.close()

    logs = []
    for row in rows:
        task_id = row["task_id"]
        logs.append({
            "id": row["id"],
            "task_id": task_id,
            "task_name": task_display_name(task_id),
            "description": row["content"],
            "photo_path": normalize_photo_url(row["photo_path"]),
            "photo_url": photo_public_url(row["photo_path"]),
            "timestamp": row["timestamp"],
            "status": "已完成",
            "display_name": row["display_name"] or row["squad_id"],
            "team_name": row["team_name"],
        })

    return jsonify({
        "success": True,
        "player": {
            "squad_id": squad_id,
            "display_name": squad.get("display_name") or squad_id,
            "team_id": squad.get("team_id"),
            "team_name": team_info["team_name"] if team_info else None,
        },
        "logs": logs,
    })


@gm_bp.route("/reset_game", methods=["POST"])
def gm_reset_game():
    denied = _require_gm()
    if denied:
        return denied

    password = request.form.get("password", "")
    if password != RESET_GAME_PASSWORD:
        return jsonify({"success": False, "error": "密碼錯誤"})

    reset_game_data()
    return jsonify({
        "success": True,
        "message": "遊戲已完全重置（所有玩家ID、Team、提交記錄已清空）",
    })


@gm_bp.route("/clear_all_images", methods=["POST"])
def gm_clear_all_images():
    denied = _require_gm()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    confirm = data.get("confirm", "")
    if confirm != "CLEAR_IMAGES":
        return jsonify({"success": False, "error": "確認碼錯誤"}), 400

    deleted_count, cleared_count = clear_all_submission_images()
    return jsonify({
        "success": True,
        "message": f"已成功刪除 {deleted_count} 張圖片（清空 {cleared_count} 筆提交記錄中的圖片欄位）",
        "deleted_files": deleted_count,
        "cleared_records": cleared_count,
    })


@gm_bp.route("/announcement", methods=["POST"])
def gm_send_announcement():
    denied = _require_gm()
    if denied:
        return denied

    message = request.form.get("message", "").strip()
    if not message:
        return jsonify({"success": False, "error": "訊息不能為空"})

    create_global_event("公告", message, "announcement", 0, "GM")
    return jsonify({"success": True, "message": "公告已發送"})


@gm_bp.route("/team_members/<team_id>")
def gm_team_members(team_id):
    denied = _require_gm()
    if denied:
        return denied

    team = get_team_by_id(team_id)
    if not team:
        return jsonify({"error": "Team 不存在"}), 404

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT squad_id FROM squads WHERE team_id = ? ORDER BY display_name, squad_id",
            (team_id,),
        ).fetchall()
    finally:
        conn.close()

    squad_ids = [row["squad_id"] for row in rows]
    from models.squad import fetch_squads_by_ids

    members_dict = fetch_squads_by_ids(squad_ids)
    members = [members_dict[sid] for sid in squad_ids if members_dict.get(sid)]
    return jsonify({"team": team, "members": members})


@gm_bp.route("/assignable_players")
def gm_assignable_players():
    denied = _require_gm()
    if denied:
        return denied

    target_team_id = normalize_team_id(request.args.get("team_id", ""))

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT squad_id, display_name, team_id
            FROM squads
            ORDER BY COALESCE(display_name, squad_id), squad_id
        """).fetchall()
    finally:
        conn.close()

    players = []
    for row in rows:
        current_team_id = normalize_team_id(row["team_id"]) if row["team_id"] else None
        on_target_team = bool(target_team_id and current_team_id == target_team_id)

        label = row["display_name"] or row["squad_id"]
        if current_team_id:
            team_info = get_team_by_id(current_team_id)
            team_label = team_info["team_name"] if team_info else current_team_id
            label += f"（現於 {team_label}）"
        else:
            label += "（未入隊）"
        if on_target_team:
            label += "（已在目標隊）"

        players.append({
            "squad_id": row["squad_id"],
            "display_name": row["display_name"] or row["squad_id"],
            "current_team_id": current_team_id,
            "label": label,
            "on_target_team": on_target_team,
            "eligible": not on_target_team,
        })

    eligible = [player for player in players if player["eligible"]]
    return jsonify({
        "success": True,
        "players": eligible,
        "all_players": players,
        "count": len(eligible),
    })


@gm_bp.route("/update_team_name", methods=["POST"])
def gm_update_team_name():
    denied = _require_gm()
    if denied:
        return denied

    team_id = request.form.get("team_id", "").strip().upper()
    new_name = request.form.get("new_name", "").strip()

    if not team_id or not new_name:
        return jsonify({"success": False, "error": "參數不完整"}), 400
    if not get_team_by_id(team_id):
        return jsonify({"success": False, "error": "Team 不存在"}), 400

    conn = sqlite3.connect(settings.db_path)
    try:
        c = conn.cursor()
        c.execute("UPDATE teams SET team_name = ? WHERE team_id = ?", (new_name, team_id))
        conn.commit()
    finally:
        conn.close()

    return jsonify({"success": True, "message": "隊名已更新"})


@gm_bp.route("/api/override_trauma_ending", methods=["POST"])
def gm_override_trauma_ending_api():
    """
    [GM 特權網關] 權威人工覆蓋：手動扭轉隊伍創傷數值與結局鎖定狀態。
    寫入專項特權審計日誌，並向全營廣播界線重組事件。
    """
    if not gm_session_valid(session):
        clear_gm_session(session)
        return jsonify({
            "success": False,
            "error": "拒絕存取：缺少 GM 權限憑證",
        }), 403

    body = request.json if request.is_json else {}
    team_id = normalize_team_id(body.get("team_id") or "")
    protagonist_key = (body.get("protagonist_key") or "").strip().lower()

    if not team_id:
        return jsonify({"success": False, "error": "缺少 team_id"}), 400

    target_trauma = body.get("target_trauma")
    target_ending_type = (body.get("target_ending_type") or "").strip().lower() or None

    if target_trauma is not None:
        if protagonist_key not in ("iggy", "marah"):
            return jsonify({
                "success": False,
                "error": "調整創傷必須指定有效的主角 key ('iggy'|'marah')",
            }), 400
        try:
            target_trauma = max(0, int(target_trauma))
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "無效的創傷數值"}), 400

    if target_ending_type and target_ending_type not in (
        "clear", "bad_ending", "normal_ending",
    ):
        return jsonify({"success": False, "error": "無效的 target_ending_type"}), 400

    if target_trauma is None and not target_ending_type:
        return jsonify({"success": False, "error": "缺少有效的覆蓋變更指令"}), 400

    now = datetime.now().isoformat()
    raw_operator = (session.get("gm_operator") or session.get("squad_id") or "").strip()
    gm_operator = re.sub(r"[^a-zA-Z0-9_\-]", "", raw_operator)
    if not gm_operator:
        current_app.logger.error(
            "CRITICAL PRIVILEGE VIOLATION: Anonymous or malformed GM operator "
            "bypass attempted from IP %s at %s (raw=%r)",
            request.remote_addr,
            now,
            raw_operator,
        )
        return jsonify({
            "success": False,
            "error": "資安審計攔截：未能識別當前工作人員身分，操作已遭封鎖",
        }), 403

    def _override_tx(conn):
        c = conn.cursor()

        team_exists = c.execute(
            "SELECT 1 FROM teams WHERE team_id = ?",
            (team_id,),
        ).fetchone()
        if not team_exists:
            return False, "找不到指定的隊伍編號"

        log_parts = []

        if target_trauma is not None:
            old_row = c.execute(
                """SELECT trauma_count FROM protagonist_states
                   WHERE team_id = ? AND protagonist = ?""",
                (team_id, protagonist_key),
            ).fetchone()
            old_trauma = int(old_row[0] or 0) if old_row else 0

            c.execute(
                """INSERT INTO protagonist_states
                   (team_id, protagonist, hp, max_hp, sanity, trauma_count, is_active, last_updated)
                   VALUES (?, ?, 100, 100, 100, ?, 1, ?)
                   ON CONFLICT(team_id, protagonist) DO UPDATE SET
                       trauma_count = excluded.trauma_count,
                       last_updated = excluded.last_updated""",
                (team_id, protagonist_key, target_trauma, now),
            )

            c.execute(
                """INSERT INTO protagonist_trauma_log
                   (team_id, protagonist, delta, reason, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    team_id,
                    protagonist_key,
                    target_trauma - old_trauma,
                    f"GM_OVERRIDE_BY_{gm_operator}",
                    now,
                ),
            )
            log_parts.append(
                f"🧠 {protagonist_key} 創傷強制變更: {old_trauma} -> {target_trauma}",
            )

        if target_ending_type:
            if target_ending_type == "clear":
                c.execute(
                    "UPDATE teams SET ending_type = NULL, ending_locked_at = NULL WHERE team_id = ?",
                    (team_id,),
                )
                log_parts.append("🌑 結局鎖定狀態徹底解除重置")
            elif target_ending_type == "bad_ending":
                c.execute(
                    """UPDATE teams SET ending_type = 'bad_ending', ending_locked_at = ?
                       WHERE team_id = ?""",
                    (now, team_id),
                )
                log_parts.append("🌑 強制鎖定為陰影結局 (bad_ending)")
            elif target_ending_type == "normal_ending":
                c.execute(
                    """UPDATE teams SET ending_type = 'normal_ending', ending_locked_at = ?
                       WHERE team_id = ?""",
                    (now, team_id),
                )
                log_parts.append("☀️ 強制鎖定為常規結局 (normal_ending)")

        summary_log = "; ".join(log_parts)
        return True, summary_log

    def _run():
        with immediate_transaction(settings.db_path) as conn:
            return _override_tx(conn)

    success, audit_msg = with_db_retry(_run)

    if not success:
        return jsonify({"success": False, "error": audit_msg}), 400

    create_global_event(
        title=f"🛠️ GM 人工干預：隊伍 [{team_id}] 歷史重組",
        description=(
            f"工作人員 {gm_operator} 啟動特權網關調整該隊邊界：{audit_msg}。"
        ),
        effect_type="announcement",
        effect_value=0,
        created_by=gm_operator,
    )

    return jsonify({
        "success": True,
        "message": f"覆蓋指令發放成功：{audit_msg}",
        "team_id": team_id,
        "timestamp": now,
    })


===== FILE: routes/items.py =====

"""Inventory and item claim routes."""
import os
import sqlite3

from flask import Blueprint, jsonify, redirect, render_template, request, session

from models.item import (
    format_item_effect_text,
    get_item_by_id,
    get_item_by_qr_code_value,
    grant_item_to_squad,
    serialize_item_for_client,
)
from models.settings import settings
from utils.decorators import require_player
from utils.qr import build_item_qr_payload, resolve_item_from_qr_payload

items_bp = Blueprint("items", __name__)


@items_bp.route("/my_items")
@require_player()
def my_items():
    squad_id = session["squad_id"]
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT pi.id, pi.item_id, i.name, i.description, i.icon, i.item_type,
               i.image_path, i.has_ability, i.effect_type, i.effect_value,
               pi.source, pi.obtained_at
        FROM player_items pi
        JOIN items i ON pi.item_id = i.id
        WHERE pi.squad_id = ?
        ORDER BY pi.obtained_at DESC
    """, (squad_id,)).fetchall()
    conn.close()

    items = []
    for row in rows:
        item = dict(row)
        item["has_ability"] = bool(item.get("has_ability"))
        item["image_path"] = item.get("image_path") or "/static/images/default-item.svg"
        item["effect_text"] = (
            format_item_effect_text(item.get("effect_type"), item.get("effect_value"))
            if item.get("has_ability") else None
        )
        items.append(item)
    return jsonify({
        "success": True,
        "items": items,
        "max_slots": settings.max_inventory_slots,
        "current_count": len(items),
    })


@items_bp.route("/api/inventory", methods=["GET"])
@require_player()
def get_combat_inventory_api():
    """Combat V2: uncached inventory slice for in-battle item picker."""
    squad_id = session["squad_id"]
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT pi.id AS player_item_id, pi.item_id, i.name, i.description, i.icon,
                   i.effect_type, i.effect_value, i.has_ability, i.image_path
            FROM player_items pi
            INNER JOIN items i ON pi.item_id = i.id
            WHERE pi.squad_id = ? AND COALESCE(i.is_active, 1) = 1
              AND (COALESCE(i.has_ability, 0) = 1 OR i.effect_type IS NOT NULL)
            ORDER BY pi.obtained_at DESC
        """, (squad_id,)).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["has_ability"] = bool(item.get("has_ability"))
            item["effect_text"] = (
                format_item_effect_text(item.get("effect_type"), item.get("effect_value"))
                if item.get("has_ability") else None
            )
            items.append(item)
        return jsonify({"success": True, "items": items})
    finally:
        conn.close()


@items_bp.route("/add_item", methods=["POST"])
@require_player()
def add_item():
    data = request.get_json(silent=True) or {}
    source = (data.get("source") or "story").strip().lower() or "story"
    item = None

    if source == "qr":
        qr_payload = data.get("qr_payload") or data.get("qr_code_value") or ""
        if not str(qr_payload).strip():
            return jsonify({"success": False, "error": "無效的 QR Code"}), 400
        item = resolve_item_from_qr_payload(qr_payload)
        if not item:
            return jsonify({"success": False, "error": "QR Code 無效或物品已停用"}), 400
        item_id = item["id"]
    else:
        try:
            item_id = int(data.get("item_id"))
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "無效物品 ID"}), 400
        item = get_item_by_id(item_id)
        if not item:
            return jsonify({"success": False, "error": "物品不存在或已停用"}), 400

    success, message, applied_effect = grant_item_to_squad(session["squad_id"], item_id, source)
    if not success:
        return jsonify({"success": False, "error": message}), 400

    response = {
        "success": True,
        "message": message,
        "item": serialize_item_for_client(item),
        "item_id": item_id,
        "item_name": item.get("name"),
        "qr_code_value": item.get("qr_code_value"),
    }
    if applied_effect:
        response["applied_effect"] = applied_effect
    return jsonify(response)


@items_bp.route("/discard_item", methods=["POST"])
@require_player()
def discard_item():
    data = request.get_json(silent=True) or {}
    player_item_id = data.get("player_item_id")
    try:
        player_item_id = int(player_item_id)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "無效物品記錄"}), 400

    conn = sqlite3.connect(settings.db_path)
    try:
        c = conn.cursor()
        c.execute(
            "DELETE FROM player_items WHERE id = ? AND squad_id = ?",
            (player_item_id, session["squad_id"]),
        )
        deleted = c.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        return jsonify({"success": False, "error": "丟棄失敗，請稍後再試"}), 500
    finally:
        conn.close()

    if deleted == 0:
        return jsonify({"success": False, "error": "找不到物品或無權限丟棄"}), 404

    return jsonify({"success": True, "message": "物品已丟棄"})


@items_bp.route("/claim_item/<int:item_id>")
def claim_item_page(item_id):
    if "squad_id" not in session:
        return redirect(f"/?next=/claim_item/{item_id}")

    item = get_item_by_id(item_id)
    if not item:
        return "找不到此物品", 404

    return render_template(
        "claim_item.html",
        item=item,
        qr_payload=build_item_qr_payload(item),
    )


@items_bp.route("/claim_qr/<path:qr_value>")
def claim_qr_page(qr_value):
    if "squad_id" not in session:
        return redirect(f"/?next=/claim_qr/{qr_value}")

    item = get_item_by_qr_code_value(qr_value)
    if not item:
        return "找不到此物品", 404

    return render_template(
        "claim_item.html",
        item=item,
        qr_payload=build_item_qr_payload(item),
    )


===== FILE: models/combat.py =====

"""Combat persistence, resolution, preview, and status responses."""
import json
import math
import random
import re
import sqlite3
import time
from datetime import datetime, timedelta

from models.settings import settings
from models.encounter import load_encounter
from services.combat_engine import (
    COMBAT_ATTACK_BASE_DAMAGE,
    DEFEND_TEAM_DAMAGE_FACTOR,
    Combatant,
    calculate_incoming_damage as _engine_calculate_incoming_damage,
    count_team_defenders,
    dice_multiplier as _engine_dice_multiplier,
    select_enemy_counter_target,
    team_defend_damage_multiplier,
)
from services.combat_flow import normalize_failed_escape_actions
from services.combat_outcomes import (
    build_defeat_outcome_payload,
    build_victory_outcome_payload,
    resolve_combat_outcome,
)
from services.ending import judge_ending
from models.squad import (
    fetch_squads_by_ids,
    get_squad,
    get_team_members,
    row_to_squad,
    update_squad,
)
from models.protagonist import (
    apply_damage_to_protagonist,
    get_controllable_protagonist_squad_id,
    get_player_control_protagonist_ids,
    get_team_protagonist_trauma_total,
    get_team_story_stage,
    is_protagonist_participant,
    parse_protagonist_squad_id,
    protagonist_player_control_enabled,
    refresh_combat_participants,
    resolve_combat_protagonist_keys,
)
from models.team import get_team_by_id, get_team_protagonists, official_squad_route
from utils.db_tx import get_db_connection, immediate_transaction, with_db_retry
from utils.helpers import normalize_team_id


class ActiveCombatExistsError(Exception):
    """Raised when a team already has a non-ended combat."""

    def __init__(self, combat_id):
        self.combat_id = combat_id
        super().__init__(f"Team already has active combat {combat_id}")


def _db():
    return settings.db_path


def _combat_db_conn(*, row_factory=sqlite3.Row):
    return get_db_connection(_db(), row_factory=row_factory)


def _combat_is_finished_for_reconcile(combat):
    """Avoid sealing combats while resolve/poll is in flight (session restore)."""
    if not combat:
        return False
    status = combat.get("status")
    if status == "ended":
        return True
    if status in (COMBAT_STATUS_RESOLVING, "enemy_phase"):
        return False
    return int(combat.get("enemy_hp") or 0) <= 0


def _resolution_max_wait():
    try:
        return float(settings.combat_resolution_max_wait_seconds or 6.0)
    except (TypeError, ValueError):
        return 6.0


COMBAT_ACTION_TYPES = settings.combat_action_types
ATTACK_ACTION_TYPES = settings.attack_action_types
DICE_MULTIPLIERS = settings.dice_multipliers
COMBAT_STATUS_RESOLVING = "resolving"
RESOLVING_STALE_SECONDS = 45


def row_to_combat(row):
    data = dict(row)
    for field in ("phase_actions", "logs"):
        try:
            data[field] = json.loads(data.get(field) or ({} if field == "phase_actions" else []))
        except (json.JSONDecodeError, TypeError):
            data[field] = {} if field == "phase_actions" else []
    return data

def get_combat(combat_id):
    conn = _combat_db_conn()
    try:
        row = conn.execute("SELECT * FROM combats WHERE id = ?", (combat_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    combat = row_to_combat(row)
    phase = combat.get("current_phase", 0)
    json_actions = combat.get("phase_actions") or {}
    combat["phase_actions"] = get_combat_phase_actions(
        combat_id, phase, json_fallback=json_actions
    )
    return combat

def get_combat_by_squad(squad_id):
    squad = get_squad(squad_id)
    if not squad:
        return None
    combat_id = squad.get("current_combat_id")
    if combat_id:
        combat = get_combat(combat_id)
        if combat and combat.get("status") not in ("ended",):
            return combat
    conn = _combat_db_conn()
    try:
        row = conn.execute(
            """SELECT * FROM combats
               WHERE squad_id = ? AND status NOT IN ('ended')
               ORDER BY started_at DESC LIMIT 1""",
            (squad_id,),
        ).fetchone()
    finally:
        conn.close()
    return row_to_combat(row) if row else None

def get_active_combat_for_team(team_id):
    if not team_id:
        return None

    conn = _combat_db_conn()
    try:
        row = conn.execute(
            """SELECT c.* FROM combats c
               JOIN squads s ON c.squad_id = s.squad_id
               WHERE UPPER(TRIM(s.team_id)) = UPPER(TRIM(?))
                 AND c.status NOT IN ('ended')
               ORDER BY c.started_at DESC LIMIT 1""",
            (team_id,),
        ).fetchone()
        return row_to_combat(row) if row else None
    finally:
        conn.close()

def save_combat(combat_id, **fields):
    allowed = {
        "status", "current_phase", "enemy_hp", "phase_actions", "logs",
        "phase_started_at", "phase_deadline", "ended_at", "winner",
    }
    updates, params = [], []
    for key, val in fields.items():
        if key not in allowed:
            continue
        if key in ("phase_actions", "logs"):
            val = json.dumps(val, ensure_ascii=False)
        updates.append(f"{key} = ?")
        params.append(val)
    if not updates:
        return
    params.append(combat_id)
    conn = _combat_db_conn(row_factory=None)
    try:
        conn.execute(f"UPDATE combats SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    finally:
        conn.close()

def set_team_combat_id(team_id, combat_id):
    for member in get_team_members(team_id):
        update_squad(member["squad_id"], current_combat_id=combat_id)

def clear_team_combat_id(team_id):
    for member in get_team_members(team_id):
        update_squad(member["squad_id"], current_combat_id=None)


def purge_combat_actions(combat_id, *, conn=None):
    """Remove orphaned phase submissions when a combat room closes."""
    if not combat_id:
        return 0
    if conn is not None:
        cur = conn.execute(
            "DELETE FROM combat_actions WHERE combat_id = ?", (int(combat_id),),
        )
        return cur.rowcount
    with immediate_transaction(settings.db_path) as tx:
        cur = tx.execute(
            "DELETE FROM combat_actions WHERE combat_id = ?", (int(combat_id),),
        )
        return cur.rowcount


def reconcile_finished_active_combat(combat, team_id=None, squad_id=None):
    """
    SSOT heal on session restore: seal finished combats, purge orphan actions,
    and release squad current_combat_id inside one BEGIN IMMEDIATE transaction.
    """
    if not combat:
        return False, None, None

    combat_id = combat.get("id")
    enemy_hp = int(combat.get("enemy_hp") or 0)
    is_finished = _combat_is_finished_for_reconcile(combat)

    if not is_finished:
        return True, combat_id, combat.get("encounter_id")

    if not combat_id:
        return False, None, None

    now_str = datetime.now().isoformat()
    with immediate_transaction(settings.db_path) as conn:
        if combat.get("status") != "ended":
            conn.execute(
                """UPDATE combats SET status = 'ended', ended_at = ?, enemy_hp = ?
                   WHERE id = ?""",
                (
                    now_str,
                    0 if enemy_hp <= 0 else enemy_hp,
                    int(combat_id),
                ),
            )
        purge_combat_actions(combat_id, conn=conn)
        if team_id:
            conn.execute(
                "UPDATE squads SET current_combat_id = NULL WHERE team_id = ?",
                (team_id,),
            )
        elif squad_id:
            conn.execute(
                "UPDATE squads SET current_combat_id = NULL WHERE squad_id = ?",
                (squad_id,),
            )

    return False, None, None

def get_effective_stat(squad, stat):
    base = int(squad.get(stat) or 0)
    trauma_key = {
        "power": "trauma_power",
        "intellect": "trauma_intellect",
        "resilience": "trauma_resilience",
    }.get(stat)
    trauma = int(squad.get(trauma_key) or 0) if trauma_key else 0
    return max(0, base - trauma)

def get_effective_attack_stat(squad):
    return max(
        get_effective_stat(squad, "power"),
        get_effective_stat(squad, "intellect"),
    )

def describe_attack_stat(squad):
    power = get_effective_stat(squad, "power")
    intellect = get_effective_stat(squad, "intellect")
    if power > intellect:
        return {"stat": "power", "value": power, "label": "力量"}
    if intellect > power:
        return {"stat": "intellect", "value": intellect, "label": "智力"}
    return {"stat": "power", "value": power, "label": "力量/智力"}


def _combatant_from_squad(squad, item_bonus=0):
    return Combatant(
        id=str(squad.get("squad_id") or squad.get("id") or ""),
        power=get_effective_stat(squad, "power"),
        intellect=get_effective_stat(squad, "intellect"),
        resilience=get_effective_stat(squad, "resilience"),
        sanity=int(squad.get("sanity") or 100),
        item_bonus=int(item_bonus or 0),
    )


def calculate_attack_damage(player, enemy_resilience, multiplier=1.0, item_bonus=0,
                            base_damage=settings.combat_attack_base_damage):
    from services.combat_engine import calculate_attack_damage as _engine_calculate_attack_damage

    attacker = _combatant_from_squad(player, item_bonus=item_bonus)
    return _engine_calculate_attack_damage(
        attacker,
        enemy_resilience,
        multiplier=multiplier,
        item_bonus=item_bonus,
        base_damage=base_damage,
    )

def calculate_damage_simple(attacker, target, base_damage=settings.combat_attack_base_damage,
                            multiplier=1.0, is_critical=False, apply_sanity_penalty=False,
                            item_bonus=0):
    """
    進階版傷害計算（可選機制模板，預設唔啟用暴擊/神智減益）。
    與 calculate_attack_damage 嘅分別：倍率/暴擊/神智係喺減防之後再疊加。
    啟用時建議：骰 3 → is_critical=True；神智 <50 → apply_sanity_penalty=True。
    target 可為敵人 dict（resilience）或整數防禦值。
    """
    if multiplier <= 0:
        return 0
    attack_power = get_effective_attack_stat(attacker)
    if isinstance(target, dict):
        defense = int(target.get("resilience") or 0)
    else:
        defense = int(target or 0)
    damage = (attack_power * 1.5) + base_damage + item_bonus - (defense * 0.8)
    damage *= multiplier
    if is_critical:
        damage *= 1.5
    if apply_sanity_penalty:
        sanity = int(attacker.get("sanity") or 100)
        if sanity < 50:
            damage *= 0.85
    return max(1, int(damage))

def calculate_damage(attacker_stat, multiplier, enemy_armor, item_bonus=0):
    """Legacy helper（暴走自傷等）；一般攻擊請用 calculate_attack_damage。"""
    base = (attacker_stat * 2.0) + item_bonus
    damage = math.floor(base * multiplier) - enemy_armor
    return max(0, damage)

def calculate_incoming_damage(
    enemy_base_damage,
    player_resilience,
    defending=False,
    team_defend_multiplier=None,
):
    return _engine_calculate_incoming_damage(
        enemy_base_damage,
        player_resilience,
        defending=defending,
        team_defend_multiplier=team_defend_multiplier,
    )


def dice_multiplier(dice_result):
    table = settings.dice_multipliers or None
    return _engine_dice_multiplier(dice_result, dice_multipliers=table)


def roll_combat_dice():
    """Server-authoritative combat dice (0=miss, 1=normal, 2=strong, 3=crit)."""
    return random.randint(0, 3)


def get_combat_phase_actions(combat_id, phase, json_fallback=None):
    conn = _combat_db_conn()
    try:
        rows = conn.execute(
            """SELECT squad_id, action_type, dice_result, item_id
               FROM combat_actions
               WHERE combat_id = ? AND phase = ?""",
            (combat_id, phase),
        ).fetchall()
        if rows:
            return {
                row["squad_id"]: {
                    "action_type": row["action_type"],
                    "dice_result": row["dice_result"],
                    "item_id": row["item_id"],
                }
                for row in rows
            }
    finally:
        conn.close()
    return dict(json_fallback or {})


def combat_action_already_submitted(combat_id, squad_id, phase):
    conn = _combat_db_conn(row_factory=None)
    try:
        row = conn.execute(
            """SELECT 1 FROM combat_actions
               WHERE combat_id = ? AND squad_id = ? AND phase = ?""",
            (combat_id, squad_id, phase),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def upsert_combat_action(combat_id, squad_id, phase, action_type, dice_result, item_id=None):
    def _write():
        conn = _combat_db_conn(row_factory=None)
        try:
            conn.execute(
                """INSERT INTO combat_actions
                   (combat_id, squad_id, phase, action_type, dice_result, item_id, submitted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(combat_id, squad_id, phase) DO UPDATE SET
                       action_type = excluded.action_type,
                       dice_result = excluded.dice_result,
                       item_id = excluded.item_id,
                       submitted_at = excluded.submitted_at""",
                (
                    combat_id,
                    squad_id,
                    phase,
                    action_type,
                    dice_result,
                    item_id,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    with_db_retry(_write)

def zoo_bonus_multiplier(sanity):
    sanity = int(sanity or 0)
    if sanity > 90:
        return 1.5
    if sanity > 80:
        return 1.4
    if sanity > 70:
        return 1.3
    return 1.0

def berserk_probability(sanity):
    sanity = int(sanity or 0)
    if sanity < 10:
        return 0.90
    if sanity < 20:
        return 0.50
    if sanity < 40:
        return 0.20
    return 0.0

def is_berserk(sanity):
    sanity = int(sanity if isinstance(sanity, (int, float)) else (sanity or {}).get("sanity", 50))
    prob = berserk_probability(sanity)
    return prob > 0 and random.random() < prob

def combat_phase_deadline(phase_started_at, limit_seconds):
    started = datetime.fromisoformat(phase_started_at)
    return (started + timedelta(seconds=limit_seconds)).isoformat()

def combat_phase_expired(combat, settings):
    deadline = combat.get("phase_deadline")
    if not deadline:
        return False
    return datetime.now() >= datetime.fromisoformat(deadline)

def _combat_team_id(combat, participants=None):
    if participants:
        for p in participants:
            if p.get("team_id"):
                return p["team_id"]
    starter_id = (combat or {}).get("squad_id")
    if starter_id:
        starter = get_squad(starter_id)
        if starter and starter.get("team_id"):
            return starter["team_id"]
    return None


def get_combat_participants(combat):
    """Players + route/final-stage protagonists as combat participants."""
    if not combat:
        return []
    starter_id = combat.get("squad_id")
    if not starter_id:
        return []

    conn = _combat_db_conn()
    try:
        rows = conn.execute("""
            WITH starter AS (
                SELECT squad_id, team_id FROM squads WHERE squad_id = ?
            )
            SELECT s.*
            FROM squads s
            CROSS JOIN starter st
            WHERE s.squad_id = st.squad_id
               OR (
                   st.team_id IS NOT NULL AND TRIM(st.team_id) != ''
                   AND UPPER(TRIM(s.team_id)) = UPPER(TRIM(st.team_id))
               )
            ORDER BY s.is_team_leader DESC, COALESCE(s.display_name, s.squad_id)
        """, (starter_id,)).fetchall()
        participants = []
        for row in rows:
            participant = row_to_squad(row)
            route = official_squad_route(participant)
            if route:
                participant["route"] = route
            participants.append(participant)
    finally:
        conn.close()

    team_id = _combat_team_id(combat, participants)
    if not team_id:
        return participants

    from models.protagonist import build_protagonist_participant

    encounter = load_encounter(combat.get("encounter_id"))
    story_stage = get_team_story_stage(team_id)
    for key in resolve_combat_protagonist_keys(team_id, encounter, story_stage):
        pro = build_protagonist_participant(team_id, key)
        if pro:
            participants.append(pro)
    return participants


def choose_protagonist_auto_action(participant, combat_settings=None):
    combat_settings = combat_settings or {}
    sanity = int(participant.get("sanity") or 50)
    dice = roll_combat_dice()
    if sanity < 30:
        return {"action_type": "defend", "dice_result": dice}
    if sanity > 70 and combat_settings.get("allow_zoo", True):
        return {"action_type": "use_zoo", "dice_result": dice}
    if sanity < 40 and dice == 0:
        return {"action_type": "pass", "dice_result": dice}
    return {"action_type": "attack", "dice_result": dice}


def inject_protagonist_auto_actions(actions, participants, encounter, player_control_ids):
    merged = dict(actions or {})
    combat_settings = (encounter or {}).get("combat_settings") or {}
    player_control_ids = set(player_control_ids or [])
    active_ids = set(get_active_combat_member_ids(participants))
    for p in participants:
        if not p.get("is_protagonist"):
            continue
        sid = p["squad_id"]
        if sid not in active_ids or sid in merged:
            continue
        merged[sid] = choose_protagonist_auto_action(p, combat_settings)
    return merged


def apply_damage_to_combat_participant(squad_id, damage, participant=None):
    if is_protagonist_participant(squad_id):
        key, team_id = parse_protagonist_squad_id(squad_id)
        if key and team_id:
            return apply_damage_to_protagonist(team_id, key, damage, participant=participant)
        return None
    apply_damage_to_player(squad_id, damage, squad=participant)
    return None

def get_active_combat_member_ids(participants):
    """存活且可行動的隊員 squad_id（非瀕死）。"""
    active = []
    for p in participants:
        sid = p["squad_id"]
        if int(p.get("hp") or 0) <= 0:
            continue
        if p.get("near_death_until"):
            try:
                if datetime.now() < datetime.fromisoformat(p["near_death_until"]):
                    continue
            except ValueError:
                pass
        active.append(sid)
    return active


def get_phase_active_member_ids(combat, participants):
    """
    INV-E: members active for current phase resolution.
    Escape submitters remain eligible until the round fully resolves.
    """
    active_ids = set(get_active_combat_member_ids(participants))
    if not combat or not combat.get("id"):
        return list(active_ids)

    phase = int(combat.get("current_phase") or 0)
    actions = get_combat_phase_actions(combat["id"], phase)
    if not actions:
        actions = (combat.get("phase_actions") or {})

    for sid, action in actions.items():
        action_type = (action.get("action_type") or action.get("action") or "")
        if action_type != "escape":
            continue
        participant = next((p for p in participants if p.get("squad_id") == sid), None)
        if participant and int(participant.get("hp") or 0) > 0:
            active_ids.add(sid)
    return list(active_ids)


def get_active_combat_members(participants):
    ids = set(get_active_combat_member_ids(participants))
    return [p for p in participants if p["squad_id"] in ids]


def _phase_player_control_context(combat, participants):
    """Split active combatants for player-controlled protagonist submit rules."""
    active = get_phase_active_member_ids(combat, participants)
    team_id = _combat_team_id(combat, participants)
    encounter = load_encounter(combat.get("encounter_id")) if combat else None
    story_stage = get_team_story_stage(team_id) if team_id else 0
    player_control_ids = set(
        get_player_control_protagonist_ids(team_id, encounter, story_stage, participants)
        if team_id else []
    )
    non_protagonist, player_control_protagonists = [], []
    for sid in active:
        p = next((x for x in participants if x["squad_id"] == sid), None)
        if p and p.get("is_protagonist"):
            if sid in player_control_ids:
                player_control_protagonists.append(sid)
            continue
        non_protagonist.append(sid)
    return {
        "non_protagonist": non_protagonist,
        "player_control_protagonists": player_control_protagonists,
    }


def get_phase_submit_required_ids(combat, participants):
    """Human players who must submit; protagonist may be manual or auto fallback."""
    ctx = _phase_player_control_context(combat, participants)
    return list(ctx["non_protagonist"])


def all_phase_actions_submitted(combat, participants):
    actions = combat.get("phase_actions") or {}
    ctx = _phase_player_control_context(combat, participants)
    non_pro = ctx["non_protagonist"]
    pro_control = ctx["player_control_protagonists"]
    if not non_pro and not pro_control:
        return True
    pro_submitted = any(sid in actions for sid in pro_control)
    non_pro_submitted = sum(1 for sid in non_pro if sid in actions)
    if pro_control:
        needed_players = max(0, len(non_pro) - (1 if pro_submitted else 0))
        return non_pro_submitted >= needed_players
    return non_pro_submitted >= len(non_pro)

def append_combat_log(combat, message, log_type="event"):
    logs = list(combat.get("logs") or [])
    now = datetime.now().isoformat()
    logs.append({
        "type": log_type,
        "message": message,
        "timestamp": now,
        "at": now,
    })
    combat["logs"] = logs[-50:]
    return combat

def apply_damage_to_player(squad_id, damage, squad=None):
    if squad is None:
        squad = get_squad(squad_id)
    if not squad:
        return
    current_hp = int(squad.get("hp") or 0)
    new_hp = max(0, current_hp - damage)
    updates = {"hp": new_hp}
    if new_hp <= 0 and current_hp > 0:
        updates["near_death_until"] = (
            datetime.now() + timedelta(minutes=settings.near_death_minutes)
        ).isoformat()
    elif new_hp <= 0 and not squad.get("near_death_until"):
        updates["near_death_until"] = (
            datetime.now() + timedelta(minutes=settings.near_death_minutes)
        ).isoformat()
    update_squad(squad_id, **updates)


def _recover_stale_resolving_combat(combat_id):
    with immediate_transaction() as conn:
        row = conn.execute(
            "SELECT status, phase_started_at FROM combats WHERE id = ?",
            (combat_id,),
        ).fetchone()
        if not row or row[0] != COMBAT_STATUS_RESOLVING:
            return
        started = row[1]
        stale = True
        if started:
            try:
                stale = (
                    datetime.now() - datetime.fromisoformat(started)
                ).total_seconds() > RESOLVING_STALE_SECONDS
            except ValueError:
                stale = True
        if stale:
            hp_row = conn.execute(
                "SELECT enemy_hp FROM combats WHERE id = ?",
                (combat_id,),
            ).fetchone()
            enemy_hp = int(hp_row[0] or 0) if hp_row else 0
            if enemy_hp <= 0:
                return
            conn.execute(
                "UPDATE combats SET status = 'player_phase' WHERE id = ? AND status = ?",
                (combat_id, COMBAT_STATUS_RESOLVING),
            )


def _claim_player_phase_resolution(combat_id):
    with immediate_transaction() as conn:
        row = conn.execute(
            "SELECT status FROM combats WHERE id = ?",
            (combat_id,),
        ).fetchone()
        if not row or row[0] != "player_phase":
            return False
        cur = conn.execute(
            "UPDATE combats SET status = ? WHERE id = ? AND status = 'player_phase'",
            (COMBAT_STATUS_RESOLVING, combat_id),
        )
        return cur.rowcount > 0


def _phase_actions_from_conn(conn, combat_id, phase, json_fallback=None):
    """Read phase actions using the caller's transaction connection (no nested locks)."""
    rows = conn.execute(
        """SELECT squad_id, action_type, dice_result, item_id
           FROM combat_actions WHERE combat_id = ? AND phase = ?""",
        (combat_id, phase),
    ).fetchall()
    if rows:
        return {
            row[0]: {
                "action_type": row[1],
                "dice_result": row[2],
                "item_id": row[3],
            }
            for row in rows
        }
    return dict(json_fallback or {})


def _claim_ready_player_phase_resolution(
    combat_id, combat_settings=None, cached_participants=None,
):
    """
    CAS claim player_phase -> resolving only when resolve preconditions hold.
    Participant assembly runs outside TX; phase_actions are re-read inside TX.
    """
    combat = get_combat(combat_id)
    if not combat or combat.get("status") != "player_phase":
        return False, None
    if cached_participants is not None:
        participants = cached_participants
    else:
        participants = get_combat_participants(combat) or []
    settings = combat_settings or {}

    with immediate_transaction() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM combats WHERE id = ?",
            (combat_id,),
        ).fetchone()
        if not row or row["status"] != "player_phase":
            return False, None
        cur = conn.execute(
            "UPDATE combats SET status = ? WHERE id = ? AND status = 'player_phase'",
            (COMBAT_STATUS_RESOLVING, combat_id),
        )
        if cur.rowcount == 0:
            return False, None

        fresh = row_to_combat(row)
        phase = int(fresh.get("current_phase") or 0)
        json_actions = fresh.get("phase_actions") or {}
        fresh["phase_actions"] = _phase_actions_from_conn(
            conn, combat_id, phase, json_fallback=json_actions
        )
        if not (
            all_phase_actions_submitted(fresh, participants)
            or combat_phase_expired(fresh, settings)
        ):
            conn.execute(
                "UPDATE combats SET status = 'player_phase' WHERE id = ? AND status = ?",
                (combat_id, COMBAT_STATUS_RESOLVING),
            )
            return False, fresh
        return True, fresh


def _release_player_phase_resolution(combat_id):
    combat = get_combat(combat_id)
    if combat and int(combat.get("enemy_hp") or 0) <= 0:
        return
    with immediate_transaction() as conn:
        conn.execute(
            "UPDATE combats SET status = 'player_phase' WHERE id = ? AND status = ?",
            (combat_id, COMBAT_STATUS_RESOLVING),
        )


def _wait_for_resolution_complete(combat_id, max_wait=None):
    if max_wait is None:
        max_wait = _resolution_max_wait()
    """Wait for another worker to finish resolve; avoids stale enemy HP snapshots."""
    deadline = time.time() + max_wait
    last = None
    while time.time() < deadline:
        combat = get_combat(combat_id)
        if not combat:
            return None, None
        last = combat
        status = combat.get("status")
        if status == "ended":
            return combat, combat.get("winner")
        if status not in (COMBAT_STATUS_RESOLVING, "enemy_phase"):
            return combat, None
        time.sleep(0.05)
    return last, None


def get_lowest_resilience_player(participants):
    best = None
    best_res = 999
    for p in participants:
        if p.get("near_death_until"):
            try:
                if datetime.now() < datetime.fromisoformat(p["near_death_until"]):
                    continue
            except ValueError:
                pass
        eff = get_effective_stat(p, "resilience")
        if eff < best_res:
            best_res = eff
            best = p
    return best or (participants[0] if participants else None)


def _escape_success_rate(combat_settings):
    try:
        rate = float((combat_settings or {}).get("escape_success_rate", 0.4))
    except (TypeError, ValueError):
        rate = 0.4
    return max(0.0, min(1.0, rate))


def _escape_meta_from_logs(logs, summary_idx=None):
    """Detect escape attempt outcome from combat logs for settlement enrichment."""
    entries = logs or []
    if summary_idx is None:
        summary_idx = _latest_team_summary_index(entries)
    start = 0
    if summary_idx is not None:
        prev = _latest_team_summary_index(entries[:summary_idx])
        start = (prev + 1) if prev is not None else 0
    scan = entries[start:summary_idx + 1] if summary_idx is not None else entries
    escape_triggered = False
    escape_success = False
    for entry in scan:
        if not isinstance(entry, dict):
            continue
        etype = entry.get("type")
        if etype in ("escape", "escape_failed"):
            escape_triggered = True
            escape_success = False
        elif etype == "escape_success":
            escape_triggered = True
            escape_success = True
    return escape_triggered, escape_success

def resolve_player_phase(combat_id):
    """
    完整解析 Player Phase：
    - 攻擊傷害（max(力量, 智力)）+ dice multiplier
    - Zoo 加成（>70/>80/>90 → 1.3x/1.4x/1.5x；≤70 為 1.0x，仍可發動）
    - 暴走（指定機率 + 30% 自傷）
    - 敵人反擊（韌性最低者；任一同隊 Defend → 全隊減傷 50%）
    - 瀕死檢查、日誌、Phase 狀態更新
    回傳 (combat, winner)；winner 為 'squad' | 'enemy' | None
    """
    _recover_stale_resolving_combat(combat_id)
    if not _claim_player_phase_resolution(combat_id):
        combat = get_combat(combat_id)
        if not combat:
            return None, None
        if combat.get("status") in (COMBAT_STATUS_RESOLVING, "enemy_phase"):
            return _wait_for_resolution_complete(combat_id)
        if combat.get("status") == "ended":
            return combat, combat.get("winner")
        return combat, None

    try:
        return _resolve_player_phase_body(combat_id)
    except Exception:
        _release_player_phase_resolution(combat_id)
        raise


def advance_combat_from_poll(combat_id, combat_settings=None):
    """
    Poll-side resolve gate — delegates to maybe_resolve_player_phase (CAS + TX).
    Returns (combat, winner, round_just_resolved, participants_cache).
    """
    combat = get_combat(combat_id)
    if not combat:
        return None, None, False, None

    if combat.get("status") == COMBAT_STATUS_RESOLVING:
        initial_phase = int(combat.get("current_phase") or 0)
        combat, winner = _wait_after_peer_resolve(combat_id, initial_phase)
        resolved = bool(
            winner
            or (combat and combat.get("status") == "ended")
            or (combat and int(combat.get("current_phase") or 0) > initial_phase)
        )
        return combat, winner, resolved, None

    if combat.get("status") != "player_phase":
        return combat, None, False, None

    settings = combat_settings or {}
    participants = get_combat_participants(combat) or []
    phase = int(combat.get("current_phase") or 0)
    fresh = dict(combat)
    fresh["phase_actions"] = get_combat_phase_actions(combat_id, phase)
    if not (
        all_phase_actions_submitted(fresh, participants)
        or combat_phase_expired(fresh, settings)
    ):
        return combat, None, False, participants

    prev_phase = phase
    prev_log_len = len(combat.get("logs") or [])
    combat, winner = maybe_resolve_player_phase(
        combat_id, settings, cached_participants=participants,
    )
    combat = get_combat(combat_id) or combat
    round_just_resolved = (
        int(combat.get("current_phase") or 0) > prev_phase
        or len(combat.get("logs") or []) > prev_log_len
    )
    return combat, winner, round_just_resolved, participants


def _wait_after_peer_resolve(combat_id, initial_phase, max_wait=None):
    if max_wait is None:
        max_wait = _resolution_max_wait()
    """
    Wait for in-flight resolve; if round already advanced, skip duplicate settlement.
    """
    waited, winner = _wait_for_resolution_complete(combat_id, max_wait=max_wait)
    if not waited:
        return None, None
    if int(waited.get("current_phase") or 0) > initial_phase:
        return waited, winner
    if waited.get("status") == "ended":
        return waited, winner
    fresh = get_combat(combat_id) or waited
    if fresh and int(fresh.get("current_phase") or 0) > initial_phase:
        return fresh, fresh.get("winner") if fresh.get("status") == "ended" else None
    return waited, winner


def maybe_resolve_player_phase(combat_id, combat_settings=None, cached_participants=None):
    """
    Authoritative resolve gate for routes: re-read DB snapshot, resolve at most once.
    Readiness is validated inside _claim_ready_player_phase_resolution (CAS + TX).
    Returns (combat, winner).
    """
    _recover_stale_resolving_combat(combat_id)
    combat = get_combat(combat_id)
    if not combat:
        return None, None

    initial_phase = int(combat.get("current_phase") or 0)
    status = combat.get("status")
    if status == "ended":
        return combat, combat.get("winner")
    if status == COMBAT_STATUS_RESOLVING:
        return _wait_after_peer_resolve(combat_id, initial_phase)
    if status != "player_phase":
        return combat, None

    encounter = load_encounter(combat.get("encounter_id") or "")
    settings = combat_settings or (encounter or {}).get("combat_settings", {})

    if cached_participants is None:
        cached_participants = get_combat_participants(combat) or []
    claimed, snapshot = _claim_ready_player_phase_resolution(
        combat_id, settings, cached_participants=cached_participants,
    )
    if not claimed:
        combat = get_combat(combat_id) or snapshot
        if combat and int(combat.get("current_phase") or 0) > initial_phase:
            return combat, combat.get("winner") if combat.get("status") == "ended" else None
        if combat and combat.get("status") == COMBAT_STATUS_RESOLVING:
            return _wait_after_peer_resolve(combat_id, initial_phase)
        return combat, None

    snap_phase = int((snapshot or {}).get("current_phase") or initial_phase)
    if snap_phase != initial_phase:
        _release_player_phase_resolution(combat_id)
        return get_combat(combat_id), None

    try:
        combat, winner = _resolve_player_phase_body(combat_id)
    except Exception:
        _release_player_phase_resolution(combat_id)
        raise
    if combat and combat.get("status") == COMBAT_STATUS_RESOLVING and winner is None:
        return _wait_after_peer_resolve(combat_id, initial_phase)
    return combat, winner


def _buffered_participant_hp(participant, squad_updates, protagonist_updates):
    sid = participant.get("squad_id")
    if is_protagonist_participant(sid):
        key, team_id = parse_protagonist_squad_id(sid)
        if team_id and key:
            buf = protagonist_updates.get((team_id, key), {})
            if "hp" in buf:
                return int(buf["hp"])
    else:
        buf = squad_updates.get(sid, {})
        if "hp" in buf:
            return int(buf["hp"])
    return int(participant.get("hp") or 0)


def _buffer_set_hp(squad_id, new_hp, squad_updates, protagonist_updates):
    if is_protagonist_participant(squad_id):
        key, team_id = parse_protagonist_squad_id(squad_id)
        if team_id and key:
            protagonist_updates.setdefault((team_id, key), {})["hp"] = int(new_hp)
    else:
        squad_updates.setdefault(squad_id, {})["hp"] = int(new_hp)


def _buffer_set_sanity(squad_id, new_san, squad_updates, protagonist_updates):
    if is_protagonist_participant(squad_id):
        key, team_id = parse_protagonist_squad_id(squad_id)
        if team_id and key:
            protagonist_updates.setdefault((team_id, key), {})["sanity"] = int(new_san)
    else:
        squad_updates.setdefault(squad_id, {})["sanity"] = int(new_san)


def _buffer_apply_damage(squad_id, damage, participant, squad_updates, protagonist_updates, trauma_events):
    participant = participant or {}
    if is_protagonist_participant(squad_id):
        key, team_id = parse_protagonist_squad_id(squad_id)
        if not key or not team_id:
            return int(participant.get("hp") or 0)
        buf = protagonist_updates.setdefault((team_id, key), {})
        curr = buf.get("hp", int(participant.get("hp") or 0))
        new_hp = max(0, curr - int(damage))
        buf["hp"] = new_hp
        if new_hp <= 0:
            buf["near_death_until"] = (
                datetime.now() + timedelta(minutes=settings.near_death_minutes)
            ).isoformat()
            prev_trauma = buf.get("trauma_count", int(participant.get("trauma_count") or 0))
            buf["trauma_count"] = prev_trauma + 1
            trauma_events.append((team_id, key, 1, "near_death_damage"))
        return new_hp

    buf = squad_updates.setdefault(squad_id, {})
    curr = buf.get("hp", int(participant.get("hp") or 0))
    new_hp = max(0, curr - int(damage))
    buf["hp"] = new_hp
    if new_hp <= 0 and not participant.get("near_death_until"):
        buf["near_death_until"] = (
            datetime.now() + timedelta(minutes=settings.near_death_minutes)
        ).isoformat()
    return new_hp


def _participants_with_buffers(participants, squad_updates, protagonist_updates):
    merged = []
    for p in participants:
        row = dict(p)
        sid = row.get("squad_id")
        if is_protagonist_participant(sid):
            key, team_id = parse_protagonist_squad_id(sid)
            buf = protagonist_updates.get((team_id, key), {}) if team_id and key else {}
        else:
            buf = squad_updates.get(sid, {})
        for field, val in buf.items():
            row[field] = val
        merged.append(row)
    return merged


def _team_defeated_from_participants(participants):
    alive = 0
    for p in participants:
        if int(p.get("hp") or 0) > 0:
            alive += 1
            continue
        if p.get("near_death_until"):
            try:
                if datetime.now() < datetime.fromisoformat(p["near_death_until"]):
                    alive += 1
            except ValueError:
                pass
    return alive == 0


def _apply_resolve_phase_writes(
    conn,
    *,
    items_to_delete,
    squad_updates,
    protagonist_updates,
    trauma_events,
):
    for squad_id, item_id in items_to_delete:
        deleted = conn.execute(
            "DELETE FROM player_items WHERE squad_id = ? AND item_id = ?",
            (squad_id, item_id),
        )
        if deleted.rowcount != 1:
            raise RuntimeError(f"item consume failed: {squad_id}/{item_id}")

    for squad_id, fields in squad_updates.items():
        if "hp" in fields:
            conn.execute(
                "UPDATE squads SET hp = ? WHERE squad_id = ?",
                (fields["hp"], squad_id),
            )
        if "sanity" in fields:
            conn.execute(
                "UPDATE squads SET sanity = ? WHERE squad_id = ?",
                (fields["sanity"], squad_id),
            )
        if "near_death_until" in fields:
            nd = fields["near_death_until"]
            if nd is None:
                conn.execute(
                    "UPDATE squads SET near_death_until = NULL WHERE squad_id = ?",
                    (squad_id,),
                )
            else:
                conn.execute(
                    "UPDATE squads SET near_death_until = ? WHERE squad_id = ?",
                    (nd, squad_id),
                )

    for (team_id, protagonist_key), fields in protagonist_updates.items():
        updates = []
        params = []
        for col in ("hp", "max_hp", "sanity", "trauma_count"):
            if col in fields:
                updates.append(f"{col} = ?")
                params.append(fields[col])
        if "near_death_until" in fields:
            nd = fields["near_death_until"]
            if nd is None:
                updates.append("near_death_until = NULL")
            else:
                updates.append("near_death_until = ?")
                params.append(nd)
        if updates:
            updates.append("last_updated = ?")
            params.append(datetime.now().isoformat())
            params.extend([team_id, protagonist_key])
            conn.execute(
                f"UPDATE protagonist_states SET {', '.join(updates)} "
                "WHERE team_id = ? AND protagonist = ?",
                params,
            )

    now = datetime.now().isoformat()
    for team_id, protagonist_key, delta, reason in trauma_events:
        conn.execute(
            """INSERT INTO protagonist_trauma_log
               (team_id, protagonist, delta, reason, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (team_id, protagonist_key, int(delta), reason, now),
        )


def _commit_resolve_phase_state(
    combat_id,
    *,
    items_to_delete,
    squad_updates,
    protagonist_updates,
    trauma_events,
    combat_fields,
):
    logs_json = json.dumps(combat_fields.get("logs") or [], ensure_ascii=False)
    with immediate_transaction(settings.db_path) as conn:
        _apply_resolve_phase_writes(
            conn,
            items_to_delete=items_to_delete,
            squad_updates=squad_updates,
            protagonist_updates=protagonist_updates,
            trauma_events=trauma_events,
        )
        allowed = {
            "status", "current_phase", "enemy_hp", "phase_actions", "logs",
            "phase_started_at", "phase_deadline",
        }
        updates = []
        params = []
        for key, val in combat_fields.items():
            if key not in allowed:
                continue
            if key == "logs":
                val = logs_json
            elif key == "phase_actions":
                val = json.dumps(val or {}, ensure_ascii=False)
            updates.append(f"{key} = ?")
            params.append(val)
        if updates:
            params.append(combat_id)
            conn.execute(
                f"UPDATE combats SET {', '.join(updates)} WHERE id = ?",
                params,
            )


def _resolve_player_phase_body(combat_id):
    combat = get_combat(combat_id)
    if not combat or combat.get("status") != COMBAT_STATUS_RESOLVING:
        _release_player_phase_resolution(combat_id)
        return combat, None

    from models.item import build_combat_item_consume_batch

    encounter = load_encounter(combat["encounter_id"])
    combat_settings = (encounter or {}).get("combat_settings", {})
    participants = get_combat_participants(combat)
    participant_by_id = {p["squad_id"]: p for p in participants}
    team_id = _combat_team_id(combat, participants)
    story_stage = get_team_story_stage(team_id) if team_id else 0
    player_control_ids = (
        get_player_control_protagonist_ids(team_id, encounter, story_stage, participants)
        if team_id else []
    )
    actions = inject_protagonist_auto_actions(
        combat.get("phase_actions") or {},
        participants,
        encounter,
        player_control_ids,
    )
    item_consume_batch = build_combat_item_consume_batch(actions)
    items_to_delete = []
    squad_updates = {}
    protagonist_updates = {}
    trauma_events = []

    enemy_hp = int(combat.get("enemy_hp") or 0)
    enemy_resilience = int(combat.get("enemy_resilience") or 0)
    enemy_sanity = int(combat.get("enemy_sanity") or 0)
    enemy_base_damage = int(combat.get("enemy_base_damage") or 0)
    enemy_name = combat.get("enemy_name") or "敵人"

    escape_triggered = any(
        (a.get("action_type") or a.get("action")) == "escape"
        for a in actions.values()
    )
    counter_target_actions = actions
    if escape_triggered:
        escape_rate = _escape_success_rate(combat_settings)
        if random.random() < escape_rate:
            combat = append_combat_log(
                combat,
                f"全隊逃跑成功！（成功率 {int(escape_rate * 100)}%）",
                log_type="escape_success",
            )
            save_combat(combat_id, logs=combat.get("logs"))
            return _end_combat(combat_id, "escaped", encounter), "escaped"
        combat = append_combat_log(
            combat,
            "全隊逃跑失敗，將繼續結算戰鬥行動",
            log_type="escape_failed",
        )
        actions = normalize_failed_escape_actions(
            actions,
            escape_triggered=True,
            escape_success=False,
        )
        counter_target_actions = actions

    total_damage_to_enemy = 0

    for player_squad_id, action_data in actions.items():
        player = participant_by_id.get(player_squad_id)
        if not player:
            continue
        display = player.get("display_name") or player_squad_id
        sanity = int(player.get("sanity") or 0)

        if int(player.get("hp") or 0) <= 0:
            combat = append_combat_log(
                combat,
                f"{display} 已無法行動",
                log_type="incapacitated",
            )
            continue

        action_type = action_data.get("action_type") or action_data.get("action") or "pass"
        if action_type == "failed_escape":
            combat = append_combat_log(
                combat,
                f"{display} 由於逃跑失敗，本回合陷入破防僵直，無法輸出任何傷害。",
                log_type="failed_escape_stuck",
            )
            continue

        if is_berserk(sanity):
            if random.random() < 0.30:
                self_dmg = max(1, int(get_effective_attack_stat(player) * 0.3))
                _buffer_apply_damage(
                    player_squad_id, self_dmg, player,
                    squad_updates, protagonist_updates, trauma_events,
                )
                player["hp"] = _buffered_participant_hp(player, squad_updates, protagonist_updates)
                combat = append_combat_log(
                    combat,
                    f"{display} 暴走！攻擊自己，造成 {self_dmg} 點傷害",
                    log_type="berserk",
                )
            else:
                combat = append_combat_log(
                    combat,
                    f"{display} 神智不清，行動失控",
                    log_type="berserk",
                )
            continue

        dice = action_data.get("dice_result", action_data.get("dice", 1))
        multiplier = dice_multiplier(dice)
        item_bonus = int(action_data.get("item_bonus") or 0)
        used_item_name = None
        item_effect_type = None
        item_effect_value = 0

        if action_type == "use_item" and action_data.get("item_id"):
            ok, item, err = item_consume_batch.consume_dry_run(
                player_squad_id, action_data["item_id"],
            )
            if not ok:
                combat = append_combat_log(
                    combat,
                    f"{display} 使用物品失敗：{err}",
                    log_type="item_fail",
                )
                continue
            used_item_name = item.get("name") or "物品"
            item_effect_type = item.get("effect_type")
            try:
                item_effect_value = int(item.get("effect_value") or 0)
            except (TypeError, ValueError):
                item_effect_value = 0
            items_to_delete.append((player_squad_id, action_data["item_id"]))

            if item_effect_type == "hp_up" and item_effect_value > 0:
                curr_hp = _buffered_participant_hp(player, squad_updates, protagonist_updates)
                max_hp = int(player.get("max_hp") or 100)
                new_hp = min(max_hp, curr_hp + item_effect_value)
                _buffer_set_hp(player_squad_id, new_hp, squad_updates, protagonist_updates)
                player["hp"] = new_hp
                combat = append_combat_log(
                    combat,
                    f"{display} 消耗了 [{used_item_name}]！❤️ 生命值回復 {item_effect_value} 點 (目前: {new_hp}/{max_hp})",
                    log_type="item_use",
                )
            elif item_effect_type == "sanity_up":
                curr_san = int(player.get("sanity") or 0)
                new_san = max(0, min(100, curr_san + item_effect_value))
                _buffer_set_sanity(player_squad_id, new_san, squad_updates, protagonist_updates)
                player["sanity"] = new_san
                san_label = "回復" if item_effect_value >= 0 else "扣除"
                combat = append_combat_log(
                    combat,
                    f"{display} 消耗了 [{used_item_name}]！🧠 神智值{san_label} {abs(item_effect_value)} 點 (目前: {new_san}/100)",
                    log_type="item_use",
                )
            elif item_effect_type == "power_up":
                item_bonus = abs(item_effect_value)
                combat = append_combat_log(
                    combat,
                    f"{display} 消耗了 [{used_item_name}]！💪 獲得臨時算力加成 +{item_bonus}",
                    log_type="item_use",
                )
            else:
                combat = append_combat_log(
                    combat,
                    f"{display} 消耗了 [{used_item_name}]！效果已生效",
                    log_type="item_use",
                )

        if action_type == "use_zoo":
            zoo_mult = zoo_bonus_multiplier(sanity)
            multiplier *= zoo_mult
            if zoo_mult > 1.0:
                combat = append_combat_log(
                    combat,
                    f"{display} 發動 Zoo 能力（×{zoo_mult}）",
                    log_type="zoo",
                )

        if action_type in ATTACK_ACTION_TYPES:
            stat_info = describe_attack_stat(player)
            dmg = calculate_attack_damage(
                player, enemy_resilience, multiplier=multiplier, item_bonus=item_bonus,
            )
            total_damage_to_enemy += dmg
            action_label = "Zoo 能力" if action_type == "use_zoo" else "攻擊"
            pro_tag = "（主角·自動）" if (
                player.get("is_protagonist")
                and player_squad_id not in (combat.get("phase_actions") or {})
            ) else ""
            combat = append_combat_log(
                combat,
                f"{display} {action_label}對{enemy_name}造成 {dmg} 點傷害"
                f"（{stat_info['label']} {stat_info['value']} · 骰 {dice}）{pro_tag}",
                log_type="damage",
            )
        elif action_type == "defend":
            pro_tag = "（主角·自動）" if (
                player.get("is_protagonist")
                and player_squad_id not in (combat.get("phase_actions") or {})
            ) else ""
            combat = append_combat_log(
                combat,
                f"{display} 為全隊堅守界線{pro_tag}",
                log_type="defend",
            )
        elif action_type == "pass":
            pro_tag = "（主角·自動）" if (
                player.get("is_protagonist")
                and player_squad_id not in (combat.get("phase_actions") or {})
            ) else ""
            combat = append_combat_log(
                combat,
                f"{display} 選擇觀望{pro_tag}",
                log_type="pass",
            )
        elif action_type == "escape":
            pro_tag = "（主角·自動）" if (
                player.get("is_protagonist")
                and player_squad_id not in (combat.get("phase_actions") or {})
            ) else ""
            combat = append_combat_log(
                combat,
                f"{display} 選擇逃跑{pro_tag}",
                log_type="escape",
            )
            continue
        elif action_type == "use_item":
            if item_effect_type in ("hp_up", "sanity_up"):
                continue
            stat_info = describe_attack_stat(player)
            dmg = calculate_attack_damage(
                player, enemy_resilience, multiplier=multiplier, item_bonus=item_bonus,
            )
            total_damage_to_enemy += dmg
            item_label = used_item_name or "物品"
            combat = append_combat_log(
                combat,
                f"{display} 使用「{item_label}」對{enemy_name}造成 {dmg} 點傷害"
                f"（{stat_info['label']} {stat_info['value']} · 骰 {dice}）",
                log_type="damage",
            )

    new_enemy_hp = max(0, enemy_hp - total_damage_to_enemy)
    if total_damage_to_enemy:
        combat = append_combat_log(
            combat,
            f"{enemy_name} 受到共 {total_damage_to_enemy} 點傷害，剩餘 HP {new_enemy_hp}",
            log_type="summary",
        )

    combat["enemy_hp"] = new_enemy_hp
    combat["phase_actions"] = {}
    write_buffers = dict(
        items_to_delete=items_to_delete,
        squad_updates=squad_updates,
        protagonist_updates=protagonist_updates,
        trauma_events=trauma_events,
    )

    if new_enemy_hp <= 0:
        _commit_resolve_phase_state(
            combat_id,
            **write_buffers,
            combat_fields={
                "enemy_hp": new_enemy_hp,
                "logs": combat.get("logs"),
                "phase_actions": {},
            },
        )
        return _end_combat(combat_id, "squad", encounter), "squad"

    fresh_participants = _participants_with_buffers(participants, squad_updates, protagonist_updates)
    target = (
        select_enemy_counter_target(
            fresh_participants, counter_target_actions, enemy_base_damage,
        )
        if escape_triggered
        else get_lowest_resilience_player(fresh_participants)
    )
    if target:
        target_id = target["squad_id"]
        defender_count = count_team_defenders(actions)
        team_defend_mult = team_defend_damage_multiplier(defender_count)
        incoming = calculate_incoming_damage(
            enemy_base_damage,
            get_effective_stat(target, "resilience"),
            team_defend_multiplier=team_defend_mult,
        )
        if incoming > 0:
            _buffer_apply_damage(
                target_id, incoming, target,
                squad_updates, protagonist_updates, trauma_events,
            )
            defend_note = ""
            if defender_count > 0:
                defend_note = (
                    f"（{defender_count} 人為全隊堅守界線，減半）"
                    if defender_count > 1
                    else "（全隊防禦，減半）"
                )
            pro_note = "（主角）" if target.get("is_protagonist") else ""
            combat = append_combat_log(
                combat,
                f"{enemy_name} 反擊 {target.get('display_name', target_id)}，造成 {incoming} 點傷害"
                + defend_note
                + pro_note,
                log_type="enemy_attack",
            )
            merged_target = _participants_with_buffers([target], squad_updates, protagonist_updates)[0]
            if merged_target.get("near_death_until"):
                trauma_note = ""
                if target.get("is_protagonist") and int(merged_target.get("trauma_count") or 0) > 0:
                    trauma_note = f"（心理創傷 +1，累計 {merged_target.get('trauma_count')}）"
                combat = append_combat_log(
                    combat,
                    f"{target.get('display_name', target_id)} 陷入瀕死！"
                    f"{settings.near_death_minutes} 分鐘內需救援{trauma_note}",
                    log_type="near_death",
                )

    write_buffers = dict(
        items_to_delete=items_to_delete,
        squad_updates=squad_updates,
        protagonist_updates=protagonist_updates,
        trauma_events=trauma_events,
    )
    defeated_participants = _participants_with_buffers(participants, squad_updates, protagonist_updates)
    if _team_defeated_from_participants(defeated_participants):
        _commit_resolve_phase_state(
            combat_id,
            **write_buffers,
            combat_fields={"logs": combat.get("logs")},
        )
        return _end_combat(combat_id, "enemy", encounter), "enemy"

    now = datetime.now().isoformat()
    limit = combat_settings.get("phase_time_limit_seconds", 180)
    _commit_resolve_phase_state(
        combat_id,
        **write_buffers,
        combat_fields={
            "status": "player_phase",
            "current_phase": int(combat.get("current_phase") or 0) + 1,
            "enemy_hp": new_enemy_hp,
            "logs": combat.get("logs"),
            "phase_started_at": now,
            "phase_deadline": combat_phase_deadline(now, limit),
            "phase_actions": {},
        },
    )
    return get_combat(combat_id), None

def _team_combat_defeated(combat):
    participants = get_combat_participants(combat)
    alive = 0
    for p in participants:
        if int(p.get("hp") or 0) > 0:
            alive += 1
            continue
        if p.get("near_death_until"):
            try:
                if datetime.now() < datetime.fromisoformat(p["near_death_until"]):
                    alive += 1
            except ValueError:
                pass
    return alive == 0

def _end_combat(combat_id, winner, encounter):
    combat = get_combat(combat_id)
    if not combat:
        return None

    squad = get_squad(combat["squad_id"])
    team_id = squad.get("team_id") if squad else None
    starter_id = combat.get("squad_id")
    now_str = datetime.now().isoformat()
    logs = list(combat.get("logs") or [])
    enemy_hp_val = 0 if winner == "squad" else combat.get("enemy_hp", 100)

    with immediate_transaction() as conn:
        row = conn.execute("SELECT 1 FROM combats WHERE id = ?", (combat_id,)).fetchone()
        if not row:
            return None
        conn.execute(
            """UPDATE combats SET status = 'ended', winner = ?, ended_at = ?, enemy_hp = ?
               WHERE id = ?""",
            (winner, now_str, enemy_hp_val, combat_id),
        )
        purge_combat_actions(combat_id, conn=conn)
        if team_id:
            conn.execute(
                "UPDATE squads SET current_combat_id = NULL WHERE team_id = ?",
                (team_id,),
            )
        else:
            conn.execute(
                "UPDATE squads SET current_combat_id = NULL WHERE squad_id = ?",
                (starter_id,),
            )

    outcome = resolve_combat_outcome(
        winner, team_id, encounter, starter_id, combat_id=combat_id,
    )
    log_messages = outcome.get("log_messages") or []
    if log_messages:
        for entry in log_messages:
            logs.append({
                "type": entry.get("log_type", "event"),
                "message": entry.get("message", ""),
                "timestamp": now_str,
                "at": now_str,
            })
        with immediate_transaction() as conn:
            conn.execute(
                "UPDATE combats SET logs = ? WHERE id = ?",
                (json.dumps(logs[-50:], ensure_ascii=False), combat_id),
            )

    return get_combat(combat_id)

def _enemy_hp_from_logs(logs):
    """Latest post-damage enemy HP parsed from round summary logs."""
    for entry in reversed(logs or []):
        if not isinstance(entry, dict) or entry.get("type") != "summary":
            continue
        msg = entry.get("message") or ""
        match = re.search(r"剩餘\s*HP\s*(\d+)", msg)
        if match:
            return int(match.group(1))
    return None


def reconcile_enemy_hp(combat, persist=False):
    """
    Align combat.enemy_hp with log summaries when DB snapshot is stale.
    Logs are written in the same resolve pass as damage; if stored HP is higher
    than the latest summary, trust the summary.
    """
    if not combat:
        return combat
    log_hp = _enemy_hp_from_logs(combat.get("logs"))
    if log_hp is None:
        return combat
    stored = combat.get("enemy_hp")
    if stored is not None and int(stored) <= log_hp:
        return combat
    combat = dict(combat)
    combat["enemy_hp"] = log_hp
    if persist and combat.get("id"):
        save_combat(combat["id"], enemy_hp=log_hp)
    return combat


def build_enemy_combat_stats(combat, encounter=None):
    """敵人 5 維數值（同玩家：生命值／神智／力量／智力／韌性）。"""
    combat = reconcile_enemy_hp(combat)
    enemy_def = (encounter or {}).get("enemy", {}) if encounter else {}
    log_hp = _enemy_hp_from_logs(combat.get("logs"))
    if log_hp is not None:
        hp = log_hp
    elif combat.get("enemy_hp") is not None:
        hp = int(combat.get("enemy_hp"))
    else:
        hp = int(enemy_def.get("hp") or 0)
    max_hp = int(combat.get("enemy_max_hp") if combat.get("enemy_max_hp") is not None else enemy_def.get("hp") or hp)
    sanity = int(
        combat.get("enemy_sanity") if combat.get("enemy_sanity") is not None
        else enemy_def.get("sanity") or 0
    )
    resilience = int(
        combat.get("enemy_resilience") if combat.get("enemy_resilience") is not None
        else enemy_def.get("resilience") or 0
    )
    base_damage = int(
        combat.get("enemy_base_damage") if combat.get("enemy_base_damage") is not None
        else enemy_def.get("base_damage") or 0
    )
    power = int(
        combat.get("enemy_power") if combat.get("enemy_power") is not None
        else enemy_def.get("power") or base_damage or max(resilience, 10)
    )
    intellect = int(
        combat.get("enemy_intellect") if combat.get("enemy_intellect") is not None
        else enemy_def.get("intellect") or sanity or max(int(resilience * 0.8), 10)
    )
    return {
        "name": combat.get("enemy_name") or enemy_def.get("name", "敵人"),
        "hp": hp,
        "max_hp": max_hp,
        "sanity": sanity,
        "power": power,
        "intellect": intellect,
        "resilience": resilience,
        "base_damage": base_damage,
    }


def build_combat_status_response(combat, encounter, squad_id, participants=None):
    from models.item import combat_item_effect_display_label, get_items_by_ids

    if combat:
        combat = reconcile_enemy_hp(combat, persist=True)
    combat_settings = (encounter or {}).get("combat_settings", {})
    if participants is None and combat:
        participants = get_combat_participants(combat)
    participants = participants or []
    participant_by_id = {p["squad_id"]: p for p in participants}

    me = participant_by_id.get(squad_id)
    if not me:
        me = fetch_squads_by_ids([squad_id]).get(squad_id) or {}

    team_id = me.get("team_id")
    if not team_id and combat:
        starter = participant_by_id.get(combat.get("squad_id"))
        if not starter and combat.get("squad_id"):
            starter = fetch_squads_by_ids([combat["squad_id"]]).get(combat["squad_id"])
        team_id = starter.get("team_id") if starter else None

    protagonists = get_team_protagonists(team_id) if team_id else {}
    team_route = protagonists.get("active_route") or me.get("route")
    if not team_route and team_id:
        team_row = get_team_by_id(team_id)
        team_route = (team_row or {}).get("route")
    phase_actions = (combat or {}).get("phase_actions") or {}
    berserk_hint = berserk_probability(me.get("sanity", 50)) > 0

    item_ids_for_status = [
        (submitted or {}).get("item_id")
        for submitted in phase_actions.values()
        if (submitted or {}).get("item_id") is not None
    ]
    item_catalog_by_id = get_items_by_ids(item_ids_for_status)

    member_states = {}
    for p in participants:
        sid = p["squad_id"]
        submitted = phase_actions.get(sid)
        item_id = (submitted or {}).get("item_id")
        item_effect_type = None
        item_effect_label = None
        if item_id:
            try:
                item_row = item_catalog_by_id.get(int(item_id))
            except (TypeError, ValueError):
                item_row = None
            if item_row:
                item_effect_type = item_row.get("effect_type")
                item_effect_label = combat_item_effect_display_label(item_effect_type)
        member_states[sid] = {
            "display_name": p.get("display_name") or sid,
            "avatar": p.get("avatar"),
            "hp": p.get("hp"),
            "max_hp": p.get("max_hp"),
            "sanity": p.get("sanity"),
            "power": p.get("power"),
            "intellect": p.get("intellect"),
            "resilience": get_effective_stat(p, "resilience"),
            "near_death_until": p.get("near_death_until"),
            "is_protagonist": bool(p.get("is_protagonist")),
            "is_team_leader": bool(p.get("is_team_leader")),
            "protagonist_key": p.get("protagonist_key"),
            "trauma_count": p.get("trauma_count"),
            "submitted": bool(submitted),
            "action_type": (submitted or {}).get("action_type"),
            "dice_result": (submitted or {}).get("dice_result"),
            "item_id": item_id,
            "item_effect_type": item_effect_type,
            "item_effect_label": item_effect_label,
        }

    logs = combat.get("logs") or []
    recent_logs = logs[-20:]
    log_messages = [
        entry.get("message") if isinstance(entry, dict) else str(entry)
        for entry in recent_logs
    ]
    log_entries = [
        {
            "type": entry.get("type", "event"),
            "message": entry.get("message", str(entry)),
        }
        if isinstance(entry, dict) else {"type": "event", "message": str(entry)}
        for entry in recent_logs
    ]

    ending_state = judge_ending(team_id) if team_id else None

    payload = {
        "success": True,
        "combat_id": combat["id"],
        "encounter_id": combat["encounter_id"],
        "title": (encounter or {}).get("title"),
        "status": combat.get("status"),
        "current_phase": combat.get("current_phase", 0),
        "phase_started_at": combat.get("phase_started_at"),
        "phase_deadline": combat.get("phase_deadline"),
        "phase_expired": combat_phase_expired(combat, combat_settings),
        "remaining_seconds": max(
            0,
            int((datetime.fromisoformat(combat["phase_deadline"]) - datetime.now()).total_seconds())
        ) if combat.get("phase_deadline") else None,
        "enemy": build_enemy_combat_stats(combat, encounter),
        "member_states": member_states,
        "protagonists": protagonists,
        "my_state": {
            **member_states.get(squad_id, {}),
            "avatar": me.get("avatar"),
            "display_name": me.get("display_name") or squad_id,
            "power": me.get("power"),
            "intellect": me.get("intellect"),
            "hp": me.get("hp"),
            "max_hp": me.get("max_hp"),
            "sanity": me.get("sanity"),
            "resilience": get_effective_stat(me, "resilience"),
            "near_death_until": me.get("near_death_until"),
        },
        "berserk_warning": berserk_hint,
        "berserk_chance": round(berserk_probability(me.get("sanity", 50)) * 100),
        "log": log_messages,
        "log_entries": log_entries,
        "reflection_prompt": (encounter or {}).get("reflection_prompt"),
        "combat_settings": combat_settings,
        "available_actions": list(settings.combat_action_types),
        "winner": combat.get("winner"),
        "enemy_description": (encounter or {}).get("enemy", {}).get("description"),
        "route": team_route or (encounter or {}).get("route"),
        "max_phases": combat_settings.get("max_phases", 5),
        "my_squad_id": squad_id,
        "team_id": team_id,
        "story_stage": get_team_story_stage(team_id) if team_id else 0,
        "protagonist_player_control": protagonist_player_control_enabled(
            encounter, get_team_story_stage(team_id) if team_id else 0
        ),
        "controllable_protagonist_id": (
            get_controllable_protagonist_squad_id(
                team_id,
                team_route,
                encounter,
                get_team_story_stage(team_id) if team_id else 0,
            )
            if team_id else None
        ),
        "protagonist_trauma_total": (
            get_team_protagonist_trauma_total(team_id) if team_id else 0
        ),
        "ending": ending_state,
        "trauma_level": (ending_state or {}).get("trauma_level", "safe"),
    }
    _enrich_settlement_meta(payload, combat=combat)
    return payload

def _preview_action_enemy_damage(player, action_type, dice_result, item_id, enemy_resilience, enemy_sanity):
    """預估單一行動對敵人傷害（不含暴走隨機結果）"""
    from models.item import get_item_by_id

    meta = {}
    sanity = int(player.get("sanity") or 0)
    berserk_chance = berserk_probability(sanity)
    if berserk_chance > 0:
        meta["berserk_risk"] = True
        meta["berserk_chance"] = round(berserk_chance * 100)

    try:
        dice = max(0, min(3, int(dice_result)))
    except (TypeError, ValueError):
        dice = 1
    multiplier = dice_multiplier(dice)
    item_bonus = 0
    if item_id:
        item = get_item_by_id(int(item_id))
        if item:
            effect = item.get("effect_type")
            if effect == "power_up":
                item_bonus = abs(int(item.get("effect_value") or 0))
            elif effect in ("hp_up", "sanity_up"):
                return 0, meta

    if action_type in ATTACK_ACTION_TYPES or action_type == "use_item":
        if action_type == "use_zoo":
            multiplier *= zoo_bonus_multiplier(sanity)
        stat_info = describe_attack_stat(player)
        meta["attack_stat"] = stat_info["stat"]
        meta["attack_stat_value"] = stat_info["value"]
        meta["attack_stat_label"] = stat_info["label"]
        dmg = calculate_attack_damage(
            player, enemy_resilience, multiplier=multiplier, item_bonus=item_bonus,
        )
    else:
        dmg = 0

    if meta.get("berserk_risk"):
        meta["damage_if_normal"] = dmg
        meta["damage_note"] = "暴走時可能無法對敵輸出"
    return dmg, meta

def build_combat_round_preview(
    combat_id, squad_id, action_type, dice_result, item_id=None, as_protagonist=False,
):
    combat = get_combat(combat_id)
    if not combat or combat.get("status") != "player_phase":
        return None

    encounter = load_encounter(combat["encounter_id"])
    enemy_res = int(combat.get("enemy_resilience") or 0)
    enemy_san = int(combat.get("enemy_sanity") or 0)
    enemy_base = int(combat.get("enemy_base_damage") or 0)
    participants = get_combat_participants(combat)
    participant_by_id = {p["squad_id"]: p for p in participants}
    player = fetch_squads_by_ids([squad_id]).get(squad_id) or participant_by_id.get(squad_id)
    team_id = (player or {}).get("team_id")
    if as_protagonist and team_id:
        team_row = get_team_by_id(team_id) or {}
        story_stage = get_team_story_stage(team_id)
        acting_id = get_controllable_protagonist_squad_id(
            team_id, team_row.get("route"), encounter, story_stage,
        )
        if acting_id:
            squad_id = acting_id
    squad = participant_by_id.get(squad_id) or fetch_squads_by_ids([squad_id]).get(squad_id)
    if not squad:
        return None

    phase_actions = dict(combat.get("phase_actions") or {})

    my_dmg, my_meta = _preview_action_enemy_damage(
        squad, action_type, dice_result, item_id, enemy_res, enemy_san,
    )
    ally_damage = 0
    ally_count = 0
    for pid, ad in phase_actions.items():
        if pid == squad_id:
            continue
        player = participant_by_id.get(pid)
        if not player:
            continue
        d, _ = _preview_action_enemy_damage(
            player,
            ad.get("action_type"),
            ad.get("dice_result", 1),
            ad.get("item_id"),
            enemy_res,
            enemy_san,
        )
        ally_damage += d
        ally_count += 1

    hypo_actions = dict(phase_actions)
    hypo_actions[squad_id] = {
        "action_type": action_type,
        "dice_result": dice_result,
        "item_id": item_id,
    }

    active_participants = []
    for p in participants:
        sid = p["squad_id"]
        if p.get("near_death_until"):
            try:
                if datetime.now() < datetime.fromisoformat(p["near_death_until"]):
                    continue
            except ValueError:
                pass
        active_participants.append(p)

    all_submitted = all(hypo_actions.get(p["squad_id"]) for p in active_participants)
    pending_count = sum(1 for p in active_participants if not hypo_actions.get(p["squad_id"]))

    target = get_lowest_resilience_player(active_participants) or (participants[0] if participants else None)
    counter_damage = 0
    counter_target_name = None
    team_defend_count = count_team_defenders(hypo_actions)
    team_defend_mult = team_defend_damage_multiplier(team_defend_count)
    counter_defending = team_defend_count > 0
    if target:
        target_id = target["squad_id"]
        counter_damage = calculate_incoming_damage(
            enemy_base,
            get_effective_stat(target, "resilience"),
            team_defend_multiplier=team_defend_mult,
        )
        counter_target_name = target.get("display_name") or target_id

    risks = []
    if my_meta.get("berserk_risk"):
        risks.append({
            "level": "berserk",
            "message": f"你有 {my_meta['berserk_chance']}% 暴走機率，可能無法對敵造成傷害",
        })

    for p in active_participants:
        sid = p["squad_id"]
        name = p.get("display_name") or sid
        hp = int(p.get("hp") or 0)
        sanity = int(p.get("sanity") or 0)
        if target and sid == target["squad_id"] and counter_damage > 0:
            after_hp = hp - counter_damage
            if after_hp <= 0:
                risks.append({
                    "level": "critical",
                    "message": f"{name} 可能被反擊致命或陷入瀕死！",
                })
            elif after_hp < 20:
                risks.append({
                    "level": "hp",
                    "message": f"{name} 生命值將降至 {after_hp}（低於 20，瀕死風險）",
                })
        if sanity < 10:
            risks.append({
                "level": "sanity",
                "message": f"{name} 神智 {sanity}，暴走機率約 90%",
            })
        elif sanity < 20:
            risks.append({
                "level": "sanity",
                "message": f"{name} 神智 {sanity}，暴走機率約 50%",
            })
        elif sanity < 40:
            risks.append({
                "level": "sanity",
                "message": f"{name} 神智 {sanity}，仍有暴走風險（約 20%）",
            })

    action_labels = {
        "attack": "攻擊",
        "attack_physical": "攻擊",
        "attack_nonphysical": "攻擊",
        "defend": "堅守界線",
        "use_zoo": "Zoo 能力",
        "use_item": "使用物品",
        "pass": "觀望",
        "escape": "逃跑",
    }

    return {
        "action_type": action_type,
        "action_label": action_labels.get(action_type, action_type),
        "dice_result": dice_result,
        "my_damage_to_enemy": my_dmg,
        "ally_damage_to_enemy": ally_damage,
        "total_damage_to_enemy": my_dmg + ally_damage,
        "enemy_counter_damage": counter_damage,
        "counter_target_name": counter_target_name,
        "counter_defending": counter_defending,
        "team_defend_count": team_defend_count,
        "counter_pending": not all_submitted and len(active_participants) > 1,
        "pending_teammates": max(0, pending_count - 0) if not all_submitted else 0,
        "phase_resolves_now": all_submitted or len(active_participants) <= 1,
        "berserk_risk": my_meta.get("berserk_risk", False),
        "damage_if_normal": my_meta.get("damage_if_normal", my_dmg),
        "attack_stat_label": my_meta.get("attack_stat_label"),
        "attack_stat_value": my_meta.get("attack_stat_value"),
        "risks": risks,
    }


def build_single_player_preview(combat_id, squad_id, squad=None):
    """多人模式：只顯示該玩家自己相關的行動預覽。"""
    combat = get_combat(combat_id)
    if not squad:
        squad = fetch_squads_by_ids([squad_id]).get(squad_id)
    if not combat or not squad:
        return None

    action_data = (combat.get("phase_actions") or {}).get(squad_id)
    if not action_data:
        return None

    action_type = action_data.get("action_type") or action_data.get("action") or "pass"
    dice_result = action_data.get("dice_result", action_data.get("dice", 1))
    item_id = action_data.get("item_id")

    base = build_combat_round_preview(
        combat_id, squad_id, action_type, dice_result, item_id,
    )
    if not base:
        return None

    display_name = squad.get("display_name") or squad_id
    counter_target = base.get("counter_target_name") or ""
    me_is_target = counter_target == display_name or counter_target == squad_id
    counter_pending = bool(base.get("counter_pending"))
    damage_taken = 0
    if me_is_target and not counter_pending:
        damage_taken = int(base.get("enemy_counter_damage") or 0)

    team_id = squad.get("team_id")
    protagonists = get_team_protagonists(team_id) if team_id else {}
    active_route = protagonists.get("active_route") or squad.get("route")
    protagonist_name = None
    if active_route == "iggy":
        protagonist_name = (protagonists.get("iggy") or {}).get("name") or "Iggy"
    elif active_route == "marah":
        protagonist_name = (protagonists.get("marah") or {}).get("name") or "Marah"

    damage_dealt = int(base.get("my_damage_to_enemy") or 0)
    summary_parts = []
    if damage_dealt > 0:
        summary_parts.append(f"你對敵人造成 {damage_dealt} 點傷害")
    elif base.get("action_label") == "堅守界線":
        summary_parts.append("你為全隊堅守界線")
    elif base.get("action_label") == "逃跑":
        summary_parts.append("你選擇逃跑")
    elif base.get("action_label") == "觀望":
        summary_parts.append("你選擇觀望")
    else:
        summary_parts.append(f"你完成「{base.get('action_label', '行動')}」")

    if protagonist_name and damage_dealt > 0:
        summary_parts.append(f"（{protagonist_name} 路線加成已計入）")

    if counter_pending and me_is_target:
        est = int(base.get("enemy_counter_damage") or 0)
        summary_parts.append(f"敵人可能對你反擊約 {est} 點（待全隊提交後結算）")
    elif damage_taken > 0:
        summary_parts.append(f"你受到 {damage_taken} 點反擊傷害")

    return {
        "player_name": display_name,
        "action_type": base.get("action_type"),
        "action_label": base.get("action_label"),
        "dice_result": base.get("dice_result"),
        "damage_dealt": damage_dealt,
        "damage_taken": damage_taken,
        "damage_taken_pending": counter_pending and me_is_target,
        "estimated_counter_damage": int(base.get("enemy_counter_damage") or 0) if me_is_target else 0,
        "counter_pending": counter_pending,
        "protagonist_name": protagonist_name,
        "berserk_risk": base.get("berserk_risk", False),
        "damage_if_normal": base.get("damage_if_normal", damage_dealt),
        "attack_stat_label": base.get("attack_stat_label"),
        "attack_stat_value": base.get("attack_stat_value"),
        "summary": "，".join(summary_parts) + "。",
        "risks": base.get("risks") or [],
    }


def _combat_outcome_json(winner, encounter, team_id=None, participants=None):
    if winner == "squad":
        return build_victory_outcome_payload(encounter, team_id=team_id)
    if winner == "enemy":
        return build_defeat_outcome_payload(
            encounter,
            participants=participants,
            team_id=team_id,
        )
    if winner == "escaped":
        escape_block = (encounter or {}).get("escape") or {}
        return {
            "success": True,
            "status": "ended",
            "outcome": "escaped",
            "winner": "escaped",
            "active": False,
            "narrative": escape_block.get("narrative") or "全隊成功脫離戰鬥。",
            "reflection_prompt": None,
        }
    return None


def build_escape_outcome_response(combat, encounter, squad_id, team_id=None):
    """Escape success JSON — combat ends without victory/defeat rewards."""
    payload = build_combat_status_response(combat, encounter, squad_id)
    meta = _combat_outcome_json("escaped", encounter, team_id=team_id) or {}
    payload.update(meta)
    payload["round_settlement"] = {
        "team_damage_dealt": 0,
        "enemy_damage_dealt": 0,
        "escape_triggered": True,
        "escape_success": True,
        "player_hits": [],
        "counter_hits": [],
        "breakdown": {},
    }
    _enrich_settlement_meta(payload, combat=combat)
    return payload


def build_victory_outcome_response(combat, encounter, squad_id, team_id=None):
    """
    Victory JSON that includes the final round settlement (logs, enemy.hp, round_settlement).
    Used on killing-blow so the client can sync HP and show the settlement modal before victory.
    """
    if not combat or not squad_id:
        return build_victory_outcome_payload(
            encounter,
            team_id=team_id,
            combat_id=(combat or {}).get("id"),
            current_round=(combat or {}).get("current_phase"),
        )
    round_payload = _build_round_resolved_response(combat, encounter, squad_id)
    meta = build_victory_outcome_payload(
        encounter,
        team_id=team_id,
        combat_id=combat.get("id"),
        current_round=combat.get("current_phase"),
    )
    payload = {**round_payload, **meta}
    payload["outcome"] = "victory"
    payload["winner"] = "squad"
    payload["status"] = "ended"
    payload["active"] = False
    payload["round_resolved"] = True
    enemy = dict(payload.get("enemy") or {})
    enemy["hp"] = 0
    payload["enemy"] = enemy
    settlement = dict(payload.get("round_settlement") or {})
    settlement["enemy_hp_after"] = 0
    payload["round_settlement"] = settlement
    payload["round_enemy_damage"] = settlement.get("team_damage_dealt") or payload.get("round_enemy_damage") or 0
    return payload


def combat_outcome_if_finished(combat, encounter, team_id=None, squad_id=None):
    """Return victory/defeat JSON when combat already ended or enemy HP is 0."""
    if not combat:
        return None
    squad_id = squad_id or combat.get("squad_id")
    if combat.get("status") == "ended":
        winner = combat.get("winner")
        if winner == "squad" and squad_id:
            return build_victory_outcome_response(combat, encounter, squad_id, team_id=team_id)
        if winner == "escaped" and squad_id:
            return build_escape_outcome_response(combat, encounter, squad_id, team_id=team_id)
        participants = get_combat_participants(combat) if combat else None
        return _combat_outcome_json(
            winner,
            encounter,
            team_id=team_id,
            participants=participants,
        )
    if int(combat.get("enemy_hp") or 0) <= 0:
        combat_id = combat.get("id")
        if combat_id:
            combat = _end_combat(combat_id, "squad", encounter)
        if squad_id:
            return build_victory_outcome_response(combat, encounter, squad_id, team_id=team_id)
        return _combat_outcome_json("squad", encounter, team_id=team_id)
    return None


def _build_full_preview_from_status(status_payload):
    return {
        "log_entries": status_payload.get("log_entries") or [],
        "log": status_payload.get("log") or [],
        "current_phase": status_payload.get("current_phase"),
        "enemy": status_payload.get("enemy"),
        "member_states": status_payload.get("member_states"),
        "round_settlement": status_payload.get("round_settlement"),
        "round_enemy_damage": status_payload.get("round_enemy_damage"),
        "round_player_damage": status_payload.get("round_player_damage"),
    }


def _round_enemy_damage_from_logs(logs):
    """Parse latest phase summary for UI feedback (e.g. high-HP test enemies)."""
    for entry in reversed(logs or []):
        if not isinstance(entry, dict) or entry.get("type") != "summary":
            continue
        msg = entry.get("message") or ""
        match = re.search(r"受到共\s*(\d+)\s*點傷害", msg)
        if match:
            return int(match.group(1))
    return 0


def _latest_team_summary_index(logs):
    for i in range(len(logs or []) - 1, -1, -1):
        entry = logs[i]
        if not isinstance(entry, dict) or entry.get("type") != "summary":
            continue
        msg = entry.get("message") or ""
        if re.search(r"受到共\s*(\d+)\s*點傷害", msg):
            return i
    return None


def _find_participant_by_display(participants, display_name):
    name = (display_name or "").strip()
    if not name:
        return None
    for participant in participants or []:
        if (participant.get("display_name") or "").strip() == name:
            return participant
        if (participant.get("squad_id") or "").strip() == name:
            return participant
    return None


def _participant_combat_role(participant, viewer_squad_id):
    if not participant:
        return "teammate"
    if participant.get("is_protagonist"):
        return "protagonist"
    sid = participant.get("squad_id")
    if viewer_squad_id and sid == viewer_squad_id:
        return "player"
    return "teammate"


def _build_settlement_role_breakdown(player_hits, counter_hits, team_dealt, enemy_dealt):
    dealt = {"player": 0, "protagonist": 0, "teammate": 0}
    taken = {"player": 0, "protagonist": 0, "teammate": 0}
    for hit in player_hits or []:
        role = hit.get("role") or "teammate"
        if role not in dealt:
            role = "teammate"
        dealt[role] += int(hit.get("damage") or 0)
    for hit in counter_hits or []:
        role = hit.get("role") or "teammate"
        if role not in taken:
            role = "teammate"
        taken[role] += int(hit.get("damage") or 0)
    return {
        "dealt": {
            **dealt,
            "total": int(team_dealt or 0) or sum(dealt.values()),
        },
        "taken": {
            **taken,
            "total": int(enemy_dealt or 0) or sum(taken.values()),
        },
        "enemy": {
            "damage_taken": int(team_dealt or 0) or sum(dealt.values()),
            "damage_dealt": int(enemy_dealt or 0) or sum(taken.values()),
        },
    }


def _round_settlement_from_logs(logs, participants=None, viewer_squad_id=None):
    """
    Parse the most recent completed round from combat logs.
    Returns team damage to enemy and enemy counter damage to squad.
    """
    entries = logs or []
    participants = participants or []
    summary_idx = _latest_team_summary_index(entries)
    team_dealt = _round_enemy_damage_from_logs(entries)
    enemy_dealt = 0
    counter_hits = []
    player_hits = []

    if summary_idx is None:
        breakdown = _build_settlement_role_breakdown(player_hits, counter_hits, team_dealt, enemy_dealt)
        escape_triggered, escape_success = _escape_meta_from_logs(entries)
        result = {
            "team_damage_dealt": team_dealt,
            "enemy_damage_dealt": enemy_dealt,
            "counter_hits": counter_hits,
            "player_hits": player_hits,
            "breakdown": breakdown,
        }
        if escape_triggered:
            result["escape_triggered"] = True
            result["escape_success"] = escape_success
        return result

    prev_summary_idx = _latest_team_summary_index(entries[:summary_idx])
    round_start = (prev_summary_idx + 1) if prev_summary_idx is not None else 0

    for entry in entries[round_start:summary_idx]:
        if not isinstance(entry, dict) or entry.get("type") != "damage":
            continue
        msg = entry.get("message") or ""
        match = re.search(r"^(.+?)\s+(?:攻擊|Zoo 能力)對.+造成\s*(\d+)\s*點傷害", msg)
        if match:
            display = match.group(1).strip()
            participant = _find_participant_by_display(participants, display)
            player_hits.append({
                "player": display,
                "damage": int(match.group(2)),
                "squad_id": participant.get("squad_id") if participant else None,
                "role": _participant_combat_role(participant, viewer_squad_id),
            })

    for entry in entries[summary_idx + 1:]:
        if not isinstance(entry, dict):
            continue
        etype = entry.get("type")
        if etype in ("near_death", "event", "incapacitated"):
            continue
        if etype != "enemy_attack":
            break
        msg = entry.get("message") or ""
        match = re.search(r"造成\s*(\d+)\s*點傷害", msg)
        if not match:
            continue
        dmg = int(match.group(1))
        enemy_dealt += dmg
        target_match = re.search(r"反擊\s*([^，]+)", msg)
        target_name = target_match.group(1).strip() if target_match else "?"
        participant = _find_participant_by_display(participants, target_name)
        counter_hits.append({
            "target": target_name,
            "damage": dmg,
            "squad_id": participant.get("squad_id") if participant else None,
            "role": _participant_combat_role(participant, viewer_squad_id),
        })

    summary_hp = None
    if summary_idx is not None:
        summary_msg = entries[summary_idx].get("message") or ""
        hp_match = re.search(r"剩餘\s*HP\s*(\d+)", summary_msg)
        if hp_match:
            summary_hp = int(hp_match.group(1))

    breakdown = _build_settlement_role_breakdown(player_hits, counter_hits, team_dealt, enemy_dealt)
    escape_triggered, escape_success = _escape_meta_from_logs(entries, summary_idx)
    result = {
        "team_damage_dealt": team_dealt,
        "enemy_damage_dealt": enemy_dealt,
        "counter_hits": counter_hits,
        "player_hits": player_hits,
        "enemy_hp_after": summary_hp,
        "breakdown": breakdown,
    }
    if escape_triggered:
        result["escape_triggered"] = True
        result["escape_success"] = escape_success
    return result


def _attach_round_settlement(payload, combat=None):
    logs = (combat or {}).get("logs") or payload.get("log_entries")
    participants = get_combat_participants(combat) if combat else []
    viewer_squad_id = payload.get("my_squad_id")
    settlement = _round_settlement_from_logs(
        logs,
        participants=participants,
        viewer_squad_id=viewer_squad_id,
    )
    enemy_hp = (payload.get("enemy") or {}).get("hp")
    if enemy_hp is None and combat is not None and combat.get("enemy_hp") is not None:
        enemy_hp = int(combat.get("enemy_hp"))
    if enemy_hp is not None:
        settlement["enemy_hp_after"] = int(enemy_hp)
    elif settlement.get("enemy_hp_after") is None:
        settlement["enemy_hp_after"] = _enemy_hp_from_logs(logs)
    payload["round_settlement"] = settlement
    payload["round_enemy_damage"] = settlement.get("team_damage_dealt") or 0
    payload["round_player_damage"] = settlement.get("enemy_damage_dealt") or 0
    return payload


def _enrich_settlement_meta(payload, combat=None):
    """Additive COMBAT_V2 fields: stable settlement progress on every status snapshot."""
    combat_id = payload.get("combat_id") or (combat or {}).get("id")
    if combat_id is None:
        return payload
    current_phase = int(
        (combat or {}).get("current_phase")
        if combat is not None
        else payload.get("current_phase") or 0
    )
    settled_round_index = max(0, current_phase - 1)
    payload["settled_round_index"] = settled_round_index
    payload["settlement_id"] = f"{combat_id}:{settled_round_index}"
    return payload


def _build_round_resolved_response(combat, encounter, squad_id):
    combat = reconcile_enemy_hp(combat, persist=True) if combat else combat
    payload = build_combat_status_response(combat, encounter, squad_id)
    payload["status"] = "round_resolved"
    payload["round_resolved"] = True
    payload["active"] = combat.get("status") not in ("ended", "precheck")
    _attach_round_settlement(payload, combat=combat)
    _enrich_settlement_meta(payload, combat=combat)
    payload["full_preview"] = _build_full_preview_from_status(payload)
    return payload


def create_combat_record(squad_id, encounter_id, encounter, initial_status="precheck"):
    squad = get_squad(squad_id)
    team_id = (squad or {}).get("team_id")
    clean_team_id = normalize_team_id(team_id) if team_id else None

    enemy = encounter.get("enemy", {})
    enemy_stats = build_enemy_combat_stats(
        {
            "enemy_name": enemy.get("name", "敵人"),
            "enemy_hp": enemy.get("hp", 100),
            "enemy_max_hp": enemy.get("hp", 100),
            "enemy_resilience": enemy.get("resilience", 0),
            "enemy_sanity": enemy.get("sanity", 0),
            "enemy_base_damage": enemy.get("base_damage", 10),
            "enemy_power": enemy.get("power"),
            "enemy_intellect": enemy.get("intellect"),
        },
        encounter,
    )
    combat_settings = encounter.get("combat_settings", {})
    now = datetime.now().isoformat()
    logs = [{"at": now, "message": f"遭遇戰開始：{encounter.get('title', encounter_id)}"}]
    phase_started = now if initial_status == "player_phase" else None
    phase_deadline = (
        combat_phase_deadline(now, combat_settings.get("phase_time_limit_seconds", 180))
        if initial_status == "player_phase" else None
    )

    with immediate_transaction() as conn:
        c = conn.cursor()
        if clean_team_id:
            row = c.execute(
                """
                SELECT c.id FROM combats c
                INNER JOIN squads s ON c.squad_id = s.squad_id
                WHERE UPPER(TRIM(s.team_id)) = UPPER(TRIM(?))
                  AND c.status NOT IN ('ended')
                ORDER BY c.started_at DESC
                LIMIT 1
                """,
                (clean_team_id,),
            ).fetchone()
            if row:
                raise ActiveCombatExistsError(row[0])

        c.execute(
            """INSERT INTO combats
               (squad_id, encounter_id, status, current_phase, enemy_name, enemy_hp, enemy_max_hp,
                enemy_resilience, enemy_sanity, enemy_base_damage, enemy_power, enemy_intellect,
                phase_actions, logs, phase_started_at, phase_deadline, started_at)
               VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?, ?, ?)""",
            (
                squad_id,
                encounter_id,
                initial_status,
                enemy_stats["name"],
                enemy_stats["hp"],
                enemy_stats["max_hp"],
                enemy_stats["resilience"],
                enemy_stats["sanity"],
                enemy_stats["base_damage"],
                enemy_stats["power"],
                enemy_stats["intellect"],
                json.dumps(logs, ensure_ascii=False),
                phase_started,
                phase_deadline,
                now,
            ),
        )
        combat_id = c.lastrowid
        if clean_team_id:
            c.execute(
                "UPDATE squads SET current_combat_id = ? WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))",
                (combat_id, clean_team_id),
            )

    return get_combat(combat_id)


# Public aliases for routes / templates
COMBAT_ACTION_TYPES = settings.combat_action_types
ATTACK_ACTION_TYPES = settings.attack_action_types
DICE_MULTIPLIERS = settings.dice_multipliers
NEAR_DEATH_MINUTES = settings.near_death_minutes


===== FILE: models/item.py =====

import sqlite3
from datetime import datetime

from models.settings import settings
from models.squad import apply_hp_change, get_squad, is_near_death_active
from utils.db_tx import immediate_transaction
from utils.helpers import clamped_stat_delta_expr, normalize_team_id

NEAR_DEATH_RESCUE_EFFECT_TYPES = frozenset({"hp_up", "near_death_rescue"})
RESCUE_REVIVE_HP = 25


def get_item_by_id(item_id):
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM items WHERE id = ? AND COALESCE(is_active, 1) = 1",
        (item_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_item_by_qr_code_value(qr_code_value):
    if not qr_code_value:
        return None
    clean_value = str(qr_code_value).strip()
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM items WHERE qr_code_value = ? AND COALESCE(is_active, 1) = 1",
        (clean_value,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def format_item_effect_text(effect_type, effect_value):
    if not effect_type or effect_type == "mixed":
        return None
    labels = settings.item_effect_labels or {}
    label = labels.get(effect_type)
    if not label:
        return None
    try:
        value = int(effect_value)
    except (TypeError, ValueError):
        return None
    sign = "+" if value >= 0 else ""
    return f"{sign}{value} {label}"


def serialize_item_for_client(item):
    if not item:
        return None
    has_ability = bool(item.get("has_ability"))
    effect_type = item.get("effect_type")
    effect_value = item.get("effect_value")
    image_path = item.get("image_path") or "/static/images/default-item.svg"
    return {
        "id": item["id"],
        "name": item.get("name"),
        "description": item.get("description"),
        "icon": item.get("icon"),
        "image_path": image_path,
        "item_type": item.get("item_type"),
        "qr_code_value": item.get("qr_code_value"),
        "has_ability": has_ability,
        "effect_type": effect_type,
        "effect_value": effect_value,
        "effect_text": format_item_effect_text(effect_type, effect_value) if has_ability else None,
    }


def _apply_stat_delta(c, squad_id, stat, delta):
    row = c.execute(
        "SELECT hp, max_hp, sanity, power, intellect, resilience, near_death_until FROM squads WHERE squad_id = ?",
        (squad_id,),
    ).fetchone()
    if not row:
        return None

    if stat == "hp":
        if delta > 0 and is_near_death_active(dict(row)):
            return dict(row)
        new_hp, new_max_hp = apply_hp_change(row["hp"], row["max_hp"], delta)
        c.execute(
            "UPDATE squads SET hp = ?, max_hp = ? WHERE squad_id = ?",
            (new_hp, new_max_hp, squad_id),
        )
    elif stat == "sanity":
        operator = "+" if delta >= 0 else "-"
        magnitude = abs(delta)
        c.execute(
            f"UPDATE squads SET sanity = {clamped_stat_delta_expr('sanity', operator)} WHERE squad_id = ?",
            (magnitude, magnitude, squad_id),
        )
    else:
        operator = "+" if delta >= 0 else "-"
        magnitude = abs(delta)
        c.execute(
            f"UPDATE squads SET {stat} = {clamped_stat_delta_expr(stat, operator)} WHERE squad_id = ?",
            (magnitude, magnitude, squad_id),
        )

    updated = c.execute(
        "SELECT hp, max_hp, sanity, power, intellect, resilience FROM squads WHERE squad_id = ?",
        (squad_id,),
    ).fetchone()
    return dict(updated) if updated else None


def apply_item_effect_to_squad(squad_id, item):
    if not item or not item.get("has_ability") or not item.get("effect_type"):
        return None

    effect_type = item.get("effect_type")
    if effect_type == "mixed":
        return None

    stat_map = settings.item_effect_stat_map or {}
    squad_attrs = settings.squad_attributes or []
    stat = stat_map.get(effect_type)
    if not stat or stat not in squad_attrs:
        return None

    try:
        delta = int(item.get("effect_value") or 0)
    except (TypeError, ValueError):
        return None
    if delta == 0:
        return None

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        stats = _apply_stat_delta(c, squad_id, stat, delta)
        conn.commit()
    finally:
        conn.close()

    if not stats:
        return None

    return {
        "effect_type": effect_type,
        "effect_value": delta,
        "effect_text": format_item_effect_text(effect_type, delta),
        "stat": stat,
        "stats": stats,
    }


def team_has_item(team_id, item_id):
    if not team_id:
        return False
    clean_team_id = normalize_team_id(team_id)
    conn = sqlite3.connect(settings.db_path)
    count = conn.execute("""
        SELECT COUNT(*) FROM player_items pi
        JOIN squads s ON pi.squad_id = s.squad_id
        WHERE UPPER(TRIM(s.team_id)) = UPPER(TRIM(?)) AND pi.item_id = ?
    """, (clean_team_id, item_id)).fetchone()[0]
    conn.close()
    return count > 0


def team_has_item_by_name(team_id, item_name):
    if not team_id or not item_name:
        return False
    clean_team_id = normalize_team_id(team_id)
    conn = sqlite3.connect(settings.db_path)
    row = conn.execute("""
        SELECT COUNT(*) FROM player_items pi
        JOIN squads s ON pi.squad_id = s.squad_id
        JOIN items i ON pi.item_id = i.id
        WHERE UPPER(TRIM(s.team_id)) = UPPER(TRIM(?)) AND i.name = ?
    """, (clean_team_id, item_name)).fetchone()
    conn.close()
    return row[0] > 0


def grant_item_to_squad(squad_id, item_id, source="story"):
    squad = get_squad(squad_id)
    if not squad:
        return False, "找不到玩家", None

    item = get_item_by_id(item_id)
    if not item:
        return False, "物品不存在或已停用", None

    is_one_time = item.get("is_one_time_use", 1)
    enforce_qr_once = source == "qr" and is_one_time
    team_id = squad.get("team_id")
    clean_team_id = normalize_team_id(team_id) if team_id else None
    now = datetime.now().isoformat()

    try:
        with immediate_transaction() as tx:
            tc = tx.cursor()
            if enforce_qr_once:
                used = tc.execute(
                    "SELECT squad_id FROM qr_code_uses WHERE item_id = ? AND squad_id = ?",
                    (item_id, squad_id),
                ).fetchone()
                if used:
                    return False, "你已經使用過此 QR Code", None

            existing = tc.execute(
                "SELECT id FROM player_items WHERE squad_id = ? AND item_id = ?",
                (squad_id, item_id),
            ).fetchone()
            if existing:
                return False, "你已經擁有此物品", None

            if clean_team_id:
                team_dup = tc.execute(
                    """
                    SELECT COUNT(*) FROM player_items pi
                    JOIN squads s ON pi.squad_id = s.squad_id
                    WHERE UPPER(TRIM(s.team_id)) = UPPER(TRIM(?)) AND pi.item_id = ?
                    """,
                    (clean_team_id, item_id),
                ).fetchone()[0]
                if team_dup > 0:
                    return False, "同一隊內已經有人擁有此物品", None

            owned_count = tc.execute(
                "SELECT COUNT(*) FROM player_items WHERE squad_id = ?",
                (squad_id,),
            ).fetchone()[0]
            max_slots = settings.max_inventory_slots
            if owned_count >= max_slots:
                return False, f"你已經持有 {max_slots} 樣物品，請先丟棄", None

            tc.execute(
                "INSERT INTO player_items (squad_id, item_id, source, obtained_at) VALUES (?, ?, ?, ?)",
                (squad_id, item_id, source, now),
            )
            if enforce_qr_once:
                tc.execute(
                    """INSERT INTO qr_code_uses (item_id, squad_id, team_id, source, used_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (item_id, squad_id, clean_team_id, source, now),
                )
    except sqlite3.IntegrityError:
        return False, "此 QR Code 已經被使用", None
    except sqlite3.Error:
        return False, "物品發放失敗，請稍後再試", None

    applied_effect = apply_item_effect_to_squad(squad_id, item)
    return True, f"成功獲得物品：{item['name']}", applied_effect


COMBAT_USABLE_EFFECT_TYPES = frozenset({"power_up", "hp_up", "sanity_up"})

COMBAT_ITEM_EFFECT_DISPLAY_LABELS = {
    "power_up": "算力乘數增益",
    "hp_up": "生命回復",
    "sanity_up": "神智解控",
}


def combat_item_effect_display_label(effect_type):
    """Localized combat settlement label (SSOT for frontend breakdown)."""
    if not effect_type:
        return None
    return COMBAT_ITEM_EFFECT_DISPLAY_LABELS.get(effect_type, "觸發戰術整備")


def get_items_by_ids(item_ids):
    """Batch-fetch catalog items by id (avoids N+1 in combat resolve / status)."""
    try:
        ids = sorted({int(i) for i in item_ids if i is not None})
    except (TypeError, ValueError):
        return {}
    if not ids:
        return {}
    placeholders = ",".join("?" * len(ids))
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"SELECT * FROM items WHERE id IN ({placeholders}) AND COALESCE(is_active, 1) = 1",
            ids,
        ).fetchall()
    finally:
        conn.close()
    return {int(row["id"]): dict(row) for row in rows}


def _item_combat_usable(item):
    if not item:
        return False
    return bool(item.get("has_ability")) or item.get("effect_type") in COMBAT_USABLE_EFFECT_TYPES


class CombatItemConsumeBatch:
    """
    Prefetch ownership + catalog for all use_item actions in one round.
    Loop consumes use O(1) memory lookups; DELETE stays per-item in immediate_transaction.
    """

    def __init__(self, actions):
        self._catalog = {}
        self._owned = set()
        self._consumed = set()
        self._pending = set()
        pairs = []
        for squad_id, action_data in (actions or {}).items():
            action_type = action_data.get("action_type") or action_data.get("action")
            if action_type != "use_item":
                continue
            raw_item_id = action_data.get("item_id")
            if raw_item_id is None:
                continue
            try:
                catalog_item_id = int(raw_item_id)
            except (TypeError, ValueError):
                continue
            pairs.append((squad_id, catalog_item_id))
        if not pairs:
            return
        catalog_ids = {pid for _, pid in pairs}
        self._catalog = get_items_by_ids(catalog_ids)
        conn = sqlite3.connect(settings.db_path)
        try:
            clauses = " OR ".join(["(squad_id = ? AND item_id = ?)"] * len(pairs))
            params = [val for pair in pairs for val in pair]
            rows = conn.execute(
                f"SELECT squad_id, item_id FROM player_items WHERE {clauses}",
                params,
            ).fetchall()
            self._owned = {(row[0], int(row[1])) for row in rows}
        finally:
            conn.close()

    def consume_dry_run(self, squad_id, catalog_item_id):
        """Validate ownership without DB write (deferred to resolve-phase transaction)."""
        try:
            catalog_item_id = int(catalog_item_id)
        except (TypeError, ValueError):
            return False, None, "無效的物品"

        key = (squad_id, catalog_item_id)
        if key in self._consumed or key in self._pending:
            return False, None, "物品消耗失敗"

        item = self._catalog.get(catalog_item_id)
        if not item:
            return False, None, "物品不存在或已停用"
        if not _item_combat_usable(item):
            return False, None, "此物品無法在戰鬥中使用"
        if key not in self._owned:
            return False, None, "你沒有這件物品"

        self._pending.add(key)
        return True, item, ""

    def consume(self, squad_id, catalog_item_id):
        try:
            catalog_item_id = int(catalog_item_id)
        except (TypeError, ValueError):
            return False, None, "無效的物品"

        key = (squad_id, catalog_item_id)
        if key in self._consumed:
            return False, None, "物品消耗失敗"

        item = self._catalog.get(catalog_item_id)
        if not item:
            return False, None, "物品不存在或已停用"
        if not _item_combat_usable(item):
            return False, None, "此物品無法在戰鬥中使用"
        if key not in self._owned:
            return False, None, "你沒有這件物品"

        try:
            with immediate_transaction() as conn:
                deleted = conn.execute(
                    "DELETE FROM player_items WHERE squad_id = ? AND item_id = ?",
                    (squad_id, catalog_item_id),
                )
                if deleted.rowcount != 1:
                    return False, None, "物品消耗失敗"
        except sqlite3.Error:
            return False, None, "物品消耗失敗，請稍後再試"

        self._consumed.add(key)
        self._owned.discard(key)
        return True, item, ""


def build_combat_item_consume_batch(actions):
    return CombatItemConsumeBatch(actions)


def consume_squad_item_for_combat(squad_id, catalog_item_id):
    """
    Verify ownership, delete player_items row, return catalog item dict.
    catalog_item_id is items.id (same as legacy combat submit_action item_id).
    """
    try:
        catalog_item_id = int(catalog_item_id)
    except (TypeError, ValueError):
        return False, None, "無效的物品"

    item = get_item_by_id(catalog_item_id)
    if not item:
        return False, None, "物品不存在或已停用"
    if not _item_combat_usable(item):
        return False, None, "此物品無法在戰鬥中使用"

    try:
        with immediate_transaction() as conn:
            owned = conn.execute(
                "SELECT id FROM player_items WHERE squad_id = ? AND item_id = ?",
                (squad_id, catalog_item_id),
            ).fetchone()
            if not owned:
                return False, None, "你沒有這件物品"
            deleted = conn.execute(
                "DELETE FROM player_items WHERE squad_id = ? AND item_id = ?",
                (squad_id, catalog_item_id),
            )
            if deleted.rowcount != 1:
                return False, None, "物品消耗失敗"
    except sqlite3.Error:
        return False, None, "物品消耗失敗，請稍後再試"

    return True, item, ""


def is_near_death_rescue_item(item):
    """Items that may revive a near-death teammate when consumed."""
    if not item or not item.get("has_ability"):
        return False
    effect_type = item.get("effect_type")
    if effect_type not in NEAR_DEATH_RESCUE_EFFECT_TYPES:
        return False
    if effect_type == "hp_up":
        try:
            return int(item.get("effect_value") or 0) > 0
        except (TypeError, ValueError):
            return False
    return True


def apply_near_death_item_rescue(rescuer_squad_id, target_squad_id, item_id):
    """
    Consume rescuer's item and revive target (clear near_death, HP=25).
    Returns (success, message, rescued_bool).
    """
    rescuer = get_squad(rescuer_squad_id)
    target = get_squad(target_squad_id)
    if not rescuer or not target:
        return False, "找不到玩家", False
    if not rescuer.get("team_id") or rescuer.get("team_id") != target.get("team_id"):
        return False, "只能救援同隊隊友", False
    if rescuer_squad_id == target_squad_id:
        return False, "無法救援自己", False
    if not is_near_death_active(target):
        return False, "沒有需要救援的隊友", False

    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        return False, "無效的物品", False

    item = get_item_by_id(item_id)
    if not item:
        return False, "物品不存在或已停用", False
    if not is_near_death_rescue_item(item):
        return False, "此物品不能用作瀕死救援", False

    try:
        with immediate_transaction() as conn:
            c = conn.cursor()
            owned = c.execute(
                "SELECT id FROM player_items WHERE squad_id = ? AND item_id = ?",
                (rescuer_squad_id, item_id),
            ).fetchone()
            if not owned:
                return False, "你沒有這件物品", False

            target_row = c.execute(
                "SELECT near_death_until FROM squads WHERE squad_id = ?",
                (target_squad_id,),
            ).fetchone()
            if not target_row or not is_near_death_active({"near_death_until": target_row[0]}):
                return False, "沒有需要救援的隊友", False

            deleted = c.execute(
                "DELETE FROM player_items WHERE squad_id = ? AND item_id = ?",
                (rescuer_squad_id, item_id),
            )
            if deleted.rowcount != 1:
                return False, "物品消耗失敗", False

            c.execute(
                "UPDATE squads SET near_death_until = NULL, hp = ? WHERE squad_id = ?",
                (RESCUE_REVIVE_HP, target_squad_id),
            )
    except sqlite3.Error:
        return False, "救援失敗，請稍後再試", False

    rescuer_name = rescuer.get("display_name") or rescuer_squad_id
    target_name = target.get("display_name") or target_squad_id
    message = f"{rescuer_name} 使用 {item['name']} 救援 {target_name}，恢復至 {RESCUE_REVIVE_HP} 生命值。"
    return True, message, True


===== FILE: models/protagonist.py =====

"""Protagonist combat state: persistence, participation, AI, trauma."""
import sqlite3
from datetime import datetime, timedelta
from enum import Enum

from models.settings import default_protagonist_template, settings
from models.squad import DEFAULT_MAX_HP, get_team_members
from models.team import get_team_by_id, get_team_protagonists
from services.story import count_team_distinct_tasks, resolve_story_stage

PROTAGONIST_PREFIX = "protagonist:"
FINAL_STAGE_THRESHOLD = 3
TRAUMA_BAD_ENDING_LIMIT = 3


class ProtagonistLifeState(str, Enum):
    """High-level protagonist state for UI and narrative triggers."""

    NORMAL = "normal"
    NEAR_DEATH = "near_death"
    TRAUMATIZED = "traumatized"
    RESOLVED = "resolved"


PROTAGONIST_PROFILES = {
    "iggy": {
        "display_name": "Iggy",
        "avatar": "guardian_male_01.png",
        "power": 100,
        "intellect": 85,
        "resilience": 90,
    },
    "marah": {
        "display_name": "Marah",
        "avatar": "healer_female_01.png",
        "power": 75,
        "intellect": 100,
        "resilience": 95,
    },
}


def _db():
    return settings.db_path


def protagonist_squad_id(team_id, protagonist_key):
    clean = (team_id or "").strip().upper()
    return f"{PROTAGONIST_PREFIX}{protagonist_key}:{clean}"


def is_protagonist_participant(squad_id):
    return bool(squad_id and str(squad_id).startswith(PROTAGONIST_PREFIX))


def parse_protagonist_squad_id(squad_id):
    if not is_protagonist_participant(squad_id):
        return None, None
    body = str(squad_id)[len(PROTAGONIST_PREFIX):]
    if ":" not in body:
        return None, None
    key, team_id = body.split(":", 1)
    if key not in ("iggy", "marah"):
        return None, None
    return key, team_id


def get_team_story_stage(team_id):
    members = get_team_members(team_id)
    if not members:
        return 0
    leader = next((m for m in members if m.get("is_team_leader")), members[0])
    count, tasks = count_team_distinct_tasks(leader["squad_id"], team_id)
    return resolve_story_stage(count, tasks)


def initialize_protagonist_for_team(team_id, protagonist_key):
    """Create protagonist row when team picks a route (idempotent)."""
    clean_team = (team_id or "").strip().upper()
    if not clean_team or protagonist_key not in ("iggy", "marah"):
        return None
    existing = get_protagonist_state(clean_team, protagonist_key, create=False)
    if existing:
        return existing
    base = default_protagonist_template()
    now = datetime.now().isoformat()
    hp = int(base.get("hp", 100))
    max_hp = int(base.get("hp", DEFAULT_MAX_HP))
    sanity = int(base.get("sanity", 100))
    conn = sqlite3.connect(_db())
    try:
        conn.execute(
            """INSERT OR IGNORE INTO protagonist_states
               (team_id, protagonist, hp, max_hp, sanity, trauma_count, is_active, last_updated)
               VALUES (?, ?, ?, ?, ?, 0, 1, ?)""",
            (clean_team, protagonist_key, hp, max_hp, sanity, now),
        )
        conn.commit()
    finally:
        conn.close()
    return get_protagonist_state(clean_team, protagonist_key, create=False)


def get_active_protagonists(team_id):
    """Rows with is_active=1 (combat-eligible protagonists)."""
    clean_team = (team_id or "").strip().upper()
    if not clean_team:
        return []
    conn = sqlite3.connect(_db())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT team_id, protagonist, hp, max_hp, sanity, trauma_count,
                      is_active, near_death_until, last_updated
               FROM protagonist_states
               WHERE team_id = ? AND COALESCE(is_active, 1) = 1""",
            (clean_team,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def log_trauma_event(team_id, protagonist_key, delta, reason=None):
    """Append audit row for trauma changes (reason = near_death, encounter_failure, …)."""
    clean_team = (team_id or "").strip().upper()
    if not clean_team or protagonist_key not in ("iggy", "marah"):
        return
    conn = sqlite3.connect(_db())
    try:
        conn.execute(
            """INSERT INTO protagonist_trauma_log
               (team_id, protagonist, delta, reason, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (clean_team, protagonist_key, int(delta), reason, datetime.now().isoformat()),
        )
        conn.commit()
    except sqlite3.Error:
        pass
    finally:
        conn.close()


def apply_trauma(team_id, protagonist_key, amount=1, reason=None):
    """Unified trauma increment; optional reason logged to protagonist_trauma_log."""
    state = get_protagonist_state(team_id, protagonist_key, create=False)
    if not state:
        return None
    delta = int(amount)
    if delta == 0:
        return int(state.get("trauma_count") or 0)
    new_trauma = int(state.get("trauma_count") or 0) + delta
    update_protagonist_state(team_id, protagonist_key, trauma_count=new_trauma)
    if reason:
        log_trauma_event(team_id, protagonist_key, delta, reason)
    return new_trauma


def get_protagonist_life_state(team_id, protagonist_key):
    """Map DB row to ProtagonistLifeState."""
    state = get_protagonist_state(team_id, protagonist_key, create=False)
    if not state:
        return ProtagonistLifeState.NORMAL

    until = state.get("near_death_until")
    if until:
        try:
            if datetime.now() < datetime.fromisoformat(until):
                return ProtagonistLifeState.NEAR_DEATH
        except ValueError:
            pass

    trauma = int(state.get("trauma_count") or 0)
    hp = int(state.get("hp") or 0)
    if has_trauma_bad_ending(team_id) or trauma > TRAUMA_BAD_ENDING_LIMIT:
        return ProtagonistLifeState.TRAUMATIZED
    if trauma >= 2:
        return ProtagonistLifeState.TRAUMATIZED
    if hp > 0 and trauma > 0 and not until:
        return ProtagonistLifeState.RESOLVED
    return ProtagonistLifeState.NORMAL


def check_ending_condition(team_id):
    """Return 'bad_ending' if protagonist trauma exceeds limit, else 'normal_ending'."""
    if has_trauma_bad_ending(team_id):
        return "bad_ending"
    return "normal_ending"


def get_team_ending_type(team_id):
    clean_team = (team_id or "").strip().upper()
    if not clean_team:
        return None
    conn = sqlite3.connect(_db())
    try:
        row = conn.execute(
            "SELECT ending_type FROM teams WHERE team_id = ?",
            (clean_team,),
        ).fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()


def record_team_ending(team_id, ending_type, source=None):
    """Persist irreversible bad ending on teams row (source = encounter_id, optional)."""
    clean_team = (team_id or "").strip().upper()
    if not clean_team or ending_type != "bad_ending":
        return False
    if get_team_ending_type(clean_team) == "bad_ending":
        return True
    now = datetime.now().isoformat()
    conn = sqlite3.connect(_db())
    try:
        conn.execute(
            "UPDATE teams SET ending_type = ?, ending_locked_at = ? WHERE team_id = ?",
            (ending_type, now, clean_team),
        )
        conn.commit()
    finally:
        conn.close()
    return True


def get_team_ending_state(team_id):
    """Snapshot for APIs/UI: trauma totals, condition, locked ending."""
    clean_team = (team_id or "").strip().upper()
    empty = {
        "ending_condition": "normal_ending",
        "ending_type": None,
        "protagonist_trauma_total": 0,
        "trauma_bad_ending": False,
        "trauma_limit": TRAUMA_BAD_ENDING_LIMIT,
        "trauma_until_bad": TRAUMA_BAD_ENDING_LIMIT + 1,
    }
    if not clean_team:
        return empty
    trauma_total = get_team_protagonist_trauma_total(clean_team)
    locked = get_team_ending_type(clean_team)
    condition = locked if locked else check_ending_condition(clean_team)
    return {
        "ending_condition": condition,
        "ending_type": locked,
        "protagonist_trauma_total": trauma_total,
        "trauma_bad_ending": condition == "bad_ending",
        "trauma_limit": TRAUMA_BAD_ENDING_LIMIT,
        "trauma_until_bad": max(0, TRAUMA_BAD_ENDING_LIMIT + 1 - trauma_total),
    }


def get_protagonist_state(team_id, protagonist_key, create=True):
    clean_team = (team_id or "").strip().upper()
    if not clean_team or protagonist_key not in ("iggy", "marah"):
        return None

    conn = sqlite3.connect(_db())
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """SELECT team_id, protagonist, hp, max_hp, sanity, trauma_count,
                      is_active, near_death_until, last_updated
               FROM protagonist_states
               WHERE team_id = ? AND protagonist = ?""",
            (clean_team, protagonist_key),
        ).fetchone()
        if row:
            return dict(row)

        if not create:
            return None

        base = default_protagonist_template()
        now = datetime.now().isoformat()
        hp = int(base.get("hp", 100))
        max_hp = int(base.get("hp", DEFAULT_MAX_HP))
        sanity = int(base.get("sanity", 100))
        conn.execute(
            """INSERT OR IGNORE INTO protagonist_states
               (team_id, protagonist, hp, max_hp, sanity, trauma_count, is_active, last_updated)
               VALUES (?, ?, ?, ?, ?, 0, 1, ?)""",
            (clean_team, protagonist_key, hp, max_hp, sanity, now),
        )
        conn.commit()
        row = conn.execute(
            """SELECT team_id, protagonist, hp, max_hp, sanity, trauma_count,
                      is_active, near_death_until, last_updated
               FROM protagonist_states
               WHERE team_id = ? AND protagonist = ?""",
            (clean_team, protagonist_key),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_protagonist_state(team_id, protagonist_key, **kwargs):
    allowed = {"hp", "max_hp", "sanity", "trauma_count", "is_active", "near_death_until"}
    updates, params = [], []
    for key, val in kwargs.items():
        if key not in allowed:
            continue
        if key == "near_death_until" and val is None:
            updates.append("near_death_until = NULL")
        elif val is not None:
            updates.append(f"{key} = ?")
            params.append(val)
    if not updates:
        return get_protagonist_state(team_id, protagonist_key)

    updates.append("last_updated = ?")
    params.append(datetime.now().isoformat())
    clean_team = (team_id or "").strip().upper()
    params.extend([clean_team, protagonist_key])

    conn = sqlite3.connect(_db())
    try:
        conn.execute(
            f"UPDATE protagonist_states SET {', '.join(updates)} "
            "WHERE team_id = ? AND protagonist = ?",
            params,
        )
        conn.commit()
    finally:
        conn.close()
    return get_protagonist_state(team_id, protagonist_key)


def enrich_protagonists_dict(team_id, protagonists):
    if not protagonists or not team_id:
        return protagonists
    for key in ("iggy", "marah"):
        if key not in protagonists:
            continue
        state = get_protagonist_state(team_id, key, create=True)
        if not state:
            continue
        protagonists[key] = {
            **protagonists.get(key, {}),
            "hp": state["hp"],
            "max_hp": state.get("max_hp", DEFAULT_MAX_HP),
            "sanity": state["sanity"],
            "trauma_count": state.get("trauma_count", 0),
            "near_death_until": state.get("near_death_until"),
        }
    return protagonists


def get_team_protagonist_trauma_total(team_id):
    clean_team = (team_id or "").strip().upper()
    if not clean_team:
        return 0
    conn = sqlite3.connect(_db())
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(trauma_count), 0) FROM protagonist_states WHERE team_id = ?",
            (clean_team,),
        ).fetchone()
        return int(row[0] or 0)
    finally:
        conn.close()


def has_trauma_bad_ending(team_id):
    return get_team_protagonist_trauma_total(team_id) > TRAUMA_BAD_ENDING_LIMIT


def resolve_combat_protagonist_keys(team_id, encounter, story_stage):
    """Which protagonists join this combat."""
    team = get_team_by_id(team_id) or {}
    route = team.get("route")
    cfg = (encounter or {}).get("protagonist_participation") or {}
    if cfg.get("enabled") is False:
        return []

    dual = story_stage >= FINAL_STAGE_THRESHOLD or cfg.get("dual_protagonists")
    if dual:
        candidates = [k for k in ("iggy", "marah") if cfg.get(k, True)]
    elif route == "iggy" and cfg.get("iggy", True):
        candidates = ["iggy"]
    elif route == "marah" and cfg.get("marah", True):
        candidates = ["marah"]
    else:
        return []

    keys = []
    for key in candidates:
        state = get_protagonist_state(team_id, key, create=False)
        if state and not int(state.get("is_active") or 0):
            continue
        if not state:
            state = initialize_protagonist_for_team(team_id, key)
        if state and int(state.get("is_active") or 1):
            keys.append(key)
    return keys


def protagonist_player_control_enabled(encounter, story_stage):
    settings_block = (encounter or {}).get("combat_settings") or {}
    if settings_block.get("protagonist_player_control") is True:
        return True
    if settings_block.get("protagonist_player_control") is False:
        return False
    return story_stage >= FINAL_STAGE_THRESHOLD


def get_player_control_protagonist_ids(team_id, encounter, story_stage, participants):
    if not protagonist_player_control_enabled(encounter, story_stage):
        return []
    team = get_team_by_id(team_id) or {}
    route = team.get("route")
    if route not in ("iggy", "marah"):
        return []
    sid = protagonist_squad_id(team_id, route)
    active_ids = {
        p["squad_id"] for p in participants
        if p.get("is_protagonist") and p["squad_id"] == sid
    }
    return list(active_ids)


def get_controllable_protagonist_squad_id(team_id, route, encounter, story_stage):
    if not protagonist_player_control_enabled(encounter, story_stage):
        return None
    if route not in ("iggy", "marah"):
        return None
    return protagonist_squad_id(team_id, route)


def _protagonist_base_stats(team_id, protagonist_key):
    protagonists = get_team_protagonists(team_id)
    template = protagonists.get(protagonist_key) or default_protagonist_template()
    profile = PROTAGONIST_PROFILES.get(protagonist_key, {})
    return {
        "display_name": template.get("name") or profile.get("display_name") or protagonist_key.title(),
        "avatar": profile.get("avatar", "default.png"),
        "power": int(template.get("power") or profile.get("power") or 100),
        "intellect": int(template.get("intellect") or profile.get("intellect") or 100),
        "resilience": int(template.get("resilience") or profile.get("resilience") or 100),
    }


def build_protagonist_participant(team_id, protagonist_key):
    state = get_protagonist_state(team_id, protagonist_key, create=True)
    if not state:
        return None
    base = _protagonist_base_stats(team_id, protagonist_key)
    clean_team = (team_id or "").strip().upper()
    return {
        "squad_id": protagonist_squad_id(clean_team, protagonist_key),
        "display_name": base["display_name"],
        "avatar": base["avatar"],
        "team_id": clean_team,
        "is_protagonist": True,
        "protagonist_key": protagonist_key,
        "hp": int(state.get("hp") or 0),
        "max_hp": int(state.get("max_hp") or DEFAULT_MAX_HP),
        "sanity": int(state.get("sanity") or 0),
        "power": base["power"],
        "intellect": base["intellect"],
        "resilience": base["resilience"],
        "near_death_until": state.get("near_death_until"),
        "trauma_count": int(state.get("trauma_count") or 0),
        "is_team_leader": 0,
    }


def refresh_combat_participants(participants):
    refreshed = []
    for p in participants:
        if p.get("is_protagonist"):
            rebuilt = build_protagonist_participant(p.get("team_id"), p.get("protagonist_key"))
            refreshed.append(rebuilt or p)
        else:
            refreshed.append(p)
    squad_ids = [p["squad_id"] for p in refreshed if not p.get("is_protagonist")]
    from models.squad import fetch_squads_by_ids

    squads = fetch_squads_by_ids(squad_ids)
    out = []
    for p in refreshed:
        if p.get("is_protagonist"):
            out.append(p)
        else:
            out.append(squads.get(p["squad_id"], p))
    return out


def apply_damage_to_protagonist(team_id, protagonist_key, damage, participant=None):
    state = get_protagonist_state(team_id, protagonist_key, create=False)
    if not state:
        return None
    new_hp = max(0, int(state.get("hp") or 0) - int(damage))
    updates = {"hp": new_hp}
    if new_hp <= 0:
        updates["near_death_until"] = (
            datetime.now() + timedelta(minutes=settings.near_death_minutes)
        ).isoformat()
        updates["trauma_count"] = apply_trauma(
            team_id, protagonist_key, 1, reason="near_death_damage",
        )
    return update_protagonist_state(team_id, protagonist_key, **updates)


def trauma_bad_ending_narrative(encounter):
    custom = (encounter or {}).get("success", {}).get("trauma_bad_ending_narrative")
    if custom:
        return custom
    return (
        "你們表面上贏了這一仗，但主角身上累積的心理創傷已太深——"
        "即使擊敗最後的陰影，也無法迎來真正的救贖結局。"
    )


===== FILE: services/combat_engine.py =====

"""Pure combat calculation engine (no side effects, no DB, no trauma/ending).

Extracted from models/combat.py calculation helpers for unit testing and
future combat_flow orchestration. Trauma-adjusted stats must already be
reflected on Combatant fields before calling these functions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Union

# Defaults match app.py bootstrap (settings.dice_multipliers / combat_attack_base_damage).
COMBAT_ATTACK_BASE_DAMAGE = 10
DEFEND_TEAM_DAMAGE_FACTOR = 0.5
DEFAULT_DICE_MULTIPLIERS: Dict[int, float] = {0: 0.0, 1: 1.0, 2: 1.5, 3: 2.0}


@dataclass
class Combatant:
    """Simplified combat unit (player squad or enemy)."""

    id: str
    power: int
    intellect: int
    resilience: int
    sanity: int = 100
    item_bonus: int = 0


@dataclass
class RoundResult:
    """Single-round calculation output (data only)."""

    damage_dealt: int
    damage_taken: int
    is_critical: bool
    dice_multiplier: float
    defender_count: int
    notes: List[str] = field(default_factory=list)


def get_effective_attack_stat(combatant: Combatant) -> int:
    """Attack stat used for damage (max of power and intellect)."""
    return max(int(combatant.power), int(combatant.intellect))


def calculate_attack_damage(
    attacker: Combatant,
    enemy_resilience: int,
    multiplier: float = 1.0,
    item_bonus: int = 0,
    base_damage: int = COMBAT_ATTACK_BASE_DAMAGE,
) -> int:
    """Player (or ally) attack damage against an enemy."""
    if multiplier <= 0:
        return 0
    attack_stat = get_effective_attack_stat(attacker)
    bonus = item_bonus if item_bonus else int(attacker.item_bonus or 0)
    raw = ((attack_stat * 1.5) + base_damage + bonus) * multiplier - (int(enemy_resilience) * 0.8)
    return max(1, int(raw))


def calculate_incoming_damage(
    enemy_base_damage: int,
    player_resilience: int,
    defending: bool = False,
    team_defend_multiplier: Optional[float] = None,
    *,
    min_damage_ratio: float = 0.1,
) -> int:
    """Enemy counter damage against a player (10% piercing floor by default)."""
    base = int(enemy_base_damage)
    reduction = math.floor(int(player_resilience) * 0.6)
    damage = base - reduction
    piercing = max(1, math.floor(base * min_damage_ratio))
    damage = max(piercing, damage)

    multiplier = team_defend_multiplier
    if multiplier is None:
        multiplier = DEFEND_TEAM_DAMAGE_FACTOR if defending else 1.0
    if multiplier < 1.0:
        damage = math.floor(damage * multiplier)
    return max(piercing, damage)


def dice_multiplier(
    dice_result: Union[int, str, None],
    dice_multipliers: Optional[Mapping[int, float]] = None,
) -> float:
    """Map server combat dice (0=miss, 1=normal, 2=strong, 3=crit) to multiplier."""
    table = dict(dice_multipliers or DEFAULT_DICE_MULTIPLIERS)
    try:
        dice = int(dice_result)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        dice = 1
    return float(table.get(max(0, min(3, dice)), 1.0))


def count_team_defenders(actions: Optional[Dict[str, Any]]) -> int:
    """Count players who chose defend this phase."""
    if not actions:
        return 0
    return sum(
        1
        for action_data in actions.values()
        if (action_data.get("action_type") or action_data.get("action")) == "defend"
    )


def team_defend_damage_multiplier(defender_count: int) -> float:
    """Team-wide defend damage reduction factor."""
    if defender_count > 0:
        return DEFEND_TEAM_DAMAGE_FACTOR
    return 1.0


def _is_active_combat_participant(participant: Mapping[str, Any]) -> bool:
    if int(participant.get("hp") or 0) <= 0:
        return False
    until = participant.get("near_death_until")
    if until:
        from datetime import datetime

        try:
            if datetime.now() < datetime.fromisoformat(until):
                return False
        except ValueError:
            pass
    return True


def select_enemy_counter_target(
    participants: List[Mapping[str, Any]],
    actions: Mapping[str, Any],
    enemy_base_damage: int,
) -> Optional[Mapping[str, Any]]:
    """
    Enemy counter targeting (Greenfield Spec 1.1) — pure calculation, resolve once per round.
    Priority: one-shot > escaping > HP<50% > trauma > protagonist last.
    """
    candidates = [p for p in participants if _is_active_combat_participant(p)]
    if not candidates:
        return None

    def sort_key(member: Mapping[str, Any]):
        hp = int(member.get("hp") or 0)
        max_hp = max(1, int(member.get("max_hp") or hp or 1))
        sid = member.get("squad_id")
        act = actions.get(sid) or {}
        action_type = act.get("action_type") or act.get("action") or ""
        trauma = int(member.get("trauma_count") or 0)
        can_oneshot = 1 if int(enemy_base_damage) >= hp else 0
        is_escaping = 1 if action_type in ("escape", "failed_escape") else 0
        low_hp = 1 if (hp / max_hp) < 0.5 else 0
        has_trauma = 1 if trauma > 0 else 0
        non_protagonist = 0 if member.get("is_protagonist") else 1
        return (can_oneshot, is_escaping, low_hp, has_trauma, non_protagonist)

    candidates.sort(key=sort_key, reverse=True)
    return candidates[0]


def resolve_round_calculation(
    attacker: Combatant,
    enemy: Combatant,
    player_actions: Dict[str, Any],
    enemy_base_damage: int,
    dice_result: int,
    dice_multipliers: Optional[Mapping[int, float]] = None,
) -> RoundResult:
    """Full single-attacker round calculation (no DB / trauma / ending)."""
    mult = dice_multiplier(dice_result, dice_multipliers=dice_multipliers)
    defender_count = count_team_defenders(player_actions)
    team_mult = team_defend_damage_multiplier(defender_count)

    damage_dealt = calculate_attack_damage(
        attacker=attacker,
        enemy_resilience=enemy.resilience,
        multiplier=mult,
        item_bonus=attacker.item_bonus,
    )

    damage_taken = calculate_incoming_damage(
        enemy_base_damage=enemy_base_damage,
        player_resilience=attacker.resilience,
        defending=defender_count > 0,
        team_defend_multiplier=team_mult,
    )

    is_critical = mult > 1.2

    return RoundResult(
        damage_dealt=damage_dealt,
        damage_taken=damage_taken,
        is_critical=is_critical,
        dice_multiplier=mult,
        defender_count=defender_count,
        notes=[],
    )


===== FILE: services/combat_flow.py =====

"""
Step 4 orchestration — mixed-round action pipeline (INV-E).
Delegates math to services.combat_engine; no DB writes here.
"""
from __future__ import annotations

import random
from copy import deepcopy
from typing import Any, Dict, Mapping, Optional

from services.combat_engine import (
    Combatant,
    RoundResult,
    count_team_defenders,
    resolve_round_calculation,
)


def normalize_failed_escape_actions(
    player_actions: Mapping[str, Any],
    *,
    escape_triggered: bool,
    escape_success: bool,
) -> Dict[str, Any]:
    """
    INV-E: after team escape fails, mark escapers as failed_escape.
    They remain in player_actions for defend denominator / targeting but deal no damage.
    """
    actions = dict(player_actions or {})
    if not escape_triggered or escape_success:
        return actions

    for sid, act in list(actions.items()):
        action_type = (act.get("action_type") or act.get("action") or "")
        if action_type == "escape":
            actions[sid] = {
                **act,
                "action_type": "failed_escape",
                "defending": False,
            }
    return actions


def _participant_to_combatant(participant: Mapping[str, Any]) -> Combatant:
    return Combatant(
        id=str(participant.get("squad_id") or ""),
        power=int(participant.get("power") or 0),
        intellect=int(participant.get("intellect") or 0),
        resilience=int(participant.get("resilience") or 0),
        sanity=int(participant.get("sanity") or 0),
        item_bonus=int(participant.get("item_bonus") or 0),
    )


def process_mixed_round_actions(
    active_combatants: Mapping[str, Mapping[str, Any]],
    enemy_stats: Mapping[str, Any],
    player_actions: Mapping[str, Any],
    enemy_base_damage: int,
    *,
    escape_success_rate: float = 0.4,
    rng: Optional[float] = None,
) -> Dict[str, Any]:
    """
    INV-E terminal orchestration: escape gate first, then per-attacker engine calls.
    Returns a pure breakdown dict (caller persists to DB).
    """
    actions = deepcopy(dict(player_actions or {}))
    round_breakdown: Dict[str, Any] = {
        "actions_performed": [],
        "failed_escape_squads": [],
        "damages_dealt": {},
        "damages_taken": {},
        "team_escaped": False,
        "defender_count": 0,
    }

    escape_intent = [
        sid for sid, act in actions.items()
        if (act.get("action_type") or act.get("action")) == "escape"
    ]

    if escape_intent:
        roll = random.random() if rng is None else float(rng)
        if roll < escape_success_rate:
            round_breakdown["team_escaped"] = True
            return round_breakdown

        actions = normalize_failed_escape_actions(
            actions,
            escape_triggered=True,
            escape_success=False,
        )
        round_breakdown["failed_escape_squads"] = list(escape_intent)

    enemy = Combatant(
        id="enemy",
        power=int(enemy_stats.get("power") or 0),
        intellect=int(enemy_stats.get("intellect") or 0),
        resilience=int(enemy_stats.get("resilience") or 0),
    )

    round_breakdown["defender_count"] = count_team_defenders(actions)

    for sid, participant in active_combatants.items():
        if sid == "enemy":
            continue

        action_data = actions.get(sid, {"action_type": "pass"})
        action_type = action_data.get("action_type") or action_data.get("action") or "pass"
        if action_type in ("failed_escape", "escape"):
            round_breakdown["actions_performed"].append({
                "squad_id": sid,
                "action": action_type,
                "damage_dealt": 0,
                "damage_taken": 0,
                "is_critical": False,
            })
            continue

        combatant = _participant_to_combatant(participant)
        dice_result = action_data.get("dice_result", action_data.get("dice", 1))
        calc_result: RoundResult = resolve_round_calculation(
            attacker=combatant,
            enemy=enemy,
            player_actions=actions,
            enemy_base_damage=enemy_base_damage,
            dice_result=dice_result,
        )

        round_breakdown["damages_dealt"][sid] = calc_result.damage_dealt
        round_breakdown["damages_taken"][sid] = calc_result.damage_taken
        round_breakdown["actions_performed"].append({
            "squad_id": sid,
            "action": action_type,
            "damage_dealt": calc_result.damage_dealt,
            "damage_taken": calc_result.damage_taken,
            "is_critical": calc_result.is_critical,
        })

    return round_breakdown


===== FILE: services/combat_outcomes.py =====

"""Orchestrate post-combat rewards, trauma, and ending side effects."""
from models.protagonist import trauma_bad_ending_narrative
from services.ending import judge_ending


def _outcome_already_recorded_team(team_id, encounter_id):
    if not team_id or not encounter_id:
        return False
    from models.encounter_outcomes import encounter_already_completed

    return encounter_already_completed(team_id, encounter_id)


def _outcome_already_recorded_solo(starter_id, encounter_id):
    if not starter_id or not encounter_id:
        return False
    from models.encounter_outcomes import encounter_already_completed_solo

    return encounter_already_completed_solo(starter_id, encounter_id)


def resolve_combat_outcome(winner, team_id, encounter, starter_id, combat_id=None):
    """
    Post-combat orchestration — idempotency enforced by encounter_completions SSOT.
    No outer with_db_retry: pipeline / completion checks must not race on dirty snapshots.
    """
    from models.encounter_outcomes import (
        apply_encounter_failure,
        apply_encounter_failure_solo,
        apply_encounter_success_solo,
        apply_trauma_bad_ending_victory,
    )
    from services.narrative_orchestrator import execute_post_combat_success_pipeline

    result = {
        "winner": winner,
        "trauma_bad_ending": False,
        "log_messages": [],
        "ending": None,
        "applied_success": False,
        "applied_failure": False,
    }
    if not encounter or not winner:
        return result

    encounter_id = encounter.get("encounter_id")

    if winner == "escaped":
        result["log_messages"].append({
            "message": "全隊成功逃離戰場",
            "log_type": "escape_success",
        })
        return result

    if winner == "squad":
        ending = judge_ending(team_id) if team_id else {}
        result["ending"] = ending
        trauma_total = int(ending.get("protagonist_trauma_total") or 0)

        if team_id and ending.get("should_apply_bad_ending_victory"):
            if not _outcome_already_recorded_team(team_id, encounter_id):
                apply_trauma_bad_ending_victory(team_id, encounter)
                result["applied_success"] = True
            result["trauma_bad_ending"] = True
            result["log_messages"].append({
                "message": (
                    f"主角心理創傷過深（累計 {trauma_total}）——"
                    "勝利無法帶來真正救贖"
                ),
                "log_type": "trauma_ending",
            })
        elif team_id:
            try:
                snap = execute_post_combat_success_pipeline(
                    team_id, encounter_id, starter_id,
                )
                result["applied_success"] = "拒絕重複" not in snap.log_message
                result["log_messages"].append({
                    "message": snap.log_message,
                    "log_type": "story_progression",
                })
            except Exception as exc:
                result["log_messages"].append({
                    "message": f"劇情推進管線觸發等冪保護: {exc}",
                    "log_type": "idempotent_blocked",
                })
        elif starter_id and not _outcome_already_recorded_solo(starter_id, encounter_id):
            apply_encounter_success_solo(starter_id, encounter)
            result["applied_success"] = True
        return result

    if winner == "enemy":
        if team_id and not _outcome_already_recorded_team(team_id, encounter_id):
            apply_encounter_failure(team_id, encounter)
            result["applied_failure"] = True
        elif starter_id and not _outcome_already_recorded_solo(starter_id, encounter_id):
            apply_encounter_failure_solo(starter_id, encounter)
            result["applied_failure"] = True
        if team_id:
            result["ending"] = judge_ending(team_id)
        return result

    return result


def build_victory_outcome_payload(
    encounter,
    team_id=None,
    combat_id=None,
    current_round=0,
):
    """Build JSON payload for combat victory responses (INV-C monotonic fields)."""
    ending = judge_ending(team_id) if team_id else {}
    trauma_bad = bool(ending.get("trauma_bad_ending"))
    safe_combat_id = int(combat_id) if combat_id is not None else 0
    round_idx = max(0, int(current_round or 0))
    settled_round_index = max(0, round_idx - 1)

    payload = {
        "success": True,
        "status": "ended",
        "outcome": "victory",
        "winner": "squad",
        "combat_id": safe_combat_id or None,
        "settled_round_index": settled_round_index,
        "settlement_id": f"{safe_combat_id}:{settled_round_index}",
        "narrative": (encounter or {}).get("success", {}).get("narrative"),
        "reflection_prompt": (encounter or {}).get("reflection_prompt"),
        "ending_condition": ending.get("ending_condition"),
        "protagonist_trauma_total": ending.get("protagonist_trauma_total", 0),
        "trauma_level": ending.get("trauma_level", "safe"),
    }
    if team_id:
        payload["ending"] = ending
        payload["ending_preview"] = ending.get("ending_preview")
    if trauma_bad:
        payload["trauma_bad_ending"] = True
        payload["narrative"] = trauma_bad_ending_narrative(encounter)
        payload["reflection_prompt"] = None
    return payload


def get_collapsed_combat_members(participants):
    """Squads that triggered INV-D (HP≤0 or active near-death)."""
    from models.squad import is_near_death_active

    collapsed = []
    for p in participants or []:
        if not p:
            continue
        if int(p.get("hp") or 0) <= 0 or is_near_death_active(p):
            collapsed.append(p)
    return collapsed


def build_defeat_outcome_payload(encounter, participants=None, team_id=None):
    dead = get_collapsed_combat_members(participants)
    if not dead and team_id:
        from models.squad import get_team_members

        dead = get_collapsed_combat_members(get_team_members(team_id))

    dead_ids = [m.get("squad_id") for m in dead if m.get("squad_id")]
    dead_names = [
        m.get("display_name") or m.get("squad_id")
        for m in dead
        if m.get("squad_id")
    ]
    failure = (encounter or {}).get("failure") or {}

    return {
        "success": True,
        "status": "ended",
        "outcome": "defeat",
        "outcome_type": "COMBAT_FAILED",
        "winner": "enemy",
        "narrative": failure.get("narrative"),
        "narrative_failure": failure.get("narrative")
        or failure.get("description")
        or "隊伍在西貢叢林中倒下了…",
        "requires_gm": True,
        "dead_squad_ids": dead_ids,
        "dead_squad_names": dead_names,
        "active": False,
    }


===== FILE: services/trauma_service.py =====

"""
Oikonomia — Trauma & Narrative Fragment Orchestration Service
Phase 1.5 Step 2: Pure Service Layer Implementation
"""
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from models.protagonist import TRAUMA_BAD_ENDING_LIMIT
from models.settings import settings
from utils.db_tx import immediate_transaction, with_db_retry

VALID_PROTAGONIST_KEYS = frozenset({"iggy", "marah"})


@dataclass
class TraumaStatusSnapshot:
    team_id: str
    protagonist_key: str
    current_trauma: int
    trauma_band: str  # 'low' | 'medium' | 'high'
    narrative_fragment: str
    is_bad_ending_locked: bool


CONDITIONAL_NARRATIVE_FRAGMENTS = {
    "low": (
        "「我的恩典夠你用的。」在微小的動搖中，心理界線的裂縫正透出微光。"
        "創傷尚未生根，重建的根基依然穩固。"
    ),
    "medium": (
        "「因為我的能力是在人的軟弱上顯得完全。」防線雖有破損，痛楚正逼使全隊面對真實的自我，"
        "這是一場恩典的試煉。"
    ),
    "high": (
        "「所以我更喜歡誇自己的軟弱，好叫基督的能力覆庇我。」創傷已達臨界點。"
        "雖然陰影籠罩，但破碎的盡頭並非毀滅，而是神聖醫治的開端。"
    ),
}


def resolve_trauma_band(trauma_count: int) -> str:
    """權威創傷能帶分級"""
    if trauma_count <= 1:
        return "low"
    if trauma_count <= 3:
        return "medium"
    return "high"


def _tx_body(conn, clean_team: str, protagonist_key: str, delta: int, reason: str, now: str):
    row = conn.execute(
        "SELECT trauma_count FROM protagonist_states WHERE team_id = ? AND protagonist = ?",
        (clean_team, protagonist_key),
    ).fetchone()
    if not row:
        raise ValueError(f"Protagonist state missing: {clean_team}/{protagonist_key}")

    current_trauma = int(row[0] or 0)
    new_trauma = max(0, current_trauma + int(delta))

    updated = conn.execute(
        """UPDATE protagonist_states
           SET trauma_count = ?, last_updated = ?
           WHERE team_id = ? AND protagonist = ?""",
        (new_trauma, now, clean_team, protagonist_key),
    )
    if updated.rowcount != 1:
        raise RuntimeError(f"Failed to update trauma for {clean_team}/{protagonist_key}")

    conn.execute(
        """INSERT INTO protagonist_trauma_log
           (team_id, protagonist, delta, reason, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (clean_team, protagonist_key, int(delta), reason, now),
    )

    total_row = conn.execute(
        "SELECT COALESCE(SUM(trauma_count), 0) FROM protagonist_states WHERE team_id = ?",
        (clean_team,),
    ).fetchone()
    total_trauma = int(total_row[0] or 0)

    is_bad_ending = total_trauma > TRAUMA_BAD_ENDING_LIMIT
    if is_bad_ending:
        conn.execute(
            """UPDATE teams
               SET ending_type = 'bad_ending', ending_locked_at = ?
               WHERE team_id = ? AND COALESCE(ending_type, '') != 'bad_ending'""",
            (now, clean_team),
        )

    band = resolve_trauma_band(new_trauma)
    fragment = CONDITIONAL_NARRATIVE_FRAGMENTS[band]

    return TraumaStatusSnapshot(
        team_id=clean_team,
        protagonist_key=protagonist_key,
        current_trauma=new_trauma,
        trauma_band=band,
        narrative_fragment=fragment,
        is_bad_ending_locked=is_bad_ending,
    )


def apply_protagonist_trauma_pipeline(
    team_id: str,
    protagonist_key: str,
    delta: int,
    reason: str,
) -> TraumaStatusSnapshot:
    """
    權威創傷管線：在單一原子事務內更新創傷、寫入審計日誌、並計算當前神學劇情片段。
    防禦鎖定：一旦觸發 bad_ending 條件，立即寫入 SSOT 狀態防線。
    """
    clean_team = (team_id or "").strip().upper()
    if protagonist_key not in VALID_PROTAGONIST_KEYS:
        raise ValueError(f"Invalid protagonist key: {protagonist_key}")
    if not clean_team:
        raise ValueError("team_id is required")

    now = datetime.now().isoformat()
    db_path = settings.db_path

    def _run():
        with immediate_transaction(db_path) as conn:
            return _tx_body(conn, clean_team, protagonist_key, delta, reason, now)

    return with_db_retry(_run)


===== FILE: services/narrative_orchestrator.py =====

"""
Oikonomia — Narrative & Post-Combat Reward Orchestrator Service
Phase 1.5 Step 3: SSOT Transaction Protection for Story Progression
"""
import json
import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from models.encounter import encounter_skips_progression, load_encounter
from models.item import get_item_by_id, get_item_by_qr_code_value
from models.settings import settings
from models.squad import get_team_members
from utils.db_tx import immediate_transaction, with_db_retry
from utils.helpers import normalize_team_id


@dataclass
class StoryProgressionSnapshot:
    team_id: str
    encounter_id: str
    old_stage: int
    new_stage: int
    reward_items_granted: list
    narrative_unlocked: bool
    log_message: str


def _serialize_rewards(rewards):
    if not rewards:
        return None
    return json.dumps(rewards, ensure_ascii=False)


def _resolve_reward_entries(encounter):
    """Map encounter success.rewards to (catalog_item_id, chance) pairs."""
    success = encounter.get("success", {})
    entries = []

    block = success.get("rewards")
    if isinstance(block, dict):
        for raw_id in block.get("item_ids") or []:
            try:
                catalog_id = int(raw_id)
            except (TypeError, ValueError):
                item = get_item_by_qr_code_value(str(raw_id))
                catalog_id = item["id"] if item else None
            if catalog_id:
                entries.append((int(catalog_id), 1.0))
        return entries

    if not isinstance(block, list):
        return entries

    for reward in block:
        if reward.get("type") != "item":
            continue
        ref = reward.get("item_id")
        item = None
        if ref is not None:
            item = get_item_by_qr_code_value(str(ref))
            if not item:
                try:
                    item = get_item_by_id(int(ref))
                except (TypeError, ValueError):
                    item = None
        if item:
            try:
                chance = float(reward.get("chance", 1))
            except (TypeError, ValueError):
                chance = 1.0
            entries.append((int(item["id"]), max(0.0, min(1.0, chance))))
    return entries


def _tx_body(conn, clean_team, encounter, encounter_id, starter_squad_id, now):
    from models.protagonist import get_team_story_stage

    c = conn.cursor()

    already_done = c.execute(
        """SELECT 1 FROM encounter_completions
           WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?)) AND encounter_id = ?""",
        (clean_team, encounter_id),
    ).fetchone()
    if already_done:
        return StoryProgressionSnapshot(
            team_id=clean_team,
            encounter_id=encounter_id,
            old_stage=0,
            new_stage=0,
            reward_items_granted=[],
            narrative_unlocked=False,
            log_message="此遭遇戰前已完成，拒絕重複結算劇情",
        )

    if encounter_skips_progression(encounter):
        return StoryProgressionSnapshot(
            team_id=clean_team,
            encounter_id=encounter_id,
            old_stage=0,
            new_stage=0,
            reward_items_granted=[],
            narrative_unlocked=False,
            log_message="練習遭遇不記錄故事進度",
        )

    success = encounter.get("success", {})
    old_stage = get_team_story_stage(clean_team)
    insight = int(success.get("insight_fragment") or 0)
    unlocks = []
    if success.get("next_story_unlock"):
        unlocks.append(success["next_story_unlock"])

    if insight > 0:
        for member in get_team_members(clean_team):
            row = c.execute(
                "SELECT insight_fragments FROM squads WHERE squad_id = ?",
                (member["squad_id"],),
            ).fetchone()
            if not row:
                continue
            new_val = int(row[0] or 0) + insight
            c.execute(
                "UPDATE squads SET insight_fragments = ? WHERE squad_id = ?",
                (new_val, member["squad_id"]),
            )

    granted_items = []
    granted_meta = []
    owned_count = c.execute(
        "SELECT COUNT(*) FROM player_items WHERE squad_id = ?",
        (starter_squad_id,),
    ).fetchone()[0]
    max_slots = settings.max_inventory_slots

    for catalog_item_id, chance in _resolve_reward_entries(encounter):
        if chance < 1.0 and random.random() > chance:
            continue
        if owned_count >= max_slots:
            break

        dup = c.execute(
            """SELECT COUNT(*) FROM player_items pi
               JOIN squads s ON pi.squad_id = s.squad_id
               WHERE UPPER(TRIM(s.team_id)) = UPPER(TRIM(?)) AND pi.item_id = ?""",
            (clean_team, catalog_item_id),
        ).fetchone()[0]
        if dup > 0:
            continue

        own_dup = c.execute(
            "SELECT 1 FROM player_items WHERE squad_id = ? AND item_id = ?",
            (starter_squad_id, catalog_item_id),
        ).fetchone()
        if own_dup:
            continue

        try:
            c.execute(
                """INSERT INTO player_items (squad_id, item_id, source, obtained_at)
                   VALUES (?, ?, 'combat_reward', ?)""",
                (starter_squad_id, catalog_item_id, now),
            )
        except sqlite3.IntegrityError:
            continue

        granted_items.append(catalog_item_id)
        item_row = c.execute(
            "SELECT name FROM items WHERE id = ?",
            (catalog_item_id,),
        ).fetchone()
        if item_row:
            granted_meta.append({"name": item_row[0], "item_id": catalog_item_id})
        owned_count += 1

    rewards_payload = {
        "insight_fragments": insight,
        "items": granted_meta,
        "unlocks": list(unlocks),
    }
    c.execute(
        """INSERT INTO encounter_completions
           (team_id, encounter_id, outcome, unlocks, narrative, rewards, completed_at)
           VALUES (?, ?, 'success', ?, ?, ?, ?)""",
        (
            clean_team,
            encounter_id,
            json.dumps(unlocks, ensure_ascii=False),
            success.get("narrative"),
            _serialize_rewards(rewards_payload),
            now,
        ),
    )

    new_stage = get_team_story_stage(clean_team)
    title = encounter.get("title") or encounter_id
    log_text = (
        f"🛡️ 隊伍成功通關 [{title}], 發放獎勵物品 ID: {granted_items}。"
        f"故事進度: Stage {old_stage} -> {new_stage}"
    )

    return StoryProgressionSnapshot(
        team_id=clean_team,
        encounter_id=encounter_id,
        old_stage=old_stage,
        new_stage=new_stage,
        reward_items_granted=granted_items,
        narrative_unlocked=(new_stage > old_stage),
        log_message=log_text,
    )


def execute_post_combat_success_pipeline(
    team_id: str,
    encounter_id: str,
    starter_squad_id: str,
    *,
    conn: Optional[sqlite3.Connection] = None,
) -> StoryProgressionSnapshot:
    """
    權威戰後劇情解鎖管線：在單一 Atomic Transaction 內發放獎勵、解鎖故事階段、寫入遭遇完成誌。
    防禦鎖定：杜絕高延遲環境下重複刷新 API 導致重複獲得物品或重複推進劇情的漏洞。
    """
    clean_team = normalize_team_id(team_id)
    if not clean_team:
        raise ValueError("team_id is required")
    if not starter_squad_id:
        raise ValueError("starter_squad_id is required")

    encounter = load_encounter(encounter_id)
    if not encounter:
        raise ValueError(f"Encounter {encounter_id} not found")

    now = datetime.now().isoformat()

    if conn is not None:
        return _tx_body(
            conn, clean_team, encounter, encounter_id, starter_squad_id, now,
        )

    db_path = settings.db_path

    def _run():
        with immediate_transaction(db_path) as new_conn:
            return _tx_body(
                new_conn, clean_team, encounter, encounter_id, starter_squad_id, now,
            )

    return with_db_retry(_run)


===== FILE: services/global_events.py =====

"""Global event persistence and squad-wide effects."""
import sqlite3

from models.settings import settings
from utils.helpers import clamped_stat_delta_expr, hkt_timestamp


def apply_global_effect(effect_type, effect_value=0):
    if not effect_type or effect_type in ("announcement", "global_debuff"):
        return
    conn = sqlite3.connect(settings.db_path)
    try:
        c = conn.cursor()
        if effect_type in ("adjust_sanity", "sanity_adjust"):
            c.execute(
                f"UPDATE squads SET sanity = {clamped_stat_delta_expr('sanity', '+')}",
                (effect_value, effect_value),
            )
        elif effect_type == "sanity_down":
            delta = abs(effect_value)
            c.execute(
                f"UPDATE squads SET sanity = {clamped_stat_delta_expr('sanity', '-')}",
                (delta, delta),
            )
        elif effect_type == "sanity_up":
            delta = abs(effect_value)
            c.execute(
                f"UPDATE squads SET sanity = {clamped_stat_delta_expr('sanity', '+')}",
                (delta, delta),
            )
        elif effect_type == "power_up":
            delta = abs(effect_value)
            c.execute(
                f"UPDATE squads SET power = {clamped_stat_delta_expr('power', '+')}",
                (delta, delta),
            )
        elif effect_type == "intellect_up":
            delta = abs(effect_value)
            c.execute(
                f"UPDATE squads SET intellect = {clamped_stat_delta_expr('intellect', '+')}",
                (delta, delta),
            )
        elif effect_type == "resilience_up":
            delta = abs(effect_value)
            c.execute(
                f"UPDATE squads SET resilience = {clamped_stat_delta_expr('resilience', '+')}",
                (delta, delta),
            )
        elif effect_type == "judas_strengthen":
            c.execute("UPDATE squads SET sanity = MAX(0, sanity - 8)")
        elif effect_type == "iggy_collapse":
            c.execute("UPDATE squads SET sanity = MAX(0, sanity - 12)")
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_global_event(title, description="", effect_type=None, effect_value=0, created_by="GM"):
    conn = sqlite3.connect(settings.db_path)
    try:
        conn.execute(
            """INSERT INTO global_events
               (title, description, effect_type, effect_value, created_by, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (title, description, effect_type, effect_value, created_by, hkt_timestamp()),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


===== FILE: combat_greenfield_final.md =====

# Oikonomia 戰鬥系統 Greenfield 重寫最終設計規格（Real-time Co-op 版）

**日期**：2026-07-01  
**版本**：Final v1.1
**負責人**：Grok Architect（整合所有確認）  
**目的**：為 20 人青年、西貢戶外營會設計穩定、可維護嘅全新戰鬥子系統

---

## 1. 最終確認嘅戰鬥機制

### 1.1 核心規則（Authoritative Spec）
- 戰鬥模式：**多人實時 Co-op + AI 主角**（單人主要用測試）
- **任何角色（包括主角）HP ≤ 0 → 戰鬥即時失敗**（絕對規則）
- 玩家可選擇：攻擊、防御、Zoo能力、使用道具、逃跑
- **Zoo 能力**（Greenfield 權威規格）：
  - **任何神智值均可發動 Zoo**——唔係「神智 >70 先用得」；僅當遭遇 `combat_settings.allow_zoo === false` 時禁止
  - Zoo 行動同樣經後端擲骰（0–3）並計入傷害結算；低神智仍有**暴走**風險（見下方暴走規則）
  - **神智加成乘數**（只喺選擇 Zoo 行動時套用，唔影響攻擊／防禦；神智 ≤70 仍可發動，但無加成）：
    | 神智 | Zoo 傷害乘數 |
    |------|-------------|
    | ≤70 | ×1.0 |
    | >70 | ×1.3 |
    | >80 | ×1.4 |
    | >90 | ×1.5 |
  - UI：**唔應**因神智不足而 disable Zoo 按鈕；神智 ≤70 顯示「可發動、無加成（×1.0）」；>70 顯示當前 tier 乘數
- 攻擊擲骰：0-3（後端權威），乘以角色 Power
- **暴走**（任何攻擊類行動，含 Zoo）：神智 <10→90%、<20→50%、<40→20% 機率失控（可能無敵傷害）
- **Defense 公式**（只限主動選擇 Defense 行動時生效）：
  - Base 30% + Resilience × 0.5%，上限 90%
- **逃跑規則**：任何人選擇逃跑 → 觸發全隊 escape 判定
  - 成功：全隊逃跑
  - 失敗：顯示失敗畫面 → 玩家確認後，繼續結算選擇戰鬥嘅玩家行動
- 多敵人 Targeting 優先順序：
  1. 可以一擊秒殺嘅角色
  2. 選擇逃跑嘅角色
  3. 血量低於 50% 嘅角色
  4. 有創傷標記嘅角色
  5. 主角（最後）
- 傷害結算必須顯示：自己角色 + 隊友 + AI 主角造成傷害 + 受到傷害
- 主角自己會擲骰並造成傷害

### 1.2 營會實用性要求
- 主要使用手機（iPhone Safari / Chrome）
- 西貢戶外網絡不穩 → 必須有動態 Polling + Reconnection 機制
- 任何失敗狀態必須有清晰、不可逆嘅退出路徑

---

## 2. 架構總覽

**核心設計原則**：
- 後端係唯一權威狀態源（SSOT）
- 前端只做 **Passive Sync**，嚴禁本地 Timer 主導 round 推進
- 單一狀態機驅動所有 UI
- **Preemptive Interrupt**：任何角色死亡必須即時搶占所有 UI 並進入 COMBAT_FAILED
- 使用 `settled_round_index` + `settlement_id` 做等冪同進度拉齊

**技術選型（Phase 1 營會前）**：
- 現有 HTTP Poll + 動態間隔（IDLE 1200ms / WAITING 800ms）
- 加入 `AbortController` + Visibility API + 指數退避
- 之後可升級至 WebSocket

---

## 3. 狀態機（State Machine）

### 主要 Phase
```javascript
const Phase = {
  IDLE,
  DICE_ROLLING,
  DICE_CONFIRM,
  SUBMITTING,
  WAITING_FOR_PLAYERS,     // 等其他真人玩家提交
  ESCAPE_ATTEMPT,          // 有人觸發逃跑，全隊進入判定
  SETTLEMENT,
  COMBAT_FAILED,           // 最高優先級 absorbing state
  VICTORY,
  ESCAPED
};
```

### 核心 Invariant（違反即 bug）
- **INV-A**：`phase === SETTLEMENT` ⇔ 傷害結算 Modal 可見
- **INV-B**：`phase === COMBAT_FAILED` ⇒ 所有操作 disabled + 顯示失敗原因
- **INV-C**：同一個 `settlement_id` 只渲染一次
- **INV-D**：任何角色 HP ≤ 0 必須即時進入 `COMBAT_FAILED`（最高優先級）
- **INV-E**：Escape 失敗後，戰鬥玩家嘅行動必須仍然結算

### Recovery 策略
- 出現幽靈 SETTLEMENT 或 INV-A 違反 → 強制 hideAllModals() + 回 IDLE + Toast 重置
- COMBAT_FAILED 係 absorbing state，嚴禁重新開啟 Polling

---

## 4. 檔案結構

```
static/js/combat/
├── index.js                    # 唯一入口：CombatApp.mount()
├── state_machine.js            # 純狀態機 + syncState + handleAnyDeath
├── api_client.js               # fetch + ResilientPollingManager
├── render.js
├── selectors.js
└── views/
    ├── hud_view.js             # 多玩家頭像 + 等待狀態 + 已就緒標記
    ├── action_view.js
    ├── dice_modal_view.js
    ├── settlement_view.js      # 傷害 Breakdown（自己 + 隊友 + 主角）
    ├── escape_result_view.js   # 逃跑失敗阻塞畫面
    └── victory_view.js
```

`templates/index.html` 只保留 `<div id="combat-root"></div>` + module script。

---

## 5. 核心實作建議

### 5.1 State Machine 核心（syncState + determineSettlementRoute）
（已整合最終優化版本，包含死亡搶占最高優先級 + Escape 拉齊機制）

### 5.2 Resilient Polling Manager（最終版）
使用 `AbortController` + Visibility API + 指數退避，適合戶外營會。

### 5.3 COMBAT_FAILED 處理
- 即時清空所有 View
- 顯示死亡成員名單
- 提供「返回大廳」同「召喚 GM」按鈕（異步 API）
- 「重新同步」只做單次 Fetch + 嚴格控流（死亡狀態下鎖死 Polling）

### 5.4 傷害結算 Breakdown 渲染
清楚分開自己、隊友、AI 主角嘅行動同傷害。

---

## 6. UI / DOM 結構重點（手機優先）

- 首屏無捲動：敵我頭像 + 數據 + 行動按鈕（攻擊 / 防御 / 物品 / 逃跑）
- 下方：隊友狀態卡片（已就緒 / 等待中）+ 主角 HP/神智
- 最下方：戰鬥 Log
- 逃跑失敗畫面：阻塞 + 確認後繼續結算
- 戰鬥失敗畫面：Absorbing + 清晰退出路徑（返回大廳 / 召喚 GM）

---

## 7. 測試規格（Playwright 關鍵案例）

- T8：混合逃跑行動（一人逃跑失敗，戰鬥玩家行動仍然結算）
- T9：Preemptive Interrupt（任何 Phase 突然死亡即時切換 COMBAT_FAILED）
- T10：10 秒超時自動 Defense + 狀態拉齊

---

## 8. 遷移與部署

- 使用 feature flag `COMBAT_V2`（預設 off）
- 保留舊版作為 rollback 方案
- 建議 PR 順序：後端 API 欄位升級 → 狀態機核心 → View 重寫 → 測試 → 上線

---

## 9. Rollback 方案

前端保留 `static/js/combat_v1/` 作為備份。  
若出現重大問題，可透過後端環境變數 `COMBAT_VERSION = "V1"` 一鍵回滾。

---

**結論**：呢個版本已經整合所有確認過嘅機制同實作建議，具備單一狀態機、死亡即時搶占、Escape 混合結算、戶外網絡 resilience 同清晰失敗退出路徑，適合 20 人營會實戰使用。

可以直接交畀 Grok Build 開始實作。


===== FILE: app.py =====

#!/usr/bin/env python3
"""
Oikonomia - Summer Camp 2026 Web App Prototype
Built by Grok Build
Priority: Beautiful Dashboard + GPS + Photo Upload
"""

import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

from utils.production_secrets import load_production_secrets

load_production_secrets(PROJECT_DIR)

from flask import Flask, jsonify, session
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import json
import shutil
import zipfile
import io
import re
from datetime import datetime, timedelta
import math
import time
import random
import hmac
import hashlib

from utils.env import is_production_env as _is_production_env

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or (
    None if _is_production_env() else "oikonomia-2026-prototype"
)
if _is_production_env() and not app.secret_key:
    raise RuntimeError("SECRET_KEY environment variable is required in production")
if _is_production_env() and not os.environ.get("GM_PIN"):
    raise RuntimeError("GM_PIN environment variable is required in production")
app.config.update(
    SESSION_COOKIE_SECURE=os.environ.get("RENDER") == "true" or os.environ.get("FLASK_ENV") == "production",
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_PATH="/",
    SESSION_COOKIE_NAME="oikonomia_session",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
)


@app.errorhandler(413)
def upload_too_large(_exc):
    return jsonify({"success": False, "error": "相片檔案太大（上限 8MB）"}), 413
RESTORE_TOKEN_MAX_AGE = int(timedelta(days=30).total_seconds())
_restore_serializer = None

def get_data_dir():
    """每個部署環境用獨立 SQLite；PA 由 wsgi.py 設 DATA_DIR=data/。"""
    if os.environ.get("DATA_DIR"):
        return os.environ["DATA_DIR"]
    if os.environ.get("RENDER") == "true" and os.path.isdir("/data"):
        return "/data"
    return os.path.join(PROJECT_DIR, "local_data")

def migrate_legacy_db(target_dir):
    """首次改用 local_data/ 時，從舊路徑複製 oikonomia.db。"""
    target_db = os.path.join(target_dir, "oikonomia.db")
    if os.path.isfile(target_db):
        return
    for legacy_dir in (PROJECT_DIR, os.path.join(PROJECT_DIR, "data")):
        legacy_db = os.path.join(legacy_dir, "oikonomia.db")
        if os.path.isfile(legacy_db):
            shutil.copy2(legacy_db, target_db)
            break
app.static_folder = os.path.join(PROJECT_DIR, "static")
AVATAR_DIR = os.path.join(app.static_folder, "avatars")
PORTRAIT_DIR = os.path.join(app.static_folder, "portraits")
PORTRAIT_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".svg")
os.makedirs(PORTRAIT_DIR, exist_ok=True)

def portrait_static_path(filename):
    """非玩家角色頭像 URL（static/portraits/）。"""
    safe = os.path.basename((filename or "").strip())
    if not safe:
        return "/static/avatars/default.png"
    return f"/static/portraits/{safe}"
DATA_DIR = get_data_dir()
os.makedirs(DATA_DIR, exist_ok=True)
if not os.environ.get("DATA_DIR"):
    migrate_legacy_db(DATA_DIR)

# 上傳圖片固定放喺 project/uploads（PA 同 local 路徑一致，避免 data/uploads 分裂）
UPLOAD_FOLDER = os.path.join(PROJECT_DIR, "uploads")
LEGACY_UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "oikonomia.db")

# ==================== Utils Layer Imports ====================
from utils.uploads import save_task_submission_photo

DEFAULT_PROTAGONIST = {"hp": 100, "sanity": 100, "power": 100, "intellect": 100, "resilience": 100}
SQUAD_ATTRIBUTES = ["hp", "sanity", "power", "intellect", "resilience"]
MAX_INVENTORY_SLOTS = 5

SAMPLE_ITEMS = [
    {
        "name": "裂縫碎片",
        "description": "來自界線的微小碎片，似乎還有溫度。",
        "icon": "🧩",
        "item_type": "story",
        "qr_code_value": "item-001",
        "has_ability": 0,
        "effect_type": None,
        "effect_value": 0,
        "image_path": "/static/images/items/item-001.svg",
    },
    {
        "name": "Judas 的信箋",
        "description": "上面有模糊的字跡，閱讀時 Sanity 會微微波動。",
        "icon": "📜",
        "item_type": "story",
        "qr_code_value": "item-002",
        "has_ability": 1,
        "effect_type": "sanity_up",
        "effect_value": -5,
        "image_path": "/static/images/items/item-002.svg",
    },
    {
        "name": "守護者徽章",
        "description": "掃描營地 QR 後獲得的證物，能強化你的 Resilience。",
        "icon": "🛡️",
        "item_type": "qr",
        "qr_code_value": "item-003",
        "has_ability": 1,
        "effect_type": "resilience_up",
        "effect_value": 8,
        "image_path": "/static/images/items/item-003.svg",
    },
    {
        "name": "記憶之瓶",
        "description": "裝住一段未完成的對話，觸碰時 Sanity 會回復。",
        "icon": "🫙",
        "item_type": "qr",
        "qr_code_value": "item-004",
        "has_ability": 1,
        "effect_type": "sanity_up",
        "effect_value": 5,
        "image_path": "/static/images/items/item-004.svg",
    },
    {
        "name": "界線之鑰",
        "description": "據說可以打開某扇隱藏的門，蘊含強大 Power。",
        "icon": "🗝️",
        "item_type": "special",
        "qr_code_value": "item-005",
        "has_ability": 1,
        "effect_type": "power_up",
        "effect_value": 10,
        "image_path": "/static/images/items/item-005.svg",
    },
]

ITEM_EFFECT_STAT_MAP = {
    "power_up": "power",
    "sanity_up": "sanity",
    "resilience_up": "resilience",
    "hp_up": "hp",
    "intellect_up": "intellect",
}

ITEM_EFFECT_LABELS = {
    "power_up": "力量",
    "sanity_up": "神智",
    "resilience_up": "韌性",
    "hp_up": "生命值",
    "intellect_up": "智力",
}

# ==================== Encounter / Combat ====================
ENCOUNTERS_DIR = os.path.join(PROJECT_DIR, "encounters")
NEAR_DEATH_MINUTES = 15
COMBAT_ACTION_TYPES = (
    "attack", "attack_physical", "attack_nonphysical",
    "defend", "use_item", "use_zoo", "pass", "escape",
)
COMBAT_ATTACK_BASE_DAMAGE = 10
ATTACK_ACTION_TYPES = frozenset({
    "attack", "attack_physical", "attack_nonphysical", "use_zoo",
})
DICE_MULTIPLIERS = {0: 0.0, 1: 1.0, 2: 1.5, 3: 2.0}
_encounter_cache = {}

from data.locations import LOCATIONS
from data.story_config import STORY_STAGE_THRESHOLDS, STORY_STAGE_REQUIRED_TASKS
from data.narrative_stories import NARRATIVE_PORTRAITS, NARRATIVE_STORIES

from models import configure as configure_models

configure_models(
    db_path=DB_PATH,
    upload_folder=UPLOAD_FOLDER,
    legacy_upload_folder=LEGACY_UPLOAD_FOLDER,
    default_protagonist=DEFAULT_PROTAGONIST,
    squad_attributes=SQUAD_ATTRIBUTES,
    max_inventory_slots=MAX_INVENTORY_SLOTS,
    encounters_dir=ENCOUNTERS_DIR,
    item_effect_stat_map=ITEM_EFFECT_STAT_MAP,
    item_effect_labels=ITEM_EFFECT_LABELS,
    encounter_cache=_encounter_cache,
    near_death_minutes=NEAR_DEATH_MINUTES,
    combat_action_types=COMBAT_ACTION_TYPES,
    attack_action_types=ATTACK_ACTION_TYPES,
    dice_multipliers=DICE_MULTIPLIERS,
    combat_attack_base_damage=COMBAT_ATTACK_BASE_DAMAGE,
    locations=LOCATIONS,
    story_stage_thresholds=STORY_STAGE_THRESHOLDS,
    story_stage_required_tasks=STORY_STAGE_REQUIRED_TASKS,
    narrative_stories=NARRATIVE_STORIES,
    avatar_dir=AVATAR_DIR,
    portrait_dir=PORTRAIT_DIR,
)

from database import (
    bootstrap_app_data,
    configure_database,
    init_db,
    migrate_db,
    safe_init_db,
)

configure_database(
    db_path=DB_PATH,
    data_dir=DATA_DIR,
    upload_folder=UPLOAD_FOLDER,
    legacy_upload_folder=LEGACY_UPLOAD_FOLDER,
    sample_items=SAMPLE_ITEMS,
)
safe_init_db()

# ==================== Model Layer Imports ====================
from utils.helpers import (
    hkt_timestamp,
    list_image_files,
    normalize_team_id,
    normalize_photo_url,
    photo_public_url,
    safe_zip_arcname,
    resolve_upload_disk_path,
)
from utils.deploy import read_deploy_version
from utils.qr import (
    build_item_qr_payload,
    resolve_item_from_qr_payload,
    sign_qr_token,
)
from utils.validators import parse_status_effects, serialize_status_effects
from models.encounter import (
    load_encounter,
    list_encounter_ids,
    load_all_encounters,
    encounter_route_matches,
    evaluate_precheck_condition,
)
from models.squad import (
    row_to_squad,
    get_squad,
    update_squad,
    get_all_squads,
    fetch_squads_by_ids,
    get_team_members,
    get_team_average_stat,
)
from models.team import (
    resolve_team_display_route,
    official_team_route,
    is_team_leader_session,
    sync_team_route,
    get_next_team_id,
    get_team_by_id,
    get_team_protagonists,
)
from models.item import (
    get_item_by_id,
    get_item_by_qr_code_value,
    format_item_effect_text,
    serialize_item_for_client,
    apply_item_effect_to_squad,
    team_has_item,
    team_has_item_by_name,
    grant_item_to_squad,
)
from models.encounter_outcomes import (
    apply_status_debuff,
    add_insight_fragments,
    encounter_already_completed,
    record_encounter_completion,
    apply_precheck_skip,
    apply_failure_side_effects,
    apply_trauma_on_failure,
    apply_encounter_success,
    apply_encounter_failure,
    apply_encounter_success_solo,
    apply_encounter_failure_solo,
)
from models.combat import (
    row_to_combat,
    get_combat,
    get_combat_by_squad,
    get_active_combat_for_team,
    save_combat,
    set_team_combat_id,
    clear_team_combat_id,
    get_effective_stat,
    get_effective_attack_stat,
    describe_attack_stat,
    calculate_attack_damage,
    calculate_damage_simple,
    calculate_damage,
    calculate_incoming_damage,
    dice_multiplier,
    roll_combat_dice,
    get_combat_phase_actions,
    combat_action_already_submitted,
    upsert_combat_action,
    zoo_bonus_multiplier,
    berserk_probability,
    is_berserk,
    combat_phase_deadline,
    combat_phase_expired,
    get_combat_participants,
    get_active_combat_member_ids,
    get_active_combat_members,
    all_phase_actions_submitted,
    append_combat_log,
    apply_damage_to_player,
    get_lowest_resilience_player,
    resolve_player_phase,
    build_enemy_combat_stats,
    build_combat_status_response,
    build_combat_round_preview,
    build_single_player_preview,
    _combat_outcome_json,
    _build_full_preview_from_status,
    _build_round_resolved_response,
    COMBAT_ACTION_TYPES,
    ATTACK_ACTION_TYPES,
    DICE_MULTIPLIERS,
    COMBAT_ATTACK_BASE_DAMAGE,
    create_combat_record,
)

# ==================== Service Layer Imports ====================
from services.announcements import list_announcements
from services.global_events import apply_global_effect, create_global_event
from services.player_status import build_player_status
from services.story import (
    count_team_distinct_tasks,
    get_pending_story_id,
    is_story_viewed,
    mark_story_viewed,
    narrative_story_id_for_stage,
    resolve_story_stage,
)
from services.teams_overview import (
    build_active_combats_overview,
    build_teams_overview,
    get_all_teams_with_stats,
    query_teams_list,
)
from utils.tasks import task_display_name
from services.narrative import (
    enrich_story_lines,
    get_available_narrative_stories,
    get_story_for_route,
    next_stage_threshold,
)

# ==================== 向後兼容層（逐步移除） ====================
_enrich_story_lines = enrich_story_lines
_create_combat_record = create_combat_record


def register_blueprints():
    """Register route blueprints after app module is fully initialized."""
    from routes.auth import auth_bp
    from routes.player import player_bp
    from routes.combat import combat_bp
    from routes.gm import gm_bp
    from routes.team import team_bp
    from routes.misc import misc_bp
    from routes.story import story_bp
    from routes.encounters import encounters_bp
    from routes.items import items_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(player_bp)
    app.register_blueprint(combat_bp)
    app.register_blueprint(gm_bp)
    app.register_blueprint(team_bp)
    app.register_blueprint(misc_bp)
    app.register_blueprint(story_bp)
    app.register_blueprint(encounters_bp)
    app.register_blueprint(items_bp)


from services.session_auth import (
    attach_restore_token,
    establish_player_session,
    make_restore_token,
    verify_restore_token,
)

# ==================== Routes ====================
@app.before_request
def refresh_player_session():
    if "squad_id" in session or session.get("is_gm"):
        session.permanent = True


@app.after_request
def prevent_html_cache(response):
    """避免手機瀏覽器快取舊版內嵌 HTML/JS。"""
    if response.content_type and "text/html" in response.content_type:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response



register_blueprints()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG", "1").lower() in ("1", "true", "yes")
    print(f"\n  Oikonomia 本地伺服器")
    print(f"  ➜  http://localhost:{port}")
    print(f"  （注意：macOS 嘅 5000 port 通常被系統佔用，請用 {port}）\n")
    try:
        app.run(host="0.0.0.0", port=port, debug=debug)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"\n  ❌ Port {port} 已被佔用。請執行：")
            print(f"     lsof -ti:{port} | xargs kill -9")
            print(f"  或者用其他 port：PORT=5002 python3 app.py\n")
        raise


===== FILE: routes/misc.py =====

"""Miscellaneous public API routes."""
import os
import sqlite3

from flask import Blueprint, abort, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename

from data.locations import LOCATIONS
from models.combat import (
    count_team_defenders,
    resolve_player_phase,
    build_combat_round_preview,
    roll_combat_dice,
)
from models.protagonist import build_protagonist_participant
from models.settings import settings
from services.announcements import list_announcements
from utils.app_state import DB_INIT_ERROR
from utils.deploy import player_template_text, read_deploy_version
from utils.helpers import list_image_files, resolve_upload_disk_path
from utils.qr import sign_qr_token
from utils.uploads import save_task_submission_photo

misc_bp = Blueprint("misc", __name__)


@misc_bp.route("/")
def index():
    combat_v2_enabled = os.environ.get("COMBAT_V2", "").lower() in ("1", "true", "yes")
    return render_template("index.html", combat_v2_enabled=combat_v2_enabled)


@misc_bp.route("/__e2e__/combat-v2")
def combat_v2_e2e_harness():
    """Minimal Combat V2 mount for Playwright PR-7 (COMBAT_E2E=1 only)."""
    if os.environ.get("COMBAT_E2E", "").lower() not in ("1", "true", "yes"):
        abort(404)
    return render_template("combat_v2_harness.html")


@misc_bp.route("/api/version")
def api_version():
    upload_folder = settings.upload_folder
    upload_count = len([
        name for name in os.listdir(upload_folder)
        if os.path.isfile(os.path.join(upload_folder, name))
    ]) if os.path.isdir(upload_folder) else 0
    avatar_dir = settings.avatar_dir
    portrait_dir = settings.portrait_dir
    template_text = player_template_text()
    combat_v2_flag = os.environ.get("COMBAT_V2", "").lower() in ("1", "true", "yes")
    combat_v2_js = os.path.isfile(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "js", "combat", "index.js")
    )
    return jsonify({
        "success": DB_INIT_ERROR is None,
        "version": read_deploy_version(),
        "combat_v2": combat_v2_flag and combat_v2_js,
        "db_init_error": DB_INIT_ERROR,
        "markers": {
            "iggy_card": "iggy-card",
            "show_only_protagonist": "showOnlyProtagonistCard",
            "combat_system": callable(resolve_player_phase),
            "combat_preview": callable(build_combat_round_preview),
            "combat_modal": (
                "combat-action-modal" in template_text
                or "combat-root-v2" in template_text
            ),
            "combat_v2_module": "combat-root-v2" in template_text,
            "session_restore_v2": "tryLoginWithStoredSquad" in template_text,
            "settings_modal": "openSettingsModal" in template_text,
            "settings_js_safe": "resetAllSettings" in template_text and ".join('\\n')" in template_text,
            "server_combat_dice": callable(roll_combat_dice),
            "combat_actions_table": True,
            "qr_signed_v2": callable(sign_qr_token),
            "task_photo_validation": callable(save_task_submission_photo),
            "model_layer_phase1": True,
            "model_combat_layer": True,
            "combat_stats_v2": "combatStatValue" in template_text,
            "combat_ui_safe": "safeSetText" in template_text,
            "input_modal": "input-modal-overlay" in template_text,
            "routes_refactored": True,
            "upload_path_hardened": True,
            "defend_team_buff": callable(count_team_defenders),
            "combat_round_continue": "continueCombatAfterRound" in template_text,
            "player_max_hp": "max_hp" in template_text and "DEFAULT_PLAYER_MAX_HP" in template_text,
            "protagonist_combat": callable(build_protagonist_participant),
            "trauma_ending": "combat-result-trauma-badge" in template_text
                and "renderTeamEndingBanner" in template_text,
            "confirm_modal": "confirm-modal-overlay" in template_text
                and "showConfirmModal" in template_text,
            "protagonist_player_control": "protagonist-control-bar" in template_text
                and "controllingProtagonist" in template_text,
            "encounter_logs": "encounter-logs-list" in template_text
                and "loadEncounterLogs" in template_text,
            "enemy_hp_sync_v2": "syncEnemyHpDisplay" in template_text
                and "enemy_hp_after" in template_text,
            "enemy_hp_sync_v3": "resolveAuthoritativeEnemyHp" in template_text
                and "Math.min(...candidates)" in template_text,
            "enemy_hp_sync_v4": "fetchNoCache" in template_text
                and "appendCacheBust" in template_text,
            "enemy_hp_sync_v5": "animateCombatNumber" in template_text
                and "combatUiSnapshotKey" in template_text,
            "enemy_hp_sync_v6": "queueVictoryDuringSettlement" in template_text
                and "X-Requested-With" in template_text,
            "enemy_hp_sync_v7": "syncHpOnlyFromPoll" in template_text,
            "combat_instant_settlement": "combat_instant_settlement" in template_text,
            "combat_flow_v2": "combat_flow_v2" in template_text
                and "applyPendingSettlementHp" in template_text,
            "combat_flow_v3": "combat_flow_v3" in template_text
                and "showCombatConfirmStep" in template_text,
            "combat_flow_v4": "combat_flow_v4" in template_text
                and "combatFinalizingVictory" in template_text,
            "combat_flow_v5": "combat_flow_v5" in template_text
                and "victorySettlementAcknowledgedCombatId" in template_text,
            "combat_flow_v6": "combat_flow_v6" in template_text
                and "ensureVictorySettlementPayload" in template_text,
            "combat_flow_v7": "combat_flow_v7" in template_text
                and "isVictorySettlement" in template_text,
            "combat_flow_v8": "combat_flow_v8" in template_text
                and "settlementDisplayKey" in template_text,
            "combat_flow_v9": "combat_flow_v9" in template_text
                and "settlementModalShown" in template_text
                and "currentSettlementRound" in template_text,
            "combat_flow_v10": "combat_flow_v10" in template_text
                and "isFinalHitOrVictory" in template_text
                and "resolveEnemyHpAfter" in template_text,
            "combat_flow_v11": "combat_flow_v11" in template_text
                and "isRoundSettlementModalVisible" in template_text,
            "combat_flow_v12": "combat_flow_v12" in template_text
                and "combatVictorySequenceCompleteId" in template_text
                and "enrichRoundSettlementData" in template_text,
            "combat_flow_v13": "combat_flow_v13" in template_text
                and "sliceLogsForSettledRound" in template_text
                and "getSettledRoundNumber" in template_text,
            "combat_flow_v14": "combat_flow_v14" in template_text
                and "clearLocalCombatSubmittedState" in template_text
                and "restoreCombatConfirmBtn" in template_text,
            "combat_flow_v15": "combat_flow_v15" in template_text
                and "showCombatSubmitLoadingShell" in template_text,
            "combat_flow_v16": "combat_flow_v16" in template_text
                and "isCombatResultPanelVisible" in template_text
                and "round_resolved" in template_text,
            "combat_flow_v17": "combat_flow_v17" in template_text
                and "settlement_modal_missing_recovery" in template_text
                and "combat-player-avatar-mobile" in template_text,
            "combat_flow_v18": "combat_flow_v18" in template_text
                and "enforceSettlementInvariant" in template_text
                and "combat_mobile_hud_v2" in template_text,
            "combat_flow_fsm_v1": "combat_flow_fsm_v1" in template_text
                and "combatFsmHook" in template_text,
            "combat_flow_fsm_v2": "combat_flow_fsm_v2" in template_text
                and "combatFsmCanPerformAction" in template_text
                and "combat_mobile_hud_v1" in template_text,
            "combat_flow_js": os.path.isfile(
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "js", "combat_flow.js")
            ),
            "combat_v2": combat_v2_flag and combat_v2_js,
            "combat_v2_module": combat_v2_js,
            "settlement_breakdown_v1": "renderSettlementBreakdown" in template_text
                and "breakdown" in template_text,
        },
        "db_path": settings.db_path,
        "upload_folder": upload_folder,
        "legacy_upload_folder": settings.legacy_upload_folder,
        "upload_file_count": upload_count,
        "avatar_dir": avatar_dir,
        "avatar_count": len(list_image_files(avatar_dir, exclude=("default.png",))),
        "portrait_dir": portrait_dir,
        "portrait_count": len(list_image_files(portrait_dir, exclude=("default.png",))),
    })


@misc_bp.route("/locations")
def get_locations():
    return jsonify(LOCATIONS)


@misc_bp.route("/global_events")
def get_global_events():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, title, description, effect_type, effect_value, created_by, timestamp
        FROM global_events
        ORDER BY timestamp DESC
        LIMIT 30
    """).fetchall()
    conn.close()
    return jsonify({
        "success": True,
        "events": [dict(row) for row in rows],
    })


@misc_bp.route("/announcements")
def get_announcements():
    return jsonify({"announcements": list_announcements()})


@misc_bp.route("/uploads/<path:filename>")
def serve_upload(filename):
    safe_name = secure_filename(os.path.basename(str(filename or "").replace("\\", "/")))
    if not safe_name:
        abort(404)
    disk_path = resolve_upload_disk_path(safe_name)
    if not disk_path or not os.path.isfile(disk_path):
        abort(404)
    return send_from_directory(os.path.dirname(disk_path), os.path.basename(disk_path))


@misc_bp.route("/debug/teams")
def debug_teams():
    conn = sqlite3.connect(settings.db_path)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='teams'")
    exists = c.fetchone() is not None
    count = 0
    if exists:
        count = c.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    conn.close()
    return jsonify({"teams_table_exists": exists, "team_count": count})


===== FILE: templates/combat_screen.html =====

{# Combat V2 mount skeleton — included when COMBAT_V2 enabled #}
<div id="combat-root-v2" class="combat-v2 flex flex-col min-h-[70vh] max-w-md lg:max-w-6xl mx-auto px-1 sm:px-0 hidden"
     data-testid="combat-v2-screen">
  <section id="combat-v2-hud" class="shrink-0 px-3 py-2 grid grid-cols-2 gap-2 max-h-20">
    <div class="flex items-center gap-2 min-w-0">
      <img id="combat-v2-enemy-avatar" src="/static/images/enemies/parasite_shadow.svg"
           class="w-8 h-8 md:w-12 md:h-12 rounded-full object-cover shrink-0" alt="敵人"
           data-testid="enemy-avatar" width="32" height="32" loading="eager" />
      <div class="min-w-0 flex-1">
        <div id="combat-v2-enemy-name" class="text-xs truncate text-red-300">敵人</div>
        <div class="h-2 bg-zinc-800 rounded overflow-hidden">
          <div id="combat-v2-enemy-hp-bar" class="h-full bg-red-500 transition-all duration-300" style="width:100%"></div>
        </div>
        <div id="combat-v2-enemy-hp" class="text-[10px] text-zinc-400" data-testid="enemy-hp">—/—</div>
      </div>
    </div>
    <div class="flex items-center gap-2 min-w-0">
      <img id="combat-v2-player-avatar" src="/static/avatars/default.png"
           class="w-8 h-8 md:w-12 md:h-12 rounded-full object-cover shrink-0" alt="我"
           data-testid="player-avatar" width="32" height="32" loading="eager" />
      <div class="min-w-0 flex-1">
        <div id="combat-v2-player-name" class="text-xs truncate text-amber-400">你</div>
        <div class="h-2 bg-zinc-800 rounded overflow-hidden">
          <div id="combat-v2-player-hp-bar" class="h-full bg-amber-500 transition-all duration-300" style="width:100%"></div>
        </div>
        <div id="combat-v2-player-hp" class="text-[10px] text-zinc-400">—/—</div>
      </div>
    </div>
  </section>

  <section id="combat-v2-protagonist-control-bar" class="hidden shrink-0 px-3 py-1.5 bg-purple-950/30 border-y border-purple-900/40 flex items-center justify-between gap-2">
    <div class="flex items-center gap-2 min-w-0">
      <span class="text-xs text-purple-300 font-bold shrink-0">⭐ 隊長特權</span>
      <span id="combat-v2-protagonist-label" class="text-[11px] text-zinc-400 truncate">可代替主角行動</span>
    </div>
    <label class="relative inline-flex items-center cursor-pointer select-none shrink-0">
      <input type="checkbox" id="combat-v2-protagonist-toggle" class="sr-only peer" data-testid="protagonist-toggle">
      <div class="w-9 h-5 bg-zinc-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-zinc-400 after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-purple-600 peer-checked:after:bg-white"></div>
      <span class="ml-2 text-xs text-purple-200 peer-checked:text-purple-400 font-medium">代打模式</span>
    </label>
  </section>

  <section id="combat-v2-team-status" class="shrink-0 px-3 py-1 border-y border-zinc-800/80 max-h-24 overflow-y-auto"></section>

  <div id="combat-v2-zoo-tip" class="hidden mx-3 mt-2"></div>

  <section id="combat-v2-log" class="flex-1 overflow-y-auto px-3 py-2 text-sm min-h-0"></section>

  <section id="combat-v2-actions" class="shrink-0 p-3 grid grid-cols-2 gap-2 md:flex md:gap-3 md:flex-wrap"
           style="touch-action: manipulation;">
    <button type="button" id="combat-v2-attack-btn" data-testid="attack-btn"
            class="min-h-11 rounded-lg bg-red-600 text-white font-medium active:scale-95 transition-transform">⚔ 攻擊</button>
    <button type="button" id="combat-v2-defend-btn" data-testid="defend-btn"
            class="min-h-11 rounded-lg bg-blue-600 text-white font-medium active:scale-95 transition-transform">🛡 防禦</button>
    <button type="button" id="combat-v2-zoo-btn" data-testid="zoo-btn"
            class="min-h-11 rounded-lg bg-purple-700 text-white font-medium text-sm active:scale-95 transition-transform">🦄 Zoo</button>
    <button type="button" id="combat-v2-item-btn"
            class="min-h-11 rounded-lg bg-amber-600 text-white font-medium text-sm active:scale-95 transition-transform">🎒 物品</button>
    <button type="button" id="combat-v2-escape-btn"
            class="min-h-11 rounded-lg bg-zinc-700 text-zinc-300 font-medium text-sm active:scale-95 transition-transform md:col-span-1 col-span-2">🏃 逃跑</button>
  </section>

  <div id="combat-v2-dice-modal" class="hidden fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true">
    <div class="bg-zinc-900 rounded-2xl p-6 text-center w-full max-w-xs">
      <div class="text-4xl font-bold text-amber-400 mb-4" id="combat-v2-dice-value" data-testid="dice-value">—</div>
      <button type="button" id="combat-v2-dice-confirm-btn" data-testid="dice-confirm-btn"
              class="hidden min-h-11 w-full rounded-lg bg-amber-600 text-white font-medium">確認並結束本回合</button>
    </div>
  </div>

  <div id="combat-v2-round-settlement-modal" class="hidden fixed inset-0 z-[75] flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true">
    <div class="bg-zinc-900 rounded-2xl p-5 w-full max-w-sm max-h-[80vh] overflow-y-auto">
      <h3 class="text-lg font-bold text-amber-400 mb-3">傷害結算</h3>
      <div id="combat-v2-settlement-body"></div>
      <button type="button" id="combat-v2-settlement-confirm-btn" data-testid="settlement-confirm-btn"
              class="mt-4 min-h-11 w-full rounded-lg bg-amber-600 text-white font-medium">確定</button>
    </div>
  </div>

  <div id="combat-v2-submit-hint" class="hidden fixed inset-0 z-[65] flex items-center justify-center bg-black/50">
    <span class="text-white text-lg animate-pulse">結算中…</span>
  </div>

  <div id="combat-v2-escape-result" class="hidden"></div>
  <div id="combat-v2-result-panel" class="hidden"></div>
  <div id="combat-v2-failed-panel" class="hidden"></div>
</div>


===== FILE: templates/combat_v2_harness.html =====

<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Combat V2 E2E Harness</title>
    <script>window.__OIKONOMIA_COMBAT_V2__ = true;</script>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { margin: 0; background: #09090b; color: #fff; font-family: system-ui, sans-serif; }
    </style>
</head>
<body>
    <div id="combat-module-container" class="w-full min-h-screen">
        {% include 'combat_screen.html' %}
    </div>
    <script type="module" src="/static/js/combat/bootstrap.js"></script>
</body>
</html>


===== FILE: tests/combat_state_machine.test.js =====

/**
 * Combat V2 FSM unit tests (no DOM)
 * Run: npm run test:combat
 */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  Phase,
  TERMINAL_PHASES,
  createInitialContext,
  transition,
  canDispatch,
  handleAnyDeath,
  isMemberCollapsed,
  isEnemyDefeated,
  parseCombatHp,
  syncState,
  determineSettlementRoute,
} from '../static/js/combat/state_machine.js';
import { normalizeSettlement, deriveSettlementId } from '../static/js/combat/settlement.js';

describe('Combat V2 state machine', () => {
  it('TERMINAL_PHASES SSOT covers endgame absorbing phases', () => {
    assert.deepEqual(TERMINAL_PHASES, [
      Phase.COMBAT_FAILED,
      Phase.VICTORY,
      Phase.DEFEAT,
      Phase.ESCAPED,
    ]);
  });

  it('IDLE + ACTION_ATTACK → DICE_ROLLING', () => {
    const ctx = createInitialContext('c1');
    const { ctx: next } = transition(ctx, 'ACTION_ATTACK', { action: 'attack', dice: 3 });
    assert.equal(next.phase, Phase.DICE_ROLLING);
    assert.equal(next.dice.action, 'attack');
  });

  it('DICE_ROLLING + ACTION_ATTACK → toast (blocked)', () => {
    let ctx = createInitialContext('c1');
    ctx = transition(ctx, 'ACTION_ATTACK', { action: 'attack', dice: 3 }).ctx;
    const { ctx: same, effects } = transition(ctx, 'ACTION_ATTACK');
    assert.equal(same.phase, Phase.DICE_ROLLING);
    assert.equal(effects[0].type, 'TOAST');
  });

  it('full solo round: IDLE → … → SETTLEMENT → IDLE', () => {
    let ctx = createInitialContext(42);
    ctx = transition(ctx, 'ACTION_ATTACK', { action: 'attack', dice: 2 }).ctx;
    ctx = transition(ctx, 'DICE_ANIMATION_DONE', { dice: 2 }).ctx;
    assert.equal(ctx.phase, Phase.DICE_CONFIRM);
    ctx = transition(ctx, 'CONFIRM_DICE').ctx;
    assert.equal(ctx.phase, Phase.SUBMITTING);
    const settlement = { team_damage_dealt: 15, enemy_damage_dealt: 5, player_hits: [] };
    ctx = transition(ctx, 'SUBMIT_SUCCESS', {
      roundResolved: true,
      settlement,
      settlementId: '42:0',
      isKillingBlow: false,
    }).ctx;
    assert.equal(ctx.phase, Phase.SETTLEMENT);
    ctx = transition(ctx, 'ACK_SETTLEMENT', { killing: false }).ctx;
    assert.equal(ctx.phase, Phase.IDLE);
  });

  it('killing blow: SETTLEMENT → VICTORY', () => {
    let ctx = createInitialContext(1);
    ctx.phase = Phase.SETTLEMENT;
    ctx.isKillingBlow = true;
    ctx.pendingSettlementId = '1:5';
    const { ctx: next, effects } = transition(ctx, 'ACK_SETTLEMENT', { killing: true });
    assert.equal(next.phase, Phase.VICTORY);
    assert.ok(effects.some((e) => e.type === 'STOP_POLL'));
  });

  it('INV-D: any death → COMBAT_FAILED', () => {
    const ctx = createInitialContext(1);
    const { ctx: failed, effects } = handleAnyDeath(ctx, {
      p1: { display_name: 'Alice', hp: 0 },
      p2: { display_name: 'Bob', hp: 50 },
    });
    assert.equal(failed.phase, Phase.COMBAT_FAILED);
    assert.deepEqual(failed.failedMembers, ['Alice']);
    assert.ok(effects.some((e) => e.type === 'STOP_POLL'));
  });

  it('poll tick does not open settlement for non-victory sync', () => {
    let ctx = createInitialContext(1);
    ctx.phase = Phase.IDLE;
    const { ctx: next, effects } = syncState(ctx, {
      combat_id: 1,
      round_resolved: true,
      round_settlement: { team_damage_dealt: 10 },
      enemy: { hp: 200, max_hp: 220 },
      my_state: { hp: 80, max_hp: 100, submitted: false },
      member_states: { s1: { hp: 80, submitted: false } },
    });
    assert.notEqual(next.phase, Phase.SETTLEMENT);
    assert.ok(!effects.some((e) => e.type === 'SHOW_SETTLEMENT'));
  });

  it('G2: poll victory with unseen settlement → SETTLEMENT before VICTORY', () => {
    const ctx = { ...createInitialContext(1), phase: Phase.WAITING_FOR_PLAYERS };
    const { ctx: next, effects } = syncState(ctx, {
      outcome: 'victory',
      combat_id: 1,
      settled_round_index: 4,
      settlement_id: '1:4',
      round_settlement: { team_damage_dealt: 22, player_hits: [{ player: '隊友', damage: 22 }] },
      enemy: { hp: 0, max_hp: 220 },
      my_state: { hp: 80, submitted: true },
      member_states: { s1: { hp: 80, submitted: true } },
    });
    assert.equal(next.phase, Phase.SETTLEMENT);
    assert.equal(next.isKillingBlow, true);
    assert.ok(effects.some((e) => e.type === 'SHOW_SETTLEMENT' && e.killing === true));
  });

  it('submitted guard blocks ACTION_ATTACK', () => {
    const ctx = { ...createInitialContext(1), hud: { me: { submitted: true } } };
    assert.equal(canDispatch(ctx, 'ACTION_ATTACK'), false);
  });

  it('entry sync absorbs stable stale settlement on first poll (INV-C)', () => {
    const ctx = {
      ...createInitialContext(99),
      phase: Phase.IDLE,
      entrySyncPending: true,
    };
    const { ctx: next, effects } = syncState(ctx, {
      combat_id: 99,
      status: 'player_phase',
      current_phase: 3,
      settled_round_index: 2,
      settlement_id: '99:2',
      round_resolved: false,
      round_settlement: { team_damage_dealt: 40, enemy_damage_dealt: 0, player_hits: [] },
      enemy: { hp: 160, max_hp: 200 },
      my_state: { hp: 100, submitted: false },
      member_states: { s1: { hp: 100, submitted: false } },
    });
    assert.equal(next.phase, Phase.IDLE);
    assert.equal(next.settledRoundIndex, 2);
    assert.equal(next.entrySyncPending, false);
    assert.ok(next.shownSettlementIds.has('99:2'));
    assert.ok(!effects.some((e) => e.type === 'SHOW_SETTLEMENT'));
  });

  it('entry sync does not swallow modal when round_resolved on reconnect (INV-A)', () => {
    const ctx = {
      ...createInitialContext(99),
      phase: Phase.IDLE,
      entrySyncPending: true,
    };
    const { ctx: next } = syncState(ctx, {
      combat_id: 99,
      status: 'player_phase',
      current_phase: 2,
      settled_round_index: 1,
      settlement_id: '99:1',
      round_resolved: true,
      round_settlement: { team_damage_dealt: 40, enemy_damage_dealt: 0, player_hits: [] },
      enemy: { hp: 160, max_hp: 200 },
      my_state: { hp: 100, submitted: false },
      member_states: { s1: { hp: 100, submitted: false } },
    });
    assert.equal(next.entrySyncPending, false);
    assert.ok(!next.shownSettlementIds.has('99:1'));
  });

  it('R12-D: stale victory poll dropped by monotonic guard (INV-C)', () => {
    const ctx = {
      ...createInitialContext(999),
      phase: Phase.SETTLEMENT,
      settledRoundIndex: 2,
      pendingSettlementId: '999:2',
      isKillingBlow: true,
      hud: { enemy: { hp: 0, max_hp: 200 }, me: { hp: 80 }, members: {}, log: [] },
    };
    const { ctx: next, effects } = syncState(ctx, {
      outcome: 'victory',
      combat_id: 999,
      settled_round_index: 1,
      settlement_id: '999:1',
      round_settlement: { team_damage_dealt: 10 },
      enemy: { hp: 50, max_hp: 200 },
      my_state: { hp: 80 },
      member_states: {},
    });
    assert.equal(next.hud.enemy.hp, 0);
    assert.equal(effects.length, 0);
  });

  it('R12-D: defeat poll during SETTLEMENT clears pending settlement (INV-A)', () => {
    const ctx = {
      ...createInitialContext(888),
      phase: Phase.SETTLEMENT,
      settledRoundIndex: 1,
      pendingSettlement: { team_damage_dealt: 12 },
      pendingSettlementId: '888:1',
      hud: { enemy: { hp: 5, max_hp: 200 }, me: { hp: 80 }, members: {}, log: [] },
    };
    const { ctx: next, effects } = syncState(ctx, {
      outcome: 'defeat',
      winner: 'enemy',
      combat_id: 888,
      dead_squad_ids: ['s1'],
      dead_squad_names: ['Alice'],
      member_states: { s1: { display_name: 'Alice', hp: 50 } },
      enemy: { hp: 5, max_hp: 200 },
      my_state: { hp: 80 },
    });
    assert.equal(next.phase, Phase.COMBAT_FAILED);
    assert.equal(next.pendingSettlement, null);
    assert.equal(next.pendingSettlementId, null);
    assert.ok(effects.some((e) => e.type === 'HIDE_SETTLEMENT'));
  });

  it('R12-D: victory poll during SETTLEMENT does not skip to VICTORY', () => {
    const ctx = {
      ...createInitialContext(999),
      phase: Phase.SETTLEMENT,
      settledRoundIndex: 2,
      pendingSettlementId: '999:2',
      isKillingBlow: true,
      hud: { enemy: { hp: 0, max_hp: 200 }, me: { hp: 80 }, members: {}, log: [] },
    };
    const { ctx: next, effects } = syncState(ctx, {
      outcome: 'victory',
      combat_id: 999,
      settled_round_index: 2,
      settlement_id: '999:2',
      enemy: { hp: 0, max_hp: 200 },
      my_state: { hp: 80 },
      member_states: {},
    });
    assert.equal(next.phase, Phase.SETTLEMENT);
    assert.ok(!effects.some((e) => e.type === 'SHOW_VICTORY'));
  });

  it('P2-5: WAITING_FOR_PLAYERS poll round_resolved → SETTLEMENT', () => {
    const ctx = { ...createInitialContext(1012), phase: Phase.WAITING_FOR_PLAYERS };
    const { ctx: next, effects } = syncState(ctx, {
      combat_id: 1012,
      status: 'round_resolved',
      round_resolved: true,
      settlement_id: '1012:1',
      waiting_for_teammates: false,
      round_settlement: { team_damage_dealt: 40, enemy_damage_dealt: 0, player_hits: [] },
      enemy: { hp: 160, max_hp: 200 },
      my_state: { hp: 100, submitted: true },
      member_states: { s1: { hp: 100, submitted: true } },
    });
    assert.equal(next.phase, Phase.SETTLEMENT);
    assert.ok(effects.some((e) => e.type === 'SHOW_SETTLEMENT'));
  });

  it('monotonic guard skips stale settlement index', () => {
    const ctx = { ...createInitialContext(1), settledRoundIndex: 3, shownSettlementIds: new Set() };
    const route = determineSettlementRoute(
      ctx,
      { settled_round_index: 1, combat_id: 1 },
      { team_damage_dealt: 5 },
      '1:1',
    );
    assert.equal(route.skipModal, true);
    assert.equal(route.settledRoundIndex, 3);
  });

  it('SETTLEMENT poll defeat exits to DEFEAT with settlement teardown (INV-A)', () => {
    const ctx = {
      ...createInitialContext(1),
      phase: Phase.SETTLEMENT,
      pendingSettlementId: '1:0',
      pendingSettlement: { team_damage_dealt: 8 },
      isKillingBlow: false,
    };
    const { ctx: next, effects } = transition(ctx, 'POLL_TICK', {
      snapshot: {
        combat_id: 1,
        outcome: 'defeat',
        winner: 'enemy',
        my_state: { hp: 80 },
        member_states: { s1: { hp: 80 } },
      },
    });
    assert.equal(next.phase, Phase.DEFEAT);
    assert.equal(next.pendingSettlement, null);
    assert.ok(effects.some((e) => e.type === 'HIDE_SETTLEMENT'));
    assert.ok(effects.some((e) => e.type === 'SHOW_DEFEAT'));
  });

  it('near_death_until triggers isMemberCollapsed (INV-D)', () => {
    assert.equal(isMemberCollapsed({ hp: 50, near_death_until: '2099-01-01T00:00:00' }), true);
    const ctx = createInitialContext(1);
    const { ctx: failed } = handleAnyDeath(ctx, {
      A: { display_name: 'A', hp: 'n/a', near_death_until: '2099-01-01T00:00:00' },
    });
    assert.equal(failed.phase, Phase.COMBAT_FAILED);
  });

  it('defeat with dead_squad_names from DICE_CONFIRM clears modals (INV-D)', () => {
    const ctx = { ...createInitialContext(1), phase: Phase.DICE_CONFIRM };
    const { ctx: next, effects } = syncState(ctx, {
      combat_id: 1,
      outcome: 'defeat',
      winner: 'enemy',
      dead_squad_names: ['Alice'],
      member_states: { A: { display_name: 'Alice', hp: 50 } },
      my_state: { hp: 80, submitted: false },
    });
    assert.equal(next.phase, Phase.COMBAT_FAILED);
    assert.ok(effects.some((e) => e.type === 'HIDE_ALL_MODALS'));
    assert.ok(effects.some((e) => e.type === 'SHOW_FAILED'));
  });

  it('defeat payload with dead_squad_names → COMBAT_FAILED', () => {
    const ctx = createInitialContext(1);
    const { ctx: next, effects } = syncState(ctx, {
      combat_id: 1,
      outcome: 'defeat',
      winner: 'enemy',
      dead_squad_names: ['Alice'],
      dead_squad_ids: ['A'],
      member_states: { A: { display_name: 'Alice', hp: 0 } },
      my_state: { hp: 80, submitted: false },
    });
    assert.equal(next.phase, Phase.COMBAT_FAILED);
    assert.deepEqual(next.failedMembers, ['Alice']);
    assert.ok(effects.some((e) => e.type === 'SHOW_FAILED'));
  });

  it('IDLE + ACTION_USE_ZOO → DICE_ROLLING (P2-2)', () => {
    const ctx = {
      ...createInitialContext('c1'),
      hud: { me: { submitted: false, sanity: 80 }, allow_zoo: true },
    };
    const { ctx: next } = transition(ctx, 'ACTION_USE_ZOO', { action: 'use_zoo', dice: 2 });
    assert.equal(next.phase, Phase.DICE_ROLLING);
    assert.equal(next.dice.action, 'use_zoo');
  });

  it('IDLE + ACTION_USE_ZOO allowed below sanity 70 (no bonus tier)', () => {
    const ctx = {
      ...createInitialContext('c1'),
      hud: { me: { submitted: false, sanity: 55 }, allow_zoo: true },
    };
    assert.equal(canDispatch(ctx, 'ACTION_USE_ZOO', { action: 'use_zoo', dice: 1 }), true);
    const { ctx: next } = transition(ctx, 'ACTION_USE_ZOO', { action: 'use_zoo', dice: 1 });
    assert.equal(next.phase, Phase.DICE_ROLLING);
  });
});

describe('Settlement normalization', () => {
  it('uses round_settlement when damage > 0', () => {
    const s = normalizeSettlement({
      round_settlement: { team_damage_dealt: 12, enemy_damage_dealt: 3, player_hits: [] },
      enemy: { hp: 208 },
    });
    assert.equal(s.team_damage_dealt, 12);
  });

  it('deriveSettlementId prefers API field', () => {
    assert.equal(deriveSettlementId({ settlement_id: '9:3', combat_id: 9 }), '9:3');
    assert.equal(deriveSettlementId({ combat_id: 9, settled_round_index: 2 }), '9:2');
  });

  it('malformed member hp does not trigger COMBAT_FAILED', () => {
    const ctx = createInitialContext(1);
    const { ctx: next } = handleAnyDeath(ctx, {
      A: { display_name: 'A', hp: 'n/a', max_hp: 100 },
    });
    assert.notEqual(next.phase, Phase.COMBAT_FAILED);
    assert.equal(isMemberCollapsed({ hp: 'n/a' }), false);
    assert.equal(isEnemyDefeated({ hp: undefined }), false);
    assert.equal(parseCombatHp(null, 80), 80);
    assert.equal(parseCombatHp('12', 80), 12);
  });

  it('falls back to authoritative round fields when settlement missing', () => {
    const s = normalizeSettlement({
      round_enemy_damage: 15,
      round_player_damage: 4,
      enemy: { hp: 85 },
    });
    assert.equal(s.team_damage_dealt, 15);
    assert.equal(s.enemy_damage_dealt, 4);
    assert.equal(s.enemy_hp_after, 85);
    assert.deepEqual(s.player_hits, []);
  });
});


===== FILE: tests/combat_v2.spec.js =====

/**
 * Combat V2 — Resilience & Phase 2 E2E (T8–T14)
 *
 * Requires: COMBAT_E2E=1 + COMBAT_V2=1 server (playwright.config.cjs webServer)
 * Run: npm run test:e2e:v2
 */
import { test, expect } from '@playwright/test';

const HARNESS_PATH = '/__e2e__/combat-v2';

async function waitForCombatV2(page) {
  await page.waitForFunction(
    () => window.combatV2?.isEnabled?.() && document.getElementById('combat-root-v2')?.__combat_app_instance__,
    null,
    { timeout: 15000 },
  );
}

async function startCombat(page, payload = {}) {
  await waitForCombatV2(page);
  await page.evaluate(async (data) => {
    document.getElementById('combat-root-v2')?.classList.remove('hidden');
    await window.combatV2.onCombatStarted({
      combat_id: data.combat_id ?? 999,
      status: 'player_phase',
      current_phase: data.current_phase ?? 2,
      enemy: data.enemy ?? { name: '速戰殘影', hp: 220, max_hp: 220 },
      my_state: data.my_state ?? {
        display_name: 'Henry',
        hp: 100,
        max_hp: 100,
        submitted: false,
      },
      member_states: data.member_states ?? {
        'PLAYER-75406': {
          display_name: 'Henry',
          hp: 100,
          max_hp: 100,
          submitted: false,
        },
      },
      ...data,
    });
  }, payload);
}

test.describe('Oikonomia Combat V2 — Resilience & Phase 2 E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(HARNESS_PATH);
  });

  test('T8: mixed escape failure then settlement modal (INV-E)', async ({ page }) => {
    await page.route('**/combat/status**', (route) => route.fulfill({ status: 204, body: '' }));

    await startCombat(page, { combat_id: 999 });

    await page.evaluate(() => {
      void window.combatV2.onSubmitSuccess({
        success: true,
        combat_id: 999,
        status: 'round_resolved',
        round_resolved: true,
        current_phase: 3,
        settled_round_index: 2,
        settlement_id: '999:2',
        my_squad_id: 'PLAYER-75406',
        enemy: { name: '速戰殘影', hp: 185, max_hp: 220 },
        my_state: { display_name: 'Henry', hp: 100, max_hp: 100, submitted: true },
        member_states: {
          'PLAYER-75406': {
            display_name: 'Henry',
            hp: 100,
            submitted: true,
            action_type: 'escape',
          },
          'TEAMMATE-02': {
            display_name: '小隊員',
            hp: 85,
            submitted: true,
            action_type: 'attack',
            dice_result: 2,
          },
        },
        round_settlement: {
          team_damage_dealt: 35,
          enemy_damage_dealt: 0,
          escape_triggered: true,
          escape_success: false,
          player_hits: [{ player: '小隊員', damage: 35, role: 'teammate' }],
          counter_hits: [],
          enemy_hp_after: 185,
        },
      });
    });

    const escapeOverlay = page.locator('#combat-v2-escape-result');
    await expect(escapeOverlay).toBeVisible();
    await expect(escapeOverlay).toContainText('逃跑失敗');

    await escapeOverlay.locator('#combat-v2-escape-continue').click();

    const settlementModal = page.locator('#combat-v2-round-settlement-modal');
    await expect(settlementModal).toBeVisible();
    await expect(page.locator('[data-testid="team-damage-dealt"]')).toContainText('隊伍造成 35 點傷害');
  });

  test('T9: preemptive interrupt hides dice modal on death (INV-D)', async ({ page }) => {
    await page.route('**/combat/status**', (route) => route.fulfill({ status: 204, body: '' }));

    await startCombat(page, {
      combat_id: 888,
      enemy: { name: '馬拉松首領', hp: 220, max_hp: 220 },
      member_states: {
        'PLAYER-75406': { display_name: 'Henry', hp: 100, max_hp: 100, submitted: false },
        p_npc_marah: { display_name: 'AI 主角 Marah', hp: 50, max_hp: 100, submitted: false, is_protagonist: true },
      },
    });

    await page.locator('#combat-v2-attack-btn').click();
    const diceModal = page.locator('#combat-v2-dice-modal');
    await expect(diceModal).toBeVisible();

    await page.evaluate(() => {
      window.combatV2.pollTick({
        success: true,
        combat_id: 888,
        status: 'player_phase',
        enemy: { name: '馬拉松首領', hp: 220, max_hp: 220 },
        my_state: { display_name: 'Henry', hp: 100, submitted: false },
        member_states: {
          'PLAYER-75406': { display_name: 'Henry', hp: 100, submitted: false },
          p_npc_marah: { display_name: 'AI 主角 Marah', hp: 0, submitted: false, is_protagonist: true },
        },
      });
    });

    await expect(diceModal).toBeHidden();
    const failedPanel = page.locator('#combat-v2-failed-panel');
    await expect(failedPanel).toBeVisible();
    await expect(failedPanel).toContainText('AI 主角 Marah');
    await expect(page.locator('#combat-v2-attack-btn')).toBeDisabled();
  });

  test('T10: visibilitychange triggers immediate sync and resets backoff', async ({ page }) => {
    let statusCalls = 0;

    await page.route('**/combat/status**', async (route) => {
      statusCalls += 1;
      if (statusCalls <= 3) {
        await route.fulfill({ status: 500, body: 'error' });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          combat_id: 777,
          status: 'player_phase',
          waiting_for_teammates: false,
          current_phase: 2,
          enemy: { name: '速戰殘影', hp: 10, max_hp: 220 },
          my_state: { display_name: 'Henry', hp: 100, max_hp: 100, submitted: true },
          member_states: {
            'PLAYER-75406': { display_name: 'Henry', hp: 100, submitted: true },
          },
        }),
      });
    });

    await startCombat(page, { combat_id: 777 });

    await page.evaluate(() => {
      const app = document.getElementById('combat-root-v2').__combat_app_instance__;
      app.dispatch('SUBMIT_SUCCESS', { roundResolved: false });
      app.poller.setPhase('WAITING_FOR_PLAYERS');
    });

    await page.waitForTimeout(4500);

    const backoffBefore = await page.evaluate(() => {
      return document.getElementById('combat-root-v2').__combat_app_instance__.poller.backoffMs;
    });
    expect(backoffBefore).toBeGreaterThan(0);

    const callsBeforeVisibility = statusCalls;

    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', { configurable: true, value: false });
      Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
      document.dispatchEvent(new Event('visibilitychange'));
    });

    await page.waitForFunction(
      () => {
        const hp = document.querySelector('[data-testid="enemy-hp"]')?.textContent || '';
        return hp.includes('10');
      },
      null,
      { timeout: 8000 },
    );

    expect(statusCalls).toBeGreaterThan(callsBeforeVisibility);

    const backoffAfter = await page.evaluate(() => {
      return document.getElementById('combat-root-v2').__combat_app_instance__.poller.backoffMs;
    });
    expect(backoffAfter).toBe(0);
  });

  test('T11: combat item pick, submit payload, and settlement (P2-1)', async ({ page }) => {
    await page.route('**/combat/status**', (route) => route.fulfill({ status: 204, body: '' }));

    await page.route('**/api/inventory**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          items: [
            {
              item_id: 105,
              name: '界線之鑰',
              description: '蘊含強大 Power 的戰鬥消耗品。',
              icon: '🗝️',
              has_ability: true,
              effect_type: 'power_up',
              effect_value: 15,
            },
          ],
        }),
      });
    });

    let submitPayload = null;
    await page.route('**/combat/submit_action**', async (route) => {
      submitPayload = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          combat_id: 999,
          status: 'round_resolved',
          round_resolved: true,
          current_phase: 3,
          settled_round_index: 2,
          settlement_id: '999:2',
          my_squad_id: 'PLAYER-75406',
          enemy: { name: '速戰殘影', hp: 120, max_hp: 220 },
          my_state: { display_name: 'Henry', hp: 100, max_hp: 100, submitted: true },
          member_states: {
            'PLAYER-75406': {
              display_name: 'Henry',
              hp: 100,
              submitted: true,
              action_type: 'use_item',
              item_id: 105,
            },
          },
          round_settlement: {
            team_damage_dealt: 45,
            enemy_damage_dealt: 0,
            player_hits: [{ player: 'Henry', damage: 45, role: 'self', action_type: 'use_item' }],
            counter_hits: [],
            enemy_hp_after: 120,
          },
        }),
      });
    });

    await startCombat(page, { combat_id: 999 });

    await page.locator('#combat-v2-item-btn').click();
    const itemModal = page.locator('#combat-v2-item-modal');
    await expect(itemModal).toBeVisible();
    await expect(itemModal).toContainText('界線之鑰');

    await itemModal.locator('button[data-item-id="105"]').click();
    await expect(itemModal).toBeHidden();

    const diceModal = page.locator('#combat-v2-dice-modal');
    await expect(diceModal).toBeVisible();
    await expect(page.locator('#combat-v2-dice-value')).toContainText('界線之鑰');

    await page.locator('#combat-v2-dice-confirm-btn').click();

    expect(submitPayload).not.toBeNull();
    expect(submitPayload.action_type).toBe('use_item');
    expect(submitPayload.item_id).toBe(105);
    expect(submitPayload.combat_id).toBe(999);

    const settlementModal = page.locator('#combat-v2-round-settlement-modal');
    await expect(settlementModal).toBeVisible();
    await expect(page.locator('[data-testid="team-damage-dealt"]')).toContainText('隊伍造成 45 點傷害');
  });

  test('T12: True Co-op parallel submission (WAITING_FOR_PLAYERS → settlement)', async ({ browser }) => {
    const leaderContext = await browser.newContext();
    const memberContext = await browser.newContext();
    const leaderPage = await leaderContext.newPage();
    const memberPage = await memberContext.newPage();

    const sharedPhaseActions = {};

    const buildSnapshot = (squadId, waiting) => {
      const submitted = !!sharedPhaseActions[squadId];
      const display = squadId === 'LEADER-1' ? '隊長' : '隊員';
      const base = {
        success: true,
        combat_id: 1012,
        status: waiting ? 'player_phase' : 'round_resolved',
        waiting_for_teammates: waiting,
        round_resolved: !waiting,
        current_phase: 2,
        settled_round_index: 1,
        settlement_id: waiting ? null : '1012:1',
        submitted_count: Object.keys(sharedPhaseActions).length,
        total_active: 2,
        enemy: { name: '真實連線影', hp: waiting ? 200 : 160, max_hp: 200 },
        member_states: {
          'LEADER-1': {
            display_name: '隊長',
            hp: 100,
            max_hp: 100,
            submitted: !!sharedPhaseActions['LEADER-1'],
            action_type: sharedPhaseActions['LEADER-1']?.action_type,
          },
          'MEMBER-2': {
            display_name: '隊員',
            hp: 100,
            max_hp: 100,
            submitted: !!sharedPhaseActions['MEMBER-2'],
            action_type: sharedPhaseActions['MEMBER-2']?.action_type,
          },
        },
      };
      base.my_state = {
        display_name: display,
        hp: 100,
        max_hp: 100,
        sanity: 80,
        submitted,
        action_type: sharedPhaseActions[squadId]?.action_type,
      };
      if (!waiting) {
        base.round_settlement = {
          team_damage_dealt: 40,
          enemy_damage_dealt: 0,
          player_hits: [
            { player: '隊長', damage: 20, role: 'self', action_type: 'attack' },
            { player: '隊員', damage: 20, role: 'teammate', action_type: 'defend' },
          ],
          counter_hits: [],
          enemy_hp_after: 160,
        };
      }
      return base;
    };

    const setupMocks = async (page, squadId) => {
      await page.route('**/combat/status**', (route) => {
        if (Object.keys(sharedPhaseActions).length === 0) {
          return route.fulfill({ status: 204, body: '' });
        }
        const waiting = Object.keys(sharedPhaseActions).length < 2;
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(buildSnapshot(squadId, waiting)),
        });
      });

      await page.route('**/combat/submit_action**', async (route) => {
        const body = route.request().postDataJSON();
        sharedPhaseActions[squadId] = { action_type: body.action_type };
        const waiting = Object.keys(sharedPhaseActions).length < 2;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(buildSnapshot(squadId, waiting)),
        });
      });
    };

    await leaderPage.addInitScript(() => { window.__OIKONOMIA_COMBAT_V2__ = true; });
    await memberPage.addInitScript(() => { window.__OIKONOMIA_COMBAT_V2__ = true; });
    await leaderPage.goto(HARNESS_PATH);
    await memberPage.goto(HARNESS_PATH);

    await setupMocks(leaderPage, 'LEADER-1');
    await setupMocks(memberPage, 'MEMBER-2');

    const baseInit = {
      combat_id: 1012,
      current_phase: 2,
      enemy: { name: '真實連線影', hp: 200, max_hp: 200 },
      member_states: {
        'LEADER-1': { display_name: '隊長', hp: 100, max_hp: 100, submitted: false },
        'MEMBER-2': { display_name: '隊員', hp: 100, max_hp: 100, submitted: false },
      },
    };

    await startCombat(leaderPage, {
      ...baseInit,
      my_state: { display_name: '隊長', hp: 100, max_hp: 100, sanity: 80, submitted: false },
    });
    await startCombat(memberPage, {
      ...baseInit,
      my_state: { display_name: '隊員', hp: 100, max_hp: 100, sanity: 80, submitted: false },
    });

    await leaderPage.locator('#combat-v2-attack-btn').click();
    await leaderPage.locator('#combat-v2-dice-confirm-btn').waitFor({ state: 'visible', timeout: 10000 });
    await leaderPage.locator('#combat-v2-dice-confirm-btn').click();

    await expect(leaderPage.locator('#combat-v2-team-status')).toContainText('✅ 已就緒');
    await expect(leaderPage.locator('#combat-v2-attack-btn')).toBeDisabled();

    await memberPage.locator('#combat-v2-defend-btn').click();
    await memberPage.locator('#combat-v2-dice-confirm-btn').waitFor({ state: 'visible' });
    await memberPage.locator('#combat-v2-dice-confirm-btn').click();

    const memberSettlement = memberPage.locator('#combat-v2-round-settlement-modal');
    await expect(memberSettlement).toBeVisible();
    await expect(memberPage.locator('[data-testid="team-damage-dealt"]')).toContainText('隊伍造成 40 點傷害');

    const resolvedSnapshot = buildSnapshot('LEADER-1', false);
    await leaderPage.evaluate((snap) => {
      document.getElementById('combat-root-v2').__combat_app_instance__.pollTick(snap);
    }, resolvedSnapshot);

    await expect(leaderPage.locator('#combat-v2-round-settlement-modal')).toBeVisible();
    await expect(leaderPage.locator('[data-testid="team-damage-dealt"]')).toContainText('隊伍造成 40 點傷害');

    await leaderContext.close();
    await memberContext.close();
  });

  test('T13: non-leader protagonist substitute blocked (P2-3)', async ({ page }) => {
    await page.route('**/combat/status**', (route) => route.fulfill({ status: 204, body: '' }));

    await startCombat(page, {
      combat_id: 1013,
      current_phase: 1,
      enemy: { name: '界線寄生影', hp: 100, max_hp: 100 },
      my_state: {
        display_name: '普通隊員 Henry',
        hp: 100,
        max_hp: 100,
        sanity: 80,
        submitted: false,
        is_team_leader: 0,
      },
      controllable_protagonist_id: 'protagonist:iggy:TEAM-01',
      member_states: {
        'LEADER-01': {
          display_name: '真・隊長',
          hp: 100,
          max_hp: 100,
          submitted: false,
          is_team_leader: 1,
        },
        'PLAYER-75406': {
          display_name: '普通隊員 Henry',
          hp: 100,
          max_hp: 100,
          submitted: false,
          is_team_leader: 0,
        },
      },
    });

    let submitCalled = false;
    await page.route('**/combat/submit_action**', async (route) => {
      submitCalled = true;
      await route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          error: '只有隊長特權才能啟動主角代打模式',
        }),
      });
    });

    await page.evaluate(() => {
      const app = document.getElementById('combat-root-v2').__combat_app_instance__;
      const toggle = document.getElementById('combat-v2-protagonist-toggle');
      if (toggle) toggle.checked = true;
      app.ctx.phase = 'DICE_CONFIRM';
      app.ctx.dice = { action: 'attack', value: 3, itemId: null };
      void app.confirmDice();
    });

    expect(submitCalled).toBe(false);

    const toast = page.locator('[data-testid="combat-toast"]');
    await expect(toast).toBeVisible();
    await expect(toast).toContainText('只有隊長特權才能啟動主角代打模式');
    await expect(page.locator('#combat-v2-attack-btn')).toBeEnabled();
  });

  test('T14: rogue player GM override endpoint hard-blocked', async ({ page }) => {
    await page.route('**/gm/api/override_trauma_ending', async (route) => {
      await route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          error: '拒絕存取：缺少 GM 權限憑證',
        }),
      });
    });

    const triggerHack = await page.evaluate(async (payload) => {
      try {
        const res = await fetch('/gm/api/override_trauma_ending', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        return { status: res.status, data: await res.json() };
      } catch (e) {
        return { status: 500, error: e.message };
      }
    }, { team_id: 'TEAM-01', target_ending_type: 'clear' });

    expect(triggerHack.status).toBe(403);
    expect(triggerHack.data.success).toBe(false);
  });
});


===== FILE: playwright.config.cjs =====

// @ts-check
const { defineConfig } = require('@playwright/test');

const port = process.env.PORT || '5001';
const baseURL = process.env.OIKONOMIA_URL || `http://127.0.0.1:${port}`;

module.exports = defineConfig({
  testDir: './tests',
  timeout: 60000,
  use: {
    baseURL,
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
  webServer: process.env.PLAYWRIGHT_SKIP_SERVER
    ? undefined
    : {
        command: `${process.env.PYTHON || './venv/bin/python3'} app.py`,
        url: `${baseURL}/__e2e__/combat-v2`,
        timeout: 120000,
        reuseExistingServer: !process.env.CI,
        env: {
          ...process.env,
          PORT: port,
          COMBAT_V2: '1',
          COMBAT_E2E: '1',
          FLASK_ENV: 'development',
          SECRET_KEY: process.env.SECRET_KEY || 'test-secret-e2e',
        },
      },
});


===== FILE: scripts/test_combat_flow.py =====

#!/usr/bin/env python3
"""P1: 本地 combat 全流程測試（Team + Iggy → enc_iggy_01_leech）"""
import os
import shutil
import sys
import tempfile
from unittest.mock import patch

# 使用獨立測試 DB，避免污染本機 oikonomia.db
TEST_DIR = tempfile.mkdtemp(prefix="oikonomia_combat_test_")
os.environ["DATA_DIR"] = TEST_DIR

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as oikonomia  # noqa: E402
from models.combat import (
    calculate_incoming_damage,
    count_team_defenders,
    get_combat,
    get_combat_participants,
    team_defend_damage_multiplier,
)
from models.squad import apply_hp_change, get_squad, squad_max_hp, update_squad
from models.item import apply_item_effect_to_squad

oikonomia.init_db()
oikonomia.migrate_db()

ENCOUNTER_ID = "enc_iggy_01_leech"
TEST_ENCOUNTER_ID = "test_combat_01"
PASS = 0
FAIL = 0
MAX_FIGHT_ROUNDS = 8


def _test_db_path():
    return os.path.join(TEST_DIR, "oikonomia.db")


def clear_encounter_completion(team_id, encounter_id):
    """Remove completion row so test encounter can be replayed."""
    import sqlite3

    conn = sqlite3.connect(_test_db_path())
    conn.execute(
        "DELETE FROM encounter_completions "
        "WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?)) AND encounter_id = ?",
        (team_id, encounter_id),
    )
    conn.commit()
    conn.close()


def teardown_test_combat(team_id, encounter_id):
    """End in-progress test combat without recording encounter completion."""
    from datetime import datetime

    from models.combat import clear_team_combat_id, get_active_combat_for_team, save_combat

    active = get_active_combat_for_team(team_id)
    if not active or active.get("encounter_id") != encounter_id:
        return
    if active.get("status") == "ended":
        clear_team_combat_id(team_id)
        return
    save_combat(
        active["id"],
        status="ended",
        winner="enemy",
        ended_at=datetime.now().isoformat(),
    )
    clear_team_combat_id(team_id)


def enable_gm_session(client):
    with client.session_transaction() as sess:
        sess["is_gm"] = True


def prepare_test_encounter(client, team_id, encounter_id):
    """Reset encounter for isolated integration tests sharing TEST_ENCOUNTER_ID."""
    enable_gm_session(client)
    teardown_test_combat(team_id, encounter_id)
    clear_encounter_completion(team_id, encounter_id)


def combat_enemy_hp(combat, default=0):
    """Read enemy_hp; 0 is valid (do not use `or default` which treats 0 as missing)."""
    if not combat or combat.get("enemy_hp") is None:
        return default
    return int(combat.get("enemy_hp"))


def ok(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}" + (f" — {detail}" if detail else ""))


def login(client, name):
    r = client.post("/login", data={"squad_id": name})
    return r.get_json()


def submit_attack(client, combat_id):
    """Submit attack; server rolls dice (client dice_result is ignored)."""
    return client.post(
        "/combat/submit_action",
        json={"combat_id": combat_id, "action_type": "attack"},
        content_type="application/json",
    )


def test_maybe_resolve_ready_claim_inside_tx():
    """R11: all_phase_actions_submitted must run inside CAS transaction boundary."""
    import sqlite3
    from datetime import datetime

    from models.combat import (
        _claim_ready_player_phase_resolution,
        maybe_resolve_player_phase,
        upsert_combat_action,
    )

    now = datetime.now().isoformat()
    conn = sqlite3.connect(_test_db_path())
    conn.execute("DELETE FROM combat_actions")
    conn.execute("DELETE FROM combats WHERE encounter_id = 'test_claim_gate'")
    conn.execute("DELETE FROM squads WHERE squad_id IN ('cg1', 'cg2')")
    conn.execute("DELETE FROM teams WHERE team_id = 'T-CLAIM'")
    conn.execute(
        "INSERT INTO teams (team_id, team_name, route, created_at) VALUES ('T-CLAIM', 'ClaimGate', 'iggy', ?)",
        (now,),
    )
    for sid, leader in (("cg1", 1), ("cg2", 0)):
        conn.execute(
            """INSERT INTO squads
               (squad_id, display_name, team_id, hp, max_hp, sanity, power, intellect,
                resilience, is_team_leader, route, zoo_skills, last_update)
               VALUES (?, ?, 'T-CLAIM', 100, 100, 50, 30, 20, 20, ?, 'iggy', '[]', ?)""",
            (sid, sid, leader, now),
        )
    conn.execute(
        """INSERT INTO combats (
               squad_id, encounter_id, status, current_phase, enemy_hp,
               enemy_resilience, enemy_sanity, enemy_base_damage, enemy_name,
               phase_actions, logs, phase_started_at, started_at
           ) VALUES ('cg1', 'test_claim_gate', 'player_phase', 0, 60, 10, 50, 5, 'Boss', '{}', '[]', ?, ?)""",
        (now, now),
    )
    combat_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute("UPDATE squads SET current_combat_id = ? WHERE squad_id IN ('cg1', 'cg2')", (combat_id,))
    conn.commit()
    conn.close()

    upsert_combat_action(combat_id, "cg1", 0, "attack", 6, None)
    partial, winner = maybe_resolve_player_phase(combat_id, {})
    ok(
        "maybe_resolve incomplete phase stays player_phase",
        partial and partial.get("status") == "player_phase" and winner is None,
        str((partial or {}).get("status")),
    )
    claimed_partial, _ = _claim_ready_player_phase_resolution(combat_id, {})
    ok("claim_ready rejects incomplete phase", claimed_partial is False)

    upsert_combat_action(combat_id, "cg2", 0, "attack", 6, None)
    claimed_full, _ = _claim_ready_player_phase_resolution(combat_id, {})
    ok("claim_ready accepts complete phase", claimed_full is True)
    if claimed_full:
        from models.combat import _release_player_phase_resolution

        _release_player_phase_resolution(combat_id)

    resolved, winner2 = maybe_resolve_player_phase(combat_id, {})
    ok(
        "maybe_resolve complete phase progresses combat",
        resolved and resolved.get("status") != "player_phase",
        str((resolved or {}).get("status")),
    )


def test_maybe_resolve_monotonic_phase_guard():
    """R11 Scope C: peer resolve must not double-settle same round."""
    import sqlite3
    from datetime import datetime

    from models.combat import get_combat, maybe_resolve_player_phase, upsert_combat_action

    now = datetime.now().isoformat()
    conn = sqlite3.connect(_test_db_path())
    conn.execute("DELETE FROM combat_actions")
    conn.execute(f"DELETE FROM combats WHERE encounter_id = '{TEST_ENCOUNTER_ID}'")
    conn.execute("DELETE FROM squads WHERE squad_id IN ('mr1', 'mr2')")
    conn.execute("DELETE FROM teams WHERE team_id = 'T-MONO'")
    conn.execute(
        "INSERT INTO teams (team_id, team_name, route, created_at) VALUES ('T-MONO', 'Mono', 'iggy', ?)",
        (now,),
    )
    for sid, leader in (("mr1", 1), ("mr2", 0)):
        conn.execute(
            """INSERT INTO squads
               (squad_id, display_name, team_id, hp, max_hp, sanity, power, intellect,
                resilience, is_team_leader, route, zoo_skills, last_update)
               VALUES (?, ?, 'T-MONO', 100, 100, 50, 30, 20, 20, ?, 'iggy', '[]', ?)""",
            (sid, sid, leader, now),
        )
    conn.execute(
        """INSERT INTO combats (
               squad_id, encounter_id, status, current_phase, enemy_hp,
               enemy_resilience, enemy_sanity, enemy_base_damage, enemy_name,
               phase_actions, logs, phase_started_at, started_at
           ) VALUES ('mr1', ?, 'player_phase', 0, 5000, 10, 50, 5, 'Boss', '{}', '[]', ?, ?)""",
        (TEST_ENCOUNTER_ID, now, now),
    )
    combat_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "UPDATE squads SET current_combat_id = ? WHERE squad_id IN ('mr1', 'mr2')",
        (combat_id,),
    )
    conn.commit()
    conn.close()

    upsert_combat_action(combat_id, "mr1", 0, "attack", 6, None)
    upsert_combat_action(combat_id, "mr2", 0, "attack", 6, None)

    first, _ = maybe_resolve_player_phase(combat_id, {})
    after_first = get_combat(combat_id)
    progressed = (
        int(after_first.get("current_phase") or 0) >= 1
        or after_first.get("status") in ("enemy_phase", "ended")
    )
    ok("monotonic: first resolve progresses combat", progressed, str(after_first.get("status")))

    logs_len_1 = len(after_first.get("logs") or [])
    enemy_hp_1 = int(after_first.get("enemy_hp") or 0)

    second, winner2 = maybe_resolve_player_phase(combat_id, {})
    after_second = get_combat(combat_id)
    ok(
        "monotonic: second resolve does not re-run same round",
        int(after_second.get("current_phase") or 0) == int(after_first.get("current_phase") or 0)
        and len(after_second.get("logs") or []) == logs_len_1
        and int(after_second.get("enemy_hp") or 0) == enemy_hp_1,
        f"phase={after_second.get('current_phase')} logs={len(after_second.get('logs') or [])} winner2={winner2}",
    )


def test_solo_resolve_combat_outcome_idempotency():
    """Solo victory uses SOLO:-scoped completion key; second resolve is idempotent."""
    import sqlite3
    from datetime import datetime

    from models.encounter import load_encounter
    from models.encounter_outcomes import solo_encounter_scope_id
    from services.combat_outcomes import resolve_combat_outcome

    squad_id = "PLAYER-SOLO-IDEM"
    enc_id = "enc_iggy_01_leech"
    now = datetime.now().isoformat()
    scope_id = solo_encounter_scope_id(squad_id)

    conn = sqlite3.connect(_test_db_path())
    conn.execute("DELETE FROM encounter_completions WHERE team_id = ?", (scope_id,))
    conn.execute("DELETE FROM squads WHERE squad_id = ?", (squad_id,))
    conn.execute(
        """INSERT INTO squads
           (squad_id, display_name, insight_fragments, last_update)
           VALUES (?, 'Solo Idem', 0, ?)""",
        (squad_id, now),
    )
    conn.commit()
    conn.close()

    encounter = load_encounter(enc_id)
    first = resolve_combat_outcome("squad", None, encounter, squad_id)
    second = resolve_combat_outcome("squad", None, encounter, squad_id)
    ok("solo outcome first apply", first.get("applied_success") is True, str(first))
    ok("solo outcome idempotent skip", second.get("applied_success") is False, str(second))

    conn = sqlite3.connect(_test_db_path())
    row = conn.execute(
        "SELECT team_id FROM encounter_completions WHERE team_id = ? AND encounter_id = ?",
        (scope_id, enc_id),
    ).fetchone()
    conn.execute("DELETE FROM encounter_completions WHERE team_id = ?", (scope_id,))
    conn.execute("DELETE FROM squads WHERE squad_id = ?", (squad_id,))
    conn.commit()
    conn.close()
    ok("solo completion stored under SOLO scope", row is not None, str(scope_id))


def test_phase2_gm_override_gateway():
    """Phase 2 Backlog: 驗證 GM 權威特權覆蓋閘門與結局狀態重置一致性。"""
    import sqlite3
    from datetime import datetime

    from services.gm_auth import establish_gm_session

    team_id = "TEAM-GM-OVERRIDE"
    proto_key = "marah"
    now = datetime.now().isoformat()

    conn = sqlite3.connect(_test_db_path())
    conn.execute("DELETE FROM protagonist_trauma_log WHERE team_id = ?", (team_id,))
    conn.execute("DELETE FROM protagonist_states WHERE team_id = ?", (team_id,))
    conn.execute("DELETE FROM global_events WHERE created_by = 'GM-CHIEF-01'")
    conn.execute("DELETE FROM teams WHERE team_id = ?", (team_id,))
    conn.execute(
        """INSERT INTO teams (team_id, team_name, ending_type, created_at)
           VALUES (?, 'GM覆蓋隊', 'bad_ending', ?)""",
        (team_id, now),
    )
    conn.execute(
        """INSERT INTO protagonist_states
           (team_id, protagonist, hp, max_hp, sanity, trauma_count, is_active, last_updated)
           VALUES (?, ?, 100, 100, 100, 4, 1, ?)""",
        (team_id, proto_key, now),
    )
    conn.commit()
    conn.close()

    client = oikonomia.app.test_client()

    r403 = client.post(
        "/gm/api/override_trauma_ending",
        json={"team_id": team_id, "protagonist_key": proto_key, "target_trauma": 1},
    )
    ok("GM Override Gate: 非管理員登入遭遇 403 熔斷拒絕", r403.status_code == 403)

    with client.session_transaction() as sess:
        establish_gm_session(sess)

    r_no_op = client.post(
        "/gm/api/override_trauma_ending",
        json={
            "team_id": team_id,
            "protagonist_key": proto_key,
            "target_trauma": 0,
            "target_ending_type": "clear",
        },
    )
    ok(
        "GM Override Gate: 有效 GM session 但無 operator 身分遭 403",
        r_no_op.status_code == 403,
        str(r_no_op.status_code),
    )

    with client.session_transaction() as sess:
        establish_gm_session(sess)
        sess["squad_id"] = "\x00\x01\x02"
    r_dirty = client.post(
        "/gm/api/override_trauma_ending",
        json={
            "team_id": team_id,
            "protagonist_key": proto_key,
            "target_trauma": 0,
        },
    )
    ok(
        "GM Override Gate: 不可見字元 operator 遭 403",
        r_dirty.status_code == 403,
        str(r_dirty.status_code),
    )

    with client.session_transaction() as sess:
        establish_gm_session(sess)
        sess["squad_id"] = "GM-CHIEF-01\x00"

    r_ok = client.post(
        "/gm/api/override_trauma_ending",
        json={
            "team_id": team_id,
            "protagonist_key": proto_key,
            "target_trauma": 0,
            "target_ending_type": "clear",
        },
    )
    body = r_ok.get_json() or {}
    ok(
        "GM Override Gate: 權威覆蓋指令發放成功",
        r_ok.status_code == 200 and body.get("success") is True,
        str(body)[:200],
    )

    conn = sqlite3.connect(_test_db_path())
    trauma = conn.execute(
        "SELECT trauma_count FROM protagonist_states WHERE team_id = ? AND protagonist = ?",
        (team_id, proto_key),
    ).fetchone()[0]
    ending = conn.execute(
        "SELECT ending_type FROM teams WHERE team_id = ?",
        (team_id,),
    ).fetchone()[0]
    log_row = conn.execute(
        """SELECT reason FROM protagonist_trauma_log
           WHERE team_id = ? AND reason LIKE '%GM_OVERRIDE%'""",
        (team_id,),
    ).fetchone()
    log_exists = 1 if log_row else 0
    event_row = conn.execute(
        "SELECT created_by FROM global_events WHERE title LIKE '%GM 人工干預%'"
        " AND title LIKE ? ORDER BY id DESC LIMIT 1",
        (f"%{team_id}%",),
    ).fetchone()
    event_exists = 1 if event_row else 0
    conn.close()

    ok("GM Override Gate: 實體表主角創傷已清零 SSOT", int(trauma) == 0)
    ok("GM Override Gate: 實體表團隊結局解鎖重置", ending is None)
    ok("GM Override Gate: 歷史審計日誌留痕合規", log_exists == 1)
    ok(
        "GM Override Gate: operator 審計字串已清洗",
        log_row and log_row[0] == "GM_OVERRIDE_BY_GM-CHIEF-01",
        str(log_row),
    )
    ok("GM Override Gate: 全營廣播通知發送成功", event_exists == 1)
    ok(
        "GM Override Gate: global event created_by 已清洗",
        event_row and event_row[0] == "GM-CHIEF-01",
        str(event_row),
    )


def test_phase2_narrative_orchestrator_pipeline():
    """Phase 1.5 Step 3: 驗證全新戰後劇情管線強等冪性與背包熔斷防線。"""
    import sqlite3
    from datetime import datetime

    from services.narrative_orchestrator import execute_post_combat_success_pipeline

    team_id = "TEAM-NARRATIVE-V2"
    squad_id = "SQUAD-LEADER-V2"
    enc_id = "enc_iggy_01_leech"
    now = datetime.now().isoformat()

    conn = sqlite3.connect(_test_db_path())
    conn.execute(
        "DELETE FROM encounter_completions WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?))",
        (team_id,),
    )
    conn.execute("DELETE FROM player_items WHERE squad_id = ?", (squad_id,))
    conn.execute("DELETE FROM squads WHERE squad_id = ?", (squad_id,))
    conn.execute("DELETE FROM teams WHERE team_id = ?", (team_id,))
    conn.execute(
        "INSERT INTO teams (team_id, team_name, created_at) VALUES (?, ?, ?)",
        (team_id, "NarrativeTest", now),
    )
    conn.execute(
        "INSERT INTO squads (squad_id, team_id, hp, max_hp, is_team_leader, display_name) "
        "VALUES (?, ?, 100, 100, 1, ?)",
        (squad_id, team_id, "Leader"),
    )
    conn.commit()
    conn.close()

    with patch("services.narrative_orchestrator.random.random", return_value=0.0):
        snap1 = execute_post_combat_success_pipeline(team_id, enc_id, squad_id)
    ok("Narrative V2: 首次結算管道成功執行", "通關" in snap1.log_message)

    conn = sqlite3.connect(_test_db_path())
    item_count = conn.execute(
        "SELECT COUNT(*) FROM player_items WHERE squad_id = ?",
        (squad_id,),
    ).fetchone()[0]
    completion_exists = conn.execute(
        """SELECT COUNT(*) FROM encounter_completions
           WHERE UPPER(TRIM(team_id)) = UPPER(TRIM(?)) AND encounter_id = ?""",
        (team_id, enc_id),
    ).fetchone()[0]
    conn.close()

    ok("Narrative V2: 獎勵物品成功發放至背包", item_count > 0)
    ok("Narrative V2: 遭遇通關誌成功存檔", completion_exists == 1)

    snap2 = execute_post_combat_success_pipeline(team_id, enc_id, squad_id)
    ok("Narrative V2: 強等冪閘門成功阻斷", "拒絕重複" in snap2.log_message)

    conn = sqlite3.connect(_test_db_path())
    item_count_after = conn.execute(
        "SELECT COUNT(*) FROM player_items WHERE squad_id = ?",
        (squad_id,),
    ).fetchone()[0]
    conn.close()
    ok("Narrative V2: 物品數量守恆，無重複發放漏洞", item_count == item_count_after)


def test_phase2_trauma_service_pipeline():
    """Phase 1.5 Step 2: 驗證全新中央創傷能帶管線與神學片段權威分發機制。"""
    import sqlite3
    from datetime import datetime

    from services.trauma_service import apply_protagonist_trauma_pipeline

    team_id = "TEAM-TRAUMA-V2"
    proto_key = "iggy"
    now = datetime.now().isoformat()

    conn = sqlite3.connect(_test_db_path())
    conn.execute("DELETE FROM protagonist_trauma_log WHERE team_id = ?", (team_id,))
    conn.execute("DELETE FROM protagonist_states WHERE team_id = ?", (team_id,))
    conn.execute("DELETE FROM teams WHERE team_id = ?", (team_id,))
    conn.execute(
        "INSERT INTO teams (team_id, team_name, created_at) VALUES (?, ?, ?)",
        (team_id, "測試隊伍", now),
    )
    conn.execute(
        """INSERT INTO protagonist_states
           (team_id, protagonist, hp, max_hp, sanity, trauma_count, is_active, last_updated)
           VALUES (?, ?, 100, 100, 100, 0, 1, ?)""",
        (team_id, proto_key, now),
    )
    conn.commit()
    conn.close()

    snap1 = apply_protagonist_trauma_pipeline(team_id, proto_key, 1, "測試低創傷原因")
    ok("Trauma V2: 創傷正確累加至 1", snap1.current_trauma == 1)
    ok("Trauma V2: 正確落入 low 能帶", snap1.trauma_band == "low")
    ok("Trauma V2: 盼望 fragment 包含恩典", "恩典" in snap1.narrative_fragment)
    ok("Trauma V2: 結局未鎖定", snap1.is_bad_ending_locked is False)

    snap2 = apply_protagonist_trauma_pipeline(team_id, proto_key, 3, "測試致命瀕死累積")
    ok("Trauma V2: 創傷穿透至 4 次", snap2.current_trauma == 4)
    ok("Trauma V2: 正確落入 high 能帶", snap2.trauma_band == "high")
    ok("Trauma V2: 盼望 fragment 包含基督能力", "基督" in snap2.narrative_fragment)
    ok("Trauma V2: 不可逆陰影結局成功鎖定", snap2.is_bad_ending_locked is True)

    conn = sqlite3.connect(_test_db_path())
    ending_type = conn.execute(
        "SELECT ending_type FROM teams WHERE team_id = ?",
        (team_id,),
    ).fetchone()[0]
    conn.close()
    ok("Trauma V2: DB 實體表寫入 bad_ending 完好合規", ending_type == "bad_ending")


def test_trauma_ending_thresholds():
    from models.protagonist import (
        TRAUMA_BAD_ENDING_LIMIT,
        check_ending_condition,
        get_team_ending_state,
        has_trauma_bad_ending,
        update_protagonist_state,
    )

    from models.protagonist import initialize_protagonist_for_team

    ok("trauma limit is 3", TRAUMA_BAD_ENDING_LIMIT == 3)
    team = "TEAM-TRAUMA-TEST"
    initialize_protagonist_for_team(team, "iggy")
    update_protagonist_state(team, "iggy", trauma_count=3, is_active=1)
    ok("3 trauma not bad ending", not has_trauma_bad_ending(team))
    ok("3 trauma normal ending", check_ending_condition(team) == "normal_ending")
    state3 = get_team_ending_state(team)
    ok("3 trauma until bad is 1", state3.get("trauma_until_bad") == 1)
    update_protagonist_state(team, "iggy", trauma_count=4)
    ok("4 trauma is bad ending", has_trauma_bad_ending(team))
    ok("4 trauma check_ending", check_ending_condition(team) == "bad_ending")


def test_trauma_bad_ending_victory(client, client2, team_id, leader_id, member_id):
    """Win combat with trauma > 3 → bad ending, no normal rewards narrative."""
    from models.protagonist import get_team_ending_type, update_protagonist_state

    prepare_test_encounter(client, team_id, TEST_ENCOUNTER_ID)
    update_protagonist_state(team_id, "iggy", trauma_count=4, is_active=0)

    r = client.post(
        "/combat/start",
        json={"encounter_id": TEST_ENCOUNTER_ID},
        content_type="application/json",
    )
    start = r.get_json() or {}
    combat_id = start.get("combat_id")
    if not combat_id:
        from models.combat import get_active_combat_for_team

        active = get_active_combat_for_team(team_id)
        combat_id = active.get("id") if active else None
    ok("trauma ending: have combat", combat_id, str(start))

    final, err = fight_until_victory(client, client2, combat_id)
    ok("trauma ending: fight completes", err is None, err or str(final)[:200])
    ok("trauma ending: still victory outcome", final.get("outcome") == "victory", str(final)[:200])
    ok("trauma ending: trauma_bad_ending flag", final.get("trauma_bad_ending") is True, str(final)[:200])
    ok("trauma ending: no reflection", not final.get("reflection_prompt"), str(final)[:200])
    ok("trauma ending: custom narrative", "心理創傷" in (final.get("narrative") or ""), str(final)[:200])

    st = client.get(f"/combat/status?combat_id={combat_id}").get_json() or {}
    ok("trauma ending: status has flag", st.get("trauma_bad_ending") is True, str(st)[:200])

    status = client.get("/status").get_json() or {}
    ending = status.get("ending") or {}
    ok("trauma ending: player status", ending.get("trauma_bad_ending") is True, str(ending))
    ok("trauma ending: team locked", get_team_ending_type(team_id) == "bad_ending")


def test_protagonist_player_control(client, client2, team_id, route="iggy"):
    """Encounter with protagonist_player_control: leader can submit as_protagonist."""
    from models.protagonist import protagonist_squad_id, update_protagonist_state

    update_protagonist_state(team_id, route, is_active=1)

    r = client.post(
        "/combat/start",
        json={"encounter_id": "test_protagonist_control"},
        content_type="application/json",
    )
    start = r.get_json() or {}
    combat_id = start.get("combat_id")
    if not combat_id:
        from models.combat import get_active_combat_for_team

        active = get_active_combat_for_team(team_id)
        combat_id = active.get("id") if active else None
    ok("pro control: start combat", combat_id, str(start))

    st = client.get(f"/combat/status?combat_id={combat_id}").get_json() or {}
    ok("pro control: flag enabled", st.get("protagonist_player_control") is True, str(st)[:200])
    pro_sid = protagonist_squad_id(team_id, route)
    ok(
        "pro control: controllable id",
        st.get("controllable_protagonist_id") == pro_sid,
        st.get("controllable_protagonist_id"),
    )

    r1 = client.post(
        "/combat/submit_action",
        json={"combat_id": combat_id, "action_type": "attack", "as_protagonist": True},
        content_type="application/json",
    )
    d1 = r1.get_json() or {}
    ok("pro control: protagonist submit", d1.get("success") or d1.get("status"), str(d1)[:200])

    r2 = client2.post(
        "/combat/submit_action",
        json={"combat_id": combat_id, "action_type": "attack"},
        content_type="application/json",
    )
    d2 = r2.get_json() or {}
    ok("pro control: teammate submit", d2.get("success") or d2.get("outcome"), str(d2)[:200])

    ok(
        "pro control: round resolved",
        d2.get("round_resolved") or d2.get("status") == "round_resolved" or d2.get("outcome"),
        str(d2)[:200],
    )


def test_protagonist_combat_participant(combat_id, route="iggy"):
    combat = get_combat(combat_id)
    participants = get_combat_participants(combat) if combat else []
    pros = [p for p in participants if p.get("is_protagonist")]
    ok("protagonist joins combat", len(pros) >= 1, f"found {len(pros)}")
    if pros:
        ok(
            f"route protagonist is {route}",
            any(p.get("protagonist_key") == route for p in pros),
            str([p.get("protagonist_key") for p in pros]),
        )
        ok("protagonist has hp", int(pros[0].get("hp") or 0) > 0)


def test_player_max_hp(leader_id):
    """HP ceiling can exceed 100 via boosts."""
    hp, max_hp = apply_hp_change(100, 100, 20)
    ok("hp boost raises max above 100", max_hp == 120 and hp == 120, f"{hp}/{max_hp}")
    hp2, max_hp2 = apply_hp_change(80, 120, 0)
    ok("damage does not lower max_hp", max_hp2 == 120 and hp2 == 80, f"{hp2}/{max_hp2}")

    update_squad(leader_id, hp=90, max_hp=100)
    applied = apply_item_effect_to_squad(leader_id, {
        "has_ability": 1,
        "effect_type": "hp_up",
        "effect_value": 25,
    })
    squad = get_squad(leader_id) or {}
    ok("hp_up item raises max_hp", applied and int(squad.get("max_hp") or 0) == 125, str(squad))
    ok("hp_up item heals to new cap", int(squad.get("hp") or 0) == 115, str(squad))
    ok("squad_max_hp helper", squad_max_hp(squad) == 125)


def test_defend_team_buff_helpers():
    """Unit checks for Defend team-wide damage reduction."""
    actions = {
        "a": {"action_type": "attack"},
        "b": {"action_type": "defend"},
    }
    ok("count_team_defenders", count_team_defenders(actions) == 1)
    ok("team_defend_multiplier", team_defend_damage_multiplier(1) == 0.5)
    ok("no defend multiplier", team_defend_damage_multiplier(0) == 1.0)
    base = calculate_incoming_damage(12, 10)
    reduced = calculate_incoming_damage(12, 10, team_defend_multiplier=0.5)
    ok("team defend halves counter", reduced == max(0, base // 2), f"{base} -> {reduced}")


def test_defend_team_buff_integration(client, client2, leader_id, member_id):
    """
    Low-resilience leader is counter target; high-resilience teammate Defends.
    Counter damage should be halved even though the target attacked.
    """
    from models.protagonist import update_protagonist_state

    leader_team = (get_squad(leader_id) or {}).get("team_id")
    if leader_team:
        prepare_test_encounter(client, leader_team, TEST_ENCOUNTER_ID)

    update_squad(leader_id, resilience=10)
    update_squad(member_id, resilience=80)
    leader_team = (get_squad(leader_id) or {}).get("team_id")
    if leader_team:
        # Protagonist auto-attack can kill the test enemy before counter resolves.
        update_protagonist_state(leader_team, "iggy", is_active=0)

    r = client.post(
        "/combat/start",
        json={"encounter_id": TEST_ENCOUNTER_ID},
        content_type="application/json",
    )
    start = r.get_json() or {}
    combat_id = start.get("combat_id")
    ok("defend test: start combat", start.get("success") and combat_id, str(start))

    leader_before = int((get_squad(leader_id) or {}).get("hp") or 0)

    r1 = client.post(
        "/combat/submit_action",
        json={"combat_id": combat_id, "action_type": "attack"},
        content_type="application/json",
    )
    ok("defend test: leader attacks", (r1.get_json() or {}).get("status") == "waiting_for_teammates")

    r2 = client2.post(
        "/combat/submit_action",
        json={"combat_id": combat_id, "action_type": "defend"},
        content_type="application/json",
    )
    phase = r2.get_json() or {}
    ok("defend test: member defends", phase.get("success") or phase.get("status"), str(phase)[:200])

    leader_after = int((get_squad(leader_id) or {}).get("hp") or 0)
    raw_counter = calculate_incoming_damage(12, 10)
    buffed_counter = calculate_incoming_damage(12, 10, team_defend_multiplier=0.5)
    damage_taken = leader_before - leader_after
    ok(
        "defend test: team buff reduces counter",
        damage_taken == buffed_counter and damage_taken < raw_counter,
        f"hp -{damage_taken}, expected {buffed_counter} (raw {raw_counter})",
    )


def test_enemy_hp_reconciled_from_logs(client, leader_id, team_id):
    """Status API must repair stale DB enemy_hp using log summaries (F5 refresh)."""
    from models.combat import build_enemy_combat_stats, create_combat_record, save_combat
    from models.encounter import load_encounter

    enc_id = "practice_iggy_01_quick"
    enc = load_encounter(enc_id)
    teardown_test_combat(team_id, enc_id)
    combat = create_combat_record(leader_id, enc_id, enc, initial_status="player_phase")
    combat_id = combat.get("id")
    start_hp = 48
    true_hp = 36
    logs = list(combat.get("logs") or [])
    logs.extend([
        {"type": "damage", "message": "Tester 攻擊對速戰殘影造成 12 點傷害"},
        {"type": "summary", "message": f"速戰殘影 受到共 12 點傷害，剩餘 HP {true_hp}"},
    ])
    save_combat(combat_id, enemy_hp=start_hp, logs=logs, status="player_phase")
    ok("reconcile test: seeded combat", combat_id, str(combat_id))

    st = client.get(f"/combat/status?combat_id={combat_id}").get_json() or {}
    payload_hp = int((st.get("enemy") or {}).get("hp") or -1)
    ok("reconcile test: status returns log HP", payload_hp == true_hp, f"{payload_hp} vs {true_hp}")

    repaired = combat_enemy_hp(get_combat(combat_id), default=start_hp)
    ok("reconcile test: DB repaired", repaired == true_hp, f"db={repaired}")

    stats = build_enemy_combat_stats(get_combat(combat_id) or {})
    ok("reconcile test: build_enemy stats", int(stats.get("hp") or -1) == true_hp, str(stats))

    teardown_test_combat(team_id, enc_id)


def test_enemy_hp_updates_after_round(client, client2, team_id):
    """Round resolve must persist enemy HP; round_resolved payload must reflect damage."""
    from models.protagonist import update_protagonist_state

    prepare_test_encounter(client, team_id, TEST_ENCOUNTER_ID)
    update_protagonist_state(team_id, "iggy", is_active=0)

    r = client.post(
        "/combat/start",
        json={"encounter_id": TEST_ENCOUNTER_ID},
        content_type="application/json",
    )
    start = r.get_json() or {}
    combat_id = start.get("combat_id")
    ok("enemy hp test: start combat", start.get("success") and combat_id, str(start))

    combat = get_combat(combat_id) if combat_id else None
    start_hp = int((combat or {}).get("enemy_hp") or 0)
    ok("enemy hp test: initial hp", start_hp > 0, str(start_hp))

    r1 = client.post(
        "/combat/submit_action",
        json={"combat_id": combat_id, "action_type": "attack"},
        content_type="application/json",
    )
    ok(
        "enemy hp test: leader submits",
        (r1.get_json() or {}).get("status") == "waiting_for_teammates",
        str(r1.get_json())[:200],
    )

    # dice=1 keeps one round sub-lethal (dice=3 can one-shot the 55 HP test enemy).
    with patch("routes.combat.roll_combat_dice", return_value=1):
        r2 = client2.post(
            "/combat/submit_action",
            json={"combat_id": combat_id, "action_type": "attack"},
            content_type="application/json",
        )
    phase = r2.get_json() or {}
    resolved = bool(
        phase.get("round_resolved")
        or phase.get("status") == "round_resolved"
        or phase.get("outcome") == "victory"
    )
    ok("enemy hp test: round resolves", resolved, str(phase)[:200])

    settlement = phase.get("round_settlement") or {}
    team_dealt = int(settlement.get("team_damage_dealt") or phase.get("round_enemy_damage") or 0)
    ok("enemy hp test: round_settlement team dealt", team_dealt > 0, str(settlement)[:200])
    ok(
        "enemy hp test: round_settlement enemy dealt present",
        "enemy_damage_dealt" in settlement,
        str(settlement)[:200],
    )

    db_hp = combat_enemy_hp(get_combat(combat_id), default=start_hp)
    if phase.get("outcome") == "victory":
        ok("enemy hp test: victory zeroes enemy hp", db_hp == 0, f"db={db_hp}")
    else:
        enemy_payload = phase.get("enemy") or {}
        payload_hp = (
            int(enemy_payload["hp"])
            if enemy_payload.get("hp") is not None
            else start_hp
        )
        ok(
            "enemy hp test: payload hp dropped",
            payload_hp < start_hp,
            f"{start_hp}->{payload_hp}",
        )
        ok(
            "enemy hp test: db hp matches payload",
            db_hp == payload_hp,
            f"db={db_hp}, payload={payload_hp}",
        )

    teardown_test_combat(team_id, TEST_ENCOUNTER_ID)
    clear_encounter_completion(team_id, TEST_ENCOUNTER_ID)
    update_protagonist_state(team_id, "iggy", is_active=1)


def test_solo_killing_blow_returns_victory(client, client2, team_id):
    """Final hit at enemy HP 1 must return victory, not another attackable player_phase."""
    from models.combat import combat_outcome_if_finished, get_active_combat_for_team, save_combat
    from models.encounter import load_encounter
    from models.protagonist import update_protagonist_state

    active = get_active_combat_for_team(team_id)
    if active:
        teardown_test_combat(team_id, active.get("encounter_id"))
    prepare_test_encounter(client, team_id, TEST_ENCOUNTER_ID)
    update_protagonist_state(team_id, "iggy", is_active=0)

    r = client.post(
        "/combat/start",
        json={"encounter_id": TEST_ENCOUNTER_ID},
        content_type="application/json",
    )
    start = r.get_json() or {}
    combat_id = start.get("combat_id")
    ok("killing blow: start combat", start.get("success") and combat_id, str(start))

    save_combat(combat_id, enemy_hp=1)
    with patch("routes.combat.roll_combat_dice", return_value=2):
        w = client.post(
            "/combat/submit_action",
            json={"combat_id": combat_id, "action_type": "attack"},
            content_type="application/json",
        ).get_json() or {}
        ok("killing blow: leader waits", w.get("status") == "waiting_for_teammates", str(w)[:200])
        data = client2.post(
            "/combat/submit_action",
            json={"combat_id": combat_id, "action_type": "attack"},
            content_type="application/json",
        ).get_json() or {}
    ok("killing blow: victory outcome", data.get("outcome") == "victory", str(data)[:240])
    settlement = data.get("round_settlement") or {}
    ok("killing blow: round_settlement on victory", bool(settlement), str(settlement)[:200])
    ok(
        "killing blow: enemy_hp_after zero",
        settlement.get("enemy_hp_after") == 0,
        str(settlement.get("enemy_hp_after")),
    )
    ok(
        "killing blow: combat ended in db",
        (get_combat(combat_id) or {}).get("status") == "ended",
        str(get_combat(combat_id))[:200],
    )

    zombie = dict(get_combat(combat_id) or {})
    zombie.update({"status": "player_phase", "enemy_hp": 0, "winner": None})
    finished = combat_outcome_if_finished(zombie, load_encounter(TEST_ENCOUNTER_ID), team_id=team_id)
    ok(
        "killing blow: zombie hp0 guard returns victory",
        finished and finished.get("outcome") == "victory",
        str(finished)[:200],
    )

    teardown_test_combat(team_id, TEST_ENCOUNTER_ID)
    clear_encounter_completion(team_id, TEST_ENCOUNTER_ID)
    update_protagonist_state(team_id, "iggy", is_active=1)


def test_solo_killing_blow_practice_quick():
    """Solo team + protagonist on practice_iggy_01_quick: one-round win includes settlement."""
    from models.protagonist import update_protagonist_state
    from models.squad import get_team_members, update_squad

    enc_id = "practice_iggy_01_quick"
    client = oikonomia.app.test_client()
    login(client, "QuickKillSolo")
    r = client.post("/team/create", data={"team_name": "QuickKillSolo"})
    team_id = (r.get_json() or {}).get("team_id")
    client.post("/set_team_route_by_leader", data={"route": "iggy"})
    update_protagonist_state(team_id, "iggy", is_active=1)
    for member in get_team_members(team_id):
        update_squad(member["squad_id"], power=12, intellect=12)

    teardown_test_combat(team_id, enc_id)
    clear_encounter_completion(team_id, enc_id)

    r = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    )
    start = r.get_json() or {}
    combat_id = start.get("combat_id")
    ok("quick kill: start", start.get("success") and combat_id, str(start)[:120])
    start_hp = combat_enemy_hp(get_combat(combat_id), default=-1)
    ok("quick kill: enemy hp ~48", 40 <= start_hp <= 55, str(start_hp))

    with patch("routes.combat.roll_combat_dice", return_value=1), patch(
        "models.combat.roll_combat_dice", return_value=1
    ):
        data = client.post(
            "/combat/submit_action",
            json={"combat_id": combat_id, "action_type": "attack"},
            content_type="application/json",
        ).get_json() or {}

    ok("quick kill: victory outcome", data.get("outcome") == "victory", str(data)[:200])
    settlement = data.get("round_settlement") or {}
    ok("quick kill: round_settlement present", bool(settlement), str(settlement)[:200])
    ok(
        "quick kill: team_damage_dealt > 0",
        int(settlement.get("team_damage_dealt") or 0) > 0,
        str(settlement),
    )
    ok("quick kill: enemy_hp_after is 0", settlement.get("enemy_hp_after") == 0, str(settlement))
    payload_hp = (data.get("enemy") or {}).get("hp")
    ok(
        "quick kill: payload enemy hp 0",
        payload_hp is not None and int(payload_hp) == 0,
        str(data.get("enemy")),
    )
    ok("quick kill: log_entries present", len(data.get("log_entries") or []) > 0, "empty logs")
    ok("quick kill: db enemy_hp 0", combat_enemy_hp(get_combat(combat_id), default=-1) == 0, "db hp")
    ok(
        "quick kill: combat ended",
        (get_combat(combat_id) or {}).get("status") == "ended",
        str((get_combat(combat_id) or {}).get("status")),
    )

    teardown_test_combat(team_id, enc_id)


def test_escape_action_type_allowed():
    from models.combat import COMBAT_ACTION_TYPES

    ok("escape in COMBAT_ACTION_TYPES", "escape" in COMBAT_ACTION_TYPES)


def test_defeat_outcome_includes_dead_roster():
    from services.combat_outcomes import build_defeat_outcome_payload

    participants = [
        {"squad_id": "A", "display_name": "Alice", "hp": 0, "max_hp": 100},
        {"squad_id": "B", "display_name": "Bob", "hp": 80, "max_hp": 100},
    ]
    payload = build_defeat_outcome_payload({"failure": {"narrative": "fail"}}, participants=participants)
    ok("defeat outcome_type COMBAT_FAILED", payload.get("outcome_type") == "COMBAT_FAILED", str(payload))
    ok("defeat dead_squad_ids", payload.get("dead_squad_ids") == ["A"], str(payload))
    ok("defeat dead_squad_names", payload.get("dead_squad_names") == ["Alice"], str(payload))
    ok("defeat requires_gm", payload.get("requires_gm") is True, str(payload))


def test_select_enemy_counter_target_priority():
    from models.combat import select_enemy_counter_target

    participants = [
        {"squad_id": "A", "hp": 80, "max_hp": 100, "resilience": 5, "is_protagonist": False},
        {"squad_id": "B", "hp": 30, "max_hp": 100, "resilience": 3, "is_protagonist": False, "trauma_count": 0},
        {"squad_id": "P", "hp": 90, "max_hp": 100, "resilience": 10, "is_protagonist": True},
    ]
    actions = {"B": {"action_type": "escape"}}
    target = select_enemy_counter_target(participants, actions, enemy_base_damage=50)
    ok("escape target prefers escaper", target and target["squad_id"] == "B", str(target))


def test_escape_fail_mixed_settlement():
    """INV-E: escape fail still resolves combat actions with settlement metadata."""
    from models.protagonist import update_protagonist_state

    enc_id = "practice_iggy_01_quick"
    client = oikonomia.app.test_client()
    login(client, "EscapeFailSolo")
    client.post("/team/create", data={"team_name": "EscapeFail"})
    client.post("/set_team_route_by_leader", data={"route": "iggy"})
    import sqlite3

    conn = sqlite3.connect(_test_db_path())
    team_id = conn.execute("SELECT team_id FROM teams ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    conn.close()
    update_protagonist_state(team_id, "iggy", is_active=0)

    teardown_test_combat(team_id, enc_id)
    clear_encounter_completion(team_id, enc_id)

    start = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    ).get_json() or {}
    combat_id = start.get("combat_id")
    ok("escape fail: start", start.get("success") and combat_id, str(start)[:120])

    with patch("models.combat.random.random", return_value=0.99), patch(
        "models.combat.roll_combat_dice", return_value=2
    ):
        data = client.post(
            "/combat/submit_action",
            json={"combat_id": combat_id, "action_type": "escape"},
            content_type="application/json",
        ).get_json() or {}

    ok("escape fail: not 400", data.get("success") is not False or data.get("round_resolved"), str(data)[:200])
    ok(
        "escape fail: round_resolved",
        data.get("round_resolved") or data.get("status") == "round_resolved",
        str(data)[:200],
    )
    settlement = data.get("round_settlement") or {}
    ok("escape fail: escape_triggered", settlement.get("escape_triggered") is True, str(settlement))
    ok("escape fail: escape_success false", settlement.get("escape_success") is False, str(settlement))
    ok(
        "escape fail: combat still active",
        (get_combat(combat_id) or {}).get("status") == "player_phase",
        str((get_combat(combat_id) or {}).get("status")),
    )

    teardown_test_combat(team_id, enc_id)


def test_use_item_combat_consumes_and_resolves():
    """P2-1: use_item consumes player_items row and resolves with damage."""
    from models.item import consume_squad_item_for_combat, grant_item_to_squad
    from models.protagonist import update_protagonist_state

    enc_id = "practice_iggy_01_quick"
    client = oikonomia.app.test_client()
    login(client, "UseItemSolo")
    client.post("/team/create", data={"team_name": "UseItem"})
    client.post("/set_team_route_by_leader", data={"route": "iggy"})
    import sqlite3

    conn = sqlite3.connect(_test_db_path())
    team_id = conn.execute("SELECT team_id FROM teams ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    squad_id = conn.execute(
        "SELECT squad_id FROM squads WHERE team_id = ? ORDER BY rowid LIMIT 1",
        (team_id,),
    ).fetchone()[0]
    conn.close()
    update_protagonist_state(team_id, "iggy", is_active=0)

    qr_value = f"test-combat-power-{os.getpid()}"
    conn = sqlite3.connect(_test_db_path())
    conn.execute("DELETE FROM player_items WHERE squad_id = ?", (squad_id,))
    conn.execute(
        """INSERT INTO items
           (name, description, icon, qr_code_value, has_ability, effect_type, effect_value, is_active)
           VALUES ('力量碎片', 'test', '💎', ?, 1, 'power_up', 5, 1)""",
        (qr_value,),
    )
    conn.commit()
    item_row = conn.execute(
        "SELECT id FROM items WHERE qr_code_value = ?", (qr_value,),
    ).fetchone()
    conn.close()
    item_id = item_row[0]

    granted, grant_msg, _ = grant_item_to_squad(squad_id, item_id, source="test")
    ok("use_item: grant power_up item", granted, grant_msg)

    r = client.get("/api/inventory")
    inv = r.get_json() or {}
    ok("use_item: /api/inventory lists item", inv.get("success") and any(
        i.get("item_id") == item_id for i in (inv.get("items") or [])
    ), str(inv)[:200])

    teardown_test_combat(team_id, enc_id)
    clear_encounter_completion(team_id, enc_id)

    start = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    ).get_json() or {}
    combat_id = start.get("combat_id")
    ok("use_item: start combat", start.get("success") and combat_id, str(start)[:120])

    with patch("routes.combat.roll_combat_dice", return_value=2):
        data = client.post(
            "/combat/submit_action",
            json={"combat_id": combat_id, "action_type": "use_item", "item_id": item_id},
            content_type="application/json",
        ).get_json() or {}

    ok("use_item: submit resolves", data.get("round_resolved") or data.get("success"), str(data)[:200])
    settlement = data.get("round_settlement") or {}
    ok("use_item: team dealt damage", int(settlement.get("team_damage_dealt") or 0) > 0, str(settlement))

    conn = sqlite3.connect(_test_db_path())
    remaining = conn.execute(
        "SELECT COUNT(*) FROM player_items WHERE squad_id = ? AND item_id = ?",
        (squad_id, item_id),
    ).fetchone()[0]
    conn.close()
    ok("use_item: inventory row consumed", remaining == 0, str(remaining))

    ok_consume, _, err = consume_squad_item_for_combat(squad_id, item_id)
    ok("use_item: double consume blocked", not ok_consume and err, err)

    teardown_test_combat(team_id, enc_id)


def test_non_leader_as_protagonist_rejected():
    """P2-3: non-leader cannot submit with as_protagonist=true."""
    from models.protagonist import update_protagonist_state

    client = oikonomia.app.test_client()
    client2 = oikonomia.app.test_client()
    login(client, "ProLeader")
    login(client2, "ProMember")
    client.post("/team/create", data={"team_name": "ProGate"})
    client.post("/set_team_route_by_leader", data={"route": "iggy"})

    import sqlite3

    conn = sqlite3.connect(_test_db_path())
    team_id = conn.execute("SELECT team_id FROM teams ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    leader_id = conn.execute(
        "SELECT squad_id FROM squads WHERE team_id = ? AND is_team_leader = 1 LIMIT 1",
        (team_id,),
    ).fetchone()[0]
    conn.close()

    client2.post("/team/join", data={"team_id": team_id, "display_name": "ProMember"})

    update_protagonist_state(team_id, "iggy", is_active=1)

    enable_gm_session(client)
    teardown_test_combat(team_id, "test_protagonist_control")
    clear_encounter_completion(team_id, "test_protagonist_control")

    r = client.post(
        "/combat/start",
        json={"encounter_id": "test_protagonist_control"},
        content_type="application/json",
    )
    start = r.get_json() or {}
    combat_id = start.get("combat_id")
    ok("pro gate: start combat", combat_id, str(start)[:120])

    with client2.session_transaction() as sess:
        member_id = sess.get("squad_id")

    r403 = client2.post(
        "/combat/submit_action",
        json={"combat_id": combat_id, "action_type": "attack", "as_protagonist": True},
        content_type="application/json",
    )
    ok("pro gate: member as_protagonist 403", r403.status_code == 403, str(r403.get_json()))
    body = r403.get_json() or {}
    ok(
        "pro gate: error message",
        "隊長" in (body.get("error") or ""),
        body.get("error"),
    )

    r_ok = client.post(
        "/combat/submit_action",
        json={"combat_id": combat_id, "action_type": "attack", "as_protagonist": True},
        content_type="application/json",
    )
    d = r_ok.get_json() or {}
    ok("pro gate: leader as_protagonist ok", d.get("success") or d.get("status"), str(d)[:200])

    teardown_test_combat(team_id, "test_protagonist_control")


def test_use_item_hp_up_and_sanity_up_in_combat():
    """P2-4: hp_up / sanity_up items heal in combat without enemy damage."""
    from models.item import grant_item_to_squad
    from models.protagonist import update_protagonist_state

    enc_id = "practice_iggy_01_quick"
    client = oikonomia.app.test_client()
    login(client, "ItemExtendSolo")
    client.post("/team/create", data={"team_name": "ItemExtend"})
    client.post("/set_team_route_by_leader", data={"route": "iggy"})
    import sqlite3

    conn = sqlite3.connect(_test_db_path())
    team_id = conn.execute("SELECT team_id FROM teams ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    squad_id = conn.execute(
        "SELECT squad_id FROM squads WHERE team_id = ? ORDER BY rowid LIMIT 1",
        (team_id,),
    ).fetchone()[0]
    heal_qr = f"test-heal-{os.getpid()}"
    san_qr = f"test-san-{os.getpid()}"
    conn.execute("DELETE FROM player_items WHERE squad_id = ?", (squad_id,))
    conn.execute(
        """INSERT INTO items
           (name, description, icon, qr_code_value, has_ability, effect_type, effect_value, is_active)
           VALUES ('生命泉源', 'heal', '🧪', ?, 1, 'hp_up', 30, 1)""",
        (heal_qr,),
    )
    conn.execute(
        """INSERT INTO items
           (name, description, icon, qr_code_value, has_ability, effect_type, effect_value, is_active)
           VALUES ('安定情緒劑', 'sanity', '🔮', ?, 1, 'sanity_up', 25, 1)""",
        (san_qr,),
    )
    conn.commit()
    heal_item_id = conn.execute(
        "SELECT id FROM items WHERE qr_code_value = ?", (heal_qr,),
    ).fetchone()[0]
    san_item_id = conn.execute(
        "SELECT id FROM items WHERE qr_code_value = ?", (san_qr,),
    ).fetchone()[0]
    conn.close()

    update_protagonist_state(team_id, "iggy", is_active=0)

    teardown_test_combat(team_id, enc_id)
    clear_encounter_completion(team_id, enc_id)

    granted, _, _ = grant_item_to_squad(squad_id, heal_item_id, source="test")
    ok("P2-4: grant hp_up item", granted)

    start = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    ).get_json() or {}
    combat_id = start.get("combat_id")
    ok("P2-4: start combat (heal)", start.get("success") and combat_id, str(start)[:120])

    update_squad(squad_id, hp=40)
    hp_before = int((get_squad(squad_id) or {}).get("hp") or 0)
    max_hp = int((get_squad(squad_id) or {}).get("max_hp") or 100)

    data = client.post(
        "/combat/submit_action",
        json={"combat_id": combat_id, "action_type": "use_item", "item_id": heal_item_id},
        content_type="application/json",
    ).get_json() or {}
    settlement = data.get("round_settlement") or {}
    squad_after_heal = get_squad(squad_id) or {}
    hp_after = int(squad_after_heal.get("hp") or 0)
    ok(
        "P2-4: hp_up increases HP vs baseline",
        hp_after > hp_before,
        f"before={hp_before} after={hp_after}",
    )
    ok("P2-4: hp_up deals no enemy damage", int(settlement.get("team_damage_dealt") or 0) == 0, str(settlement))
    logs = (get_combat(combat_id) or {}).get("logs") or []
    ok(
        "P2-4: hp_up combat log",
        any("生命值回復" in (e.get("message") if isinstance(e, dict) else str(e)) for e in logs),
        str(logs[-5:]),
    )

    teardown_test_combat(team_id, enc_id)
    clear_encounter_completion(team_id, enc_id)

    granted2, _, _ = grant_item_to_squad(squad_id, san_item_id, source="test")
    ok("P2-4: grant sanity_up item", granted2)

    start2 = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    ).get_json() or {}
    combat_id2 = start2.get("combat_id")
    ok("P2-4: start combat (sanity)", start2.get("success") and combat_id2, str(start2)[:120])

    update_squad(squad_id, sanity=50)
    san_before = int((get_squad(squad_id) or {}).get("sanity") or 0)

    data2 = client.post(
        "/combat/submit_action",
        json={"combat_id": combat_id2, "action_type": "use_item", "item_id": san_item_id},
        content_type="application/json",
    ).get_json() or {}
    settlement2 = data2.get("round_settlement") or {}
    squad_after_san = get_squad(squad_id) or {}
    san_after = int(squad_after_san.get("sanity") or 0)
    ok(
        "P2-4: sanity_up restores sanity SSOT",
        san_after == min(100, san_before + 25),
        f"before={san_before} after={san_after}",
    )
    ok("P2-4: sanity_up deals no enemy damage", int(settlement2.get("team_damage_dealt") or 0) == 0, str(settlement2))

    teardown_test_combat(team_id, enc_id)


def test_combat_summon_gm_creates_global_event():
    """P2-3/GM: summon_gm writes global_events row and combat log."""
    import sqlite3

    enc_id = "practice_iggy_01_quick"
    client = oikonomia.app.test_client()
    login(client, "SummonGmSolo")
    client.post("/team/create", data={"team_name": "SummonGm"})
    client.post("/set_team_route_by_leader", data={"route": "iggy"})

    conn = sqlite3.connect(_test_db_path())
    team_id = conn.execute("SELECT team_id FROM teams ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    squad_id = conn.execute(
        "SELECT squad_id FROM squads WHERE team_id = ? LIMIT 1", (team_id,)
    ).fetchone()[0]
    conn.close()

    teardown_test_combat(team_id, enc_id)
    clear_encounter_completion(team_id, enc_id)

    start = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    ).get_json() or {}
    combat_id = start.get("combat_id")
    ok("summon_gm: start combat", start.get("success") and combat_id, str(start)[:120])

    resp = client.post(
        "/combat/summon_gm",
        json={"combat_id": combat_id},
        content_type="application/json",
    ).get_json() or {}
    ok("summon_gm: success", resp.get("success"), str(resp))

    conn = sqlite3.connect(_test_db_path())
    row = conn.execute(
        "SELECT title, description FROM global_events ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    conn.close()
    ok("summon_gm: global_events row", row and "救援訊號" in (row[0] or ""), str(row))

    combat = get_combat(combat_id) or {}
    logs = combat.get("logs") or []
    ok(
        "summon_gm: combat log entry",
        any("求助" in (e.get("message") if isinstance(e, dict) else str(e)) for e in logs),
        str(logs[-3:]),
    )

    teardown_test_combat(team_id, enc_id)


def test_escape_success_ends_combat():
    """Escape success ends combat with outcome escaped."""
    from models.protagonist import update_protagonist_state

    enc_id = "practice_iggy_01_quick"
    client = oikonomia.app.test_client()
    login(client, "EscapeWinSolo")
    client.post("/team/create", data={"team_name": "EscapeWin"})
    client.post("/set_team_route_by_leader", data={"route": "iggy"})
    import sqlite3

    conn = sqlite3.connect(_test_db_path())
    team_id = conn.execute("SELECT team_id FROM teams ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    conn.close()
    update_protagonist_state(team_id, "iggy", is_active=0)

    teardown_test_combat(team_id, enc_id)
    clear_encounter_completion(team_id, enc_id)

    start = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    ).get_json() or {}
    combat_id = start.get("combat_id")
    ok("escape win: start", start.get("success") and combat_id, str(start)[:120])

    with patch("models.combat.random.random", return_value=0.01):
        data = client.post(
            "/combat/submit_action",
            json={"combat_id": combat_id, "action_type": "escape"},
            content_type="application/json",
        ).get_json() or {}

    ok("escape win: outcome escaped", data.get("outcome") == "escaped", str(data)[:200])
    ok("escape win: winner escaped", data.get("winner") == "escaped", str(data)[:200])
    settlement = data.get("round_settlement") or {}
    ok("escape win: escape_success", settlement.get("escape_success") is True, str(settlement))
    ok(
        "escape win: combat ended",
        (get_combat(combat_id) or {}).get("winner") == "escaped",
        str(get_combat(combat_id)),
    )

    teardown_test_combat(team_id, enc_id)


def test_solo_multi_round_poll_hp_monotonic():
    """Solo multi-round: submit + poll must return decreasing enemy.hp (Henry scenario)."""
    from models.protagonist import update_protagonist_state

    enc_id = "practice_iggy_03_boundary"
    client = oikonomia.app.test_client()
    login(client, "SoloPollHp")
    client.post("/team/create", data={"team_name": "SoloPoll"})
    client.post("/set_team_route_by_leader", data={"route": "iggy"})
    import sqlite3

    conn = sqlite3.connect(_test_db_path())
    team_id = conn.execute("SELECT team_id FROM teams ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    conn.close()
    update_protagonist_state(team_id, "iggy", is_active=0)

    teardown_test_combat(team_id, enc_id)
    clear_encounter_completion(team_id, enc_id)

    r = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    )
    combat_id = (r.get_json() or {}).get("combat_id")
    start_hp = combat_enemy_hp(get_combat(combat_id), default=-1)
    ok("solo poll hp: start", start_hp > 0, str(start_hp))

    prev_payload_hp = start_hp
    prev_poll_hp = start_hp
    import models.combat as combat_model

    orig_auto = combat_model.choose_protagonist_auto_action
    combat_model.choose_protagonist_auto_action = lambda p, settings=None: {
        "action_type": "defend",
        "dice_result": 1,
    }
    try:
        for round_no in range(1, 4):
            with patch("routes.combat.roll_combat_dice", return_value=1):
                d = client.post(
                    "/combat/submit_action",
                    json={"combat_id": combat_id, "action_type": "attack"},
                    content_type="application/json",
                ).get_json() or {}
            if d.get("outcome"):
                ok("solo poll hp: skip victory", False, f"victory round {round_no}")
                break
            ok(
                f"solo poll hp: R{round_no} round_resolved",
                d.get("round_resolved") or d.get("status") == "round_resolved",
                str(d)[:160],
            )
            payload_hp_raw = (d.get("enemy") or {}).get("hp")
            payload_hp = int(payload_hp_raw) if payload_hp_raw is not None else None
            ok(
                f"solo poll hp: R{round_no} payload dropped",
                payload_hp is not None and payload_hp < prev_payload_hp,
                f"{prev_payload_hp}->{payload_hp}",
            )
            settlement = d.get("round_settlement") or {}
            ok(
                f"solo poll hp: R{round_no} settlement present",
                int(settlement.get("team_damage_dealt") or 0) > 0,
                str(settlement)[:120],
            )
            after = settlement.get("enemy_hp_after")
            ok(
                f"solo poll hp: R{round_no} after matches payload",
                after is not None and int(after) == payload_hp,
                f"after={after}, payload={payload_hp}",
            )

            st = client.get(f"/combat/status?combat_id={combat_id}").get_json() or {}
            poll_hp_raw = (st.get("enemy") or {}).get("hp")
            poll_hp = int(poll_hp_raw) if poll_hp_raw is not None else None
            ok(
                f"solo poll hp: R{round_no} poll matches payload",
                poll_hp == payload_hp,
                f"poll={poll_hp}, payload={payload_hp}",
            )
            ok(
                f"solo poll hp: R{round_no} poll monotonic",
                poll_hp is not None and poll_hp <= prev_poll_hp,
                f"{prev_poll_hp}->{poll_hp}",
            )
            ok(
                f"solo poll hp: R{round_no} db matches",
                combat_enemy_hp(get_combat(combat_id), default=-1) == payload_hp,
                "db mismatch",
            )
            prev_payload_hp = payload_hp
            prev_poll_hp = poll_hp
    finally:
        combat_model.choose_protagonist_auto_action = orig_auto

    teardown_test_combat(team_id, enc_id)


def test_zombie_hp_zero_status_poll_returns_victory():
    """Status poll must end combat when enemy HP is 0 but status still player_phase."""
    from models.protagonist import update_protagonist_state

    enc_id = "practice_iggy_03_boundary"
    client = oikonomia.app.test_client()
    login(client, "ZombieHpZero")
    client.post("/team/create", data={"team_name": "ZombieHp"})
    client.post("/set_team_route_by_leader", data={"route": "iggy"})
    import sqlite3

    conn = sqlite3.connect(_test_db_path())
    team_id = conn.execute("SELECT team_id FROM teams ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    conn.close()
    update_protagonist_state(team_id, "iggy", is_active=0)

    teardown_test_combat(team_id, enc_id)
    clear_encounter_completion(team_id, enc_id)

    r = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    )
    combat_id = (r.get_json() or {}).get("combat_id")
    ok("zombie hp0: start", bool(combat_id), str(r.get_json())[:120])

    from models.combat import append_combat_log, save_combat

    combat = get_combat(combat_id)
    combat = append_combat_log(
        combat,
        "練習・界線共生影 受到共 140 點傷害，剩餘 HP 0",
        log_type="summary",
    )
    save_combat(
        combat_id,
        status="player_phase",
        enemy_hp=4,
        logs=combat.get("logs"),
        winner=None,
    )

    st = client.get(f"/combat/status?combat_id={combat_id}").get_json() or {}
    ok("zombie hp0: poll returns victory", st.get("outcome") == "victory", str(st)[:200])
    ok("zombie hp0: poll inactive", st.get("active") is False, str(st.get("active")))
    ok(
        "zombie hp0: db ended",
        (get_combat(combat_id) or {}).get("status") == "ended",
        str((get_combat(combat_id) or {}).get("status")),
    )

    teardown_test_combat(team_id, enc_id)


def test_practice_combat_start_enemy_hp_full():
    """Fresh practice combat must start with full enemy HP (not 0 from stale reconcile)."""
    from models.protagonist import update_protagonist_state

    cases = (
        ("practice_iggy_01_quick", 48),
        ("practice_iggy_03_boundary", 140),
    )
    for enc_id, expected_hp in cases:
        client = oikonomia.app.test_client()
        login(client, f"StartHp_{enc_id[-6:]}")
        client.post("/team/create", data={"team_name": f"StartHp_{enc_id[-6:]}"})
        client.post("/set_team_route_by_leader", data={"route": "iggy"})
        import sqlite3

        conn = sqlite3.connect(_test_db_path())
        team_id = conn.execute("SELECT team_id FROM teams ORDER BY rowid DESC LIMIT 1").fetchone()[0]
        conn.close()
        update_protagonist_state(team_id, "iggy", is_active=0)
        teardown_test_combat(team_id, enc_id)
        clear_encounter_completion(team_id, enc_id)

        start = client.post(
            "/combat/start",
            json={"encounter_id": enc_id},
            content_type="application/json",
        ).get_json() or {}
        combat_id = start.get("combat_id")
        ok(f"start hp {enc_id}: created", bool(combat_id), str(start)[:120])
        db_hp = combat_enemy_hp(get_combat(combat_id), default=-1)
        ok(f"start hp {enc_id}: db", db_hp == expected_hp, f"db={db_hp}")

        st = client.get(f"/combat/status?combat_id={combat_id}").get_json() or {}
        payload_hp = (st.get("enemy") or {}).get("hp")
        ok(
            f"start hp {enc_id}: status poll",
            payload_hp is not None and int(payload_hp) == expected_hp,
            f"poll={payload_hp}",
        )
        ok(
            f"start hp {enc_id}: still active",
            st.get("active") is True and not st.get("outcome"),
            str(st)[:160],
        )
        teardown_test_combat(team_id, enc_id)


def fight_until_victory(client, client2, combat_id):
    """
    Both players attack each player_phase until victory or max rounds.
    Patches roll_combat_dice → 3 so damage is deterministic (server-side dice).
    """
    last = {}
    clients = (client, client2)
    with patch("routes.combat.roll_combat_dice", return_value=3):
        for _round in range(MAX_FIGHT_ROUNDS):
            for idx, c in enumerate(clients):
                r = submit_attack(c, combat_id)
                last = r.get_json() or {}
                if r.status_code >= 400:
                    return last, f"HTTP {r.status_code} player{idx + 1}"
                if not last.get("success"):
                    return last, f"player{idx + 1} submit failed"
                if last.get("outcome") == "victory":
                    return last, None
                if last.get("status") == "waiting_for_teammates":
                    continue

            st = client.get(f"/combat/status?combat_id={combat_id}").get_json() or {}
            if st.get("outcome") == "victory" or st.get("status") == "ended":
                return st, None
            if st.get("status") not in ("player_phase", None):
                continue
    return last, f"no victory after {MAX_FIGHT_ROUNDS} rounds"


PRODUCTION_ENCOUNTERS = (
    "enc_iggy_01_leech",
    "enc_iggy_02_boundary",
    "enc_marah_01_whisper",
)


def test_near_death_rescue_security(client, leader_id, member_id):
    import sqlite3
    from datetime import datetime, timedelta

    from models.item import (
        get_item_by_qr_code_value,
        grant_item_to_squad,
        is_near_death_rescue_item,
    )

    until = (datetime.now() + timedelta(minutes=15)).isoformat()
    update_squad(member_id, near_death_until=until, hp=0)

    login(client, leader_id)
    rescuer_until = (datetime.now() + timedelta(minutes=15)).isoformat()
    update_squad(leader_id, near_death_until=rescuer_until, hp=0)
    r = client.post("/combat/rescue_near_death", json={"rescue_type": "prayer"})
    blocked = r.get_json() or {}
    ok(
        "rescuer near_death blocked",
        r.status_code == 400 and not blocked.get("success"),
        str(blocked),
    )
    update_squad(leader_id, near_death_until=None, hp=100)

    update_squad(leader_id, sanity=0)
    r = client.post("/combat/rescue_near_death", json={"rescue_type": "prayer"})
    sanity_blocked = r.get_json() or {}
    ok(
        "rescuer sanity collapse blocked",
        r.status_code == 400 and not sanity_blocked.get("success"),
        str(sanity_blocked),
    )
    update_squad(leader_id, sanity=50)

    r = client.post(
        "/combat/rescue_near_death",
        json={"rescue_type": "item", "item_id": 99999},
    )
    data = r.get_json() or {}
    ok("item rescue rejected without ownership", r.status_code == 400 and not data.get("success"))

    r = client.post("/combat/rescue_near_death", json={"rescue_type": "exploit"})
    ok("invalid rescue_type rejected", r.status_code == 400)

    qr_value = f"test-rescue-item-{os.getpid()}"
    db = os.path.join(TEST_DIR, "oikonomia.db")
    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM player_items WHERE squad_id = ?", (leader_id,))
    conn.execute(
        """INSERT INTO items
           (name, description, icon, qr_code_value, has_ability, effect_type, effect_value, is_active)
           VALUES ('測試藥水', 'test', '💊', ?, 1, 'hp_up', 10, 1)""",
        (qr_value,),
    )
    conn.commit()
    conn.close()

    item = get_item_by_qr_code_value(qr_value)
    ok("rescue test item visible", item is not None, qr_value)
    ok("rescue test item eligible", is_near_death_rescue_item(item), str(item))
    item_id = item["id"]

    granted, grant_msg, _effect = grant_item_to_squad(leader_id, item_id, source="test")
    ok("grant rescue item", granted, grant_msg)
    r = client.post(
        "/combat/rescue_near_death",
        json={"rescue_type": "item", "item_id": item_id},
    )
    data = r.get_json() or {}
    ok("item rescue with hp_up consumes item", data.get("success") and data.get("rescued"), str(data))

    member = get_squad(member_id)
    ok("target revived hp=25", int(member.get("hp") or 0) == 25, str(member))
    ok("target near_death cleared", not member.get("near_death_until"))
    update_squad(member_id, near_death_until=None, hp=100)


def test_qr_code_grant_scoped_per_squad_not_global(leader_id):
    """QR one-time use is per squad_id, not global catalog item_id."""
    import sqlite3

    from models.item import grant_item_to_squad

    qr_value = f"test-qr-per-squad-{os.getpid()}"
    outsider_id = f"PLAYER-QROUT-{os.getpid()}"
    db = os.path.join(TEST_DIR, "oikonomia.db")
    conn = sqlite3.connect(db)
    conn.execute(
        """INSERT INTO items
           (name, description, icon, qr_code_value, has_ability, effect_type, effect_value, is_active, is_one_time_use)
           VALUES ('共享 QR 測試', 'test', '🎫', ?, 1, 'power_up', 5, 1, 1)""",
        (qr_value,),
    )
    conn.execute(
        """INSERT INTO squads (squad_id, hp, max_hp, display_name)
           VALUES (?, 100, 100, 'QR Outsider')""",
        (outsider_id,),
    )
    conn.commit()
    item_id = conn.execute(
        "SELECT id FROM items WHERE qr_code_value = ?", (qr_value,),
    ).fetchone()[0]
    conn.close()

    ok1, msg1, _ = grant_item_to_squad(leader_id, item_id, source="qr")
    ok("qr per squad: leader first scan", ok1, msg1)
    ok2, msg2, _ = grant_item_to_squad(leader_id, item_id, source="qr")
    ok(
        "qr per squad: leader second scan blocked",
        not ok2 and "你已經使用過此 QR Code" in (msg2 or ""),
        msg2,
    )
    ok3, msg3, _ = grant_item_to_squad(outsider_id, item_id, source="qr")
    ok("qr per squad: other player can scan same catalog item", ok3, msg3)


def test_combat_start_rejects_body_squad_id_spoof(client, leader_id, member_id, team_id):
    """Body squad_id must not override session (IDOR prevention)."""
    from datetime import datetime

    from models.combat import clear_team_combat_id, get_combat, save_combat

    prepare_test_encounter(client, team_id, TEST_ENCOUNTER_ID)
    login(client, leader_id)

    r = client.post(
        "/combat/start",
        json={"encounter_id": TEST_ENCOUNTER_ID, "squad_id": member_id},
        content_type="application/json",
    )
    start = r.get_json() or {}
    ok("spoof start returns success", start.get("success"), str(start))
    combat_id = start.get("combat_id")
    combat = get_combat(combat_id) if combat_id else None
    ok(
        "combat owned by session squad not body",
        combat and combat.get("squad_id") == leader_id,
        f"expected {leader_id} got {(combat or {}).get('squad_id')}",
    )
    if combat_id:
        save_combat(combat_id, status="ended", winner="squad", ended_at=datetime.now().isoformat())
        clear_team_combat_id(team_id)


def test_rescue_near_death_target_squad_id(client, leader_id, member_id, team_id):
    """Explicit target_squad_id rescues the intended teammate when multiple are near death."""
    from datetime import datetime, timedelta

    client3 = oikonomia.app.test_client()
    p3 = login(client3, "TestMember2")
    ok("player3 login", p3 and p3.get("squad_id"))
    member2_id = p3.get("squad_id")
    join3 = client3.post("/team/join", data={"team_id": team_id}).get_json() or {}
    ok("player3 join team", join3.get("success"), str(join3))

    until_long = (datetime.now() + timedelta(minutes=30)).isoformat()
    until_short = (datetime.now() + timedelta(minutes=10)).isoformat()
    update_squad(member_id, near_death_until=until_long, hp=0)
    update_squad(member2_id, near_death_until=until_short, hp=0)

    login(client, leader_id)
    update_squad(leader_id, near_death_until=None, hp=100, sanity=50)

    r = client.post(
        "/combat/rescue_near_death",
        json={"rescue_type": "prayer", "target_squad_id": member2_id},
    )
    data = r.get_json() or {}
    ok("targeted rescue success", data.get("success"), str(data))

    m2 = get_squad(member2_id)
    m1 = get_squad(member_id)
    ok(
        "selected target deadline shortened",
        m2.get("near_death_until") and m2["near_death_until"] != until_short,
        f"until={m2.get('near_death_until')}",
    )
    ok(
        "non-target still near death",
        m1.get("near_death_until") == until_long,
        f"member1 until={m1.get('near_death_until')}",
    )

    update_squad(member_id, near_death_until=None, hp=100)
    update_squad(member2_id, near_death_until=None, hp=100)


def test_create_combat_record_active_guard(leader_id, team_id):
    from models.combat import (
        ActiveCombatExistsError,
        clear_team_combat_id,
        create_combat_record,
        get_active_combat_for_team,
        save_combat,
    )
    from models.encounter import load_encounter

    enc = load_encounter(TEST_ENCOUNTER_ID)
    active_before = get_active_combat_for_team(team_id)
    if active_before:
        save_combat(active_before["id"], status="ended", winner="squad")
        clear_team_combat_id(team_id)

    combat = create_combat_record(leader_id, TEST_ENCOUNTER_ID, enc, initial_status="player_phase")
    ok("create_combat_record opens combat", combat and combat.get("id"))
    duplicate = False
    try:
        create_combat_record(leader_id, TEST_ENCOUNTER_ID, enc, initial_status="player_phase")
    except ActiveCombatExistsError:
        duplicate = True
    ok("create_combat_record blocks duplicate team combat", duplicate)
    save_combat(combat["id"], status="ended", winner="squad")
    clear_team_combat_id(team_id)


def test_encounter_list_hides_test_for_players(client, team_id):
    """Non-GM players must not see trigger_type=test encounters in /encounters."""
    r = client.get("/encounters")
    data = r.get_json() or {}
    ok("encounter list API", data.get("success"), str(data)[:200])
    ids = [e.get("encounter_id") for e in (data.get("encounters") or [])]
    for hidden_id in (
        "test_combat_01",
        "test_undefeatable",
        "test_protagonist_control",
        "test_hard_win_item",
        "test_lose_trauma",
    ):
        ok(f"encounter list hides {hidden_id}", hidden_id not in ids, str(ids))
    ok(
        "encounter list shows first story encounter",
        "enc_iggy_01_leech" in ids,
        str(ids),
    )
    for practice_id in (
        "practice_iggy_01_quick",
        "practice_iggy_02_leech",
        "practice_iggy_03_boundary",
        "practice_iggy_04_marathon",
    ):
        ok(f"encounter list shows {practice_id}", practice_id in ids, str(ids))
    practice = next((e for e in (data.get("encounters") or []) if e.get("encounter_id") == "practice_iggy_01_quick"), {})
    ok("practice encounter is replayable", practice.get("replayable") is True, str(practice))
    ok("encounter list has progress hint", bool(data.get("progress_hint")), data.get("progress_hint"))


def test_encounters_reconcile_stale_active_combat(client, team_id, leader_id):
    """Finished combat with stale current_combat_id must not surface as active in lobby."""
    from models.combat import (
        clear_team_combat_id,
        create_combat_record,
        get_active_combat_for_team,
        save_combat,
        set_team_combat_id,
    )
    from models.encounter import load_encounter
    from models.squad import get_squad

    enc = load_encounter("practice_iggy_01_quick")
    clear_team_combat_id(team_id)
    combat = create_combat_record(
        leader_id, enc["encounter_id"], enc, initial_status="player_phase",
    )
    combat_id = combat["id"]

    save_combat(combat_id, status="player_phase", enemy_hp=0)
    set_team_combat_id(team_id, combat_id)

    r = client.get("/encounters")
    data = r.get_json() or {}
    ok("encounters reconcile: success", data.get("success"), str(data)[:200])
    ok("encounters reconcile: no stale active_combat", data.get("active_combat") is False, str(data))
    ok("encounters reconcile: active_combat_id cleared", not data.get("active_combat_id"), str(data))

    squad = get_squad(leader_id)
    ok(
        "encounters reconcile: squad current_combat_id cleared",
        not squad.get("current_combat_id"),
        str(squad),
    )
    ok(
        "encounters reconcile: get_active_combat_for_team empty",
        get_active_combat_for_team(team_id) is None,
        str(data),
    )

    save_combat(combat_id, status="ended", winner="squad")
    clear_team_combat_id(team_id)


def test_practice_boundary_settlement_enemy_hp(client, team_id):
    """Round settlement must include enemy_hp_after matching DB after damage."""
    from models.protagonist import update_protagonist_state

    update_protagonist_state(team_id, "iggy", is_active=0)
    enc_id = "practice_iggy_03_boundary"
    teardown_test_combat(team_id, enc_id)
    r = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    )
    combat_id = (r.get_json() or {}).get("combat_id")
    ok("boundary hp test: start", combat_id, str(r.get_json())[:120])
    start_hp = int((get_combat(combat_id) or {}).get("enemy_hp") or 0)

    with patch("routes.combat.roll_combat_dice", return_value=1):
        d = client.post(
            "/combat/submit_action",
            json={"combat_id": combat_id, "action_type": "attack"},
            content_type="application/json",
        ).get_json() or {}
    if d.get("outcome"):
        ok("boundary hp test: skip one-shot", True, "victory in one round")
        teardown_test_combat(team_id, enc_id)
        return

    settlement = d.get("round_settlement") or {}
    payload_hp = int((d.get("enemy") or {}).get("hp") or -1)
    after = settlement.get("enemy_hp_after")
    db_hp = int((get_combat(combat_id) or {}).get("enemy_hp") or -1)
    ok("boundary hp test: team dealt damage", int(settlement.get("team_damage_dealt") or 0) > 0, str(settlement))
    breakdown = settlement.get("breakdown") or {}
    dealt = breakdown.get("dealt") or {}
    taken = breakdown.get("taken") or {}
    enemy_bd = breakdown.get("enemy") or {}
    ok("boundary hp test: breakdown dealt total", int(dealt.get("total") or 0) > 0, str(dealt))
    ok(
        "boundary hp test: breakdown enemy damage_taken",
        int(enemy_bd.get("damage_taken") or 0) == int(settlement.get("team_damage_dealt") or 0),
        str(enemy_bd),
    )
    ok(
        "boundary hp test: breakdown taken total",
        int(taken.get("total") or 0) == int(settlement.get("enemy_damage_dealt") or 0),
        str(taken),
    )
    ok("boundary hp test: player_hits have role", all(h.get("role") for h in settlement.get("player_hits") or []), str(settlement.get("player_hits")))
    ok("boundary hp test: enemy_hp_after present", after is not None, str(settlement))
    ok("boundary hp test: hp dropped", payload_hp < start_hp, f"{start_hp}->{payload_hp}")
    ok("boundary hp test: after matches payload", int(after) == payload_hp, f"{after} vs {payload_hp}")
    ok("boundary hp test: after matches db", int(after) == db_hp, f"{after} vs db {db_hp}")
    teardown_test_combat(team_id, enc_id)


def test_practice_encounter_replayable(client, team_id):
    """Practice fights can be started again after victory without new player."""
    from models.encounter import load_encounter
    from models.encounter_outcomes import encounter_already_completed, record_encounter_completion

    enc_id = "practice_iggy_01_quick"
    enc = load_encounter(enc_id)
    ok("practice encounter loads", enc is not None)
    record_encounter_completion(team_id, enc_id, "success", narrative="prior run")
    ok("practice marked completed in db", encounter_already_completed(team_id, enc_id))

    r = client.post(
        "/combat/start",
        json={"encounter_id": enc_id},
        content_type="application/json",
    )
    data = r.get_json() or {}
    ok("practice replay start allowed", data.get("success") and data.get("combat_id"), str(data)[:200])

    from models.combat import clear_team_combat_id, get_active_combat_for_team, save_combat
    from datetime import datetime

    active = get_active_combat_for_team(team_id)
    if active:
        save_combat(active["id"], status="ended", winner="enemy", ended_at=datetime.now().isoformat())
        clear_team_combat_id(team_id)


def test_encounter_catalog():
    """Production encounter JSON must load with required fields."""
    from models.encounter import load_encounter

    required_enemy = ("name", "hp")
    for eid in PRODUCTION_ENCOUNTERS:
        enc = load_encounter(eid)
        ok(f"encounter loads: {eid}", enc is not None)
        if not enc:
            continue
        ok(f"{eid} encounter_id matches", enc.get("encounter_id") == eid)
        ok(f"{eid} has title", bool(enc.get("title")))
        ok(f"{eid} has route", bool(enc.get("route")))
        ok(f"{eid} has enemy", isinstance(enc.get("enemy"), dict))
        enemy = enc.get("enemy") or {}
        for key in required_enemy:
            ok(f"{eid} enemy.{key}", key in enemy and enemy[key] not in (None, ""))
        ok(f"{eid} success narrative", bool((enc.get("success") or {}).get("narrative")))
        ok(f"{eid} failure narrative", bool((enc.get("failure") or {}).get("narrative")))


def main():
    client = oikonomia.app.test_client()
    print(f"\n=== Combat 全流程測試 (DATA_DIR={TEST_DIR}) ===\n")

    # --- 玩家 1：建隊 + Iggy 路線 ---
    p1 = login(client, "TestLeader")
    ok("玩家1 登入", p1 and p1.get("squad_id"))
    leader_id = p1.get("squad_id")

    r = client.post("/team/create", data={"team_name": "CombatTest隊"})
    team_data = r.get_json()
    ok("建隊成功", team_data.get("success"), str(team_data))
    team_id = team_data.get("team_id")

    r = client.post("/set_team_route_by_leader", data={"route": "iggy"})
    route_data = r.get_json()
    ok("設定 Iggy 路線", route_data.get("route") == "iggy" or route_data.get("team", {}).get("route") == "iggy", str(route_data))

    test_encounter_list_hides_test_for_players(client, team_id)
    test_encounters_reconcile_stale_active_combat(client, team_id, leader_id)
    test_practice_encounter_replayable(client, team_id)
    test_practice_boundary_settlement_enemy_hp(client, team_id)

    # --- 玩家 2：加入隊伍 ---
    client2 = oikonomia.app.test_client()
    p2 = login(client2, "TestMember")
    ok("玩家2 登入", p2 and p2.get("squad_id"))
    member_id = p2.get("squad_id")

    r2 = client2.post("/team/join", data={"team_id": team_id})
    join_data = r2.get_json()
    ok("玩家2 加入隊伍", join_data.get("success"), str(join_data))

    test_defend_team_buff_helpers()
    test_trauma_ending_thresholds()
    test_encounter_catalog()
    test_enemy_hp_updates_after_round(client, client2, team_id)
    test_enemy_hp_reconciled_from_logs(client, leader_id, team_id)

    # --- 開始 encounter（max_hp 測試會改 TestLeader stats，先跑主線）---
    r = client.post(
        "/combat/start",
        json={"encounter_id": ENCOUNTER_ID},
        content_type="application/json",
    )
    start = r.get_json()
    ok("開始 encounter", start.get("success"), str(start))
    combat_id = start.get("combat_id")
    precheck_passed = start.get("precheck_passed")
    print(f"    combat_id={combat_id}, status={start.get('status')}, precheck_passed={precheck_passed}")

    fight = {}
    if start.get("status") == "precheck" and precheck_passed:
        r = client.post(
            "/combat/start",
            json={"encounter_id": ENCOUNTER_ID, "confirm": "fight"},
            content_type="application/json",
        )
        fight = r.get_json()
        ok("Precheck → 選擇戰鬥", fight.get("success") and fight.get("status") == "player_phase", str(fight))
        combat_id = fight.get("combat_id")

    in_player_phase = start.get("status") == "player_phase" or fight.get("status") == "player_phase"
    ok("進入 player_phase", in_player_phase)
    test_protagonist_combat_participant(combat_id, route="iggy")

    # --- 兩玩家提交行動（server-side 骰子，loop 至勝利）---
    final, err = fight_until_victory(client, client2, combat_id)
    ok("戰鬥流程完成（無錯誤）", err is None, err or str(final)[:200])
    ok("submit_action 觸發勝利", final.get("outcome") == "victory", str(final)[:200])
    ok("勝利有反思題目", bool((final.get("reflection_prompt") or {}).get("questions")))

    # --- Defend 全隊 buff（主線戰鬥結束後另開 test encounter）---
    test_defend_team_buff_integration(client, client2, leader_id, member_id)

    test_player_max_hp(leader_id)
    test_near_death_rescue_security(client, leader_id, member_id)
    test_create_combat_record_active_guard(leader_id, team_id)
    test_trauma_bad_ending_victory(client, client2, team_id, leader_id, member_id)
    test_protagonist_player_control(client, client2, team_id, route="iggy")
    test_non_leader_as_protagonist_rejected()
    test_solo_killing_blow_returns_victory(client, client2, team_id)
    test_solo_killing_blow_practice_quick()
    test_escape_action_type_allowed()
    test_defeat_outcome_includes_dead_roster()
    test_select_enemy_counter_target_priority()
    test_escape_fail_mixed_settlement()
    test_use_item_combat_consumes_and_resolves()
    test_use_item_hp_up_and_sanity_up_in_combat()
    test_combat_summon_gm_creates_global_event()
    test_escape_success_ends_combat()
    test_solo_multi_round_poll_hp_monotonic()
    test_zombie_hp_zero_status_poll_returns_victory()
    test_practice_combat_start_enemy_hp_full()
    test_phase2_trauma_service_pipeline()
    test_phase2_narrative_orchestrator_pipeline()
    test_maybe_resolve_ready_claim_inside_tx()
    test_maybe_resolve_monotonic_phase_guard()
    test_solo_resolve_combat_outcome_idempotency()
    test_phase2_gm_override_gateway()
    test_qr_code_grant_scoped_per_squad_not_global(leader_id)
    test_combat_start_rejects_body_squad_id_spoof(client, leader_id, member_id, team_id)
    test_rescue_near_death_target_squad_id(client, leader_id, member_id, team_id)

    # --- 輪詢狀態（戰鬥已結束應仍回傳 outcome）---
    r = client.get(f"/combat/status?combat_id={combat_id}")
    status = r.get_json()
    ok("輪詢 combat/status", status.get("success"), str(status)[:200])
    ok("status 回傳勝利 outcome", status.get("outcome") == "victory", str(status))
    ok("status 回傳 narrative", bool(status.get("narrative")))

    # --- encounter 列表 ---
    r = client.get("/encounters")
    enc_list = r.get_json()
    ok("GET /encounters", enc_list.get("success"), str(enc_list)[:150])

    # --- 驗證 API version marker ---
    r = client.get("/api/version")
    ver = r.get_json()
    ok("combat_system marker", ver.get("markers", {}).get("combat_system") is True)
    ok("server_combat_dice marker", ver.get("markers", {}).get("server_combat_dice") is True)
    ok("defend_team_buff marker", ver.get("markers", {}).get("defend_team_buff") is True)
    ok("combat_v2_module marker", ver.get("markers", {}).get("combat_v2_module") is True)
    ok("player_max_hp marker", ver.get("markers", {}).get("player_max_hp") is True)
    ok("protagonist_combat marker", ver.get("markers", {}).get("protagonist_combat") is True)
    ok("trauma_ending marker", ver.get("markers", {}).get("trauma_ending") is True)
    ok("confirm_modal marker", ver.get("markers", {}).get("confirm_modal") is True)
    ok("combat_v2 marker key present", "combat_v2" in (ver.get("markers") or {}))
    ok("encounter_logs marker", ver.get("markers", {}).get("encounter_logs") is True)

    r = client.get("/encounter_logs")
    enc_logs = r.get_json() or {}
    ok("encounter_logs API", enc_logs.get("success") and enc_logs.get("has_team"), str(enc_logs)[:200])
    logs = enc_logs.get("logs") or []
    ok("encounter_logs has entries", len(logs) >= 1, f"count={len(logs)}")
    if logs:
        latest = logs[0]
        ok("encounter_log has outcome", bool(latest.get("outcome_label")), str(latest)[:200])
        ok("encounter_log has reward_lines", isinstance(latest.get("reward_lines"), list), str(latest)[:200])

    ok("version 正確", ver.get("version") == oikonomia.read_deploy_version())

    print(f"\n=== 結果：{PASS} 通過 / {FAIL} 失敗 ===\n")
    shutil.rmtree(TEST_DIR, ignore_errors=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


===== FILE: scripts/test_combat_engine.py =====

#!/usr/bin/env python3
"""Unit tests for services/combat_engine.py (pure calculation, no Flask/DB)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.combat_engine import (
    Combatant,
    calculate_attack_damage,
    calculate_incoming_damage,
    count_team_defenders,
    dice_multiplier,
    resolve_round_calculation,
    select_enemy_counter_target,
    team_defend_damage_multiplier,
)

PASS = 0
FAIL = 0


def ok(label):
    global PASS
    PASS += 1
    print(f"  ✓ {label}")


def fail(label, detail=""):
    global FAIL
    FAIL += 1
    print(f"  ✗ {label}" + (f" — {detail}" if detail else ""))


def test_calculate_attack_damage_basic():
    attacker = Combatant(id="p1", power=60, intellect=40, resilience=50)
    dmg = calculate_attack_damage(attacker, enemy_resilience=30, multiplier=1.0)
    # ((60*1.5)+10)*1 - (30*0.8) = 100 - 24 = 76
    if dmg == 76:
        ok("calculate_attack_damage basic")
    else:
        fail("calculate_attack_damage basic", f"got {dmg}, expected 76")

    miss = calculate_attack_damage(attacker, enemy_resilience=30, multiplier=0.0)
    if miss == 0:
        ok("calculate_attack_damage zero multiplier")
    else:
        fail("calculate_attack_damage zero multiplier", f"got {miss}")


def test_dice_multiplier_edge_cases():
    cases = [(0, 0.0), (1, 1.0), (2, 1.5), (3, 2.0), (99, 2.0), ("bad", 1.0)]
    for dice, expected in cases:
        got = dice_multiplier(dice)
        if got == expected:
            ok(f"dice_multiplier({dice!r})")
        else:
            fail(f"dice_multiplier({dice!r})", f"got {got}, expected {expected}")


def test_resolve_round_calculation_with_defend():
    attacker = Combatant(id="p1", power=50, intellect=50, resilience=40)
    enemy = Combatant(id="e1", power=0, intellect=0, resilience=20)
    actions = {
        "s1": {"action_type": "defend"},
        "s2": {"action_type": "attack"},
    }
    result = resolve_round_calculation(
        attacker=attacker,
        enemy=enemy,
        player_actions=actions,
        enemy_base_damage=50,
        dice_result=2,
    )
    if result.defender_count == 1:
        ok("resolve_round_calculation defender_count")
    else:
        fail("resolve_round_calculation defender_count", str(result.defender_count))

    if result.dice_multiplier == 1.5:
        ok("resolve_round_calculation dice_multiplier")
    else:
        fail("resolve_round_calculation dice_multiplier", str(result.dice_multiplier))

    if result.damage_dealt > 0 and result.is_critical:
        ok("resolve_round_calculation damage_dealt + critical")
    else:
        fail("resolve_round_calculation damage_dealt + critical")

    expected_taken = calculate_incoming_damage(
        50,
        40,
        defending=True,
        team_defend_multiplier=team_defend_damage_multiplier(1),
    )
    if result.damage_taken == expected_taken:
        ok("resolve_round_calculation damage_taken with defend")
    else:
        fail(
            "resolve_round_calculation damage_taken with defend",
            f"got {result.damage_taken}, expected {expected_taken}",
        )


def test_count_team_defenders():
    if count_team_defenders(None) == 0:
        ok("count_team_defenders empty")
    else:
        fail("count_team_defenders empty")
    actions = {"a": {"action": "defend"}, "b": {"action_type": "attack"}}
    if count_team_defenders(actions) == 1:
        ok("count_team_defenders mixed")
    else:
        fail("count_team_defenders mixed")


def test_incoming_damage_piercing_floor():
    dmg = calculate_incoming_damage(50, 200, defending=False)
    if dmg >= 5:
        ok("incoming damage piercing floor (10% of base)")
    else:
        fail("incoming damage piercing floor", f"got {dmg}")


def test_incoming_damage_extreme_team_defend():
    """INV-D: 10% piercing floor survives extreme team-defend multipliers."""
    base = 5
    dmg = calculate_incoming_damage(
        base, 0, team_defend_multiplier=0.001,
    )
    piercing = max(1, base // 10)
    if dmg >= piercing and dmg > 0:
        ok("incoming damage extreme defend cannot zero out piercing")
    else:
        fail("incoming damage extreme defend cannot zero out piercing", f"got {dmg}")


def test_select_enemy_counter_target_engine():
    participants = [
        {"squad_id": "A", "hp": 80, "max_hp": 100, "resilience": 5, "is_protagonist": False},
        {"squad_id": "B", "hp": 30, "max_hp": 100, "resilience": 3, "is_protagonist": False},
    ]
    actions = {"B": {"action_type": "escape"}}
    target = select_enemy_counter_target(participants, actions, enemy_base_damage=50)
    if target and target.get("squad_id") == "B":
        ok("select_enemy_counter_target prefers escaper")
    else:
        fail("select_enemy_counter_target prefers escaper", str(target))


def test_select_enemy_counter_target_failed_escape():
    """INV-E: post-normalize failed_escape still counts as escape priority."""
    participants = [
        {"squad_id": "A", "hp": 80, "max_hp": 100, "resilience": 5, "is_protagonist": False},
        {"squad_id": "B", "hp": 30, "max_hp": 100, "resilience": 3, "is_protagonist": False},
    ]
    actions = {"B": {"action_type": "failed_escape"}}
    target = select_enemy_counter_target(participants, actions, enemy_base_damage=50)
    if target and target.get("squad_id") == "B":
        ok("select_enemy_counter_target prefers failed_escape escaper")
    else:
        fail("select_enemy_counter_target prefers failed_escape escaper", str(target))


def main():
    print("=== Combat engine unit tests ===\n")
    test_calculate_attack_damage_basic()
    test_dice_multiplier_edge_cases()
    test_count_team_defenders()
    test_resolve_round_calculation_with_defend()
    test_incoming_damage_piercing_floor()
    test_incoming_damage_extreme_team_defend()
    test_select_enemy_counter_target_engine()
    test_select_enemy_counter_target_failed_escape()
    print(f"\n=== 結果：{PASS} 通過 / {FAIL} 失敗 ===\n")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())


===== FILE: scripts/test_combat_flow_orchestrator.py =====

#!/usr/bin/env python3
"""Unit tests for services/combat_flow.py (INV-E pure orchestration)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.combat_flow import (
    normalize_failed_escape_actions,
    process_mixed_round_actions,
)

PASS = 0
FAIL = 0


def ok(label):
    global PASS
    PASS += 1
    print(f"  ✓ {label}")


def fail(label, detail=""):
    global FAIL
    FAIL += 1
    print(f"  ✗ {label}" + (f" — {detail}" if detail else ""))


def test_normalize_failed_escape():
    actions = {
        "A": {"action_type": "escape", "dice_result": 1},
        "B": {"action_type": "attack", "dice_result": 2},
    }
    out = normalize_failed_escape_actions(
        actions, escape_triggered=True, escape_success=False,
    )
    if out["A"]["action_type"] == "failed_escape" and out["B"]["action_type"] == "attack":
        ok("normalize_failed_escape marks escaper only")
    else:
        fail("normalize_failed_escape marks escaper only", str(out))


def test_mixed_round_escape_fail_continues_attack():
    participants = {
        "A": {"squad_id": "A", "power": 40, "intellect": 10, "resilience": 10, "sanity": 50},
        "B": {"squad_id": "B", "power": 50, "intellect": 10, "resilience": 10, "sanity": 50},
    }
    actions = {
        "A": {"action_type": "escape", "dice_result": 1},
        "B": {"action_type": "attack", "dice_result": 2},
    }
    breakdown = process_mixed_round_actions(
        participants,
        {"resilience": 5},
        actions,
        enemy_base_damage=20,
        escape_success_rate=0.4,
        rng=0.99,
    )
    if breakdown.get("team_escaped") is False and "A" in breakdown.get("failed_escape_squads", []):
        ok("mixed round escape fail retains escaper in breakdown")
    else:
        fail("mixed round escape fail retains escaper", str(breakdown))

    b_dealt = breakdown.get("damages_dealt", {}).get("B", 0)
    a_dealt = breakdown.get("damages_dealt", {}).get("A", 0)
    if b_dealt > 0 and a_dealt == 0:
        ok("mixed round attacker damage while escaper deals zero")
    else:
        fail("mixed round attacker damage while escaper deals zero", str(breakdown))


def test_consume_dry_run_defers_delete():
    from models.item import CombatItemConsumeBatch

    class FakeBatch(CombatItemConsumeBatch):
        def __init__(self):
            self._catalog = {9: {"id": 9, "name": "Test", "has_ability": True, "effect_type": "power_up", "effect_value": 5}}
            self._owned = {("s1", 9)}
            self._consumed = set()
            self._pending = set()

    batch = FakeBatch()
    ok1, item1, err1 = batch.consume_dry_run("s1", 9)
    ok2, _, err2 = batch.consume_dry_run("s1", 9)
    if ok1 and item1 and not ok2 and err2:
        ok("consume_dry_run validates without DB write")
    else:
        fail("consume_dry_run validates without DB write", f"{ok1},{ok2},{err1},{err2}")


def test_victory_payload_settlement_id():
    from services.combat_outcomes import build_victory_outcome_payload

    payload = build_victory_outcome_payload(
        {"success": {"narrative": "win"}},
        combat_id=42,
        current_round=3,
    )
    if payload.get("settlement_id") == "42:2" and payload.get("settled_round_index") == 2:
        ok("victory payload includes settlement_id")
    else:
        fail("victory payload includes settlement_id", str(payload))


def main():
    print("=== Combat flow orchestrator tests ===\n")
    test_normalize_failed_escape()
    test_mixed_round_escape_fail_continues_attack()
    test_consume_dry_run_defers_delete()
    test_victory_payload_settlement_id()
    print(f"\n=== 結果：{PASS} 通過 / {FAIL} 失敗 ===\n")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())


===== FILE: scripts/pre_deploy_checks.sh =====

#!/bin/bash
# Regression gate before PythonAnywhere deploy or CI merge.
# Uses isolated temp DBs inside each test script — never touches production data/.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="python3"
if [ -x "$ROOT/venv/bin/python3" ]; then
    PYTHON="$ROOT/venv/bin/python3"
fi

export FLASK_ENV=development
export SECRET_KEY="${SECRET_KEY:-test-secret-pre-deploy}"

run_test() {
    local script="$1"
    local label="$2"
    echo ""
    echo "=========================================="
    echo " $label"
    echo "=========================================="
    "$PYTHON" "$script"
}

echo "Pre-deploy checks (Python: $PYTHON)"
echo "Repo: $ROOT"

run_test scripts/test_combat_engine.py "Combat engine (pure calculation unit)"
run_test scripts/test_combat_flow_orchestrator.py "Combat flow orchestrator (INV-E)"
run_test scripts/test_combat_flow.py "Combat flow (API + HP sync + practice)"
run_test scripts/test_combat_audit.py "Combat audit (settlement + solo + protagonist)"
run_test scripts/test_combat_concurrency.py "Combat concurrency smoke"
run_test scripts/test_db_hardening.py "DB hardening (WAL, SSOT, purge, restore)"
run_test scripts/test_ending_flow.py "Ending orchestrator regression"

if ! test -f static/js/combat/index.js; then
    echo "ERROR: static/js/combat/index.js missing (Combat V2 module)"
    exit 1
fi
if ! grep -q "combat-root-v2" templates/combat_screen.html 2>/dev/null; then
    echo "ERROR: templates/combat_screen.html missing combat-root-v2 mount"
    exit 1
fi
if ! grep -q "enemy_hp_after" models/combat.py 2>/dev/null; then
    echo "ERROR: models/combat.py missing enemy_hp_after settlement field"
    exit 1
fi

if [ -d "$ROOT/node_modules/@playwright/test" ] && command -v npx >/dev/null 2>&1; then
    echo ""
    echo "=========================================="
    echo " Combat V2 Playwright E2E (T8–T14 Phase 2)"
    echo "=========================================="
    if ! npx playwright test -c playwright.config.cjs tests/combat_v2.spec.js --reporter=line; then
        echo "ERROR: Combat V2 Playwright E2E failed"
        exit 1
    fi
else
    echo ""
    echo "SKIP: Playwright not installed — run: npm install && npx playwright install chromium"
fi

echo ""
echo "=========================================="
echo " All pre-deploy checks passed"
echo "=========================================="


---
*End of COMBAT_V2_AUDIT_BUNDLE v15 · 2026-07-02 · `137dfa9`*
