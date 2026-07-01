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