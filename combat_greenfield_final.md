# Oikonomia 戰鬥系統 Greenfield 重寫最終設計規格（Real-time Co-op 版）

**日期**：2026-07-01  
**版本**：Final v1.1
**負責人**：Grok Architect（整合所有確認）  
**目的**：為 20 人青年、西貢戶外營會設計穩定、可維護嘅全新戰鬥子系統

---

## 1. 最終確認嘅戰鬥機制

### 1.1 核心規則（Authoritative Spec）
- 戰鬥模式：**多人實時 Co-op + AI 主角**（單人主要用測試）
- **任何角色（包括主角）HP ≤ 0 → 戰鬥即時失敗**（絕對規則）
- 玩家可選擇：攻擊、防御、Zoo能力、使用道具、逃跑
- **Zoo 能力**（Greenfield 權威規格）：
  - **任何神智值均可發動 Zoo**——唔係「神智 ≥70 先用得」；僅當遭遇 `combat_settings.allow_zoo === false` 時禁止
  - Zoo 行動同樣經後端擲骰（0–3）並計入傷害結算；低神智仍有**暴走**風險（見下方暴走規則）
  - **神智加成乘數**（只喺選擇 Zoo 行動時套用，唔影響攻擊／防禦；神智 <70 仍可發動，但無加成）：
    | 神智 | Zoo 傷害乘數 |
    |------|-------------|
    | <70 | ×1.0 |
    | ≥70 | ×1.3 |
    | ≥80 | ×1.4 |
    | ≥90 | ×1.5 |
    | ≥100 | ×1.8 |
  - UI：**唔應**因神智不足而 disable Zoo 按鈕；神智 <70 顯示「可發動、無加成（×1.0）」；≥70 顯示當前 tier 乘數
  - AI 主角：`choose_protagonist_auto_action` 喺 `allow_zoo` 且神智 ≥30 時可有機率自動 Zoo（唔 gate 於 ≥70）；神智 <30 仍強制防禦
- 攻擊擲骰：0-3（後端權威），乘以角色 Power
- **暴走**（任何攻擊類行動，含 Zoo）：神智 <10→90%、<20→50%、<40→20% 機率失控（可能無敵傷害）
- **Defense 公式**（只限主動選擇 Defense 行動時生效）：
  - Base 30% + Resilience × 0.5%，上限 90%
- **逃跑規則**：任何人選擇逃跑 → 觸發全隊 escape 判定
  - 成功：全隊逃跑
  - 失敗：顯示失敗畫面 → 玩家確認後，繼續結算選擇戰鬥嘅玩家行動
- 多敵人 Targeting 優先順序：
  1. 可以一擊秒殺嘅角色
  2. 選擇逃跑嘅角色
  3. 血量低於 50% 嘅角色
  4. 有創傷標記嘅角色
  5. 主角（最後）
- 傷害結算必須顯示：自己角色 + 隊友 + AI 主角造成傷害 + 受到傷害
- 主角自己會擲骰並造成傷害

### 1.2 營會實用性要求
- 主要使用手機（iPhone Safari / Chrome）
- 西貢戶外網絡不穩 → 必須有動態 Polling + Reconnection 機制
- 任何失敗狀態必須有清晰、不可逆嘅退出路徑

---

## 2. 架構總覽

**核心設計原則**：
- 後端係唯一權威狀態源（SSOT）
- 前端只做 **Passive Sync**，嚴禁本地 Timer 主導 round 推進
- 單一狀態機驅動所有 UI
- **Preemptive Interrupt**：任何角色死亡必須即時搶占所有 UI 並進入 COMBAT_FAILED
- 使用 `settled_round_index` + `settlement_id` 做等冪同進度拉齊

**技術選型（Phase 1 營會前）**：
- 現有 HTTP Poll + 動態間隔（IDLE 1200ms / WAITING 800ms）
- 加入 `AbortController` + Visibility API + 指數退避
- 之後可升級至 WebSocket

---

## 3. 狀態機（State Machine）

### 主要 Phase
```javascript
const Phase = {
  IDLE,
  DICE_ROLLING,
  DICE_CONFIRM,
  SUBMITTING,
  WAITING_FOR_PLAYERS,     // 等其他真人玩家提交
  ESCAPE_ATTEMPT,          // 有人觸發逃跑，全隊進入判定
  SETTLEMENT,
  COMBAT_FAILED,           // 最高優先級 absorbing state
  VICTORY,
  ESCAPED
};
```

### 核心 Invariant（違反即 bug）
- **INV-A**：`phase === SETTLEMENT` ⇔ 傷害結算 Modal 可見
- **INV-B**：`phase === COMBAT_FAILED` ⇒ 所有操作 disabled + 顯示失敗原因
- **INV-C**：同一個 `settlement_id` 只渲染一次
- **INV-D**：任何角色 HP ≤ 0 必須即時進入 `COMBAT_FAILED`（最高優先級）
- **INV-E**：Escape 失敗後，戰鬥玩家嘅行動必須仍然結算

### Recovery 策略
- 出現幽靈 SETTLEMENT 或 INV-A 違反 → 強制 hideAllModals() + 回 IDLE + Toast 重置
- COMBAT_FAILED 係 absorbing state，嚴禁重新開啟 Polling

---

## 4. 檔案結構

```
static/js/combat/
├── index.js                    # 唯一入口：CombatApp.mount()
├── state_machine.js            # 純狀態機 + syncState + handleAnyDeath
├── api_client.js               # fetch + ResilientPollingManager
├── render.js
├── selectors.js
└── views/
    ├── hud_view.js             # 多玩家頭像 + 等待狀態 + 已就緒標記
    ├── action_view.js
    ├── dice_modal_view.js
    ├── settlement_view.js      # 傷害 Breakdown（自己 + 隊友 + 主角）
    ├── escape_result_view.js   # 逃跑失敗阻塞畫面
    └── victory_view.js
```

`templates/index.html` 只保留 `<div id="combat-root"></div>` + module script。

---

## 5. 核心實作建議

### 5.1 State Machine 核心（syncState + determineSettlementRoute）
（已整合最終優化版本，包含死亡搶占最高優先級 + Escape 拉齊機制）

### 5.2 Resilient Polling Manager（最終版）
使用 `AbortController` + Visibility API + 指數退避，適合戶外營會。

### 5.3 COMBAT_FAILED 處理
- 即時清空所有 View
- 顯示死亡成員名單
- 提供「返回大廳」同「召喚 GM」按鈕（異步 API）
- 「重新同步」只做單次 Fetch + 嚴格控流（死亡狀態下鎖死 Polling）

### 5.4 傷害結算 Breakdown 渲染
清楚分開自己、隊友、AI 主角嘅行動同傷害。

---

## 6. UI / DOM 結構重點（手機優先）

- 首屏無捲動：敵我頭像 + 數據 + 行動按鈕（攻擊 / 防御 / 物品 / 逃跑）
- 下方：隊友狀態卡片（已就緒 / 等待中）+ 主角 HP/神智
- 最下方：戰鬥 Log
- 逃跑失敗畫面：阻塞 + 確認後繼續結算
- 戰鬥失敗畫面：Absorbing + 清晰退出路徑（返回大廳 / 召喚 GM）

---

## 7. 測試規格（Playwright 關鍵案例）

- T8：混合逃跑行動（一人逃跑失敗，戰鬥玩家行動仍然結算）
- T9：Preemptive Interrupt（任何 Phase 突然死亡即時切換 COMBAT_FAILED）
- T10：10 秒超時自動 Defense + 狀態拉齊

---

## 8. 遷移與部署

- 戰鬥 V2 **預設開啟**；GM 後台「戰鬥監控」可關閉（`data/.combat_v2`）；緊急可用 env `COMBAT_V2=0`
- 保留舊版作為 rollback 方案
- 建議 PR 順序：後端 API 欄位升級 → 狀態機核心 → View 重寫 → 測試 → 上線

---

## 9. Rollback 方案

前端保留 `static/js/combat_v1/` 作為備份。  
若出現重大問題，可透過後端環境變數 `COMBAT_VERSION = "V1"` 一鍵回滾。

---

**結論**：呢個版本已經整合所有確認過嘅機制同實作建議，具備單一狀態機、死亡即時搶占、Escape 混合結算、戶外網絡 resilience 同清晰失敗退出路徑，適合 20 人營會實戰使用。

可以直接交畀 Grok Build 開始實作。