/**
 * @file static/js/combat/views/action_view.js
 * @description 戰鬥主行動控制面板 — P2-2 Zoo / P2-3 主角代打
 */

import { Phase, TERMINAL_PHASES } from '../state_machine.js';
import { DOM_IDS } from '../selectors.js';

function zooBonusMultiplier(sanity) {
  if (sanity >= 100) return 1.8;
  if (sanity >= 90) return 1.5;
  if (sanity >= 80) return 1.4;
  if (sanity >= 70) return 1.3;
  return 1.0;
}

function berserkChancePct(sanity) {
  if (sanity < 10) return 90;
  if (sanity < 20) return 50;
  if (sanity < 40) return 20;
  return 0;
}

const BUSY_PHASES = [
  Phase.DICE_ROLLING,
  Phase.DICE_CONFIRM,
  Phase.SUBMITTING,
  Phase.SETTLEMENT,
  Phase.WAITING_FOR_PLAYERS,
  Phase.ESCAPE_ATTEMPT,
];

export function createActionView(rootEl, handlers = {}) {
  const attackBtn = rootEl.querySelector(`#${DOM_IDS.ATTACK_BTN}`);
  const defendBtn = rootEl.querySelector(`#${DOM_IDS.DEFEND_BTN}`);
  const escapeBtn = rootEl.querySelector(`#${DOM_IDS.ESCAPE_BTN}`);
  const zooBtn = rootEl.querySelector(`#${DOM_IDS.ZOO_BTN}`);
  const itemBtn = rootEl.querySelector(`#${DOM_IDS.ITEM_BTN}`);
  const zooTip = rootEl.querySelector(`#${DOM_IDS.ZOO_TIP}`);
  const protagonistBar = rootEl.querySelector(`#${DOM_IDS.PROTAGONIST_BAR}`);
  const protagonistLabel = rootEl.querySelector(`#${DOM_IDS.PROTAGONIST_LABEL}`);
  const actionBtns = [attackBtn, defendBtn, escapeBtn, zooBtn, itemBtn];

  attackBtn?.addEventListener('click', () => { void handlers.onAttack?.(); });
  defendBtn?.addEventListener('click', () => { void handlers.onDefend?.(); });
  escapeBtn?.addEventListener('click', () => { void handlers.onEscape?.(); });
  zooBtn?.addEventListener('click', () => { void handlers.onZoo?.(); });
  itemBtn?.addEventListener('click', () => handlers.onItemClick?.());

  let tutorialLocked = false;

  function setDisabled(disabled) {
    actionBtns.forEach((btn) => {
      if (btn) btn.disabled = disabled || tutorialLocked;
    });
  }

  function setTutorialLock(locked) {
    tutorialLocked = !!locked;
    setDisabled(tutorialLocked);
  }

  function updateZooTip(_ctx) {
    // Player Zoo UI disabled for camp — never show tip.
    if (!zooTip) return;
    zooTip.className = 'hidden';
    zooTip.innerHTML = '';
    zooTip.setAttribute('aria-hidden', 'true');
  }

  function updateProtagonistBar(ctx) {
    if (!protagonistBar) return;
    const ctrlId = ctx.hud?.controllable_protagonist_id;
    const isLeader = !!ctx.hud?.me?.is_team_leader;
    const show = !!ctrlId && isLeader && !TERMINAL_PHASES.includes(ctx.phase);
    if (show) {
      protagonistBar.classList.remove('hidden');
      const members = ctx.hud?.members || {};
      const pro = members[ctrlId];
      const name = pro?.display_name || '主角';
      if (protagonistLabel) protagonistLabel.textContent = `代替 ${name} 行動`;
    } else {
      protagonistBar.classList.add('hidden');
    }
  }

  return {
    setTutorialLock,
    update(ctx) {
      const absorbing = TERMINAL_PHASES.includes(ctx.phase);
      const busy = BUSY_PHASES.includes(ctx.phase);
      const submitted = !!ctx.hud?.me?.submitted;
      setDisabled(absorbing || busy || submitted || tutorialLocked);
      // Always hide Zoo control for players (camp: no Zoo usage).
      if (zooBtn) {
        zooBtn.classList.add('hidden');
        zooBtn.disabled = true;
        zooBtn.setAttribute('aria-hidden', 'true');
        zooBtn.tabIndex = -1;
      }

      updateZooTip(ctx);
      updateProtagonistBar(ctx);
    },
  };
}