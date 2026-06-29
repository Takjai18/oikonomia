# Bug Log Index

| ID | 日期 | 標題 | 狀態 | 修復 commit | Case 路徑 |
|----|------|------|------|-------------|-----------|
| BUG-2026-001 | 2026-06-29 | 戰鬥敵人 HP 唔跌／結算 modal 缺失（killing blow） | **resolved**（待 Henry 實機確認） | `3c89f62` | [cases/2026-06-29_combat_enemy_hp_settlement](./cases/2026-06-29_combat_enemy_hp_settlement/REPORT.md) |

## 狀態說明

- **investigating** — 根因未確認
- **fix_in_progress** — 已有方案，開發中
- **resolved** — 已 push + CI 綠；待實機或營會驗證
- **monitoring** — 已 deploy，觀察會否再現
- **wontfix** — 已知限制，刻意不修

## 快速連結

- [README（用途與流程）](./README.md)
- Drive SSOT：`My Drive/oikonomia/bug_log/`
- 架構決策：`decisions_log.md` § 2026-06-29 Combat Killing Blow
- 部署閘門：`scripts/pre_deploy_checks.sh` + `.github/workflows/ci.yml`