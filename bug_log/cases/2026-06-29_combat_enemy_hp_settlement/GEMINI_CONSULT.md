# GEMINI_CONSULT — BUG-2026-001（Phase 2：動畫 delay）

> Phase 1（HP 唔跌／modal 缺失）經 v4–v6 修復後 **大幅改善**。本檔聚焦 **殘留動畫 delay**。完整脈絡見 `REPORT.md` §13。

## 一句話

**PA `aecffa9`（`enemy_hp_sync_v6`）後端 HP 正確，Henry 實機 HP／settlement 大致正常，但每回合攻擊後敵 HP 更新同「本回合戰果」modal 仍覺得慢（動畫／計時器堆疊）。**

## 實機條件

| 項目 | 值 |
|------|-----|
| 玩家 | Henry · `PLAYER-75406` · Iggy · 單人 |
| PA version | `aecffa9`（2026-06-30 curl） |
| 頭先戰鬥 | Combat **#35** `practice_iggy_01_quick`（一輪勝利，後端 HP 48→0 ✓） |
| 近期 boundary | Combat **#34** `practice_iggy_03_boundary`：R1 140→91，R2→0（後端 log ✓） |

## 已確認（後台）

- `/combat/status?combat_id=34|35`：`enemy.hp`、`round_settlement.enemy_hp_after`、summary log **一致**
- 問題 **唔係** stale cache 或 HP sync regression（v6 poll 凍結係刻意設計）

## 懷疑方向（計時器堆疊）

1. 擲骰：`DICE_ROLL_PRESETS.normal` ≈ 2.2s（提交前）
2. HP tween：`animateCombatNumber` **420ms**；血條即時跳、數字後追
3. Settlement：`COMBAT_SETTLEMENT_DELAY_MS.normal` **1500ms** 先彈 modal
4. `settlementTimerPending` 期間 `loadCombatStatus` **零 DOM 更新**（修 race 副作用）

## 請產出

1. 推薦修復方案（縮 delay / 跳過 tween / 練習模式 fast path / 分拆 poll 凍結）+ pseudo-diff
2. 保留 v6 race 修復前提下嘅 **最低風險** 改動順序
3. 建議新預設（`combatSettlementDelay`、practice encounter 特例）
4. 可自動化嘅延遲上限測試（例如 round_resolved → modal visible < 1200ms）

## 必讀檔案（GitHub `aecffa9`）

- `templates/index.html` — `animateCombatNumber`, `showFullRoundSettlement`, `getSettlementModalDelayMs`, `settlementTimerPending`, `loadCombatStatus` early return
- `DICE_ROLL_PRESETS` / `COMBAT_SETTLEMENT_DELAY_MS` 常數（~L1238）

## 點讀

**`GEMINI_PACKET.md`**（`bash scripts/build_gemini_packet.sh` 重新生成）