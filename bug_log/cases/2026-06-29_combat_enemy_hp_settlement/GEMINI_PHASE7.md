# GEMINI — Phase 7：FSM shadow 後實機回歸 + iPhone Safari 戰鬥版面（2026-06-30）

> **用途**：全文 Copy & Paste 到 Gemini chat（讀唔到 URL／Drive）。  
> **你的角色**：第三方 Architect — 審查 v16 熱修方向、設計 PR #2（FSM 主導）、產出 Playwright 規格與 iPhone 戰鬥 UX 方案。  
> **唔改 repo**；產出交 Grok Build 實作。

---

## 1. 一句話

**Henry（Chrome）在 `practice_iggy_04_marathon` 上：非 0 骰但結算顯示 0、非一擊必殺時唔出結算／敵 HP 動畫、勝利後仍再彈結算；iPhone Safari 進戰鬥預設睇唔到敵人面板。PR #1 FSM shadow 已上線但未解決 legacy guard 競態。**

---

## 2. 實機回報（Henry · 2026-06-30 · post-FSM PR#1）

| 欄位 | 值 |
|------|-----|
| **玩家** | Henry · `PLAYER-75406` |
| **瀏覽器** | Chrome macOS（主）；Safari 對照待測 |
| **Encounter** | `practice_iggy_04_marathon`（【練習】長戰巨影 · HP 220） |
| **PA baseline** | `4806357`（`combat_flow_fsm_v1` + `combat_flow_v15`） |
| **狀態** | **fix_in_progress** — v16 熱修 + PR #2 |

### 症狀矩陣

| ID | 情境 | 症狀 | 預期 |
|----|------|------|------|
| **F1** | 一般回合（非 OSK） | 擲骰 **非 0**；**傷害結算 modal 各欄顯示 0**（或根本 **唔彈** modal） | 結算數字與敵 HP 跌幅一致 |
| **F2** | 一般回合 | **無**傷害結算畫面；**無**敵人扣血動畫 | 每 `round_resolved` 必出結算 + HP 動畫 |
| **F3** | Killing blow / 勝利 | 結算 →「確定，查看勝利」→ 勝利畫面 → **再次彈出傷害結算** | 勝利後絕不二次結算 |
| **F4** | iPhone Safari 進入戰鬥 | 首屏見玩家 HP／行動；**敵人資料在視窗上方看不見** | 進戰鬥同時見敵我雙方關鍵資料 |

**備註**：F1／F2 可能同根因（`hasDamage` heuristic 為 false → 跳過 `showFullRoundSettlement`）；亦可能 F1 有 modal 但 `enrichRoundSettlementData`／`breakdown` 全 0。

---

## 3. 架構現況

| 層 | 檔案 | 狀態 |
|----|------|------|
| Legacy UI + 15+ boolean | `templates/index.html` ~L1580–4160 | **仍主導行為** |
| FSM shadow（PR #1） | `static/js/combat_flow.js` | 只 log + `reconcileLegacyState`，**唔 block** |
| 後端 | `routes/combat.py`, `models/combat.py` | 權威 `roll_combat_dice()`；`round_settlement` 由 server 組裝 |

### FSM 產品路徑（已同意）

```
IDLE → DICE_ROLLING (~440ms) → DICE_CONFIRM → SUBMITTING → SETTLEMENT → IDLE
Killing blow: SETTLEMENT（最後一回合）→ VICTORY（唔 skip settlement）
```

### Shadow mismatch 示例（請 Gemini 對照設計 PR #2）

FSM 認為應在 `SETTLEMENT`，但 legacy `combatAwaitingSettlementAck=false` 且 modal 不可見 → `handleCombatRoundResolved` 走了 `updateCombatUI` fallback。

---

## 4. 根因假設（請 Gemini 驗證／反駁）

### F1 — 結算顯示 0

```javascript
// enrichRoundSettlementData — 若 API 帶 round_settlement 但 team_damage_dealt=0
// 且 breakdown 存在，可能 early return 而不從 log 補建
function enrichRoundSettlementData(data) {
    let settlement = getRoundSettlement(data);
    if (settlementHasDamageNumbers(settlement)) {
        const bd = settlement.breakdown;
        const bdTotal = Number(bd?.dealt?.total) || 0;
        if (!bd || bdTotal > 0 || Number(settlement.team_damage_dealt) === 0) {
            return { ...data, round_settlement: settlement }; // ← 可能全 0 UI
        }
    }
    // buildClientRoundSettlement(sliceLogsForSettledRound(...)) 補建路徑
}
```

```javascript
// buildSettlementBreakdown — stale breakdown early return
if (settlement?.breakdown) {
    const bdTotal = Number(settlement.breakdown?.dealt?.total) || 0;
    if (teamDealt === 0 || bdTotal > 0) return settlement.breakdown; // teamDealt=0 → 全 0
}
```

**長戰污染**：`sliceLogsForSettledRound` 依 `summary`「受到共 N 點傷害」切回合；marathon 多回合 log 若 summary 缺失／順序錯，補建失敗。

### F2 — 唔出結算 modal

```javascript
function handleCombatRoundResolved(data) {
    // ...
    const hasDamage = Number(settlement.team_damage_dealt) > 0
        || (settled.log_entries || []).some(e => e?.type === 'damage');
    const mustShow = (settled.round_resolved || settled.status === 'round_resolved') && hasDamage;
    // hasDamage=false → 走 updateCombatUI，唔 call showFullRoundSettlement
}
```

```javascript
function showFullRoundSettlement(data) {
    if (phase > 0 && phase <= lastShownSettlementPhase && ...) return; // phase guard 擋重複
}
```

**假設**：`round_resolved=true` 但 `team_damage_dealt=0` 且 `log_entries` 未附帶（submit 回應精簡）→ **整輪跳過結算**。

### F3 — 勝利後再結算

```javascript
// finalizeCombatVictoryFromPayload → showCombatResult({ fromVictoryFinalize: true })
// keepVictoryLock 保留 combatVictorySequenceCompleteId
// 但 finally { victoryFinalizeInProgress = false } 後 in-flight poll 仍可能：
loadCombatStatus → handleCombatRoundResolved → showFullRoundSettlement
```

**缺口**：`showFullRoundSettlement` 未檢查 `combat-result-panel` 已顯示；poll 在 `stopCombatPolling` 與 lock 之間競態。

### F4 — iPhone 敵人不可見

- `#combat-screen`：`flex-col`，`#enemy-panel` 為 `order-1`（理論上置頂）
- 大廳 scroll 位置保留 → `showCombatScreen()` **無** `scrollTo`／`scrollIntoView`
- 首屏高度：返回鍵 + 標題 + timer + enemy 5 維 grid + player + 行動按鈕 → iPhone SE／mini 敵人可能在 fold 外

---

## 5. v16 熱修方向（Grok 擬實作 · 請 Gemini review）

| 項 | 改動 |
|----|------|
| F2 | `round_resolved` → **強制** `showFullRoundSettlement`（移除 `hasDamage` gate） |
| F1 | `enrichRoundSettlementData`：顯示總計為 0 時 **一律** 嘗試 `buildClientRoundSettlement`；`breakdown` 全 0 時丟棄重算 |
| F3 | `showFullRoundSettlement`／`loadCombatStatus`：若 `combat-result-panel` 可見或 `isCombatVictorySequenceComplete` → return + `stopCombatPolling` |
| F4 | `showCombatScreen()`：`window.scrollTo(0,0)` + `combat-screen.scrollIntoView`；`max-lg` sticky 精簡敵人 HP bar |

**Marker**：`combat_flow_v16`

---

## 6. 請 Gemini 交付（PR #2 + 測試 + 手機 UX）

### 6.1 PR #2：FSM 主導（取代 legacy boolean）

1. **單一 gate**：`CombatFlowManager.canPerformAction` / phase 決定可否攻擊、可否 poll 彈 modal
2. **移除或降級**：`combatAwaitingSettlementAck`、`settlementModalShown`、`lastShownSettlementPhase`…（列出完整刪除清單）
3. **`onSubmitResponse`**：legacy `handleCombatRoundResolved` 改為 **只聽 FSM** 進入 SETTLEMENT
4. **VICTORY 終態**：poll / submit / UI update 全部 no-op（除 dashboard refresh）
5. **Shadow → Production**：`shadowMode: false` 切換條件與 rollback

### 6.2 Playwright 規格（4+ asserts · marathon）

```javascript
// 請 Gemini 寫完整 spec 骨架
test('marathon round 1: non-zero dice → settlement modal with damage > 0', async ({ page }) => {
  // login PLAYER-75406 fixture
  // start practice_iggy_04_marathon
  // performAction attack → confirm dice
  // assert #combat-round-settlement-modal visible
  // assert #round-settlement-dealt-total not '0'
  // assert #enemy-hp-current decreased
});

test('marathon killing blow: settlement once then victory, no second modal', async ({ page }) => {
  // fast-forward or multi-round loop
  // after #combat-result-panel visible, wait 3s
  // assert #combat-round-settlement-modal hidden
});

test('iPhone viewport: enemy HP visible without scroll on combat entry', async ({ page }) => {
  // page.setViewportSize({ width: 390, height: 844 })
  // enter combat
  // assert #enemy-panel bounding box top >= 0 && bottom <= viewport height * 0.45
  // OR assert #enemy-hp-current is visible in viewport
});
```

### 6.3 iPhone Safari 戰鬥 UX（請出 wireframe 文字 + CSS 策略）

**需求**：進入戰鬥後 **無需捲動** 即可同時看到：
- 敵：名稱 + HP bar + 當前 HP 數字（5 維可折疊）
- 我：名稱 + HP + 至少一個行動入口

**請比較並推薦**：
- A) Sticky 精簡敵人列（48px）+ 可展開完整 panel
- B) 雙欄迷你卡（敵左我右，單行 HP）
- C) 進戰鬥強制 scroll top + 縮短 header（timer 移 inline）
- D) 組合方案

交付：`max-lg` Tailwind class 清單、`showCombatScreen` 行為、是否改 `order-*`。

---

## 7. 關鍵程式碼摘錄（供推理 · 行號為摘錄時近似）

### 7.1 `handleCombatRoundResolved`（結算 gate）

```javascript
function handleCombatRoundResolved(data) {
    if (isCombatVictorySequenceComplete(data?.combat_id)) return;
    data = enrichRoundSettlementData(data);
    // ...
    const settlement = getRoundSettlement(settled);
    const hasDamage = Number(settlement.team_damage_dealt) > 0
        || (settled.log_entries || []).some(e => e?.type === 'damage');
    const mustShow = (settled.round_resolved || settled.status === 'round_resolved') && hasDamage;
    if (hasSettlementPayload && (mustShow || hasDamage)) {
        showFullRoundSettlement(settled);
        return;
    }
    if (mustShow || shouldShowRoundSettlement(settled)) {
        showFullRoundSettlement(settled);
        return;
    }
    // FALLBACK: 無 modal
    updateCombatUI(settled, { damageDelay: 0 });
    syncEnemyHpDisplay(settled);
    startCombatPolling(COMBAT_POLL_INTERVAL_NORMAL);
}
```

### 7.2 `showFullRoundSettlement`（phase guard + victory lock）

```javascript
function showFullRoundSettlement(data) {
    const combatId = data?.combat_id || currentCombatId;
    if (isCombatVictorySequenceComplete(combatId)) return;
    data = enrichRoundSettlementData(data);
    const phase = Number(data?.current_phase) || 0;
    if (phase > 0 && phase <= lastShownSettlementPhase && ...) return;
    // ... showRoundSettlementModal(data)
}
```

### 7.3 `loadCombatStatus` poll 補結算

```javascript
if (data.round_settlement && !settlementModalShown && !combatAwaitingSettlementAck ...) {
    const pollHasDamage = Number(pollSettlement.team_damage_dealt) > 0
        || (pollSettled.log_entries || []).some(e => e?.type === 'damage');
    if (pollHasDamage) {
        handleCombatRoundResolved(pollSettled);
    }
}
```

### 7.4 FSM `onSubmitResponse`（shadow · 尚未驅動 UI）

```javascript
onSubmitResponse(data, meta = {}) {
    const isVictory = !!(data?.outcome === 'victory' || ...);
    const hasSettlement = !!(data?.round_settlement || data?.round_resolved);
    if (isVictory && hasSettlement) {
        this.transitionTo(CombatUiPhase.SETTLEMENT, { reason: 'killing_blow_settlement_first' });
        return CombatUiPhase.SETTLEMENT;
    }
    if (hasSettlement || data?.status === 'round_resolved') {
        this.transitionTo(CombatUiPhase.SETTLEMENT, { reason: 'round_resolved' });
        return CombatUiPhase.SETTLEMENT;
    }
}
```

### 7.5 戰鬥 DOM（手機）

```html
<div id="combat-screen" class="hidden max-w-md lg:max-w-6xl ...">
  <!-- header: title + phase-timer -->
  <div class="flex flex-col lg:grid lg:grid-cols-2">
    <div id="enemy-panel" class="order-1 lg:order-2 ...">...</div>
    <div id="player-panel" class="order-2 lg:order-1 ...">...</div>
  </div>
  <div id="combat-team-strip" class="mt-3 ...">...</div>
</div>
```

### 7.6 `showCombatScreen`（現無 scroll）

```javascript
async function showCombatScreen() {
    setVisible(document.getElementById('combat-lobby'), false);
    setVisible(document.getElementById('combat-screen'), true);
    // 無 window.scrollTo / scrollIntoView
}
```

---

## 8. 後端合約（唔改 breaking API）

- `POST /combat/submit_action` → `round_resolved` + `round_settlement` + `log_entries`（請確認 marathon 是否精簡 log）
- `GET /combat/status` → 同上；poll 路徑依賴 `round_settlement`
- 前端擲骰 cosmetic；server `roll_combat_dice()` 權威（Phase 2 可選傳 `dice_result`）

---

## 9. 驗證 checklist（部署後）

```bash
curl -s https://takjai.pythonanywhere.com/api/version | jq '.combat_flow_v16, .combat_flow_fsm_v1'
```

| 測試 | 帳號 | 瀏覽器 | 通過條件 |
|------|------|--------|----------|
| 長戰 R1 結算 | Henry | Chrome | 非 0 骰 → modal 傷害 > 0 → 敵 HP 動畫 |
| 長戰 R2+ | Henry | Chrome | 每回合必有結算 |
| Killing blow | Henry | Chrome | 結算 1 次 → 勝利 → 3s 內無第二次結算 |
| 首屏敵我 | Henry/Vini | iPhone Safari | 無捲動見敵 HP + 我行動區 |

---

## 10. 參考文件

- `REPORT.md` §21–§28
- `GEMINI_COMBAT_REWRITE.md`（Phase 6 完整重寫規格）
- `static/js/combat_flow.js`（PR #1）
- `encounters/practice_iggy_04_marathon.json`

---

*Phase 7 · 2026-06-30 · post `4806357`*