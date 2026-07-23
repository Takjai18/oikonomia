/**
 * @file static/js/combat/views/escape_result_view.js
 * @description 逃跑判定（成功離開戰場／失敗後進入結算）阻塞確認彈窗
 */

import { DOM_IDS } from '../selectors.js';

export function createEscapeResultView(rootEl) {
  let panel = rootEl.querySelector(`#${DOM_IDS.ESCAPE_RESULT}`);
  let onContinue = null;

  /** Host on document.body so fixed fullscreen is never clipped by combat shell. */
  function ensureBodyHost(el) {
    if (!el || !el.ownerDocument) return el;
    const body = el.ownerDocument.body;
    if (body && el.parentElement !== body) {
      body.appendChild(el);
    }
    return el;
  }

  return {
    show({ success, message }) {
      panel = ensureBodyHost(panel || rootEl.querySelector(`#${DOM_IDS.ESCAPE_RESULT}`));
      if (!panel) return;

      const ok = !!success;
      const continueLabel = ok ? '⛺ 離開戰場並返回' : '讀取本回合結算';

      panel.className = 'fixed inset-0 z-[120] flex items-center justify-center bg-zinc-950/90 p-4 backdrop-blur-sm';
      panel.innerHTML = `
        <div class="bg-zinc-900 border ${ok ? 'border-emerald-500/30' : 'border-red-500/30'} rounded-3xl p-6 max-w-xs w-full text-center shadow-2xl">
          <div class="text-5xl mb-3">${ok ? '🏃‍♂️' : '🫷'}</div>
          <h3 class="text-xl font-black ${ok ? 'text-emerald-400' : 'text-red-400'} mb-2 tracking-wider">
            ${ok ? '全隊成功脫離' : '全隊逃跑失敗'}
          </h3>
          <p class="text-sm text-zinc-300 leading-relaxed mb-6 bg-zinc-950/40 p-3 rounded-2xl border border-zinc-800">
            ${message || (ok ? '全隊已安全撤離戰場。' : '敵方看穿了你們的意圖，其餘戰鬥玩家的行動將繼續結算。')}
          </p>
          <button type="button" id="combat-v2-escape-continue"
                  class="min-h-11 px-4 rounded-2xl ${ok ? 'bg-emerald-600 hover:bg-emerald-500' : 'bg-amber-600 hover:bg-amber-500'} font-bold text-sm text-white w-full tracking-wider transition-colors shadow-md active:scale-[0.98]">
            ${continueLabel}
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
