/** @file Normalize round settlement from API — prevent zero-damage stale breakdown */

/**
 * @param {object} apiPayload
 * @returns {object|null}
 */
export function normalizeSettlement(apiPayload) {
  if (!apiPayload) return null;

  let settlement = apiPayload.round_settlement;

  if (!settlement || isZeroSettlement(settlement)) {
    settlement = {
      team_damage_dealt: apiPayload.round_enemy_damage || 0,
      enemy_damage_dealt: apiPayload.round_player_damage || 0,
      enemy_hp_after: apiPayload.enemy?.hp ?? null,
      player_hits: [],
      counter_hits: [],
      breakdown: {},
    };
  }

  const teamDealt = intVal(
    settlement.team_damage_dealt ?? settlement.round_enemy_damage ?? apiPayload.round_enemy_damage,
  );
  const enemyDealt = intVal(
    settlement.enemy_damage_dealt ?? settlement.round_player_damage ?? apiPayload.round_player_damage,
  );

  const enemyHp = apiPayload.enemy?.hp;
  const enemyHpAfter = settlement.enemy_hp_after ?? enemyHp;

  return {
    team_damage_dealt: teamDealt,
    enemy_damage_dealt: enemyDealt,
    enemy_hp_after: enemyHpAfter != null ? intVal(enemyHpAfter) : null,
    player_hits: settlement.player_hits || [],
    counter_hits: settlement.counter_hits || [],
    breakdown: settlement.breakdown || {},
    escape_triggered: !!settlement.escape_triggered,
    escape_success: !!settlement.escape_success,
  };
}

function isZeroSettlement(s) {
  const dealt = intVal(s.team_damage_dealt);
  const hits = s.player_hits || [];
  if (dealt > 0) return false;
  return hits.length === 0;
}

function intVal(v) {
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : 0;
}

export function deriveSettledIndex(payload) {
  const phase = intVal(payload.current_phase);
  if (payload.round_resolved) return Math.max(0, phase - 1);
  return Math.max(0, phase - 1);
}

export function deriveSettlementId(payload) {
  if (payload.settlement_id) return String(payload.settlement_id);
  const combatId = payload.combat_id;
  const idx = payload.settled_round_index ?? deriveSettledIndex(payload);
  if (combatId == null) return null;
  return `${combatId}:${idx}`;
}

/**
 * Fallback: rebuild settlement slice from combat logs.
 * @param {Array} logEntries
 * @param {number} settledRoundIndex
 */
export function buildSettlementFromLogs(logEntries, settledRoundIndex) {
  const entries = Array.isArray(logEntries) ? logEntries : [];
  const summaries = entries
    .map((e, i) => ({ e, i }))
    .filter(({ e }) => e?.type === 'summary' || (e?.message || '').includes('回合結算'));

  if (summaries.length === 0) return null;

  const targetIdx = Math.min(settledRoundIndex, summaries.length - 1);
  const summaryEntry = summaries[targetIdx]?.e || summaries[summaries.length - 1].e;
  const summaryIdx = summaries[targetIdx]?.i ?? summaries[summaries.length - 1].i;
  const msg = summaryEntry?.message || '';

  const teamMatch = msg.match(/隊伍造成\s*(\d+)\s*點傷害/);
  const enemyMatch = msg.match(/敵方造成\s*(\d+)\s*點傷害/);
  const hpMatch = msg.match(/剩餘\s*HP\s*(\d+)/);

  const player_hits = [];
  const start = targetIdx > 0 ? summaries[targetIdx - 1].i + 1 : 0;
  for (let i = start; i < summaryIdx; i++) {
    const entry = entries[i];
    if (!entry?.message) continue;
    const hit = entry.message.match(/造成\s*(\d+)\s*點傷害/);
    if (hit) {
      player_hits.push({ player: '—', damage: intVal(hit[1]) });
    }
  }

  const teamDealt = teamMatch ? intVal(teamMatch[1]) : player_hits.reduce((s, h) => s + h.damage, 0);

  return {
    team_damage_dealt: teamDealt,
    enemy_damage_dealt: enemyMatch ? intVal(enemyMatch[1]) : 0,
    enemy_hp_after: hpMatch ? intVal(hpMatch[1]) : null,
    player_hits,
    counter_hits: [],
    breakdown: {},
  };
}

/**
 * First paint after /combat/start — prefer start enemy HP when status returns a
 * transient 0 HP snapshot without victory (poll race / stale DB row).
 */
export function mergeEntryCombatPayload(startPayload, statusPayload) {
  if (!startPayload) return statusPayload || {};
  if (!statusPayload) return startPayload;
  const merged = { ...startPayload, ...statusPayload };
  const startEnemy = startPayload.enemy;
  const statusEnemy = statusPayload.enemy;
  const active = statusPayload.active !== false
    && ['player_phase', 'precheck'].includes(statusPayload.status);
  const noOutcome = !statusPayload.outcome && !statusPayload.winner;

  if (!statusEnemy && startEnemy) {
    merged.enemy = startEnemy;
    return merged;
  }

  if (active && noOutcome && startEnemy && statusEnemy) {
    const statusHp = parseInt(statusEnemy.hp, 10);
    const startHp = parseInt(startEnemy.hp, 10);
    const maxHp = parseInt(statusEnemy.max_hp ?? startEnemy.max_hp, 10);
    if (
      Number.isFinite(statusHp)
      && statusHp <= 0
      && ((Number.isFinite(startHp) && startHp > 0) || (Number.isFinite(maxHp) && maxHp > 0))
    ) {
      const hp = Number.isFinite(startHp) && startHp > 0 ? startHp : maxHp;
      merged.enemy = { ...statusEnemy, ...startEnemy, hp };
    }
  }
  return merged;
}

export function extractHud(snapshot) {
  if (!snapshot) return { enemy: null, me: null, members: {}, log: [] };
  const teamId = snapshot.team_id || null;
  const route = snapshot.route || null;
  const me = snapshot.my_state
    ? { ...snapshot.my_state, team_id: snapshot.my_state.team_id || teamId }
    : null;
  return {
    enemy: snapshot.enemy || null,
    me,
    team_id: teamId,
    route,
    encounter_id: snapshot.encounter_id || null,
    members: snapshot.member_states || {},
    log: snapshot.log_entries || snapshot.log || [],
    waiting: !!snapshot.waiting_for_teammates,
    submittedCount: snapshot.submitted_count,
    totalActive: snapshot.total_active,
    currentPhase: snapshot.current_phase,
    combatId: snapshot.combat_id,
    status: snapshot.status,
    outcome: snapshot.outcome,
    winner: snapshot.winner,
    controllable_protagonist_id: snapshot.controllable_protagonist_id || null,
    remaining_seconds: snapshot.remaining_seconds,
    berserk_chance: snapshot.berserk_chance,
    allow_zoo: snapshot.combat_settings?.allow_zoo !== false,
  };
}