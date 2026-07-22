/**
 * @file static/js/combat/views/settlement_view.js
 * @description 回合傷害結算視圖
 */

import { DOM_IDS, TEST_IDS } from '../selectors.js';

export function createSettlementView(rootEl) {
  let modal = rootEl.querySelector(`#${DOM_IDS.SETTLEMENT_MODAL}`);
  const body = rootEl.querySelector(`#${DOM_IDS.SETTLEMENT_BODY}`);
  const ackBtn = rootEl.querySelector(`#${DOM_IDS.SETTLEMENT_ACK}`);
  let onAck = null;

  function ensureBodyHost(el) {
    if (!el || !el.ownerDocument) return el;
    const docBody = el.ownerDocument.body;
    if (docBody && el.parentElement !== docBody) {
      docBody.appendChild(el);
    }
    return el;
  }

  ackBtn?.addEventListener('click', () => {
    if (onAck) onAck();
  });

  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function renderBreakdown(settlement, hud) {
    const hits = settlement.player_hits || [];
    const counters = settlement.counter_hits || [];
    const me = hud?.me?.display_name || '你';
    const members = hud?.members || {};

    let html = `<div class="space-y-3 text-xs max-h-[50vh] overflow-y-auto pr-1 font-mono">`;

    html += `<div data-testid="${TEST_IDS.TEAM_DAMAGE}" class="text-sm font-bold text-amber-400 border-b border-zinc-800 pb-1.5">💥 隊伍造成 ${settlement.team_damage_dealt} 點傷害</div>`;
    if (settlement.enemy_damage_dealt > 0) {
      html += `<div class="text-red-400 font-bold">🎯 敵方反擊造成 ${settlement.enemy_damage_dealt} 點傷害</div>`;
    }

    if (hits.length) {
      html += `<div class="text-zinc-400 font-bold mt-2 text-[11px]">⚔️ 我方行動明細：</div>`;
      hits.forEach((h) => {
        const isMe = h.role === 'self' || h.player === me;
        const roleTag = isMe ? '（你）' : '';
        const color = isMe ? 'text-zinc-200' : 'text-zinc-400';
        const itemTag = h.action_type === 'use_item' ? ' 🎒' : '';
        html += `<div class="${color} pl-2 border-l border-zinc-800">${escapeHtml(h.player || '—')}${roleTag}${itemTag}：造成 <span class="text-rose-400 font-bold">${h.damage}</span> 點傷害</div>`;
      });
    } else if (settlement.team_damage_dealt > 0) {
      html += `<div class="text-zinc-400 pl-2 border-l border-zinc-800">${escapeHtml(me)}：造成 <span class="text-rose-400 font-bold">${settlement.team_damage_dealt}</span> 點傷害</div>`;
    }

    if (counters.length) {
      html += `<div class="text-zinc-400 font-bold mt-2 text-[11px]">🛡️ 敵方防禦反擊：</div>`;
      counters.forEach((c) => {
        html += `<div class="text-red-300/90 pl-2 border-l border-red-950">${escapeHtml(c.target || '—')} 承受了 <span class="text-red-400 font-bold">${c.damage}</span> 點反擊傷害</div>`;
      });
    }

    html += `<div class="text-zinc-400 font-bold mt-2 text-[11px]">🎒 本回合戰資消耗：</div>`;
    let hasItemConsumables = false;

    const itemEffectLabels = {
      power_up: '算力乘數增益',
      hp_up: '生命回復',
      sanity_up: '神智解控',
    };

    Object.values(members).forEach((m) => {
      if (m.action_type === 'use_item' && (m.item_id || m.item_effect_type)) {
        hasItemConsumables = true;
        const effectDetail = m.item_effect_label
          || itemEffectLabels[m.item_effect_type]
          || '觸發戰術整備';
        const healTag = m.item_effect_type === 'hp_up' ? ' ❤️' : '';
        const sanTag = m.item_effect_type === 'sanity_up' ? ' 🧠' : '';
        html += `<div class="text-amber-300/90 bg-amber-950/20 border border-amber-900/30 p-1.5 rounded-lg mt-1 flex justify-between gap-2">
          <span>🎒 ${escapeHtml(m.display_name || '—')} 消耗了戰鬥道具${healTag}${sanTag}</span>
          <span class="text-[10px] text-amber-400 shrink-0 font-bold">[${effectDetail}]</span>
        </div>`;
      }

      if (m.is_protagonist && m.action_type) {
        html += `<div class="text-purple-300 bg-purple-950/20 border border-purple-900/30 p-1.5 rounded-lg mt-1">⭐ 主角行為：[${escapeHtml(m.action_type)}] ${m.dice_result != null ? `（骰 ${m.dice_result}）` : ''}</div>`;
      }
    });

    if (!hasItemConsumables) {
      html += `<div class="text-zinc-600 italic pl-2 text-[10px]">無物品消耗</div>`;
    }

    if (settlement.enemy_hp_after != null && settlement.enemy_hp_after !== undefined) {
      html += `<div class="text-[10px] text-zinc-500 pt-2 border-t border-zinc-800/60 text-right">敵人剩餘生命值：${settlement.enemy_hp_after}</div>`;
    }

    html += `</div>`;
    return html;
  }

  return {
    isVisible() {
      return modal && !modal.classList.contains('hidden');
    },
    show(settlement, ctx, { killing = false } = {}) {
      modal = ensureBodyHost(modal || rootEl.querySelector(`#${DOM_IDS.SETTLEMENT_MODAL}`));
      if (!modal) return;
      const bodyEl = modal.querySelector(`#${DOM_IDS.SETTLEMENT_BODY}`) || body;
      const ack = modal.querySelector(`#${DOM_IDS.SETTLEMENT_ACK}`) || ackBtn;
      if (bodyEl) bodyEl.innerHTML = renderBreakdown(settlement, ctx.hud);
      if (ack) {
        ack.textContent = killing ? '確定，查看勝利結果' : '確認並進入下一回合';
        ack.dataset.testid = TEST_IDS.SETTLEMENT_CONFIRM;
      }
      modal.className = 'fixed inset-0 z-[115] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm';
    },
    hide() {
      modal = modal || rootEl.querySelector(`#${DOM_IDS.SETTLEMENT_MODAL}`);
      if (modal) {
        modal.className = 'hidden';
      }
    },
    onAck(handler) {
      onAck = handler;
    },
  };
}