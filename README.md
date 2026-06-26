# Oikonomia - Summer Camp 2026

這是 Oikonomia 青年營會的 ARG（另類實境遊戲）Web App 原型。

## 功能
- 美觀 Dashboard（HP + Sanity + Zoo 技能）
- GPS 定位驗證
- 影相上傳 + 任務提交
- 小隊即時狀態

## 本地運行方法

```bash
cd oikonomia
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

然後用瀏覽器打開 http://localhost:5001

（macOS 預設 5000 port 常被系統佔用，所以本地用 5001）

## 正式環境（PythonAnywhere）

| 用途 | 網址 |
|------|------|
| 玩家端 | https://takjai.pythonanywhere.com |
| GM 後台 | https://takjai.pythonanywhere.com/gm |
| GM PIN | `gm2026` |

每次 GitHub 有更新後，在 PythonAnywhere **Bash** 執行：

```bash
bash ~/oikonomia/deploy/pa-update.sh
```

然後到 **Web** tab 按 **Reload**。