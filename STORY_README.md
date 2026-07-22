# Oikonomia — 劇情更新專用說明（Grok Build）

> **用途**：只更新遊戲劇情／文案時用。  
> **目標**：慳 token——**唔好**讀 combat、部署、GEMINI、COMBAT bundle、全站 assessment。  
> **讀者**：Grok Build（實作）· 用戶交劇情稿時請標 **【劇情更新】**

---

## 0. 開場必做（只做這些）

1. **只讀本檔** + 下面列出的 **data 檔**（按任務選讀）。  
2. **禁止**主動讀：`models/combat.py`、`static/js/combat/**`、`COMBAT_V2_*`、`GEMINI_REVIEW.md`、`bug_log/**`、整份 `AGENT_HANDOFF.md`（除非用戶明確要求接戰鬥敘事）。  
3. 改完：**語法可 parse** → 簡述改了邊個 `story_id` → 用戶若寫「commit+push」先做。  
4. 回覆 **≤ 8 行**（改咗咩、點試）；唔寫長 review。

```
【劇情更新】
範圍：welcome | iggy_stageN | marah_stageN | STORY_CONTENT | 結局碎片 | 世界觀
內容：<貼新文案或「改第 X 段」>
完成：commit+push（可選）
```

---

## 1. 劇情資料在邊（SSOT）

| 檔案 | 改咩 | 幾時讀 |
|------|------|--------|
| **`data/narrative_stories.py`** | **主對話**：`NARRATIVE_STORIES` 的 `lines[]`、章節標題；頭像表 `NARRATIVE_PORTRAITS` | **幾乎所有劇情改文** |
| **`data/story_config.py`** | 階段門檻 `STORY_STAGE_THRESHOLDS`；Dashboard 短摘要 `STORY_CONTENT` | 改「做幾多任務先 unlock」或階段卡文案 |
| **`data/cosmos_lore.py`** | 世界觀／角色設定（背景文，多數未直接推 UI 對白） | 改設定、GM 備註、對齊 lore |
| **`data/route_config.py`** | 強制路線（營會預設 **Iggy**） | 改路線政策時 |
| **`data/act1_qr_hooks.py`** | Act1 QR → 任務／教學戰 | 改 Act1 道具觸發敘事流程時 |
| **`data/locations.py`** | 探索任務名／描述（會出現在劇情「去做任務」指引） | 劇情提到任務名要一致時 |
| **`encounters/*.json`** | 勝敗 `narrative`、遭遇標題 | 只改戰鬥前後旁白時（**唔改數值公式**） |
| **`static/portraits/`** | 立繪圖檔 | 加角色圖時 |

**幾乎唔使改（劇情文案任務）**：`routes/story.py`、`services/story.py`、`services/narrative.py`——邏輯已穩；只改 data 即可。

---

## 2. 玩家會點樣見到劇情

```
PIN 登入
  → pending: welcome（序章，必看一次）
  → 分配能力值 stats_allocated
  → 按任務數解鎖 stage 0→3
  → pending: {route}_stage{N}  （例如 iggy_stage0）
  → 看完 mark viewed（story_views 表）
```

| 規則 | 說明 |
|------|------|
| 主線 ID 格式 | `{route}_stage{stage}` → `iggy_stage0` … `iggy_stage3` |
| stage 點計 | 全隊 **distinct 完成任務數** vs `STORY_STAGE_THRESHOLDS` |
| 現時門檻（可改） | stage1 要 **4** 個任務；stage2 要 **7**；stage3 要 **11** |
| 營會路線 | 預設 **強制 Iggy**（`OIKONOMIA_FORCED_ROUTE` / `route_config.py`） |
| Marah | 文案仍可改，但玩家流程通常唔會揀到 |

### 現有 `story_id` 一覽

| story_id | 用途 |
|----------|------|
| `welcome` | 序章世界觀（PIN 後、建角前） |
| `iggy_stage0` | Act 1 雪山 |
| `iggy_stage1` | Act 2 |
| `iggy_stage2` | Act 3–4 |
| `iggy_stage3` | Act 5–6 |
| `marah_stage0`…`3` | Marah 線（後備） |
| `weakness_grace` / `trauma_caution` / `trauma_critical` / `bad_ending_locked` | 結局／創傷碎片（條件觸發） |

---

## 3. 對話條目格式（改文時跟）

```python
"iggy_stage0": {
    "story_id": "iggy_stage0",       # 必須同 dict key 一致
    "chapter": "ACT 1 — …",
    "title": "短標題",
    "current_stage": 1,              # UI 用；可同 min_stage 一齊對齊
    "total_stages": 6,
    "route": "iggy",                 # welcome 用 None；主線用 "iggy" / "marah"
    "min_stage": 0,                  # 玩家 story stage ≥ 此值先可看
    "skippable": True,
    "replayable": True,
    "lines": [
        {
            "character": "旁白",     # 或 "Iggy" / "Julian" / "Savio" …
            "text": "對白內容。",    # 繁中；可多段字串元組相加
        },
        {
            "character": "Iggy",
            "text": "有頭像的角色行。",
        },
    ],
},
```

### 頭像

- 表：`NARRATIVE_PORTRAITS`（`character` 字串 → `/static/portraits/...`）
- **`旁白`**：UI 當旁白、唔顯示角色頭像  
- 新角色：加 portrait 檔到 `static/portraits/`（**檔名建議 ASCII**）+ 在 `NARRATIVE_PORTRAITS` 登記  
- 已有檔例：`iggy.jpg`、`act1_injured_iggy.jpg`、`julian.png`、`Marah.png`、`Savio.png` …

```python
# 可選：某行強制指定頭像
{"character": "Iggy", "text": "…", "portrait": "/static/portraits/act1_injured_iggy.jpg"}
```

### 寫作注意

- 玩家 UI 文案：**繁體中文**  
- 現場指引要具體（掃邊個 QR、邊個探索任務名）→ 同 `locations.py` / QR hooks **用詞一致**  
- 唔好改 `story_id` key 除非同步改 DB 已 viewed 邏輯（舊玩家可能重睇或永遠 skip）  
- 長句用括號串接，保持檔案可讀：

```python
"text": (
    "第一句。"
    "第二句。"
),
```

---

## 4. 階段門檻與 Dashboard 摘要

**`data/story_config.py`**

- `STORY_STAGE_THRESHOLDS`：`{ 1: 最少任務數, 2: …, 3: … }`  
- `STORY_CONTENT[route][stage]`：Dashboard 階段卡 **title + content**（短文，唔係全套對白）  
- `STORY_STAGE_REQUIRED_TASKS`：可選「必須完成某 task_id 先升 stage」（預設註解關閉）

改 Act 結構時：**thresholds + STORY_CONTENT + narrative `iggy_stage*` 一齊對齊**。

---

## 5. 常見任務類型（只改相關檔）

| 你想做 | 改邊啲 |
|--------|--------|
| 改某 Act 對白 | 只改 `narrative_stories.py` 對應 `iggy_stageN` 的 `lines` |
| 改序章 | 只改 `welcome` |
| 改階段解鎖要幾多任務 | `story_config.py` → `STORY_STAGE_THRESHOLDS` |
| 改 Dashboard 階段簡介 | `story_config.py` → `STORY_CONTENT` |
| 改結局／創傷旁白 | `narrative_stories.py` 底部碎片 + 如有 `CONDITIONAL_NARRATIVE_FRAGMENTS` |
| 改世界觀設定（非對白） | `cosmos_lore.py` |
| 改 Act1「掃木材開戰」類流程文案+連結 | `narrative` 文案 + `act1_qr_hooks.py` + 必要時 `locations`／encounter JSON **只 narrative 欄** |
| 加一章新 stage 故事 | 新 key `iggy_stage4` **不夠**——現階段系統綁 0–3；要加階段必須改 `services/story.py` 門檻邏輯（**超出純文案，先問用戶**） |

---

## 6. 驗證（劇情改完最少做）

```bash
# 語法
python3 -c "from data.narrative_stories import NARRATIVE_STORIES, NARRATIVE_PORTRAITS; print(len(NARRATIVE_STORIES), 'stories')"
python3 -c "from data.story_config import STORY_STAGE_THRESHOLDS, STORY_CONTENT; print(STORY_STAGE_THRESHOLDS)"

# 本地（可選）
# python3 app.py → 登入 → 看故事／pending 是否正常
```

**唔使**跑 `test_combat_flow` 除非動到 encounter 數值或 combat code。

### 上線

```bash
git add data/narrative_stories.py   # 同你改過嘅 data/*
# 有新 portrait：
# git add static/portraits/<file>
git commit -m "story: <一句說明改邊段>"
git push origin main
# Render 自動 deploy；版本：curl -s …/api/version
```

---

## 7. Grok Build 回覆模板（慳 token）

```
已改：data/narrative_stories.py → iggy_stage0（6 行對白）
驗證：import OK
commit：abc1234（若有要求 push）
試：登入 → 待看故事 / 重看 Act1
```

---

## 8. 明確唔做（除非用戶點名）

- 重構 story API / DB schema  
- 改 combat 公式、FSM、HP  
- 讀或更新 `COMBAT_V2_AUDIT_BUNDLE`  
- 全站 code review  
- 為「美觀」大改 `index.html` 故事 UI（只改 data 已夠顯示新文案）

---

*STORY_README · 劇情專用 · 2026-07-23 · 配合 Iggy Arc 主線*
