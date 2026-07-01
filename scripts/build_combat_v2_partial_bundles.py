#!/usr/bin/env python3
"""
Generate themed COMBAT_V2 partial audit bundles for Gemini 【審計模式】.

Outputs:
  COMBAT_V2_PARTIAL_INDEX.md          — 選哪個 bundle、何時用
  COMBAT_V2_R11_PARTIAL_BUNDLE.md     — 營會現場風險（GM / 超時 / Co-op resolve）
  COMBAT_V2_R12_A_FRONTEND_BRIDGE.md  — 大廳橋接與 poll 隔離
  COMBAT_V2_R12_B_DB_HARDENING.md     — SQLite WAL / 髒數據 / SSOT
  COMBAT_V2_R12_C_STEP4_ORCHESTRATION.md — 純計算層 + 編排層
  COMBAT_V2_R12_D_INV_MONOTONIC.md    — INV-A～E 與弱網狀態機
"""
from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_file(rel: str) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else f"# MISSING: {rel}\n"


def extract_lines(rel: str, start: int, end: int) -> str:
    lines = read_file(rel).splitlines()
    if not lines or lines[0].startswith("# MISSING"):
        return lines[0] if lines else ""
    start_idx = max(0, start - 1)
    end_idx = min(len(lines), end)
    body = "\n".join(lines[start_idx:end_idx])
    return f"# {rel} (L{start}–L{end})\n\n{body}"


def extract_function_block(rel: str, def_name: str, extra_lines: int = 120) -> str:
    lines = read_file(rel).splitlines()
    start = next(
        (i for i, l in enumerate(lines) if l.startswith(f"def {def_name}") or f"async {def_name}" in l),
        None,
    )
    if start is None:
        return f"# MISSING: {def_name} in {rel}\n"
    end = start + 1
    while end < len(lines) and end < start + extra_lines:
        if end > start + 1 and lines[end].startswith(("def ", "async ", "@", "class ")):
            break
        end += 1
    return extract_lines(rel, start + 1, end)


def extract_js_method(rel: str, method_name: str, extra_lines: int = 80) -> str:
    lines = read_file(rel).splitlines()
    patterns = (f"  {method_name}(", f"  async {method_name}(")
    start = next((i for i, l in enumerate(lines) if any(p in l for p in patterns)), None)
    if start is None:
        return f"# MISSING: {method_name} in {rel}\n"
    end = start + 1
    depth = 0
    while end < len(lines) and end < start + extra_lines:
        line = lines[end]
        depth += line.count("{") - line.count("}")
        if end > start and depth <= 0 and line.strip() == "}":
            end += 1
            break
        end += 1
    return extract_lines(rel, start + 1, end)


def extract_js_function(rel: str, fn_name: str, extra_lines: int = 60) -> str:
    lines = read_file(rel).splitlines()
    patterns = (f"function {fn_name}(", f"async function {fn_name}(")
    start = next((i for i, l in enumerate(lines) if any(p in l for p in patterns)), None)
    if start is None:
        return f"# MISSING: {fn_name} in {rel}\n"
    end = start + 1
    depth = 0
    while end < len(lines) and end < start + extra_lines:
        line = lines[end]
        depth += line.count("{") - line.count("}")
        if end > start and depth <= 0 and line.strip().startswith("}"):
            end += 1
            break
        end += 1
    return extract_lines(rel, start + 1, end)


def extract_index_bridge() -> str:
    lines = read_file("templates/index.html").splitlines()
    chunks = []

    def grab(start_pat: str, end_pat: str | None = None, max_lines: int = 200):
        start = next((i for i, l in enumerate(lines) if start_pat in l), None)
        if start is None:
            return
        end = min(len(lines), start + max_lines)
        if end_pat:
            for j in range(start + 1, end):
                if end_pat in lines[j]:
                    end = j + 1
                    break
        chunks.append("\n".join(lines[start:end]))

    grab("// ── Combat lobby bridge", "function isPlayerInActiveCombatV2")
    grab("function isPlayerInActiveCombatV2", "async function rescueNearDeath")
    grab("async function finishSessionRestore", "async function fallbackToNormalSession")
    grab("setInterval(() => {", None, 25)
    return "\n\n".join(chunks)


def write_bundle(path: Path, content: str) -> tuple[float, int]:
    path.write_text(content, encoding="utf-8")
    text = path.read_text(encoding="utf-8")
    return path.stat().st_size / 1024, len(text.splitlines())


def git_head() -> str:
    try:
        import subprocess as sp
        return sp.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            text=True,
        ).strip()
    except Exception:
        ref = ROOT / ".git" / "refs" / "heads" / "main"
        return ref.read_text(encoding="utf-8").strip()[:7] if ref.exists() else "unknown"


def build_index(today: str, head: str) -> str:
    return f"""# COMBAT_V2 Partial Audit Bundle 索引（Gemini 審計導航）

> **日期**：{today} · **commit**：`{head}`  
> **生成**：`python3 scripts/build_combat_v2_partial_bundles.py`

---

## 何時用哪個 Bundle？

| Bundle | 檔名 | 目的 | 何時貼給 Gemini | 大小級別 |
|--------|------|------|-----------------|----------|
| **Full SSOT** | `COMBAT_V2_AUDIT_BUNDLE.md` | **首次 onboarding / 重大版本錨點** — 建立完整 Baseline（前後端全文 + 規格 + 測試） | 新 Gemini 對話第一次審計；Phase 封頂前總審 | ~數 MB |
| **R11 現場風險** | `COMBAT_V2_R11_PARTIAL_BUNDLE.md` | **營會當日高風險路徑** — GM 特權面板、戶外超時防禦、Co-op 雙人同秒 resolve | 部署前最後一輪；懷疑現場卡死／雙擊／GM 救援 | ~30–50 KB |
| **R12-A 大廳橋接** | `COMBAT_V2_R12_A_FRONTEND_BRIDGE.md` | **Legacy index.html ↔ V2 模組交界** — 3s poll 隔離、`exitCombatScreen`、session restore fast-forward | 幽靈 modal、大廳與戰鬥畫面不同步、重連後卡 lobby | ~25–40 KB |
| **R12-B DB 硬化** | `COMBAT_V2_R12_B_DB_HARDENING.md` | **20 人併發資料層** — SQLite WAL、`combat_actions` 清理、主角 SSOT、session restore 後端 | `database is locked`、500 錯誤、主角 Dashboard 與戰鬥 HP 分裂 | ~20–35 KB |
| **R12-C Step4 編排** | `COMBAT_V2_R12_C_STEP4_ORCHESTRATION.md` | **純計算 + 戰後管線** — `combat_engine`、`combat_flow` INV-E、`combat_outcomes` 冪等 | 逃跑混合結算、勝利重複發獎、傷害公式極端值 | ~35–55 KB |
| **R12-D 不變式** | `COMBAT_V2_R12_D_INV_MONOTONIC.md` | **弱網狀態機 INV-A～E** — `settlement_id`、monotonic guard、`entrySyncPending` | 重複 settlement 彈窗、stale round、INV 違反 | ~30–45 KB |

---

## 審計協議（所有 Partial 共用）

1. **模式**：Gemini **【審計模式】** — 輸出 【Critical】→【High/Medium】→【Low】→ 健康度 **X/10**
2. **Baseline**：Partial 審計**假設** Gemini 已讀過 `COMBAT_V2_AUDIT_BUNDLE.md`（或同對話早前建立過 Baseline）
3. **唔貼** Full SSOT 全文 + Partial 同時 — 只貼**一個** Partial + 本索引（可選）
4. **威脅模型**：Client 不可信；GM API 需 `gm_session_valid`；西貢弱網 + 20 人 Co-op

---

## 建議審計輪次（R14 · 西貢營會前）

| 輪次 | Bundle / Scope | 狀態 |
|------|----------------|------|
| 1 | Full SSOT v13（僅一次） | ✅ 本生成 |
| 2 | R12-D 不變式 | ✅ 已審已修 · `GEMINI_REVIEW.md` §20 |
| 3 | R12-A 大廳橋接 | ✅ 已審已修 · §20 |
| 4 | R12-B DB 硬化 | ✅ 已審已修 · §20 |
| 5 | R12-C Step4 編排 | ✅ 已審已修 · §20 |
| 6 | R11 現場風險 | ✅ 已審已修 · §18–§20 |
| 7 | **下一輪新 scope** | 見 `GEMINI_REVIEW.md` §20.3 · PA 基準 `adf54a8` §21 |

---

## 測試基線（{today} · `{head}`）

```bash
./venv/bin/python3 scripts/test_combat_flow.py      # 280/280
./venv/bin/python3 scripts/test_db_hardening.py     # 12/12
./venv/bin/python3 scripts/test_combat_engine.py    # 17/17
./venv/bin/python3 scripts/test_combat_flow_orchestrator.py  # 4/4
./venv/bin/python3 scripts/test_combat_concurrency.py
npm run test:combat                                 # 23/23
npm run test:e2e:v2                               # T8–T14
bash scripts/pre_deploy_checks.sh
```

---

## 生成指令

```bash
# 全文 SSOT + 所有 Partial
python3 scripts/build_combat_v2_audit_bundle.py

# 僅 Partial（含本索引 + R11 + R12 A–D）
python3 scripts/build_combat_v2_partial_bundles.py
```

---

*End of COMBAT_V2_PARTIAL_INDEX · {today}*
"""


def build_r12_a_frontend_bridge(today: str, head: str) -> str:
    header = f"""# COMBAT_V2_R12_A_FRONTEND_BRIDGE（局部審計 · 大廳橋接與 Poll 隔離）

> **目的**：審計 **Legacy `index.html` 全局腳本** 與 **Combat V2 模組** 的交界 — 防止雙 poll、重連幽靈狀態、舊 overlay 疊加  
> **日期**：{today} · **commit**：`{head}`  
> **Baseline**：假設已讀 `COMBAT_V2_AUDIT_BUNDLE.md`  
> **生成**：`python3 scripts/build_combat_v2_partial_bundles.py`

---

## 0. 給 Gemini 的指令

**焦點問題**：
1. 全局 3s `/status` poll 是否會在 V2 戰鬥中沖刷 FSM 快照？（`isPlayerInActiveCombatV2`）
2. `exitCombatScreen` ↔ `exitToLobby` 是否會遞迴或漏清 overlay？
3. `finishSessionRestore` + `current_combat_id` 是否正確 fast-forward？
4. 舊 `#combat-near-death-overlay` 是否仍與 `failed_panel.js` 衝突？

**輸出**：【Critical】→【High/Medium】→【Low】→ 健康度 X/10

---

## 1. index.html 橋接核心

"""
    buf = [header, extract_index_bridge(), "\n"]
    buf.append("\n## 2. bootstrap 掛載\n\n")
    buf.append(read_file("static/js/combat/bootstrap.js").rstrip())
    buf.append("\n\n## 3. exitToLobby 與 entry sync\n\n")
    buf.append(extract_js_method("static/js/combat/index.js", "onCombatStarted", 30))
    buf.append("\n")
    buf.append(extract_js_method("static/js/combat/index.js", "exitToLobby", 35))
    buf.append(f"\n\n---\n*End of R12-A · {today}*\n")
    return "".join(buf)


def build_r12_b_db_hardening(today: str, head: str) -> str:
    header = f"""# COMBAT_V2_R12_B_DB_HARDENING（局部審計 · SQLite 併發與資料 SSOT）

> **目的**：審計 **20 人西貢戶外** 資料層 — WAL 模式、orphan `combat_actions`、主角狀態單一真相源、斷線重連後端握手  
> **日期**：{today} · **commit**：`{head}`  
> **Baseline**：假設已讀 `COMBAT_V2_AUDIT_BUNDLE.md`  
> **生成**：`python3 scripts/build_combat_v2_partial_bundles.py`

---

## 0. 給 Gemini 的指令

**焦點問題**：
1. WAL + `busy_timeout` 是否覆蓋最熱寫入路徑（`immediate_transaction`）？殘留直連 `sqlite3.connect` 風險？
2. `purge_combat_actions` 是否在所有戰鬥結束路徑觸發（含 reconcile）？
3. `get_team_protagonists` 是否仍可能讀到 stale `squads.protagonist_stats`？
4. `/session/restore` 的 `current_combat_id` 與 `reconcile_finished_active_combat` 是否一致？

**輸出**：【Critical】→【High/Medium】→【Low】→ 健康度 X/10

---

## 1. SQLite WAL 工廠

"""
    buf = [header]
    buf.append(read_file("utils/db_tx.py").rstrip())
    buf.append("\n\n## 2. bootstrap 啟用 WAL\n\n")
    buf.append(extract_lines("database.py", 76, 85))
    buf.append("\n")
    buf.append(extract_lines("database.py", 196, 212))
    buf.append("\n\n## 3. combat_actions 清理\n\n")
    buf.append(extract_function_block("models/combat.py", "purge_combat_actions", 45))
    buf.append("\n")
    buf.append(extract_function_block("models/combat.py", "_end_combat", 40))
    buf.append("\n\n## 4. 主角 SSOT\n\n")
    buf.append(extract_function_block("models/team.py", "get_team_protagonists", 70))
    buf.append("\n\n## 5. Session restore fast-forward\n\n")
    buf.append(extract_function_block("routes/auth.py", "session_restore", 35))
    buf.append("\n\n## 6. 測試\n\n")
    buf.append(read_file("scripts/test_db_hardening.py").rstrip())
    buf.append(f"\n\n---\n*End of R12-B · {today}*\n")
    return "".join(buf)


def build_r12_c_step4_orchestration(today: str, head: str) -> str:
    header = f"""# COMBAT_V2_R12_C_STEP4_ORCHESTRATION（局部審計 · 純計算層與戰後編排）

> **目的**：審計 **Greenfield Step 4** — `combat_engine` 純函式、`combat_flow` INV-E 混合結算、`combat_outcomes` 冪等與 `settlement_id`  
> **日期**：{today} · **commit**：`{head}`  
> **Baseline**：假設已讀 `COMBAT_V2_AUDIT_BUNDLE.md` + `combat_greenfield_final.md` §1.1 INV-E  
> **生成**：`python3 scripts/build_combat_v2_partial_bundles.py`

---

## 0. 給 Gemini 的指令

**焦點問題**：
1. 逃跑失敗後防禦分母與攻擊結算是否滿足 INV-E？（`normalize_failed_escape_actions` vs `_resolve_player_phase_body`）
2. `calculate_incoming_damage` piercing 10% 是否可被極端 buff 繞過？
3. `resolve_combat_outcome` 冪等閘門 vs 巢狀 transaction 死鎖取捨是否安全？
4. `build_victory_outcome_payload` 的 `settlement_id` 是否單調遞增？

**輸出**：【Critical】→【High/Medium】→【Low】→ 健康度 X/10

---

## 1. 純計算層

"""
    buf = [header, read_file("services/combat_engine.py").rstrip(), "\n"]
    buf.append("\n\n## 2. Step 4 編排（INV-E）\n\n")
    buf.append(read_file("services/combat_flow.py").rstrip())
    buf.append("\n\n## 3. 生產路徑 escape 接入\n\n")
    buf.append(extract_function_block("models/combat.py", "_resolve_player_phase_body", 90))
    buf.append("\n\n## 4. 戰後編排與 settlement_id\n\n")
    buf.append(read_file("services/combat_outcomes.py").rstrip())
    buf.append("\n\n## 5. 單元測試\n\n")
    buf.append(read_file("scripts/test_combat_flow_orchestrator.py").rstrip())
    buf.append("\n")
    buf.append(read_file("scripts/test_combat_engine.py").rstrip())
    buf.append(f"\n\n---\n*End of R12-C · {today}*\n")
    return "".join(buf)


def build_r12_d_inv_monotonic(today: str, head: str) -> str:
    header = f"""# COMBAT_V2_R12_D_INV_MONOTONIC（局部審計 · 弱網狀態機與 INV-A～E）

> **目的**：審計 **前端權威狀態機** — `settlement_id` / `settled_round_index` 單調防護、`entrySyncPending` 進場吸收、INV-D 失敗搶占  
> **日期**：{today} · **commit**：`{head}`  
> **Baseline**：假設已讀 `combat_greenfield_final.md` §3 不變式表  
> **生成**：`python3 scripts/build_combat_v2_partial_bundles.py`

---

## 0. 給 Gemini 的指令

**焦點問題**：
| INV | 審計問題 |
|-----|----------|
| INV-A | SETTLEMENT ⇔ modal 可見是否雙向成立？ |
| INV-B/C | 同一 `settlement_id` 是否只渲染一次？stale round 是否被拒？ |
| INV-D | HP≤0 / `dead_squad_names` 是否進 COMBAT_FAILED？ |
| INV-E | escape 失敗後攻擊方傷害是否仍結算？ |

**輸出**：【Critical】→【High/Medium】→【Low】→ 健康度 X/10

---

## 1. 狀態機核心

"""
    buf = [header, read_file("static/js/combat/state_machine.js").rstrip(), "\n"]
    buf.append("\n\n## 2. settlement 正規化\n\n")
    buf.append(read_file("static/js/combat/settlement.js").rstrip())
    buf.append("\n\n## 3. poll 與 entry sync\n\n")
    buf.append(extract_js_method("static/js/combat/index.js", "pollTick", 120))
    buf.append("\n")
    buf.append(extract_js_method("static/js/combat/index.js", "onSubmitSuccess", 80))
    buf.append("\n\n## 4. 後端 settlement meta\n\n")
    buf.append(extract_function_block("models/combat.py", "_enrich_settlement_meta", 40))
    buf.append("\n\n## 5. 單元 + E2E 摘錄\n\n")
    buf.append(read_file("tests/combat_state_machine.test.js").rstrip())
    buf.append("\n\n")
    buf.append(extract_lines("tests/combat_v2.spec.js", 1, 120))
    buf.append(f"\n\n---\n*End of R12-D · {today}*\n")
    return "".join(buf)


def main():
    today = date.today().isoformat()
    head = git_head()

    bundles = [
        (ROOT / "COMBAT_V2_PARTIAL_INDEX.md", build_index(today, head)),
        (ROOT / "COMBAT_V2_R12_A_FRONTEND_BRIDGE.md", build_r12_a_frontend_bridge(today, head)),
        (ROOT / "COMBAT_V2_R12_B_DB_HARDENING.md", build_r12_b_db_hardening(today, head)),
        (ROOT / "COMBAT_V2_R12_C_STEP4_ORCHESTRATION.md", build_r12_c_step4_orchestration(today, head)),
        (ROOT / "COMBAT_V2_R12_D_INV_MONOTONIC.md", build_r12_d_inv_monotonic(today, head)),
    ]

    for path, content in bundles:
        kb, lines = write_bundle(path, content)
        print(f"Wrote {path.name} ({kb:.1f} KB, {lines} lines)")

    r11_script = ROOT / "scripts/build_combat_v2_r11_partial_bundle.py"
    if r11_script.exists():
        subprocess.run([sys.executable, str(r11_script)], check=True, cwd=ROOT)

    print(f"\nPartial audit bundles ready · commit {head}")


if __name__ == "__main__":
    main()