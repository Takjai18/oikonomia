# GEMINI_CONSULT — BUG-2026-001（Phase 3：Delay 殘留 + Settlement v10）

> Phase 1（HP／modal）→ v4–v10 已多輪修復。Phase 2（人工 delay 移除 → `combat_instant_settlement`）已實作。  
> **本檔聚焦**：實機仍覺得慢嘅 **殘留 delay** + settlement／victory 過渡是否穩健。  
> 完整脈絡：`REPORT.md` §13–§19 · `decisions_log.md` § instant settlement · § Combat Settlement Modal Bug

## 一句話

**PA `6391b22`（`combat_flow_v10`）後端／CI 全綠；Henry／Tak 實機 settlement 大致 OK，但戶外仍覺得「攻擊→HP→modal」有 lag；另需確認 v10 final-hit 過渡無 regression。**

## 實機條件（2026-06-30）

| 項目 | 值 |
|------|-----|
| 玩家 | Henry · `PLAYER-75406` · Iggy · 單人 |
| PA / GitHub | `6391b22`（deploy 後 curl 核對） |
| Markers | `combat_instant_settlement`, `combat_flow_v7`–`v10`, `enemy_hp_sync_v7`, `settlement_breakdown_v1` |
| 已驗 encounter | `practice_iggy_01_quick`、`practice_iggy_03_boundary`（instant checklist OK） |
| 新修復待驗 | `practice_iggy_02_leech`（情緒寄生影 final-hit stuck → v10） |

## 已確認

- 後端 `enemy.hp` / `round_settlement.enemy_hp_after` / DB log **一致**（`test_combat_flow.py` 192+ 項）
- `COMBAT_SETTLEMENT_DELAY_MS` 已移除；`pauseMs: 0`；settlement modal **即時**（無 1500ms 人工等待）
- v8–v10：`settlementModalShown`、`isFinalHitOrVictory`、`resolveEnemyHpAfter` 防 duplicate + final-hit 過渡

## 殘留 delay 懷疑（Phase 3 — 請 Gemini 重點查）

| 來源 | 位置 | 體感 |
|------|------|------|
| 擲骰動畫 | `DICE_ROLL_PRESETS.normal`：8×55ms ≈ **440ms**（提交**前**） | 攻擊 confirm 前仍要等 |
| 網絡 RTT | `submit_action` + `loadCombatStatus` poll（3s interval） | 戶外 Wi‑Fi 慢時體感 lag |
| HP 顯示時機 | `deferEnemyHp`：modal 期間主畫面**舊 HP**；按「確定」先 `applyPendingSettlementHp` | 玩家以為 HP 未跌 |
| Poll 凍結 | `combatAwaitingSettlementAck` 期間 `loadCombatStatus` 只做 `syncHpOnlyFromPoll` | 必要但可能加重「無反應」感 |
| 血條 vs 數字 | `syncEnemyHpDisplay` instant；血條 width 即時 | 應已同步，請確認無 regression |

**注意**：唔好再建議恢復 `COMBAT_SETTLEMENT_DELAY_MS` 或 1500ms modal delay（已決策移除）。

## Gemini Review 回應（2026-06-30）

| Gemini 項 | 現行 `main` 核對 | 處理 |
|-----------|------------------|------|
| `getSettlementModalDelayMs` 1500ms | ❌ **唔存在**（Gemini 可能睇舊版 upload） | 無需改；v11 註解標明 instant modal |
| `victorySettlementModalCombatId` 過度 guard | ✅ 存在 | **v11** 改為 modal 可見才 skip；stuck 時恢復 |
| `deferEnemyHp` 錯位 | ✅ 存在 | **v11** 改 `deferEnemyHp: false` + 即時 `syncEnemyHpDisplay` |
| 雙重 `DICE_ROLL_PRESETS` pauseMs 1150 | ❌ 僅一處；`pauseMs: 0` | 無需改 |

## 請 Gemini 產出

1. **Delay**：在保留 v6–v10 race guard 前提下，邊條路徑仍可縮至「攻擊 confirm 後 <1s 見 HP+modal」？具體 pseudo-diff（只 frontend）。
2. **Settlement**：v10 `isFinalHitOrVictory` / `buildVictoryTransitionPayload` 有無 edge case（poll 與 submit 競態、duplicate modal、stuck buttons）？
3. **測試**：點樣加 contract／Playwright  assert「round_resolved → `#combat-round-settlement-modal` visible < 1500ms」？
4. **優先序**：delay vs 雙人隊未驗 vs 營會前穩定性 — P0/P1 建議。

## 必讀（GitHub `6391b22`）

見 `GEMINI_REVIEW.md` §16 檔案包；**唔使全讀** `index.html`，跟 packet §D 摘錄即可。

## 點讀

```bash
bash scripts/build_gemini_packet.sh
# → 貼 bug_log/cases/.../GEMINI_PACKET.md 全文入 Gemini
```