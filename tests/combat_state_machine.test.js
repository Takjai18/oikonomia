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

  it('IDLE + ACTION_USE_ZOO allowed below sanity 70 (no bonus tier)', () => {
    const ctx = {
      ...createInitialContext('c1'),
      hud: { me: { submitted: false, sanity: 55 }, allow_zoo: true },
    };
    assert.equal(canDispatch(ctx, 'ACTION_USE_ZOO', { action: 'use_zoo', dice: 1 }), true);
    const { ctx: next } = transition(ctx, 'ACTION_USE_ZOO', { action: 'use_zoo', dice: 1 });
    assert.equal(next.phase, Phase.DICE_ROLLING);
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