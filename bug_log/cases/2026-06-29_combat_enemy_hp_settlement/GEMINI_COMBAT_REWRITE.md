# GEMINI — 戰鬥系統完整重寫規格（Phase 6 · 2026-06-30）

> **用途**：直接 Copy & Paste 全文到 Gemini chat。Gemini 讀唔到 Drive／GitHub URL。  
> **背景**：`templates/index.html` 戰鬥區塊經 v4–v15 補丁後仍不穩定；產品方要求 **重寫狀態機**，唔再疊加 guard。  
> **你的角色**：第三方 Architect — 產出**可交 Grok Build 實作**的設計文檔 + pseudo-code；唔改 repo。

---

## 1. 一句話

**用單一 Combat Flow State Machine 取代現有 15+ 個 boolean guard，保留擲骰動畫，確認後零體感 gap 接傷害結算，勝利後絕不二次結算。**

---

## 2. 現況與失敗模式（實機 · commit da97fda / v15 前）

| ID | 症狀 | 玩家 | 狀態 |
|----|------|------|------|
| F1 | 勝利後再次彈傷害結算 | Henry Chrome | v12–v15 仍間歇復發 |
| F2 | R2+ 按攻擊無反應 | Henry Chrome、Vini Safari | v14 部分改善 |
| F3 | 結算確認後擲骰 UI 殘留 | 全平台 | v14 引入（confirm 留 modal） |
| F4 | 擲骰→結算體感 delay | 全平台 | 用戶要動畫，但**唔要** confirm 後空白 |
| F5 | Safari 結算 0 傷害 | Vini | v13 log slice 待驗 |

**patch 疲勞**：現有符號包括 `combatAwaitingSettlementAck`、`settlementModalShown`、`victorySettlementAcknowledgedCombatId`、`combatVictorySequenceCompleteId`、`lastShownSettlementPhase`、`pendingVictoryAfterSettlement`… 互相競態，難以推理。

---

## 3. 產品需求（硬約束 · 不可違反）

### 3.1 UX 時序（單人 solo · 必須滿足）

```
[攻擊] → 擲骰動畫（保留，~300–450ms）→ 顯示骰值 +「確認並結束本回合」
       → 玩家按確認 → 即刻隱藏骰子 UI，顯示「結算中」（可覆蓋 RTT）
       → API 返回 → **無縫**彈出「傷害結算」modal（唔好退回空白主畫面）
       → 玩家按「確定」→ 解鎖下一回合 → R2 攻擊必須有反應（擲骰或 toast）
```

| 項目 | 要 | 唔要 |
|------|----|------|
| 擲骰動畫 | ✅ 保留（normal ≈ 8×55ms） | ❌ 完全移除動畫 |
| Confirm 後 | ✅ 即時 loading → 結算 modal | ❌ 主畫面空白等 poll |
| 人工 delay | ❌ 0ms（無 1500ms modal delay） | ❌ 恢復 COMBAT_SETTLEMENT_DELAY_MS |
| 勝利 flow | ✅ 結算 1 次 →「確定，查看勝利」→ 勝利畫面 | ❌ 勝利後再彈結算 |
| 被擋操作 | ✅ 必須 toast | ❌ silent return |
| 雙人隊 | 可 Phase 2；先保 solo | — |

### 3.2 後端合約（唔改 breaking API）

- `POST /combat/submit_action` → `round_resolved` 或 `outcome` 或 `waiting_for_teammates`
- `GET /combat/status` → `round_settlement`、`log_entries`、`my_state.submitted`、`current_phase`
- `models/combat.py`：`resolve_player_phase`、`_build_round_resolved_response`、`_attach_round_settlement`
- 前端擲骰 **cosmetic**；後端 `roll_combat_dice()` 為權威（可選 Phase 2：傳 `dice_result`）

### 3.3 CI 必須仍綠

- `scripts/pre_deploy_checks.sh`（192+ combat flow + audit）
- 新增：Playwright 或 contract test（見 §7）

---

## 4. 建議架構：Combat Flow State Machine

### 4.1 單一狀態變數（取代 10+ boolean）

```javascript
// 建議 enum（Gemini 請具體化）
const CombatUiPhase = {
    IDLE: 'idle',                    // player_phase，可選行動
    DICE_ROLLING: 'dice_rolling',    // 擲骰動畫中
    DICE_CONFIRM: 'dice_confirm',    // 等玩家按確認
    SUBMITTING: 'submitting',        // POST submit_action in-flight
    SETTLEMENT: 'settlement',        // 傷害結算 modal 顯示中
    VICTORY: 'victory',              // 勝利／失敗結局（終態）
    POLLING: 'polling',              // 僅 sync HP，唔彈 modal
};
let combatUiPhase = CombatUiPhase.IDLE;
let combatUiPhaseCombatId = null;   // 綁定 combat_id，新戰鬥 reset
```

**規則**：

1. 只有 `transitionTo(next, { reason, payload })` 可改 phase；內建非法轉移拒絕 + `console.warn`。
2. `VICTORY` 為 **absorbing state** — 禁止任何 modal／poll 觸發 settlement。
3. `SETTLEMENT` 期間 poll 只做 `syncHpOnly`，唔 call `showFullRoundSettlement`。
4. `SUBMITTING` 期間禁止 `performAction`（toast：結算中）。

### 4.2 建議檔案結構（Grok Build 實作）

```
templates/index.html          # 精簡：只留 DOM + 呼叫 CombatFlow
static/js/combat_flow.js      # 新建：state machine + 純函式（或 inline module）
services/combat_engine.py     # 已有：純計算，唔動
models/combat.py              # API 合約，最小改動
```

### 4.3 關鍵轉移表（Gemini 請補全 edge case）

| From | Event | To | UI |
|------|-------|-----|-----|
| IDLE | attack click | DICE_ROLLING | open modal, start animation |
| DICE_ROLLING | animation end | DICE_CONFIRM | show confirm btn |
| DICE_CONFIRM | confirm | SUBMITTING | hide dice, show「結算中」 |
| SUBMITTING | submit OK + round_resolved | SETTLEMENT | close action modal, open settlement |
| SUBMITTING | submit OK + outcome | VICTORY | skip settlement 或 先 SETTLEMENT 再 VICTORY（killing blow） |
| SETTLEMENT | confirm | IDLE | clear submitted locally, loadCombatStatus |
| SETTLEMENT | confirm + killing blow | VICTORY | mark endgame, show result |
| * | poll during VICTORY | VICTORY | no-op |

**Killing blow 產品決策（請 Gemini 二選一並說明）**：

- **A**：最後一擊仍顯示 settlement → 再 VICTORY（現行）
- **B**：最後一擊 skip settlement，直接 VICTORY

現行產品選 **A**，但 VICTORY 後 **絕不**再 SETTLEMENT。

---

## 5. 必須刪除／合併的舊邏輯（重寫時）

以下函式應由 state machine **取代**，唔好再疊 guard：

- `showFullRoundSettlement` / `finishCombatVictoryFromPayload` 內多層 early return
- `combatAwaitingSettlementAck` + `settlementTimerPending` 雙軌
- `victorySettlementAcknowledgedCombatId` vs `combatVictorySequenceCompleteId` 重疊
- `showCombatResult` 內 `resetCombatSessionState` 清空 guard 導致 poll 重入（F1 根因）
- `performAction` 靜默 return（已部分改 toast，應統一由 phase 判斷）

**保留可重用**：

- `buildSettlementBreakdown` / `enrichRoundSettlementData` / `sliceLogsForSettledRound`（v13）
- `services/combat_engine.py`
- `DICE_ROLL_PRESETS`（動畫保留）

---

## 6. 現行 Code 摘錄（供你審查 · 唔使讀全檔）

### 6.1 擲骰（要保留動畫）

```javascript
const DICE_ROLL_PRESETS = {
    fast: { intervalMs: 40, maxRolls: 6, pauseMs: 0 },
    normal: { intervalMs: 55, maxRolls: 8, pauseMs: 0 },
    slow: { intervalMs: 75, maxRolls: 10, pauseMs: 0 },
};
function rollDiceInModal() { /* setInterval until maxRolls, then revealConfirm */ }
function confirmRound() { showCombatSubmitLoadingShell(); submitAction(); }
```

### 6.2 結算鏈（問題集中區）

```javascript
async function submitAction() {
    const data = await fetch('/combat/submit_action', ...);
    if (data.round_resolved) handleCombatRoundResolved(data);
}
function handleCombatRoundResolved(data) {
    showFullRoundSettlement(settled);  // 多 guard
}
function continueCombatAfterRound() {
    hideRoundSettlementModal();
    clearLocalCombatSubmittedState();
    loadCombatStatus(false);
}
async function finalizeCombatVictoryFromPayload(data) {
    markCombatVictorySequenceComplete(combatId);
    showCombatResult(data, { fromVictoryFinalize: true });
}
function showCombatResult(data) {
    resetCombatSessionState({ keepVictoryLock });  // 曾清空 guard → F1
}
```

### 6.3 後端 round resolved

```python
def _build_round_resolved_response(combat, encounter, squad_id):
    payload["status"] = "round_resolved"
    payload["round_resolved"] = True
    _attach_round_settlement(payload, combat=combat)
    return payload
```

---

## 7. 測試合約（Gemini 請寫具體 assert）

### 7.1 Playwright E2E

1. **Dice animation preserved**：attack → `#modal-dice-value` 變化 ≥3 次 → confirm visible（<500ms 內出 confirm）
2. **Confirm → settlement**：click confirm → `#combat-round-settlement-modal` visible（允許 network RTT，但 action modal 骰子已 hidden）
3. **R2 unlock**：settlement confirm → `#attack-action-btn` enabled → click → `#modal-confirm-btn` visible
4. **Victory no duplicate**：killing blow flow → `#combat-result-panel` visible → `#combat-round-settlement-modal` **never** visible again（5s 內）

### 7.2 Contract（可併入 test_combat_flow.py）

- Solo 3-round `practice_iggy_03_boundary`：每 round `round_settlement.team_damage_dealt > 0`
- Killing blow：`outcome=victory` + `round_settlement` 存在 + `enemy_hp_after=0`

---

## 8. 請 Gemini 交付物

1. **狀態機圖**（Mermaid）：所有 state + transition + guard
2. **非法轉移表** + 對應 user-facing toast
3. **`combat_flow.js` 骨架**（`transitionTo`、`onSubmitSuccess`、`onSettlementConfirm`、`onPoll`）
4. **刪除清單**：現有 `index.html` 哪些函式可刪
5. **migration 計劃**：如何分 PR 落地（避免一次改 7000 行）
6. **F1/F2/F3 根因**對照表：你的設計點樣保證唔再發生
7. **風險**：雙人隊、主角操控、practice replay

---

## 9. 明確禁止

- ❌ 恢復 1500ms `COMBAT_SETTLEMENT_DELAY_MS`
- ❌ 完全移除擲骰動畫（產品要保留）
- ❌ 再新增第 16 個 boolean guard 而唔改狀態機
- ❌ 建議重寫後端 `resolve_player_phase` 除非有 failing test 證明必要

---

## 10. Copy-paste 開場白（精簡版）

```
你是 Oikonomia 戰鬥系統 Architect。請根據下文 GEMINI_COMBAT_REWRITE.md 產出：
1) Mermaid 狀態機 2) combat_flow.js 骨架 3) 遷移 PR 計劃 4) Playwright 測試清單。
基準 commit da97fda，solo 優先，保留擲骰動畫，confirm 後零體感 gap 接結算，勝利後絕不二次結算。
```

---

---

## 11. Gemini Architect 回覆摘要（2026-06-30 · 已收）

Gemini 交付 FSM + `combat_flow.js` 骨架 + 3 PR 計劃 + Playwright 清單。

**Grok Build 調整（與產品硬需求對齊）**：

| Gemini 提案 | 產品實際 | PR#1 實作 |
|-------------|----------|-----------|
| 動畫完**自動** submit | 動畫完 → **玩家確認** → submit | 加 `DICE_CONFIRM` 狀態 |
| killing blow 直達 VICTORY | **先 SETTLEMENT 再 VICTORY** | `onSubmitResponse` + `pendingVictory` |
| 砍掉 confirm 步驟 | 保留 confirm | 維持 `confirmRound` |

**PR #1 已落地**（shadow mode）：`static/js/combat_flow.js` + `combatFsmHook` in `index.html` · marker `combat_flow_fsm_v1`

**PR #2/#3**：待 shadow 對照無 mismatch 後執行。

*Grok Build 會根據你的設計實作 · 本檔可 commit 引用*