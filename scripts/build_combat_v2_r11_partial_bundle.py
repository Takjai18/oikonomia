#!/usr/bin/env python3
"""Generate COMBAT_V2_R11_PARTIAL_BUNDLE.md —局部審計包（防 context 溢出）。"""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "COMBAT_V2_R11_PARTIAL_BUNDLE.md"


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
    start = next((i for i, l in enumerate(lines) if l.startswith(f"def {def_name}") or f"async {def_name}" in l), None)
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


def main():
    today = date.today().isoformat()
    header = f"""# COMBAT_V2_R11_PARTIAL_BUNDLE（局部審計 · 營會現場風險）

> **用途**：Gemini **【審計模式】** — 只貼本檔，唔貼 `COMBAT_V2_AUDIT_BUNDLE.md` 全文  
> **日期**：{today}  
> **Baseline**：假設已讀 **COMBAT_V2_AUDIT_BUNDLE v11**（SSOT 在 repo，首次 onboarding 用 v11 全文）  
> **生成**：`python3 scripts/build_combat_v2_r11_partial_bundle.py`

---

## 0. 給 Gemini 的指令（R11 — 局部 Audit）

**輸出格式**：【Critical】→【High/Medium】→【Low】→ **健康度總評 X/10**  
**威脅模型**：玩家可開 DevTools；GM override 需 `gm_session_valid`；假設 client 不可信。

### Scope A — GM 現場嵌入式特權面板
- `victory_view.js` `showFailed` + 三重點擊解鎖
- `routes/gm.py` `gm_override_trauma_ending_api`
- 焦點：`team_id` fallback、`COMBAT_RESET`、同瀏覽器 GM session、403 阻斷

### Scope B — 超時自動防禦（戶外 poll）
- `index.js` `triggerTimeoutAutomaticDefense` + `pollTick` phase_expired 路徑
- 焦點：double-submit、poll 延遲、與 `SUBMITTING` 狀態互斥

### Scope C — Co-op 併發 resolve
- `models/combat.py` `_claim_player_phase_resolution` + `maybe_resolve_player_phase`
- 焦點：CAS 鎖、stale resolving、兩人同秒 submit

### 已知缺口（審計時標註即可，唔阻 deploy）
- 無 T15 E2E（真 GM session override 流程）
- `combat_v1` rollback 目錄不存在；`COMBAT_V2=0` 僅顯示聯繫 GM
- `models/combat.py` ~2000 行 — Step 3/4 拆分屬營會後技術債

### 測試基線（R11）
```bash
npm run test:combat                              # 15/15
./venv/bin/python3 scripts/test_combat_flow.py   # 264/264
./venv/bin/python3 scripts/test_db_hardening.py  # 8/8
npm run test:e2e:v2                              # T8–T14
```

> 其他 Partial 見 `COMBAT_V2_PARTIAL_INDEX.md`（R12-A～D）

---

## 1. Scope A — GM 現場救援

"""

    buf = [header]
    buf.append("\n\n===== FILE: static/js/combat/views/victory_view.js =====\n\n")
    buf.append(read_file("static/js/combat/views/victory_view.js").rstrip())
    buf.append("\n")

    buf.append("\n\n===== EXCERPT: static/js/combat/index.js — executeGmOverride =====\n\n")
    buf.append(extract_js_method("static/js/combat/index.js", "executeGmOverride", 50))
    buf.append("\n")

    buf.append("\n\n===== EXCERPT: static/js/combat/api_client.js — overrideTraumaEnding =====\n\n")
    buf.append(extract_js_method("static/js/combat/api_client.js", "overrideTraumaEnding", 30))
    buf.append("\n")

    buf.append("\n\n===== EXCERPT: routes/gm.py — gm_override_trauma_ending_api =====\n\n")
    buf.append(extract_function_block("routes/gm.py", "gm_override_trauma_ending_api", 160))
    buf.append("\n")

    buf.append("\n\n## 2. Scope B — 超時自動防禦\n\n")
    buf.append(extract_js_method("static/js/combat/index.js", "triggerTimeoutAutomaticDefense", 40))
    buf.append("\n")
    buf.append(extract_js_method("static/js/combat/index.js", "pollTick", 100))
    buf.append("\n")

    buf.append("\n\n## 3. Scope C — Co-op 併發 resolve\n\n")
    buf.append(extract_function_block("models/combat.py", "_claim_player_phase_resolution", 80))
    buf.append("\n")
    buf.append(extract_function_block("models/combat.py", "maybe_resolve_player_phase", 120))
    buf.append("\n")

    buf.append("\n\n## 4. E2E 參考 — T14 特權阻斷\n\n")
    buf.append(extract_lines("tests/combat_v2.spec.js", 498, 560))
    buf.append("\n")

    buf.append(f"\n\n---\n*End of COMBAT_V2_R11_PARTIAL_BUNDLE · {today}*\n")

    OUT.write_text("".join(buf), encoding="utf-8")
    size_kb = OUT.stat().st_size / 1024
    line_count = len(OUT.read_text(encoding="utf-8").splitlines())
    print(f"Wrote {OUT} ({size_kb:.1f} KB, {line_count} lines)")


if __name__ == "__main__":
    main()