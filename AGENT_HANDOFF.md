# Oikonomia — Agent Handoff（新 Tab 必讀）

> **給下一個 AI Agent**：用戶會開新 tab 繼續開發。請**直接執行**，唔好只係話用戶點做。  
> 最後更新：2026-06-28

---

## 專案概覽

| 項目 | 值 |
|------|-----|
| 專案路徑 | `/Users/mingtakyau/Documents/oikonomia` |
| 主檔 | `app.py`（單體 Flask + 內嵌 HTML/JS，~8500 行） |
| 資料庫 | `oikonomia.db`（本地）；PA 上在 `data/oikonomia.db` |
| GitHub | https://github.com/Takjai18/oikonomia |
| 正式環境 | https://takjai.pythonanywhere.com |
| GM 後台 | https://takjai.pythonanywhere.com/gm （PIN: `gm2026`） |
| 本地開發 | `source venv/bin/activate && python3 app.py` → http://localhost:5001 |

**主題**：Summer Camp 2026 ARG（Oikonomia 青年營會），Iggy / Marah 雙主角路線。

---

## 用戶期望（重要）

1. **Agent 要自己執行** — 改 code、跑測試、commit、push、更新 PA，唔好淨係出 instruction。
2. **每次有 code 改動都要更新 PythonAnywhere** — 見下方 Deploy 流程。
3. **唔好亂改無關檔案** — `app.py` 係核心；`encounters/*.json` 係 encounter 定義。
4. **唔好 commit `*.db`** — 已在 `.gitignore`。

---

## 本輪已完成（Combat / Encounter 系統）

### 後端（`app.py`）

- **中文屬性標籤**：生命值、神智、力量、智力、韌性（ID 不變）
- **Encounter JSON**：`encounters/enc_iggy_01_leech.json`（巨嬰之影：情緒勒索）
- **DB 表**：`combats`、`encounter_completions`；`squads` 新增 `trauma_*`、`near_death_until`、`current_combat_id`、`insight_fragments`、`status_effects`
- **`migrate_db()`** 會自動加欄位 — PA 上 reload 後第一次 request 會跑 migration

### Combat API

| 端點 | 用途 |
|------|------|
| `POST /combat/start` | 開始戰鬥 + precheck |
| `GET /combat/status` | 輪詢（`?combat_id=` 或 `?squad_id=`） |
| `POST /combat/submit_action` | 提交行動 + 骰子 0–3 |
| `POST /combat/resolve_phase` | 強制結算 player phase |
| `POST /combat/rescue_near_death` | 禱告救援（縮短 5 分鐘瀕死） |
| `POST /encounters/<id>/start` | alias → `/combat/start` |
| `GET /encounters` | encounter 列表 |

### `resolve_player_phase(combat_id)` 核心邏輯

```
傷害：floor((stat×2 + item_bonus) × multiplier) − armor
骰子倍率：0→0, 1→1.0, 2→1.5, 3→2.0
Zoo（use_zoo）：神智 ≥70/80/90/100 → ×1.3/1.4/1.5/1.8
暴走機率：神智 <10→90%, <20→50%, <40→20%
暴走效果：30% 自傷（power×0.3），否則行動失控
敵人反擊：攻擊全隊韌性最低者；defend 減傷 50%
瀕死：HP≤0 → near_death_until +15 分鐘
回傳：(combat, winner) — 'squad' | 'enemy' | None
```

### 前端（內嵌於 `app.py` HTML_TEMPLATE）

- `#combat-screen`：Phase 倒數、敵人 HP、隊伍卡、6 種行動、骰子、Log
- Precheck modal、瀕死 overlay、勝敗反思頁
- 暴走 UI 已對齊三段門檻（<10 / <20 / <40）
- 輪詢 8 秒；Iggy 酒紅 / Marah 海軍藍 accent

### 靜態資源

- `static/images/items/*.svg` — 物品圖示
- `static/avatars/` — 頭像（Niel.png、Yiu.png、default.png）

---

## 尚未完成（下一個 Agent 可優先做）

| 優先 | 項目 | 說明 |
|------|------|------|
| P0 | **部署到 PA** | 見下方；確保 `/api/version` commit 係最新 |
| P1 | **實機測試 combat** | Team + Iggy 路線 → `enc_iggy_01_leech` 全流程 |
| P2 | GM 強制結算按鈕 | `/combat/resolve_phase` 已有 API，GM UI 未做 |
| P3 | Defend 全隊 buff | 目前只對「被反擊目標」減傷 50% |
| P4 | 更多 encounter JSON | Marah 線、stage 2+ |
| P5 | 瀕死 background timer | 目前靠 polling + `near_death_until` |

---

## Deploy 流程（PythonAnywhere）— Agent 必須執行

### 標準流程（GitHub → PA）

```bash
# 1. 本地：驗證 + commit + push
cd /Users/mingtakyau/Documents/oikonomia
./venv/bin/python3 -m py_compile app.py
git add -A && git commit -m "描述改動" && git push origin main

# 2. PA Bash console（用戶帳號 takjai）
bash ~/oikonomia/deploy/pa-update.sh

# 3. PA Web tab → Reload takjai.pythonanywhere.com

# 4. 驗證
curl https://takjai.pythonanywhere.com/api/version
```

### 驗證 marker

`/api/version` 應包含：

```json
{
  "version": "<git short commit>",
  "markers": {
    "combat_system": true,
    "show_only_protagonist": true
  }
}
```

`deploy/pa-update.sh` 會檢查 `resolve_player_phase` 是否存在。

### Agent 無法 SSH 時

本機通常**無** `takjai@ssh.pythonanywhere.com` 金鑰。若 SSH 失敗：

1. 完成 git push
2. 請用戶在 PA Bash 跑 `bash ~/oikonomia/deploy/pa-update.sh` + Web Reload  
   **或** 提供 PA API token / SSH 設定
3. 用 `curl /api/version` 確認遠端 commit

### PA 重要設定

- **WSGI**：import `wsgi.application`
- **Static files**：**唔好** map `/uploads/`（交俾 Flask route）
- **DATA_DIR**：`wsgi.py` 設為 `~/oikonomia/data`
- **DB migration**：app 啟動時 `init_db()` → `migrate_db()` 自動跑

---

## 本地開發速查

```bash
cd /Users/mingtakyau/Documents/oikonomia
source venv/bin/activate
python3 app.py                    # → :5001
./venv/bin/python3 -m py_compile app.py
```

| 用途 | 值 |
|------|-----|
| GM PIN | `gm2026` |
| 重置遊戲 | `reset2026` |
| 清空上傳 | 確認碼 `CLEAR_IMAGES` |

---

## 關鍵檔案地圖

```
oikonomia/
├── app.py                          # 全部邏輯 + UI
├── wsgi.py                         # PA 入口
├── deploy/pa-update.sh             # PA 更新腳本
├── encounters/enc_iggy_01_leech.json
├── static/images/items/*.svg
├── static/avatars/
├── requirements.txt                # flask
├── README.md                       # 簡短說明
└── AGENT_HANDOFF.md                # 本檔（新 tab 必讀）
```

### `app.py` 重要函數（行號可能隨改動漂移，用 grep 搵）

- `init_db()` / `migrate_db()` — DB schema
- `resolve_player_phase()` — 戰鬥結算
- `calculate_damage()` / `calculate_incoming_damage()`
- `berserk_probability()` / `is_berserk()` / `zoo_bonus_multiplier()`
- `build_combat_status_response()` — API 輪詢 payload
- `load_encounter()` — 讀 `encounters/*.json`

---

## 對話脈絡（上一個 tab）

用戶提供了 `resolve_player_phase` 草稿；已整合進 `app.py` 並擴充（最低韌性反擊、瀕死、trauma、phase 推進）。  
前端暴走 UI 已對齊 <10/<20/<40 三段。  
用戶因 context window 將滿，要求寫 handoff README 並**執行部署**。

---

## 新 Tab 開場白建議

用戶可以貼：

```
請讀 /Users/mingtakyau/Documents/oikonomia/AGENT_HANDOFF.md，
繼續 Oikonomia 開發。先 curl /api/version 確認 PA 版本，
然後做 P1 實機測試或我指定的任務。記得自己執行，唔好只出 instruction。
```