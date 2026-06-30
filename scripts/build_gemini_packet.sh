#!/bin/bash
# Build self-contained GEMINI_PACKET.md for AI review (Gemini cannot read Drive folder).
# Usage: bash scripts/build_gemini_packet.sh [CASE_DIR]
# Default case: bug_log/cases/2026-06-29_combat_enemy_hp_settlement

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
CASE_DIR="${1:-$REPO/bug_log/cases/2026-06-29_combat_enemy_hp_settlement}"
OUT="$CASE_DIR/GEMINI_PACKET.md"
COMMIT="$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)"
GITHUB_RAW="https://raw.githubusercontent.com/Takjai18/oikonomia/${COMMIT}"

extract() {
    local file="$1" start="$2" end="$3" lang="$4"
    echo ""
    echo "### \`${file}\` L${start}–L${end}"
    echo ""
    echo "\`\`\`${lang}"
    sed -n "${start},${end}p" "$REPO/$file"
    echo "\`\`\`"
}

{
    cat <<EOF
# GEMINI_PACKET — BUG-2026-001（自包含，可直接貼入 Gemini）

> **生成時間**：$(date -u +"%Y-%m-%d %H:%M UTC")  
> **Git commit**：\`${COMMIT}\`  
> **Phase**：4 — Safari **0 傷害** + Chrome **勝利後重複結算**（v12 patch）
> **用途**：Gemini **讀唔到** Google Drive bug_log 時，將**成個檔案** Copy & Paste 到 Gemini chat。  
> **重新生成**：\`bash scripts/build_gemini_packet.sh\`

---

## 點樣俾 Gemini（下次照做）

1. **最簡單（推薦）**：打開本檔 → 全選 Copy → 貼到 Gemini
2. **加文檔**：另貼 \`GEMINI_REVIEW.md\` §16 或只貼 \`GEMINI_CONSULT.md\`
3. **GitHub Raw**（若 Gemini 支援 URL）：
   - 本檔：${GITHUB_RAW}/bug_log/cases/2026-06-29_combat_enemy_hp_settlement/GEMINI_PACKET.md
   - Consult：${GITHUB_RAW}/bug_log/cases/2026-06-29_combat_enemy_hp_settlement/GEMINI_CONSULT.md
   - index.html（大檔）：${GITHUB_RAW}/templates/index.html
4. **唔好用**：Drive 資料夾連結、\`attachments/\` 舊快照

---

EOF

    if [[ -f "$CASE_DIR/GEMINI_CONSULT.md" ]]; then
        echo "## A. GEMINI_CONSULT（Phase 3 摘要）"
        echo ""
        cat "$CASE_DIR/GEMINI_CONSULT.md"
        echo ""
        echo "---"
        echo ""
    fi

    cat <<'EOF'
## B. 請 Gemini 回答（Phase 4：0 傷害 + 勝利後重複結算）

1. `showCombatResult` → `resetCombatSessionState` 係咪 §22 根因？`combatVictorySequenceCompleteId` 夠唔夠？
2. `enrichRoundSettlementData` 會否誤 parse 舊回合 log？點加 phase 邊界？
3. Safari 0 傷害除 stale settlement 外，仲有無 `breakdown` early return 以外嘅 path？
4. Playwright assert：勝利 panel visible 後 settlement modal 不可再 `flex`？
5. v12 deploy 後邊個 browser／玩家先驗？

**勿建議**：恢復 1500ms modal delay。

## C. DOM 目標

| Element ID | 用途 |
|------------|------|
| `enemy-hp-current` | 敵人當前 HP 數字 |
| `enemy-hp-bar` | 血條 width % |
| `combat-round-settlement-modal` | 傷害結算 modal |
| `round-settlement-confirm-btn` | 確定／確定，查看勝利 |

函數鏈：`submitAction` → `handleCombatRoundResolved` / `finishCombatVictoryFromPayload` → `showFullRoundSettlement` → `continueCombatAfterRound` → `loadCombatStatus`（poll）

## D. 關鍵 JavaScript（templates/index.html 摘錄）

EOF

    extract "templates/index.html" 1238 1271 "javascript"
    extract "templates/index.html" 1576 1605 "javascript"
    extract "templates/index.html" 1655 1685 "javascript"
    extract "templates/index.html" 1988 2070 "javascript"
    extract "templates/index.html" 2120 2160 "javascript"
    extract "templates/index.html" 2288 2360 "javascript"
    extract "templates/index.html" 2395 2520 "javascript"
    extract "templates/index.html" 2545 2595 "javascript"
    extract "templates/index.html" 3468 3525 "javascript"
    extract "templates/index.html" 3715 3810 "javascript"

    cat <<EOF

## E. 後端 Python（API 合約摘錄）

EOF

    extract "routes/combat.py" 161 278 "python"
    extract "routes/combat.py" 331 475 "python"
    extract "models/combat.py" 931 1010 "python"

    cat <<EOF

## F. CI 已通過

- \`scripts/test_combat_engine.py\` — 14 項純計算
- \`scripts/test_combat_flow.py\` — 192+ 項（含 killing blow、poll HP、practice）
- \`scripts/pre_deploy_checks.sh\` — 全綠

## G. 實機狀態（2026-06-30）

| 項目 | 狀態 |
|------|------|
| Commit | \`${COMMIT}\` |
| Markers | \`combat_flow_v11\`–\`v12\`, \`combatVictorySequenceCompleteId\`, \`enrichRoundSettlementData\` |
| §21 Vini Safari | 結算 0 傷害（marathon）— v12 待驗 |
| §22 Henry Chrome | 勝利後重複結算 — v12 待驗 |
| Henry Safari §16 | 先前通過；Chrome 新 regression |

## H. 相關文檔

- \`GEMINI_REVIEW.md\` §16 — 檔案包清單
- \`bug_log/.../REPORT.md\` §13–§19
- \`decisions_log.md\` § instant settlement

---

*由 scripts/build_gemini_packet.sh 自動生成 · 改 code 後重新 run*
EOF

} > "$OUT"

echo "Wrote $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes)"