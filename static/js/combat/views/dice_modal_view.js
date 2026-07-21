import { DOM_IDS, TEST_IDS } from '../selectors.js';

const DICE_FRAMES = 8;
const DICE_MS = 55;

export function createDiceModalView(rootEl) {
  const modal = rootEl.querySelector(`#${DOM_IDS.DICE_MODAL}`);
  const valueEl = rootEl.querySelector(`#${DOM_IDS.DICE_VALUE}`);
  const confirmBtn = rootEl.querySelector(`#${DOM_IDS.DICE_CONFIRM}`);
  let onConfirm = null;
  let rolling = false;

  confirmBtn?.addEventListener('click', () => {
    if (onConfirm) onConfirm();
  });

  return {
    isVisible() {
      return modal && !modal.classList.contains('hidden');
    },
    showRolling() {
      if (!modal) return;
      modal.classList.remove('hidden');
      modal.classList.add('flex');
      if (valueEl) valueEl.textContent = '…';
      if (confirmBtn) confirmBtn.classList.add('hidden');
    },
    async animateCosmeticDice(finalValue) {
      if (!valueEl) return;
      rolling = true;
      for (let i = 0; i < DICE_FRAMES; i++) {
        valueEl.textContent = String(Math.floor(Math.random() * 4));
        await sleep(DICE_MS);
      }
      if (finalValue == null) {
        valueEl.textContent = '—';
      } else {
        valueEl.textContent = String(finalValue);
      }
      rolling = false;
    },
    showConfirm(value, options = {}) {
      const {
        isDefend = false,
        isEscape = false,
        isItem = false,
        isZoo = false,
        itemName = '',
        pendingServerRoll = false,
      } = options;
      if (!modal) return;
      modal.classList.remove('hidden');
      modal.classList.add('flex');
      if (valueEl) {
        if (isItem) valueEl.textContent = itemName ? `🎒 ${itemName}` : '🎒 道具';
        else if (isEscape) valueEl.textContent = '🏃 逃跑';
        else if (isDefend) valueEl.textContent = '🛡 防禦';
        // Server-authoritative dice: never show a cosmetic final face as "result".
        else if (pendingServerRoll || value == null || value === '') {
          valueEl.textContent = isZoo ? '🦄 ？' : '？';
        } else if (isZoo) {
          valueEl.textContent = `🦄 ${value}`;
        } else {
          valueEl.textContent = String(value);
        }
      }
      if (confirmBtn) {
        confirmBtn.classList.remove('hidden');
        if (isItem) {
          confirmBtn.textContent = '確認使用並結束回合';
        } else if (pendingServerRoll || value == null || value === '') {
          confirmBtn.textContent = isZoo ? '確認並由系統擲 Zoo 骰' : '確認並由系統擲骰';
        } else {
          confirmBtn.textContent = '確認並結束本回合';
        }
      }
    },
    setConfirmDisabled(disabled) {
      if (confirmBtn) confirmBtn.disabled = !!disabled;
    },
    hide() {
      if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
      }
      if (confirmBtn) confirmBtn.disabled = false;
      rolling = false;
    },
    onConfirm(handler) {
      onConfirm = handler;
    },
    isRolling() {
      return rolling;
    },
  };
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

export { DICE_FRAMES, DICE_MS };