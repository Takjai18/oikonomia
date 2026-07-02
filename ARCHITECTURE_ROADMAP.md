# Oikonomia — Architecture Roadmap

> **來源**：Grok 方向建議（2026-06-29）· **對照 commit**：`d1e47d4`  
> **讀者**：Grok（方向）、Grok Build（實作）、Gemini（review）、Tak（決策）  
> **營會約束**：~20 人、3 日 2 夜西貢戶外、**Render Starter（新加坡）為主、PA 後備**、穩定性 > 新功能

---

## Hosting（2026-07-02）

| 環境 | URL | 角色 | 資料路徑 |
|------|-----|------|----------|
| **Render Starter** | https://oikonomia.onrender.com | **正式（現行）** | `/data` 持久碟（`DATA_DIR=/data`） |
| **PythonAnywhere** | https://takjai.pythonanywhere.com | 後備（rollback） | `~/oikonomia/data/` |

**Render 服務**：`srv-d8v8i7cvikkc73fbsv0g` · repo `Takjai18/oikonomia` · branch `main` · Blueprint `render.yaml`。

**遷移原則**

1. SQLite + 上傳相片必須在 **Persistent Disk**（`/data`），唔好用 `project/src/data`（redeploy 會清）。
2. 生產用 **gunicorn**（`wsgi:application`），唔用 `python3 app.py`。
3. `SECRET_KEY` / `GM_PIN` 與 PA 一致（搬 `data/.secret_key`、`.gm_pin`），避免玩家 session 失效。
4. Cutover 已完成（2026-07-02）；PA 保留 48h 作 rollback。
5. 每次 push `main` 後 CI 觸發 Deploy Hook；Grok Build 必須 `curl /api/version` 確認與 commit 一致。

**腳本**：`deploy/render-predeploy.sh`、`deploy/render-sync.sh`、`deploy/render-check.sh`；PA 後備 `deploy/pa-update.sh`。

---

## 設計目標

| 目標 | 含義 |
|------|------|
| **一致性** | Protagonist / Trauma / Ending 以 DB 為 SSOT，`/status` 統一聚合 |
| **可維護性** | 結算編排在 Service 層；重大決策記本文 + Drive 備份 |
| **可靠性** | DB 鎖、前端 resolving poll、GM override + log |
| **神學整合** | Trauma 對應軟弱中得力；Ending 體現救贖／盼望（非純懲罰） |

---

## 現況評估（2026-06-29）

### 已有優勢 ✅

| 模組 | 現況 |
|------|------|
| **Combat** | `models/combat.py` 原子 resolving 鎖、`with_db_retry`；server dice；前端 phase lock + 1s poll（`d1e47d4`） |
| **Protagonist** | `protagonist_states` 表；stage≥3 或 JSON flag 玩家操控；AI fallback |
| **Trauma** | 瀕死 +1 `trauma_count`；>3 → `bad_ending`；`test_combat_flow` 有 regression |
| **Ending** | `teams.ending_type`；`get_team_ending_state()`；勝利時 `apply_trauma_bad_ending_victory` |
| **Outcome 事務** | `apply_encounter_success/failure` 已包 `immediate_transaction`（`d1e47d4`） |
| **Status** | `/status` 經 `build_player_status()` 回傳 `protagonists` + `ending` |

### 待改善 ⚠️

| 問題 | 現況 |
|------|------|
| **Ending 判斷分散** | `protagonist.py`、`combat.py` `_end_combat`、`encounter_outcomes.py` 各有一部分 |
| **Outcome 編排分散** | `_end_combat` 直接呼叫 success/failure/trauma_bad_ending，無單一 orchestrator |
| **Trauma 觸發單一** | 主要來自瀕死；encounter narrative 條件觸發未擴展 |
| **Good Ending** | 正面結局 narrative／演出待寫（AGENT_HANDOFF 已知待辦） |
| **GM override** | 可調 stat；trauma/ending 強制覆寫 + audit log 未完整 |
| **前端離線** | 無 offline queue（營會 Wi‑Fi 不穩時靠 polling 重試） |

---

## 目標架構（高層）

```mermaid
flowchart LR
    subgraph routes [Routes]
        CombatAPI["/combat/*"]
        StatusAPI["/status"]
        GMAPI["/gm/*"]
    end
    subgraph services [Services - 目標擴充]
        OutcomeOrch["combat_outcomes.py"]
        EndingSvc["ending.py"]
        PlayerStatus["player_status.py"]
    end
    subgraph models [Models - 規則]
        CombatM["combat.py"]
        ProtagonistM["protagonist.py"]
        EncounterOut["encounter_outcomes.py"]
    end
    CombatAPI --> CombatM
    CombatM --> OutcomeOrch
    OutcomeOrch --> EncounterOut
    OutcomeOrch --> ProtagonistM
    OutcomeOrch --> EndingSvc
    StatusAPI --> PlayerStatus
    PlayerStatus --> ProtagonistM
    PlayerStatus --> EndingSvc
    GMAPI --> EndingSvc
```

**原則**：Models 保留規則與 DB；Services 負責「戰鬥結束後做咩」的編排；Routes 薄層。

---

## 分階段計劃

### Phase 1 — 營會前可做（低風險，~2h）

| # | 任務 | 產出 | 風險 |
|---|------|------|------|
| 1.1 | **`services/ending.py`** | `judge_ending(team_id)` 整合 `check_ending_condition`、`teams.ending_type`、trauma 總數 | 低 |
| 1.2 | **`protagonist.apply_trauma(delta, reason)`** | 統一入口 + reason log（可先寫 combat log 或 DB 欄位） | 低 |
| 1.3 | **`/status` 強化** | 加 `trauma_level`、`ending_preview`（玩家可見摘要；GM 細節仍用 `/gm`） | 低 |
| 1.4 | **`_end_combat` 改呼叫** | 勝利後改經 `judge_ending` / 薄 wrapper，行為不變 | 低 |

**唔做（Phase 1）**：大規模搬移 `models/combat.py`、Event Bus、拆 `index.html`。

### Phase 1.5 — Context 减负（營會後優先 · Step 1 可先做）

> **目標**：單檔 400–600 行；Grok Build 改 combat 只 read 2–3 小檔。  
> **原則**：抽取時**行為不變**；先 engine，後 flow orchestrator。

| Step | 模組 | 職責 | 原本屬於 | 優先 |
|------|------|------|----------|------|
| **1** | `services/combat_engine.py` | 純計算：傷害、骰子倍率、defend、`resolve_round_calculation` | `models/combat.py` L170–249 等 | **P0** |
| 2 | `services/trauma_service.py` | `apply_trauma`、band、narrative fragment | `protagonist.py` + `ending.py` | P1 |
| 3 | `services/protagonist_combat.py` | control、AI 行動、trauma→control | `protagonist.py` + `combat_outcomes.py` | P1 |
| 4 | `services/combat_flow.py` | 開始戰鬥、submit、round 推進、settlement 觸發 | `routes/combat.py` + `combat_outcomes.py` | P1 |
| 5 | 測試 + `decisions_log` | regression 全綠 | — | P0 |

#### Step 1 介面（已鎖定 · 2026-06-30）

```python
@dataclass
class Combatant:
    id: str
    power: int
    intellect: int
    resilience: int
    sanity: int = 100
    item_bonus: int = 0

@dataclass
class RoundResult:
    damage_dealt: int
    damage_taken: int
    is_critical: bool
    dice_multiplier: float
    defender_count: int
    notes: List[str]
```

**必須函數**：`get_effective_attack_stat`、`calculate_attack_damage`、`calculate_incoming_damage`、`dice_multiplier`、`count_team_defenders`、`resolve_round_calculation`

**骰子**：`dice_result` 0–3，倍率表同 `app.py` `DICE_MULTIPLIERS`（唔用簡化 1–6 骰 spec）。

**測試**：`test_calculate_attack_damage_basic`、`test_resolve_round_calculation_with_defend`、`test_dice_multiplier_edge_cases`

### Phase 2 — 營會後／下個版本（半天）

| # | 任務 | 產出 |
|---|------|------|
| 2.1 | **`services/combat_outcomes.py`** | `resolve_combat_outcome(winner, team_id, encounter)` 統一 success/failure/trauma/ending |
| 2.2 | **Protagonist 狀態機** | enum：`normal` / `near_death` / `traumatized` / `resolved`（文件 + helper） |
| 2.3 | **Narrative 條件片段** | `data/narrative_stories.py` 擴展 trauma/ending 觸發 |
| 2.4 | **拆 `app.py` migrations** | → `database.py`（Gemini 技術債） |

### Phase 3 — 長期

- Event bus（僅當 encounter 類型 >10 或多系統整合時）
- 前端 offline queue + 提交重試
- Good Ending 完整演出 + Salvio Boss encounter

---

## 方案比較（Grok 建議摘錄）

| 方案 | 複雜度 | 維護性 | 營會適用 | 建議 |
|------|--------|--------|----------|------|
| 現況（分散） | 低 | 中 | 中 | 已可上線；Phase 1 收斂 ending |
| **中央 Orchestrator** | 中 | 高 | **高** | **首選**（Phase 2） |
| 全 Event Bus | 高 | 最高 | 低（3 日營會） | 暫緩 |

---

## 風險與緩解

| 風險 | 緩解 |
|------|------|
| 併發／網路 | ✅ DB 鎖 + resolving 1s poll；可加 submit 指數退避 |
| GM 調整 | GM 調 stat 已有；待加 trauma/ending override + `gm_audit` log |
| Trauma 太懲罰 | 維持 >3 才 bad_ending；narrative 強調「軟弱中得力」 |
| Context 壓力 | 本文 + `AGENT_HANDOFF` + `CURRENT_STRUCTURE`；決策記下文 |

---

## 決策日誌

| 日期 | 決策 | 負責 |
|------|------|------|
| 2026-06-29 | 採 Grok 三分工：Grok 方向 / Grok Build 實作 / Gemini review | Tak |
| 2026-06-29 | 戰鬥模組標記 Production Ready（Gemini §15）；優先做 Phase 1 收斂 ending | Grok + Grok Build |
| 2026-06-29 | Phase 2 Orchestrator 延後至營會後；營會前不拆 `index.html` | Grok Build 建議 |
| 2026-06-29 | **Phase 1 完成**：`services/ending.py`、`apply_trauma(reason)`、`/status` trauma_level + ending_preview、`_end_combat` 經 `judge_ending` | Grok Build |
| 2026-06-29 | **Phase 2 完成**：`services/combat_outcomes.py`、`ProtagonistLifeState`、`CONDITIONAL_NARRATIVE_FRAGMENTS`、`database.py` 拆出 migrations | Grok Build |
| 2026-06-29 | Grok Phase 1 spec 確認：營會前只做低風險 ending 收斂；Drive SSOT | Tak + Grok |
| 2026-06-29 | **Phase 1 spec 補齊**：`apply_ending`、`trauma_summary`、`protagonist_control_status`、`OIKONOMIA_ENDING_ENABLED`、`test_ending_flow.py`、`decisions_log.md` | Grok Build |
| 2026-06-30 | **BUG-2026-001 resolved**（`12e1edd`）：Combat UX instant settlement + v7；Henry 實機通過；營會前 monitoring | Tak + Grok Build |
| 2026-06-30 | **Phase 1.5 Step 1 spec 鎖定**：`services/combat_engine.py` 抽取計劃；Henry instant settlement 專項 checklist | Grok Architect + Tak |

---

## 相關文檔

| 文檔 | 用途 |
|------|------|
| `AGENT_HANDOFF.md` | Grok Build 實作交接 |
| `CURRENT_STRUCTURE.md` | 目錄快照 |
| `GEMINI_REVIEW.md` | Review 清單與對照表 |
| `README.md` | 三角色分工 |