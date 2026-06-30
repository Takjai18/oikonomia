# Bug Log Index

| ID | 日期 | 標題 | 狀態 | 修復 commit | Case 路徑 |
|----|------|------|------|-------------|-----------|
| BUG-2026-001 | 2026-06-29 | 戰鬥敵人 HP／結算 modal／delay 殘留 | **fix_in_progress** — Gemini Phase 4 → **v13**（log 邊界 + endgame lock）待實機 | `84877d8`→v13 | [REPORT](./cases/2026-06-29_combat_enemy_hp_settlement/REPORT.md) · [Consult](./cases/2026-06-29_combat_enemy_hp_settlement/GEMINI_CONSULT.md) · [Packet](./cases/2026-06-29_combat_enemy_hp_settlement/GEMINI_PACKET.md) |

## 狀態說明

- **investigating** — 根因未確認
- **fix_in_progress** — 已有方案，開發中
- **resolved** — 已 push + CI 綠；實機確認通過
- **reopened** — 曾標 resolved 但實機仍失敗；需新一輪調查
- **partial_fix** — 主症狀已修；仍有子問題（見 case REPORT）
- **monitoring** — 已 deploy，觀察會否再現
- **wontfix** — 已知限制，刻意不修

## 快速連結

- [README（用途與流程）](./README.md)
- Drive SSOT：`My Drive/oikonomia/bug_log/`
- 架構決策：`decisions_log.md` § 2026-06-29 Combat Killing Blow
- 部署閘門：`scripts/pre_deploy_checks.sh` + `.github/workflows/ci.yml`