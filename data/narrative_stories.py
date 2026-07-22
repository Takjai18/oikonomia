"""Narrative story content for the story UI — Iggy Arc (設定1)."""

NARRATIVE_PORTRAITS = {
    "Iggy": "/static/portraits/guardian_male_01.png",
    "Marah": "/static/portraits/healer_female_01.png",
    "Julian": "/static/portraits/seeker_female_02.png",
    "Savio": "/static/portraits/visionary_female_04.png",
    "Donna": "/static/portraits/healer_female_01.png",
    "Judas": "/static/portraits/seeker_female_02.png",
    "旁白": "/static/portraits/visionary_female_04.png",
}

NARRATIVE_STORIES = {
    "welcome": {
        "story_id": "welcome",
        "chapter": "序章 · No Pain No Gain",
        "title": "No Pain No Gain",
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
                    "歡迎來到 Cosmos——一個既充滿無限「可能」，"
                    "又充滿殘酷「跌序」的世界。"
                ),
            },
            {
                "character": "旁白",
                "text": (
                    "在 Cosmos 的法則下，每個人天生都潛藏著一種名為 Zoo 的非凡力量。"
                    "當 Zoo 覺醒，人便能爆發出超越想像的超凡能力："
                    "有人能飛天遁地，有人能發揮出狂暴絕倫的撕裂重擊，"
                    "有人能超速再生，甚至能起死回生。"
                ),
            },
            {
                "character": "旁白",
                "text": (
                    "然而，No Pain, No Gain——這是 Cosmos 不可違抗的秩序法則。"
                    "付出了才會有收穫，覺醒必然伴隨著劇痛。"
                ),
            },
            {
                "character": "旁白",
                "text": (
                    "雖然人人體內都有 Zoo 的種子，但能成功覺醒的人卻屈指可數。"
                    "因為要覺醒 Zoo，人就必須赤裸地直面自己內心最深處的黑暗——"
                    "去凝視那一條又一條從未撕開、從未癒合的血淚傷痕。"
                    "唯有敢於誠實面對真實自我、有勇氣承認自身軟弱的人，"
                    "Zoo 的力量才會在劇痛中誕生。"
                ),
            },
            {
                "character": "旁白",
                "text": (
                    "若是無法誠實面對自己，"
                    "若是無法忍受那如同灼燒般的心理創傷與痛楚……"
                    "Zoo 就永遠無法覺醒。"
                ),
            },
            {
                "character": "旁白",
                "text": "在這片土地上，存在著一個名為 Polis 的國度。",
            },
            {
                "character": "旁白",
                "text": (
                    "Polis 是「No Pain, No Gain」的忠實執行者。"
                    "他們深信，沒有付出就沒有收穫，痛苦是成長的必然，"
                    "任何無痛成長都只是不切實際的幻想。"
                ),
            },
            {
                "character": "旁白",
                "text": (
                    "故此，Polis 實行殘酷的精英主義。"
                    "他們從小逼迫人們不斷努力、咬牙忍痛、力爭上游。"
                    "Polis 從不在意「弱者」，因為在殘酷的世界裡，弱者根本無法生存——"
                    "「物競天擇，適者生存」，失敗者就只能被淘汰。"
                    "對於 Polis 而言，這就是世界的客觀法則，他們不過是順天而行。"
                ),
            },
            {
                "character": "旁白",
                "text": (
                    "在 Polis 的精英制下，確實誕生了一批超級精英，"
                    "帶領國家走向無與倫比的繁榮。"
                    "然而在風光的背後，無數被 Polis 拋棄的失敗者被踩在了腳下。"
                    "他們或是智力平庸、能力不足，或是經歷失敗後無法翻身，"
                    "又或是 Zoo 能力覺醒失敗的破碎靈魂。"
                    "這群被拋棄的人，只能在城市的角落靠撿垃圾為生，"
                    "苟延殘喘，生活猶如地獄。"
                ),
            },
            {
                "character": "旁白",
                "text": "在這群被遺棄的失敗者中，有一個名為 Savio 的人。",
            },
            {
                "character": "旁白",
                "text": (
                    "Savio 出生在一個充滿家暴與衝突的家庭中。"
                    "他無比渴望著一個沒有紛爭、沒有痛苦的世界。"
                    "他不明白，為什麼人的成長一定要伴隨著撕心裂肺的痛苦？"
                    "難道就不能無痛成長嗎？"
                ),
            },
            {
                "character": "旁白",
                "text": (
                    "事實上，Savio 自己早已習慣了忍受痛苦。"
                    "他不介意自己受苦，他只是不希望看到其他人，"
                    "去承受自己曾經遭遇過的絕望。"
                ),
            },
            {
                "character": "旁白",
                "text": (
                    "Savio 原本被 Polis 判定為「Zoo 覺醒失敗者」而遭棄置。"
                    "然而，事實並非如此——Savio 覺醒了一種歷史上從未出現過的神聖力量："
                    "Goat（代罪羔羊）。"
                ),
            },
            {
                "character": "旁白",
                "text": (
                    "這是一項能夠「代替他人承受覺醒之痛」的能力。"
                    "憑藉著 Goat，他能讓身邊的人在幾乎無痛的情況下，安全地覺醒 Zoo。"
                ),
            },
            {
                "character": "旁白",
                "text": (
                    "Savio 深信，既然世界給予了他這種力量，"
                    "就說明世界認同了他的理想：人是可以無痛成長的，"
                    "或者至少……可以由他，來為大家承擔所有的痛！"
                ),
            },
            {
                "character": "旁白",
                "text": (
                    "憑藉著這股強大的力量與大愛，"
                    "Savio 聚集了所有被 Polis 拋棄的弱者，"
                    "創立了一個名為 Oikos 的組織——希臘文中的「家」。"
                ),
            },
            {
                "character": "旁白",
                "text": (
                    "他要建立一個真正的「家」，接納所有被世界傷害的人。"
                    "同時，他也立下誓言……終有一天，"
                    "要徹底推翻 Polis 那冷酷無情的管治！"
                ),
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
                "character": "Savio",
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
                "text": "最後的領域在前方。擊敗 Savio，摧毀有毒體制。",
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
