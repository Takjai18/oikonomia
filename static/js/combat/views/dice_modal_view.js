import { DOM_IDS, TEST_IDS } from '../selectors.js';

const DICE_FRAMES = 8;
const DICE_MS = 55;
const LAND_HOLD_MS = 420;

export function createDiceModalView(rootEl) {
  const modal = rootEl.querySelector(`#${DOM_IDS.DICE_MODAL}`);
  const valueEl = rootEl.querySelector(`#${DOM_IDS.DICE_VALUE}`);
  const confirmBtn = rootEl.querySelector(`#${DOM_IDS.DICE_CONFIRM}`);
  let onConfirm = null;
  let rolling = false;

  confirmBtn?.addEventListener('click', () => {
    if (onConfirm) onConfirm();
  });

  function showModal() {
    if (!modal) return;
    modal.classList.remove('hidden');
    modal.classList.add('flex');
  }

  return {
    isVisible() {
      return modal && !modal.classList.contains('hidden');
    },
    showRolling() {
      showModal();
      if (valueEl) valueEl.textContent = '…';
      if (confirmBtn) confirmBtn.classList.add('hidden');
    },
    /**
     * Spin frames for atmosphere only; finalValue null → keep "…"
     * (legacy defend/escape path).
     */
    async animateCosmeticDice(finalValue) {
      if (!valueEl) return;
      rolling = true;
      showModal();
      if (confirmBtn) confirmBtn.classList.add('hidden');
      for (let i = 0; i < DICE_FRAMES; i++) {
        valueEl.textContent = String(Math.floor(Math.random() * 4));
        await sleep(DICE_MS);
      }
      if (finalValue == null) {
        valueEl.textContent = '…';
      } else {
        valueEl.textContent = String(finalValue);
      }
      rolling = false;
    },
    /**
     * Plan A: spin while waiting for server, then land on authoritative face.
     * @param {Promise<{dice_result?: number|string}>|Promise<any>} submitPromise
     * @param {{ isZoo?: boolean, minFrames?: number, holdMs?: number }} [opts]
     */
    async spinThenLandOnServer(submitPromise, opts = {}) {
      const {
        isZoo = false,
        minFrames = DICE_FRAMES,
        holdMs = LAND_HOLD_MS,
      } = opts;
      showModal();
      if (confirmBtn) confirmBtn.classList.add('hidden');
      rolling = true;
      let frame = 0;
      let data;
      let settled = false;
      const pending = Promise.resolve(submitPromise).then((res) => {
        data = res;
        settled = true;
        return res;
      });

      // Keep spinning until both min frames and server response are ready.
      while (!settled || frame < minFrames) {
        if (valueEl) {
          const face = Math.floor(Math.random() * 4);
          valueEl.textContent = isZoo ? `🦄 ${face}` : String(face);
        }
        frame += 1;
        await sleep(DICE_MS);
        if (frame > 80) break; // safety cap ~4.4s
      }
      await pending;

      const raw = data?.dice_result;
      const serverDice = raw == null || raw === '' ? null : Number(raw);
      const face = Number.isFinite(serverDice) ? serverDice : raw;
      if (valueEl) {
        if (face == null || face === '') {
          valueEl.textContent = isZoo ? '🦄 —' : '—';
        } else {
          valueEl.textContent = isZoo ? `🦄 ${face}` : String(face);
        }
      }
      rolling = false;
      if (holdMs > 0) await sleep(holdMs);
      return data;
    },
    showConfirm(value, options = {}) {
      const {
        isDefend = false,
        isEscape = false,
        isItem = false,
        isZoo = false,
        itemName = '',
      } = options;
      showModal();
      if (valueEl) {
        if (isItem) valueEl.textContent = itemName ? `🎒 ${itemName}` : '🎒 道具';
        else if (isEscape) valueEl.textContent = '🏃 逃跑';
        else if (isDefend) valueEl.textContent = '🛡 防禦';
        else if (isZoo) valueEl.textContent = `🦄 ${value ?? '—'}`;
        else valueEl.textContent = String(value ?? '—');
      }
      if (confirmBtn) {
        confirmBtn.classList.remove('hidden');
        confirmBtn.textContent = isItem ? '確認使用並結束回合' : '確認並結束本回合';
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

export { DICE_FRAMES, DICE_MS, LAND_HOLD_MS };
