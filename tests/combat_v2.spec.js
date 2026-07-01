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
    await expect(diceModal).toBeVisible();

    await page.evaluate(() => {
      window.combatV2.pollTick({
        success: true,
        combat_id: 888,
        status: 'player_phase',
        enemy: { name: '馬拉松首領', hp: 220, max_hp: 220 },
        my_state: { display_name: 'Henry', hp: 100, submitted: false },
        member_states: {
          'PLAYER-75406': { display_name: 'Henry', hp: 100, submitted: false },
          p_npc_marah: { display_name: 'AI 主角 Marah', hp: 0, submitted: false, is_protagonist: true },
        },
      });
    });

    await expect(diceModal).toBeHidden();
    const failedPanel = page.locator('#combat-v2-failed-panel');
    await expect(failedPanel).toBeVisible();
    await expect(failedPanel).toContainText('AI 主角 Marah');
    await expect(page.locator('#combat-v2-attack-btn')).toBeDisabled();
  });

  test('T10: visibilitychange triggers immediate sync and resets backoff', async ({ page }) => {
    let statusCalls = 0;

    await page.route('**/combat/status**', async (route) => {
      statusCalls += 1;
      if (statusCalls <= 3) {
        await route.fulfill({ status: 500, body: 'error' });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          combat_id: 777,
          status: 'player_phase',
          waiting_for_teammates: false,
          current_phase: 2,
          enemy: { name: '速戰殘影', hp: 10, max_hp: 220 },
          my_state: { display_name: 'Henry', hp: 100, max_hp: 100, submitted: true },
          member_states: {
            'PLAYER-75406': { display_name: 'Henry', hp: 100, submitted: true },
          },
        }),
      });
    });

    await startCombat(page, { combat_id: 777 });

    await page.evaluate(() => {
      const app = document.getElementById('combat-root-v2').__combat_app_instance__;
      app.dispatch('SUBMIT_SUCCESS', { roundResolved: false });
      app.poller.setPhase('WAITING_FOR_PLAYERS');
    });

    await page.waitForTimeout(4500);

    const backoffBefore = await page.evaluate(() => {
      return document.getElementById('combat-root-v2').__combat_app_instance__.poller.backoffMs;
    });
    expect(backoffBefore).toBeGreaterThan(0);

    const callsBeforeVisibility = statusCalls;

    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', { configurable: true, value: false });
      Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
      document.dispatchEvent(new Event('visibilitychange'));
    });

    await page.waitForFunction(
      () => {
        const hp = document.querySelector('[data-testid="enemy-hp"]')?.textContent || '';
        return hp.includes('10');
      },
      null,
      { timeout: 8000 },
    );

    expect(statusCalls).toBeGreaterThan(callsBeforeVisibility);

    const backoffAfter = await page.evaluate(() => {
      return document.getElementById('combat-root-v2').__combat_app_instance__.poller.backoffMs;
    });
    expect(backoffAfter).toBe(0);
  });

  test('T11: combat item pick, submit payload, and settlement (P2-1)', async ({ page }) => {
    await page.route('**/combat/status**', (route) => route.fulfill({ status: 204, body: '' }));

    await page.route('**/api/inventory**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          items: [
            {
              item_id: 105,
              name: '界線之鑰',
              description: '蘊含強大 Power 的戰鬥消耗品。',
              icon: '🗝️',
              has_ability: true,
              effect_type: 'power_up',
              effect_value: 15,
            },
          ],
        }),
      });
    });

    let submitPayload = null;
    await page.route('**/combat/submit_action**', async (route) => {
      submitPayload = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          combat_id: 999,
          status: 'round_resolved',
          round_resolved: true,
          current_phase: 3,
          settled_round_index: 2,
          settlement_id: '999:2',
          my_squad_id: 'PLAYER-75406',
          enemy: { name: '速戰殘影', hp: 120, max_hp: 220 },
          my_state: { display_name: 'Henry', hp: 100, max_hp: 100, submitted: true },
          member_states: {
            'PLAYER-75406': {
              display_name: 'Henry',
              hp: 100,
              submitted: true,
              action_type: 'use_item',
              item_id: 105,
            },
          },
          round_settlement: {
            team_damage_dealt: 45,
            enemy_damage_dealt: 0,
            player_hits: [{ player: 'Henry', damage: 45, role: 'self', action_type: 'use_item' }],
            counter_hits: [],
            enemy_hp_after: 120,
          },
        }),
      });
    });

    await startCombat(page, { combat_id: 999 });

    await page.locator('#combat-v2-item-btn').click();
    const itemModal = page.locator('#combat-v2-item-modal');
    await expect(itemModal).toBeVisible();
    await expect(itemModal).toContainText('界線之鑰');

    await itemModal.locator('button[data-item-id="105"]').click();
    await expect(itemModal).toBeHidden();

    const diceModal = page.locator('#combat-v2-dice-modal');
    await expect(diceModal).toBeVisible();
    await expect(page.locator('#combat-v2-dice-value')).toContainText('界線之鑰');

    await page.locator('#combat-v2-dice-confirm-btn').click();

    expect(submitPayload).not.toBeNull();
    expect(submitPayload.action_type).toBe('use_item');
    expect(submitPayload.item_id).toBe(105);
    expect(submitPayload.combat_id).toBe(999);

    const settlementModal = page.locator('#combat-v2-round-settlement-modal');
    await expect(settlementModal).toBeVisible();
    await expect(page.locator('[data-testid="team-damage-dealt"]')).toContainText('隊伍造成 45 點傷害');
  });

  test('T12: True Co-op parallel submission (WAITING_FOR_PLAYERS → settlement)', async ({ browser }) => {
    const leaderContext = await browser.newContext();
    const memberContext = await browser.newContext();
    const leaderPage = await leaderContext.newPage();
    const memberPage = await memberContext.newPage();

    const sharedPhaseActions = {};

    const buildSnapshot = (squadId, waiting) => {
      const submitted = !!sharedPhaseActions[squadId];
      const display = squadId === 'LEADER-1' ? '隊長' : '隊員';
      const base = {
        success: true,
        combat_id: 1012,
        status: waiting ? 'player_phase' : 'round_resolved',
        waiting_for_teammates: waiting,
        round_resolved: !waiting,
        current_phase: 2,
        settled_round_index: 1,
        settlement_id: waiting ? null : '1012:1',
        submitted_count: Object.keys(sharedPhaseActions).length,
        total_active: 2,
        enemy: { name: '真實連線影', hp: waiting ? 200 : 160, max_hp: 200 },
        member_states: {
          'LEADER-1': {
            display_name: '隊長',
            hp: 100,
            max_hp: 100,
            submitted: !!sharedPhaseActions['LEADER-1'],
            action_type: sharedPhaseActions['LEADER-1']?.action_type,
          },
          'MEMBER-2': {
            display_name: '隊員',
            hp: 100,
            max_hp: 100,
            submitted: !!sharedPhaseActions['MEMBER-2'],
            action_type: sharedPhaseActions['MEMBER-2']?.action_type,
          },
        },
      };
      base.my_state = {
        display_name: display,
        hp: 100,
        max_hp: 100,
        sanity: 80,
        submitted,
        action_type: sharedPhaseActions[squadId]?.action_type,
      };
      if (!waiting) {
        base.round_settlement = {
          team_damage_dealt: 40,
          enemy_damage_dealt: 0,
          player_hits: [
            { player: '隊長', damage: 20, role: 'self', action_type: 'attack' },
            { player: '隊員', damage: 20, role: 'teammate', action_type: 'defend' },
          ],
          counter_hits: [],
          enemy_hp_after: 160,
        };
      }
      return base;
    };

    const setupMocks = async (page, squadId) => {
      await page.route('**/combat/status**', (route) => {
        if (Object.keys(sharedPhaseActions).length === 0) {
          return route.fulfill({ status: 204, body: '' });
        }
        const waiting = Object.keys(sharedPhaseActions).length < 2;
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(buildSnapshot(squadId, waiting)),
        });
      });

      await page.route('**/combat/submit_action**', async (route) => {
        const body = route.request().postDataJSON();
        sharedPhaseActions[squadId] = { action_type: body.action_type };
        const waiting = Object.keys(sharedPhaseActions).length < 2;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(buildSnapshot(squadId, waiting)),
        });
      });
    };

    await leaderPage.addInitScript(() => { window.__OIKONOMIA_COMBAT_V2__ = true; });
    await memberPage.addInitScript(() => { window.__OIKONOMIA_COMBAT_V2__ = true; });
    await leaderPage.goto(HARNESS_PATH);
    await memberPage.goto(HARNESS_PATH);

    await setupMocks(leaderPage, 'LEADER-1');
    await setupMocks(memberPage, 'MEMBER-2');

    const baseInit = {
      combat_id: 1012,
      current_phase: 2,
      enemy: { name: '真實連線影', hp: 200, max_hp: 200 },
      member_states: {
        'LEADER-1': { display_name: '隊長', hp: 100, max_hp: 100, submitted: false },
        'MEMBER-2': { display_name: '隊員', hp: 100, max_hp: 100, submitted: false },
      },
    };

    await startCombat(leaderPage, {
      ...baseInit,
      my_state: { display_name: '隊長', hp: 100, max_hp: 100, sanity: 80, submitted: false },
    });
    await startCombat(memberPage, {
      ...baseInit,
      my_state: { display_name: '隊員', hp: 100, max_hp: 100, sanity: 80, submitted: false },
    });

    await leaderPage.locator('#combat-v2-attack-btn').click();
    await leaderPage.locator('#combat-v2-dice-confirm-btn').waitFor({ state: 'visible', timeout: 10000 });
    await leaderPage.locator('#combat-v2-dice-confirm-btn').click();

    await expect(leaderPage.locator('#combat-v2-team-status')).toContainText('✅ 已就緒');
    await expect(leaderPage.locator('#combat-v2-attack-btn')).toBeDisabled();

    await memberPage.locator('#combat-v2-defend-btn').click();
    await memberPage.locator('#combat-v2-dice-confirm-btn').waitFor({ state: 'visible' });
    await memberPage.locator('#combat-v2-dice-confirm-btn').click();

    const memberSettlement = memberPage.locator('#combat-v2-round-settlement-modal');
    await expect(memberSettlement).toBeVisible();
    await expect(memberPage.locator('[data-testid="team-damage-dealt"]')).toContainText('隊伍造成 40 點傷害');

    const resolvedSnapshot = buildSnapshot('LEADER-1', false);
    await leaderPage.evaluate((snap) => {
      document.getElementById('combat-root-v2').__combat_app_instance__.pollTick(snap);
    }, resolvedSnapshot);

    await expect(leaderPage.locator('#combat-v2-round-settlement-modal')).toBeVisible();
    await expect(leaderPage.locator('[data-testid="team-damage-dealt"]')).toContainText('隊伍造成 40 點傷害');

    await leaderContext.close();
    await memberContext.close();
  });

  test('T13: non-leader protagonist substitute blocked (P2-3)', async ({ page }) => {
    await page.route('**/combat/status**', (route) => route.fulfill({ status: 204, body: '' }));

    await startCombat(page, {
      combat_id: 1013,
      current_phase: 1,
      enemy: { name: '界線寄生影', hp: 100, max_hp: 100 },
      my_state: {
        display_name: '普通隊員 Henry',
        hp: 100,
        max_hp: 100,
        sanity: 80,
        submitted: false,
        is_team_leader: 0,
      },
      controllable_protagonist_id: 'protagonist:iggy:TEAM-01',
      member_states: {
        'LEADER-01': {
          display_name: '真・隊長',
          hp: 100,
          max_hp: 100,
          submitted: false,
          is_team_leader: 1,
        },
        'PLAYER-75406': {
          display_name: '普通隊員 Henry',
          hp: 100,
          max_hp: 100,
          submitted: false,
          is_team_leader: 0,
        },
      },
    });

    let submitCalled = false;
    await page.route('**/combat/submit_action**', async (route) => {
      submitCalled = true;
      await route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          error: '只有隊長特權才能啟動主角代打模式',
        }),
      });
    });

    await page.evaluate(() => {
      const app = document.getElementById('combat-root-v2').__combat_app_instance__;
      const toggle = document.getElementById('combat-v2-protagonist-toggle');
      if (toggle) toggle.checked = true;
      app.ctx.phase = 'DICE_CONFIRM';
      app.ctx.dice = { action: 'attack', value: 3, itemId: null };
      void app.confirmDice();
    });

    expect(submitCalled).toBe(false);

    const toast = page.locator('[data-testid="combat-toast"]');
    await expect(toast).toBeVisible();
    await expect(toast).toContainText('只有隊長特權才能啟動主角代打模式');
    await expect(page.locator('#combat-v2-attack-btn')).toBeEnabled();
  });

  test('T14: rogue player GM override endpoint hard-blocked', async ({ page }) => {
    await page.route('**/gm/api/override_trauma_ending', async (route) => {
      await route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          error: '拒絕存取：缺少 GM 權限憑證',
        }),
      });
    });

    const triggerHack = await page.evaluate(async (payload) => {
      try {
        const res = await fetch('/gm/api/override_trauma_ending', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        return { status: res.status, data: await res.json() };
      } catch (e) {
        return { status: 500, error: e.message };
      }
    }, { team_id: 'TEAM-01', target_ending_type: 'clear' });

    expect(triggerHack.status).toBe(403);
    expect(triggerHack.data.success).toBe(false);
  });
});