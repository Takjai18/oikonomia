# GEMINI_PACKET — BUG-2026-001（自包含，可直接貼入 Gemini）

> **生成時間**：2026-06-30 03:15 UTC  
> **Git commit**：`40a2c53`  
> **Phase**：4 — Safari **0 傷害** + Chrome **勝利後重複結算**（v12 patch）
> **用途**：Gemini **讀唔到** Google Drive bug_log 時，將**成個檔案** Copy & Paste 到 Gemini chat。  
> **重新生成**：`bash scripts/build_gemini_packet.sh`

---

## 點樣俾 Gemini（下次照做）

1. **最簡單（推薦）**：打開本檔 → 全選 Copy → 貼到 Gemini
2. **加文檔**：另貼 `GEMINI_REVIEW.md` §16 或只貼 `GEMINI_CONSULT.md`
3. **GitHub Raw**（若 Gemini 支援 URL）：
   - 本檔：https://raw.githubusercontent.com/Takjai18/oikonomia/40a2c53/bug_log/cases/2026-06-29_combat_enemy_hp_settlement/GEMINI_PACKET.md
   - Consult：https://raw.githubusercontent.com/Takjai18/oikonomia/40a2c53/bug_log/cases/2026-06-29_combat_enemy_hp_settlement/GEMINI_CONSULT.md
   - index.html（大檔）：https://raw.githubusercontent.com/Takjai18/oikonomia/40a2c53/templates/index.html
4. **唔好用**：Drive 資料夾連結、`attachments/` 舊快照

---

## A. GEMINI_CONSULT（Phase 3 摘要）

# GEMINI_CONSULT — BUG-2026-001（Phase 4：Safari 0 傷害 + Chrome 勝利後重複結算）

> Phase 1–3 → v4–v11 已多輪修復。Henry Safari §16 resolved；**2026-06-30 新回報** reopen 兩個子議題。  
> 完整脈絡：`REPORT.md` §21–§23 · `decisions_log.md` § instant settlement

## 一句話

**PA `40a2c53`（v11）後：Vini Safari 長戰結算顯示 0 傷害；Henry Chrome 勝利畫面後再彈結算。v12 patch 已實作，待實機驗證。**

## 實機條件（2026-06-30 · 新回報）

| 子議題 | 玩家 | 瀏覽器 | Encounter | 症狀 |
|--------|------|--------|-----------|------|
| §21 | Vini | **Safari** macOS | `practice_iggy_04_marathon` | 非 0 骰；結算 UI **全 0**（HP 有變） |
| §22 | Henry · `PLAYER-75406` | **Chrome** macOS | （長戰／killing blow） | 結算→勝利→**再結算** |

| 項目 | 值 |
|------|-----|
| Baseline commit | `40a2c53`（`combat_flow_v11`） |
| v12 markers | `combat_flow_v12`, `combatVictorySequenceCompleteId`, `enrichRoundSettlementData` |
| 對照 | Henry Chrome §21 **無** 0 傷害；Henry Safari §16 **無** §22 |

## Code review 結論（Phase 4 — 請 Gemini 確認）

### §22 Critical：勝利後重複結算

**根因鏈**：

```
continueCombatAfterRound → finalizeCombatVictoryFromPayload
  → showCombatResult → resetCombatSessionState()
  → settlementModalShown = false, victorySettlementAcknowledgedCombatId = null
  → in-flight loadCombatStatus(poll) 仍帶 round_settlement
  → handleCombatRoundResolved → showFullRoundSettlement (再彈)
```

**v12 修復**：

- `combatVictorySequenceCompleteId` — finalize 前標記；poll / `showFullRoundSettlement` / `loadCombatStatus` early return
- `showCombatResult(..., { fromVictoryFinalize: true })` — `keepVictoryLock` 唔清勝利鎖

### §21 High：Safari 結算 0 傷害

**根因鏈**：

```
getRoundSettlement → round_settlement 存在但 team_damage_dealt=0 或 breakdown.total=0
  → buildSettlementBreakdown 早期 return 空 breakdown
  → renderSettlementBreakdown 顯示全 0
  （enemy HP 仍由 applySettlementEnemyHp / enemy_hp_after 更新）
```

**v12 修復**：

- `enrichRoundSettlementData` — 從 `log_entries` 用 `buildClientRoundSettlement` 補數字
- `buildSettlementBreakdown` — breakdown total=0 但 team_damage_dealt>0 時重算

**Safari 因素**：可能疊加 **快取舊 JS**；實機必須硬刷新 + 核對 `/api/version` `combat_flow_v12: true`。

## 請 Gemini 產出（Phase 4）

1. **§22**：`combatVictorySequenceCompleteId` 有無 race（`showCombatResult` 被 defeat 路徑呼叫、`resetCombatSessionState` 其他 caller）？
2. **§21**：`enrichRoundSettlementData` 會否誤用**上一回合** log？如何加 `current_phase` / summary 邊界 assert？
3. **測試**：最小 Playwright／contract —「勝利畫面 visible 後 `#combat-round-settlement-modal` 不可再 flex」？
4. **優先序**：v12 deploy 後 Vini Safari vs Henry Chrome 驗證順序？

**勿建議**：恢復 1500ms modal delay；勿移除 instant settlement。

## 必讀

```bash
bash scripts/build_gemini_packet.sh
# → GEMINI_PACKET.md（含 v12 摘錄）
```

見 `GEMINI_REVIEW.md` §17。
---

## B. 請 Gemini 回答（Phase 4：0 傷害 + 勝利後重複結算）

1. `showCombatResult` → `resetCombatSessionState` 係咪 §22 根因？`combatVictorySequenceCompleteId` 夠唔夠？
2. `enrichRoundSettlementData` 會否誤 parse 舊回合 log？點加 phase 邊界？
3. Safari 0 傷害除 stale settlement 外，仲有無 `breakdown` early return 以外嘅 path？
4. Playwright assert：勝利 panel visible 後 settlement modal 不可再 `flex`？
5. v12 deploy 後邊個 browser／玩家先驗？

**勿建議**：恢復 1500ms modal delay。

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

### `templates/index.html` L1576–L1605

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
        // combat_flow_v12: blocks poll/UI from re-opening settlement after victory sequence
        let combatVictorySequenceCompleteId = null;
        let combatPhaseLocked = false;
        let combatPhaseLockedRound = 0;
        let lastCombatUiSnapshotKey = '';
        let lastCombatStatusJson = '';
        const COMBAT_POLL_INTERVAL_NORMAL = 3000;
        const COMBAT_POLL_INTERVAL_WAITING = 4000;
        const COMBAT_POLL_INTERVAL_RESOLVING = 1000;

        function appendCacheBust(url) {
            const sep = url.includes('?') ? '&' : '?';
            return `${url}${sep}t=${Date.now()}`;
```

### `templates/index.html` L1655–L1685

```javascript
        }

        function isCombatVictoryPayload(data) {
            if (!data) return false;
            return !!(data.outcome || data.status === 'ended' || data.winner);
        }

        function isCombatVictorySequenceComplete(combatId) {
            const cid = combatId || currentCombatId;
            return !!(combatVictorySequenceCompleteId && cid === combatVictorySequenceCompleteId);
        }

        function markCombatVictorySequenceComplete(combatId) {
            const cid = combatId || currentCombatId;
            if (cid) combatVictorySequenceCompleteId = cid;
        }

        function queueVictoryDuringSettlement(data) {
            if (isCombatVictoryPayload(data)) {
                pendingVictoryAfterSettlement = data;
                return true;
            }
            if (shouldFinishCombatVictory(data)) {
                pendingVictoryAfterSettlement = {
                    ...data,
                    outcome: data.winner === 'enemy' ? 'defeat' : 'victory',
                };
                return true;
            }
            return false;
        }
```

### `templates/index.html` L1988–L2070

```javascript
            return 'teammate';
        }

        function settlementHasDamageNumbers(settlement) {
            if (!settlement) return false;
            if (Number(settlement.team_damage_dealt) > 0) return true;
            if (Number(settlement.enemy_damage_dealt) > 0) return true;
            return (settlement.player_hits || []).some(h => Number(h.damage) > 0)
                || (settlement.counter_hits || []).some(h => Number(h.damage) > 0);
        }

        function enrichRoundSettlementData(data) {
            if (!data) return data;
            let settlement = getRoundSettlement(data);
            if (settlementHasDamageNumbers(settlement)) {
                const bd = settlement.breakdown;
                const bdTotal = Number(bd?.dealt?.total) || 0;
                if (!bd || bdTotal > 0 || Number(settlement.team_damage_dealt) === 0) {
                    return { ...data, round_settlement: settlement };
                }
                settlement = { ...settlement, breakdown: undefined };
            }
            const logs = data.log_entries || data.log || [];
            const normalized = Array.isArray(logs) && logs[0]?.type
                ? logs
                : logs.map((line) => ({ type: 'event', message: String(line) }));
            if (!normalized.length) return data;
            const built = buildClientRoundSettlement(normalized);
            if (!settlementHasDamageNumbers(built)) return data;
            return {
                ...data,
                round_settlement: built,
                round_resolved: data.round_resolved ?? data.status === 'round_resolved',
                round_enemy_damage: built.team_damage_dealt,
                round_player_damage: built.enemy_damage_dealt,
            };
        }

        function buildSettlementBreakdown(data, settlement) {
            const teamDealt = Number(settlement?.team_damage_dealt) || 0;
            if (settlement?.breakdown) {
                const bd = settlement.breakdown;
                const bdTotal = Number(bd?.dealt?.total) || 0;
                if (bdTotal > 0 || teamDealt === 0) return bd;
            }
            const lookup = buildCombatParticipantLookup(data);
            const dealt = { player: 0, protagonist: 0, teammate: 0 };
            const taken = { player: 0, protagonist: 0, teammate: 0 };
            const dealtNames = { player: [], protagonist: [], teammate: [] };
            const takenNames = { player: [], protagonist: [], teammate: [] };
            (settlement?.player_hits || []).forEach((hit) => {
                const role = hit.role || resolveHitRole(hit.player, lookup);
                const dmg = Number(hit.damage) || 0;
                if (!dealt[role]) dealt[role] = 0;
                dealt[role] += dmg;
                if (dmg > 0 && hit.player) dealtNames[role].push(`${hit.player} -${dmg}`);
            });
            (settlement?.counter_hits || []).forEach((hit) => {
                const role = hit.role || resolveHitRole(hit.target, lookup);
                const dmg = Number(hit.damage) || 0;
                if (!taken[role]) taken[role] = 0;
                taken[role] += dmg;
                if (dmg > 0 && hit.target) takenNames[role].push(`${hit.target} -${dmg}`);
            });
            const enemyDealt = Number(settlement?.enemy_damage_dealt) || 0;
            return {
                dealt: {
                    ...dealt,
                    total: teamDealt || dealt.player + dealt.protagonist + dealt.teammate,
                    details: dealtNames,
                },
                taken: {
                    ...taken,
                    total: enemyDealt || taken.player + taken.protagonist + taken.teammate,
                    details: takenNames,
                },
                enemy: {
                    damage_taken: teamDealt || dealt.player + dealt.protagonist + dealt.teammate,
                    damage_dealt: enemyDealt || taken.player + taken.protagonist + taken.teammate,
                },
            };
        }

```

### `templates/index.html` L2120–L2160

```javascript
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

        function isRoundSettlementModalVisible() {
            const modal = document.getElementById('combat-round-settlement-modal');
            return !!(modal && modal.classList.contains('flex'));
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
```

### `templates/index.html` L2288–L2360

```javascript
        // combat_flow_v7: v6 + 勝利結算唔 poll、modal 即時、確認後唔重彈
        // combat_flow_v8: settlementDisplayKey 防重複；mustShow 強制出 modal
        // combat_flow_v9: settlementModalShown + currentSettlementRound idempotent guard
        // combat_flow_v10: final hit → pendingVictoryAfterSettlement before modal
        // combat_flow_v11: instant modal (no setTimeout); HP sync with modal; soften victory guard
        // combat_flow_v12: victory sequence lock; enrich settlement from logs when API zeros
        function showFullRoundSettlement(data) {
            const combatId = data?.combat_id || currentCombatId;
            if (isCombatVictorySequenceComplete(combatId)) return;
            data = enrichRoundSettlementData(data);
            const phase = Number(data?.current_phase) || 0;
            const roundKey = settlementRoundKey(data);
            const displayKey = settlementDisplayKey(data);
            if (settlementModalShown && currentSettlementRound === roundKey) {
                if (isFinalHitOrVictory(data) && !isRoundSettlementModalVisible()) {
                    showRoundSettlementModal(applySettlementEnemyHp(data));
                    lockCombatActionsForSettlement();
                }
                return;
            }
            if (combatFinalizingVictory || victoryFinalizeInProgress) return;
            if (victorySettlementAcknowledgedCombatId
                && combatId === victorySettlementAcknowledgedCombatId) return;
            if (lastSettlementDisplayKey === displayKey) return;
            if (combatAwaitingSettlementAck && isRoundSettlementModalVisible()) {
                return;
            }
            if (combatAwaitingSettlementAck) {
                combatAwaitingSettlementAck = false;
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
            const hpSynced = applySettlementEnemyHp(data);
            updateCombatUI(hpSynced, {
                damageDelay: 0,
                skipActionEnable: true,
                deferEnemyHp: false,
            });
            syncEnemyHpDisplay(hpSynced);
            if (isVictorySettlement) {
                stopCombatPolling();
            } else {
                startCombatPolling(COMBAT_POLL_INTERVAL_NORMAL);
            }
```

### `templates/index.html` L2395–L2520

```javascript
                };
            }
            return data;
        }

        function victorySettlementAlreadyShown(combatId, phase) {
            if (!(phase > 0) || phase > lastShownSettlementPhase) return false;
            const cid = combatId || currentCombatId;
            return !cid || cid === settlementCombatId || cid === currentCombatId;
        }

        async function finishCombatVictoryFromPayload(data) {
            if (victoryFinalizeInProgress) return;
            const combatId = data?.combat_id || currentCombatId;
            if (isCombatVictorySequenceComplete(combatId)) return;
            data = ensureVictorySettlementPayload(enrichRoundSettlementData(data));

            if (combatAwaitingSettlementAck && isFinalHitOrVictory(data)) {
                if (isRoundSettlementModalVisible()) {
                    if (!pendingVictoryAfterSettlement) {
                        pendingVictoryAfterSettlement = buildVictoryTransitionPayload(data);
                    }
                    return;
                }
                combatAwaitingSettlementAck = false;
                victorySettlementModalCombatId = null;
                clearSettlementModalGuard();
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
                if (victorySettlementModalCombatId === combatId && isRoundSettlementModalVisible()) {
                    return;
                }
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
                    } catch (_) { /* use local payload */ }
                }
                const outcome = payload.outcome
                    || (payload.winner === 'enemy' ? 'defeat' : 'victory');
                markCombatVictorySequenceComplete(payload.combat_id || currentCombatId);
                showCombatResult({
                    ...payload,
                    outcome,
                    active: false,
                }, { fromVictoryFinalize: true });
                const statusRes = await fetchNoCache('/status');
                updateDashboard(await statusRes.json());
                combatItemsLoaded = false;
            } finally {
                victoryFinalizeInProgress = false;
                combatFinalizingVictory = false;
            }
        }
```

### `templates/index.html` L2545–L2595

```javascript
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
            if (isCombatVictorySequenceComplete(data?.combat_id)) return;
            data = enrichRoundSettlementData(data);
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
```

### `templates/index.html` L3468–L3525

```javascript
            resetCombatEnemyHpTracking(null);
            showCombatScreen();
            await loadCombatStatus(true, { skipSquadRefresh: true });
        }

        function showCombatResult(data, options = {}) {
            resetCombatSessionState({ keepVictoryLock: !!options.fromVictoryFinalize });
            resetCombatEnemyHpTracking(null);
            controllingProtagonist = false;
            setVisible(document.getElementById('combat-screen'), false);
            setVisible(document.getElementById('combat-near-death-overlay'), false);
            setVisible(document.getElementById('combat-precheck-modal'), false);
            setVisible(document.getElementById('combat-lobby'), false);
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

        function updateNearDeathOverlay(me) {
            const overlay = document.getElementById('combat-near-death-overlay');
            const countdownEl = document.getElementById('near-death-countdown');
            const inNearDeath = me?.near_death_until && new Date(me.near_death_until) > new Date();
            setVisible(overlay, !!inNearDeath);
            if (inNearDeath && countdownEl) {
                const remaining = Math.max(0, Math.floor((new Date(me.near_death_until) - Date.now()) / 1000));
                countdownEl.textContent = formatTimerDisplay(remaining);
            }
        }
```

### `templates/index.html` L3715–L3810

```javascript
                else if (me.submitted) hintEl.textContent = `已提交：${COMBAT_ACTION_LABELS[me.action_type] || me.action_type}（骰 ${me.dice_result ?? '?' }），等待隊友…`;
                else if (isResolving || combatPhaseLocked) hintEl.textContent = '回合結算中，請稍候…';
                else if (uiData.status !== 'player_phase') hintEl.textContent = '敵人回合結算中…';
                else if (actionModalRolling) hintEl.textContent = '系統擲骰中，請稍候…';
                else if (isCombatModalOpen()) hintEl.textContent = '請於彈窗內確認並結束本回合';
                else if (selectedAction === 'use_item' && !selectedItemId) hintEl.textContent = '請選擇要使用的物品';
                else hintEl.textContent = '選擇行動後確認提交';
            }
        }

        async function loadCombatStatus(showLoading, options = {}) {
            try {
                if (isCombatVictorySequenceComplete(currentCombatId)) return;
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
                    && !combatAwaitingSettlementAck && !victoryFinalizeInProgress
                    && !isCombatVictorySequenceComplete(data.combat_id)
                    && !data.outcome && data.status !== 'ended') {
                    const pollSettled = applySettlementEnemyHp({
                        ...data,
                        round_resolved: true,
                        active: data.active !== false,
                    });
                    const pollSettlement = getRoundSettlement(pollSettled);
                    const pollHasDamage = Number(pollSettlement.team_damage_dealt) > 0
                        || (pollSettled.log_entries || []).some(e => e?.type === 'damage');
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
| Commit | `40a2c53` |
| Markers | `combat_flow_v11`–`v12`, `combatVictorySequenceCompleteId`, `enrichRoundSettlementData` |
| §21 Vini Safari | 結算 0 傷害（marathon）— v12 待驗 |
| §22 Henry Chrome | 勝利後重複結算 — v12 待驗 |
| Henry Safari §16 | 先前通過；Chrome 新 regression |

## H. 相關文檔

- `GEMINI_REVIEW.md` §16 — 檔案包清單
- `bug_log/.../REPORT.md` §13–§19
- `decisions_log.md` § instant settlement

---

*由 scripts/build_gemini_packet.sh 自動生成 · 改 code 後重新 run*
