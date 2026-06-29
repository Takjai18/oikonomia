# Oikonomia - Summer Camp 2026

Oikonomia 青年營會 ARG（另類實境遊戲）Web App。雙主角路線（Iggy / Marah），含任務提交、遭遇戰、故事階段、GM 後台。

## 功能

- 玩家 Dashboard（HP / 神智 / 力量 / 智力 / 韌性、隊伍、物品、故事）
- GPS 定位驗證、影相上傳（PIL 驗證、8MB 上限）
- Team 協作、任務提交、故事階段解鎖
- Encounter 遭遇戰（precheck、多回合 player phase、瀕死救援）
- GM 後台（隊伍管理、戰鬥監控、公告、重置 PIN、下載隊伍圖片）

## 專案結構（重構後）

```
app.py              # Flask 入口 + DB migrate（~940 行）
wsgi.py             # PythonAnywhere 入口
templates/          # index.html（玩家 UI）、claim_item.html

models/             # 資料層：squad, team, item, encounter, combat
routes/             # Blueprint：auth, player, team, combat, encounters, items, story, misc, gm
services/           # 業務邏輯：story, teams_overview, global_events, gm_admin…
utils/              # helpers, uploads（PIL）, qr, validators, env, deploy
data/               # 靜態遊戲資料：locations, story_config, narrative_stories

encounters/         # Encounter JSON 定義
static/             # 頭像、物品圖、portraits
uploads/            # 玩家上傳相片（不 commit）
deploy/             # PythonAnywhere 部署腳本
```

詳細架構、戰鬥公式、部署狀態見 **[AGENT_HANDOFF.md](./AGENT_HANDOFF.md)**。  
外部 code review（Gemini 等）請讀 **[GEMINI_REVIEW.md](./GEMINI_REVIEW.md)**。

## 本地運行

```bash
cd oikonomia
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

macOS 預設 5000 port 常被佔用，本地預設用 **5001**（`PORT=5002 python3 app.py` 可改）。

## 本地開發網址

| 用途 | 網址 |
|------|------|
| 玩家端 | http://localhost:5001 |
| GM 後台 | http://localhost:5001/gm |
| API 版本 | http://localhost:5001/api/version |

本地預設憑證（非 production）：

| 項目 | 值 |
|------|-----|
| GM PIN | `gm2026` |
| 重置遊戲密碼 | `reset2026`（可用 `RESET_GAME_PASSWORD` 覆寫） |
| 清空上傳圖片確認碼 | `CLEAR_IMAGES` |

Production 必須設定環境變數：`SECRET_KEY`、`GM_PIN`。

## 正式環境（PythonAnywhere）

| 用途 | 網址 |
|------|------|
| 玩家端 | https://takjai.pythonanywhere.com |
| GM 後台 | https://takjai.pythonanywhere.com/gm |

部署（GitHub 有更新後，在 PA Bash）：

```bash
FORCE=1 bash ~/oikonomia/deploy/pa-update.sh
```

然後到 **Web** tab 按 **Reload**。

驗證：

```bash
curl -s https://takjai.pythonanywhere.com/api/version | python3 -m json.tool
```

## 測試

```bash
python3 -m py_compile app.py models/*.py routes/*.py services/*.py utils/*.py
python3 test_combat.py          # 需本地 DB / 環境
```

## AI Agent 交接

| 對象 | 文檔 |
|------|------|
| Cursor / Grok 繼續開發 | **[AGENT_HANDOFF.md](./AGENT_HANDOFF.md)** |
| Gemini / 外部 Engineer review | **[GEMINI_REVIEW.md](./GEMINI_REVIEW.md)** |