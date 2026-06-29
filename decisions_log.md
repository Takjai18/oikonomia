# Oikonomia — Decisions Log

> **SSOT**：Google Drive `oikonomia/` 同步本 repo · 重大架構決定記錄於此  
> **讀者**：Grok（方向）、Grok Build（實作）、Gemini（review）、Tak（決策）

---

## 2026-06-29 — Grok Phase 1 Spec 確認

| 決策 | 內容 | 狀態 |
|------|------|------|
| 營會前範圍 | **只做 Phase 1**（低風險 ending 收斂）；Phase 2+ 營會後 | ✅ 已執行 |
| 優先級 | 穩定性 > 新功能；20 人 PA 單機 | ✅ |
| 神學整合 | Trauma/Ending narrative 正面（2 Cor 12:9）；bad_ending 仍保留盼望片段 | ✅ `CONDITIONAL_NARRATIVE_FRAGMENTS` |
| 架構選擇 | **中央 Orchestrator**（`services/ending.py`）優於 Event Bus（營會前） | ✅ |
| SSOT | Drive docs + repo；`ARCHITECTURE_ROADMAP.md` / 本檔 | ✅ |
| 回滾開關 | `OIKONOMIA_ENDING_ENABLED=0` 停用 orchestrator 副作用 | ✅ |
| Good Ending 完整演出 | 延後 Phase 3 | 待做 |
| GM trauma/ending override + audit | 延後；`protagonist_trauma_log` 已有 combat trauma | 部分 |
| 前端 offline queue | Phase 2+ | 待做 |

### Phase 1 交付清單（Grok Build）

| 項目 | 產出 |
|------|------|
| 1.1 `services/ending.py` | `judge_ending`、`apply_ending`、`build_trauma_summary`、`preview_ending_for_players` |
| 1.2 `apply_trauma(delta, reason)` | `models/protagonist.py` + `protagonist_trauma_log` |
| 1.3 `/status` 強化 | `trauma_level`、`trauma_summary`、`ending_preview`、`protagonist_control_status` |
| 1.4 Combat 收斂 | `services/combat_outcomes.resolve_combat_outcome` → `judge_ending` / `apply_ending` |
| 測試 | `scripts/test_ending_flow.py` + `scripts/test_combat_flow.py`（109 項） |
| DB 拆出 | `database.py`（Phase 2 技術債，已完成） |

### 下一步（營會後 / Gemini review 後）

1. Gemini review Phase 1 diff（`services/ending.py`、`player_status.py`、combat 路徑）
2. GM `/gm` ending override + `gm_audit` log
3. Good Ending narrative + Salvio Boss（Phase 3）
4. 前端 exponential backoff（Wi‑Fi 不穩）

---

## 2026-06-29 — Combat Killing Blow HP/Settlement Bug 修復（方案1）

**問題**：低 HP 練習敵人（`practice_iggy_01_quick`，48 HP）+ 主角自動 Zoo 極易一輪秒殺。`submit_action` 喺 `winner == "squad"` 時直接 return `build_victory_outcome_payload()`（極簡，無 `round_settlement`、`enemy.hp`、`log_entries`），前端 `submitAction()` 見 `data.outcome` 即跳 `finishCombatVictoryFromPayload()`，跳過 `showFullRoundSettlement()` + `syncEnemyHpDisplay()`。DB 正確但 UI 唔顯示 HP 下降同完整結算 modal。

**決策**：採用**方案1（後端為主）**

- killing blow 用 `build_victory_outcome_response()`：合併 `round_settlement` + `enemy.hp=0` + `log_entries` + victory narrative
- 前端 `finishCombatVictoryFromPayload`：若有 settlement，先顯示結算 modal，再顯示勝利
- 測試：`test_solo_killing_blow_practice_quick` + killing blow assert settlement

**Trade-off**：victory payload 稍大；前端改動輕微；polling 穩定。

**影響範圍**：`routes/combat.py`、`models/combat.py`、`templates/index.html`、`scripts/test_combat_flow.py`

**驗證**：`bash scripts/pre_deploy_checks.sh` 全綠；Henry 實機 `practice_iggy_01_quick` checklist

**狀態**：`3c89f62` 已 deploy；**實機未通過（reopened）** — 見 `bug_log` REPORT §10；下一輪修 poll `outcome` 捷徑

---

## 變更紀錄

| 日期 | Commit | 摘要 |
|------|--------|------|
| 2026-06-29 | `fc72077` | Phase 1+2 初版：ending、combat_outcomes、database.py |
| 2026-06-29 | `c1768a1` | 修 combat import + test 隔離 |
| 2026-06-29 | `fd4e0e1` | Model bootstrap fallback（encounters_dir、default_protagonist） |
| 2026-06-29 | （本 commit） | Grok Phase 1 spec 補齊：apply_ending、trauma_summary、test_ending_flow、decisions_log |