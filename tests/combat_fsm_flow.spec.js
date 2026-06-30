/**
 * Oikonomia Combat FSM — Playwright contract tests (Gemini Phase 7)
 *
 * Run: npx playwright test tests/combat_fsm_flow.spec.js
 * Requires: npm install && npx playwright install chromium
 */
const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.OIKONOMIA_URL || 'http://127.0.0.1:5000';

test.describe('Oikonomia Combat FSM Engine Verification', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto(`${BASE_URL}/`);
    });

    test('Assert-1: dice rolling blocks repeat attack with toast', async ({ page }) => {
        test.skip(!process.env.COMBAT_E2E_AUTH, 'Set COMBAT_E2E_AUTH=1 with logged-in storage state');

        await page.click('[data-section="combat"]');
        await page.click('#attack-action-btn');

        await page.waitForTimeout(200);
        await page.click('#attack-action-btn');

        const toast = page.locator('.fixed.bottom-6');
        await expect(toast.first()).toBeVisible({ timeout: 3000 });
    });

    test('Assert-2: submit RTT shows settling hint and R2 attack unlocks', async ({ page }) => {
        test.skip(!process.env.COMBAT_E2E_AUTH, 'Set COMBAT_E2E_AUTH=1 with logged-in storage state');

        await page.route('**/combat/submit_action', async (route) => {
            await new Promise((r) => setTimeout(r, 1000));
            await route.continue();
        });

        await page.click('#attack-action-btn');
        await page.click('#modal-confirm-btn');

        await expect(page.locator('#combat-submit-hint')).toHaveText(/結算/, { timeout: 5000 });

        await page.click('#round-settlement-confirm-btn', { timeout: 8000 });
        await expect(page.locator('#attack-action-btn')).not.toBeDisabled({ timeout: 5000 });
    });

    test('Assert-3: victory poll does not reopen settlement modal', async ({ page }) => {
        test.skip(!process.env.COMBAT_E2E_MOCK, 'Set COMBAT_E2E_MOCK=1 for mocked status route');

        await page.route('**/combat/status**', async (route) => {
            await route.fulfill({
                json: {
                    success: true,
                    active: false,
                    status: 'ended',
                    outcome: 'victory',
                    winner: 'squad',
                    combat_id: 'mock-combat',
                },
            });
        });

        await page.click('#attack-action-btn');
        await page.click('#modal-confirm-btn');

        await expect(page.locator('#combat-result-panel')).toBeVisible({ timeout: 5000 });
        await expect(page.locator('#combat-round-settlement-modal')).toBeHidden();
    });

    test('Assert-4: iPhone viewport shows enemy and action buttons without scroll', async ({ page }) => {
        await page.setViewportSize({ width: 390, height: 844 });
        await page.click('[data-section="combat"]');

        const enemyHp = page.locator('#enemy-hp-current');
        const attackBtn = page.locator('#attack-action-btn');

        if (await enemyHp.isVisible()) {
            const enemyBox = await enemyHp.boundingBox();
            const attackBox = await attackBtn.boundingBox();
            expect(enemyBox).not.toBeNull();
            expect(attackBox).not.toBeNull();
            expect(enemyBox.y).toBeGreaterThanOrEqual(0);
            expect(attackBox.y + attackBox.height).toBeLessThanOrEqual(844);
        }
    });
});