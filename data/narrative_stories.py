"""Narrative story content for the story UI — Iggy Arc (設定1)."""

NARRATIVE_PORTRAITS = {
    "Iggy": "/static/portraits/guardian_male_01.png",
    "Marah": "/static/portraits/healer_female_01.png",
    "Julian": "/static/portraits/seeker_female_02.png",
    "Salvio": "/static/portraits/visionary_female_04.png",
    "Donna": "/static/portraits/healer_female_01.png",
    "Judas": "/static/portraits/seeker_female_02.png",
    "旁白": "/static/portraits/visionary_female_04.png",
}

NARRATIVE_STORIES = {
    "welcome": {
        "story_id": "welcome",
        "chapter": "OIKONOMIA · COSMOS",
        "title": "歡迎來到 Cosmos",
        "current_stage": 0,
        "total_stages": 1,
        "route": None,
        "min_stage": 0,
        "skippable": True,
        "replayable": True,
        "lines": [
            {
                "character": "旁白",
                "text": (
                    "Cosmos 有不可違抗的法則：責任、因果、尊重。"
                    "試圖建立「無痛溫室」、迴避現實與創傷，只會養出怪獸，並令系統崩潰。"
                ),
            },
            {
                "character": "旁白",
                "text": (
                    "Zoo——靈獸——是心理防禦與潛能的具象化。"
                    "只有直面真實自我、承擔摩擦力的人，才能駕馭它。"
                ),
            },
            {
                "character": "旁白",
                "text": (
                    "兩極失衡：Polis 用痛苦強迫成長，製造空殼木偶；"
                    "Oikos 用「愛」消除一切負面感受，養出巨嬰。"
                    "你將走進 Iggy 的故事——討好者的界線之路。"
                ),
            },
            {
                "character": "旁白",
                "text": "加入小隊、完成任務、面對遭遇。界線不會自己守住。",
            },
        ],
    },
    # —— Act 1 / stage 0 ——
    "iggy_stage0": {
        "story_id": "iggy_stage0",
        "chapter": "ACT 1 — 雪山",
        "title": "雪山與醬板鴨",
        "current_stage": 1,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 0,
        "skippable": True,
        "replayable": True,
        "lines": [
            {
                "character": "旁白",
                "text": (
                    "Iggy 與 Marah 交戰。鳳凰 Zoo 失控，他又被擊敗，"
                    "從高處墜入雪山——能力與記憶短暫消散。"
                ),
            },
            {
                "character": "Iggy",
                "text": "……好冷。你是誰？我……為什麼在這裡？",
            },
            {
                "character": "旁白",
                "text": (
                    "你在雪山上遇見他。要確認他的身份，需要找出他的貼身物品；"
                    "要幫他撐下去，需要一隻——醬板鴨。"
                ),
            },
            {
                "character": "Iggy",
                "text": "如果……如果你肯幫我，我欠你一次。不管我是誰。",
            },
        ],
    },
    "iggy_stage1": {
        "story_id": "iggy_stage1",
        "chapter": "ACT 2 — 逃亡",
        "title": "虛妄的羔羊與引路人",
        "current_stage": 2,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 1,
        "skippable": True,
        "replayable": True,
        "lines": [
            {
                "character": "旁白",
                "text": (
                    "逃亡途中，你們目擊 Polis 的殘暴拷問。"
                    "「沒有痛苦就沒有成長」——他們用鎖鏈實踐這句話。"
                ),
            },
            {
                "character": "Iggy",
                "text": (
                    "如果我走出去……如果我替他們擋下一切……"
                    "是不是就不會再有人痛？我可以的。我應該的。"
                ),
            },
            {
                "character": "Julian",
                "text": "別傻了。現在不是讓你當祭品的時候。——跟我走。",
            },
            {
                "character": "旁白",
                "text": (
                    "Julian 擊退敵人，成為「引路人」。"
                    "你卻隱約感到：他救下的，不只是命——還有可被利用的感恩。"
                ),
            },
        ],
    },
    "iggy_stage2": {
        "story_id": "iggy_stage2",
        "chapter": "ACT 3–4 — 裂痕與血田",
        "title": "溫室的裂痕 · 血田的獠牙",
        "current_stage": 3,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 2,
        "skippable": False,
        "replayable": True,
        "lines": [
            {
                "character": "Julian",
                "text": "來，Iggy。我會幫你找回記憶。你只要……再信我一次。",
            },
            {
                "character": "Iggy",
                "text": (
                    "那些我救過的人……為什麼對我只有索取？"
                    "我的「包容」……是在製造巨嬰嗎？"
                ),
            },
            {
                "character": "旁白",
                "text": (
                    "在你引導下，Iggy 第一次清楚說出「不」。"
                    "麻醉之炎轉為帶灼熱的涅槃之火——痛，卻能燒斷病態共生。"
                ),
            },
            {
                "character": "Julian",
                "text": "很好……能力覺醒了。那這份力量，就由我來收割吧。——血田，開。",
            },
            {
                "character": "旁白",
                "text": "背刺。Julian 露出真面目。你必須與他戰鬥，守護剛點燃的界線之火。",
            },
        ],
    },
    "iggy_stage3": {
        "story_id": "iggy_stage3",
        "chapter": "ACT 5–6 — 業火與結局",
        "title": "業火與重塑 · 打破無傷神話",
        "current_stage": 4,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 3,
        "skippable": False,
        "replayable": True,
        "lines": [
            {
                "character": "旁白",
                "text": (
                    "Julian 承受不了「承擔真實痛苦與責任」的重量，能力暴走。"
                    "Oikos 成員集體失控——溫室崩裂成災難。"
                ),
            },
            {
                "character": "Iggy",
                "text": "這次……我不逃了。我們一起，把有毒的共生燒斷。",
            },
            {
                "character": "Salvio",
                "text": (
                    "何必如此痛苦？回到我身邊。"
                    "無痛的烏托邦才是愛。——脆弱，才是罪。"
                ),
            },
            {
                "character": "Iggy",
                "text": (
                    "愛有時需要衝突，需要必要的痛。"
                    "我不再相信「絕對不造成任何痛楚」的神話。"
                ),
            },
            {
                "character": "旁白",
                "text": "最後的領域在前方。擊敗 Salvio，摧毀有毒體制。",
            },
        ],
    },
    # Keep thin Marah stubs (camp mainline is Iggy)
    "marah_stage0": {
        "story_id": "marah_stage0",
        "chapter": "MARAH — 支線",
        "title": "智慧的開端",
        "current_stage": 1,
        "total_stages": 4,
        "route": "marah",
        "min_stage": 0,
        "skippable": True,
        "replayable": True,
        "lines": [
            {
                "character": "Marah",
                "text": (
                    "我是 Marah。有人叫我控制狂——我叫它「必要的痛」。"
                    "這次營會主線在 Iggy；若你仍選擇我，請以韌性面對界線。"
                ),
            },
            {
                "character": "旁白",
                "text": "（主線以 Iggy Arc 為準；Marah 內容保留作對照與未來擴充。）",
            },
        ],
    },
    "marah_stage1": {
        "story_id": "marah_stage1",
        "chapter": "MARAH — 支線",
        "title": "低語的解析",
        "current_stage": 2,
        "total_stages": 4,
        "route": "marah",
        "min_stage": 1,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "Marah", "text": "暴政之毒與恩典解藥只有一線之隔——你站在哪邊？"},
        ],
    },
    "marah_stage2": {
        "story_id": "marah_stage2",
        "chapter": "MARAH — 支線",
        "title": "韌性的考驗",
        "current_stage": 3,
        "total_stages": 4,
        "route": "marah",
        "min_stage": 2,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "Marah", "text": "強迫成長不是愛。但放任巨嬰也不是。"},
        ],
    },
    "marah_stage3": {
        "story_id": "marah_stage3",
        "chapter": "MARAH — 支線",
        "title": "覺醒",
        "current_stage": 4,
        "total_stages": 4,
        "route": "marah",
        "min_stage": 3,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "Marah", "text": "當痛楚成為尊重而非武器時，獅蠍才真正屬於你。"},
        ],
    },
}

# Conditional fragments for trauma / ending (triggered via services.narrative)
CONDITIONAL_NARRATIVE_FRAGMENTS = {
    "weakness_grace": {
        "fragment_id": "weakness_grace",
        "summary": "界線仍清晰。記得：能力是在人的軟弱上顯得完全（林後 12:9）。",
        "lines": [
            {
                "character": "旁白",
                "text": "你們仍走在光中。軟弱不是羞恥，而是讓恩典有空間停留的地方。",
            },
        ],
    },
    "trauma_caution": {
        "fragment_id": "trauma_caution",
        "summary": "主角身上留有創傷——請彼此守望，在軟弱中同行。",
        "lines": [
            {
                "character": "旁白",
                "text": "裂縫正在加深。此刻需要的不是獨自硬撐，而是誠實與禱告。",
            },
        ],
    },
    "trauma_critical": {
        "fragment_id": "trauma_critical",
        "summary": "創傷已逼近臨界——再受重創可能無法迎來真正的救贖結局。",
        "lines": [
            {
                "character": "旁白",
                "text": "陰影在主角心裡扎根。全隊需要放慢腳步，為彼此守住界線。",
            },
        ],
    },
    "bad_ending_locked": {
        "fragment_id": "bad_ending_locked",
        "summary": "心理創傷過深，故事已走向陰影結局。",
        "lines": [
            {
                "character": "旁白",
                "text": "你們贏過不少戰役，卻輸給了未處理的傷。盼望仍在基督裡，但此行的結局已偏離。",
            },
        ],
    },
}
