# COMBAT_V2_R12_D_INV_MONOTONIC（局部審計 · 弱網狀態機與 INV-A～E）

> **目的**：審計 **前端權威狀態機** — `settlement_id` / `settled_round_index` 單調防護、`entrySyncPending` 進場吸收、INV-D 失敗搶占  
> **日期**：2026-07-01 · **commit**：`d41f23a`  
> **Baseline**：假設已讀 `combat_greenfield_final.md` §3 不變式表  
> **生成**：`python3 scripts/build_combat_v2_partial_bundles.py`

---

## 0. 給 Gemini 的指令

**焦點問題**（§22–§24 已修：teardown · `submittingActive` poll 降級 — 回歸 only）：
| INV | 審計問題 |
|-----|----------|
| INV-A | SETTLEMENT ⇔ modal 可見是否雙向成立？終端轉移是否清零 `pendingSettlement`？ |
| INV-B/C | 同一 `settlement_id` 是否只渲染一次？stale round 是否被拒？ |
| INV-D | HP≤0 / `dead_squad_names` 是否進 COMBAT_FAILED 並 `HIDE_SETTLEMENT`？ |
| INV-E | escape 失敗後攻擊方傷害是否仍結算？ |

**輸出**：【Critical】→【High/Medium】→【Low】→ 健康度 X/10

---

## 1. 狀態機核心

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
        if (ctx.hud?.allow_zoo === false) return false;
        return parseInt(ctx.hud?.me?.sanity ?? 0, 10) >= 70;
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
      reduce: (ctx, meta) => ({ ...syncState(ctx, meta.snapshot).ctx, phase: Phase.SUBMITTING }),
      effects: (ctx, meta) => syncState(ctx, meta.snapshot).effects.map((e) =>
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
  if (ctx.shownSettlementIds.has(settlementId)) {
    return { roundResolved: true, skipModal: true, settledRoundIndex: apiData.settled_round_index };
  }
  const isKillingBlow = apiData.outcome === 'victory'
    || apiData.winner === 'squad'
    || (apiData.enemy?.hp ?? 1) <= 0;
  return {
    roundResolved: true,
    settlement,
    settlementId,
    settledRoundIndex: apiData.settled_round_index,
    isKillingBlow,
  };
}


## 2. settlement 正規化

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

## 3. poll 與 entry sync

# static/js/combat/index.js (L481–L491)

  pollTick(snapshot) {
    if (!snapshot || snapshot.success === false) return;

    if (this.submittingActive) {
      if (this.debug) console.log('[CombatV2] poll muted during in-flight submit');
      if (snapshot.enemy || snapshot.my_state || snapshot.member_states) {
        this.ctx.hud = extractHud(snapshot);
        this.views.hud?.update(this.ctx, { hpOnly: true });
      }
      return;
    }
# static/js/combat/index.js (L313–L322)

  async onSubmitSuccess(data) {
    const deathCheck = handleAnyDeath(
      { ...this.ctx, hud: extractHud(data) },
      data.member_states,
    );
    if (deathCheck.ctx.phase === Phase.COMBAT_FAILED) {
      this.ctx = deathCheck.ctx;
      this.applyEffects(deathCheck.effects);
      return;
    }

## 4. 後端 settlement meta

# models/combat.py (L2474–L2489)

def _enrich_settlement_meta(payload, combat=None):
    """Additive COMBAT_V2 fields: stable settlement progress on every status snapshot."""
    combat_id = payload.get("combat_id") or (combat or {}).get("id")
    if combat_id is None:
        return payload
    current_phase = int(
        (combat or {}).get("current_phase")
        if combat is not None
        else payload.get("current_phase") or 0
    )
    settled_round_index = max(0, current_phase - 1)
    payload["settled_round_index"] = settled_round_index
    payload["settlement_id"] = f"{combat_id}:{settled_round_index}"
    return payload



## 5. 單元 + E2E 摘錄

/**
 * Combat V2 FSM unit tests (no DOM)
 * Run: npm run test:combat
 */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  Phase,
  TERMINAL_PHASES,
  createInitialContext,
  transition,
  canDispatch,
  handleAnyDeath,
  isMemberCollapsed,
  isEnemyDefeated,
  parseCombatHp,
  syncState,
  determineSettlementRoute,
} from '../static/js/combat/state_machine.js';
import { normalizeSettlement, deriveSettlementId } from '../static/js/combat/settlement.js';

describe('Combat V2 state machine', () => {
  it('TERMINAL_PHASES SSOT covers endgame absorbing phases', () => {
    assert.deepEqual(TERMINAL_PHASES, [
      Phase.COMBAT_FAILED,
      Phase.VICTORY,
      Phase.DEFEAT,
      Phase.ESCAPED,
    ]);
  });

  it('IDLE + ACTION_ATTACK → DICE_ROLLING', () => {
    const ctx = createInitialContext('c1');
    const { ctx: next } = transition(ctx, 'ACTION_ATTACK', { action: 'attack', dice: 3 });
    assert.equal(next.phase, Phase.DICE_ROLLING);
    assert.equal(next.dice.action, 'attack');
  });

  it('DICE_ROLLING + ACTION_ATTACK → toast (blocked)', () => {
    let ctx = createInitialContext('c1');
    ctx = transition(ctx, 'ACTION_ATTACK', { action: 'attack', dice: 3 }).ctx;
    const { ctx: same, effects } = transition(ctx, 'ACTION_ATTACK');
    assert.equal(same.phase, Phase.DICE_ROLLING);
    assert.equal(effects[0].type, 'TOAST');
  });

  it('full solo round: IDLE → … → SETTLEMENT → IDLE', () => {
    let ctx = createInitialContext(42);
    ctx = transition(ctx, 'ACTION_ATTACK', { action: 'attack', dice: 2 }).ctx;
    ctx = transition(ctx, 'DICE_ANIMATION_DONE', { dice: 2 }).ctx;
    assert.equal(ctx.phase, Phase.DICE_CONFIRM);
    ctx = transition(ctx, 'CONFIRM_DICE').ctx;
    assert.equal(ctx.phase, Phase.SUBMITTING);
    const settlement = { team_damage_dealt: 15, enemy_damage_dealt: 5, player_hits: [] };
    ctx = transition(ctx, 'SUBMIT_SUCCESS', {
      roundResolved: true,
      settlement,
      settlementId: '42:0',
      isKillingBlow: false,
    }).ctx;
    assert.equal(ctx.phase, Phase.SETTLEMENT);
    ctx = transition(ctx, 'ACK_SETTLEMENT', { killing: false }).ctx;
    assert.equal(ctx.phase, Phase.IDLE);
  });

  it('killing blow: SETTLEMENT → VICTORY', () => {
    let ctx = createInitialContext(1);
    ctx.phase = Phase.SETTLEMENT;
    ctx.isKillingBlow = true;
    ctx.pendingSettlementId = '1:5';
    const { ctx: next, effects } = transition(ctx, 'ACK_SETTLEMENT', { killing: true });
    assert.equal(next.phase, Phase.VICTORY);
    assert.ok(effects.some((e) => e.type === 'STOP_POLL'));
  });

  it('INV-D: any death → COMBAT_FAILED', () => {
    const ctx = createInitialContext(1);
    const { ctx: failed, effects } = handleAnyDeath(ctx, {
      p1: { display_name: 'Alice', hp: 0 },
      p2: { display_name: 'Bob', hp: 50 },
    });
    assert.equal(failed.phase, Phase.COMBAT_FAILED);
    assert.deepEqual(failed.failedMembers, ['Alice']);
    assert.ok(effects.some((e) => e.type === 'STOP_POLL'));
  });

  it('poll tick does not open settlement for non-victory sync', () => {
    let ctx = createInitialContext(1);
    ctx.phase = Phase.IDLE;
    const { ctx: next, effects } = syncState(ctx, {
      combat_id: 1,
      round_resolved: true,
      round_settlement: { team_damage_dealt: 10 },
      enemy: { hp: 200, max_hp: 220 },
      my_state: { hp: 80, max_hp: 100, submitted: false },
      member_states: { s1: { hp: 80, submitted: false } },
    });
    assert.notEqual(next.phase, Phase.SETTLEMENT);
    assert.ok(!effects.some((e) => e.type === 'SHOW_SETTLEMENT'));
  });

  it('G2: poll victory with unseen settlement → SETTLEMENT before VICTORY', () => {
    const ctx = { ...createInitialContext(1), phase: Phase.WAITING_FOR_PLAYERS };
    const { ctx: next, effects } = syncState(ctx, {
      outcome: 'victory',
      combat_id: 1,
      settled_round_index: 4,
      settlement_id: '1:4',
      round_settlement: { team_damage_dealt: 22, player_hits: [{ player: '隊友', damage: 22 }] },
      enemy: { hp: 0, max_hp: 220 },
      my_state: { hp: 80, submitted: true },
      member_states: { s1: { hp: 80, submitted: true } },
    });
    assert.equal(next.phase, Phase.SETTLEMENT);
    assert.equal(next.isKillingBlow, true);
    assert.ok(effects.some((e) => e.type === 'SHOW_SETTLEMENT' && e.killing === true));
  });

  it('submitted guard blocks ACTION_ATTACK', () => {
    const ctx = { ...createInitialContext(1), hud: { me: { submitted: true } } };
    assert.equal(canDispatch(ctx, 'ACTION_ATTACK'), false);
  });

  it('entry sync absorbs stable stale settlement on first poll (INV-C)', () => {
    const ctx = {
      ...createInitialContext(99),
      phase: Phase.IDLE,
      entrySyncPending: true,
    };
    const { ctx: next, effects } = syncState(ctx, {
      combat_id: 99,
      status: 'player_phase',
      current_phase: 3,
      settled_round_index: 2,
      settlement_id: '99:2',
      round_resolved: false,
      round_settlement: { team_damage_dealt: 40, enemy_damage_dealt: 0, player_hits: [] },
      enemy: { hp: 160, max_hp: 200 },
      my_state: { hp: 100, submitted: false },
      member_states: { s1: { hp: 100, submitted: false } },
    });
    assert.equal(next.phase, Phase.IDLE);
    assert.equal(next.settledRoundIndex, 2);
    assert.equal(next.entrySyncPending, false);
    assert.ok(next.shownSettlementIds.has('99:2'));
    assert.ok(!effects.some((e) => e.type === 'SHOW_SETTLEMENT'));
  });

  it('entry sync does not swallow modal when round_resolved on reconnect (INV-A)', () => {
    const ctx = {
      ...createInitialContext(99),
      phase: Phase.IDLE,
      entrySyncPending: true,
    };
    const { ctx: next } = syncState(ctx, {
      combat_id: 99,
      status: 'player_phase',
      current_phase: 2,
      settled_round_index: 1,
      settlement_id: '99:1',
      round_resolved: true,
      round_settlement: { team_damage_dealt: 40, enemy_damage_dealt: 0, player_hits: [] },
      enemy: { hp: 160, max_hp: 200 },
      my_state: { hp: 100, submitted: false },
      member_states: { s1: { hp: 100, submitted: false } },
    });
    assert.equal(next.entrySyncPending, false);
    assert.ok(!next.shownSettlementIds.has('99:1'));
  });

  it('R12-D: stale victory poll dropped by monotonic guard (INV-C)', () => {
    const ctx = {
      ...createInitialContext(999),
      phase: Phase.SETTLEMENT,
      settledRoundIndex: 2,
      pendingSettlementId: '999:2',
      isKillingBlow: true,
      hud: { enemy: { hp: 0, max_hp: 200 }, me: { hp: 80 }, members: {}, log: [] },
    };
    const { ctx: next, effects } = syncState(ctx, {
      outcome: 'victory',
      combat_id: 999,
      settled_round_index: 1,
      settlement_id: '999:1',
      round_settlement: { team_damage_dealt: 10 },
      enemy: { hp: 50, max_hp: 200 },
      my_state: { hp: 80 },
      member_states: {},
    });
    assert.equal(next.hud.enemy.hp, 0);
    assert.equal(effects.length, 0);
  });

  it('R12-D: defeat poll during SETTLEMENT clears pending settlement (INV-A)', () => {
    const ctx = {
      ...createInitialContext(888),
      phase: Phase.SETTLEMENT,
      settledRoundIndex: 1,
      pendingSettlement: { team_damage_dealt: 12 },
      pendingSettlementId: '888:1',
      hud: { enemy: { hp: 5, max_hp: 200 }, me: { hp: 80 }, members: {}, log: [] },
    };
    const { ctx: next, effects } = syncState(ctx, {
      outcome: 'defeat',
      winner: 'enemy',
      combat_id: 888,
      dead_squad_ids: ['s1'],
      dead_squad_names: ['Alice'],
      member_states: { s1: { display_name: 'Alice', hp: 50 } },
      enemy: { hp: 5, max_hp: 200 },
      my_state: { hp: 80 },
    });
    assert.equal(next.phase, Phase.COMBAT_FAILED);
    assert.equal(next.pendingSettlement, null);
    assert.equal(next.pendingSettlementId, null);
    assert.ok(effects.some((e) => e.type === 'HIDE_SETTLEMENT'));
  });

  it('R12-D: victory poll during SETTLEMENT does not skip to VICTORY', () => {
    const ctx = {
      ...createInitialContext(999),
      phase: Phase.SETTLEMENT,
      settledRoundIndex: 2,
      pendingSettlementId: '999:2',
      isKillingBlow: true,
      hud: { enemy: { hp: 0, max_hp: 200 }, me: { hp: 80 }, members: {}, log: [] },
    };
    const { ctx: next, effects } = syncState(ctx, {
      outcome: 'victory',
      combat_id: 999,
      settled_round_index: 2,
      settlement_id: '999:2',
      enemy: { hp: 0, max_hp: 200 },
      my_state: { hp: 80 },
      member_states: {},
    });
    assert.equal(next.phase, Phase.SETTLEMENT);
    assert.ok(!effects.some((e) => e.type === 'SHOW_VICTORY'));
  });

  it('P2-5: WAITING_FOR_PLAYERS poll round_resolved → SETTLEMENT', () => {
    const ctx = { ...createInitialContext(1012), phase: Phase.WAITING_FOR_PLAYERS };
    const { ctx: next, effects } = syncState(ctx, {
      combat_id: 1012,
      status: 'round_resolved',
      round_resolved: true,
      settlement_id: '1012:1',
      waiting_for_teammates: false,
      round_settlement: { team_damage_dealt: 40, enemy_damage_dealt: 0, player_hits: [] },
      enemy: { hp: 160, max_hp: 200 },
      my_state: { hp: 100, submitted: true },
      member_states: { s1: { hp: 100, submitted: true } },
    });
    assert.equal(next.phase, Phase.SETTLEMENT);
    assert.ok(effects.some((e) => e.type === 'SHOW_SETTLEMENT'));
  });

  it('monotonic guard skips stale settlement index', () => {
    const ctx = { ...createInitialContext(1), settledRoundIndex: 3, shownSettlementIds: new Set() };
    const route = determineSettlementRoute(
      ctx,
      { settled_round_index: 1, combat_id: 1 },
      { team_damage_dealt: 5 },
      '1:1',
    );
    assert.equal(route.skipModal, true);
    assert.equal(route.settledRoundIndex, 3);
  });

  it('SETTLEMENT poll defeat exits to DEFEAT with settlement teardown (INV-A)', () => {
    const ctx = {
      ...createInitialContext(1),
      phase: Phase.SETTLEMENT,
      pendingSettlementId: '1:0',
      pendingSettlement: { team_damage_dealt: 8 },
      isKillingBlow: false,
    };
    const { ctx: next, effects } = transition(ctx, 'POLL_TICK', {
      snapshot: {
        combat_id: 1,
        outcome: 'defeat',
        winner: 'enemy',
        my_state: { hp: 80 },
        member_states: { s1: { hp: 80 } },
      },
    });
    assert.equal(next.phase, Phase.DEFEAT);
    assert.equal(next.pendingSettlement, null);
    assert.ok(effects.some((e) => e.type === 'HIDE_SETTLEMENT'));
    assert.ok(effects.some((e) => e.type === 'SHOW_DEFEAT'));
  });

  it('near_death_until triggers isMemberCollapsed (INV-D)', () => {
    assert.equal(isMemberCollapsed({ hp: 50, near_death_until: '2099-01-01T00:00:00' }), true);
    const ctx = createInitialContext(1);
    const { ctx: failed } = handleAnyDeath(ctx, {
      A: { display_name: 'A', hp: 'n/a', near_death_until: '2099-01-01T00:00:00' },
    });
    assert.equal(failed.phase, Phase.COMBAT_FAILED);
  });

  it('defeat with dead_squad_names from DICE_CONFIRM clears modals (INV-D)', () => {
    const ctx = { ...createInitialContext(1), phase: Phase.DICE_CONFIRM };
    const { ctx: next, effects } = syncState(ctx, {
      combat_id: 1,
      outcome: 'defeat',
      winner: 'enemy',
      dead_squad_names: ['Alice'],
      member_states: { A: { display_name: 'Alice', hp: 50 } },
      my_state: { hp: 80, submitted: false },
    });
    assert.equal(next.phase, Phase.COMBAT_FAILED);
    assert.ok(effects.some((e) => e.type === 'HIDE_ALL_MODALS'));
    assert.ok(effects.some((e) => e.type === 'SHOW_FAILED'));
  });

  it('defeat payload with dead_squad_names → COMBAT_FAILED', () => {
    const ctx = createInitialContext(1);
    const { ctx: next, effects } = syncState(ctx, {
      combat_id: 1,
      outcome: 'defeat',
      winner: 'enemy',
      dead_squad_names: ['Alice'],
      dead_squad_ids: ['A'],
      member_states: { A: { display_name: 'Alice', hp: 0 } },
      my_state: { hp: 80, submitted: false },
    });
    assert.equal(next.phase, Phase.COMBAT_FAILED);
    assert.deepEqual(next.failedMembers, ['Alice']);
    assert.ok(effects.some((e) => e.type === 'SHOW_FAILED'));
  });

  it('IDLE + ACTION_USE_ZOO → DICE_ROLLING (P2-2)', () => {
    const ctx = {
      ...createInitialContext('c1'),
      hud: { me: { submitted: false, sanity: 80 }, allow_zoo: true },
    };
    const { ctx: next } = transition(ctx, 'ACTION_USE_ZOO', { action: 'use_zoo', dice: 2 });
    assert.equal(next.phase, Phase.DICE_ROLLING);
    assert.equal(next.dice.action, 'use_zoo');
  });
});

describe('Settlement normalization', () => {
  it('uses round_settlement when damage > 0', () => {
    const s = normalizeSettlement({
      round_settlement: { team_damage_dealt: 12, enemy_damage_dealt: 3, player_hits: [] },
      enemy: { hp: 208 },
    });
    assert.equal(s.team_damage_dealt, 12);
  });

  it('deriveSettlementId prefers API field', () => {
    assert.equal(deriveSettlementId({ settlement_id: '9:3', combat_id: 9 }), '9:3');
    assert.equal(deriveSettlementId({ combat_id: 9, settled_round_index: 2 }), '9:2');
  });

  it('malformed member hp does not trigger COMBAT_FAILED', () => {
    const ctx = createInitialContext(1);
    const { ctx: next } = handleAnyDeath(ctx, {
      A: { display_name: 'A', hp: 'n/a', max_hp: 100 },
    });
    assert.notEqual(next.phase, Phase.COMBAT_FAILED);
    assert.equal(isMemberCollapsed({ hp: 'n/a' }), false);
    assert.equal(isEnemyDefeated({ hp: undefined }), false);
    assert.equal(parseCombatHp(null, 80), 80);
    assert.equal(parseCombatHp('12', 80), 12);
  });

  it('falls back to authoritative round fields when settlement missing', () => {
    const s = normalizeSettlement({
      round_enemy_damage: 15,
      round_player_damage: 4,
      enemy: { hp: 85 },
    });
    assert.equal(s.team_damage_dealt, 15);
    assert.equal(s.enemy_damage_dealt, 4);
    assert.equal(s.enemy_hp_after, 85);
    assert.deepEqual(s.player_hits, []);
  });
});

# tests/combat_v2.spec.js (L1–L120)

/**
 * Combat V2 — Resilience & Phase 2 E2E (T8–T14)
 *
 * Requires: COMBAT_E2E=1 + COMBAT_V2=1 server (playwright.config.cjs webServer)
 * Run: npm run test:e2e:v2
 */
import { test, expect } from '@playwright/test';

const HARNESS_PATH = '/__e2e__/combat-v2';

async function waitForCombatV2(page) {
  await page.waitForFunction(
    () => window.combatV2?.isEnabled?.() && document.getElementById('combat-root-v2')?.__combat_app_instance__,
    null,
    { timeout: 15000 },
  );
}

async function startCombat(page, payload = {}) {
  await waitForCombatV2(page);
  await page.evaluate(async (data) => {
    document.getElementById('combat-root-v2')?.classList.remove('hidden');
    await window.combatV2.onCombatStarted({
      combat_id: data.combat_id ?? 999,
      status: 'player_phase',
      current_phase: data.current_phase ?? 2,
      enemy: data.enemy ?? { name: '速戰殘影', hp: 220, max_hp: 220 },
      my_state: data.my_state ?? {
        display_name: 'Henry',
        hp: 100,
        max_hp: 100,
        submitted: false,
      },
      member_states: data.member_states ?? {
        'PLAYER-75406': {
          display_name: 'Henry',
          hp: 100,
          max_hp: 100,
          submitted: false,
        },
      },
      ...data,
    });
  }, payload);
}

test.describe('Oikonomia Combat V2 — Resilience & Phase 2 E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(HARNESS_PATH);
  });

  test('T8: mixed escape failure then settlement modal (INV-E)', async ({ page }) => {
    await page.route('**/combat/status**', (route) => route.fulfill({ status: 204, body: '' }));

    await startCombat(page, { combat_id: 999 });

    await page.evaluate(() => {
      void window.combatV2.onSubmitSuccess({
        success: true,
        combat_id: 999,
        status: 'round_resolved',
        round_resolved: true,
        current_phase: 3,
        settled_round_index: 2,
        settlement_id: '999:2',
        my_squad_id: 'PLAYER-75406',
        enemy: { name: '速戰殘影', hp: 185, max_hp: 220 },
        my_state: { display_name: 'Henry', hp: 100, max_hp: 100, submitted: true },
        member_states: {
          'PLAYER-75406': {
            display_name: 'Henry',
            hp: 100,
            submitted: true,
            action_type: 'escape',
          },
          'TEAMMATE-02': {
            display_name: '小隊員',
            hp: 85,
            submitted: true,
            action_type: 'attack',
            dice_result: 2,
          },
        },
        round_settlement: {
          team_damage_dealt: 35,
          enemy_damage_dealt: 0,
          escape_triggered: true,
          escape_success: false,
          player_hits: [{ player: '小隊員', damage: 35, role: 'teammate' }],
          counter_hits: [],
          enemy_hp_after: 185,
        },
      });
    });

    const escapeOverlay = page.locator('#combat-v2-escape-result');
    await expect(escapeOverlay).toBeVisible();
    await expect(escapeOverlay).toContainText('逃跑失敗');

    await escapeOverlay.locator('#combat-v2-escape-continue').click();

    const settlementModal = page.locator('#combat-v2-round-settlement-modal');
    await expect(settlementModal).toBeVisible();
    await expect(page.locator('[data-testid="team-damage-dealt"]')).toContainText('隊伍造成 35 點傷害');
  });

  test('T9: preemptive interrupt hides dice modal on death (INV-D)', async ({ page }) => {
    await page.route('**/combat/status**', (route) => route.fulfill({ status: 204, body: '' }));

    await startCombat(page, {
      combat_id: 888,
      enemy: { name: '馬拉松首領', hp: 220, max_hp: 220 },
      member_states: {
        'PLAYER-75406': { display_name: 'Henry', hp: 100, max_hp: 100, submitted: false },
        p_npc_marah: { display_name: 'AI 主角 Marah', hp: 50, max_hp: 100, submitted: false, is_protagonist: true },
      },
    });

    await page.locator('#combat-v2-attack-btn').click();
    const diceModal = page.locator('#combat-v2-dice-modal');

---
*End of R12-D · 2026-07-01*
