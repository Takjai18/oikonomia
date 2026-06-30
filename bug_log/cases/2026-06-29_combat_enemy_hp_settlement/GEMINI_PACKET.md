# GEMINI_PACKET — BUG-2026-001（自包含，可直接貼入 Gemini）

> **生成時間**：2026-06-30 03:03 UTC  
> **Git commit**：`6391b22`  
> **Phase**：3 — **Delay 殘留** + settlement v10（instant settlement 已上線）  
> **用途**：Gemini **讀唔到** Google Drive bug_log 時，將**成個檔案** Copy & Paste 到 Gemini chat。  
> **重新生成**：`bash scripts/build_gemini_packet.sh`

---

## 點樣俾 Gemini（下次照做）

1. **最簡單（推薦）**：打開本檔 → 全選 Copy → 貼到 Gemini
2. **加文檔**：另貼 `GEMINI_REVIEW.md` §16 或只貼 `GEMINI_CONSULT.md`
3. **GitHub Raw**（若 Gemini 支援 URL）：
   - 本檔：https://raw.githubusercontent.com/Takjai18/oikonomia/6391b22/bug_log/cases/2026-06-29_combat_enemy_hp_settlement/GEMINI_PACKET.md
   - Consult：https://raw.githubusercontent.com/Takjai18/oikonomia/6391b22/bug_log/cases/2026-06-29_combat_enemy_hp_settlement/GEMINI_CONSULT.md
   - index.html（大檔）：https://raw.githubusercontent.com/Takjai18/oikonomia/6391b22/templates/index.html
4. **唔好用**：Drive 資料夾連結、`attachments/` 舊快照

---

## A. GEMINI_CONSULT（Phase 3 摘要）

# GEMINI_CONSULT — BUG-2026-001（Phase 3：Delay 殘留 + Settlement v10）

> Phase 1（HP／modal）→ v4–v10 已多輪修復。Phase 2（人工 delay 移除 → `combat_instant_settlement`）已實作。  
> **本檔聚焦**：實機仍覺得慢嘅 **殘留 delay** + settlement／victory 過渡是否穩健。  
> 完整脈絡：`REPORT.md` §13–§19 · `decisions_log.md` § instant settlement · § Combat Settlement Modal Bug

## 一句話

**PA `6391b22`（`combat_flow_v10`）後端／CI 全綠；Henry／Tak 實機 settlement 大致 OK，但戶外仍覺得「攻擊→HP→modal」有 lag；另需確認 v10 final-hit 過渡無 regression。**

## 實機條件（2026-06-30）

| 項目 | 值 |
|------|-----|
| 玩家 | Henry · `PLAYER-75406` · Iggy · 單人 |
| PA / GitHub | `6391b22`（deploy 後 curl 核對） |
| Markers | `combat_instant_settlement`, `combat_flow_v7`–`v10`, `enemy_hp_sync_v7`, `settlement_breakdown_v1` |
| 已驗 encounter | `practice_iggy_01_quick`、`practice_iggy_03_boundary`（instant checklist OK） |
| 新修復待驗 | `practice_iggy_02_leech`（情緒寄生影 final-hit stuck → v10） |

## 已確認

- 後端 `enemy.hp` / `round_settlement.enemy_hp_after` / DB log **一致**（`test_combat_flow.py` 192+ 項）
- `COMBAT_SETTLEMENT_DELAY_MS` 已移除；`pauseMs: 0`；settlement modal **即時**（無 1500ms 人工等待）
- v8–v10：`settlementModalShown`、`isFinalHitOrVictory`、`resolveEnemyHpAfter` 防 duplicate + final-hit 過渡

## 殘留 delay 懷疑（Phase 3 — 請 Gemini 重點查）

| 來源 | 位置 | 體感 |
|------|------|------|
| 擲骰動畫 | `DICE_ROLL_PRESETS.normal`：8×55ms ≈ **440ms**（提交**前**） | 攻擊 confirm 前仍要等 |
| 網絡 RTT | `submit_action` + `loadCombatStatus` poll（3s interval） | 戶外 Wi‑Fi 慢時體感 lag |
| HP 顯示時機 | `deferEnemyHp`：modal 期間主畫面**舊 HP**；按「確定」先 `applyPendingSettlementHp` | 玩家以為 HP 未跌 |
| Poll 凍結 | `combatAwaitingSettlementAck` 期間 `loadCombatStatus` 只做 `syncHpOnlyFromPoll` | 必要但可能加重「無反應」感 |
| 血條 vs 數字 | `syncEnemyHpDisplay` instant；血條 width 即時 | 應已同步，請確認無 regression |

**注意**：唔好再建議恢復 `COMBAT_SETTLEMENT_DELAY_MS` 或 1500ms modal delay（已決策移除）。

## 請 Gemini 產出

1. **Delay**：在保留 v6–v10 race guard 前提下，邊條路徑仍可縮至「攻擊 confirm 後 <1s 見 HP+modal」？具體 pseudo-diff（只 frontend）。
2. **Settlement**：v10 `isFinalHitOrVictory` / `buildVictoryTransitionPayload` 有無 edge case（poll 與 submit 競態、duplicate modal、stuck buttons）？
3. **測試**：點樣加 contract／Playwright  assert「round_resolved → `#combat-round-settlement-modal` visible < 1500ms」？
4. **優先序**：delay vs 雙人隊未驗 vs 營會前穩定性 — P0/P1 建議。

## 必讀（GitHub `6391b22`）

見 `GEMINI_REVIEW.md` §16 檔案包；**唔使全讀** `index.html`，跟 packet §D 摘錄即可。

## 點讀

```bash
bash scripts/build_gemini_packet.sh
# → 貼 bug_log/cases/.../GEMINI_PACKET.md 全文入 Gemini
```
---

## B. 請 Gemini 回答（Phase 3：Delay + Settlement v10）

1. instant settlement 後，剩餘 delay 最可能來自邊 1–2 條 path？（擲骰 / deferEnemyHp / poll 3s / 網絡）
2. `deferEnemyHp` 會否令玩家誤判「HP 冇跌」？建議改法？
3. v10 `isFinalHitOrVictory` 有無 submit vs poll race 仍 stuck 或 duplicate modal？
4. 最低風險 patch 順序（營會前）？
5. 點樣自動化「confirm 後 modal visible < 1.5s」？

**勿建議**：恢復 `COMBAT_SETTLEMENT_DELAY_MS` 或 1500ms 人工 modal 等待（已決策移除）。

## C. DOM 目標

| Element ID | 用途 |
|------------|------|
| `enemy-hp-current` | 敵人當前 HP 數字 |
| `enemy-hp-bar` | 血條 width % |
| `combat-round-settlement-modal` | 傷害結算 modal |
| `round-settlement-confirm-btn` | 確定／確定，查看勝利 |

函數鏈：`submitAction` → `handleCombatRoundResolved` / `finishCombatVictoryFromPayload` → `showFullRoundSettlement` → `continueCombatAfterRound` → `loadCombatStatus`（poll）

## D. 關鍵 JavaScript（templates/index.html 摘錄）


### `templates/index.html` L1238–L1271

```javascript
        const DICE_ROLL_PRESETS = {
            fast: { intervalMs: 40, maxRolls: 6, pauseMs: 0 },
            normal: { intervalMs: 55, maxRolls: 8, pauseMs: 0 },
            slow: { intervalMs: 75, maxRolls: 10, pauseMs: 0 },
        };

        function syncHpOnlyFromPoll(data) {
            if (!data?.enemy || pendingSettlementHpPayload) return;
            syncEnemyHpDisplay(applySettlementEnemyHp(data));
        }

        /** 確認結算後即刻扣血（無 delay）；主畫面結算期間保持舊 HP */
        function applyPendingSettlementHp() {
            const data = pendingSettlementHpPayload;
            pendingSettlementHpPayload = null;
            if (!data?.enemy) return;
            const enriched = applySettlementEnemyHp(data);
            const settlement = getRoundSettlement(enriched);
            const teamDealt = Number(settlement.team_damage_dealt) || 0;
            const enemyDealt = Number(settlement.enemy_damage_dealt) || 0;
            if (teamDealt > 0) showDamageNumber('enemy-panel', teamDealt, false);
            if (enemyDealt > 0) showDamageNumber('player-panel', enemyDealt, false);
            syncEnemyHpDisplay(enriched);
            const roundDmgEl = document.getElementById('enemy-round-damage');
            if (roundDmgEl && teamDealt > 0) {
                roundDmgEl.textContent = `本回合對敵 -${teamDealt.toLocaleString('zh-Hant')}`;
                setVisible(roundDmgEl, true);
            }
        }

        function getDiceRollConfig() {
            const preset = getGameSettings().diceRollSpeed || 'normal';
            return DICE_ROLL_PRESETS[preset] || DICE_ROLL_PRESETS.normal;
        }
```

### `templates/index.html` L1576–L1595

```javascript
        let lastShownSettlementPhase = 0;
        let lastSettlementDisplayKey = '';
        let victorySettlementModalCombatId = null;
        // Settlement guard (combat_flow_v9): idempotent per round, blocks duplicate modal
        let currentSettlementRound = null;
        let settlementModalShown = false;
        let settlementCombatId = null;
        let combatAwaitingSettlementAck = false;
        let settlementTimerPending = false;
        let pendingSettlementHpPayload = null;
        let lastCombatStatus = null;
        let combatEnemyHpSeen = null;
        let lastAnimatedEnemyHp = null;
        let pendingVictoryAfterSettlement = null;
        let combatFinalizingVictory = false;
        let victoryFinalizeInProgress = false;
        let victorySettlementAcknowledgedCombatId = null;
        let combatPhaseLocked = false;
        let combatPhaseLockedRound = 0;
        let lastCombatUiSnapshotKey = '';
```

### `templates/index.html` L1832–L1886

```javascript
        function syncEnemyHpDisplay(data, options = {}) {
            if (options && typeof options === 'object' && options.hp != null
                && options.enemyOverride === undefined) {
                options = { enemyOverride: options };
            }
            const enemyOverride = options.enemyOverride ?? null;
            const ctx = enemyOverride
                ? { ...data, enemy: { ...(data?.enemy || {}), ...enemyOverride } }
                : data;
            let hp = resolveAuthoritativeEnemyHp(ctx);
            if (!Number.isFinite(hp)) return;
            const combatId = ctx?.combat_id || currentCombatId;
            const sameCombat = !combatId || combatId === currentCombatId;
            if (sameCombat && Number.isFinite(lastAnimatedEnemyHp) && hp > lastAnimatedEnemyHp) {
                hp = lastAnimatedEnemyHp;
            }
            const maxHp = Number(ctx?.enemy?.max_hp || ctx?.enemy?.hp) || 1;
            const prevHpRaw = Number.isFinite(lastAnimatedEnemyHp)
                ? lastAnimatedEnemyHp
                : resolveAuthoritativeEnemyHp(lastCombatStatus);
            const prevHp = Number.isFinite(prevHpRaw) ? prevHpRaw : hp;
            const fmt = (n) => Number(n).toLocaleString('zh-Hant');
            safeSetText('enemy-hp-max', fmt(maxHp));
            safeSetText('enemy-hp-current', fmt(hp));
            const bar = document.getElementById('enemy-hp-bar');
            const targetPct = Math.max(0, Math.min(100, Math.round(hp / maxHp * 100)));
            if (bar) {
                bar.style.width = `${targetPct}%`;
                if (Number.isFinite(prevHp) && hp < prevHp) flashEnemyHpBar();
            }
            combatEnemyHpSeen = hp;
            lastAnimatedEnemyHp = hp;
            safeSetText('enemy-stat-hp', fmt(hp));
            const roundDmgEl = document.getElementById('enemy-round-damage');
            if (roundDmgEl && Number.isFinite(prevHp) && hp < prevHp) {
                const delta = prevHp - hp;
                roundDmgEl.textContent = `敵人剩餘 ${fmt(hp)}（本回合 -${fmt(delta)}）`;
                setVisible(roundDmgEl, true);
            }
        }

        function applySettlementEnemyHp(data) {
            if (!data?.enemy) return data;
            const settlement = getRoundSettlement(data);
            let remaining = Number.isFinite(Number(settlement.enemy_hp_after))
                ? Number(settlement.enemy_hp_after)
                : parseEnemyRemainingHpFromStatus(data);
            const current = Number(data.enemy.hp);
            if (remaining == null && !Number.isFinite(current)) return data;
            const candidates = [];
            if (Number.isFinite(current)) candidates.push(current);
            if (remaining != null) candidates.push(remaining);
            if (!candidates.length) return data;
            return { ...data, enemy: { ...data.enemy, hp: Math.min(...candidates) } };
        }
```

### `templates/index.html` L2065–L2110

```javascript
                };
        }

        function settlementRoundKey(data) {
            const cid = data?.combat_id || currentCombatId || '';
            const phase = data?.round ?? data?.current_phase ?? 'unknown';
            return `${cid}:${phase}`;
        }

        function clearSettlementModalGuard() {
            settlementModalShown = false;
            currentSettlementRound = null;
        }

        function markSettlementModalShown(data) {
            settlementModalShown = true;
            currentSettlementRound = settlementRoundKey(data);
        }

        function settlementDisplayKey(data) {
            const cid = data?.combat_id || currentCombatId || '';
            const phase = Number(data?.current_phase) || 0;
            const victory = !!(data?.outcome || pendingVictoryAfterSettlement);
            return `${cid}:p${phase}:v${victory ? 1 : 0}`;
        }

        function shouldShowRoundSettlement(data) {
            if (combatAwaitingSettlementAck || settlementTimerPending) return false;
            const phase = Number(data?.current_phase) || 0;
            const resolved = !!(data?.round_resolved || data?.status === 'round_resolved');
            const advancedWhileWaiting = combatWaitingForRound
                && phase > (Number(combatSubmittedPhase) || 0);
            if (!resolved && !advancedWhileWaiting) return false;
            if (resolved) return phase > lastShownSettlementPhase;
            return phase > lastShownSettlementPhase;
        }

        function resetCombatSettlementState() {
            combatAwaitingSettlementAck = false;
            settlementTimerPending = false;
            pendingSettlementHpPayload = null;
            pendingVictoryAfterSettlement = null;
            lastShownSettlementPhase = 0;
            lastSettlementDisplayKey = '';
            victorySettlementModalCombatId = null;
            clearSettlementModalGuard();
```

### `templates/index.html` L2184–L2290

```javascript
        function continueCombatAfterRound() {
            applyPendingSettlementHp();
            settlementTimerPending = false;
            clearTimeout(showFullRoundSettlement._modalTimer);
            showFullRoundSettlement._modalTimer = null;
            hideRoundSettlementModal();
            hideSinglePlayerResultModal();
            combatWaitingForRound = false;
            resetCombatDiceUi();
            selectedDice = null;
            const panel = document.getElementById('player-panel');
            if (panel) panel.style.opacity = '1';
            if (pendingVictoryAfterSettlement) {
                const victoryPayload = pendingVictoryAfterSettlement;
                const combatId = victoryPayload.combat_id || currentCombatId;
                pendingVictoryAfterSettlement = null;
                stopCombatPolling();
                victorySettlementAcknowledgedCombatId = combatId;
                combatAwaitingSettlementAck = false;
                clearSettlementModalGuard();
                void finalizeCombatVictoryFromPayload(victoryPayload);
                return;
            }
            const resumeData = pendingSettlementHpPayload || lastCombatStatus;
            if (isFinalHitOrVictory(resumeData)) {
                const victoryPayload = buildVictoryTransitionPayload(resumeData);
                const combatId = victoryPayload.combat_id || currentCombatId;
                combatAwaitingSettlementAck = false;
                clearSettlementModalGuard();
                pendingVictoryAfterSettlement = null;
                stopCombatPolling();
                victorySettlementAcknowledgedCombatId = combatId;
                void finalizeCombatVictoryFromPayload(victoryPayload);
                return;
            }
            clearSettlementModalGuard();
            combatAwaitingSettlementAck = false;
            lastCombatStatusJson = '';
            lastCombatUiSnapshotKey = '';
            const phase = lastCombatStatus?.current_phase || 0;
            if (phase) lastDicePhase = phase;
            loadCombatStatus(false);
        }

        // combat_instant_settlement: 零人工 delay；HP + 傷害結算 modal 即時
        // combat_flow_v7: v6 + 勝利結算唔 poll、modal 即時、確認後唔重彈
        // combat_flow_v8: settlementDisplayKey 防重複；mustShow 強制出 modal
        // combat_flow_v9: settlementModalShown + currentSettlementRound idempotent guard
        // combat_flow_v10: final hit → pendingVictoryAfterSettlement before modal
        function showFullRoundSettlement(data) {
            const phase = Number(data?.current_phase) || 0;
            const combatId = data?.combat_id || currentCombatId;
            const roundKey = settlementRoundKey(data);
            const displayKey = settlementDisplayKey(data);
            if (settlementModalShown && currentSettlementRound === roundKey) {
                return;
            }
            if (combatFinalizingVictory || victoryFinalizeInProgress) return;
            if (victorySettlementAcknowledgedCombatId
                && combatId === victorySettlementAcknowledgedCombatId) return;
            if ((pendingVictoryAfterSettlement || data?.outcome || isFinalHitOrVictory(data))
                && victorySettlementModalCombatId === combatId) return;
            if (lastSettlementDisplayKey === displayKey) return;
            if (combatAwaitingSettlementAck) {
                return;
            }
            if (phase > 0 && phase <= lastShownSettlementPhase
                && (!combatId || combatId === settlementCombatId || combatId === currentCombatId)) {
                return;
            }
            data = applySettlementEnemyHp(data);
            if (isFinalHitOrVictory(data) && !pendingVictoryAfterSettlement) {
                pendingVictoryAfterSettlement = buildVictoryTransitionPayload(data);
            }
            const isVictorySettlement = !!pendingVictoryAfterSettlement
                || !!data?.outcome
                || isFinalHitOrVictory(data);
            pendingSettlementHpPayload = data;
            settlementTimerPending = false;
            combatAwaitingSettlementAck = true;
            if (phase > lastShownSettlementPhase) {
                lastShownSettlementPhase = phase;
            }
            if (combatId) settlementCombatId = combatId;
            combatWaitingForRound = false;
            hideCombatWaitingPanel();
            hideSinglePlayerResultModal();
            hideCombatModal();
            clearTimeout(showFullRoundSettlement._modalTimer);
            showFullRoundSettlement._modalTimer = null;
            lockCombatActionsForSettlement();
            lastSettlementDisplayKey = displayKey;
            markSettlementModalShown(data);
            if (isVictorySettlement && combatId) {
                victorySettlementModalCombatId = combatId;
            }
            showRoundSettlementModal(data);
            updateCombatUI(data, {
                damageDelay: 0,
                skipActionEnable: true,
                deferEnemyHp: true,
            });
            if (isVictorySettlement) {
                stopCombatPolling();
            } else {
                startCombatPolling(COMBAT_POLL_INTERVAL_NORMAL);
            }
```

### `templates/index.html` L2336–L2425

```javascript
        async function finishCombatVictoryFromPayload(data) {
            if (victoryFinalizeInProgress) return;
            data = ensureVictorySettlementPayload(data);
            const combatId = data?.combat_id || currentCombatId;

            if (combatAwaitingSettlementAck && victorySettlementModalCombatId === combatId
                && isFinalHitOrVictory(data)) {
                if (!pendingVictoryAfterSettlement) {
                    pendingVictoryAfterSettlement = buildVictoryTransitionPayload(data);
                }
                return;
            }

            if (victorySettlementAcknowledgedCombatId
                && combatId === victorySettlementAcknowledgedCombatId) {
                if (!combatAwaitingSettlementAck && !victoryFinalizeInProgress) {
                    await finalizeCombatVictoryFromPayload(data);
                }
                return;
            }
            if (combatFinalizingVictory) return;

            if (combatAwaitingSettlementAck) {
                if (!pendingVictoryAfterSettlement) {
                    pendingVictoryAfterSettlement = data;
                }
                return;
            }

            const roundResolved = data?.round_resolved || data?.status === 'round_resolved';
            const phase = Number(data?.current_phase) || 0;
            const hasSettlementUi = victoryPayloadHasSettlement(data) && (roundResolved || data?.outcome);

            if (hasSettlementUi) {
                if (combatAwaitingSettlementAck && pendingVictoryAfterSettlement) return;
                if (victorySettlementModalCombatId === combatId) return;
                if (victorySettlementAlreadyShown(combatId, phase)) {
                    if (!combatAwaitingSettlementAck) {
                        pendingVictoryAfterSettlement = data;
                    }
                    return;
                }
                pendingVictoryAfterSettlement = data;
                const enriched = applySettlementEnemyHp({
                    ...data,
                    enemy: { ...(data.enemy || lastCombatStatus?.enemy || {}), hp: 0 },
                    round_resolved: true,
                    active: true,
                });
                showFullRoundSettlement(enriched);
                return;
            }
            await finalizeCombatVictoryFromPayload(data);
        }

        async function finalizeCombatVictoryFromPayload(data) {
            if (victoryFinalizeInProgress) return;
            victoryFinalizeInProgress = true;
            combatFinalizingVictory = true;
            stopCombatPolling();
            combatAwaitingSettlementAck = false;
            settlementTimerPending = false;
            pendingSettlementHpPayload = null;
            pendingVictoryAfterSettlement = null;
            clearSettlementModalGuard();
            clearTimeout(showFullRoundSettlement._modalTimer);
            showFullRoundSettlement._modalTimer = null;
            combatWaitingForRound = false;
            hideCombatWaitingPanel();
            hideRoundSettlementModal();
            hideSinglePlayerResultModal();
            hideCombatModal();
            try {
                if (data?.log_entries?.length) {
                    processCombatDamageAnimations(data, 0);
                }
                resetCombatEnemyHpTracking(0);
                updateEnemyCombatStats(
                    { ...(data.enemy || lastCombatStatus?.enemy || {}), hp: 0 },
                    data.enemy_description || lastCombatStatus?.enemy_description || '',
                );
                let payload = data;
                if (!payload.outcome) {
                    try {
                        const url = currentCombatId
                            ? `/combat/status?combat_id=${currentCombatId}`
                            : '/combat/status';
                        const res = await fetchNoCache(url);
                        const fresh = await res.json();
                        if (fresh.outcome) payload = { ...payload, ...fresh };
```

### `templates/index.html` L2440–L2525

```javascript
                combatFinalizingVictory = false;
            }
        }

        // combat_flow_v10: final hit uses round_settlement.enemy_hp_after (not only enemy.hp)
        function resolveEnemyHpAfter(data) {
            if (!data) return null;
            const settlement = getRoundSettlement(data);
            const fromSettlement = Number(settlement.enemy_hp_after);
            if (Number.isFinite(fromSettlement)) return fromSettlement;
            const hp = Number(data.enemy?.hp);
            if (Number.isFinite(hp)) return hp;
            return null;
        }

        function isFinalHitOrVictory(data) {
            if (!data) return false;
            if (data.outcome) return true;
            if (data.status === 'ended' || data.winner) return true;
            const hpAfter = resolveEnemyHpAfter(data);
            return hpAfter !== null && hpAfter <= 0;
        }

        function shouldFinishCombatVictory(data) {
            return isFinalHitOrVictory(data);
        }

        function buildVictoryTransitionPayload(data) {
            const hpAfter = resolveEnemyHpAfter(data);
            const enemyHp = Number.isFinite(hpAfter) ? Math.max(0, hpAfter) : 0;
            return {
                ...data,
                outcome: data.outcome || (data.winner === 'enemy' ? 'defeat' : 'victory'),
                enemy: { ...(data.enemy || lastCombatStatus?.enemy || {}), hp: enemyHp },
                round_resolved: true,
            };
        }

        function handleCombatRoundResolved(data) {
            if (!data) return;
            if (isVictoryFlowLocked(data?.combat_id)) return;
            if (combatAwaitingSettlementAck || settlementTimerPending) {
                return;
            }
            if (shouldFinishCombatVictory(data)) {
                finishCombatVictoryFromPayload(data);
                return;
            }
            setCombatPhaseLock(false);
            hideCombatModal();
            const settled = applySettlementEnemyHp(data);
            if (isFinalHitOrVictory(settled)) {
                finishCombatVictoryFromPayload(buildVictoryTransitionPayload(settled));
                return;
            }
            const settlement = getRoundSettlement(settled);
            const hasDamage = Number(settlement.team_damage_dealt) > 0
                || (settled.log_entries || []).some(e => e?.type === 'damage');
            const mustShow = (settled.round_resolved || settled.status === 'round_resolved') && hasDamage;
            const hasSettlementPayload = !!(settled.round_settlement || data.round_settlement);
            if (hasSettlementPayload && (mustShow || hasDamage)) {
                showFullRoundSettlement(settled);
                return;
            }
            if (mustShow || shouldShowRoundSettlement(settled)) {
                showFullRoundSettlement(settled);
                return;
            }
            combatWaitingForRound = false;
            hideCombatWaitingPanel();
            updateCombatUI(settled, { damageDelay: 0 });
            syncEnemyHpDisplay(settled);
            startCombatPolling(COMBAT_POLL_INTERVAL_NORMAL);
        }

        function formatTimerDisplay(totalSeconds) {
            const s = Math.max(0, totalSeconds);
            const m = Math.floor(s / 60);
            const sec = s % 60;
            return `${m}:${String(sec).padStart(2, '0')}`;
        }

        function startPhaseCountdown(deadlineIso) {
            if (combatPhaseTimer) clearInterval(combatPhaseTimer);
            const timerEl = document.getElementById('phase-timer');
            if (!deadlineIso || !timerEl) return;
```

### `templates/index.html` L3641–L3725

```javascript
        async function loadCombatStatus(showLoading, options = {}) {
            try {
                if (victoryFinalizeInProgress) return;
                if (combatFinalizingVictory) return;
                if (!options.skipSquadRefresh) {
                    await refreshSquadFromServer();
                }
                const url = currentCombatId
                    ? `/combat/status?combat_id=${currentCombatId}`
                    : '/combat/status';
                const res = await fetchNoCache(url);
                if (!res.ok) throw new Error(`combat/status HTTP ${res.status}`);
                const data = await res.json();
                if (data.success === false && !data.my_state && !data.active) return;

                if (settlementTimerPending || combatAwaitingSettlementAck) {
                    if (queueVictoryDuringSettlement(data)) return;
                    syncHpOnlyFromPoll(data);
                    return;
                }

                if (isCombatVictoryPayload(data)
                    || (isFinalHitOrVictory(data) && Number(resolveEnemyHpAfter(data)) <= 0)) {
                    combatWaitingForRound = false;
                    hideCombatWaitingPanel();
                    hideSinglePlayerResultModal();

                    if (victoryFinalizeInProgress || combatFinalizingVictory) {
                        return;
                    }

                    if (combatAwaitingSettlementAck || settlementTimerPending) {
                        queueVictoryDuringSettlement(data);
                        return;
                    }

                    if (victoryPayloadHasSettlement(data) || isFinalHitOrVictory(data)) {
                        await finishCombatVictoryFromPayload(
                            buildVictoryTransitionPayload(data),
                        );
                    } else {
                        resetCombatSettlementState();
                        hideRoundSettlementModal();
                        showCombatResult(data);
                    }

                    const statusRes = await fetchNoCache('/status');
                    updateDashboard(await statusRes.json());
                    return;
                }

                const roundResolved = data.status === 'round_resolved' || data.round_resolved;
                const phaseAdvanced = combatWaitingForRound
                    && data.current_phase > combatSubmittedPhase
                    && !data.my_state?.submitted;

                if (roundResolved || phaseAdvanced) {
                    if (phaseAdvanced && !data.round_settlement && data.log_entries?.length) {
                        data.round_settlement = buildClientRoundSettlement(data.log_entries);
                    }
                    if (shouldFinishCombatVictory(data)) {
                        await finishCombatVictoryFromPayload(data);
                        return;
                    }
                    handleCombatRoundResolved(data);
                    return;
                }

                if (shouldFinishCombatVictory(data)) {
                    await finishCombatVictoryFromPayload(data);
                    return;
                }

                if (data.round_settlement && !settlementModalShown
                    && !combatAwaitingSettlementAck && !victoryFinalizeInProgress) {
                    const pollSettled = applySettlementEnemyHp({
                        ...data,
                        round_resolved: true,
                        active: data.active !== false,
                    });
                    const pollSettlement = getRoundSettlement(pollSettled);
                    const pollHasDamage = Number(pollSettlement.team_damage_dealt) > 0
                        || (pollSettled.log_entries || []).some(e => e?.type === 'damage');
                    if (pollHasDamage) {
                        handleCombatRoundResolved(pollSettled);
```

### `templates/index.html` L3768–L3825

```javascript
        async function submitAction() {
            if (combatAwaitingSettlementAck || settlementTimerPending) {
                showToast('請先等待本回合傷害結算', 'error');
                return;
            }
            if (combatPhaseLocked || lastCombatStatus?.status === 'resolving') {
                showToast('回合結算中，請稍候', 'error');
                return;
            }
            if (selectedAction === 'use_item' && !selectedItemId) {
                showToast('請先選擇要使用的物品', 'error');
                return;
            }
            if (COMBAT_DICE_ACTIONS.has(selectedAction) && selectedDice === null) {
                showToast('請先選擇攻擊行動並完成擲骰', 'error');
                return;
            }
            if (selectedDice === null) selectedDice = 1;

            const confirmBtn = document.getElementById('modal-confirm-btn');
            if (confirmBtn) confirmBtn.disabled = true;

            const payload = {
                combat_id: currentCombatId,
                action_type: selectedAction,
            };
            if (controllingProtagonist && lastCombatStatus?.protagonist_player_control) {
                payload.as_protagonist = true;
            }
            if (selectedAction === 'use_item' && selectedItemId) payload.item_id = selectedItemId;

            let data;
            try {
                const res = await fetch('/combat/submit_action', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
                data = await res.json();
            } catch (e) {
                if (confirmBtn) confirmBtn.disabled = false;
                showToast('提交失敗，請稍後再試', 'error');
                return;
            }
            if (!data.success && data.error) {
                if (confirmBtn) confirmBtn.disabled = false;
                if (data.error.includes('結算中')) {
                    setCombatPhaseLock(true, lastCombatStatus || { current_phase: combatSubmittedPhase });
                    startCombatPolling(COMBAT_POLL_INTERVAL_RESOLVING);
                }
                showToast(data.error, 'error');
                return;
            }
            if (data.outcome || shouldFinishCombatVictory(data)) {
                await finishCombatVictoryFromPayload(data);
                return;
            }
```

## E. 後端 Python（API 合約摘錄）


### `routes/combat.py` L161–L278

```python
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
def combat_status_api():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

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
            return jsonify({
                "success": True,
                "active": False,
                "winner": winner,
                "outcome": "defeat",
                "narrative": (encounter or {}).get("failure", {}).get("narrative"),
            })
        return jsonify({"success": True, "active": False, "winner": winner})

    encounter = load_encounter(combat["encounter_id"])
    settings = (encounter or {}).get("combat_settings", {})

    round_just_resolved = False
    participants = None
    if combat.get("status") == "player_phase":
        participants = get_combat_participants(combat)
        should_resolve = (
            all_phase_actions_submitted(combat, participants)
            or combat_phase_expired(combat, settings)
        )
        if should_resolve:
            prev_phase = int(combat.get("current_phase") or 0)
            prev_log_len = len(combat.get("logs") or [])
            combat, winner = resolve_player_phase(combat["id"])
            actor = get_squad(session["squad_id"])
            actor_team_id = actor.get("team_id") if actor else None
            if winner == "squad":
                combat = get_combat(combat["id"]) or combat
                return jsonify(build_victory_outcome_response(
                    combat, encounter, session["squad_id"], team_id=actor_team_id,
                ))
            if winner == "enemy":
                return jsonify({**_combat_outcome_json("enemy", encounter), "active": False})
            combat = get_combat(combat["id"]) or combat
            finished = combat_outcome_if_finished(
                combat,
                encounter,
                team_id=actor_team_id,
                squad_id=session["squad_id"],
            )
            if finished:
                return jsonify({**finished, "active": False})
            participants = None
            round_just_resolved = (
                int(combat.get("current_phase") or 0) > prev_phase
                or len(combat.get("logs") or []) > prev_log_len
            )

    payload = build_combat_status_response(
        combat, encounter, session["squad_id"], participants=participants,
    )
    _attach_round_settlement(payload, combat=combat)
    payload["active"] = combat.get("status") not in ("ended", "precheck")
    payload["in_precheck"] = combat.get("status") == "precheck"
    if combat.get("status") == "resolving":
        payload["resolving"] = True

    if round_just_resolved:
        payload["status"] = "round_resolved"
        payload["round_resolved"] = True
        payload["full_preview"] = _build_full_preview_from_status(payload)
    elif combat.get("status") == "player_phase":
        if participants is None:
            participants = get_combat_participants(combat) or []
        active_ids = get_active_combat_member_ids(participants or [])
        phase_actions = combat.get("phase_actions") or {}
        if session["squad_id"] in phase_actions and len(phase_actions) < len(active_ids):
            payload["waiting_for_teammates"] = True
            payload["submitted_count"] = len(phase_actions)
            payload["total_active"] = len(active_ids)

    raw_enemy_hp = (payload.get("enemy") or {}).get("hp")
    enemy_hp = int(raw_enemy_hp) if raw_enemy_hp is not None else 1
```

### `routes/combat.py` L331–L475

```python
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
def combat_submit_action_api():
    if "squad_id" not in session:
        return jsonify({"error": "未登入"}), 401

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
        acting_id = get_controllable_protagonist_squad_id(
            squad["team_id"], squad.get("route"), encounter, story_stage,
        )
        if not acting_id:
            return jsonify({"success": False, "error": "此階段不可代替主角行動"}), 400
    else:
        acting_id = session["squad_id"]

    participants = get_combat_participants(combat) or []
    actor_state = next(
        (p for p in participants if p["squad_id"] == acting_id),
        squad if acting_id == session["squad_id"] else None,
    )
    if not actor_state:
        return jsonify({"success": False, "error": "找不到行動者"}), 400

    if actor_state.get("near_death_until"):
        try:
            if datetime.now() < datetime.fromisoformat(actor_state["near_death_until"]):
                label = "主角" if as_protagonist else "你"
                return jsonify({"success": False, "error": f"{label}已陷入瀕死，等待救援"}), 400
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
    combat["phase_actions"] = phase_actions
    save_combat(combat_id, phase_actions=phase_actions)

    participants = get_combat_participants(combat) or []
    required_ids = get_phase_submit_required_ids(combat, participants)
    winner = None
    if all_phase_actions_submitted(combat, participants) or combat_phase_expired(combat, settings):
        combat, winner = resolve_player_phase(combat_id)

    if winner == "squad":
        combat = get_combat(combat_id) or combat
        payload = build_victory_outcome_response(
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

    if len(required_ids) > 1 and len(phase_actions) < len(required_ids):
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
```

### `models/combat.py` L931–L1010

```python
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
```

## F. CI 已通過

- `scripts/test_combat_engine.py` — 14 項純計算
- `scripts/test_combat_flow.py` — 192+ 項（含 killing blow、poll HP、practice）
- `scripts/pre_deploy_checks.sh` — 全綠

## G. 實機狀態（2026-06-30）

| 項目 | 狀態 |
|------|------|
| Commit | `6391b22` |
| Markers | `combat_instant_settlement`, `combat_flow_v7`–`v10`, `enemy_hp_sync_v7` |
| Henry instant checklist | ✅ OK（quick + boundary） |
| 殘留 | **Delay 體感**未完全解決；v10 final-hit 待 Henry 驗 `practice_iggy_02_leech` |
| 後端 | Combat log / `enemy_hp_after` 正確 |

## H. 相關文檔

- `GEMINI_REVIEW.md` §16 — 檔案包清單
- `bug_log/.../REPORT.md` §13–§19
- `decisions_log.md` § instant settlement

---

*由 scripts/build_gemini_packet.sh 自動生成 · 改 code 後重新 run*
