# Oikonomia — Decisions Log

> **SSOT**：Google Drive `oikonomia/` 同步本 repo · 重大架構決定記錄於此  
> **讀者**：Grok（方向）、Grok Build（實作）、Gemini（review）、Tak（決策）

---

## 2026-07-22 — 設定1（Iggy Arc）落地

| 決策 | 內容 | 狀態 |
|------|------|------|
| 劇情 SSOT | `data/cosmos_lore.py`（法則／陣營／角色矩陣／六幕） | ✅ |
| Stage 映射 | Act1→stage0；Act2→1；Act3–4→2；Act5–6→3；門檻 2／5／8 任務 | ✅ |
| 主線 Boss | `enc_iggy_act2_polis`（**survive 5 回合**）、`enc_iggy_act4_julian`、`enc_iggy_act6_salvio` | ✅ |
| 生存勝利 | `combat_settings.win_condition=survive` + `max_phases`；預設仍 `defeat_enemy` | ✅ |
| City Hunt GPS | 美孚／深水埗／九龍塘／彩虹用 **placeholder** 座標，實地 pin 後再改 | 待實地 |
| Where’s Iggy／迷宮圖 | 暫用既有 minigame 代替，正式素材後補 | 待素材 |
| Marah 主線 | 營會以 Iggy 強制路線為主；Marah 保留薄 stub | ✅ 刻意 |

**影響範圍**：`data/*`、`encounters/enc_iggy_act*.json`、`models/combat.py`（survival win）、`scripts/test_combat_flow.py`

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

## 2026-06-29 — Combat Killing Blow Bug Reopened（方案1 不足）

**問題**：方案1（`3c89f62`）只 fix 咗 `submit_action` victory 路徑，但 **poll 主入口**（`loadCombatStatus` `if (data.outcome)`）仍然直接 call `showCombatResult(data)` 並 return，完全 bypass `finishCombatVictoryFromPayload` 同 settlement 處理。

**根因定位**（已全面讀取 bug_log attachments `index.html`）：
- `loadCombatStatus` L~3484：`if (data.outcome) { ... showCombatResult(data); return; }`
- `updateCombatUI` L~3318：非 live 狀態時另一條 outcome 捷徑
- `finishCombatVictoryFromPayload` 雖然存在，但主要 poll 路徑永遠唔會走到

**新決策**：
- 採用「統一勝利入口」策略：所有 `outcome` 情況必須經過 `finishCombatVictoryFromPayload`
- 優先改動 `loadCombatStatus` 入面 `if (data.outcome)` 區塊
- 同步更新 `bug_log/REPORT.md` 同 `INDEX.md` 狀態

**影響範圍**：只改前端 `templates/index.html`（polling 勝利處理）
**風險**：低（只係 redirect 現有函數呼叫）
**驗證**：Henry 實機 `practice_iggy_01_quick` 一輪勝利 + settlement modal 正常顯示

---

## 2026-06-30 — Combat UX Delay Phase 2 優化（fixes 1+2+3）

**問題**：後端數據正確（`enemy_hp_sync_v6` + production 採證），但前端 timer stacking 造成 ~4s/round 體感 lag，尤其多回合 `practice_iggy_03_boundary`（140 HP）。血條即刻跳 + HP 數字 tween 420ms + settlement modal 1500ms + poll 凍結期間 DOM 唔更新，加強「lag」感。即使 data 正確，玩家仍覺得慢或「打唔入」。

**決策**：採納低風險組合修復 **1+2+3**（Tak 於 2026-06-30 確認；Grok Architect 記錄）：

1. **練習戰自動 fast**：`practice_*` encounter 自動使用 800ms settlement `modalDelay`，**跳過 HP tween**（只即時 set HP）。
2. **`syncEnemyHpDisplay(data, { animate: false })`**：round_resolved / poll 路徑即時更新數字（解決血條即刻跳、數字慢數不同步）。
3. **分拆 poll 凍結**：`settlementTimerPending` 只擋 full `updateCombatUI`，但**保留 HP sync 通道**（保留 v6 race fix 成果）。

**架構設計原則**：

- 細粒度 lock 而非全凍結：`settlementTimerPending` 期間仍容許 authoritative HP sync
- Practice encounter 自動 bypass 長 animation queue（`encounter_id` prefix `practice_`）
- 為之後 **configurable `combatSpeed` preset**（slow/normal/fast）鋪路
- 保持現有 victory settlement flow（`finishCombatVictoryFromPayload` + `showFullRoundSettlement`）不變

**影響範圍**：

- 主要：`templates/index.html`（`syncEnemyHpDisplay`、`loadCombatStatus`、`showFullRoundSettlement`）
- 次要：`routes/misc.py` marker `enemy_hp_sync_v7`

**風險評估**：**低**（patch 為主，無大重構）。最大風險係 poll 時序 — 已用細粒度 HP channel 緩解，避免 reintroduce v6 stale HP overwrite（`resolveAuthoritativeEnemyHp` + monotonic guard 保留）。

**營會實用性**：高。20 人西貢戶外營會，mobile + 可能不穩網絡；practice 每回合目標由 ~4s 減到 ~1–1.5s，提升 immersion 同「行動有即時後果」感覺。

**實作紀錄（Grok Build）**：

| Step | 狀態 | 備註 |
|------|------|------|
| 1 `syncEnemyHpDisplay` `{ animate }` option | ✅ | commit `66f70c6` |
| 2 round_resolved / poll 即時 HP | ✅ | `handleCombatRoundResolved`、`updateEnemyCombatStats` |
| 3 practice 自動 fast | ✅ | `isPracticeCombat` + `getEffectiveSettlementDelayMs` |
| 4 分拆 poll 凍結 | ✅ | `syncHpOnlyFromPoll`（等同 `hpSyncAllowedDuringSettlement`） |
| 5 modalDelay 扣減 hpAnimMs | ✅ | `max(120/200, baseDelay - hpAnimMs)` |
| 6 perf log | ✅ | `window.COMBAT_PERF_DEBUG` |

**驗證計劃**：

- CI：`scripts/test_combat_flow.py` — **188 通過 / 0 失敗**（`66f70c6`）
- Henry 實機（待）：`practice_iggy_03_boundary` HP 即時 + modal <1.5s；`practice_iggy_01_quick` 一輪殺 settlement 正常
- PA deploy 後：`curl /api/version` → `enemy_hp_sync_v7: true`

**狀態**：**已實作、待 deploy + Henry 實機確認** — 見 `bug_log/cases/2026-06-29_combat_enemy_hp_settlement/REPORT.md` §14

**記錄者**：Grok Architect（依 Tak 確認 1+2+3）· Grok Build 實作 `66f70c6`

---

## 變更紀錄

| 日期 | Commit | 摘要 |
|------|--------|------|
| 2026-06-29 | `fc72077` | Phase 1+2 初版：ending、combat_outcomes、database.py |
| 2026-06-29 | `c1768a1` | 修 combat import + test 隔離 |
| 2026-06-29 | `fd4e0e1` | Model bootstrap fallback（encounters_dir、default_protagonist） |
| 2026-06-29 | — | Grok Phase 1 spec 補齊：apply_ending、trauma_summary、test_ending_flow、decisions_log |
| 2026-06-30 | `66f70c6` | Combat UX Delay Phase 2（fixes 1+2+3）；`enemy_hp_sync_v7` |
| 2026-06-30 | — | **取消**戰鬥動畫 delay 設計 → `combat_instant_settlement`（即時 HP、即時戰果 modal、零擲骰 pause、移除設定頁結算延遲） |
| 2026-06-30 | `cc5671d` | Combat flow v2–v5 + settlement_breakdown_v1；Henry sub-problem patch |
| 2026-06-30 | `ebe49ff` | `combat_flow_v6`：一輪擊殺必出 settlement modal |
| 2026-06-30 | `12e1edd` | `combat_flow_v7`：勝利結算停 poll、確認後唔重彈；**BUG-2026-001 resolved**（Henry 實機） |
| 2026-06-30 | — | Phase 1.5 Step 1 spec 鎖定；Henry instant settlement 專項 checklist（§17） |
| 2026-07-21 | — | **全線強制 Iggy**：`FORCED_ROUTE=iggy`；`data/route_config.py` + SSOT + UI + docs |
| 2026-07-21 | — | **Zoo 階段解鎖**：`ZOO_UNLOCK_STORY_STAGE=2`；未達階段隱藏 UI／拒絕 use_zoo／主角 AI 唔用 Zoo |

## 2026-06-30 — 取消戰鬥動畫 Delay 設計

**決策（Tak）**：整套 artificial delay（結算 modal 等待、HP tween、練習戰 fast path、設定頁「傷害結算延遲」）**全部移除**。

**改為**：
- `combat_instant_settlement`：回合結算後 HP 同「本回合戰果」modal **即時**
- 擲骰 `pauseMs = 0`（仍保留短 roll 動畫，預覽即刻載入）
- 敵血條移除 CSS `transition` 延遲

**保留**：v6 race fix（`combatAwaitingSettlementAck`、`queueVictoryDuringSettlement`、`syncHpOnlyFromPoll`）。

---

## 2026-06-30 — Combat Flow v2–v5 + Settlement Breakdown v1（`cc5671d`）

**決策（Tak 確認）**：code 已推進至 `12e1edd`（GitHub `main`；PA 以 `curl /api/version` 為準）。Henry 實機 checklist 全通過 → **BUG-2026-001 resolved**（2026-06-30）。

| Commit / Marker | 實際內容（以 code 為準） |
|-----------------|--------------------------|
| `387c89b` `combat_flow_v2` | 精簡「傷害結算」modal；按「確定」先喺主畫面扣血 |
| `03cf917` `combat_flow_v3` | **取消**「本回合預計傷害」— 唔再 call `preview_action`；擲骰後直接確認提交 |
| `46cc3a5` `combat_flow_v4` | 已確認 `round_resolved` poll 解鎖下一回合；`resetCombatSessionState` 防第二場卡住 |
| `c621354` `settlement_breakdown_v1` | 結算畫面：Player／主角／隊友 輸出＋承受＋敵人總計（`models/combat.py` `breakdown`） |
| `cc5671d` `combat_flow_v5` | 勝利確認後 `victorySettlementAcknowledgedCombatId` + `victoryFinalizeInProgress` 防重複結算 modal |

**Henry 新 sub-problem（2026-06-30 回報）**：
- 勝利後仍見 1～2 次傷害結算 → `combat_flow_v5` patch
- 界線共生影第二場／第二回合無反應 → `combat_flow_v4` patch

| `ebe49ff` `combat_flow_v6` | 一輪擊殺必出 settlement modal（唔跳過） |
| `12e1edd` `combat_flow_v7` | 勝利結算期停 poll；`isVictoryFlowLocked` 防確認後重彈 |

**原則（Architect 同 Tak 一致）**：
- BUG-2026-001 **resolved**；營會前 P0 = 穩定性 monitoring，唔開新功能
- **暫停**重複 poll／monotonic guard patch（已多輪驗證；再現開新子議題）
- 保留 instant settlement（無人工 delay）
- 大檔 review 用 `bug_log/.../GEMINI_PACKET.md`，唔好成份讀 `index.html`

**影響範圍**：`templates/index.html`（主）、`models/combat.py`（`breakdown`）、`routes/misc.py`（markers）

**Henry checklist**（單人 Iggy，`PLAYER-75406` · 2026-06-30 Safari · **全通過**）：
- [x] `practice_iggy_04_marathon`：贏咗 → 結算只 1 次 →「確定，查看勝利」→ 直接勝利畫面
- [x] `practice_iggy_03_boundary`：R1 確定 → R2 攻擊有反應；打完再開同一場正常
- [x] 結算 modal 有 Player／主角／隊友分類 + 敵人總計

**記錄者**：Grok Architect（Tak 確認）· Grok Build 實作 v2–v7 · Henry 實機 resolved

---

## 2026-06-30 — Henry instant settlement 專項 checklist（線 A · **通過**）

**決策（Architect + Tak 鎖定）**：instant settlement 專項驗證完成。

**Encounter**：`practice_iggy_01_quick` → `practice_iggy_03_boundary`

**Henry 結果（2026-06-30）**：checklist **OK** — HP 即時、modal <1.5s、體感「打完有反應」

**殘留（Tak 回報 · 需 v8 patch）**：
- `practice_iggy_01_quick`（速戰情緒殘影）：有時攻擊後**完全無**傷害結算 modal
- 勝利確認後**偶發**再彈一次傷害結算

**修復**：`combat_flow_v8`–`v10` — settlement guard + **final hit 過渡**（`resolveEnemyHpAfter` / `isFinalHitOrVictory`）；confirm 後唔再 stuck

---

## 2026-06-30 — Combat Settlement Modal Bug（instant settlement 後遺症）

**問題**（Tak + Henry 實測）：
- 單人隊「速戰情緒殘影」攻擊後完全無傷害結算 modal
- 勝利後重複彈 settlement modal
- **練習・情緒寄生影**：第一次攻擊 settlement 後無法再行動（敵已死、無勝利畫面）
- 已 deploy `combat_engine.py`（`98441cd`）+ instant settlement；console 無 error；後端測試全綠

**診斷**：
- 前端多入口（poll、`handleCombatRoundResolved`、`finishCombatVictoryFromPayload`）instant 模式下 timing 改變
- **Final hit stuck**：`round_settlement.enemy_hp_after=0` 但 `enemy.hp` 未 sync → 當普通回合 settlement，confirm 後 `my_state.submitted` 鎖住按鈕
- 與 killing blow + poll 路徑問題同源

**決策（Tak 確認）**：
- 502 已解決（Web Reload）
- Frontend patch 只改 `templates/index.html`（v8–v10）
- 驗證：`practice_iggy_02_leech`（情緒寄生影）+ `practice_iggy_01_quick` killing blow

**執行次序**：
1. ~~502~~ ✅
2. v8–v10 frontend patch ✅
3. Henry 實機驗證 ⏳
4. Phase 1.5 Step 2 `trauma_service.py`（營會後）

**記錄者**：Grok Architect（Tak 2026-06-30）· Grok Build 實作 v10  
**狀態**：patch pushed，待 Henry 驗證

**詳細**：`bug_log/.../REPORT.md` §17–§18

---

## 2026-06-30 — Phase 1.5 Step 1：`services/combat_engine.py`（線 B · 已鎖定 spec）

**決策（Architect + Tak）**：營會後／低風險窗口抽取 `models/combat.py` 純計算層；**唔改行為**，只搬邏輯。

| 項目 | 內容 |
|------|------|
| **新檔** | `services/combat_engine.py`（目標 ≤450 行） |
| **職責** | 傷害計算、骰子倍率、defend 計數、單回合 `resolve_round_calculation` |
| **禁止** | 讀 DB、改 state、import `services.ending` / trauma side effects |
| **dataclass** | `Combatant`、`RoundResult` |
| **常數** | `COMBAT_ATTACK_BASE_DAMAGE=10`、`DEFEND_TEAM_DAMAGE_FACTOR=0.5`；骰子表 `{0:0, 1:1, 2:1.5, 3:2}`（同 `app.py`） |
| **行為 SSOT** | 必須同 `models/combat.py` 現有 `calculate_attack_damage` / `calculate_incoming_damage` / `dice_multiplier` 一致 |
| **測試** | `scripts/test_combat_engine.py` + 現有 `test_combat_flow.py` 仍全綠 |
| **下一步** | Step 2 `trauma_service.py`、Step 3 `protagonist_combat.py`、Step 4 `combat_flow.py`（營會後） |

**完整 spec**：`ARCHITECTURE_ROADMAP.md` § Phase 1.5

**實作（2026-06-30）**：`services/combat_engine.py` + `models/combat.py` 委派；`scripts/test_combat_engine.py`；`pre_deploy_checks` 全綠。行為不變。**Spec 已確認鎖定**（Architect + Tak）。

---

## 2026-06-30 — 確認 Combat + Trauma + Ending 細粒度架構重構

**決策（Grok Architect + Tak）**：為降低 context window 負擔，將 `models/combat.py`（~1750 行）與 trauma/ending 牽扯邏輯拆入 `services/` 層。

### Context 管理原則

| 原則 | 內容 |
|------|------|
| SSOT | Google Drive `oikonomia/`；chat 唔 paste 整檔 |
| 每輪 scope | 1–2 個 module |
| 大 refactor 前 | 更新 `ARCHITECTURE_ROADMAP.md` + `decisions_log.md` |
| 複雜域 | Combat / Protagonist / Trauma / Ending 繼續拆細 |

### 目標模組（Phase 1.5）

| 模組 | 職責 | 狀態 |
|------|------|------|
| `services/combat_engine.py` | 純計算（傷害、骰子、defend、round calc） | ✅ Step 1 完成（`98441cd`） |
| `services/trauma_service.py` | `apply_trauma`、band、narrative fragment | ⏳ Step 2 spec 待 Architect |
| `services/protagonist_combat.py` | Iggy/Marah control、AI 行動 | ⏳ Step 3 |
| `services/combat_flow.py` | round 編排 + side effects | ⏳ Step 4 |
| `services/ending.py` | judge + apply + preview（維持） | ✅ 已有 |

### 建議資料結構（Step 2+）

```python
@dataclass
class TraumaEvent:
    timestamp: datetime
    delta: int
    reason: str
    narrative_fragment: str | None
    band: str  # low | medium | high

@dataclass
class ProtagonistCombatState:
    protagonist_id: str
    is_participating: bool
    control_level: float
    last_action: str | None
    trauma_impact_this_round: int
```

### 系統流程（目標）

```
submit_action → combat_flow.resolve_round()
  → combat_engine.calculate_round_outcome()
  → trauma_service.apply_trauma_if_needed()
  → protagonist_combat.update_control_status()
  → ending_orchestrator.judge_ending()（如需要）
  → round_settlement payload（instant UI）
```

### 營會前約束

- P0 = 穩定性（BUG-2026-001 monitoring + v8 settlement patch）
- 唔開新功能；Phase 1.5 Step 2+ 營會後
- `combat_instant_settlement` 只影響 UI；trauma/ending 後端時機不變

**記錄者**：Grok Architect · Tak 確認 · Grok Build 實作 Step 1

---

## 2026-07-02 — Render.com 遷移（Starter / Singapore）

| 決策 | 內容 | 狀態 |
|------|------|------|
| 主機 | **Render Starter**（Singapore）取代 PA 為營會正式環境；PA 暫留後備 | ✅ 完成 |
| 持久化 | `DATA_DIR=/data` + 1GB disk；DB `oikonomia.db`、上傳 `uploads/` | ✅ Shell 匯入完成 |
| 程序 | gunicorn `wsgi:application`；`preDeployCommand` → `render-predeploy.sh` | ✅ 運行中 |
| 密鑰 | `/data/.secret_key`、`.gm_pin`（或 Dashboard env） | ✅ 已匯入 |
| Deploy 同步 | push `main` → CI tests → Deploy Hook → `/api/version` 驗證 | ✅ CI + `render-sync.sh` |
| Cutover | 正式流量已指向 Render；PA 保留 48h rollback | ✅ |

**實測（2026-07-02）**：https://oikonomia.onrender.com TTFB ~0.15s；`db_path` → `/data/oikonomia.db`；`render: true` ✅。Secret gist `978ddde…` 已刪除。Service ID `srv-d8v8i7cvikkc73fbsv0g`。

**記錄者**：Tak（升級 Starter）· Grok Build（Blueprint + deploy 腳本）

---

## 2026-07-21 — 全線強制 Iggy 路線（營會設定）

| 決策 | 內容 | 狀態 |
|------|------|------|
| 路線政策 | **所有玩家／隊伍必定 Iggy 路線**；關閉 Marah 選擇 | ✅ 已實作 |
| 設定位置 | `data/route_config.py` → `FORCED_ROUTE`（預設 `"iggy"`） | ✅ |
| 回滾開關 | `OIKONOMIA_FORCED_ROUTE=`（空字串）恢復雙線；`=marah` 可強制 Marah | ✅ |
| SSOT | `official_team_route` / `official_squad_route` 喺 force 模式永遠回傳 forced route | ✅ |
| 持久化 | App 啟動 `apply_forced_route_to_all()` 回填所有 `teams` / `squads`；`/status` 補寫 drift | ✅ |
| 建隊 | 玩家／GM 建隊自動 `route=iggy`，唔再要求手動揀 | ✅ |
| API 守衛 | `set_route` / `team/set_route` / GM `set_team_route` 拒絕非 forced 路線 | ✅ |
| UI | 隱藏 Marah 雙線 picker；dashboard badge 顯示 Iggy | ✅ |
| 版本標記 | `/api/version` → `forced_route: "iggy"`、`markers.forced_route_iggy: true` | ✅ |

**影響檔案**：
- `data/route_config.py`（新）
- `models/team.py`、`services/player_status.py`
- `routes/team.py`、`routes/gm.py`、`routes/misc.py`、`app.py`
- `templates/index.html`
- 本檔 + `UPDATE_LOG.md` + `AGENT_HANDOFF.md`

**Trade-off**：
- Marah encounter／故事內容仍保留喺 codebase，但玩家流程唔會進入
- 依賴 dual-route 嘅測試需設 `OIKONOMIA_FORCED_ROUTE=` 先跑 Marah case

**備份**：改動前已觸發 Google Drive backup（`backup-oikonomia` skill）

**記錄者**：Tak 決策 · Grok Build 實作

---

## 2026-07-21 — Zoo 能力按故事階段解鎖

| 決策 | 內容 | 狀態 |
|------|------|------|
| 開局 | 玩家同主角 **唔能** 用 Zoo；戰鬥 UI **隱藏** Zoo 按鈕 | ✅ |
| 解鎖 | Team `story_stage >= ZOO_UNLOCK_STORY_STAGE`（預設 **2**） | ✅ |
| SSOT | `effective_allow_zoo` = stage unlocked **且** encounter `allow_zoo` | ✅ |
| Config | `data/combat_feature_config.py`；env `OIKONOMIA_ZOO_UNLOCK_STAGE`（`0`=一開始就開） | ✅ |
| 測試 | CI `OIKONOMIA_ZOO_UNLOCK_STAGE=0` 以免 regression 被鎖 | ✅ |

**影響**：`models/combat.py`、`routes/combat.py`、`services/player_status.py`、`static/js/combat/views/action_view.js`、`settlement.js`、`templates/index.html`、`/api/version`

**記錄者**：Tak 決策 · Grok Build 實作