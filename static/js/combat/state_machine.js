/** @file Pure combat FSM — zero DOM dependency */

import { normalizeSettlement, deriveSettlementId } from './settlement.js';

/** Fallback when HP field is missing (display / max baseline — not “alive” sentinel). */
export const DEFAULT_COMBAT_MAX_HP = 100;

export const Phase = {
  IDLE: 'IDLE',
  DICE_ROLLING: 'DICE_ROLLING',
  DICE_CONFIRM: 'DICE_CONFIRM',
  SUBMITTING: 'SUBMITTING',
  WAITING_FOR_PLAYERS: 'WAITING_FOR_PLAYERS',
  ESCAPE_ATTEMPT: 'ESCAPE_ATTEMPT',
  SETTLEMENT: 'SETTLEMENT',
  COMBAT_FAILED: 'COMBAT_FAILED',
  VICTORY: 'VICTORY',
  DEFEAT: 'DEFEAT',
  ESCAPED: 'ESCAPED',
};

/** SSOT: terminal absorbing phases (views + poll guards) */
export const TERMINAL_PHASES = Object.freeze([
  Phase.COMBAT_FAILED,
  Phase.VICTORY,
  Phase.DEFEAT,
  Phase.ESCAPED,
]);

const PHASE_LABELS = {
  [Phase.IDLE]: '等待行動',
  [Phase.DICE_ROLLING]: '擲骰中',
  [Phase.DICE_CONFIRM]: '確認行動',
  [Phase.SUBMITTING]: '伺服器結算中',
  [Phase.WAITING_FOR_PLAYERS]: '等待隊友',
  [Phase.ESCAPE_ATTEMPT]: '逃跑判定',
  [Phase.SETTLEMENT]: '傷害結算',
  [Phase.COMBAT_FAILED]: '戰鬥失敗',
  [Phase.VICTORY]: '戰鬥勝利',
  [Phase.DEFEAT]: '戰鬥失敗',
  [Phase.ESCAPED]: '成功逃跑',
};

const ABSORBING = new Set(TERMINAL_PHASES);

const DICE_BUSY = new Set([Phase.DICE_ROLLING, Phase.DICE_CONFIRM]);

/** Phases that must exit SETTLEMENT without pinning poll handler */
const SETTLEMENT_EXIT_PHASES = new Set(TERMINAL_PHASES);

function terminalModalTeardownEffects(effects) {
  return [
    { type: 'HIDE_SETTLEMENT' },
    { type: 'HIDE_ALL_MODALS' },
    ...effects.filter(
      (e) => e.type !== 'HIDE_ALL_MODALS' && e.type !== 'HIDE_SETTLEMENT',
    ),
  ];
}

/**
 * @returns {import('./state_machine.js').CombatContext}
 */
export function createInitialContext(combatId = null) {
  return {
    combatId,
    phase: Phase.IDLE,
    settledRoundIndex: -1,
    pendingSettlement: null,
    pendingSettlementId: null,
    shownSettlementIds: new Set(),
    isKillingBlow: false,
    failedMembers: [],
    escapePending: false,
    dice: { action: null, value: null },
    hud: { enemy: null, me: null, members: {}, log: [] },
    pollPaused: false,
    error: null,
    entrySyncPending: false,
  };
}

export function canDispatch(ctx, event, meta = {}) {
  const rule = resolveTransition(ctx, event);
  if (!rule) return false;
  if (rule.guard && !rule.guard(ctx, meta)) return false;
  return true;
}

export function blockedMessage(ctx, actionName = '此操作') {
  const phase = PHASE_LABELS[ctx.phase] || ctx.phase;
  if (ctx.phase === Phase.DICE_ROLLING) return '系統擲骰中，請稍候…';
  if (ctx.phase === Phase.DICE_CONFIRM) return '請先完成當前行動';
  if (ctx.phase === Phase.SUBMITTING) return '回合提交結算中，請稍候…';
  if (ctx.phase === Phase.SETTLEMENT) return '請先關閉當前結算彈窗';
  if (ctx.phase === Phase.WAITING_FOR_PLAYERS) return '已提交，等待其他隊友…';
  if (ctx.phase === Phase.ESCAPE_ATTEMPT) return '逃跑判定中，請稍候…';
  if (ABSORBING.has(ctx.phase)) return `戰鬥已結束（${phase}）`;
  if (ctx.hud?.me?.submitted) return '本回合行動已提交';
  return `${actionName}目前不可用（${phase}）`;
}

/**
 * @typedef {Object} Effect
 * @property {string} type
 */

/**
 * @returns {{ ctx: object, effects: Effect[] }}
 */
export function transition(ctx, event, meta = {}) {
  const rule = resolveTransition(ctx, event);
  if (!rule) {
    return {
      ctx,
      effects: [{ type: 'TOAST', message: blockedMessage(ctx, event) }],
    };
  }
  if (rule.guard && !rule.guard(ctx, meta)) {
    return {
      ctx,
      effects: [{ type: 'TOAST', message: rule.guardMessage?.(ctx, meta) || blockedMessage(ctx, event) }],
    };
  }
  const prev = ctx.phase;
  const newCtx = rule.reduce(ctx, meta);
  const effects = rule.effects?.(newCtx, meta, prev) || [];
  return { ctx: newCtx, effects };
}

function resolveTransition(ctx, event) {
  const table = TRANSITIONS[ctx.phase];
  return table?.[event] || null;
}

/**
 * First poll after COMBAT_RESET — strict entry absorb boundary (INV-A/C).
 * @returns {{ ctx: object, effects: Effect[] } | null}
 */
function absorbStaleSettlementOnEntry(ctx, snapshot, settlementId) {
  if (!ctx.entrySyncPending) return null;

  const apiIdx = snapshot.settled_round_index;
  const snapRoundIdx = Number.isFinite(parseInt(apiIdx, 10))
    ? parseInt(apiIdx, 10)
    : parseInt(snapshot.current_phase, 10) - 1;
  const shown = new Set(ctx.shownSettlementIds);

  // Only mark shown when backend is in stable player_phase without an unresolved round
  if (settlementId && snapshot.status === 'player_phase' && !snapshot.round_resolved) {
    shown.add(settlementId);
  }

  const alignedCtx = {
    ...ctx,
    settledRoundIndex: Number.isFinite(snapRoundIdx) ? Math.max(0, snapRoundIdx) : 0,
    pendingSettlement: null,
    pendingSettlementId: null,
    shownSettlementIds: shown,
    entrySyncPending: false,
    phase: ctx.phase,
  };
  return {
    ctx: alignedCtx,
    effects: [{ type: 'UPDATE_HUD', hpOnly: false }],
  };
}

/** Death preempt — INV-D highest priority */
export function handleAnyDeath(ctx, members) {
  const dead = Object.entries(members || {})
    .filter(([, m]) => isMemberCollapsed(m))
    .map(([id, m]) => m.display_name || id);
  if (dead.length === 0) return { ctx, effects: [] };
  if (ctx.phase === Phase.COMBAT_FAILED) return { ctx, effects: [] };
  const newCtx = {
    ...ctx,
    phase: Phase.COMBAT_FAILED,
    failedMembers: dead,
    pollPaused: true,
    pendingSettlement: null,
    pendingSettlementId: null,
  };
  return {
    ctx: newCtx,
    effects: terminalModalTeardownEffects([
      { type: 'SHOW_FAILED', members: dead },
      { type: 'STOP_POLL' },
    ]),
  };
}

/**
 * Passive sync from poll — monotonic guards + settlement modal routing.
 * @returns {{ ctx: object, effects: Effect[] }}
 */
export function syncState(ctx, snapshot) {
  if (ABSORBING.has(ctx.phase)) {
    return { ctx, effects: [] };
  }

  const apiIdx = parseInt(snapshot.settled_round_index, 10);
  if (Number.isFinite(apiIdx) && ctx.settledRoundIndex >= 0 && apiIdx < ctx.settledRoundIndex) {
    console.warn(
      `[FSM] Stale snapshot dropped (API round ${apiIdx} < local ${ctx.settledRoundIndex})`,
    );
    return { ctx, effects: [] };
  }

  const hud = {
    enemy: snapshot.enemy || ctx.hud.enemy,
    me: snapshot.my_state || ctx.hud.me,
    members: snapshot.member_states || ctx.hud.members,
    log: snapshot.log_entries || snapshot.log || ctx.hud.log,
    waiting: !!snapshot.waiting_for_teammates,
    submittedCount: snapshot.submitted_count,
    totalActive: snapshot.total_active,
    currentPhase: snapshot.current_phase,
    combatId: snapshot.combat_id,
    status: snapshot.status,
    outcome: snapshot.outcome,
    winner: snapshot.winner,
  };

  let newCtx = { ...ctx, hud, combatId: snapshot.combat_id || ctx.combatId };
  let effects = [{ type: 'UPDATE_HUD', hpOnly: isHpOnlyPhase(ctx.phase) }];

  const death = handleAnyDeath(newCtx, hud.members);
  if (death.ctx.phase === Phase.COMBAT_FAILED) {
    return death;
  }

  if (ctx.entrySyncPending) {
    const settlementId = snapshot.round_settlement
      ? deriveSettlementId(snapshot)
      : null;
    const entryAbsorb = absorbStaleSettlementOnEntry(newCtx, snapshot, settlementId);
    if (entryAbsorb) {
      newCtx = { ...entryAbsorb.ctx, hud: newCtx.hud, combatId: newCtx.combatId };
      effects = [...entryAbsorb.effects, ...effects.filter((e) => e.type !== 'UPDATE_HUD')];
    }
  }

  if (snapshot.outcome === 'defeat' || snapshot.winner === 'enemy') {
    const deadNames = snapshot.dead_squad_names?.length
      ? snapshot.dead_squad_names
      : (snapshot.dead_squad_ids || []).map(
        (id) => snapshot.member_states?.[id]?.display_name || id,
      );
    if (deadNames.length > 0) {
      return {
        ctx: {
          ...newCtx,
          phase: Phase.COMBAT_FAILED,
          failedMembers: deadNames,
          pollPaused: true,
          pendingSettlement: null,
          pendingSettlementId: null,
        },
        effects: terminalModalTeardownEffects([
          { type: 'SHOW_FAILED', members: deadNames },
          { type: 'STOP_POLL' },
        ]),
      };
    }
    newCtx = {
      ...newCtx,
      phase: Phase.DEFEAT,
      pollPaused: true,
      pendingSettlement: null,
      pendingSettlementId: null,
      isKillingBlow: false,
    };
    return {
      ctx: newCtx,
      effects: terminalModalTeardownEffects([
        { type: 'SHOW_DEFEAT', data: snapshot },
        { type: 'STOP_POLL' },
      ]),
    };
  }

  if (snapshot.outcome === 'victory' || snapshot.winner === 'squad') {
    const settlement = normalizeSettlement(snapshot);
    const settlementId = deriveSettlementId(snapshot);
    const unseenKillingSettlement = settlement
      && settlementId
      && !ctx.shownSettlementIds.has(settlementId)
      && ctx.phase !== Phase.SETTLEMENT;

    if (unseenKillingSettlement) {
      newCtx = {
        ...newCtx,
        phase: Phase.SETTLEMENT,
        pendingSettlement: settlement,
        pendingSettlementId: settlementId,
        isKillingBlow: true,
        pollPaused: true,
      };
      return {
        ctx: newCtx,
        effects: [
          { type: 'UPDATE_HUD', hpOnly: false },
          { type: 'HIDE_SUBMITTING' },
          { type: 'SHOW_SETTLEMENT', settlement, killing: true },
          { type: 'STOP_POLL' },
        ],
      };
    }

    if (ctx.phase === Phase.SETTLEMENT) {
      return { ctx: newCtx, effects };
    }

    newCtx = {
      ...newCtx,
      phase: Phase.VICTORY,
      pollPaused: true,
      pendingSettlement: null,
      pendingSettlementId: null,
      isKillingBlow: false,
    };
    return {
      ctx: newCtx,
      effects: terminalModalTeardownEffects([
        { type: 'SHOW_VICTORY', data: snapshot },
        { type: 'STOP_POLL' },
      ]),
    };
  }

  if (snapshot.waiting_for_teammates && ctx.phase === Phase.SUBMITTING) {
    newCtx = { ...newCtx, phase: Phase.WAITING_FOR_PLAYERS };
    effects.push({ type: 'HIDE_SUBMITTING' });
    return { ctx: newCtx, effects };
  }

  if (
    ctx.phase === Phase.WAITING_FOR_PLAYERS
    && !snapshot.waiting_for_teammates
    && (snapshot.round_resolved || snapshot.status === 'round_resolved')
    && snapshot.round_settlement
  ) {
    const settlement = normalizeSettlement(snapshot);
    const settlementId = deriveSettlementId(snapshot);
    if (settlement && settlementId && !ctx.shownSettlementIds.has(settlementId)) {
      const killing = snapshot.outcome === 'victory'
        || snapshot.winner === 'squad'
        || isEnemyDefeated(snapshot.enemy);
      newCtx = {
        ...newCtx,
        phase: Phase.SETTLEMENT,
        pendingSettlement: settlement,
        pendingSettlementId: settlementId,
        isKillingBlow: killing,
        pollPaused: true,
      };
      return {
        ctx: newCtx,
        effects: [
          { type: 'UPDATE_HUD', hpOnly: false },
          { type: 'HIDE_SUBMITTING' },
          { type: 'SHOW_SETTLEMENT', settlement, killing },
          { type: 'STOP_POLL' },
        ],
      };
    }
  }

  return { ctx: newCtx, effects };
}

function isHpOnlyPhase(phase) {
  return DICE_BUSY.has(phase) || phase === Phase.SUBMITTING || phase === Phase.SETTLEMENT;
}

/**
 * Parse HP for display; uses member/enemy max_hp when value is absent.
 * @param {number|string|null|undefined} value
 * @param {number|string|null|undefined} maxHp
 */
export function parseCombatHp(value, maxHp = DEFAULT_COMBAT_MAX_HP) {
  const n = parseInt(value, 10);
  if (Number.isFinite(n)) return n;
  const max = parseInt(maxHp, 10);
  return Number.isFinite(max) ? max : DEFAULT_COMBAT_MAX_HP;
}

/** INV-D: hp ≤ 0 or active near-death marker counts as collapsed. */
export function isMemberCollapsed(member) {
  if (!member) return false;
  if (member.near_death_until) return true;
  const hp = parseInt(member.hp, 10);
  if (Number.isFinite(hp)) {
    return hp <= 0;
  }
  return false;
}

export function isEnemyDefeated(enemy) {
  const hp = parseInt(enemy?.hp, 10);
  return Number.isFinite(hp) && hp <= 0;
}

const TRANSITIONS = {
  [Phase.IDLE]: {
    COMBAT_RESET: {
      reduce: (ctx, meta) => createInitialContext(meta.combatId ?? null),
      effects: () => [{ type: 'HIDE_ALL_MODALS' }, { type: 'RENDER' }],
    },
    ACTION_ATTACK: {
      guard: (ctx) => !ctx.hud?.me?.submitted,
      reduce: (ctx, meta) => ({
        ...ctx,
        phase: Phase.DICE_ROLLING,
        dice: { action: meta.action || 'attack', value: meta.dice, cosmetic: true },
        error: null,
      }),
      effects: () => [{ type: 'SHOW_DICE_ROLLING' }],
    },
    ACTION_DEFEND: {
      guard: (ctx) => !ctx.hud?.me?.submitted,
      reduce: (ctx, meta) => ({
        ...ctx,
        phase: Phase.DICE_ROLLING,
        dice: { action: 'defend', value: null, cosmetic: false },
        error: null,
      }),
      effects: () => [{ type: 'SHOW_DICE_ROLLING' }],
    },
    ACTION_ESCAPE: {
      guard: (ctx) => !ctx.hud?.me?.submitted,
      reduce: (ctx) => ({
        ...ctx,
        phase: Phase.DICE_ROLLING,
        dice: { action: 'escape', value: null, cosmetic: false },
        escapePending: true,
      }),
      effects: () => [{ type: 'SHOW_DICE_ROLLING' }],
    },
    ACTION_USE_ITEM: {
      guard: (ctx, meta) => !ctx.hud?.me?.submitted && !!meta.itemId,
      reduce: (ctx, meta) => ({
        ...ctx,
        phase: Phase.DICE_ROLLING,
        dice: {
          action: 'use_item',
          value: null,
          cosmetic: false,
          itemId: meta.itemId,
          itemName: meta.itemName || '物品',
        },
        error: null,
      }),
      effects: () => [{ type: 'SHOW_DICE_ROLLING' }],
    },
    ACTION_USE_ZOO: {
      guard: (ctx) => {
        if (ctx.hud?.me?.submitted) return false;
        return ctx.hud?.allow_zoo !== false;
      },
      reduce: (ctx, meta) => ({
        ...ctx,
        phase: Phase.DICE_ROLLING,
        dice: { action: 'use_zoo', value: meta.dice, cosmetic: true },
        error: null,
      }),
      effects: () => [{ type: 'SHOW_DICE_ROLLING' }],
    },
    POLL_TICK: {
      reduce: (ctx, meta) => syncState(ctx, meta.snapshot).ctx,
      effects: (ctx, meta) => syncState(ctx, meta.snapshot).effects,
    },
  },

  [Phase.DICE_ROLLING]: {
    DICE_ANIMATION_DONE: {
      reduce: (ctx, meta) => ({
        ...ctx,
        phase: Phase.DICE_CONFIRM,
        dice: { ...ctx.dice, value: meta.dice ?? ctx.dice.value },
      }),
      effects: () => [{ type: 'SHOW_DICE_CONFIRM' }],
    },
    ACTION_ATTACK: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '擲骰中，請稍候…' }] },
    ACTION_DEFEND: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '擲骰中，請稍候…' }] },
    ACTION_USE_ITEM: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '擲骰中，請稍候…' }] },
    ACTION_USE_ZOO: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '擲骰中，請稍候…' }] },
    POLL_TICK: {
      reduce: (ctx, meta) => ({ ...syncState(ctx, meta.snapshot).ctx, phase: Phase.DICE_ROLLING }),
      effects: (ctx, meta) => {
        const r = syncState(ctx, meta.snapshot);
        return r.effects.map((e) => (e.type === 'UPDATE_HUD' ? { ...e, hpOnly: true } : e));
      },
    },
  },

  [Phase.DICE_CONFIRM]: {
    CONFIRM_DICE: {
      reduce: (ctx) => ({ ...ctx, phase: Phase.SUBMITTING, pollPaused: true }),
      effects: () => [{ type: 'HIDE_DICE' }, { type: 'SHOW_SUBMITTING' }],
    },
    ACTION_ATTACK: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '請先確認並結束本回合' }] },
    ACTION_DEFEND: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '請先確認並結束本回合' }] },
    ACTION_USE_ITEM: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '請先確認並結束本回合' }] },
    ACTION_USE_ZOO: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '請先確認並結束本回合' }] },
    POLL_TICK: {
      reduce: (ctx, meta) => ({ ...syncState(ctx, meta.snapshot).ctx, phase: Phase.DICE_CONFIRM }),
      effects: (ctx, meta) => syncState(ctx, meta.snapshot).effects.map((e) =>
        e.type === 'UPDATE_HUD' ? { ...e, hpOnly: true } : e,
      ),
    },
  },

  [Phase.SUBMITTING]: {
    SUBMIT_SUCCESS: {
      reduce: (ctx, meta) => {
        if (meta.escaped) {
          return {
            ...ctx,
            phase: Phase.ESCAPED,
            escapePending: false,
            pollPaused: true,
          };
        }
        if (meta.roundResolved === false) {
          return { ...ctx, phase: Phase.WAITING_FOR_PLAYERS, pollPaused: false };
        }
        if (meta.skipToVictory) {
          return {
            ...ctx,
            phase: Phase.VICTORY,
            settledRoundIndex: meta.settledRoundIndex ?? ctx.settledRoundIndex,
            pollPaused: true,
            pendingSettlement: null,
            pendingSettlementId: null,
            isKillingBlow: false,
          };
        }
        if (meta.skipModal) {
          return {
            ...ctx,
            phase: Phase.IDLE,
            settledRoundIndex: meta.settledRoundIndex ?? ctx.settledRoundIndex,
            pollPaused: false,
          };
        }
        return {
          ...ctx,
          phase: Phase.SETTLEMENT,
          pendingSettlement: meta.settlement,
          pendingSettlementId: meta.settlementId,
          isKillingBlow: !!meta.isKillingBlow,
          settledRoundIndex: meta.settledRoundIndex ?? ctx.settledRoundIndex,
          pollPaused: true,
        };
      },
      effects: (ctx, meta) => {
        if (meta.escaped) {
          return [
            { type: 'HIDE_SUBMITTING' },
            { type: 'SHOW_ESCAPED', data: meta.data },
            { type: 'STOP_POLL' },
          ];
        }
        if (meta.roundResolved === false) {
          return [{ type: 'HIDE_SUBMITTING' }, { type: 'UPDATE_HUD' }, { type: 'START_POLL' }];
        }
        if (meta.skipToVictory) {
          return terminalModalTeardownEffects([
            { type: 'HIDE_SUBMITTING' },
            { type: 'SHOW_VICTORY', data: meta.data },
            { type: 'STOP_POLL' },
          ]);
        }
        if (meta.skipModal) {
          return [{ type: 'HIDE_SUBMITTING' }, { type: 'START_POLL' }];
        }
        return [{ type: 'HIDE_SUBMITTING' }, { type: 'SHOW_SETTLEMENT', settlement: meta.settlement, killing: meta.isKillingBlow }];
      },
    },
    SUBMIT_ERROR: {
      reduce: (ctx, meta) => ({
        ...ctx,
        phase: Phase.IDLE,
        error: meta.error,
        pollPaused: false,
      }),
      effects: (_, meta) => [
        { type: 'HIDE_SUBMITTING' },
        { type: 'TOAST', message: meta.error || '提交失敗', level: 'error' },
        { type: 'START_POLL' },
      ],
    },
    ACTION_ATTACK: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '回合提交結算中，請稍候…' }] },
    POLL_TICK: {
      reduce: (ctx, meta) => {
        const synced = syncState(ctx, meta.snapshot);
        meta._submittingPollEffects = synced.effects;
        const keepSyncedPhase = synced.ctx.phase === Phase.SETTLEMENT
          || TERMINAL_PHASES.includes(synced.ctx.phase);
        return {
          ...synced.ctx,
          phase: keepSyncedPhase ? synced.ctx.phase : Phase.SUBMITTING,
        };
      },
      effects: (_, meta) => (meta._submittingPollEffects || []).map((e) =>
        e.type === 'UPDATE_HUD' ? { ...e, hpOnly: true } : e,
      ),
    },
  },

  [Phase.WAITING_FOR_PLAYERS]: {
    POLL_TICK: {
      reduce: (ctx, meta) => syncState(ctx, meta.snapshot).ctx,
      effects: (ctx, meta) => syncState(ctx, meta.snapshot).effects,
    },
    SUBMIT_SUCCESS: {
      reduce: (ctx, meta) => transition(ctx, 'SUBMIT_SUCCESS', meta).ctx,
      effects: (ctx, meta) => transition(
        { ...ctx, phase: Phase.WAITING_FOR_PLAYERS },
        'SUBMIT_SUCCESS',
        meta,
      ).effects,
    },
    ACTION_ATTACK: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '已提交，等待其他隊友…' }] },
  },

  [Phase.SETTLEMENT]: {
    ACK_SETTLEMENT: {
      reduce: (ctx, meta) => {
        const shown = new Set(ctx.shownSettlementIds);
        if (ctx.pendingSettlementId) shown.add(ctx.pendingSettlementId);
        const idx = ctx.settledRoundIndex >= 0 ? ctx.settledRoundIndex : deriveIdx(ctx);
        if (meta.killing || ctx.isKillingBlow) {
          return {
            ...ctx,
            phase: Phase.VICTORY,
            shownSettlementIds: shown,
            pendingSettlement: null,
            pendingSettlementId: null,
            settledRoundIndex: idx,
            pollPaused: true,
          };
        }
        return {
          ...ctx,
          phase: Phase.IDLE,
          shownSettlementIds: shown,
          pendingSettlement: null,
          pendingSettlementId: null,
          settledRoundIndex: idx,
          isKillingBlow: false,
          pollPaused: false,
        };
      },
      effects: (ctx, meta) => {
        if (meta.killing || ctx.isKillingBlow) {
          return [{ type: 'HIDE_SETTLEMENT' }, { type: 'SHOW_VICTORY' }, { type: 'STOP_POLL' }];
        }
        return [{ type: 'HIDE_SETTLEMENT' }, { type: 'START_POLL' }];
      },
    },
    ACTION_ATTACK: { reduce: (c) => c, effects: () => [{ type: 'TOAST', message: '請先關閉當前結算彈窗' }] },
    POLL_TICK: {
      reduce: (ctx, meta) => {
        const { ctx: synced } = syncState(ctx, meta.snapshot);
        if (SETTLEMENT_EXIT_PHASES.has(synced.phase)) {
          return synced;
        }
        return { ...synced, phase: Phase.SETTLEMENT };
      },
      effects: (ctx, meta) => {
        // reduce may have advanced phase; replay sync from SETTLEMENT for effect list
        const sourceCtx = SETTLEMENT_EXIT_PHASES.has(ctx.phase)
          ? { ...ctx, phase: Phase.SETTLEMENT }
          : ctx;
        const { ctx: synced, effects } = syncState(sourceCtx, meta.snapshot);
        if (SETTLEMENT_EXIT_PHASES.has(synced.phase)) {
          return terminalModalTeardownEffects(effects);
        }
        return effects.map((e) =>
          (e.type === 'UPDATE_HUD' ? { ...e, hpOnly: true } : e),
        );
      },
    },
    INV_RECOVERY: {
      reduce: (ctx) => ({ ...ctx, phase: Phase.IDLE, pollPaused: false }),
      effects: () => [
        { type: 'HIDE_ALL_MODALS' },
        { type: 'TOAST', message: '結算異常，已重置', level: 'warn' },
        { type: 'START_POLL' },
      ],
    },
  },

  [Phase.COMBAT_FAILED]: {
    COMBAT_RESET: {
      reduce: (ctx, meta) => createInitialContext(meta.combatId ?? ctx.combatId),
      effects: () => [
        { type: 'HIDE_ALL_MODALS' },
        { type: 'RENDER' },
        { type: 'START_POLL' },
      ],
    },
    EXIT_LOBBY: {
      reduce: (ctx) => ctx,
      effects: () => [{ type: 'NAVIGATE_LOBBY' }],
    },
    RESYNC_ONCE: {
      reduce: (ctx) => ctx,
      effects: () => [{ type: 'FETCH_ONCE' }],
    },
  },

  [Phase.VICTORY]: {
    EXIT_LOBBY: {
      reduce: (ctx) => ctx,
      effects: () => [{ type: 'NAVIGATE_LOBBY' }],
    },
  },

  [Phase.DEFEAT]: {
    EXIT_LOBBY: {
      reduce: (ctx) => ctx,
      effects: () => [{ type: 'NAVIGATE_LOBBY' }],
    },
  },

  [Phase.ESCAPED]: {
    EXIT_LOBBY: {
      reduce: (ctx) => ctx,
      effects: () => [{ type: 'NAVIGATE_LOBBY' }],
    },
  },
};

function deriveIdx(ctx) {
  const phase = parseInt(ctx.hud?.currentPhase, 10);
  return Number.isFinite(phase) ? Math.max(0, phase - 1) : ctx.settledRoundIndex + 1;
}

export function determineSettlementRoute(ctx, apiData, settlement, settlementId) {
  const apiIdx = parseInt(apiData.settled_round_index, 10);
  if (
    Number.isFinite(apiIdx)
    && ctx.settledRoundIndex >= 0
    && apiIdx < ctx.settledRoundIndex
  ) {
    return {
      roundResolved: true,
      skipModal: true,
      settledRoundIndex: ctx.settledRoundIndex,
    };
  }
  const isKillingBlow = apiData.outcome === 'victory'
    || apiData.winner === 'squad'
    || (apiData.enemy?.hp ?? 1) <= 0;
  if (ctx.shownSettlementIds.has(settlementId)) {
    if (isKillingBlow) {
      return {
        roundResolved: true,
        skipToVictory: true,
        settledRoundIndex: apiData.settled_round_index,
        data: apiData,
      };
    }
    return { roundResolved: true, skipModal: true, settledRoundIndex: apiData.settled_round_index };
  }
  return {
    roundResolved: true,
    settlement,
    settlementId,
    settledRoundIndex: apiData.settled_round_index,
    isKillingBlow,
  };
}