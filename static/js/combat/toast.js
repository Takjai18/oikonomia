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