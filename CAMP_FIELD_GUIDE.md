# 營會現場救場指南（GM）

> **對象**：Tak / 現場 GM  
> **前提**：玩家唔識電腦、唔會作弊；問題多數係 GPS 飄、影相失敗、伺服器冷啟動  
> **正式站**：https://oikonomia.onrender.com · GM：`/gm`  
> **最後更新**：2026-07-21

---

## 0. 開場 2 分鐘（每日）

```bash
# 電腦／手機瀏覽器均可；或本機：
bash deploy/render-check.sh https://oikonomia.onrender.com
```

| 檢查 | 正常值 |
|------|--------|
| `success` | `true` |
| `db_init_error` | `null` |
| `data_dir` / `db_path` | `/data` · `/data/oikonomia.db` |
| `version` / `git_commit` 前 7 字 | 與本機 `git rev-parse --short HEAD` 對齊（而家約 `57bbca7`） |
| `combat_v2` | `true` |
| `forced_route` | `iggy`（營會政策） |

**首次開頁 502 / 很慢**：Render Starter 閒置會睡。等 30–60 秒再 refresh，或先開一次 `/api/version` 喚醒。**唔使當壞機**。

**GM 登入**：`/gm` → PIN（env `GM_PIN`；本地預設 `gm2026`）· session 約 8 小時。

---

## 1. GPS／任務／影相救場（最常用）

### 1.1 玩家話「到咗但定位唔過」

| 步驟 | 做咩 |
|------|------|
| 1 | 問清楚邊個任務（`loc1` 裂縫起點 / `loc2` / `loc3`） |
| 2 | 叫玩家開 **Chrome 或 Safari 完整瀏覽器**（唔好用 WhatsApp 內建瀏覽器） |
| 3 | 開系統定位權限；室外行開少少再試 |
| 4 | 仍唔過 → **GM 人工承認到場**（見下「補獎勵」） |

GPS 任務（`loc1`）設計：**定位有時唔準，靠全組相證明**。現場以「人到 + 有相」為準。

### 1.2 玩家話「影相上唔到／檔案太大」

| 症狀 | 玩家可試 | GM |
|------|----------|-----|
| 檔案太大（上限 8MB） | 用相機影、唔好用超高清相簿原圖；或系統壓縮後再上 | 確認後補獎勵 |
| 只接受 JPEG/PNG | 唔好上 HEIC／截圖異常格式；再影一張 | 同上 |
| 上到但「已計過分」 | 正常：同一 task 全隊只計 **一次** 獎勵 | 唔使再補（除非完全未計） |

### 1.3 GM 補獎勵（任務失敗但現場已完成）

後台：`/gm` → 搵該玩家／小隊 → **調整數值**（API：`POST /gm/adjust`）

| 欄位 | 正常任務首次獎勵 | 建議補法 |
|------|------------------|----------|
| `sanity` | +6（上限 100） | 現值 +6（唔好盲目 +100） |
| `resources` | +1 | 現值 +1 |
| `hp` / 其他 | 任務唔改 | 只在戰鬥／瀕死救場先動 |

**操作口訣**：

1. 開 GM → 對應玩家詳情  
2. 記低目前神智／Resource  
3. 神智 +6、Resource +1（若該 task 從未成功計過分）  
4. 用公告或口頭通知玩家「已幫你補」  
5. 叫玩家 **下拉刷新／等 3 秒** 等 Dashboard 更新  

> 若整隊已有人成功提交同一 `task_id`，系統**唔會**再發首次獎勵——唔好重複 +6。

### 1.4 任務一覽（方便口頭對）

| ID | 名稱 | 類型 | 備註 |
|----|------|------|------|
| `loc1` | 裂縫起點 | GPS + **必須影相** | 全組入鏡 |
| `loc2` | Judas 嘅低語 | puzzle | 無強制 GPS 相 |
| `loc3` | 痛楚回音 | photo | 影「界線」主題相 |

劇情階段：全隊 distinct 任務數約 **2 / 4 / 6** → stage 1 / 2 / 3（見 `data/story_config.py`）。

---

## 2. 其他常見現場（簡表）

| 情況 | 處理 |
|------|------|
| 戰鬥卡住／返唔到大廳 | 硬刷新一次；仍卡 → GM 睇「進行中戰鬥」；必要時等 timeout 或叫玩家重開 encounter |
| 瀕死／崩壞 | 隊友救援；或 GM 調 `hp`／清瀕死（玩家詳情） |
| 忘記 PIN | GM **重置 PIN** |
| 頭像／死圖 | 硬刷新；確認 `version` 已係最新 deploy |
| 全站 502 | 等 1 分鐘喚醒；仍 502 → Render Dashboard 睇 service 是否 suspended |

---

## 3. 伺服器／備份（營運）

| 頻率 | 動作 |
|------|------|
| **每日開場** | `bash deploy/render-check.sh https://oikonomia.onrender.com` |
| **重大環節前**（開戰、結局） | 再 check 一次 version |
| **本地有改動後** | commit → push → 等 Render deploy → 再 check `version` 對齊 |
| **備份** | 對 Grok 講「backup」或跑 skill；同步至 Google Drive `My Drive/oikonomia` |

**持久資料（Render）**：

- DB：`/data/oikonomia.db`  
- 相片：`/data/uploads/`  
- 密鑰：`/data/.secret_key`、`.gm_pin`（或 Dashboard env）  

**絕對唔好**：

- 隨便按「重置遊戲」（會清玩家）— 要密碼 `reset2026`（或 env）  
- 改 `SECRET_KEY` 會令全營 session 失效  

**後備站**（只 rollback）：https://takjai.pythonanywhere.com  

---

## 4. 緊急指令（本機）

```bash
# 健康
bash deploy/render-check.sh https://oikonomia.onrender.com

# 版本一眼
curl -s https://oikonomia.onrender.com/api/version | python3 -m json.tool | head -30

# 本機 commit
cd /Users/mingtakyau/Documents/oikonomia && git rev-parse --short HEAD
```

---

*End of CAMP_FIELD_GUIDE · 2026-07-21*
