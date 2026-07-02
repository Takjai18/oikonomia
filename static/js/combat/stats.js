/** @file Combat HUD stat parsing — defensive extraction from my_state / enemy */

/**
 * @param {number|string|null|undefined} value
 * @param {number|null} [fallback]
 */
export function parseCombatStat(value, fallback = null) {
  const n = parseInt(value, 10);
  return Number.isFinite(n) ? n : fallback;
}

/**
 * @param {object|null|undefined} entity
 * @returns {{ hp: number, max_hp: number, sanity: number, power: number, intellect: number, resilience: number } | null}
 */
export function resolveCombatStats(entity) {
  if (!entity || typeof entity !== 'object') return null;
  const maxHp = parseCombatStat(entity.max_hp, 100) ?? 100;
  return {
    hp: parseCombatStat(entity.hp, maxHp) ?? maxHp,
    max_hp: maxHp,
    sanity: parseCombatStat(entity.sanity, 100) ?? 100,
    power: parseCombatStat(entity.power, 0) ?? 0,
    intellect: parseCombatStat(entity.intellect, 0) ?? 0,
    resilience: parseCombatStat(entity.resilience, 0) ?? 0,
  };
}

/**
 * @param {number} value
 * @param {number} [max=100]
 */
export function statBarPct(value, max = 100) {
  const v = parseCombatStat(value, 0) ?? 0;
  const m = parseCombatStat(max, 100) ?? 100;
  return `${Math.max(0, Math.min(100, (v / m) * 100))}%`;
}

/**
 * INV-C: reject poll snapshots older than local settled round (hpOnly race guard).
 * @param {{ settledRoundIndex?: number }} ctx
 * @param {{ settled_round_index?: number|string, current_phase?: number|string }} snapshot
 */
export function isStaleHudSnapshot(ctx, snapshot) {
  if (!snapshot) return false;
  // Terminal payloads must never be dropped — post-combat pipeline / VICTORY routing (INV-C).
  if (
    snapshot.outcome === 'victory'
    || snapshot.outcome === 'defeat'
    || snapshot.winner
    || snapshot.status === 'ended'
    || snapshot.active === false
  ) {
    return false;
  }
  const apiIdx = parseInt(snapshot.settled_round_index, 10);
  if (
    Number.isFinite(apiIdx)
    && ctx.settledRoundIndex >= 0
    && apiIdx < ctx.settledRoundIndex
  ) {
    return true;
  }
  return false;
}

/** Active player_phase with enemy max_hp>0 but hp<=0 — likely transient entry bug. */
export function needsEntryHudRepair(hud, snapshot = {}) {
  const enemy = hud?.enemy;
  if (!enemy) return true;
  const hp = parseCombatStat(enemy.hp, null);
  const maxHp = parseCombatStat(enemy.max_hp, 100) ?? 100;
  const active = snapshot.active !== false
    && ['player_phase', 'precheck'].includes(snapshot.status);
  const noOutcome = !snapshot.outcome && !snapshot.winner;
  return !!(active && noOutcome && maxHp > 0 && (hp == null || hp <= 0));
}