/**
 * Combat V2 — single entry CombatApp.mount()
 * Passive sync poll; settlement modal only via onSubmitSuccess.
 */

import { CombatApi, ResilientPollingManager } from './api_client.js';
import {
  Phase,
  createInitialContext,
  transition,
  canDispatch,
  blockedMessage,
  determineSettlementRoute,
  handleAnyDeath,
} from './state_machine.js';
import {
  normalizeSettlement,
  deriveSettlementId,
  extractHud,
} from './settlement.js';
import { showToast } from './toast.js';
import { renderAll } from './render.js';
import { DOM_IDS } from './selectors.js';
import { createHudView } from './views/hud_view.js';
import { createActionView } from './views/action_view.js';
import { createDiceModalView } from './views/dice_modal_view.js';
import { createSettlementView } from './views/settlement_view.js';
import { createSubmittingOverlay } from './views/submitting_overlay.js';
import { createEscapeResultView } from './views/escape_result_view.js';
import { createVictoryView } from './views/victory_view.js';
import { createItemSelectView } from './views/item_select_view.js';

export class CombatApp {
  /**
   * @param {HTMLElement} rootEl
   * @param {{ debug?: boolean }} options
   */
  static mount(rootEl, options = {}) {
    return new CombatApp(rootEl, options);
  }

  constructor(rootEl, options = {}) {
    this.rootEl = rootEl;
    this.debug = !!options.debug;
    this.ctx = createInitialContext();
    this.invRecoveryCount = 0;
    this.hasTriggeredTimeoutDefense = false;

    this.views = {
      hud: createHudView(rootEl),
      actions: createActionView(rootEl, {
        onAttack: () => this.performAction('attack'),
        onDefend: () => this.performAction('defend'),
        onEscape: () => this.performAction('escape'),
        onZoo: () => this.performAction('use_zoo'),
        onItemClick: () => this.openItemSelect(),
      }),
      dice: createDiceModalView(rootEl),
      settlement: createSettlementView(rootEl),
      submitting: createSubmittingOverlay(rootEl),
      escape: createEscapeResultView(rootEl),
      endgame: createVictoryView(rootEl),
      items: createItemSelectView(rootEl, (action, opts) => this.performAction(action, opts)),
    };

    this.views.dice.onConfirm(() => this.confirmDice());
    this.views.settlement.onAck(() => this.ackSettlement());

    this.poller = new ResilientPollingManager({
      onTick: (data) => this.pollTick(data),
      onError: (err) => {
        if (this.debug) console.warn('[CombatV2] poll error', err);
      },
    });

    renderAll(this.views, this.ctx);

    if (this.rootEl) {
      this.rootEl.__combat_app_instance__ = this;
    }
  }

  unmount() {
    this.destroy();
  }

  destroy() {
    try {
      if (this.poller) {
        this.poller.stop();
        if (typeof this.poller.destroy === 'function') {
          this.poller.destroy();
        }
      }
      this.hideAllModals();
      this.views?.endgame?.hideAll();
      this.views?.items?.hide();
      if (this.rootEl) {
        this.rootEl.classList.add('hidden');
      }
      this.hasTriggeredTimeoutDefense = false;
    } catch (err) {
      console.error('[CombatV2] destroy failed', err);
    }
  }

  getState() {
    return this.ctx;
  }

  async onCombatStarted(data) {
    this.dispatch('COMBAT_RESET', { combatId: data.combat_id });
    this.ctx.combatId = data.combat_id;
    this.ctx.settledRoundIndex = -1;
    this.ctx.shownSettlementIds.clear();
    this.ctx.entrySyncPending = true;
    this.hasTriggeredTimeoutDefense = false;
    this.invRecoveryCount = 0;

    if (data.combat_id) {
      sessionStorage.setItem('OIKONOMIA_ACTIVE_COMBAT_ID', String(data.combat_id));
    }

    this.hideAllModals();
    this.views.endgame.hideAll();

    const toggle = this.rootEl.querySelector(`#${DOM_IDS.PROTAGONIST_TOGGLE}`);
    if (toggle) toggle.checked = false;
    if (data.enemy || data.status) {
      this.ctx.hud = extractHud(data);
    }
    renderAll(this.views, this.ctx);
    this.poller.start(data.combat_id);
    try {
      const snapshot = await CombatApi.status(data.combat_id);
      this.pollTick(snapshot);
    } catch (_) { /* noop */ }
  }

  dispatch(event, meta = {}) {
    const { ctx, effects } = transition(this.ctx, event, meta);
    this.ctx = ctx;
    this.applyEffects(effects);
    return ctx;
  }

  openItemSelect() {
    if (['COMBAT_FAILED', 'VICTORY', 'DEFEAT', 'ESCAPED'].includes(this.ctx.phase)) {
      return;
    }
    if (this.ctx.phase !== Phase.IDLE || this.ctx.hud?.me?.submitted) {
      showToast(blockedMessage(this.ctx, '物品'));
      return;
    }
    this.views.items.show();
  }

  async performAction(actionType, options = {}) {
    const eventMap = {
      attack: 'ACTION_ATTACK',
      defend: 'ACTION_DEFEND',
      escape: 'ACTION_ESCAPE',
      use_item: 'ACTION_USE_ITEM',
      use_zoo: 'ACTION_USE_ZOO',
    };
    const event = eventMap[actionType] || 'ACTION_ATTACK';

    if (actionType === 'use_item') {
      if (!options.itemId) {
        showToast('請選擇要使用的物品');
        return;
      }
      if (!canDispatch(this.ctx, event, options)) {
        showToast(blockedMessage(this.ctx, actionType));
        return;
      }
      this.dispatch(event, {
        action: 'use_item',
        itemId: options.itemId,
        itemName: options.itemName,
      });
      this.dispatch('DICE_ANIMATION_DONE', { dice: null });
      return;
    }

    if (!canDispatch(this.ctx, event)) {
      showToast(blockedMessage(this.ctx, actionType));
      return;
    }

    if (actionType === 'escape') {
      this.dispatch(event, { action: 'escape' });
      this.views.dice.showRolling();
      await this.views.dice.animateCosmeticDice(null);
      this.dispatch('DICE_ANIMATION_DONE', { dice: null });
      return;
    }

    if (actionType === 'defend') {
      this.dispatch(event, { action: 'defend' });
      this.views.dice.showRolling();
      await this.views.dice.animateCosmeticDice(null);
      this.dispatch('DICE_ANIMATION_DONE', { dice: null });
      return;
    }

    if (actionType === 'use_zoo') {
      const cosmeticDice = Math.floor(Math.random() * 4);
      this.dispatch(event, { action: 'use_zoo', dice: cosmeticDice });
      this.views.dice.showRolling();
      await this.views.dice.animateCosmeticDice(cosmeticDice);
      this.dispatch('DICE_ANIMATION_DONE', { dice: cosmeticDice });
      return;
    }

    // 後端權威骰 0–3；cosmetic 動畫收束同範圍
    const cosmeticDice = Math.floor(Math.random() * 4);
    this.dispatch(event, { action: 'attack', dice: cosmeticDice });
    this.views.dice.showRolling();
    await this.views.dice.animateCosmeticDice(cosmeticDice);
    this.dispatch('DICE_ANIMATION_DONE', { dice: cosmeticDice });
  }

  async confirmDice() {
    if (this.ctx.phase !== Phase.DICE_CONFIRM) {
      showToast(blockedMessage(this.ctx, 'confirm'));
      return;
    }

    const isProtagonistToggled = !!this.rootEl.querySelector(
      `#${DOM_IDS.PROTAGONIST_TOGGLE}`,
    )?.checked;
    if (isProtagonistToggled && !this.ctx.hud?.me?.is_team_leader) {
      showToast('只有隊長特權才能啟動主角代打模式', 'error');
      const toggle = this.rootEl.querySelector(`#${DOM_IDS.PROTAGONIST_TOGGLE}`);
      if (toggle) toggle.checked = false;
      return;
    }

    this.dispatch('CONFIRM_DICE');
    this.poller.pause();

    try {
      const actionMap = {
        defend: 'defend',
        escape: 'escape',
        attack: 'attack',
        use_item: 'use_item',
        use_zoo: 'use_zoo',
      };
      const actionType = actionMap[this.ctx.dice.action] || 'attack';
      const asProtagonist = isProtagonistToggled
        && !!this.ctx.hud?.controllable_protagonist_id
        && !!this.ctx.hud?.me?.is_team_leader;
      const data = await CombatApi.submit({
        combatId: this.ctx.combatId,
        actionType,
        itemId: this.ctx.dice.itemId,
        asProtagonist,
      });
      await this.onSubmitSuccess(data);
    } catch (err) {
      this.dispatch('SUBMIT_ERROR', { error: err.message || '提交失敗' });
    } finally {
      if (!this.ctx.pollPaused) this.poller.resume();
    }
  }

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

    if (data.outcome === 'escaped' || data.winner === 'escaped') {
      this.ctx.hud = extractHud(data);
      this.dispatch('SUBMIT_SUCCESS', { escaped: true, data });
      return;
    }

    if (data.status === 'waiting_for_teammates' || data.waiting_for_teammates) {
      this.ctx.hud = extractHud(data);
      this.dispatch('SUBMIT_SUCCESS', { roundResolved: false });
      return;
    }

    const roundResolved = !!(data.round_resolved || data.status === 'round_resolved');
    if (!roundResolved && data.success && data.active) {
      this.ctx.hud = extractHud(data);
      this.dispatch('SUBMIT_SUCCESS', { roundResolved: false });
      return;
    }

    const settlement = normalizeSettlement(data);
    const settlementId = deriveSettlementId(data);

    if (!settlement && !data.outcome) {
      this.dispatch('SUBMIT_ERROR', { error: '結算資料缺失' });
      return;
    }

    if (settlement?.escape_triggered && !settlement?.escape_success) {
      await new Promise((resolve) => {
        this.views.escape.onContinue(resolve);
        this.views.escape.show({
          success: false,
          message: '逃跑失敗，將結算已提交行動',
        });
      });
    }

    const route = determineSettlementRoute(this.ctx, data, settlement, settlementId);
    this.ctx.hud = extractHud(data);
    const { ctx, effects } = transition(
      { ...this.ctx, phase: Phase.SUBMITTING },
      'SUBMIT_SUCCESS',
      route,
    );
    this.ctx = ctx;
    this.applyEffects(effects);
    this.enforceSettlementInvariant();
  }

  ackSettlement() {
    if (this.ctx.phase !== Phase.SETTLEMENT) {
      showToast('目前無待確認結算');
      return;
    }
    this.hasTriggeredTimeoutDefense = false;
    const killing = this.ctx.isKillingBlow;
    this.dispatch('ACK_SETTLEMENT', { killing });
  }

  triggerTimeoutAutomaticDefense() {
    if (this.hasTriggeredTimeoutDefense) return;

    const protectedPhases = [
      Phase.DICE_ROLLING,
      Phase.DICE_CONFIRM,
      Phase.SUBMITTING,
      Phase.SETTLEMENT,
      Phase.WAITING_FOR_PLAYERS,
    ];
    if (protectedPhases.includes(this.ctx.phase)) return;

    if (this.ctx.hud?.me?.submitted) {
      this.hasTriggeredTimeoutDefense = true;
      return;
    }

    this.hasTriggeredTimeoutDefense = true;
    showToast('操作超時！系統已自動為您執行「防禦」指令。', 'warn');
    void this.performActionDirectly('defend');
  }

  async performActionDirectly(actionType) {
    if (this.ctx.phase === Phase.SUBMITTING) return;

    if (this.ctx.phase === Phase.IDLE) {
      this.ctx = {
        ...this.ctx,
        phase: Phase.DICE_CONFIRM,
        dice: {
          action: actionType,
          value: null,
          itemId: null,
          cosmetic: false,
        },
      };
    } else if (this.ctx.phase !== Phase.DICE_CONFIRM) {
      return;
    }

    this.dispatch('CONFIRM_DICE');
    this.poller.pause();

    try {
      const data = await CombatApi.submit({
        combatId: this.ctx.combatId,
        actionType,
        itemId: null,
        asProtagonist: false,
      });
      await this.onSubmitSuccess(data);
    } catch (err) {
      this.hasTriggeredTimeoutDefense = false;
      this.dispatch('SUBMIT_ERROR', { error: err.message || '自動提交失敗' });
    } finally {
      if (!this.ctx.pollPaused) this.poller.resume();
    }
  }

  pollTick(snapshot) {
    if (!snapshot || snapshot.success === false) return;

    const deathCheck = handleAnyDeath(
      { ...this.ctx, hud: extractHud(snapshot) },
      snapshot.member_states,
    );
    if (deathCheck.ctx.phase === Phase.COMBAT_FAILED) {
      this.ctx = deathCheck.ctx;
      this.applyEffects(deathCheck.effects);
      return;
    }

    if (
      snapshot.status === 'player_phase'
      && snapshot.remaining_seconds === 0
      && !snapshot.my_state?.submitted
    ) {
      this.triggerTimeoutAutomaticDefense();
      if (this.hasTriggeredTimeoutDefense) return;
    }

    if (['VICTORY', 'DEFEAT', 'COMBAT_FAILED', 'ESCAPED'].includes(this.ctx.phase)) {
      return;
    }

    const { ctx, effects } = transition(this.ctx, 'POLL_TICK', { snapshot });
    this.ctx = ctx;
    if (this.ctx.entrySyncPending) {
      this.ctx.entrySyncPending = false;
    }
    this.poller.setPhase(ctx.phase);
    this.applyEffects(effects);

    if (this.ctx.phase === Phase.SETTLEMENT) {
      this.enforceSettlementInvariant();
    }
  }

  enforceSettlementInvariant() {
    const modalVisible = this.views.settlement.isVisible();
    const inSettlement = this.ctx.phase === Phase.SETTLEMENT;

    if (inSettlement && !modalVisible && this.ctx.pendingSettlement) {
      this.invRecoveryCount += 1;
      if (this.invRecoveryCount <= 2) {
        this.views.settlement.show(
          this.ctx.pendingSettlement,
          this.ctx,
          { killing: this.ctx.isKillingBlow },
        );
        return;
      }
      this.dispatch('INV_RECOVERY');
      this.invRecoveryCount = 0;
      return;
    }

    if (!inSettlement && modalVisible) {
      this.views.settlement.hide();
    }

    if (inSettlement && modalVisible) {
      this.invRecoveryCount = 0;
    }
  }

  hideAllModals() {
    this.views.dice.hide();
    this.views.settlement.hide();
    this.views.submitting.hide();
    this.views.escape.hide();
    this.views.items?.hide();
  }

  applyEffects(effects) {
    for (const fx of effects || []) {
      switch (fx.type) {
        case 'TOAST':
          showToast(fx.message, fx.level || 'info');
          break;
        case 'SHOW_DICE_ROLLING':
          this.views.dice.showRolling();
          break;
        case 'SHOW_DICE_CONFIRM':
          this.views.dice.showConfirm(this.ctx.dice.value, {
            isDefend: this.ctx.dice.action === 'defend',
            isEscape: this.ctx.dice.action === 'escape',
            isItem: this.ctx.dice.action === 'use_item',
            isZoo: this.ctx.dice.action === 'use_zoo',
            itemName: this.ctx.dice.itemName,
          });
          break;
        case 'HIDE_DICE':
          this.views.dice.hide();
          break;
        case 'SHOW_SUBMITTING':
          this.views.submitting.show();
          break;
        case 'HIDE_SUBMITTING':
          this.views.submitting.hide();
          break;
        case 'SHOW_SETTLEMENT':
          this.views.settlement.show(fx.settlement, this.ctx, { killing: fx.killing });
          break;
        case 'HIDE_SETTLEMENT':
          this.views.settlement.hide();
          break;
        case 'SHOW_VICTORY':
          this.views.endgame.showVictory(fx.data || this.ctx.hud);
          break;
        case 'SHOW_DEFEAT':
          this.views.endgame.showDefeat(fx.data);
          break;
        case 'SHOW_FAILED':
          this.views.endgame.showFailed(fx.members);
          break;
        case 'SHOW_ESCAPED':
          this.views.escape.onContinue(() => this.exitToLobby());
          this.views.escape.show({
            success: true,
            message: fx.data?.narrative || '全隊已脫離戰鬥',
          });
          break;
        case 'HIDE_ALL_MODALS':
          this.hideAllModals();
          this.views.endgame.hideAll();
          break;
        case 'UPDATE_HUD':
          renderAll(this.views, this.ctx, { hpOnly: fx.hpOnly });
          break;
        case 'RENDER':
          renderAll(this.views, this.ctx);
          break;
        case 'START_POLL':
          if (this.ctx.combatId) {
            this.poller.start(this.ctx.combatId);
          }
          break;
        case 'STOP_POLL':
          this.poller.stop();
          break;
        case 'NAVIGATE_LOBBY':
          this.exitToLobby();
          break;
        case 'FETCH_ONCE':
          if (this.ctx.combatId) {
            CombatApi.status(this.ctx.combatId).then((d) => this.pollTick(d)).catch(() => {});
          }
          break;
        default:
          break;
      }
    }
    renderAll(this.views, this.ctx);
  }

  exitToLobby() {
    if (typeof window.exitCombatScreen === 'function') {
      showToast('已安全退出戰場', 'info');
      window.exitCombatScreen({ fromV2: true });
      return;
    }

    sessionStorage.removeItem('OIKONOMIA_ACTIVE_COMBAT_ID');
    this.destroy();

    if (window.AppRouter && typeof window.AppRouter.navigateTo === 'function') {
      window.AppRouter.navigateTo('dashboard');
    } else {
      const lobby = document.getElementById('combat-lobby');
      if (lobby) lobby.classList.remove('hidden');
    }

    showToast('已安全退出戰場', 'info');
  }

  async summonGm() {
    if (!this.ctx.combatId) {
      showToast('無有效戰鬥編號', 'error');
      return;
    }
    try {
      const data = await CombatApi.summonGm(this.ctx.combatId);
      if (data.success) {
        showToast(data.message || '已通知 GM 工作人員', 'info');
      } else {
        showToast(data.error || '發送失敗', 'error');
      }
    } catch (_) {
      showToast('GM 通訊失敗，請聯繫現場工作人員', 'error');
    }
  }

  /** P2 Backlog: GM 特權遠端數據同步重置核心 */
  async executeGmOverride(opts) {
    try {
      showToast('正在發射特權變更指令…', 'info');
      const data = await CombatApi.overrideTraumaEnding(opts);
      if (data.success) {
        showToast(data.message || '特權歷史重組成功！', 'info');

        if (opts.targetEndingType === 'clear') {
          this.dispatch('COMBAT_RESET', { combatId: this.ctx.combatId });
        } else if (this.ctx.combatId) {
          const snapshot = await CombatApi.status(this.ctx.combatId);
          this.pollTick(snapshot);
        }
      } else {
        showToast(data.error || '指令被後端網關拒絕', 'error');
      }
    } catch (err) {
      showToast(err.message || 'GM 特權通訊失敗', 'error');
    }
  }
}

export { Phase };