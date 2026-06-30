# GEMINI — 戰鬥系統從零重寫（Greenfield · 2026-06-30）

> **用途**：**全文 Copy & Paste** 到 Gemini chat（讀唔到 URL／Drive／GitHub）。  
> **指令**：唔好再建議 patch `templates/index.html` 戰鬥區塊。請 **從 0 設計全新前端戰鬥子系統**，交 Grok Build 可直接實作嘅完整規格。  
> **你的角色**：首席 Architect — 只產出設計文檔、檔案結構、狀態機、API 合約、測試、遷移計劃；**唔改 repo**。

---

## 0. 給 Gemini 的明確指令（請先讀）

我哋已經試過 **v4→v18** 補丁、**FSM shadow（PR#1）**、**FSM production（PR#2）**、`enforceSettlementInvariant`、`settlementRoundKey logR`、手機 HUD v1/v2——**實機仍然大量 bug**。

**請停止**：
- 喺現有 `templates/index.html`（~7600 行）上再加 guard／hook
- 用「最小 diff」「熱修」修補 `handleCombatRoundResolved` / `showFullRoundSettlement` / `loadCombatStatus` 競態

**請改為**：
- **刪除並重寫**整個前端戰鬥 UI 層（建議獨立 ES module，唔再塞入 index.html 巨型 `<script>`）
- **單一狀態機** 驅動所有 UI；poll 只係「資料同步」，**唔得**觸發 modal
- 交付 **完整檔案清單 + 每檔職責 + 狀態轉移表 + 錯誤處理 + Playwright 規格 + 分 PR 遷移 DAG**

---

## 1. 專案與產品背景

**Oikonomia** — 網頁 RPG，戰鬥為核心 loop。  
**技術棧**：Flask + SQLite + Jinja `templates/index.html` + Tailwind + 原生 JS（無 React）。  
**部署**：PythonAnywhere · 測試帳號 **Henry** `PLAYER-75406` · 標準回歸 encounter **`practice_iggy_04_marathon`**（敵 HP 220，專測多回合）。

---

## 2. 補丁疲勞：已失敗嘅一切（請當反面教材）

### 2.1 版本線（全部未能穩定上實機）

| 版本 | 宣稱修復 | 實機結果 |
|------|----------|----------|
| v4–v11 | instant settlement、delay 移除 | 仍有 lag、結算不穩 |
| v12–v15 | victory lock、enrich settlement、dice 動畫 | 勝利後再結算、0 傷害 |
| FSM PR#1 | shadow `combat_flow.js` | legacy boolean 仍主導 |
| FSM PR#2 | 移除 boolean、FSM SSOT | R2 卡死、SETTLEMENT 幽靈態 |
| v16–v18 | phase guard、logR key、invariant | **Henry 回報仍然好多 bug** |

### 2.2 累積症狀清單（必須在新系統逐條杜絕）

| ID | 症狀 | 平台 |
|----|------|------|
| B1 | 擲骰非 0，結算顯示 **0 傷害** | Safari / Chrome |
| B2 | 非一擊必殺：**無**結算 modal、**無**敵 HP 動畫 | Chrome |
| B3 | **R2+** 擲骰後卡住，無法繼續 | Chrome（長戰） |
| B4 | FSM=`SETTLEMENT` 但 modal 不可見 → 全面鎖死 | Chrome |
| B5 | 勝利後 **再次**彈傷害結算 | Chrome |
| B6 | R2 按攻擊 **完全無反應**（silent） | Chrome |
| B7 | iPhone：進戰鬥 **睇唔到敵人**／按鈕唔喺首屏 | Safari |
| B8 | iPhone：**無角色頭像**（產品要求要有） | Safari |
| B9 | iPhone：按「開始戰鬥」**無反應** | Safari |
| B10 | `settlementRoundKey` / `current_phase` 碰撞導致 silent skip | 全平台 |
| B11 | poll 與 submit 競態，重複／漏彈 modal | 全平台 |
| B12 | `me.submitted` stale，R2 鎖死 | 全平台 |

### 2.3 根因結論（Architect 必須正面解決）

1. **雙控制面**：FSM + 15+ legacy 變量 + poll 旁路 → 不可能靠 invariant 補救  
2. **modal 觸發散佈**：`submitAction`、`handleCombatRoundResolved`、`loadCombatStatus` 三處都能彈結算  
3. **idempotency 用錯 key**：`current_phase` 唔等於「已結算回合序號」  
4. **7600 行 monolith**：無法測試、無法推理  
5. **手機 layout 與邏輯耦合**：改 CSS 就係改狀態假設  

---

## 3. 產品硬約束（不可違反）

### 3.1 Solo 戰鬥 UX 時序（必須滿足）

```
[IDLE] 玩家按「攻擊」
  → [DICE_ROLLING] 擲骰動畫 ~440ms（8×55ms，保留）
  → [DICE_CONFIRM] 顯示骰值 +「確認並結束本回合」
  → 玩家按確認
  → [SUBMITTING] 隱藏骰子區，顯示「結算中…」（覆蓋 RTT）
  → API 返回 round_resolved
  → [SETTLEMENT] **必定**彈出傷害結算 modal（數字 > 0 且與 HP 一致）
  → 玩家按「確定」
  → [IDLE] 解鎖下一回合；R2 攻擊必須即時有反應（擲骰或 toast，**絕不 silent**）

Killing blow（敵 HP≤0）：
  → [SETTLEMENT] 最後一回合結算（**唔 skip**）
  → 按「確定，查看勝利」
  → [VICTORY] 勝利畫面
  → **絕不**再彈結算（poll/submit 均 no-op）
```

| 要 | 唔要 |
|----|------|
| 擲骰動畫 | 完全移除動畫 |
| Confirm 後即時 loading → 結算 | Confirm 後空白主畫面等 poll |
| 0ms 人工 modal delay | 1500ms setTimeout |
| 被擋操作必須 toast | silent return |
| 手機：敵我 **小頭像** + HP + 行動喺首屏 | 隱藏頭像、要捲動先見到敵人 |

### 3.2 後端（Phase 1 盡量唔 breaking）

**保留**現有 Flask API（可建議 **additive** 欄位，唔好 breaking）：

| 方法 | 路徑 | 回傳要點 |
|------|------|----------|
| POST | `/combat/start` | `combat_id`, `status`, `precheck` |
| POST | `/combat/submit_action` | `round_resolved`, `round_settlement`, `log_entries`, `enemy`, `current_phase` |
| GET | `/combat/status` | 同上 + `my_state.submitted` |
| GET | `/api/version` | 部署標記 |

**權威**：後端 `roll_combat_dice()`；前端擲骰可 cosmetic（Phase 2 可選傳 `dice_result`）。

**建議 Gemini 評估**（可選，寫明利弊）：
- 回應加 **`settled_round_index`**（單調遞增）取代前端用 `current_phase` 防抖
- 回應加 **`settlement_id`**（UUID 或 `combat_id:round_n`）作結算冪等 key

### 3.3 CI

- `scripts/pre_deploy_checks.sh`（192+ 項）必須仍綠
- 新系統必須附 **Playwright** 或 **contract test**（見 §7）

---

## 4. 新架構要求（Greenfield）

### 4.1 檔案結構（請 Gemini 定稿）

**禁止**再將 >500 行戰鬥邏輯放入 `index.html`。建議：

```
static/js/combat/
  index.js              # 唯一入口：CombatApp.mount()
  state_machine.js      # 純狀態機，零 DOM 依賴
  api_client.js         # submit/status/start only
  views/
    hud_view.js         # 敵我面板（含手機雙欄+頭像）
    action_view.js      # 攻擊/防禦/Zoo/物品
    dice_modal_view.js  # 擲骰+確認
    settlement_view.js  # 傷害結算 modal
    victory_view.js     # 勝利/失敗
  render.js             # 從 state 渲染 DOM（單向）
  selectors.js          # DOM id 集中管理
templates/
  combat_screen.html    # 可選：Jinja partial，或 index 只留 mount point
```

`templates/index.html` 只保留：
```html
<div id="combat-root"></div>
<script type="module" src="/static/js/combat/index.js"></script>
```

### 4.2 狀態機（唯一 SSOT）

請設計 **不可變轉移表** + **非法轉移拒絕** + **reason 日誌**。

```javascript
// 請 Gemini 補全所有轉移與 guard
const Phase = {
  IDLE, DICE_ROLLING, DICE_CONFIRM, SUBMITTING,
  SETTLEMENT, VICTORY, DEFEAT,
};

// 建議 context（取代所有 boolean）
{
  combatId,
  phase,
  settledRoundIndex,      // 已確認結算嘅最高回合序號
  pendingSettlementId,    // 後端 settlement_id 或 client 生成
  dice: { action, value },
  error: null,
}
```

### 4.3 核心不變式（Invariant — 違反即 bug）

```
INV-A: phase === SETTLEMENT  <=>  settlement_modal.isVisible === true
INV-B: phase === VICTORY|DEFEAT  =>  poll 只更新 dashboard，禁止任何 modal
INV-C: 同一 settlement_id 只顯示一次
INV-D: performAction 在任何非法 phase 必須 toast（含 SUBMITTING、SETTLEMENT）
INV-E: SUBMITTING 結束後，要麼進 SETTLEMENT（有 round_resolved），要麼回 IDLE（錯誤）
```

**Recovery 策略**請寫清楚：違反 INV-A 時，重彈 modal 定強制回 IDLE？唔好留「幽靈 SETTLEMENT」。

### 4.4 Poll 規則（請明確寫死）

| phase | loadCombatStatus 允許 |
|-------|----------------------|
| IDLE | 更新 HUD、解鎖行動 |
| DICE_* / SUBMITTING | 只 sync HP 數字，**唔改 phase、唔彈 modal** |
| SETTLEMENT | 只 sync HP，**唔彈第二次 modal** |
| VICTORY | **no-op**（stop polling） |

**禁止**：poll 路徑調用 `showSettlement`（呢點係舊系統最大毒瘤）。

### 4.5 結算資料

- **優先**用 `round_settlement` API 欄位  
- **Fallback**：從 `log_entries` 補建（marathon 多回合）— 請獨立函式 `buildSettlementFromLogs(logs, settledRoundIndex)`  
- **禁止** stale `breakdown` early return 導致 UI 全 0  

---

## 5. 手機 UX（必須一併設計）

**裝置**：iPhone Safari · viewport 390×844（亦要考慮 SE 667px）。

**首屏必須同時可見（無需捲動）**：
- 敵：小頭像 w-8 + 名 + HP bar + 數字  
- 我：小頭像 w-8 + 名 + HP bar + 數字  
- 至少 **攻擊 + 防禦** 兩個按鈕  

請交付 **wireframe ASCII** + Tailwind class 清單 + 估算高度（header ≤36px、HUD ≤80px、actions ≤160px）。

**Safari 專項**：
- `touch-action: manipulation`  
- `showConfirmModal` 必須喺 **click handler 同步** resolve（唔包 setTimeout）  
- Encounter 開始按鈕用 `<button type="button">`，唔用 div onclick  

---

## 6. 必須刪除嘅舊邏輯（遷移時）

請列出 **刪除清單**（Grok 實作時逐個 grep 確認已無引用）：

- `combatAwaitingSettlementAck`, `settlementModalShown`, `lastShownSettlementPhase`
- `combatVictorySequenceCompleteId`（改為 FSM VICTORY absorbing）
- `handleCombatRoundResolved` 式「到處開 modal」
- `loadCombatStatus` 內任何 `showFullRoundSettlement` 呼叫
- `enrichRoundSettlementData` 與 `buildClientRoundSettlement` 若可合併到單一 `normalizeSettlement(apiPayload)`
- `combatFsmHook` shadow 層（整個移除，只留一個 FSM）

---

## 7. 測試規格（交付物之一）

### 7.1 Playwright（必須寫完整 spec 骨架）

| # | 場景 | 斷言 |
|---|------|------|
| T1 | `practice_iggy_04_marathon` R1 | 非 0 骰 → 結算傷害 > 0 → 敵 HP 下降 |
| T2 | 同上 R2 | R1 確認後 → 攻擊可用 → R2 結算 **再次**彈出 |
| T3 | Killing blow | 結算 1 次 → 勝利 → 3s 內無第二次結算 |
| T4 | 擲骰中 double-click 攻擊 | toast 出現 |
| T5 | submit 延遲 1s | 「結算中」可見；完成後 R2 可用 |
| T6 | iPhone 390×844 | 敵我頭像 + 攻擊鈕在 viewport 內 |
| T7 | Safari startEncounter | 確認框 → 進入戰鬥畫面 |

### 7.2 Contract test（可選）

對 `submit_action` 回應 JSON schema：`round_settlement.team_damage_dealt` 與 `enemy.hp` 一致性。

---

## 8. 遷移計劃（請交 PR DAG）

請給 **有序 PR 列表**（Grok 可逐個 merge）：

```
PR-0: 新建 static/js/combat/* + 空 mount（舊系統仍運行）
PR-1: 狀態機 + api_client + unit tests（無 DOM）
PR-2: dice_modal + submit 路徑（solo only）
PR-3: settlement_view + killing blow → victory
PR-4: hud_view 手機+桌面 + 頭像
PR-5: 切 feature flag COMBAT_V2=1，預設 off
PR-6: 刪除 index.html 舊戰鬥 script 區塊
PR-7: Playwright CI
```

每個 PR：**改動檔案列表、rollback 方式、手動驗證步驟**。

---

## 9. 交付清單（Gemini 輸出必須包含）

請一次過交付：

1. **Architecture Overview**（1 頁）  
2. **狀態轉移表**（完整，含錯誤邊界）  
3. **Invariant + Recovery** 章節  
4. **檔案結構 + 每檔 public API**  
5. **核心 pseudo-code**：`transition`, `performAction`, `confirmDice`, `onSubmitSuccess`, `ackSettlement`, `pollTick`  
6. **DOM / HTML 結構**（手機+桌面）  
7. **後端 additive 建議**（`settled_round_index` 等）  
8. **刪除清單**（舊符號）  
9. **Playwright spec 全文**  
10. **PR DAG + 工時估算**  

**輸出格式**：Markdown，繁體中文為主，code 用 JavaScript。

---

## 10. 參考：現有程式規模（供估算重寫量）

| 檔案 | 行數 | 備註 |
|------|------|------|
| `templates/index.html` | ~7645 | 戰鬥邏輯散佈其中 ~2500 行 |
| `static/js/combat_flow.js` | ~296 | PR#2 FSM（將廢棄） |
| `routes/combat.py` | ~597 | API 層 |
| `models/combat.py` | ~1754 | 結算邏輯 |

### 10.1 後端 submit 回傳（概念）

```python
# routes/combat.py — submit 成功後概念上
payload["status"] = "round_resolved"
payload["round_resolved"] = True
payload = _build_round_resolved_response(combat, encounter, squad_id)
# 含 round_settlement, log_entries, enemy, current_phase
```

### 10.2 長戰測試敵人

```json
{
  "encounter_id": "practice_iggy_04_marathon",
  "enemy": { "name": "練習・長戰巨影", "hp": 220 }
}
```

### 10.3 舊 FSM（將廢棄 — 勿再擴展）

```javascript
// static/js/combat_flow.js — 僅供理解失敗原因
onSubmitResponse(data) {
  this.transitionTo(CombatUiPhase.SETTLEMENT, { reason: 'round_resolved' });
}
// 但 legacy index.html 仍有多處直接 showFullRoundSettlement → 競態
```

---

## 11. 驗收標準（重寫完成定義）

Henry 用 Chrome、`practice_iggy_04_marathon`：

- [ ] 連續 **5 回合** 每回合：擲骰 → 確認 → 結算（傷害>0）→ 敵 HP 動畫 → R(n+1) 攻擊正常  
- [ ] Killing blow：結算 1 次 → 勝利 → 唔再結算  
- [ ] Console 無 error；FSM 無 `[Shadow mismatch]`  

iPhone Safari：

- [ ] 敵我 **頭像**可見；首屏見攻擊鈕  
- [ ] 開始遭遇有反應  

`/api/version`：`combat_v2: true`（新標記，與舊 `combat_flow_v*` 脫鈎）

---

## 12. 先前諮詢文件（背景，唔使重複讀 URL）

- `GEMINI_COMBAT_REWRITE.md` — Phase 6 初版重寫（已被 patch 淹沒）  
- `GEMINI_PHASE7.md` / `GEMINI_PHASE8.md` — 實機回歸  
- `bug_log/.../REPORT.md` §21–§30 — 完整 bug 時間線  

**今次請當 Phase 6 未做過，重新 Greenfield。**

---

*Greenfield Rewrite Request · 2026-06-30 · baseline `a386c14` · 請 Gemini 從 0 設計，唔再 patch*