# Oikonomia — Update Log（已知問題與設定陷阱）

> **用途**：記錄已發生過嘅 production／開發問題、相關設定、修復 commit，同**刻意設計**（唔係 bug）。  
> **讀者**：Grok（方向）、Grok Build（實作）、Gemini（review）、Tak（決策）  
> **SSOT**：本 repo；副本可同步至 Google Drive `oikonomia/`

---

## ⚠️ AI 協作必讀

**Grok / Gemini / Grok Build 喺提出架構建議、code review、或 debug 假設之前，必須先讀本檔。**

若你嘅意見與下方「已修復／已知陷阱／刻意設計」矛盾，請：

1. **明確引用**本檔相關章節（例如「UPDATE_LOG § PA Secrets」）
2. 說明點解仍建議改動（例如新需求、已過時）
3. **唔好**把已列為「刻意設計」嘅行為當成未修 bug 重複提出

用戶可以話：「請考慮 `UPDATE_LOG.md` 再答」——代表你漏咗本檔內容。

**相關文檔**（唔好混淆）：

| 文檔 | 內容 |
|------|------|
| **本檔 `UPDATE_LOG.md`** | 實際踩過嘅坑、設定、修復、假陽性 |
| `decisions_log.md` | 架構取捨與 Phase 範圍決策 |
| `AGENT_HANDOFF.md` | 部署步驟、測試指令、版本狀態 |
| `GEMINI_REVIEW.md` | 第三方 review 紀錄（歷史快照，可能過時） |

---

## 設定與環境變數速查（易出問題）

| 設定 | 位置 | 常見問題 | 正確做法 |
|------|------|----------|----------|
| `SECRET_KEY` | PA Web worker | Bash `export` **唔會**傳入 worker → session 失效、全站 500 | `data/.secret_key`（`deploy/pa-ensure-secret.sh`）；`wsgi.py` / `app.py` 經 `utils/production_secrets.py` 載入 |
| `GM_PIN` | PA Web worker | 同上；GM 登入失敗 | `data/.gm_pin` 或 Web tab env |
| `DATA_DIR` | PA | 預設應指向 `~/oikonomia/data`；錯路徑會搵錯 DB | `pa-update.sh` 會 set；WSGI 要與磁碟一致 |
| Deploy 後未 Reload | PA Web tab | `git pull` 成功但 running code 仍舊；`/api/version` 可能仍舊或 500 | **必須** Web → Reload；用 `curl /api/version` 核對 `version` + `markers` |
| `FORCE=1` | `pa-update.sh` | 一般 `git pull` 因 `.deploy-version` 等本地檔失敗 | PA 上一律 `FORCE=1 bash ~/oikonomia/deploy/pa-update.sh` |
| `OIKONOMIA_SHOW_TEST_ENCOUNTERS` | env | `1` 時非 GM 都見到測試 encounter | Production **唔好**設；僅開發／GM 測試用 |
| `OIKONOMIA_ENDING_ENABLED` | env | `0` 停用 ending orchestrator 副作用 | 測試用；production 預設 `1` |
| `OIKONOMIA_SKIP_DB_BOOTSTRAP` | env | `1` 跳過 DB bootstrap | 僅特殊測試；唔好喺 PA 亂開 |
| `FLASK_ENV=production` | PA | 未設可能用 dev 預設憑證 | `pa-update.sh` 會處理 |
| 本地 port | 開發 | macOS 5000 常被佔用 | 預設 **5001**（`app.py`） |
| `venv` | 測試 | 直接用系統 `python3` 缺 `werkzeug` 等 | `./venv/bin/python3 scripts/test_combat_flow.py` |

---

## 遊戲機制：易被誤判為 bug 的設計

| 項目 | 說明 | 唔係 bug |
|------|------|----------|
| **永恆崩壞影** `test_undefeatable` | HP 9999、resilience 99；`route: test` | 刻意打唔贏，測 Trauma／失敗流程 |
| 測試 encounter 隱藏 | `route=test` 僅 GM 或 `OIKONOMIA_SHOW_TEST_ENCOUNTERS=1` 可開 | 防止玩家誤入測試戰（commit `3df7bdb`） |
| 骰子 **0** | `DICE_MULTIPLIERS[0]=0.0` → 該次攻擊 **0 傷害** | 設計如此；log 會寫「造成 0 點傷害」 |
| 最低傷害 1 | `calculate_attack_damage` 喺 multiplier > 0 時 `max(1, …)` | 骰 1–3 至少 1 點（除非 multiplier≤0） |
| 暴走 | 神智過低可能攻擊自己而唔打敵 | 檢查 log 有冇「暴走」 |
| 高 HP 敵人血條 | 9999 HP 扣 20 點仍 ~100% 闊度 | 睇數字／本回合傷害提示，唔好單靠血條 |

---

## 更新紀錄（按時間倒序）

### 2026-06-29 — 全隊傷害結算畫面唔顯示／只得 log

| 項目 | 內容 |
|------|------|
| **症狀** | 攻擊後睇唔到「全隊對敵／敵對我方」傷害結算畫面 |
| **根因** | ① 結算 modal 只得文字 log，冇雙向傷害數字 ② `full_preview` 無 `round_settlement` ③ 輪詢 `phaseAdvanced` 缺 payload ④ 重複 `handleCombatRoundResolved` 會跳過 modal |
| **修復** | 後端 `_round_settlement_from_logs`；modal 雙欄傷害；`shouldShowRoundSettlement`；status 一律附 `round_settlement` |
| **勿重複建議** | 唔好只加 toast；結算要用 `round_settlement.team_damage_dealt` / `enemy_damage_dealt` |

### 2026-06-29 — 傷害浮字被回合結算 Modal 遮住

| 項目 | 內容 |
|------|------|
| **症狀** | 玩家攻擊永恆崩壞影多次，仍睇唔到傷害貼圖／浮字 |
| **根因** | ① 回合結算 modal `z-[73]` 即刻蓋住 `.damage-number`（原 z-50）② 浮字掛喺 `enemy-panel`（`overflow-hidden`）被裁切 ③ `/combat/status` 輪詢 `round_just_resolved` 時漏傳 `round_enemy_damage` |
| **修復** | 浮字改 `position:fixed` + `document.body` + z-80；延遲 ~950ms 先開結算 modal；modal 內顯示本回合傷害；status API 補 `round_enemy_damage` |
| **勿重複建議** | 唔好只改 regex（`3df7bdb` 已修）；要檢查 modal 疊層同輪詢 payload |

### 2026-06-29 — 敵人 HP 動畫與千分位數字

| 項目 | 內容 |
|------|------|
| **Commit** | `4e07cb7` |
| **症狀** | 敵人 HP 顯示 `9,999` 時，動畫由錯誤起點計算；高 HP 戰鬥難以察覺扣血 |
| **根因** | `parseInt("9,999")` → `9`；只靠 DOM 文字做動畫起點 |
| **修復** | `parseLocaleInt`；`lastAnimatedEnemyHp`；敵人面板「本回合受到 X 點傷害」 |
| **勿重複建議** | 唔好再建議「後端冇扣敵人 HP」而唔查 log／`round_enemy_damage` |

### 2026-06-29 — 戰鬥傷害 UI 不顯示（永恆崩壞影「毫髮無傷」）

| 項目 | 內容 |
|------|------|
| **Commit** | `3df7bdb` |
| **症狀** | 玩家多次攻擊，敵人似無受傷；無傷害浮字 |
| **根因** | ① `parseLogDamageEvent` 正則寫成 literal `\s` ② 9999 HP 血條幾乎唔郁 ③ 測試 Boss 防禦極高 |
| **修復** | 正則 `/造成\s*(\d+)\s*點傷害/`；`round_enemy_damage` toast；高 HP `toLocaleString`；隱藏 `route=test` encounter |
| **後端** | `models/combat.py` 一直有扣 `enemy_hp`；屬 **前端回饋** 問題 |
| **勿重複建議** | 唔好建議削弱永恆崩壞影或刪測試檔（除非改測試策略）；應區分 UI vs 結算 |

### 2026-06-29 — PythonAnywhere 全站掛／登入失敗

| 項目 | 內容 |
|------|------|
| **Commit** | `bc53851`, `cc3f38f`, `4b81c1c` |
| **症狀** | `/api/version` → "Something went wrong"；玩家／GM 登入唔到 |
| **根因** | Web worker 唔繼承 Bash `export SECRET_KEY`／`GM_PIN`；舊 worker 未 Reload |
| **修復** | `utils/production_secrets.py` 讀 `data/.secret_key`、`data/.gm_pin`；`wsgi.py` + `app.py` 啟動前載入 |
| **勿重複建議** | 唔好只建議「喺 Bash export 一次」作為唯一解法 |

### 2026-06-29 — Combat 測試 25 項失敗

| 項目 | 內容 |
|------|------|
| **Commit** | `c1768a1`, `fd4e0e1` |
| **症狀** | `test_combat_flow.py` 大量 HTTP 500 |
| **根因** | `models/combat.py` 缺 import；測試隔離（`dice=1`、`enemy_hp=0` falsy） |
| **修復** | 補 import；`prepare_test_encounter()`；明確處理 `enemy_hp is not None` |
| **現狀** | 109/109 combat tests、23/23 ending tests（以 AGENT_HANDOFF 為準，跑完再核對） |

### 2026-06-29 — Grok Phase 1 ending orchestrator

| 項目 | 內容 |
|------|------|
| **Commit** | `fc34e95`, `fc72077` |
| **內容** | `services/ending.py`、`apply_ending`、`trauma_summary`、`OIKONOMIA_ENDING_ENABLED` |
| **注意** | Good Ending 完整演出、GM ending override **刻意延後**（見 `decisions_log.md`） |
| **勿重複建議** | 營會前唔好 push 大改 ending UX 除非 Tak 確認 |

### 2026-06-28 — Combat UI phase lock／輪詢

| 項目 | 內容 |
|------|------|
| **Commit** | `d1e47d4` |
| **症狀** | 結算中 UI 閃爍、重複提交、輪詢過慢 |
| **修復** | `combatPhaseLocked`、`resolving` 快輪詢、transactional encounter outcomes |
| **勿重複建議** | 已有 phase lock；新建議應說明與現有 lock 嘅分別 |

### 2026-06-28 — Near-death rescue 安全

| 項目 | 內容 |
|------|------|
| **Commit** | `b7ace0b` |
| **內容** | 瀕死救援驗證、combat start race guard |
| **勿重複建議** | Gemini 舊 review 可能未反映此修復 |

---

## 檔案與模組：改動前注意

| 路徑 | 注意 |
|------|------|
| `templates/index.html` | ~6500 行；戰鬥 JS 易引入 regex／locale 問題；改動要跑 combat 實機 |
| `models/combat.py` | 結算 SSOT；改傷害公式要同步 `scripts/test_combat_flow.py` |
| `encounters/test_*.json` | 測試用；`route: test` 唔應出現在玩家列表（除非 GM） |
| `data/.secret_key`, `data/.gm_pin` | **gitignore**；唔好 commit；PA 上用 `pa-ensure-secret.sh` |
| `GEMINI_REVIEW.md` | 歷史 review；**以本檔 + git log 為準**判斷是否已修 |

---

## 驗證清單（改動後）

```bash
# 本地（要有 venv）
./venv/bin/python3 scripts/test_combat_flow.py
./venv/bin/python3 scripts/test_ending_flow.py

# PA（deploy 後）
curl -s https://takjai.pythonanywhere.com/api/version | python3 -m json.tool
```

預期：`success: true`，`version` 與 `git rev-parse --short HEAD` 一致。

---

## 變更本檔嘅規則（Grok Build）

每次修復 **production 問題**、**玩家回報假陽性**、或新增 **env／設定陷阱**，應喺本檔加一節（日期倒序），包含：

- 症狀（用戶看到咩）
- 根因（技術上點解）
- Commit（如有）
- **勿重複建議**（俾 Grok／Gemini 避開重複勞動）

重大架構決策仍寫入 `decisions_log.md`；本檔專注**實戰踩坑**。