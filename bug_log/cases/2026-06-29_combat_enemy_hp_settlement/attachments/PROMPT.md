# Oikonomia 戰鬥 HP / 結算 Bug — 請協作診斷同提出修復方案

## 背景

Flask Web ARG 遊戲「Oikonomia」，正式環境：https://takjai.pythonanywhere.com  
Repo：https://github.com/Takjai18/oikonomia  
最新 commit：`e2e6dc7`（PA 已部署，curl /api/version 確認 `enemy_hp_sync_v2: true`）

已做過多輪修復，GitHub Actions CI + `pa-update.sh` 部署前會跑 regression（142+ 測試全綠），但**真機實測仍然間歇性出錯**。

## 用戶回報（2026-06-29，更新後仍發生）

- 玩家：**Henry**（實機測試帳號）
- 遭遇戰：**【練習】速戰情緒殘影**（`practice_iggy_01_quick`，敵人「速戰殘影」，HP 僅 **48**）
- 症狀（同之前 Saliba / 界線共生影類似）：
  - 有時見到傷害數字，但敵人 HP 條/數字唔跌
  - 有時冇完整結算 modal
  - 有時擲骰 preview 同實際結果唔一致
  - F5 刷新未必救到
- 後端測試顯示 DB `enemy_hp` 通常正確；懷疑 **前端 poll/動畫覆寫**，或 **一輪擊殺 victory 路徑跳過結算 payload**

## 已嘗試修復（請勿重複造輪）

| Commit | 內容 |
|--------|------|
| `14bd58e` | poll 跳過 settlement 期間；log-based HP |
| `60408b2` | `reconcile_enemy_hp`；保護 dice preview |
| `4bbb885` | `syncEnemyHpDisplay`；`enemy_hp_after` |
| `e2e6dc7` | 一輪擊敗前 save logs；CI + deploy gate |

## 強烈懷疑（請驗證）

1. **Killing-blow / 一輪勝利 API 路徑**  
   `routes/combat.py` `submit_action` 喺 `winner == "squad"` 時直接 `return jsonify(build_victory_outcome_payload(...))`，**冇** `round_settlement`、`log_entries`、`enemy.hp`。  
   `services/combat_outcomes.py` 的 victory payload 極簡。  
   前端 `submitAction()` 見到 `data.outcome` 就跳 `finishCombatVictoryFromPayload()`，**跳過** `showFullRoundSettlement()` / `syncEnemyHpDisplay()`。  
   → 對 48 HP 速戰殘影 + Iggy 主角自動 Zoo（power 100），極易一輪秒殺，用戶就睇唔到 HP 變化。

2. **前端 victory 與 round_resolved 雙軌**  
   `loadCombatStatus` / `handleCombatRoundResolved` / `shouldShowRoundSettlement` 邏輯複雜；`combatAwaitingSettlementAck`、`settlementTimerPending`、`combatPreviewPending` 互斥條件可能漏 case。

3. **主角自動行動**  
   `models/combat.py` `choose_protagonist_auto_action` 用 `models.combat.roll_combat_dice`（唔係 `routes.combat`），sanity≥70 會 Zoo；傷害遠大於玩家。

## 請你哋做乜

### A. Root cause（分 backend / frontend / race）

- 畫出 `submit_action` → `resolve_player_phase` → victory vs `round_resolved` 決策流程（mermaid 可）
- 解釋點解 **automated tests pass** 但 **Henry + practice_iggy_01_quick** 仍 fail
- 列出所有會令 UI 顯示舊 HP 的 code path（poll、animation、`updateEnemyCombatStats`、`normalizeCombatStatusData` 等）

### B. 具體修復方案（要可落地）

至少涵蓋以下之一，並講 trade-off：

- **方案 1（後端）**：killing blow 仍回 `round_resolved` payload（含 `round_settlement`、`log_entries`、`enemy.hp`），再附 `outcome: victory`；或 victory payload 補齊最後一輪結算欄位
- **方案 2（前端）**：`finishCombatVictoryFromPayload` 前先 fetch `/combat/status` 或從 response logs 做 settlement + HP sync
- **方案 3（測試）**：新增 `practice_iggy_01_quick` 一輪擊殺測試，assert API 有 log/settlement、DB enemy_hp=0、模擬前端唔會顯示錯 HP

### C. 回歸測試清單

- 單人 + 主角、48 HP 一輪勝利
- 140 HP 多回合（界線共生影）
- 雙人隊伍 waiting → round_resolved
- poll 期間 settlement modal 開住
- 並發 submit（`test_combat_concurrency.py`）

### D. 交付格式

1. Executive summary（3–5 句）
2. Root cause（有 code 行號引用）
3. 建議 patch（pseudo-diff 或具體函數改動）
4. 新/改測試 case 名稱同 assert
5. 手動驗證步驟（Henry 實機 checklist）

## 本資料夾檔案（按優先級）

### 必讀

| 檔案 | 重點 |
|------|------|
| `templates/index.html` | `syncEnemyHpDisplay`、`submitAction`、`loadCombatStatus`、`finishCombatVictoryFromPayload` |
| `routes/combat.py` | `submit_action`、`combat/status` |
| `models/combat.py` | `resolve_player_phase`、`_end_combat`、`_attach_round_settlement` |
| `services/combat_outcomes.py` | `build_victory_outcome_payload` |
| `encounters/practice_iggy_01_quick.json` | 速戰殘影（HP 48） |

### 測試

| 檔案 | 重點 |
|------|------|
| `scripts/test_combat_flow.py` | 142 tests |
| `scripts/test_combat_audit.py` | settlement、主角 |
| `scripts/test_combat_concurrency.py` | 並發 resolve |
| `scripts/pre_deploy_checks.sh` | CI/deploy gate |

### 輔助

| 檔案 | 重點 |
|------|------|
| `models/protagonist.py` | 主角參戰 |
| `routes/misc.py` | `/api/version` markers |
| `GEMINI_REVIEW.md` | 歷史 review |
| `AGENT_HANDOFF.md` | 架構、部署 |
| `deploy/pa-update.sh` | 部署腳本 |

## 環境事實

```bash
curl -s https://takjai.pythonanywhere.com/api/version
# version: e2e6dc7
# markers.enemy_hp_sync_v2: true
```

```bash
cd oikonomia && bash scripts/pre_deploy_checks.sh
```

## 協作方式

- **Gemini**：偏靜態 review、邏輯漏洞、邊界 case
- **Grok / Build agent**：實作 patch、跑測試、push
- Acceptance test：Henry + `practice_iggy_01_quick` 一輪勝利時 HP/結算正確

## 實測補充

Henry 打速戰殘影時，通常**第一下攻擊就贏**；贏咗之後往往**冇見過完整結算 modal**，敵人 HP 條好似冇跌。

請由「一輪擊殺 victory payload 缺少 settlement」呢個假設開始驗證。