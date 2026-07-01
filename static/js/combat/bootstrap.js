/**
 * @file static/js/combat/bootstrap.js
 * @description COMBAT_V2 綠地架構啟動器 — 同步 skeleton 防止弱網重連競態
 */

import { CombatApp } from './index.js';

let app = null;
let enabled = null;
let initPromise = null;
let initComplete = false;

const handlers = {
  async onCombatStarted() {},
  async performAction() {},
  exitToLobby() {},
  summonGm() {},
  executeGmOverride() {},
  pollTick() {},
  onSubmitSuccess() {},
};

const root = () => document.getElementById('combat-root-v2');

async function detectCombatV2() {
  if (window.__OIKONOMIA_COMBAT_V2__ === true) return true;
  if (window.__OIKONOMIA_COMBAT_V2__ === false) return false;
  try {
    const res = await fetch('/api/version', {
      credentials: 'same-origin',
      headers: { 'Cache-Control': 'no-cache' },
    });
    const data = await res.json();
    return !!(data.combat_v2 || data.markers?.combat_v2);
  } catch (_) {
    return false;
  }
}

async function ensureInitialized() {
  if (!initPromise) {
    initPromise = init();
  }
  await initPromise;
}

function mountDisabledStub() {
  enabled = false;
  Object.assign(handlers, {
    async onCombatStarted() {},
    async performAction() {},
    exitToLobby() {},
    summonGm() {},
    executeGmOverride() {},
    pollTick() {},
    onSubmitSuccess() {},
  });
}

function bindLiveHandlers(combatRoot) {
  handlers.onCombatStarted = async (data) => {
    console.log(`[Greenfield] 接收到戰鬥啟動訊號，戰鬥ID: ${data.combat_id}`);
    if (data.combat_id) {
      sessionStorage.setItem('OIKONOMIA_COMBAT_V2_LOCK', 'true');
      sessionStorage.setItem('OIKONOMIA_ACTIVE_COMBAT_ID', String(data.combat_id));
    }
    combatRoot.classList.remove('hidden');
    await app.onCombatStarted(data);
  };
  handlers.performAction = (type) => app.performAction(type);
  handlers.exitToLobby = () => app.exitToLobby();
  handlers.summonGm = () => app.summonGm();
  handlers.executeGmOverride = (opts) => app.executeGmOverride(opts);
  handlers.pollTick = (data) => app.pollTick(data);
  handlers.onSubmitSuccess = (data) => app.onSubmitSuccess(data);
}

window.combatV2 = {
  isEnabled: () => enabled === true,
  isInitComplete: () => initComplete,
  async onCombatStarted(data) {
    await ensureInitialized();
    return handlers.onCombatStarted(data);
  },
  async performAction(type) {
    await ensureInitialized();
    return handlers.performAction(type);
  },
  exitToLobby: () => {
    void ensureInitialized().then(() => handlers.exitToLobby());
  },
  summonGm: () => {
    void ensureInitialized().then(() => handlers.summonGm());
  },
  executeGmOverride: (opts) => {
    void ensureInitialized().then(() => handlers.executeGmOverride(opts));
  },
  getState: () => app?.getState() ?? null,
  pollTick: (data) => {
    if (app) return handlers.pollTick(data);
    void ensureInitialized();
  },
  onSubmitSuccess: (data) => {
    if (app) return handlers.onSubmitSuccess(data);
    void ensureInitialized();
  },
  getApp: () => app,
  destroy: () => {
    if (app) {
      app.destroy();
      app = null;
    }
  },
};
window.CombatV2App = window.combatV2;

async function init() {
  try {
    enabled = await detectCombatV2();
    const combatRoot = root();

    if (!enabled || !combatRoot) {
      mountDisabledStub();
      return;
    }

    app = CombatApp.mount(combatRoot);
    bindLiveHandlers(combatRoot);

    console.log(
    '%c[Greenfield] Oikonomia Combat V2 核心已成功獨立掛載，Legacy 代碼完全清理完成。',
    'color: #10b981; font-weight: bold;',
    );
  } finally {
    initComplete = true;
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => { void ensureInitialized(); });
} else {
  void ensureInitialized();
}