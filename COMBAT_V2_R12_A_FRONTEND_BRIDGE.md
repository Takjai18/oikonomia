# COMBAT_V2_R12_A_FRONTEND_BRIDGE（局部審計 · 大廳橋接與 Poll 隔離）

> **目的**：審計 **Legacy `index.html` 全局腳本** 與 **Combat V2 模組** 的交界 — 防止雙 poll、重連幽靈狀態、舊 overlay 疊加  
> **日期**：2026-07-01 · **commit**：`649526a`  
> **Baseline**：假設已讀 `COMBAT_V2_AUDIT_BUNDLE.md`  
> **生成**：`python3 scripts/build_combat_v2_partial_bundles.py`

---

## 0. 給 Gemini 的指令

**焦點問題**：
1. 全局 3s `/status` poll 是否會在 V2 戰鬥中沖刷 FSM 快照？（`isPlayerInActiveCombatV2`）
2. `exitCombatScreen` ↔ `exitToLobby` 是否會遞迴或漏清 overlay？
3. `finishSessionRestore` + `current_combat_id` 是否正確 fast-forward？
4. 舊 `#combat-near-death-overlay` 是否仍與 `failed_panel.js` 衝突？

**輸出**：【Critical】→【High/Medium】→【Low】→ 健康度 X/10

---

## 1. index.html 橋接核心

    // ── Combat lobby bridge (PR-6: legacy inline combat script removed) ──
    let pendingEncounterId = null;
    let currentCombatId = null;
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
            if (window.combatV2 && typeof window.combatV2.isEnabled === 'function' && !window.combatV2.isEnabled()) {
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
                    const combatId = data.current_combat_id;
                    console.log(`[Bridge] 偵測到重連進行中戰鬥 ${combatId}，強開權威引導渲染...`);
                    setActiveCombatBridge(combatId);
                    revealCombatV2Surface();
                    await waitForCombatRepaint();
                    await new Promise((r) => setTimeout(r, 60));

                    const ready = await waitForCombatV2Ready();
                    if (ready) {
                        revealCombatV2Surface();
                        await waitForCombatRepaint();
                        await window.combatV2.onCombatStarted({ combat_id: combatId });
                    } else {
                        console.warn('[Bridge] Combat V2 未能及時就緒，執行降級引導。');
                        if (typeof loadCombatPage === 'function') {
                            await loadCombatPage(combatId);
                        }
                    }
                } else {
                    clearActiveCombatBridge();
                }
                return true;
            } catch (e) {
                console.error('finishSessionRestore 遭遇競態崩潰:', e);
                showLoginScreenAfterFailedRestore(loadLocalSession());
                return false;
            }
        }

        async function fallbackToNormalSession() {

            storyTypewriterTimer = setInterval(() => {
                if (i < content.length) {
                    textEl.textContent += content.charAt(i);
                    i += 1;
                } else {
                    clearStoryTypewriter();
                    if (onDone) onDone();
                    scheduleStoryAutoAdvance();
                }
            }, getTypewriterSpeedMs());
        }

        function renderStoryChoices(line) {
            const choicesContainer = document.getElementById('story-choices');
            const continueBtn = document.getElementById('story-continue-btn');
            if (!choicesContainer) return;

            choicesContainer.innerHTML = '';
            const choices = line?.choices || [];
            if (!choices.length) {
                setVisible(choicesContainer, false);
                if (continueBtn) setVisible(continueBtn, true);
                return;
            }


## 2. bootstrap 掛載

/**
 * @file static/js/combat/bootstrap.js
 * @description COMBAT_V2 綠地架構啟動器 - 已完全移除 Legacy 熔斷保險絲
 */

import { CombatApp } from './index.js';

let app = null;
let enabled = false;

/**
 * 安全檢測後端 Feature Flag 狀態
 */
async function detectCombatV2() {
  if (window.__OIKONOMIA_COMBAT_V2__ === true) return true;
  if (window.__OIKONOMIA_COMBAT_V2__ === false) return false;
  try {
    const res = await fetch('/api/version', { credentials: 'same-origin' });
    const data = await res.json();
    return !!(data.combat_v2 || data.markers?.combat_v2);
  } catch (_) {
    return false;
  }
}

function getRoot() {
  return document.getElementById('combat-root-v2');
}

/**
 * 綠地初始化生命週期
 */
async function init() {
  enabled = await detectCombatV2();
  const root = getRoot();

  if (!enabled || !root) {
    window.combatV2 = { isEnabled: () => false };
    return;
  }

  app = CombatApp.mount(root);

  window.combatV2 = {
    isEnabled: () => true,

    async onCombatStarted(data) {
      console.log(`[Greenfield] 接收到戰鬥啟動訊號，戰鬥ID: ${data.combat_id}`);
      if (data.combat_id) {
        sessionStorage.setItem('OIKONOMIA_COMBAT_V2_LOCK', 'true');
        sessionStorage.setItem('OIKONOMIA_ACTIVE_COMBAT_ID', String(data.combat_id));
      }
      root.classList.remove('hidden');
      await app.onCombatStarted(data);
    },

    async performAction(type) {
      return app.performAction(type);
    },

    exitToLobby: () => app.exitToLobby(),
    summonGm: () => app.summonGm(),
    executeGmOverride: (opts) => app.executeGmOverride(opts),
    getState: () => app.getState(),
    pollTick: (data) => app.pollTick(data),
    onSubmitSuccess: (data) => app.onSubmitSuccess(data),
    getApp: () => app,
    destroy: () => {
      if (app) {
        app.destroy();
        app = null;
      }
    },
  };

  window.CombatV2App = window.combatV2;

  console.log(
    '%c[Greenfield] Oikonomia Combat V2 核心已成功獨立掛載，Legacy 代碼完全清理完成。',
    'color: #10b981; font-weight: bold;',
  );
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

## 3. exitToLobby 與 entry sync

# static/js/combat/index.js (L114–L126)

  async onCombatStarted(data) {
    this.dispatch('COMBAT_RESET', { combatId: data.combat_id });
    this.ctx.combatId = data.combat_id;
    this.ctx.settledRoundIndex = -1;
    this.ctx.shownSettlementIds.clear();
    this.ctx.entrySyncPending = true;
    this.hasTriggeredTimeoutDefense = false;
    this.invRecoveryCount = 0;

    if (data.combat_id) {
      sessionStorage.setItem('OIKONOMIA_COMBAT_V2_LOCK', 'true');
      sessionStorage.setItem('OIKONOMIA_ACTIVE_COMBAT_ID', String(data.combat_id));
    }
# static/js/combat/index.js (L573–L578)

  exitToLobby() {
    if (typeof window.exitCombatScreen === 'function') {
      showToast('已安全退出戰場', 'info');
      window.exitCombatScreen({ fromV2: true });
      return;
    }

---
*End of R12-A · 2026-07-01*
