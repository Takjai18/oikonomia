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
> **Phase**：3 — **Delay 殘留** + settlement v10（instant settlement 已上線）  
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
## B. 請 Gemini 回答（Phase 3：Delay + Settlement v10）

1. instant settlement 後，剩餘 delay 最可能來自邊 1–2 條 path？（擲骰 / deferEnemyHp / poll 3s / 網絡）
2. `deferEnemyHp` 會否令玩家誤判「HP 冇跌」？建議改法？
3. v10 `isFinalHitOrVictory` 有無 submit vs poll race 仍 stuck 或 duplicate modal？
4. 最低風險 patch 順序（營會前）？
5. 點樣自動化「confirm 後 modal visible < 1.5s」？

**勿建議**：恢復 `COMBAT_SETTLEMENT_DELAY_MS` 或 1500ms 人工 modal 等待（已決策移除）。

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
    extract "templates/index.html" 1576 1595 "javascript"
    extract "templates/index.html" 1832 1886 "javascript"
    extract "templates/index.html" 2065 2110 "javascript"
    extract "templates/index.html" 2184 2290 "javascript"
    extract "templates/index.html" 2336 2425 "javascript"
    extract "templates/index.html" 2440 2525 "javascript"
    extract "templates/index.html" 3641 3725 "javascript"
    extract "templates/index.html" 3768 3825 "javascript"

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
| Markers | \`combat_instant_settlement\`, \`combat_flow_v7\`–\`v10\`, \`enemy_hp_sync_v7\` |
| Henry instant checklist | ✅ OK（quick + boundary） |
| 殘留 | **Delay 體感**未完全解決；v10 final-hit 待 Henry 驗 \`practice_iggy_02_leech\` |
| 後端 | Combat log / \`enemy_hp_after\` 正確 |

## H. 相關文檔

- \`GEMINI_REVIEW.md\` §16 — 檔案包清單
- \`bug_log/.../REPORT.md\` §13–§19
- \`decisions_log.md\` § instant settlement

---

*由 scripts/build_gemini_packet.sh 自動生成 · 改 code 後重新 run*
EOF

} > "$OUT"

echo "Wrote $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes)"