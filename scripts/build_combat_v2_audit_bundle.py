#!/usr/bin/env python3
"""Generate COMBAT_V2_AUDIT_BUNDLE.md (self-contained Gemini audit packet)."""
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "COMBAT_V2_AUDIT_BUNDLE.md"
OUT_R11 = ROOT / "COMBAT_V2_R11_PARTIAL_BUNDLE.md"

FRONTEND_FILES = [
    "static/js/combat/bootstrap.js",
    "static/js/combat/index.js",
    "static/js/combat/state_machine.js",
    "static/js/combat/api_client.js",
    "static/js/combat/settlement.js",
    "static/js/combat/render.js",
    "static/js/combat/selectors.js",
    "static/js/combat/toast.js",
    "static/js/combat/views/hud_view.js",
    "static/js/combat/views/action_view.js",
    "static/js/combat/views/dice_modal_view.js",
    "static/js/combat/views/settlement_view.js",
    "static/js/combat/views/escape_result_view.js",
    "static/js/combat/views/submitting_overlay.js",
    "static/js/combat/views/victory_view.js",
    "static/js/combat/views/item_select_view.js",
]

BACKEND_FILES = [
    "routes/combat.py",
    "routes/gm.py",
    "routes/items.py",
    "models/combat.py",
    "models/item.py",
    "models/protagonist.py",
    "services/combat_outcomes.py",
    "services/trauma_service.py",
    "services/narrative_orchestrator.py",
    "services/global_events.py",
    "combat_greenfield_final.md",
    "app.py",
    "routes/misc.py",
    "templates/combat_screen.html",
    "templates/combat_v2_harness.html",
    "tests/combat_state_machine.test.js",
    "tests/combat_v2.spec.js",
    "playwright.config.cjs",
    "scripts/test_combat_flow.py",
    "scripts/pre_deploy_checks.sh",
]


def read_file(rel: str) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else f"# MISSING: {rel}\n"


def extract_index_combat_bridge() -> str:
    lines = (ROOT / "templates/index.html").read_text(encoding="utf-8").splitlines()
    chunks = []

    def grab(start_pat, end_pat=None, max_lines=400):
        start = next((i for i, l in enumerate(lines) if start_pat in l), None)
        if start is None:
            return
        end = len(lines)
        if end_pat:
            for j in range(start + 1, min(start + max_lines, len(lines))):
                if end_pat in lines[j]:
                    end = j + (1 if end_pat.startswith("async function") else 0)
                    break
        chunks.append("\n".join(lines[start:end]))

    grab("<!-- Combat -->", "<!-- Team 區塊 -->")
    grab("// ── Combat lobby bridge", "async function rescueNearDeath")
    grab("async function rescueNearDeath", "let currentStory = null")
    grab("async function finishSessionRestore", "async function fallbackToNormalSession")
    grab('<script type="module" src="/static/js/combat/bootstrap.js">', None, 5)
    return "\n\n".join(chunks)


def extract_app_combat_types() -> str:
    text = read_file("app.py")
    start = text.find("COMBAT_ACTION_TYPES = (")
    end = text.find("DICE_MULTIPLIERS", start)
    return text[start:end].strip() if start != -1 else "# COMBAT_ACTION_TYPES not found"


def append_file(buf: list, rel: str, content: str | None = None):
    body = content if content is not None else read_file(rel)
    buf.append(f"\n\n===== FILE: {rel} =====\n\n")
    buf.append(body.rstrip())
    buf.append("\n")


def extract_gemini_context_protocol() -> str:
    text = read_file("GEMINI_REVIEW.md")
    start = text.find("## 0.5 Context 管理協議")
    end = text.find("## 1. Review 前必讀", start)
    if start == -1:
        return "# MISSING: GEMINI_REVIEW.md §0.5\n"
    return text[start:end].strip()


def extract_handoff_context_protocol() -> str:
    text = read_file("AGENT_HANDOFF.md")
    start = text.find("## Context 管理協議")
    end = text.find("### Bug Log", start)
    if start == -1:
        return "# MISSING: AGENT_HANDOFF.md Context section\n"
    return text[start:end].strip()


def main():
    today = date.today().isoformat()
    index_lines = len((ROOT / "templates/index.html").read_text(encoding="utf-8").splitlines())
    combat_flow_exists = (ROOT / "static/js/combat_flow.js").exists()

    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            text=True,
        ).strip()
    except Exception:
        ref = ROOT / ".git" / "refs" / "heads" / "main"
        head = ref.read_text(encoding="utf-8").strip()[:7] if ref.exists() else "unknown"

    header = f"""# COMBAT_V2_AUDIT_BUNDLE v12（營會 SSOT · R11/R12 封頂版）

> **用途**：**首次 onboarding** 或重大版本錨點 — Copy 全文到 Gemini 建立 Baseline  
> **日期**：{today} · **commit**：`{head}`  
> **實作者**：Grok Build（Combat V2 Greenfield · Phase 2 封頂）  
> **Baseline**：`combat_greenfield_final.md`（附錄內含全文）  
> **上一輪**：R11 現場風險 A/B/C ✅ · R12-A～D 橋接/DB/編排/INV ✅  
> **本輪**：R11/R12 審計修復已落地；下一輪用 **Partial Bundle** 做 regression 審計  
> **Feature Flag**：`COMBAT_V2=1` · `OIKONOMIA_SHOW_TEST_ENCOUNTERS=0`（production）

> ⚠️ **後續局部審計唔貼本檔全文** — 見 `COMBAT_V2_PARTIAL_INDEX.md` 選 R11 / R12-A～D  
> 生成：`python3 scripts/build_combat_v2_partial_bundles.py`

---

## 0. 給 Gemini 的指令（R12 封頂 — Baseline / 錨點 Audit）

1. **PASS/FAIL** 總評 + 健康度 **X/10**
2. **Context 協議**：後續用戶只貼單檔 Partial；本檔作 SSOT 引用
3. **已修對照**：`GEMINI_REVIEW.md` §17（R11/R12）— 唔好重複報已落地項
4. **下一輪建議 scope**（見 §0.1）— 新功能或 regression only

### 0.1 建議局部審計（用 Partial Bundle，唔貼全文）

| Bundle | 焦點 | 狀態（`{head}`） |
|--------|------|------------------|
| **R12-D** | settlement monotonic · INV-A～E | ✅ 已審已修 |
| **R12-A** | sessionStorage lock · restore 時序 | ✅ 已審已修 |
| **R12-B** | atomic `_end_combat` · WAL · purge actions | ✅ 已審已修 |
| **R12-C** | piercing floor · failed_escape · outcome 冪等 | ✅ 已審已修 |
| **R11** | GM override · timeout mutex · co-op CAS | ✅ 已審已修 |

**測試帳號**：Henry `PLAYER-75406`  
**Encounter**：`practice_iggy_04_marathon` · `test_protagonist_control`

---

## 1. Phase 2 功能狀態總表

| 功能 | 狀態 | 主要檔案 |
|------|------|----------|
| P2-1 戰鬥物品（power_up） | ✅ | `item_select_view.js`, `routes/items.py`, `models/item.py` |
| P2-2 Zoo UI + 暴走提示 | ✅ | `action_view.js`, `state_machine.js` ACTION_USE_ZOO, `combat_screen.html` |
| P2-3 主角代打（隊長專屬） | ✅ | `routes/combat.py` 403 gate, `index.js` asProtagonist, `action_view.js` toggle |
| P2-4 物品效果擴展（醫療/解控） | ✅ | `models/combat.py` use_item, `settlement_view.js` Breakdown |
| P2-5 雙人 Co-op E2E | ✅ | `tests/combat_v2.spec.js` T12, `state_machine.js` poll settlement |
| 真・GM 召喚 API | ✅ | `routes/combat.py` `/combat/summon_gm`, `services/global_events.py` |
| 超時自動防禦 | ✅ | `index.js` pollTick + `triggerTimeoutAutomaticDefense` |
| T13 非隊長代打阻擋 | ✅ | `tests/combat_v2.spec.js` T13, `test_non_leader_as_protagonist_rejected` |
| GM Override 後端網關 | ✅ | `routes/gm.py` `/gm/api/override_trauma_ending`, T14 403 gate |
| GM UI Bridge（嵌入式特權面板） | ✅ | `api_client.js`, `index.js`, `victory_view.js`, `bootstrap.js` |

---

## 2. Phase 1.5 編排層狀態

| 模組 | 狀態 | 職責 |
|------|------|------|
| `services/trauma_service.py` | ✅ | 創傷能帶 · 審計 log · bad_ending SSOT 鎖定 |
| `services/narrative_orchestrator.py` | ✅ | 戰後獎勵 · encounter_completions 等冪 · insight/unlocks |
| `services/combat_outcomes.py` | ✅ | 勝利/失敗編排入口 · 委派上述管線 |

---

## 3. 測試狀態（R12 · `{head}`）

```bash
npm run test:combat                                    # 17/17 pass
./venv/bin/python3 scripts/test_combat_flow.py         # 267/267 pass
./venv/bin/python3 scripts/test_db_hardening.py        # 11/11 pass
./venv/bin/python3 scripts/test_combat_engine.py       # 17/17 pass
./venv/bin/python3 scripts/test_combat_flow_orchestrator.py  # 4/4 pass
./venv/bin/python3 scripts/test_combat_concurrency.py
scripts/test_ending_flow.py                            # 23/23 pass
npm run test:e2e:v2                                    # T8–T14
```

---

## 4. 架構資料流（R11）

```
戰鬥勝利 → resolve_combat_outcome()
  ├─ judge_ending → trauma_bad_ending? → apply_trauma_bad_ending_victory
  └─ execute_post_combat_success_pipeline()  [IMMEDIATE TX · INV-C 等冪]
       ├─ insight_fragments · item rewards · encounter_completions
       └─ story stage snapshot

主角瀕死 → apply_protagonist_trauma_pipeline()  [IMMEDIATE TX]
submit_action → maybe_resolve_player_phase() → CombatItemConsumeBatch

GM 現場救援（瀕死面板）→ 三重點擊標題 → executeGmOverride()
  ├─ overrideTraumaEnding → /gm/api/override_trauma_ending  [gm_session_valid]
  └─ clear ending → COMBAT_RESET from COMBAT_FAILED → IDLE + START_POLL
```

---

## 5. 不變式防線（INV-A～E）

| ID | 規則 | 落地點 |
|----|------|--------|
| INV-A | Settlement 主觸發 `onSubmitSuccess`；co-op poll 例外 | `index.js` syncState |
| INV-B | `settlement_id` 冪等，不重複開 modal | `settlement.js` deriveSettlementId |
| INV-C | poll tick 被動，不主動製造 settlement | `state_machine.js` |
| INV-D | HP≤0 搶占中斷所有 UI | `handleAnyDeath` |
| INV-E | escape 失敗後仍顯示混合結算 | T8, `escape_result_view.js` |

---

## 6. PR-6 結構（回歸）

- `index.html` {index_lines} 行 · `combat_flow.js` {'已刪除' if not combat_flow_exists else '仍存在'}

---

## 7. Context 管理協議（摘錄）

> 全文見 `GEMINI_REVIEW.md` §0.5 · `AGENT_HANDOFF.md` · `README.md`

---

## 8. 完整原始碼附錄（R11）

> 由 `scripts/build_combat_v2_audit_bundle.py` 自動生成

"""

    buf = [header]
    append_file(buf, "GEMINI_REVIEW.md (§0.5 Context 協議摘錄)", extract_gemini_context_protocol())
    append_file(buf, "AGENT_HANDOFF.md (Context 協議摘錄)", extract_handoff_context_protocol())

    append_file(buf, "templates/index.html (PR-6 combat excerpts)", extract_index_combat_bridge())
    append_file(buf, "app.py (COMBAT_ACTION_TYPES excerpt)", extract_app_combat_types())

    for rel in FRONTEND_FILES:
        append_file(buf, rel)

    for rel in BACKEND_FILES:
        append_file(buf, rel)

    buf.append(f"\n\n---\n*End of COMBAT_V2_AUDIT_BUNDLE v12 · {today} · `{head}`*\n")

    OUT.write_text("".join(buf), encoding="utf-8")
    size_kb = OUT.stat().st_size / 1024
    print(f"Wrote {OUT} ({size_kb:.1f} KB, {len(OUT.read_text(encoding='utf-8').splitlines())} lines)")

    # Chain-generate all partial bundles + index
    import subprocess
    partial_script = ROOT / "scripts/build_combat_v2_partial_bundles.py"
    if partial_script.exists():
        subprocess.run(["python3", str(partial_script)], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()