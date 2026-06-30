# GEMINI_CONSULT — BUG-2026-001（Phase 4：Safari 0 傷害 + Chrome 勝利後重複結算）

> Phase 1–3 → v4–v11 已多輪修復。Henry Safari §16 resolved；**2026-06-30 新回報** reopen 兩個子議題。  
> 完整脈絡：`REPORT.md` §21–§23 · `decisions_log.md` § instant settlement

## 一句話

**PA `40a2c53`（v11）後：Vini Safari 長戰結算顯示 0 傷害；Henry Chrome 勝利畫面後再彈結算。v12 patch 已實作，待實機驗證。**

## 實機條件（2026-06-30 · 新回報）

| 子議題 | 玩家 | 瀏覽器 | Encounter | 症狀 |
|--------|------|--------|-----------|------|
| §21 | Vini | **Safari** macOS | `practice_iggy_04_marathon` | 非 0 骰；結算 UI **全 0**（HP 有變） |
| §22 | Henry · `PLAYER-75406` | **Chrome** macOS | （長戰／killing blow） | 結算→勝利→**再結算** |

| 項目 | 值 |
|------|-----|
| Baseline commit | `40a2c53`（`combat_flow_v11`） |
| v12 markers | `combat_flow_v12`, `combatVictorySequenceCompleteId`, `enrichRoundSettlementData` |
| 對照 | Henry Chrome §21 **無** 0 傷害；Henry Safari §16 **無** §22 |

## Code review 結論（Phase 4 — 請 Gemini 確認）

### §22 Critical：勝利後重複結算

**根因鏈**：

```
continueCombatAfterRound → finalizeCombatVictoryFromPayload
  → showCombatResult → resetCombatSessionState()
  → settlementModalShown = false, victorySettlementAcknowledgedCombatId = null
  → in-flight loadCombatStatus(poll) 仍帶 round_settlement
  → handleCombatRoundResolved → showFullRoundSettlement (再彈)
```

**v12 修復**：

- `combatVictorySequenceCompleteId` — finalize 前標記；poll / `showFullRoundSettlement` / `loadCombatStatus` early return
- `showCombatResult(..., { fromVictoryFinalize: true })` — `keepVictoryLock` 唔清勝利鎖

### §21 High：Safari 結算 0 傷害

**根因鏈**：

```
getRoundSettlement → round_settlement 存在但 team_damage_dealt=0 或 breakdown.total=0
  → buildSettlementBreakdown 早期 return 空 breakdown
  → renderSettlementBreakdown 顯示全 0
  （enemy HP 仍由 applySettlementEnemyHp / enemy_hp_after 更新）
```

**v12 修復**：

- `enrichRoundSettlementData` — 從 `log_entries` 用 `buildClientRoundSettlement` 補數字
- `buildSettlementBreakdown` — breakdown total=0 但 team_damage_dealt>0 時重算

**Safari 因素**：可能疊加 **快取舊 JS**；實機必須硬刷新 + 核對 `/api/version` `combat_flow_v12: true`。

## 請 Gemini 產出（Phase 4）

1. **§22**：`combatVictorySequenceCompleteId` 有無 race（`showCombatResult` 被 defeat 路徑呼叫、`resetCombatSessionState` 其他 caller）？
2. **§21**：`enrichRoundSettlementData` 會否誤用**上一回合** log？如何加 `current_phase` / summary 邊界 assert？
3. **測試**：最小 Playwright／contract —「勝利畫面 visible 後 `#combat-round-settlement-modal` 不可再 flex」？
4. **優先序**：v12 deploy 後 Vini Safari vs Henry Chrome 驗證順序？

**勿建議**：恢復 1500ms modal delay；勿移除 instant settlement。

## 必讀

```bash
bash scripts/build_gemini_packet.sh
# → GEMINI_PACKET.md（含 v12 摘錄）
```

見 `GEMINI_REVIEW.md` §17。