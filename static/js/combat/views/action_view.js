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

  function setDisabled(disabled) {
    actionBtns.forEach((btn) => {
      if (btn) btn.disabled = disabled;
    });
  }

  function updateZooTip(ctx) {
    if (!zooTip) return;
    const me = ctx.hud?.me;
    if (!me || TERMINAL_PHASES.includes(ctx.phase)) {
      zooTip.className = 'hidden';
      zooTip.innerHTML = '';
      return;
    }

    const sanity = parseInt(me.sanity ?? 0, 10);
    const allowZoo = ctx.hud?.allow_zoo !== false;
    const zooMult = zooBonusMultiplier(sanity);
    const bChance = berserkChancePct(sanity);

    if (!allowZoo) {
      zooTip.className = 'hidden';
      zooTip.innerHTML = '';
      return;
    }

    if (bChance > 0) {
      zooTip.className = 'text-[10px] text-red-400 font-mono animate-pulse bg-red-950/20 border border-red-900/30 p-1.5 rounded-xl mx-3';
      zooTip.innerHTML = `⚠️ 神智偏低 (${sanity})：發動行動有 <b>${bChance}%</b> 暴走機率，可能無法對敵造成傷害！`;
    } else if (zooMult > 1.0) {
      zooTip.className = 'text-[10px] text-purple-400 font-mono bg-purple-950/20 border border-purple-900/30 p-1.5 rounded-xl mx-3';
      zooTip.innerHTML = `✨ Zoo 就緒：神智 ${sanity}，發動 Zoo 可獲 <b>×${zooMult}</b> 算力增益`;
    } else {
      zooTip.className = 'text-[10px] text-zinc-500 font-mono bg-zinc-900/40 border border-zinc-800 p-1.5 rounded-xl mx-3';
      zooTip.innerHTML = `Zoo 可發動（神智 ${sanity}）；神智 ≥70 才有加成（目前 ×1.0）`;
    }
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
    update(ctx) {
      const absorbing = TERMINAL_PHASES.includes(ctx.phase);
      const busy = BUSY_PHASES.includes(ctx.phase);
      const submitted = !!ctx.hud?.me?.submitted;
      const allowZoo = ctx.hud?.allow_zoo !== false;

      setDisabled(absorbing || busy || submitted);
      if (zooBtn) {
        // Stage-locked / encounter-disabled: hide entirely (not greyed out).
        if (!allowZoo) {
          zooBtn.classList.add('hidden');
          zooBtn.disabled = true;
          zooBtn.title = '';
        } else {
          zooBtn.classList.remove('hidden');
          zooBtn.disabled = absorbing || busy || submitted;
          zooBtn.title = '';
        }
      }

      updateZooTip(ctx);
      updateProtagonistBar(ctx);
    },
  };
}