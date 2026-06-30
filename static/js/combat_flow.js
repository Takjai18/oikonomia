/**
 * Oikonomia Combat Flow — FSM (PR #1 shadow mode)
 * Replaces v4–v15 boolean guards incrementally.
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
    };

    const PHASE_LABELS = {
        [CombatUiPhase.IDLE]: '等待行動',
        [CombatUiPhase.DICE_ROLLING]: '擲骰中',
        [CombatUiPhase.DICE_CONFIRM]: '確認行動',
        [CombatUiPhase.SUBMITTING]: '伺服器結算中',
        [CombatUiPhase.SETTLEMENT]: '傷害結算',
        [CombatUiPhase.VICTORY]: '戰鬥結束',
    };

    class CombatFlowManager {
        constructor(options = {}) {
            this.shadowMode = options.shadowMode !== false;
            this.debug = !!options.debug;
            this.currentPhase = CombatUiPhase.IDLE;
            this.combatId = null;
            this.pendingSettlementData = null;
            this.pendingVictory = false;
            this._lastShadowMismatchAt = 0;
        }

        log(...args) {
            if (this.debug || this.shadowMode) {
                console.log('[Combat FSM]', ...args);
            }
        }

        warn(...args) {
            console.warn('[Combat FSM]', ...args);
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
            this.transitionTo(CombatUiPhase.IDLE, { reason: 'combat_reset', force: true });
        }

        blockedMessage(actionName) {
            const phase = PHASE_LABELS[this.currentPhase] || this.currentPhase;
            if (this.currentPhase === CombatUiPhase.DICE_ROLLING) {
                return '擲骰中，請稍候';
            }
            if (this.currentPhase === CombatUiPhase.SUBMITTING) {
                return '戰鬥處理中，請稍候';
            }
            if (this.currentPhase === CombatUiPhase.SETTLEMENT) {
                return '請先確認傷害結算';
            }
            if (this.currentPhase === CombatUiPhase.VICTORY) {
                return '戰鬥已結束';
            }
            return `目前為「${phase}」，無法${actionName || '執行此操作'}`;
        }

        canPerformAction(actionName) {
            if (this.currentPhase === CombatUiPhase.VICTORY) {
                return { ok: false, message: this.blockedMessage(actionName) };
            }
            if (this.currentPhase === CombatUiPhase.IDLE) {
                return { ok: true };
            }
            return { ok: false, message: this.blockedMessage(actionName) };
        }

        /* Shadow hooks — called from templates/index.html (PR #1) */

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

            const isVictory = !!(data?.outcome === 'victory' || data?.winner === 'squad'
                || (meta.isFinalHit && Number(meta.enemyHpAfter) <= 0));
            const hasSettlement = !!(data?.round_settlement || data?.round_resolved
                || data?.status === 'round_resolved');

            if (isVictory && hasSettlement && meta.productPath !== 'skip_settlement') {
                this.pendingVictory = true;
                this.pendingSettlementData = data;
                this.transitionTo(CombatUiPhase.SETTLEMENT, { reason: 'killing_blow_settlement_first' });
                return CombatUiPhase.SETTLEMENT;
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
                this.transitionTo(CombatUiPhase.IDLE, { reason: 'waiting_for_teammates' });
                return CombatUiPhase.IDLE;
            }

            this.transitionTo(CombatUiPhase.IDLE, { reason: 'submit_fallback' });
            return CombatUiPhase.IDLE;
        }

        onSettlementShown(data, meta = {}) {
            this.pendingSettlementData = data;
            this.transitionTo(CombatUiPhase.SETTLEMENT, { reason: 'settlement_modal_shown', ...meta });
        }

        onSettlementConfirm(meta = {}) {
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
            this.transitionTo(CombatUiPhase.VICTORY, { reason: 'victory_screen', ...meta });
        }

        onCombatReset(meta = {}) {
            this.resetForCombat(meta.combatId || null);
        }

        /**
         * PR #1: compare FSM phase with legacy boolean guards (no behavior change).
         */
        reconcileLegacyState(legacy = {}) {
            const now = Date.now();
            if (now - this._lastShadowMismatchAt < 800) return;
            const issues = [];

            if (this.currentPhase === CombatUiPhase.IDLE && legacy.combatAwaitingSettlementAck) {
                issues.push('FSM=IDLE but combatAwaitingSettlementAck=true');
            }
            if (this.currentPhase === CombatUiPhase.SETTLEMENT && !legacy.settlementModalVisible
                && !legacy.combatAwaitingSettlementAck) {
                issues.push('FSM=SETTLEMENT but settlement modal/guard inactive');
            }
            if (this.currentPhase === CombatUiPhase.VICTORY && legacy.combatLive) {
                issues.push('FSM=VICTORY but combat still live');
            }
            if (this.currentPhase === CombatUiPhase.SUBMITTING && legacy.actionModalRolling) {
                issues.push('FSM=SUBMITTING but actionModalRolling=true');
            }
            if (this.currentPhase === CombatUiPhase.IDLE && legacy.victoryFinalizeInProgress) {
                issues.push('FSM=IDLE but victoryFinalizeInProgress=true');
            }

            if (issues.length) {
                this._lastShadowMismatchAt = now;
                this.warn('[Shadow mismatch]', issues.join('; '), {
                    fsm: this.currentPhase,
                    legacy,
                });
            }
        }
    }

    function ensureCombatFlow(options) {
        if (!global.__combatFlow) {
            global.__combatFlow = new CombatFlowManager(options);
        }
        return global.__combatFlow;
    }

    function combatFsmHook(method, ...args) {
        try {
            const flow = ensureCombatFlow({ shadowMode: true });
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
    global.combatFsmHook = combatFsmHook;
})(typeof window !== 'undefined' ? window : globalThis);