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
> **用途**：Gemini **讀唔到** Google Drive bug_log 資料夾時，將**成個檔案** Copy & Paste 到 Gemini chat。
> **重新生成**：\`bash scripts/build_gemini_packet.sh\`

---

## 點樣俾 Gemini（下次照做）

1. **最簡單**：打開本檔 \`GEMINI_PACKET.md\` → 全選 Copy → 貼到 Gemini
2. **GitHub Raw**（若 Gemini 支援 URL）：
   - 本檔：${GITHUB_RAW}/bug_log/cases/2026-06-29_combat_enemy_hp_settlement/GEMINI_PACKET.md
   - 完整 index.html：${GITHUB_RAW}/templates/index.html
   - routes/combat.py：${GITHUB_RAW}/routes/combat.py
3. **唔好用**：Drive 資料夾連結（Gemini API 索引唔到 .md / bug_log）
4. **可選**：將本檔 Upload 為 **Google Doc**（單檔分享連結）再俾 Gemini

---

EOF

    if [[ -f "$CASE_DIR/GEMINI_CONSULT.md" ]]; then
        echo "## A. GEMINI_CONSULT（精簡摘要）"
        echo ""
        cat "$CASE_DIR/GEMINI_CONSULT.md"
        echo ""
        echo "---"
        echo ""
    fi

    cat <<'EOF'
## B. §12.5 請 Gemini 回答

1. API 正確但 DOM 唔更新 — 最可能邊條 code path？
2. 方案 A（前端簡化）vs B（後端 `display_enemy_hp`）vs C（cache-bust + 只用 `enemy.hp`）— 邊個風險最低？
3. Henry 最少採證：Network JSON、Console、Safari 清快取？
4. 架構級建議（拆 JS module、Service Worker）？

## C. DOM 目標（HP 顯示）

| Element ID | 用途 |
|------------|------|
| `enemy-hp-current` | 敵人當前 HP 數字 |
| `enemy-hp-max` | 敵人最大 HP |
| `enemy-hp-bar` | 血條 width % |
| `enemy-stat-hp` | 敵人面板 stat |
| `enemy-round-damage` | 本回合傷害提示 |

更新函數鏈：`loadCombatStatus` / `submitAction` → `handleCombatRoundResolved` → `updateCombatUI` → `updateEnemyCombatStats` → **`syncEnemyHpDisplay`**

## D. 關鍵 JavaScript（templates/index.html）

EOF

    extract "templates/index.html" 1785 2199 "javascript"
    extract "templates/index.html" 3323 3680 "javascript"
    extract "templates/index.html" 4562 4585 "javascript"

    cat <<EOF

## E. 後端 Python

EOF

    extract "routes/combat.py" 161 278 "python"
    extract "routes/combat.py" 331 475 "python"
    extract "models/combat.py" 931 1010 "python"

    cat <<EOF

## F. CI 已通過（API 層）

- \`test_solo_multi_round_poll_hp_monotonic\` — 單人 practice_iggy_03_boundary 每回合 enemy.hp 遞減
- \`test_practice_combat_start_enemy_hp_full\` — 開局 48/140 HP
- \`test_zombie_hp_zero_status_poll_returns_victory\`
- \`test_solo_killing_blow_practice_quick\`

## G. 實機仍 fail 條件（Henry）

- Iggy 線、**單人**、\`practice_iggy_03_boundary\`（140 HP）
- PA \`${COMMIT}\`、\`enemy_hp_sync_v3: true\`
- 戰鬥中敵 HP **顯示**唔更新

---

*由 scripts/build_gemini_packet.sh 自動生成 · 勿手改（改源碼後重新 run script）*
EOF

} > "$OUT"

echo "Wrote $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes)"