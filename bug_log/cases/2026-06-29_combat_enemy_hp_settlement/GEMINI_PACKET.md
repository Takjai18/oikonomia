# GEMINI_PACKET — BUG-2026-001（自包含，可直接貼入 Gemini）

> **生成時間**：2026-06-29 15:41 UTC  
> **Git commit**：`fd3a036`  
> **用途**：Gemini **讀唔到** Google Drive  資料夾時，將**成個檔案** Copy & Paste 到 Gemini chat。  
> **重新生成**：`bash scripts/build_gemini_packet.sh`

---

## 點樣俾 Gemini（下次照做）

1. **最簡單**：打開本檔 `GEMINI_PACKET.md` → 全選 Copy → 貼到 Gemini
2. **GitHub Raw**（若 Gemini 支援 URL）：
   - 本檔：https://raw.githubusercontent.com/Takjai18/oikonomia/fd3a036/bug_log/cases/2026-06-29_combat_enemy_hp_settlement/GEMINI_PACKET.md
   - 完整 index.html：https://raw.githubusercontent.com/Takjai18/oikonomia/fd3a036/templates/index.html
   - routes/combat.py：https://raw.githubusercontent.com/Takjai18/oikonomia/fd3a036/routes/combat.py
3. **唔好用**：Drive 資料夾連結（Gemini API 索引唔到 .md / bug_log）
4. **可選**：將本檔 Upload 為 **Google Doc**（單檔分享連結）再俾 Gemini

---

## A. GEMINI_CONSULT（精簡摘要）

# GEMINI_CONSULT — BUG-2026-001（Henry 實機仍失敗）

> 俾 Gemini Architect 嘅精簡入口。完整脈絡見同目錄 `REPORT.md` §12。

## 一句話

**PA 已 deploy `641da28`（`enemy_hp_sync_v3: true`），CI 單人 `practice_iggy_03_boundary` 多回合 API 測試全綠，但 Henry（Iggy 線、單人）實機戰鬥中敵 HP 顯示仍唔更新。**

## 實機條件

| 項目 | 值 |
|------|-----|
| 玩家 | Henry |
| 路線 | Iggy |
| 隊伍 | 單人 |
| Encounter | `practice_iggy_03_boundary`（140 HP） |
| PA version | `641da28`（2026-06-29 curl 確認） |

## 已排除（自動化）

- 後端 `submit_action` / `combat/status`：`enemy.hp` 每回合遞減（`test_solo_multi_round_poll_hp_monotonic`）
- 開局 full HP（`test_practice_combat_start_enemy_hp_full`）
- Killing blow settlement payload（`test_solo_killing_blow_practice_quick`）

## 懷疑方向（請取捨）

1. Safari 快取舊 `index.html`（server marker 新、client JS 舊）
2. 前端多源 HP（`resolveAuthoritativeEnemyHp` Math.min + monotonic + `lastCombatStatus`）仍有 race
3. `combatAwaitingSettlementAck` 卡住令 poll 唔 refresh DOM
4. 140 HP 血條變化太細（UX 误判）— 需確認**數字**有冇變
5. 無 DOM/integration test 覆蓋

## 請產出

1. 最可能單一根因 + code path（附行號）
2. 推薦修復方案（pseudo-diff）同 trade-off
3. Henry 最少採證步驟
4. 建議新增測試（最好含 DOM 或 contract assert）

## 必讀檔案（GitHub `641da28`）

- `templates/index.html` — `syncEnemyHpDisplay`, `loadCombatStatus`, `handleCombatRoundResolved`
- `routes/combat.py` — `/combat/status`, `/combat/submit_action`
- `models/combat.py` — `reconcile_enemy_hp`, `build_enemy_combat_stats`
- `scripts/test_combat_flow.py` — `test_solo_multi_round_poll_hp_monotonic`

## attachments 注意

`attachments/` 係 `3c89f62` 快照，**唔反映最新修復**。請以 GitHub main 為準。
---

## B. §12.5 請 Gemini 回答

1. API 正確但 DOM 唔更新 — 最可能邊條 code path？
2. 方案 A（前端簡化）vs B（後端 `display_enemy_hp`）vs C（cache-bust + 只用 `enemy.hp`）— 邊個風險最低？
3. Henry 最少採證：Network JSON、Console、Safari 清快取？
4. 架構級建議（拆 JS module、Service Worker）？

## C. DOM 目標（HP 顯示）

| Element ID | 用途 |
|------------|------|
| `enemy-hp-current` | 敵人當前 HP 數字 |
| `enemy-hp-max` | 敵人最大 HP |
| `enemy-hp-bar` | 血條 width % |
| `enemy-stat-hp` | 敵人面板 stat |
| `enemy-round-damage` | 本回合傷害提示 |

更新函數鏈：`loadCombatStatus` / `submitAction` → `handleCombatRoundResolved` → `updateCombatUI` → `updateEnemyCombatStats` → **`syncEnemyHpDisplay`**

## D. 關鍵 JavaScript（templates/index.html）


### `templates/index.html` L1785–L2199

```javascript
        function resolveAuthoritativeEnemyHp(data) {
            if (!data) return null;
            const settlement = getRoundSettlement(data);
            const fromSettlement = Number(settlement.enemy_hp_after);
            const fromEnemy = Number(data.enemy?.hp);
            const fromLog = parseEnemyRemainingHpFromStatus(data);
            const candidates = [];
            if (Number.isFinite(fromEnemy)) candidates.push(fromEnemy);
            if (Number.isFinite(fromSettlement)) candidates.push(fromSettlement);
            if (fromLog != null) candidates.push(fromLog);
            if (!candidates.length) return null;
            // Never show inflated HP when settlement snapshot lags behind enemy.hp
            return Math.min(...candidates);
        }

        function syncEnemyHpDisplay(data, enemyOverride = null) {
            const ctx = enemyOverride
                ? { ...data, enemy: { ...(data?.enemy || {}), ...enemyOverride } }
                : data;
            let hp = resolveAuthoritativeEnemyHp(ctx);
            if (!Number.isFinite(hp)) return;
            // Same combat only: stale poll must not inflate HP (never bleed across combats)
            const combatId = ctx?.combat_id || currentCombatId;
            const sameCombat = !combatId || combatId === currentCombatId;
            if (sameCombat && Number.isFinite(lastAnimatedEnemyHp) && hp > lastAnimatedEnemyHp) {
                hp = lastAnimatedEnemyHp;
            }
            const maxHp = Number(ctx?.enemy?.max_hp || ctx?.enemy?.hp) || 1;
            const prevHp = Number.isFinite(lastAnimatedEnemyHp)
                ? lastAnimatedEnemyHp
                : resolveAuthoritativeEnemyHp(lastCombatStatus);
            resetCombatEnemyHpTracking(hp);
            const fmt = (n) => Number(n).toLocaleString('zh-Hant');
            safeSetText('enemy-hp-current', fmt(hp));
            safeSetText('enemy-stat-hp', fmt(hp));
            safeSetText('enemy-hp-max', fmt(maxHp));
            lastAnimatedEnemyHp = hp;
            const bar = document.getElementById('enemy-hp-bar');
            if (bar) {
                bar.style.width = `${Math.max(0, Math.min(100, Math.round(hp / maxHp * 100)))}%`;
                if (Number.isFinite(prevHp) && hp < prevHp) {
                    flashEnemyHpBar();
                }
            }
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

        function buildClientRoundSettlement(logEntries) {
            const entries = logEntries || [];
            let summaryIdx = -1;
            for (let i = entries.length - 1; i >= 0; i--) {
                const e = entries[i];
                if (e?.type === 'summary' && (e.message || '').includes('受到共')) {
                    summaryIdx = i;
                    break;
                }
            }
            let teamDealt = 0;
            let enemyDealt = 0;
            const playerHits = [];
            const counterHits = [];
            if (summaryIdx >= 0) {
                const m = (entries[summaryIdx].message || '').match(/受到共\s*(\d+)\s*點傷害/);
                if (m) teamDealt = parseInt(m[1], 10);
                for (let i = summaryIdx - 1; i >= 0; i--) {
                    const e = entries[i];
                    if (e?.type !== 'damage') break;
                    const dm = (e.message || '').match(/造成\s*(\d+)\s*點傷害/);
                    const pm = (e.message || '').match(/^(.+?)\s+(?:攻擊|Zoo 能力)/);
                    if (dm) playerHits.unshift({ player: pm ? pm[1].trim() : '隊友', damage: parseInt(dm[1], 10) });
                }
                for (let i = summaryIdx + 1; i < entries.length; i++) {
                    const e = entries[i];
                    if (e?.type !== 'enemy_attack') break;
                    const dm = (e.message || '').match(/造成\s*(\d+)\s*點傷害/);
                    const tm = (e.message || '').match(/反擊\s*([^，]+)/);
                    if (dm) {
                        const dmg = parseInt(dm[1], 10);
                        enemyDealt += dmg;
                        counterHits.push({ target: tm ? tm[1].trim() : '?', damage: dmg });
                    }
                }
            }
            let enemyHpAfter = null;
            if (summaryIdx >= 0) {
                const hm = (entries[summaryIdx].message || '').match(/剩餘\s*HP\s*(\d+)/);
                if (hm) enemyHpAfter = parseInt(hm[1], 10);
            }
            return {
                team_damage_dealt: teamDealt,
                enemy_damage_dealt: enemyDealt,
                player_hits: playerHits,
                counter_hits: counterHits,
                enemy_hp_after: enemyHpAfter,
            };
        }

        function getRoundSettlement(data) {
            const preview = data?.full_preview || {};
            return data?.round_settlement
                || preview.round_settlement
                || {
                    team_damage_dealt: parseInt(data?.round_enemy_damage, 10) || 0,
                    enemy_damage_dealt: parseInt(data?.round_player_damage, 10) || 0,
                    counter_hits: [],
                    player_hits: [],
                };
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
            lastShownSettlementPhase = 0;
            settlementCombatId = null;
            clearTimeout(showFullRoundSettlement._modalTimer);
            showFullRoundSettlement._modalTimer = null;
        }

        function lockCombatActionsForSettlement() {
            document.querySelectorAll('.combat-action-btn, .combat-item-btn').forEach(el => {
                el.disabled = true;
            });
            const panel = document.getElementById('player-panel');
            if (panel) panel.style.opacity = '0.45';
            const hintEl = document.getElementById('combat-submit-hint');
            if (hintEl) hintEl.textContent = '本回合傷害結算中，請稍候…';
        }

        function showRoundSettlementModal(data) {
            const modal = document.getElementById('combat-round-settlement-modal');
            const logsEl = document.getElementById('round-settlement-logs');
            const preview = data.full_preview || {};
            const settlement = getRoundSettlement(data);
            const teamDealt = Number(settlement.team_damage_dealt) || 0;
            const enemyDealt = Number(settlement.enemy_damage_dealt) || 0;
            const phase = Number(data.current_phase) || 0;

            safeSetText('round-settlement-phase', phase > 1 ? `第 ${phase - 1} 回合` : '第 1 回合');
            safeSetText('round-settlement-team-dealt', teamDealt.toLocaleString('zh-Hant'));
            safeSetText('round-settlement-enemy-dealt', enemyDealt.toLocaleString('zh-Hant'));

            const enemy = data.enemy || preview.enemy || lastCombatStatus?.enemy || {};
            const enemyHp = Number(enemy.hp);
            const enemyMax = Number(enemy.max_hp || enemy.hp);
            const fmtHp = (n) => (Number.isFinite(n) ? Number(n).toLocaleString('zh-Hant') : '—');
            safeSetText('round-settlement-enemy-hp', fmtHp(enemyHp));
            safeSetText('round-settlement-enemy-hp-max', Number.isFinite(enemyMax) ? ` / ${fmtHp(enemyMax)}` : '');
            const hpNote = document.getElementById('round-settlement-hp-note');
            if (hpNote) {
                if (teamDealt <= 0) {
                    hpNote.textContent = '本回合對敵方造成 0 點傷害（失手或暴走）';
                } else if (Number.isFinite(enemyMax) && enemyMax >= 500) {
                    hpNote.textContent = '高 HP 敵人血條幾乎唔郁，請以數字同本回合傷害為準';
                } else {
                    hpNote.textContent = '';
                }
            }

            const counterNote = document.getElementById('round-settlement-counter-note');
            if (counterNote) {
                const hits = settlement.counter_hits || [];
                if (hits.length === 1) {
                    counterNote.textContent = `${hits[0].target} 受到反擊`;
                } else if (hits.length > 1) {
                    counterNote.textContent = hits.map(h => h.target).join('、');
                } else if (enemyDealt > 0) {
                    counterNote.textContent = '全隊受到反擊';
                } else {
                    counterNote.textContent = '本回合無反擊';
                }
            }

            const breakdownEl = document.getElementById('round-settlement-breakdown');
            if (breakdownEl) {
                const lines = [];
                (settlement.player_hits || []).forEach(h => {
                    lines.push(`<div class="py-0.5 text-emerald-300">• ${h.player} 造成 ${h.damage} 點</div>`);
                });
                (settlement.counter_hits || []).forEach(h => {
                    lines.push(`<div class="py-0.5 text-red-300">• ${h.target} 受到反擊 ${h.damage} 點</div>`);
                });
                breakdownEl.innerHTML = lines.join('') || '<div class="text-zinc-500">本回合已結算</div>';
            }

            const entries = preview.log_entries || data.log_entries || [];
            const recent = entries.slice(-8);
            if (logsEl) {
                logsEl.innerHTML = recent.length
                    ? recent.map(e => `<div class="py-0.5">• ${e.message || e}</div>`).join('')
                    : (preview.log || data.log || []).slice(-8).map(line => `<div class="py-0.5">• ${line}</div>`).join('')
                      || '<div class="text-zinc-500">尚無詳細紀錄</div>';
            }
            hideCombatModal();
            setVisible(modal, true);
            modal.classList.add('flex');
            const continueBtn = modal?.querySelector('.px-5.py-4 button');
            if (continueBtn) {
                continueBtn.textContent = pendingVictoryAfterSettlement
                    ? '確認戰果，查看勝利'
                    : '繼續下一回合';
            }
        }

        function hideRoundSettlementModal() {
            const modal = document.getElementById('combat-round-settlement-modal');
            if (!modal) return;
            modal.classList.remove('flex');
            setVisible(modal, false);
        }

        function continueCombatAfterRound() {
            combatAwaitingSettlementAck = false;
            settlementTimerPending = false;
            clearTimeout(showFullRoundSettlement._modalTimer);
            showFullRoundSettlement._modalTimer = null;
            hideRoundSettlementModal();
            hideSinglePlayerResultModal();
            combatWaitingForRound = false;
            resetCombatDiceUi();
            selectedDice = null;
            if (pendingVictoryAfterSettlement) {
                const victoryPayload = pendingVictoryAfterSettlement;
                pendingVictoryAfterSettlement = null;
                void finalizeCombatVictoryFromPayload(victoryPayload);
                return;
            }
            const phase = lastCombatStatus?.current_phase || 0;
            if (phase) lastDicePhase = phase;
            loadCombatStatus(false);
        }

        function showFullRoundSettlement(data) {
            data = applySettlementEnemyHp(data);
            if (data.enemy?.hp != null) {
                resetCombatEnemyHpTracking(data.enemy.hp);
            }
            const phase = Number(data?.current_phase) || 0;
            combatAwaitingSettlementAck = true;
            settlementTimerPending = true;
            if (phase > lastShownSettlementPhase) {
                lastShownSettlementPhase = phase;
            }
            combatWaitingForRound = false;
            hideCombatWaitingPanel();
            hideSinglePlayerResultModal();
            hideCombatModal();
            processCombatDamageAnimations(data, 120);
            updateCombatUI(data, { damageDelay: 200, skipActionEnable: true });
            syncEnemyHpDisplay(data);
            lockCombatActionsForSettlement();
            const settlement = getRoundSettlement(data);
            const teamDealt = Number(settlement.team_damage_dealt) || 0;
            const enemyDealt = Number(settlement.enemy_damage_dealt) || 0;
            const hasDamageLogs = (data.log_entries || []).some(e => e.type === 'damage');
            if (teamDealt > 0) {
                showDamageNumber('enemy-panel', teamDealt, false);
            }
            if (enemyDealt > 0) {
                showDamageNumber('player-panel', enemyDealt, false);
            }
            const roundDmgEl = document.getElementById('enemy-round-damage');
            if (roundDmgEl) {
                if (teamDealt > 0) {
                    roundDmgEl.textContent = `本回合對敵 -${teamDealt.toLocaleString('zh-Hant')}`;
                    setVisible(roundDmgEl, true);
                } else {
                    roundDmgEl.textContent = '';
                    setVisible(roundDmgEl, false);
                }
            }
            const modalDelay = (teamDealt > 0 || enemyDealt > 0 || hasDamageLogs)
                ? getSettlementModalDelayMs()
                : Math.min(500, Math.round(getSettlementModalDelayMs() * 0.3));
            clearTimeout(showFullRoundSettlement._modalTimer);
            showFullRoundSettlement._modalTimer = setTimeout(() => {
                settlementTimerPending = false;
                showRoundSettlementModal(data);
            }, modalDelay);
            startCombatPolling(COMBAT_POLL_INTERVAL_NORMAL);
        }

        function victoryPayloadHasSettlement(data) {
            const roundResolved = data?.round_resolved || data?.status === 'round_resolved';
            if (data?.outcome && data?.round_settlement) return true;
            if (!roundResolved) return false;
            const settlement = getRoundSettlement(data);
            if (Number(settlement.team_damage_dealt) > 0) return true;
            return (data.log_entries || []).some(e => e?.type === 'damage');
        }

        async function finishCombatVictoryFromPayload(data) {
            const roundResolved = data?.round_resolved || data?.status === 'round_resolved';
            if (victoryPayloadHasSettlement(data) && (roundResolved || data?.outcome)) {
                pendingVictoryAfterSettlement = data;
                const enriched = applySettlementEnemyHp({
                    ...data,
                    enemy: { ...(data.enemy || lastCombatStatus?.enemy || {}), hp: 0 },
                    round_resolved: true,
                    active: true,
                });
                syncEnemyHpDisplay(enriched);
                showFullRoundSettlement(enriched);
                return;
            }
            await finalizeCombatVictoryFromPayload(data);
        }

        async function finalizeCombatVictoryFromPayload(data) {
            resetCombatSettlementState();
            pendingVictoryAfterSettlement = null;
            combatWaitingForRound = false;
            hideCombatWaitingPanel();
            hideRoundSettlementModal();
            hideSinglePlayerResultModal();
            hideCombatModal();
            if (data?.log_entries?.length) {
                processCombatDamageAnimations(data, 120);
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
                    const res = await fetch(url, { credentials: 'same-origin' });
                    const fresh = await res.json();
                    if (fresh.outcome) payload = { ...payload, ...fresh };
                } catch (_) { /* use local payload */ }
            }
            const outcome = payload.outcome
                || (payload.winner === 'enemy' ? 'defeat' : 'victory');
            showCombatResult({
                ...payload,
                outcome,
                active: false,
            });
            const statusRes = await fetch('/status', { credentials: 'same-origin' });
            updateDashboard(await statusRes.json());
            combatItemsLoaded = false;
        }

        function shouldFinishCombatVictory(data) {
            if (!data) return false;
            if (data.outcome) return true;
            if (data.status === 'ended' || data.winner) return true;
            const hp = Number(data.enemy?.hp);
            return Number.isFinite(hp) && hp <= 0;
        }

        function handleCombatRoundResolved(data) {
            if (!data) return;
            if (shouldFinishCombatVictory(data)) {
                finishCombatVictoryFromPayload(data);
                return;
            }
            setCombatPhaseLock(false);
            hideCombatModal();
            if (data.enemy?.hp != null) {
                resetCombatEnemyHpTracking(data.enemy.hp);
            }
            const phase = Number(data.current_phase) || 0;
            const settled = applySettlementEnemyHp(data);
            const settlement = getRoundSettlement(settled);
            const hasDamage = Number(settlement.team_damage_dealt) > 0
                || (settled.log_entries || []).some(e => e?.type === 'damage');
            const mustShow = (settled.round_resolved || settled.status === 'round_resolved') && hasDamage;
            if (!shouldShowRoundSettlement(settled) && !mustShow) {
                if (combatAwaitingSettlementAck || settlementTimerPending) {
                    return;
                }
                combatWaitingForRound = false;
                hideCombatWaitingPanel();
                updateCombatUI(settled, { damageDelay: 0 });
                syncEnemyHpDisplay(settled);
                startCombatPolling(COMBAT_POLL_INTERVAL_NORMAL);
                return;
            }
            showFullRoundSettlement(settled);
        }
```

### `templates/index.html` L3323–L3680

```javascript
        function updateCombatUI(data, options = {}) {
            if (!data) return;
            const uiData = normalizeCombatStatusData(applySettlementEnemyHp(data));
            if (!uiData.my_state && (uiData.active || uiData.status === 'player_phase' || uiData.status === 'enemy_phase')) {
                console.warn('Combat data missing my_state');
            }
            lastCombatStatus = uiData;
            setVisible(document.getElementById('combat-result-panel'), false);

            if (uiData.in_precheck) {
                setVisible(document.getElementById('combat-precheck-modal'), true);
                return;
            }

            const isResolving = uiData.status === 'resolving';
            if (isResolving) {
                setCombatPhaseLock(true, uiData);
            } else if (combatPhaseLocked) {
                const phase = uiData.current_phase || 0;
                if (uiData.status === 'player_phase' && phase > combatPhaseLockedRound) {
                    setCombatPhaseLock(false);
                }
            }

            const combatLive = uiData.active === true
                || ['player_phase', 'enemy_phase', 'resolving'].includes(uiData.status);
            if (!combatLive) {
                if (uiData.outcome) {
                    if (shouldFinishCombatVictory(uiData)) {
                        void finishCombatVictoryFromPayload(uiData);
                    } else {
                        showCombatResult(uiData);
                    }
                }
                return;
            }

            currentCombatId = uiData.combat_id || currentCombatId;
            if (uiData.combat_id && uiData.combat_id !== settlementCombatId) {
                settlementCombatId = uiData.combat_id;
                lastShownSettlementPhase = 0;
                combatAwaitingSettlementAck = false;
                settlementTimerPending = false;
                clearTimeout(showFullRoundSettlement._modalTimer);
                showFullRoundSettlement._modalTimer = null;
                resetCombatEnemyHpTracking(null);
            }
            showCombatScreen();
            applyCombatAccent(uiData.route);

            safeSetText('combat-title', uiData.title || '戰鬥中');
            const routeLabel = ROUTE_SUBTITLES[uiData.route] || 'Encounter';
            const phaseNum = uiData.current_phase || 1;
            safeSetText('combat-subtitle', `${routeLabel} · 第 ${phaseNum} 回合`);
            safeSetText('max-phase', uiData.max_phases || 5);

            const phaseLabels = {
                player_phase: { text: 'Player Phase', color: 'text-emerald-400' },
                enemy_phase: { text: 'Enemy Phase', color: 'text-red-400' },
                resolving: { text: '結算中', color: 'text-sky-400' },
            };
            const pl = phaseLabels[uiData.status] || { text: uiData.status, color: 'text-zinc-400' };
            safeSetText('phase-status-label', pl.text);
            safeSetClass('phase-status-label', `text-xs ${pl.color}`);

            const squad = currentSquad || {};
            const me = buildCombatMyState(uiData);
            const enemy = uiData.enemy || {};

            updateEnemyCombatStats(enemy, uiData.enemy_description || '');
            updateCombatPlayerAvatar(me);
            safeSetText('combat-player-name', me.display_name || '你');
            safeSetText('combat-player-team', squad.team?.team_name || squad.team_name || '單人');
            updateCombatPlayerStats(me, squad);
            updateAttackButtonHint();

            const protagonists = uiData.protagonists || squad.protagonists || {};
            const teamData = {
                ...uiData,
                my_squad_id: uiData.my_squad_id || squad.squad_id,
                route: uiData.route || protagonists.active_route || squad.route,
                protagonists,
                member_states: uiData.member_states || {},
            };
            renderCombatTeamRow(teamData);
            updateProtagonistControlUi();

            const sanity = me.sanity ?? 100;
            const berserkBar = document.getElementById('combat-berserk-bar');
            const berserkChance = uiData.berserk_chance || 0;
            if (sanity < 40) {
                setVisible(berserkBar, true);
                let berserkMsg;
                if (sanity < 10) {
                    berserkMsg = `神智崩潰邊緣！暴走機率 ${berserkChance}% — 極高風險`;
                } else if (sanity < 20) {
                    berserkMsg = `神智危險！暴走機率 ${berserkChance}% — 提交前請確認`;
                } else {
                    berserkMsg = `神智偏低（${sanity}），暴走風險 ${berserkChance}%`;
                }
                safeSetText('combat-berserk-bar-text', berserkMsg);
                if (berserkBar) berserkBar.classList.toggle('berserk-critical', sanity < 10);
            } else {
                setVisible(berserkBar, false);
                if (berserkBar) berserkBar.classList.remove('berserk-critical');
            }

            setVisible(document.getElementById('combat-berserk-overlay'),
                sanity < 10 && uiData.status === 'player_phase' && !me.submitted);

            const zooHint = document.getElementById('zoo-hint');
            if (zooHint) {
                if (sanity >= 100) zooHint.textContent = 'Zoo 加成 ×1.8';
                else if (sanity >= 90) zooHint.textContent = 'Zoo 加成 ×1.5';
                else if (sanity >= 80) zooHint.textContent = 'Zoo 加成 ×1.4';
                else if (sanity >= 70) zooHint.textContent = 'Zoo 加成 ×1.3 ✓';
                else zooHint.textContent = `神智 ${sanity}，需 ≥70`;
                zooHint.className = sanity >= 70 ? 'text-[10px] text-orange-300 font-medium' : 'text-[10px] text-zinc-500';
            }

            if (uiData.phase_deadline && uiData.status === 'player_phase') {
                startPhaseCountdown(uiData.phase_deadline);
            } else if (uiData.phase_expired) {
                safeSetText('phase-timer', '0:00');
            }

            const logEl = document.getElementById('combat-log');
            if (logEl) {
                logEl.innerHTML = (uiData.log || []).map(line => `<div class="py-0.5">• ${line}</div>`).join('')
                    || '<div class="text-zinc-500">尚無戰鬥記錄</div>';
                logEl.scrollTop = logEl.scrollHeight;
            }
            processCombatDamageAnimations(
                uiData,
                options.damageDelay ?? 0,
                !!options.initLogsOnly,
            );

            const inNearDeath = me.near_death_until && new Date(me.near_death_until) > new Date();
            updateNearDeathOverlay(me);

            const hintEl = document.getElementById('combat-submit-hint');
            const actionContainer = document.getElementById('player-panel');
            const canAct = uiData.status === 'player_phase'
                && !combatPhaseLocked
                && !isResolving
                && !inNearDeath
                && !me.submitted
                && !combatAwaitingSettlementAck
                && !settlementTimerPending
                && !options.skipActionEnable;
            if (actionContainer) actionContainer.style.opacity = canAct ? '1' : '0.45';
            document.querySelectorAll('.combat-action-btn, .combat-item-btn').forEach(el => {
                el.disabled = !canAct || actionModalRolling || combatPhaseLocked || isResolving;
            });
            if (canAct && phaseNum !== lastDicePhase) {
                lastDicePhase = phaseNum;
                if (!isCombatModalBusy()) {
                    resetCombatDiceUi();
                }
            } else if ((me.submitted || !canAct) && !isCombatModalBusy()) {
                hideCombatModal();
            }
            if (hintEl) {
                if (combatAwaitingSettlementAck || settlementTimerPending) {
                    hintEl.textContent = '本回合傷害結算中，請稍候…';
                } else if (inNearDeath) hintEl.textContent = '你已瀕死，等待隊友救援';
                else if (me.submitted) hintEl.textContent = `已提交：${COMBAT_ACTION_LABELS[me.action_type] || me.action_type}（骰 ${me.dice_result ?? '?' }），等待隊友…`;
                else if (isResolving || combatPhaseLocked) hintEl.textContent = '回合結算中，請稍候…';
                else if (uiData.status !== 'player_phase') hintEl.textContent = '敵人回合結算中…';
                else if (actionModalRolling) hintEl.textContent = '系統擲骰中，請稍候…';
                else if (isCombatModalOpen()) hintEl.textContent = '請於彈窗內確認並結束本回合';
                else if (selectedAction === 'use_item' && !selectedItemId) hintEl.textContent = '請選擇要使用的物品';
                else hintEl.textContent = '選擇行動後將彈出戰況預覽';
            }
        }

        async function loadCombatStatus(showLoading) {
            try {
                await refreshSquadFromServer();
                const url = currentCombatId
                    ? `/combat/status?combat_id=${currentCombatId}`
                    : '/combat/status';
                const res = await fetch(url, { credentials: 'same-origin' });
                const data = await res.json();
                if (data.success === false && !data.my_state && !data.active) return;
                if (data.outcome) {
                    combatWaitingForRound = false;
                    hideCombatWaitingPanel();
                    hideSinglePlayerResultModal();
                    resetCombatSettlementState();
                    hideRoundSettlementModal();

                    if (shouldFinishCombatVictory(data)) {
                        await finishCombatVictoryFromPayload(data);
                    } else {
                        showCombatResult(data);
                    }

                    const statusRes = await fetch('/status', { credentials: 'same-origin' });
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

                if (combatAwaitingSettlementAck || settlementTimerPending) {
                    if (shouldFinishCombatVictory(data)) {
                        await finishCombatVictoryFromPayload(data);
                    }
                    return;
                }

                if (shouldFinishCombatVictory(data)) {
                    await finishCombatVictoryFromPayload(data);
                    return;
                }

                if (data.status === 'resolving') {
                    setCombatPhaseLock(true, data);
                    startCombatPolling(COMBAT_POLL_INTERVAL_RESOLVING);
                } else if (data.waiting_for_teammates || data.status === 'waiting_for_teammates') {
                    combatWaitingForRound = true;
                    showCombatResolvingPanel(false);
                    showCombatWaitingPanel(data.submitted_count || 0, data.total_active || 0);
                    startCombatPolling(COMBAT_POLL_INTERVAL_WAITING);
                }

                if (data.active) {
                    setVisible(document.getElementById('combat-lobby'), false);
                }
                const uiOptions = showLoading ? { initLogsOnly: true } : {};
                const applyCombatUi = () => updateCombatUI(data, uiOptions);
                if (data.active || data.in_precheck) {
                    setTimeout(applyCombatUi, 50);
                } else {
                    applyCombatUi();
                }
                if (data.active || data.in_precheck) {
                    startCombatPolling(getCombatPollInterval(data));
                } else {
                    stopCombatPolling();
                }
            } catch (e) {
                if (showLoading) console.error('載入戰鬥狀態失敗', e);
            }
        }

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

            resetCombatDiceUi();
            lastDicePhase = 0;

            if (data.status === 'waiting_for_teammates') {
                combatWaitingForRound = true;
                combatSubmittedPhase = data.current_phase || lastCombatStatus?.current_phase || 0;
                showSinglePlayerResultModal(data.single_preview);
                showCombatWaitingPanel(data.submitted_count || 0, data.total_active || 0);
                showToast('已提交行動，等待隊友後先會顯示全隊傷害結算', 'info');
                updateCombatUI({ ...data, active: true }, { initLogsOnly: true });
                startCombatPolling(COMBAT_POLL_INTERVAL_WAITING);
                return;
            }

            if (data.status === 'round_resolved' || data.round_resolved) {
                if (data.enemy?.hp != null) {
                    resetCombatEnemyHpTracking(data.enemy.hp);
                }
                handleCombatRoundResolved({ ...data, active: true });
                return;
            }

            updateCombatUI({ ...data, active: true }, { damageDelay: 350 });
        }

        async function rescueNearDeath() {
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
```

### `templates/index.html` L4562–L4585

```javascript
            safeSetText('combat-m-resilience', stats.resilience);
        }

        function resetCombatEnemyHpTracking(enemyHp = null) {
            combatEnemyHpSeen = enemyHp;
            lastAnimatedEnemyHp = enemyHp != null ? enemyHp : null;
        }

        function updateEnemyCombatStats(enemy, description) {
            safeSetText('enemy-name', enemy.name || '敵人');
            const quoteEl = document.getElementById('enemy-quote');
            if (quoteEl) quoteEl.textContent = description || '';
            syncEnemyHpDisplay(lastCombatStatus, enemy);
            const maxHp = Number(enemy.max_hp || enemy.hp) || 1;
            const hpHintEl = document.getElementById('enemy-hp-hint');
            if (hpHintEl) {
                if (maxHp >= 500) {
                    hpHintEl.textContent = '高 HP 敵人：血條變化唔明顯，請睇 HP 數字同結算畫面';
                    setVisible(hpHintEl, true);
                } else {
                    hpHintEl.textContent = '';
                    setVisible(hpHintEl, false);
                }
            }
```

## E. 後端 Python


### `routes/combat.py` L161–L278

```python
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
```

### `routes/combat.py` L331–L475

```python
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
```

### `models/combat.py` L931–L1010

```python
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
    if combat:
        combat = reconcile_enemy_hp(combat, persist=True)
```

## F. CI 已通過（API 層）

- `test_solo_multi_round_poll_hp_monotonic` — 單人 practice_iggy_03_boundary 每回合 enemy.hp 遞減
- `test_practice_combat_start_enemy_hp_full` — 開局 48/140 HP
- `test_zombie_hp_zero_status_poll_returns_victory`
- `test_solo_killing_blow_practice_quick`

## G. 實機仍 fail 條件（Henry）

- Iggy 線、**單人**、`practice_iggy_03_boundary`（140 HP）
- PA `fd3a036`、`enemy_hp_sync_v3: true`
- 戰鬥中敵 HP **顯示**唔更新

---

*由 scripts/build_gemini_packet.sh 自動生成 · 勿手改（改源碼後重新 run script）*
