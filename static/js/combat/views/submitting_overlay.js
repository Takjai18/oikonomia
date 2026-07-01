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