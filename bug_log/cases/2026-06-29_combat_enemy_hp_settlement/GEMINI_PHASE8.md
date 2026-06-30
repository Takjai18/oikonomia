# GEMINI — Phase 8：PR#2 FSM 實機回歸（Henry R2 卡住 · iPhone 無反應／無頭像）

> **用途**：全文 Copy & Paste 到 Gemini chat。  
> **你的角色**：第三方 Architect — 審查 v17 熱修、指出 PR#2 設計缺口、交付 Playwright 補強。  
> **Baseline**：`9e47dd7`（`combat_flow_fsm_v2` + `combat_mobile_hud_v1` + `combat_flow_v16`）

---

## 1. 一句話

**Henry（Chrome）長戰 R1 後 R2 擲骰畫面出現但無法進入傷害結算；iPhone Safari 戰鬥無頭像、按「開始戰鬥」無反應。懷疑 FSM `SETTLEMENT` 殘留 + `lastShownSettlementPhase` phase guard 擋住 R2 結算。**

---

## 2. 實機回報（2026-06-30 · post PR#2）

| ID | 玩家 | 環境 | Encounter | 症狀 |
|----|------|------|-----------|------|
| **G1** | Henry · `PLAYER-75406` | Chrome macOS | `practice_iggy_04_marathon` | **第一回合後**，再按攻擊 → 擲骰畫面出現 → **之後無法繼續**（無傷害結算、無扣血動畫） |
| **G2** | Henry／Vini | iPhone Safari | 同上／遭遇列表 | **`combat_mobile_hud_v1` 後玩家／敵人頭像消失**（產品要求保留小頭像） |
| **G3** | Henry／Vini | iPhone Safari | 遭遇列表 | 按「開始戰鬥」／Encounter **完全無反應**（無 toast、無 modal） |

### G1 細節（Henry）

1. R1：攻擊 → 擲骰 →（可能）確認 → 進入 R2 玩家回合  
2. R2：攻擊 → **擲骰 modal 出現** → 卡住（不確定 confirm 按鈕有否出現）  
3. **無**傷害結算 modal、**無**敵 HP 動畫  

### G2 細節（iPhone）

- `combat-enemy-avatar` 設了 `hidden lg:block`（僅桌面顯示）  
- `combat-player-avatar` 在 `hidden lg:block` 桌面區塊內，手機迷你卡無 avatar  

### G3 細節（iPhone）

- 可能：`startEncounter` → `showConfirmModal` Safari 觸控／`pointer-events`  
- 可能：FSM `SETTLEMENT`／`SUBMITTING` 殘留令 `performAction` silent（應有 toast 若 PR#2 正常）  
- 可能：舊 session／cache 載入舊 JS  

---

## 3. 根因假設（請 Gemini 驗證）

### G1-A：`showFullRoundSettlement` phase guard 擋 R2（**High**）

```javascript
// showFullRoundSettlement — PR#2 仍保留
if (phase > 0 && phase <= lastShownSettlementPhase
    && (!combatId || combatId === settlementCombatId || combatId === currentCombatId)) {
    return;  // ← R2 submit 若 current_phase 未大於 lastShownSettlementPhase → 唔彈結算
}
```

**鏈路**：

```
R1 submit → onSubmitResponse → SETTLEMENT → showFullRoundSettlement (lastShownSettlementPhase=2)
→ 用戶確認 → onSettlementConfirm → IDLE
R2 submit → onSubmitResponse → SETTLEMENT → showFullRoundSettlement
→ phase=2, lastShownSettlementPhase=2 → early return
→ FSM 停留 SETTLEMENT、modal 已關（submitAction 內 resetCombatDiceUi）
→ 無結算、無 HP 動畫
```

**修復方向（v17）**：`round_resolved` 時略過 phase guard，或改用 `settlementRoundKey`／`displayKey` 作唯一 idempotency。

### G1-B：`submitAction` 失敗後 FSM 停留 `SUBMITTING`（**Medium**）

```javascript
onConfirmSubmit() → SUBMITTING
// catch / error path：
restoreCombatConfirmBtn();
return;  // 無 combatFsmHook 回 IDLE
```

若 R1 網絡錯誤後用戶強制繼續，R2 `submitAction` 開頭擋 `isCombatFsmSubmitting()`。

### G1-C：擲骰後 confirm 按鈕未顯示（**Medium**）

- `onDiceAnimationComplete` → `DICE_CONFIRM`  
- `showCombatConfirmStep()` 依賴 `showCombatModalPanel('modal-confirm-btn', true)`  
- Safari：`display:none`／`hidden` 切換與 `flex` modal 疊加問題？  

### G2：手機 HUD 刻意隱藏頭像（**Confirmed regression**）

```html
<img id="combat-enemy-avatar" class="hidden lg:block ...">
<!-- player avatar 僅在 hidden lg:block 區塊 -->
```

**產品要求**：手機保留 **w-8～w-9** 小頭像（敵我並排 HUD 內）。

### G3：遭遇戰入口（**待查**）

```javascript
async function startEncounter(encounterId) {
    const agreed = await showConfirmModal({ ... });  // Safari 是否卡住？
    ...
    showCombatScreen();
    await loadCombatStatus(true);
}
```

---

## 4. v17 熱修方向（Grok 擬實作 · 請 review）

| 項 | 改動 |
|----|------|
| G1 | `showFullRoundSettlement`：`round_resolved` 時跳過 `phase <= lastShownSettlementPhase` guard |
| G1 | `submitAction` error／`!data.success`：`combatFsmHook` 回 `IDLE` 或 `DICE_CONFIRM` |
| G1 | `handleCombatRoundResolved`：若 FSM=`SETTLEMENT` 但 modal 不可見 → 強制 `showFullRoundSettlement` |
| G2 | 手機 HUD：敵我各加 `w-8 h-8` 頭像（唔用 `hidden lg:block` 藏晒） |
| G3 | `startEncounter`：confirm 取消時 toast；`combatFsmHook('onCombatReset')` on new combat |

**Marker**：`combat_flow_v17`

---

## 5. 關鍵程式摘錄

### 5.1 FSM `canPerformAction`（PR#2）

```javascript
canPerformAction(actionName) {
    if (this.currentPhase === CombatUiPhase.DICE_CONFIRM) {
        return { ok: false, message: '請先完成當前行動' };
    }
    if (this.shouldBlockPerformAction()) { ... }
    return { ok: true };
}
// SETTLEMENT 時 performAction → toast「請先關閉當前結算彈窗」
```

### 5.2 submit → 結算鏈

```javascript
async function submitAction() {
    if (isCombatFsmSubmitting()) { ... return; }
    // ...
    if (data.status === 'round_resolved' || data.round_resolved) {
        resetCombatDiceUi();
        combatFsmHook('onSubmitResponse', data, { ... });  // → SETTLEMENT
        handleCombatRoundResolved({ ...data, active: true });
    }
}
```

### 5.3 continueCombatAfterRound（R1→R2 解鎖）

```javascript
combatFsmHook('onSettlementConfirm', { combatId: currentCombatId });  // → IDLE
clearLocalCombatSubmittedState();
if (lastCombatStatus?.my_state) lastCombatStatus.my_state.submitted = false;
loadCombatStatus(false);
```

### 5.4 手機 HUD（現狀 · 無頭像）

```html
<img id="combat-enemy-avatar" class="hidden lg:block w-20 h-20 ...">
<div class="lg:hidden">
  <!-- 僅文字 HP，無 combat-player-avatar -->
</div>
```

---

## 6. 請 Gemini 交付

1. **確認 G1 根因**：phase guard vs FSM 殘留 vs confirm UI — 哪個為主因？  
2. **FSM 不變式**：`SETTLEMENT` phase 必須與 `#combat-round-settlement-modal` 可見性雙向綁定；不可見時必須 auto-transition `IDLE` 或重試 `showFullRoundSettlement`。  
3. **手機 HUD v2 wireframe**：雙欄迷你卡 **含** 敵我 w-8 頭像 + 行動區；估算首屏高度（iPhone SE 667px）。  
4. **Playwright Assert-5**：R1 結算確認 → R2 攻擊 → submit → `#combat-round-settlement-modal` visible。  
5. **Safari 專項**：`startEncounter` touch、`showConfirmModal` promise 解析。

---

## 7. 驗證 checklist

| 測試 | 通過條件 |
|------|----------|
| Henry Chrome 長戰 R2 | 擲骰 → 確認 → 結算 modal → 敵 HP 動畫 |
| iPhone Safari | 敵我小頭像可見 |
| iPhone 開始遭遇 | 按鈕有反應（modal 或 toast） |
| `/api/version` | `combat_flow_v17: true` |

---

## 8. 參考

- `GEMINI_PHASE7.md` · `REPORT.md` §29  
- `static/js/combat_flow.js` · `templates/index.html`  

---

*Phase 8 · 2026-06-30 · Henry + iPhone 回歸*