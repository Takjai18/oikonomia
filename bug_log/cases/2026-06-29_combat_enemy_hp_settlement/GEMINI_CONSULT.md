# GEMINI_CONSULT — BUG-2026-001（Henry 實機仍失敗）

> 俾 Gemini Architect 嘅精簡入口。完整脈絡見同目錄 `REPORT.md` §12。

## 一句話

**PA 已 deploy `641da28`（`enemy_hp_sync_v3: true`），CI 單人 `practice_iggy_03_boundary` 多回合 API 測試全綠，但 Henry（Iggy 線、單人）實機戰鬥中敵 HP 顯示仍唔更新。**

## 實機條件

| 項目 | 值 |
|------|-----|
| 玩家 | Henry |
| 路線 | Iggy |
| 隊伍 | 單人 |
| Encounter | `practice_iggy_03_boundary`（140 HP） |
| PA version | `641da28`（2026-06-29 curl 確認） |

## 已排除（自動化）

- 後端 `submit_action` / `combat/status`：`enemy.hp` 每回合遞減（`test_solo_multi_round_poll_hp_monotonic`）
- 開局 full HP（`test_practice_combat_start_enemy_hp_full`）
- Killing blow settlement payload（`test_solo_killing_blow_practice_quick`）

## 懷疑方向（請取捨）

1. Safari 快取舊 `index.html`（server marker 新、client JS 舊）
2. 前端多源 HP（`resolveAuthoritativeEnemyHp` Math.min + monotonic + `lastCombatStatus`）仍有 race
3. `combatAwaitingSettlementAck` 卡住令 poll 唔 refresh DOM
4. 140 HP 血條變化太細（UX 误判）— 需確認**數字**有冇變
5. 無 DOM/integration test 覆蓋

## 請產出

1. 最可能單一根因 + code path（附行號）
2. 推薦修復方案（pseudo-diff）同 trade-off
3. Henry 最少採證步驟
4. 建議新增測試（最好含 DOM 或 contract assert）

## 必讀檔案（GitHub `641da28`）

- `templates/index.html` — `syncEnemyHpDisplay`, `loadCombatStatus`, `handleCombatRoundResolved`
- `routes/combat.py` — `/combat/status`, `/combat/submit_action`
- `models/combat.py` — `reconcile_enemy_hp`, `build_enemy_combat_stats`
- `scripts/test_combat_flow.py` — `test_solo_multi_round_poll_hp_monotonic`

## attachments 注意

`attachments/` 係 `3c89f62` 快照，**唔反映最新修復**。請以 GitHub main 為準。

## 點讀（Gemini 讀唔到 Drive 時）

**請用同目錄 `GEMINI_PACKET.md`**（~55KB，內嵌完整 JS/Python）：

1. 打開 `bug_log/cases/2026-06-29_combat_enemy_hp_settlement/GEMINI_PACKET.md`
2. 全選 Copy → 貼入本 chat

或 GitHub Raw（將 `COMMIT` 換成最新 short hash）：

`https://raw.githubusercontent.com/Takjai18/oikonomia/COMMIT/bug_log/cases/2026-06-29_combat_enemy_hp_settlement/GEMINI_PACKET.md`

重新生成：`bash scripts/build_gemini_packet.sh`