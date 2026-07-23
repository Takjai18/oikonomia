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
  let panel = rootEl.querySelector(`#${DOM_IDS.VICTORY_PANEL}`);
  let failedPanel = rootEl.querySelector(`#${DOM_IDS.FAILED_PANEL}`);

  /** Host endgame layers on document.body so fixed fullscreen is never clipped. */
  function ensureBodyHost(el) {
    if (!el || !el.ownerDocument) return el;
    const body = el.ownerDocument.body;
    if (body && el.parentElement !== body) {
      body.appendChild(el);
    }
    return el;
  }

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
      panel = ensureBodyHost(panel || rootEl.querySelector(`#${DOM_IDS.VICTORY_PANEL}`));
      if (!panel) return;
      const narrative = data?.narrative || '你們成功看穿了這場衝突背後的情緒勒索與邊界扭曲。';
      const nextStory = data?.next_story_unlock || null;
      if (nextStory) {
        try {
          sessionStorage.setItem('OIKONOMIA_PENDING_STORY', nextStory);
        } catch (_) { /* noop */ }
      }

      panel.className = 'fixed inset-0 z-[120] flex items-center justify-center bg-zinc-950/90 p-4 backdrop-blur-sm';
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
      panel = ensureBodyHost(panel || rootEl.querySelector(`#${DOM_IDS.VICTORY_PANEL}`));
      if (!panel) return;
      const narrative = data?.narrative || '心理界線宣告失守，全隊陷入混亂。';

      panel.className = 'fixed inset-0 z-[120] flex items-center justify-center bg-zinc-950/90 p-4 backdrop-blur-sm';
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

      failedPanel = ensureBodyHost(
        failedPanel || rootEl.querySelector(`#${DOM_IDS.FAILED_PANEL}`),
      );
      if (!failedPanel) return;
      const list = (members || []).map((m) => `<li class="text-red-300 font-mono">${escapeHtml(m)}</li>`).join('');

      failedPanel.className = 'fixed inset-0 z-[125] flex items-center justify-center bg-black/95 p-4';
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