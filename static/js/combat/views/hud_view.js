import { DOM_IDS, TEST_IDS } from '../selectors.js';
import { bindAvatarImage } from '../avatar_urls.js';

export function createHudView(rootEl) {
  const enemyAvatar = rootEl.querySelector(`#${DOM_IDS.ENEMY_AVATAR}`);
  const enemyName = rootEl.querySelector(`#${DOM_IDS.ENEMY_NAME}`);
  const enemyHp = rootEl.querySelector(`#${DOM_IDS.ENEMY_HP}`);
  const enemyHpBar = rootEl.querySelector(`#${DOM_IDS.ENEMY_HP_BAR}`);
  const playerAvatar = rootEl.querySelector(`#${DOM_IDS.PLAYER_AVATAR}`);
  const playerName = rootEl.querySelector(`#${DOM_IDS.PLAYER_NAME}`);
  const playerHp = rootEl.querySelector(`#${DOM_IDS.PLAYER_HP}`);
  const playerHpBar = rootEl.querySelector(`#${DOM_IDS.PLAYER_HP_BAR}`);
  const teamStatus = rootEl.querySelector(`#${DOM_IDS.TEAM_STATUS}`);
  const logEl = rootEl.querySelector(`#${DOM_IDS.LOG}`);

  function hpPct(hp, max) {
    const h = parseInt(hp, 10);
    const m = parseInt(max, 10) || 1;
    return `${Math.max(0, Math.min(100, (h / m) * 100))}%`;
  }

  function setHp(bar, text, hp, max) {
    if (bar) bar.style.width = hpPct(hp, max);
    if (text) text.textContent = `${hp ?? '—'}/${max ?? '—'}`;
  }

  return {
    update(ctx, { hpOnly = false } = {}) {
      const enemy = ctx.hud?.enemy;
      const me = ctx.hud?.me;
      if (enemy) {
        if (!hpOnly && enemyName) enemyName.textContent = enemy.name || '敵人';
        if (!hpOnly && enemyAvatar) {
          bindAvatarImage(enemyAvatar, enemy.avatar, { isEnemy: true });
        }
        setHp(enemyHpBar, enemyHp, enemy.hp, enemy.max_hp);
      }
      if (me) {
        if (!hpOnly && playerName) playerName.textContent = me.display_name || '你';
        if (!hpOnly && playerAvatar) {
          bindAvatarImage(playerAvatar, me.avatar, { isProtagonist: !!me.is_protagonist });
        }
        setHp(playerHpBar, playerHp, me.hp, me.max_hp);
      }
      if (!hpOnly && teamStatus) {
        const members = ctx.hud?.members || {};
        teamStatus.innerHTML = Object.entries(members)
          .map(([id, m]) => {
            const label = m.is_protagonist ? '⭐ ' : '';
            const isSubmitted = !!m.submitted;
            const status = isSubmitted ? '✅ 已就緒' : '⏳ 等待中';
            const statusCss = isSubmitted ? 'text-green-400 font-bold' : 'text-amber-500 animate-pulse';
            const actionHint = (isSubmitted && m.action_type)
              ? ` · <span class="text-zinc-300">[${escapeHtml(m.action_type)}]</span>${m.dice_result != null ? `（骰${m.dice_result}）` : ''}`
              : '';
            return `<div class="text-xs flex justify-between py-0.5 border-b border-zinc-800/40 gap-2"><span class="truncate">${label}${escapeHtml(m.display_name || id)}</span><span class="shrink-0 ${statusCss}">${status}${actionHint}</span></div>`;
          })
          .join('');
      }
      if (!hpOnly && logEl) {
        const logs = ctx.hud?.log || [];
        logEl.innerHTML = logs.slice(-12).map((e) => {
          const msg = typeof e === 'string' ? e : (e.message || '');
          return `<div class="text-zinc-400 text-xs py-0.5">${escapeHtml(msg)}</div>`;
        }).join('');
      }
    },
  };
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}