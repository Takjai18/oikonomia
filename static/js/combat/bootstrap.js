/**
 * @file static/js/combat/bootstrap.js
 * @description COMBAT_V2 綠地架構啟動器 - 已完全移除 Legacy 熔斷保險絲
 */

import { CombatApp } from './index.js';

let app = null;
let enabled = false;

/**
 * 安全檢測後端 Feature Flag 狀態
 */
async function detectCombatV2() {
  if (window.__OIKONOMIA_COMBAT_V2__ === true) return true;
  if (window.__OIKONOMIA_COMBAT_V2__ === false) return false;
  try {
    const res = await fetch('/api/version', { credentials: 'same-origin' });
    const data = await res.json();
    return !!(data.combat_v2 || data.markers?.combat_v2);
  } catch (_) {
    return false;
  }
}

function getRoot() {
  return document.getElementById('combat-root-v2');
}

/**
 * 綠地初始化生命週期
 */
async function init() {
  enabled = await detectCombatV2();
  const root = getRoot();

  if (!enabled || !root) {
    window.combatV2 = { isEnabled: () => false };
    return;
  }

  app = CombatApp.mount(root);

  window.combatV2 = {
    isEnabled: () => true,

    async onCombatStarted(data) {
      console.log(`[Greenfield] 接收到戰鬥啟動訊號，戰鬥ID: ${data.combat_id}`);
      if (data.combat_id) {
        sessionStorage.setItem('OIKONOMIA_COMBAT_V2_LOCK', 'true');
        sessionStorage.setItem('OIKONOMIA_ACTIVE_COMBAT_ID', String(data.combat_id));
      }
      root.classList.remove('hidden');
      await app.onCombatStarted(data);
    },

    async performAction(type) {
      return app.performAction(type);
    },

    exitToLobby: () => app.exitToLobby(),
    summonGm: () => app.summonGm(),
    executeGmOverride: (opts) => app.executeGmOverride(opts),
    getState: () => app.getState(),
    pollTick: (data) => app.pollTick(data),
    onSubmitSuccess: (data) => app.onSubmitSuccess(data),
    getApp: () => app,
    destroy: () => {
      if (app) {
        app.destroy();
        app = null;
      }
    },
  };

  window.CombatV2App = window.combatV2;

  console.log(
    '%c[Greenfield] Oikonomia Combat V2 核心已成功獨立掛載，Legacy 代碼完全清理完成。',
    'color: #10b981; font-weight: bold;',
  );
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}