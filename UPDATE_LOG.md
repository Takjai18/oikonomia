# Oikonomia — Update Log（已知問題與設定陷阱）

> **用途**：記錄已發生過嘅 production／開發問題、相關設定、修復 commit，同**刻意設計**（唔係 bug）。  
> **讀者**：Grok（方向）、Grok Build（實作）、Gemini（review）、Tak（決策）  
> **SSOT**：本 repo；副本可同步至 Google Drive `oikonomia/`

---

## 2026-07-22 — Act 1 飛狐雪山（QR + 布布教學戰）

| 項目 | 內容 |
|------|------|
| **劇情** | `iggy_stage0` 停在「去場地掃 QR」；**唔預先寫死**搵到火機／已打贏布布 |
| **任務** | `act1_wood` · `act1_water` · `act1_goat_badge` · `act1_iron_plate`（**無火機**） |
| **QR** | `act1-wood` · `act1-water` · `act1-goat-badge` · `act1-iron-plate` |
| **布布** | **只**掃木材 → 立刻 `enc_iggy_act1_bubo` |
| **進度** | Stage 門檻 4 / 7 / 11 |

**GM**：印 4 個簽章 QR；舊 `act1-lighter` 可忽略／停用。

---

## 2026-07-22 — 練習長戰擊敗後無勝利畫面（Raya）

| 項目 | 內容 |
|------|------|
| **症狀** | 練習長影／多回合打完敵 HP 0，畫面停住無「戰鬥勝利」 |
| **根因** | poll 勝利時若 phase=SUBMITTING 且 settlement_id 已見過／缺，只 UPDATE_HUD 軟卡死 |
| **次因** | 全螢幕殼 overflow/transform 可裁切 fixed 結算／勝利層 |
| **修復** | 勝利 poll 一律進 VICTORY（已在 SETTLEMENT 等 ACK 除外）；endgame/settlement 掛 body；去掉 shell overflow:hidden |
| **UX 提示** | 斬殺回合仍會先彈「傷害結算」→ 按「確定，查看勝利結果」 |

---

## 2026-07-22 — GM 瀕死救援訊號不再全營廣播

| 項目 | 內容 |
|------|------|
| **症狀** | 玩家「請求 GM 介入瀕死」寫成 `effect_type=announcement`，全營通告／全球事件記錄都睇到 |
| **修復** | 改 `gm_alert`；玩家 `/announcements` 與 `/global_events` 過濾 staff-only 與舊「救援訊號」列 |
| **GM 消除** | 後台日誌每則「消除」；「清除救援訊號」一次清走全部 gm_alert／舊救援列 |
| **API** | `DELETE /gm/api/global_events/<id>` · `POST /gm/api/global_events/clear_gm_alerts` |

**勿重複建議**：把救援訊號再當 public announcement 發（應維持 `gm_alert`）。

---

## 2026-07-22 — 設定1 Iggy Arc 寫入遊戲

| 項目 | 內容 |
|------|------|
| **內容** | Cosmos 法則／Polis·Oikos／六幕敘事／City Hunt 任務／Polis·Julian·Savio 遭遇戰 |
| **機制** | `win_condition: survive` + `max_phases`（Act2 Polis 5 回合不敗即勝）；提前擊殺仍勝 |
| **檔案** | `data/cosmos_lore.py`、`story_config`、`narrative_stories`、`locations`、`enc_iggy_act2/4/6_*.json`、`models/combat.py` |
| **未完成** | Where’s Wally 正式圖、真迷宮、醬板鴨／貼身物實體 props、MTR GPS 精確 pin |
| **測試** | `test_survival_win_after_max_phases` |

**勿重複建議**：把所有戰鬥的 `max_phases` 預設當硬上限（只在 `win_condition=survive` 時觸發生存勝；預設仍靠打到 0 HP）。

---

## 2026-07-21 — 營會 threat model + 現場救場文檔

| 項目 | 內容 |
|------|------|
| **決策** | 玩家唔識電腦、基本上唔會作弊 → **暫擱** task/item API 反作弊硬化（見 assessment） |
| **仍做** | GPS／影相 **GM 救場**；伺服器健康 + Drive 備份 |
| **文檔** | 新增 [`CAMP_FIELD_GUIDE.md`](./CAMP_FIELD_GUIDE.md)；`AGENT_HANDOFF.md` 加開場 checklist 連結 |
| **Production** | `https://oikonomia.onrender.com` · live `version` 以 `/api/version` 為準（2026-07-21 查：`83d1661`；本機 `main` 可再超前 1 commit）· `data_dir=/data` · `combat_v2=true` · `forced_route=iggy` |
| **注意** | Render 閒置首次請求可 **502**（冷啟動）；等 30–60s 再試，見 Field Guide §0 |

**勿重複建議**：為誠實玩家場趕修假 task_id／add_item 白攞（營後可做）。

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
| **本檔 `UPDATE_LOG.md`** | 實際踩過嘅坑、設定、修復、假陽性（**短條目**） |
| **`bug_log/`** | 難解、多輪修復嘅 bug **長篇調查** + attachments（Drive SSOT） |
| `decisions_log.md` | 架構取捨與 Phase 範圍決策 |
| `AGENT_HANDOFF.md` | 部署步驟、測試指令、版本狀態 |
| `GEMINI_REVIEW.md` | 第三方 review 紀錄（歷史快照，可能過時） |

---

## 2026-06-29 — 戰鬥敵 HP／結算（BUG-2026-001 reopened）

| 項目 | 內容 |
|------|------|
| **症狀** | Henry 打練習速戰殘影等，敵 HP 唔跌／冇完整結算 modal（與早前 Saliba 相同類） |
| **已做** | 方案1 `3c89f62`：`build_victory_outcome_response` + 前端先 settlement 再勝利 |
| **PA** | `curl /api/version` 已為 `3c89f62`，`enemy_hp_sync_v2: true` |
| **結果** | **實機仍失敗** — Henry：單人、多回合、**從未見 settlement modal**、HP 唔跌 |
| **第二輪** | UI：`resolveAuthoritativeEnemyHp` 取 min；poll `outcome` 統一入口；強制 settlement modal |
| **下一輪懷疑** | stale `round_settlement` 蓋過 `enemy.hp`；poll `outcome` 捷徑（見 `bug_log` REPORT §10.4） |
| **詳細** | **[bug_log/cases/2026-06-29_combat_enemy_hp_settlement/REPORT.md](./bug_log/cases/2026-06-29_combat_enemy_hp_settlement/REPORT.md)** |

**勿重複建議**：只改 `build_victory_outcome_payload` 而唔統一 poll 勝利路徑，已證明不足。

---

## 2026-06-30 — combat_flow_v8 settlement guard（instant 殘留）

| 項目 | 內容 |
|------|------|
| **症狀** | 速戰殘影有時無 modal；勝利後偶發重複傷害結算 |
| **修復** | `settlementDisplayKey`；`mustShow` 強制 modal；`combat_instant_settlement` marker 字串 |
| **Henry instant 專項** | checklist OK；v8 針對殘留 edge case |

---

## 2026-06-30 — BUG-2026-001 resolved（Henry 實機通過 · `12e1edd`）

| 項目 | 內容 |
|------|------|
| **最終版本** | `12e1edd`（`combat_flow_v7` + `settlement_breakdown_v1` + `enemy_hp_sync_v7` + instant settlement） |
| **實機** | Henry（`PLAYER-75406`，Iggy solo，Safari 硬刷新）— marathon / boundary / breakdown 全通過 |
| **狀態** | **resolved**；營會期 **monitoring**（雙人隊、主線 encounter 未充分驗） |
| **詳細** | `bug_log/.../REPORT.md` §16 · `decisions_log.md` § Henry resolved |

**勿重複建議**：poll race、killing blow payload、monotonic guard 已多輪修；若再現應附 encounter + Network JSON 開新子議題。

---

## 2026-06-30 — BUG-2026-001 更新至 `cc5671d`（已 supersede）

| 項目 | 內容 |
|------|------|
| **新版本** | `cc5671d`（`combat_flow_v2`–`v5` + `settlement_breakdown_v1`） |
| **已 patch** | 勝利後重複結算 modal（v5）；第二場／下一回合無反應（v4）；取消預計傷害預覽（v3） |
| **狀態** | 已由 `12e1edd` + Henry 實機取代 |
| **詳細** | `bug_log/.../REPORT.md` §15 |

**勿重複建議**：再改 killing blow payload 或 poll 勝利捷徑而唔睇 v4/v5/v7 鎖；舊「本回合戰果」字眼已改「傷害結算」。

---

## 2026-07-02 — Render 死圖 + 勝利 FSM 卡死（Gemini 戰鬥 audit · `df5acea`）

| 項目 | 內容 |
|------|------|
| **症狀** | Render 戰鬥 HUD 破圖；最後一擊後無勝利畫面／卡在提交中 |
| **Gemini 建議** | 三處 `_attach_round_settlement`、fallback `default-enemy.svg`、Clear Build Cache |
| **取捨** | ① 後端勝利 payload **已在 `5e8b3b6`**，唔重做 ② fallback 檔名 **錯** ③ 真因：API 裸檔名 + V2 無 `onerror` ④ FSM `skipModal` / SUBMITTING poll 釘 phase |
| **修復** | `avatar_urls.js`；`models/combat.py` URL 正規化；`skipToVictory`；SUBMITTING `POLL_TICK` |
| **驗證** | `npm run test:combat` 29/29 · `test_combat_flow` 297/297 |

**勿重複建議**：`default-enemy.svg`／`default-avatar.svg`（無檔）；三處手動 `_attach_round_settlement`（已有 `_json_victory_outcome`）；`parasite_shadow.svg` Render 404（實測 200）。詳見 `GEMINI_REVIEW.md` §29。

### 永久規則：Gemini Audit 批判性審視

當 Tak 提交 Gemini Audit Report 時，**Grok Build 唔盲目跟從**。流程見 `README.md`（Gemini Audit 批判性審視）、`AGENT_HANDOFF.md` 同節、`GEMINI_REVIEW.md` §30。每輪 audit 必須：驗證 → 分類（採用／已 ship／拒絕／延後）→ 更新文檔 → 只改真正缺口。

---

## 2026-07-02 — 戰後管線：終端封包 bypass + 勝利解鎖

| 項目 | 內容 |
|------|------|
| **Gemini** | isStale 可能丟棄 victory 封包 → 大廳鎖死 |
| **修復** | 終端 outcome/active:false 永不 stale-drop；`releaseCombatBridgeLock` on SHOW_VICTORY 等 |
| **拒絕** | Gunicorn session 分裂（Flask 簽名 cookie + SECRET_KEY 已強制） |

---

## 2026-07-02 — 大廳 /status reconcile（髒 current_combat_id）

| 項目 | 內容 |
|------|------|
| **Gemini §37** | 戰後 `releaseCombatBridgeLock` 後，大廳 poll 可能讀到 stale `current_combat_id` → 閃爍死鎖 |
| **根因** | `GET /status` 直接 `**squad` 展開；`/session/restore` 與 `/encounters` 已有 reconcile，lobby 缺 |
| **修復** | `reconcile_status_combat_fields()` 於 `routes/player.py`；fallback `[ERR_STATUS_*]` toast |
| **已 ship** | `syncState` TERMINAL `ABSORBING` 頂層攔截（`9d31b63` / R12-D 測試） |
| **§38 跟進** | `81acdf1` 寫入改 **唯讀 payload 過濾**（高頻 GET 唔做 UPDATE）；DB heal 留 restore/encounters |

---

## 2026-07-02 — 勝利跳過 Breakdown（skipToVictory 誤觸）

| 項目 | 內容 |
|------|------|
| **症狀** | 最後一擊直接彈勝利 Modal，冇傷害結算 Breakdown |
| **根因** | `determineSettlementRoute` 對 killing blow 在 `shownSettlementIds` 已含 id 時走 `skipToVictory`；entry absorb 曾過早標記 |
| **修復** | killing blow 有 settlement 時強制走 SETTLEMENT；`absorbStaleSettlementOnEntry` 排除 terminal/0 HP |
| **附帶** | `/combat/start` 顯式 `active`/`round_resolved`；`#my-team-card` 水平對齊 |
| **§40 跟進** | 恢復 `shownSettlementIds` 護欄：僅 `SUBMITTING` 假陽性可重開 SETTLEMENT；VICTORY/TERMINAL 一律 `skipModal` |
| **§41** | 營會終極 checklist + 雙人併發實機項寫入 `AGENT_HANDOFF.md`；Gemini 程式範例多數已 ship |

---

## 2026-07-02 — 重開戰鬥殘留上一場（需 F5）

| 項目 | 內容 |
|------|------|
| **症狀** | 離開戰鬥後再開 encounter，首屏仍見上一場 HP 0／勝利殘影；F5 才正常 |
| **根因 1** | `mergeEntryCombatPayload` 曾 `{...start, ...status}` — stale status 覆蓋 start |
| **根因 2** | `exitCombatScreen` → `combatV2.destroy()` 將 `app=null`，下一場未 remount |
| **根因 3** | `COMBAT_RESET` 僅 IDLE/COMBAT_FAILED 可觸發，VICTORY 等終端態殘留 |
| **修復** | start 優先 merge；`ensureLiveApp` remount；`onCombatStarted` 硬重置 ctx；全域 `COMBAT_RESET` |

---

## 2026-07-02 — 戰鬥 UX：捲動置頂 + HP 首屏 + 能力值標籤

| 項目 | 內容 |
|------|------|
| **問題** | iPhone 進戰鬥要 scroll up；HP 仍要 F5；我方能力值無「我」標籤 |
| **修復** | `scrollCombatToTop`；entry 先畫 start payload + 3 次 status retry；`isStaleHudSnapshot`；玩家名稱標籤 |
| **勿** | 自動 F5（改 entry repair + 即時渲染） |

---

## 2026-07-02 — 戰鬥畫面能力值空白（V2 缺 UI）

| 項目 | 內容 |
|------|------|
| **Gemini 稱** | 快取舊 hud_view；`isHpOnly` 鎖死；`hp_value` fallback |
| **實際** | `combat_screen.html` **從未有能力值 DOM**；後端 `my_state` 已齊 |
| **修復** | 神智條 + 力/智/韌面板；`stats.js`；`hud_view` vitals 永遠更新 |
| **勿重複建議** | 硬編碼 commit cache bust；`hp_value` 欄位 |

見 `GEMINI_REVIEW.md` §36。

---

## 2026-07-02 — HP 0 需 F5（ES module 快取 + entry 競態）

| 項目 | 內容 |
|------|------|
| **症狀** | 首進戰鬥敵人 HP 0；F5 後正常 |
| **根因** | ES module 依賴鏈快取舊 FSM；poller 與 entry status 競態；status 覆蓋 start payload |
| **修復** | 動態 `import(index.js?v=)`；combat JS `no-store`；`mergeEntryCombatPayload`；poller 延後；練習殭屍戰 ended |
| **勿重複建議** | 硬編碼 `?v=41b9da1`（用 `deploy_version`） |

見 `GEMINI_REVIEW.md` §35。

---

## 2026-07-02 — 戰鬥 HP 0 卡死 + HUD 空白 + 劇情破圖（Gemini audit · 批判性審視）

| 項目 | 內容 |
|------|------|
| **Gemini 稱** | FSM 殘留 `enemy_hp:0`；`power_value` 欄位不一致；劇情 portrait 404 |
| **取捨** | ✅ entry HUD merge + killing blow 判定 · ❌ `power_value`（不存在）· ✅ start 補 `my_state` · ✅ story onerror |
| **修復** | `buildHudFromSnapshot`；`determineSettlementRoute`；`onCombatStarted` 先 status；`combat/start`；劇情肖像；練習離開鈕 |
| **驗證** | `npm run test:combat` 32/32 · `test_combat_flow` 299/299 |

見 `GEMINI_REVIEW.md` §34。

---

## 2026-07-02 — allocate_stats「分配失敗」（Gemini audit · 批判性審視）

| 項目 | 內容 |
|------|------|
| **Gemini 稱** | `player.py` 缺路由 → 404；或 DB lock → 500 |
| **實際** | 路由在 **`routes/auth.py`**（非 404）；痛點係 `update_squad` 無 retry |
| **修復** | `immediate_transaction` + `with_db_retry`；前端具體錯誤；測試 299/299 |
| **勿重複建議** | 把 `/allocate_stats` 複製到 `player.py`；Gemini 範例裸 `sqlite3.connect` |

見 `GEMINI_REVIEW.md` §33。

---

## 2026-07-02 — Android Chrome 登入 audit（批判性審視）

| 項目 | 內容 |
|------|------|
| **Gemini 根因** | DB lock；Ghost Cache；In-App SameSite |
| **取捨** | ❌ 重複建 `get_db_connection`（已有 `db_tx.py`）· ✅ auth no-cache headers · ✅ `get_squad` WAL · ✅ fallback `/status` cache bust |
| **勿重複建議** | 再貼 `database.py` timeout=30 範例；10s 超時（已 25s） |

見 `GEMINI_REVIEW.md` §32。

---

## 2026-07-02 — iPhone Safari 登入「網絡連線」假錯誤（Gemini audit · 批判性審視）

| 項目 | 內容 |
|------|------|
| **症狀** | Safari 顯示「登入失敗，請重試或檢查網絡連線」 |
| **Gemini 根因** | Cookie 缺 Secure/SameSite；DB lock；10s 超時 |
| **取捨** | ❌ Cookie **已配置**（curl 驗證 Set-Cookie）· ❌ 唔用 `DATA_DIR` 判 Cookie · ✅ `/login` 改 WAL+retry · ✅ 25s 超時+具體錯誤文案 |
| **勿重複建議** | 再貼 `app.py` Cookie 區塊（L40–47 已有） |

詳見 `GEMINI_REVIEW.md` §31。

---

## 2026-07-02 — Gemini df5acea 跟進 audit（批判性審視）

| Gemini 項 | 審視 | 處理 |
|-----------|------|------|
| Critical：頭像 URL SSOT + 等冪 | ✅ 已 ship（`df5acea`） | ❌ 拒絕其 `enemy_avatar`/`avatar_url` 範例；維持 `_combat_*_avatar_url` + `avatar` 欄位 |
| High：skipToVictory + poll→VICTORY | ✅ 已 ship | 加測試 `poll victory with already-shown settlement` |
| Low：`bootstrap.js` cache bust | ✅ 採用改良 | `?v={{ deploy_version }}`（唔硬編碼 commit） |
| Ops：version 核對 + sessionStorage.clear | ✅ 文檔 | 唔改 code |

**勿重複建議**：再改頭像 SSOT 或 skipToVictory（已覆蓋）；唔好硬編碼 `?v=<hash>` 入 HTML。

---

## 2026-07-02 — Render ProxyFix（Gemini infra audit）

| 項目 | 內容 |
|------|------|
| **建議** | Render 反向代理後 `request.remote_addr` 會是內網 IP |
| **實際影響** | GPS 驗證用客戶端 lat/lng，**唔依賴 IP**；GM audit log（`routes/gm.py`）會受影響 |
| **修復** | `RENDER=true` 時 `app.wsgi_app = ProxyFix(..., x_for=1, ...)` |
| **持久碟** | 已存在：`render.yaml` disk `/data` + `DATA_DIR`；`/api/version` 已驗證 |

**勿重複建議**：再建 Persistent Disk / `DATA_DIR=/data`（已配置）；`combat/status` 已只在 `player_phase`/`resolving` 才 `advance_combat_from_poll`。

---

## 2026-07-02 — 最後一擊跳過結算 Modal + reconcile winner 遺漏（Gemini audit）

| 項目 | 內容 |
|------|------|
| **症狀** | 秒殺／Session restore 後無傷害結算 Modal、卡死無勝利畫面 |
| **根因** | ① 勝利路徑未保證 `round_settlement` ② `reconcile_finished_active_combat` 設 `ended` 但 `winner=NULL` |
| **修復** | `_json_victory_outcome` + reconcile `winner='squad'` + `combat_outcome_if_finished` 推斷 winner；`api_client` `isFetching` 鎖 |
| **驗證** | `test_combat_flow` 297/297 · `test_db_hardening` 14/14 |

**勿重複建議**：V2 前端在 `static/js/combat/`（唔係 `index.html` inline）；正式環境為 **Render** https://oikonomia.onrender.com

---

## 2026-07-02 — Render.com 遷移完成（Starter / Singapore）

| 項目 | 內容 |
|------|------|
| **正式 URL** | https://oikonomia.onrender.com（Service `srv-d8v8i7cvikkc73fbsv0g`） |
| **PA 角色** | 降為**後備**；營會流量走 Render |
| **持久資料** | `/data/oikonomia.db`、`/data/uploads/`、`.secret_key`、`.gm_pin`、`.combat_v2` |
| **Deploy** | push `main` → CI `pre_deploy_checks` → POST Deploy Hook → `preDeployCommand` |
| **驗證** | `curl …/api/version` → `render: true`、`data_dir: /data`、`version` = git short hash |
| **Commit** | `895405c`–`c3252df`（`render.yaml`、gunicorn、`deploy/render-*`） |

**勿重複建議**：再當 PA 為主機；新功能要考慮 `/data` 持久碟同 gunicorn 多 worker。Deploy Hook URL **勿** commit（用 GitHub Secret `RENDER_DEPLOY_HOOK`）。

### 2026-07-02 — Render version 顯示舊 hash（`3017e16`）假陽性

| 項目 | 內容 |
|------|------|
| **症狀** | `/api/version` 長期 `3017e16`，與 `main` 不符；但 `render: true`、`combat_v2: true` 正常 |
| **根因** | ① `.deploy-version` **誤 commit** 入 git（值 `3017e16`）② Dashboard **未設** `preDeployCommand`（log 無 `=== Render pre-deploy ===`） |
| **修復** | `.deploy-version` 加入 `.gitignore` 並從 repo 移除；`read_deploy_version()` fallback `RENDER_GIT_COMMIT`；`startCommand` 開跑前執行 `render-predeploy.sh` |
| **Dashboard** | Settings → Start Command 應與 `render.yaml` 一致（含 `render-predeploy.sh`）；建議加 Pre-deploy command |

**勿重複建議**：version 舊唔代表 code 未 deploy；先查 log 有無 preDeploy、`.deploy-version` 有無被 commit。

**文檔**：詳見 `README.md`（Deploy 陷阱）、`AGENT_HANDOFF.md`（Render Deploy 陷阱）、`GEMINI_REVIEW.md` §28。

---

## 設定與環境變數速查（易出問題）

| 設定 | 位置 | 常見問題 | 正確做法 |
|------|------|----------|----------|
| `SECRET_KEY` | **Render** `/data/.secret_key` 或 Dashboard | 未設 → session 失效 | `deploy/render-predeploy.sh` 或 Dashboard env；`utils/production_secrets.py` |
| `GM_PIN` | **Render** `/data/.gm_pin` 或 Dashboard | GM 登入失敗 | 同上 |
| `DATA_DIR` | **Render** | 必須 `/data`（Persistent Disk） | `render.yaml` 已設；唔好用 `project/src/data` |
| Render deploy 落後 | GitHub / Hook | push 後 `version` 仍舊 | 確認 CI `deploy-render` job；手動 `deploy/render-trigger-deploy.sh` |
| `RENDER` | Render env | `true` 時上傳目錄改 `/data/uploads` | `app.py` + `utils/env.py` |
| `SECRET_KEY` | PA Web worker（後備） | Bash `export` **唔會**傳入 worker | `data/.secret_key`（`deploy/pa-ensure-secret.sh`） |
| `GM_PIN` | PA Web worker（後備） | 同上 | `data/.gm_pin` 或 Web tab env |
| `DATA_DIR` | PA（後備） | 應指向 `~/oikonomia/data` | `pa-update.sh` 會 set |
| Deploy 後未 Reload | PA Web tab | running code 仍舊 | Web → Reload（僅 PA rollback 時） |
| `FORCE=1` | `pa-update.sh` | 一般 `git pull` 失敗 | PA 上一律 `FORCE=1 bash ~/oikonomia/deploy/pa-update.sh` |
| `COMBAT_V2` | env / `data/.combat_v2` | **預設開啟**；GM 後台「戰鬥監控」可關閉；`COMBAT_V2=0` env 強制關 | 營會正常應 `combat_v2: true`；關閉只顯示維護提示 |
| `OIKONOMIA_SHOW_TEST_ENCOUNTERS` | env | `1` 時非 GM 都見到測試 encounter | Production **唔好**設；僅開發／GM 測試用 |
| `OIKONOMIA_ENDING_ENABLED` | env | `0` 停用 ending orchestrator 副作用 | 測試用；production 預設 `1` |
| `OIKONOMIA_FORCED_ROUTE` | env · `data/route_config.py` | **預設 `iggy`**：全線強制 Iggy；空字串=` ` 恢復雙線；`marah` 強制 Marah | 營會 production 保持預設；Marah 測試先要 unset／空值 |
| `OIKONOMIA_ZOO_UNLOCK_STAGE` | env · `data/combat_feature_config.py` | **預設 `2`**：story stage 達標先解鎖 Zoo；`0`=一開始就開 | Production 用預設；CI／pre_deploy 設 `0` |
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
| **全線 Iggy（2026-07-21）** | `FORCED_ROUTE=iggy`：玩家唔可以揀 Marah；建隊自動 Iggy | **刻意設計**（營會設定）；唔係 picker bug |
| **開局無 Zoo（2026-07-21）** | story stage < 2 時戰鬥隱藏 Zoo；後端拒 `use_zoo`；主角 AI 唔 Zoo | **刻意設計**；解鎖後先顯示 |
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

## 2026-07-21 — 全線強制 Iggy 路線

| 項目 | 內容 |
|------|------|
| **症狀若誤解** | 玩家見唔到 Marah 選項／揀 Marah 被拒 |
| **刻意設計** | 營會全線 Iggy；`data/route_config.py` `FORCED_ROUTE` 預設 `iggy` |
| **回滾** | env `OIKONOMIA_FORCED_ROUTE=`（空）→ 恢復雙線 |
| **驗證** | `curl /api/version` → `"forced_route": "iggy"`、`markers.forced_route_iggy: true` |
| **詳細** | `decisions_log.md` § 2026-07-21 |

**勿重複建議**：唔好當「路線選擇 UI 壞咗」重開 dual-route UI；除非 Tak 明確取消 forced route。

---

## 2026-07-21 — 戰鬥骰 UI 顯示非 0 但實際 0 傷

| 項目 | 內容 |
|------|------|
| **症狀** | 攻擊顯示骰 1/3，結算 0 傷（server 實際骰 0） |
| **根因** | V2 前端 **cosmetic 骰** 當最終結果顯示；server `roll_combat_dice()` 才係權威 |
| **修復 v1** | 確認前「？」→ 體感差，已 superseded |
| **修復 v2（方案 A）** | 攻擊／Zoo **即 submit**；旋轉動畫 **落地 server `dice_result`**；無「？」 |
| **檔案** | `static/js/combat/index.js`、`dice_modal_view.js` |

**勿重複建議**：唔好再把 client `Math.random()` 結果當最終骰面。

---

## 2026-07-21 — 戰鬥頭像空白

| 項目 | 內容 |
|------|------|
| **症狀** | 進戰鬥畫面玩家頭像唔顯示 |
| **根因** | `_combat_player_avatar_url` 用 `basename` 砍掉 `new avatars for players/`；`default.png` 缺失 |
| **修復** | 保留 subdir + URL encode；補 `static/avatars/default.png` |

---

## 2026-07-21 — GM 回血後仍顯示已死亡／無法再戰

| 項目 | 內容 |
|------|------|
| **症狀** | Zubimendi 死後 GM 改 HP，再進戰仍「已死亡／瀕死」 |
| **根因** | 瀕死 flag `near_death_until` 未清；前端 `isMemberCollapsed` 見 flag 就判死，唔理 HP |
| **修復** | `is_near_death_active`：HP>0 即非瀕死；`update_squad(hp>0)` 清 flag；前端對齊 |
| **GM 操作** | 再 set 一次 HP>0 即可清 DB；或等 deploy 後舊 flag 亦唔再擋 HP>0 玩家 |

---

## 2026-07-21 — 非秒殺卡喺上回合擲骰 popup

| 項目 | 內容 |
|------|------|
| **症狀** | 一擊唔死敵人時，卡喺顯示上回合骰面嘅 message box |
| **根因** | Plan A 攻擊路徑唔經 `CONFIRM_DICE`，冇 `HIDE_DICE`；`SUBMIT_SUCCESS` 只開 settlement 唔關 dice |
| **修復** | 所有 `SUBMIT_SUCCESS`／`SUBMIT_ERROR`／`ACK_SETTLEMENT` 加 `HIDE_DICE`；`onSubmitSuccess` 開頭強制 hide |

---

## 2026-07-21 — 逃離成功但 UI 仍顯示 Iggy 未行動

| 項目 | 內容 |
|------|------|
| **症狀** | 逃離後 ~10s 顯示「逃離成功」，但主角 Iggy 仍顯示等待中／可行動 |
| **根因** | (1) poll `syncState` **未處理** `winner=escaped`；(2) 結束戰鬥 API 對 escaped 只回精簡 JSON；(3) 超時喺 escape 確認畫面會誤轉防禦 |
| **修復** | poll 同步 ESCAPED+SHOW_ESCAPED；ended+escaped 回完整 escape payload；escape 超時自動確認逃跑；結束後隊伍狀態顯示「已脫離」 |

---

## 驗證清單（改動後）

```bash
# 本地（要有 venv）
./venv/bin/python3 scripts/test_combat_flow.py
./venv/bin/python3 scripts/test_ending_flow.py

# Render（deploy 後 · 正式）
curl -s https://oikonomia.onrender.com/api/version | python3 -m json.tool

# PA（後備 · 可選）
curl -s https://takjai.pythonanywhere.com/api/version | python3 -m json.tool
```

預期：`success: true`，`render: true`（Render），`version` 與 `git rev-parse --short HEAD` 一致；`forced_route: "iggy"`。

---

## 變更本檔嘅規則（Grok Build）

每次修復 **production 問題**、**玩家回報假陽性**、或新增 **env／設定陷阱**，應喺本檔加一節（日期倒序），包含：

- 症狀（用戶看到咩）
- 根因（技術上點解）
- Commit（如有）
- **勿重複建議**（俾 Grok／Gemini 避開重複勞動）

重大架構決策仍寫入 `decisions_log.md`；本檔專注**實戰踩坑**。