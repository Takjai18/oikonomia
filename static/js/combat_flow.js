/**
 * Oikonomia Combat Flow — FSM (PR #2 production · combat_flow_fsm_v2 · v18 invariant)
 * Single source of truth for combat UI phase; replaces legacy boolean guards.
 *
 * Product flow (solo):
 *   IDLE → DICE_ROLLING (~440ms) → DICE_CONFIRM → SUBMITTING → SETTLEMENT → IDLE
 *   Killing blow: SETTLEMENT (final round) → VICTORY (not skip settlement)
 */
(function (global) {
    'use strict';

    const CombatUiPhase = {
        IDLE: 'IDLE',
        DICE_ROLLING: 'DICE_ROLLING',
        DICE_CONFIRM: 'DICE_CONFIRM',
        SUBMITTING: 'SUBMITTING',
        SETTLEMENT: 'SETTLEMENT',
        VICTORY: 'VICTORY',
        DEFEAT: 'DEFEAT',
    };

    const PHASE_LABELS = {
        [CombatUiPhase.IDLE]: '等待行動',
        [CombatUiPhase.DICE_ROLLING]: '擲骰中',
        [CombatUiPhase.DICE_CONFIRM]: '確認行動',
        [CombatUiPhase.SUBMITTING]: '伺服器結算中',
        [CombatUiPhase.SETTLEMENT]: '傷害結算',
        [CombatUiPhase.VICTORY]: '戰鬥結束',
        [CombatUiPhase.DEFEAT]: '戰鬥失敗',
    };

    class CombatFlowManager {
        constructor(options = {}) {
            this.shadowMode = options.shadowMode === true;
            this.debug = !!options.debug;
            this.currentPhase = CombatUiPhase.IDLE;
            this.combatId = null;
            this.pendingSettlementData = null;
            this.pendingVictory = false;
            this.settlementRoundKey = null;
            this.finalizingEndgame = false;
        }

        log(...args) {
            if (this.debug) {
                console.log('[Combat FSM]', ...args);
            }
        }

        warn(...args) {
            console.warn('[Combat FSM]', ...args);
        }

        getPhase() {
            return this.currentPhase;
        }

        isSettlementPhase() {
            return this.currentPhase === CombatUiPhase.SETTLEMENT;
        }

        isSubmittingPhase() {
            return this.currentPhase === CombatUiPhase.SUBMITTING;
        }

        isEndgamePhase() {
            return this.currentPhase === CombatUiPhase.VICTORY
                || this.currentPhase === CombatUiPhase.DEFEAT;
        }

        isDiceBusyPhase() {
            return this.currentPhase === CombatUiPhase.DICE_ROLLING
                || this.currentPhase === CombatUiPhase.DICE_CONFIRM;
        }

        shouldBlockPoll() {
            return this.isSettlementPhase()
                || this.isSubmittingPhase()
                || this.isEndgamePhase()
                || this.finalizingEndgame;
        }

        shouldBlockPerformAction() {
            return this.isDiceBusyPhase()
                || this.isSubmittingPhase()
                || this.isSettlementPhase()
                || this.isEndgamePhase()
                || this.finalizingEndgame;
        }

        transitionTo(nextPhase, meta = {}) {
            const prev = this.currentPhase;
            if (prev === nextPhase && !meta.force) return false;
            this.currentPhase = nextPhase;
            this.log(`transition ${prev} → ${nextPhase}`, meta.reason || '', meta);
            return true;
        }

        resetForCombat(combatId) {
            this.combatId = combatId || null;
            this.pendingSettlementData = null;
            this.pendingVictory = false;
            this.settlementRoundKey = null;
            this.finalizingEndgame = false;
            this.transitionTo(CombatUiPhase.IDLE, { reason: 'combat_reset', force: true });
        }

        blockedMessage(actionName) {
            const phase = PHASE_LABELS[this.currentPhase] || this.currentPhase;
            if (this.currentPhase === CombatUiPhase.DICE_ROLLING) {
                return '系統擲骰中，請稍候…';
            }
            if (this.currentPhase === CombatUiPhase.DICE_CONFIRM) {
                return '請先完成當前行動';
            }
            if (this.currentPhase === CombatUiPhase.SUBMITTING) {
                return '回合提交結算中，請稍候…';
            }
            if (this.currentPhase === CombatUiPhase.SETTLEMENT) {
                return '請先關閉當前結算彈窗';
            }
            if (this.isEndgamePhase()) {
                return '戰鬥已結束';
            }
            return `目前為「${phase}」，無法${actionName || '執行此操作'}`;
        }

        canPerformAction(actionName) {
            if (this.currentPhase === CombatUiPhase.DICE_CONFIRM) {
                return { ok: false, message: this.blockedMessage(actionName) };
            }
            if (this.shouldBlockPerformAction()) {
                return { ok: false, message: this.blockedMessage(actionName) };
            }
            return { ok: true };
        }

        markSettlementShown(roundKey) {
            this.settlementRoundKey = roundKey || null;
        }

        clearSettlementRound() {
            this.settlementRoundKey = null;
        }

        hasShownSettlementFor(roundKey) {
            return !!(roundKey && this.settlementRoundKey === roundKey);
        }

        setFinalizingEndgame(active) {
            this.finalizingEndgame = !!active;
        }

        onActionStart(actionType, meta = {}) {
            this.transitionTo(CombatUiPhase.DICE_ROLLING, {
                reason: 'action_start',
                actionType,
                combatId: meta.combatId,
            });
            if (meta.combatId) this.combatId = meta.combatId;
        }

        onDiceAnimationComplete(meta = {}) {
            this.transitionTo(CombatUiPhase.DICE_CONFIRM, { reason: 'dice_animation_complete', ...meta });
        }

        onConfirmSubmit(meta = {}) {
            this.transitionTo(CombatUiPhase.SUBMITTING, { reason: 'confirm_submit', ...meta });
        }

        onSubmitResponse(data, meta = {}) {
            if (this.currentPhase !== CombatUiPhase.SUBMITTING
                && this.currentPhase !== CombatUiPhase.DICE_CONFIRM) {
                this.warn('submit_response_out_of_phase', this.currentPhase, meta);
            }

            const isDefeat = !!(data?.outcome === 'defeat' || data?.winner === 'enemy');
            const isVictory = !!(data?.outcome === 'victory' || data?.winner === 'squad'
                || (meta.isFinalHit && Number(meta.enemyHpAfter) <= 0));
            const hasSettlement = !!(data?.round_settlement || data?.round_resolved
                || data?.status === 'round_resolved');

            if ((isVictory || isDefeat) && hasSettlement && meta.productPath !== 'skip_settlement') {
                this.pendingVictory = isVictory;
                this.pendingSettlementData = data;
                this.transitionTo(CombatUiPhase.SETTLEMENT, { reason: 'endgame_settlement_first' });
                return CombatUiPhase.SETTLEMENT;
            }

            if (isDefeat) {
                this.pendingVictory = false;
                this.transitionTo(CombatUiPhase.DEFEAT, { reason: 'submit_defeat' });
                return CombatUiPhase.DEFEAT;
            }

            if (isVictory) {
                this.pendingVictory = false;
                this.transitionTo(CombatUiPhase.VICTORY, { reason: 'submit_victory' });
                return CombatUiPhase.VICTORY;
            }

            if (hasSettlement || data?.status === 'round_resolved') {
                this.pendingVictory = false;
                this.pendingSettlementData = data;
                this.transitionTo(CombatUiPhase.SETTLEMENT, { reason: 'round_resolved' });
                return CombatUiPhase.SETTLEMENT;
            }

            if (data?.status === 'waiting_for_teammates') {
                this.transitionTo(CombatUiPhase.SUBMITTING, { reason: 'waiting_for_teammates' });
                return CombatUiPhase.SUBMITTING;
            }

            this.transitionTo(CombatUiPhase.IDLE, { reason: 'submit_fallback' });
            return CombatUiPhase.IDLE;
        }

        onSettlementShown(data, meta = {}) {
            this.pendingSettlementData = data;
            if (meta.roundKey) this.markSettlementShown(meta.roundKey);
            this.transitionTo(CombatUiPhase.SETTLEMENT, { reason: 'settlement_modal_shown', ...meta });
        }

        onSettlementConfirm(meta = {}) {
            if (meta.recovery) {
                this.pendingVictory = false;
                this.pendingSettlementData = null;
                this.clearSettlementRound();
                this.transitionTo(CombatUiPhase.IDLE, { reason: 'submit_error_recovery', ...meta });
                return CombatUiPhase.IDLE;
            }
            this.clearSettlementRound();
            if (this.pendingVictory || meta.pendingVictory) {
                this.pendingVictory = false;
                this.pendingSettlementData = null;
                this.transitionTo(CombatUiPhase.VICTORY, { reason: 'settlement_confirm_to_victory', ...meta });
                return CombatUiPhase.VICTORY;
            }
            this.pendingSettlementData = null;
            this.transitionTo(CombatUiPhase.IDLE, { reason: 'settlement_confirm', ...meta });
            return CombatUiPhase.IDLE;
        }

        onVictoryShown(data, meta = {}) {
            this.pendingVictory = false;
            this.pendingSettlementData = null;
            this.clearSettlementRound();
            const outcome = meta.outcome || data?.outcome;
            const phase = outcome === 'defeat' ? CombatUiPhase.DEFEAT : CombatUiPhase.VICTORY;
            this.transitionTo(phase, { reason: 'endgame_screen', ...meta });
            return phase;
        }

        onCombatReset(meta = {}) {
            this.resetForCombat(meta.combatId || null);
        }
    }

    function ensureCombatFlow(options) {
        if (!global.__combatFlow) {
            global.__combatFlow = new CombatFlowManager(options);
        }
        return global.__combatFlow;
    }

    function getCombatFlow() {
        return ensureCombatFlow({ shadowMode: false });
    }

    function getCombatUiPhase() {
        return getCombatFlow().getPhase();
    }

    function combatFsmCanPerformAction(actionName) {
        return getCombatFlow().canPerformAction(actionName);
    }

    function combatFsmHook(method, ...args) {
        try {
            const flow = getCombatFlow();
            if (typeof flow[method] === 'function') {
                return flow[method](...args);
            }
        } catch (err) {
            console.warn('[Combat FSM] hook failed', method, err);
        }
        return undefined;
    }

    global.CombatUiPhase = CombatUiPhase;
    global.CombatFlowManager = CombatFlowManager;
    global.ensureCombatFlow = ensureCombatFlow;
    global.getCombatFlow = getCombatFlow;
    global.getCombatUiPhase = getCombatUiPhase;
    global.combatFsmCanPerformAction = combatFsmCanPerformAction;
    global.combatFsmHook = combatFsmHook;
})(typeof window !== 'undefined' ? window : globalThis);