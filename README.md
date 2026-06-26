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

## 部署（之後）
會部署到 Render.com，方便大家用網上連結玩。