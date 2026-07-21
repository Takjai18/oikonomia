import { DOM_IDS } from '../selectors.js';
import { bindAvatarImage } from '../avatar_urls.js';
import { parseCombatHp, Phase, TERMINAL_PHASES } from '../state_machine.js';
import { resolveCombatStats, statBarPct, isStaleHudSnapshot } from '../stats.js';

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
  const playerStatsLabel = rootEl.querySelector(`#${DOM_IDS.PLAYER_STATS_LABEL}`);
  const playerPirLabel = rootEl.querySelector('#combat-v2-player-stats-pir-label');
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

  function playerStatsLabelText(me) {
    const name = (me?.display_name || '').trim();
    if (!name || name === '你') return '我';
    return name.length > 6 ? `${name.slice(0, 6)}…` : name;
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
      const label = playerStatsLabelText(me);
      const fullName = (me?.display_name || '').trim();
      if (playerStatsLabel) {
        playerStatsLabel.textContent = label;
        if (fullName) playerStatsLabel.title = fullName;
      }
      if (playerPirLabel) {
        playerPirLabel.textContent = label;
        if (fullName) playerPirLabel.title = fullName;
      }
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
    update(ctx, { hpOnly = false, snapshot = null } = {}) {
      const enemy = ctx.hud?.enemy;
      const me = ctx.hud?.me;
      const stale = snapshot ? isStaleHudSnapshot(ctx, snapshot) : false;

      if (!stale) {
        renderVitals(enemy, me);
      }

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
      // Team / Iggy roster: always refresh HP+sanity (including hpOnly poll sync).
      if (teamStatus) {
        renderTeamStatus(teamStatus, ctx, { hpOnly });
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

/**
 * Teammates + Iggy (protagonists): name, ready status, HP bar, sanity.
 * @param {HTMLElement} teamStatus
 * @param {object} ctx
 * @param {{ hpOnly?: boolean }} [opts]
 */
function renderTeamStatus(teamStatus, ctx, opts = {}) {
  const members = ctx.hud?.members || {};
  const entries = Object.entries(members);
  if (!entries.length) {
    if (!opts.hpOnly) teamStatus.innerHTML = '';
    return;
  }

  const combatOver = TERMINAL_PHASES.includes(ctx.phase)
    || ctx.hud?.active === false;
  const escaped = ctx.phase === Phase.ESCAPED
    || ctx.hud?.outcome === 'escaped'
    || ctx.hud?.winner === 'escaped';
  const myId = ctx.hud?.me?.squad_id || ctx.hud?.my_squad_id || null;

  // Stable order: self first, then protagonists, then others (name).
  entries.sort(([idA, a], [idB, b]) => {
    const score = (id, m) => {
      if (myId && id === myId) return 0;
      if (m.is_protagonist) return 1;
      return 2;
    };
    const d = score(idA, a) - score(idB, b);
    if (d !== 0) return d;
    return String(a.display_name || idA).localeCompare(String(b.display_name || idB), 'zh');
  });

  teamStatus.innerHTML = entries.map(([id, m]) => {
    const isSelf = myId && id === myId;
    const label = m.is_protagonist ? '⭐ ' : (isSelf ? '👤 ' : '');
    const name = escapeHtml(m.display_name || id);
    const isSubmitted = !!m.submitted || combatOver;
    const status = combatOver
      ? (escaped ? '🏃 已脫離' : '⏹ 結束')
      : (isSubmitted ? '✅ 已就緒' : '⏳ 等待中');
    const statusCss = combatOver
      ? 'text-emerald-400 font-bold'
      : (isSubmitted ? 'text-green-400 font-bold' : 'text-amber-500 animate-pulse');
    const actionHint = (!combatOver && isSubmitted && m.action_type)
      ? ` · <span class="text-zinc-300">[${escapeHtml(m.action_type)}]</span>${m.dice_result != null ? `（骰${m.dice_result}）` : ''}`
      : '';

    const maxHp = parseCombatHp(m.max_hp, 100);
    const hp = parseCombatHp(m.hp, maxHp);
    const sanity = resolveCombatStats(m)?.sanity ?? parseCombatHp(m.sanity, 100);
    const hpPctVal = Math.max(0, Math.min(100, (hp / maxHp) * 100));
    const sanPctVal = Math.max(0, Math.min(100, (sanity / 100) * 100));
    const hpBarColor = hpPctVal <= 25 ? 'bg-red-500' : (hpPctVal <= 50 ? 'bg-amber-500' : 'bg-rose-400');
    const sanBarColor = sanPctVal <= 30 ? 'bg-red-400' : 'bg-purple-500';
    const nearDeath = !!(m.near_death_until) && hp <= 0;

    return `
      <div class="py-1.5 border-b border-zinc-800/50 last:border-0" data-member-id="${escapeHtml(id)}">
        <div class="text-xs flex justify-between gap-2 items-baseline mb-0.5">
          <span class="truncate font-medium text-zinc-200">${label}${name}${nearDeath ? ' <span class="text-red-400 text-[10px]">瀕死</span>' : ''}</span>
          <span class="shrink-0 ${statusCss} text-[10px]">${status}${actionHint}</span>
        </div>
        <div class="grid grid-cols-2 gap-x-2 gap-y-0.5">
          <div>
            <div class="flex justify-between text-[10px] text-zinc-500 mb-0.5">
              <span>❤️ 生命</span>
              <span class="font-mono text-rose-300">${hp}/${maxHp}</span>
            </div>
            <div class="h-1 bg-zinc-800 rounded overflow-hidden">
              <div class="h-full ${hpBarColor} transition-all duration-300" style="width:${hpPctVal}%"></div>
            </div>
          </div>
          <div>
            <div class="flex justify-between text-[10px] text-zinc-500 mb-0.5">
              <span>🧠 神智</span>
              <span class="font-mono text-purple-300">${sanity}/100</span>
            </div>
            <div class="h-1 bg-zinc-800 rounded overflow-hidden">
              <div class="h-full ${sanBarColor} transition-all duration-300" style="width:${sanPctVal}%"></div>
            </div>
          </div>
        </div>
      </div>`;
  }).join('');
}