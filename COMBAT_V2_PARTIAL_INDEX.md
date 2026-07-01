# COMBAT_V2 Partial Audit Bundle 索引（Gemini 審計導航）

> **日期**：2026-07-01 · **commit**：`5ea4cf8`  
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
| 7 | **下一輪新 scope** | 見 `GEMINI_REVIEW.md` §20.3 |

---

## 測試基線（2026-07-01 · `5ea4cf8`）

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

*End of COMBAT_V2_PARTIAL_INDEX · 2026-07-01*
