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