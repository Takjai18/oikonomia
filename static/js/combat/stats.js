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