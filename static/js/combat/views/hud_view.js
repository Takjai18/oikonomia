import { DOM_IDS } from '../selectors.js';
import { bindAvatarImage } from '../avatar_urls.js';
import { parseCombatHp } from '../state_machine.js';
import { resolveCombatStats, statBarPct } from '../stats.js';

export function createHudView(rootEl) {
  const enemyAvatar = rootEl.querySelector(`#${DOM_IDS.ENEMY_AVATAR}`);
  const enemyName = rootEl.querySelector(`#${DOM_IDS.ENEMY_NAME}`);
  const enemyHp = rootEl.querySelector(`#${DOM_IDS.ENEMY_HP}`);
  const enemyHpBar = rootEl.querySelector(`#${DOM_IDS.ENEMY_HP_BAR}`);
  const enemySanity = rootEl.querySelector(`#${DOM_IDS.ENEMY_SANITY}`);
  const enemyPower = rootEl.querySelector(`#${DOM_IDS.ENEMY_POWER}`);
  const enemyIntellect = rootEl.querySelector(`#${DOM_IDS.ENEMY_INTELLECT}`);
  const enemyResilience = rootEl.querySelector(`#${DOM_IDS.ENEMY_RESILIENCE}`);
  const playerAvatar = rootEl.querySelector(`#${DOM_IDS.PLAYER_AVATAR}`);
  const playerName = rootEl.querySelector(`#${DOM_IDS.PLAYER_NAME}`);
  const playerHp = rootEl.querySelector(`#${DOM_IDS.PLAYER_HP}`);
  const playerHpBar = rootEl.querySelector(`#${DOM_IDS.PLAYER_HP_BAR}`);
  const playerSanity = rootEl.querySelector(`#${DOM_IDS.PLAYER_SANITY}`);
  const playerSanityBar = rootEl.querySelector(`#${DOM_IDS.PLAYER_SANITY_BAR}`);
  const playerPower = rootEl.querySelector(`#${DOM_IDS.PLAYER_POWER}`);
  const playerIntellect = rootEl.querySelector(`#${DOM_IDS.PLAYER_INTELLECT}`);
  const playerResilience = rootEl.querySelector(`#${DOM_IDS.PLAYER_RESILIENCE}`);
  const teamStatus = rootEl.querySelector(`#${DOM_IDS.TEAM_STATUS}`);
  const logEl = rootEl.querySelector(`#${DOM_IDS.LOG}`);
  const practiceExitBtn = rootEl.querySelector(`#${DOM_IDS.PRACTICE_EXIT_BTN}`);

  function hpPct(hp, max) {
    const h = parseCombatHp(hp, max);
    const m = parseCombatHp(max, 100);
    return `${Math.max(0, Math.min(100, (h / m) * 100))}%`;
  }

  function setHp(bar, text, hp, max) {
    const maxVal = parseCombatHp(max, 100);
    const hpVal = parseCombatHp(hp, maxVal);
    if (bar) bar.style.width = hpPct(hpVal, maxVal);
    if (text) text.textContent = `${hpVal}/${maxVal}`;
  }

  function setSanity(bar, text, sanity) {
    const val = resolveCombatStats({ sanity })?.sanity ?? 100;
    if (bar) bar.style.width = statBarPct(val, 100);
    if (text) text.textContent = `${val}/100`;
  }

  function setStatText(el, value) {
    if (el) el.textContent = String(value ?? '—');
  }

  function renderVitals(enemy, me) {
    if (enemy) {
      setHp(enemyHpBar, enemyHp, enemy.hp, enemy.max_hp);
      const estats = resolveCombatStats(enemy);
      if (estats) {
        setStatText(enemySanity, estats.sanity);
        setStatText(enemyPower, estats.power);
        setStatText(enemyIntellect, estats.intellect);
        setStatText(enemyResilience, estats.resilience);
      }
    }
    if (me) {
      setHp(playerHpBar, playerHp, me.hp, me.max_hp);
      const pstats = resolveCombatStats(me);
      if (pstats) {
        setSanity(playerSanityBar, playerSanity, pstats.sanity);
        setStatText(playerPower, pstats.power);
        setStatText(playerIntellect, pstats.intellect);
        setStatText(playerResilience, pstats.resilience);
      }
    }
  }

  return {
    update(ctx, { hpOnly = false } = {}) {
      const enemy = ctx.hud?.enemy;
      const me = ctx.hud?.me;

      renderVitals(enemy, me);

      if (enemy && !hpOnly) {
        if (enemyName) enemyName.textContent = enemy.name || '敵人';
        if (enemyAvatar) {
          bindAvatarImage(enemyAvatar, enemy.avatar, { isEnemy: true });
        }
      }
      if (me && !hpOnly) {
        if (playerName) playerName.textContent = me.display_name || '你';
        if (playerAvatar) {
          bindAvatarImage(playerAvatar, me.avatar, { isProtagonist: !!me.is_protagonist });
        }
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
      if (practiceExitBtn) {
        const encounterId = ctx.hud?.encounter_id || '';
        const showPracticeExit = typeof encounterId === 'string' && encounterId.startsWith('practice_');
        practiceExitBtn.classList.toggle('hidden', !showPracticeExit);
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