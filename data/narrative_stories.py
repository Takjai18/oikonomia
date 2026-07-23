"""Narrative story content — Act 0–3 (Iggy / Oikos mainline)."""

NARRATIVE_PORTRAITS = {
    "Iggy": "/static/portraits/iggy.jpg",
    "Iggy（重傷）": "/static/portraits/act1_injured_iggy.jpg",
    "Marah": "/static/portraits/marah.png",
    "Julian": "/static/portraits/julian.png",
    "Savio": "/static/portraits/savio.png",
    "Donna": "/static/portraits/eonna.png",
    "Judas": "/static/portraits/npc_1.png",
    "旁白": "/static/portraits/villager.png",
}

NARRATIVE_STORIES = {
    "welcome": {
        "story_id": "welcome",
        "chapter": "序章 · No Pain, No Gain",
        "title": "No Pain, No Gain",
        "current_stage": 0,
        "total_stages": 1,
        "route": None,
        "min_stage": 0,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": "歡迎來到 Cosmos——一個既有「可能」，又有「跌序」的世界。"},
            {"character": "旁白", "text": (
                "在 Cosmos 的法則下，每個人天生都潛藏著一種名為 Zoo 的非凡力量。"
                "當 Zoo 覺醒，人便能發揮出各式各樣、超越想像的超凡能力："
                "或是飛天遁地，或是爆發出撕裂重擊，或是超速再生，甚至能起死回生。"
            )},
            {"character": "旁白", "text": (
                "然而，No Pain, No Gain——付出是需要有收穫，覺醒是需要經歷痛苦，"
                "這便是 Cosmos 不可違抗的秩序法則。"
            )},
            {"character": "旁白", "text": (
                "雖然每個人體內都潛藏著 Zoo 的能力，但並不是每個人都能成功覺醒。"
                "因為要覺醒 Zoo，人就必須赤裸地直面自己內心最深處的黑暗——"
                "去凝視那一條又一條從未撕開、從未癒合的血淚傷痕。"
                "唯有敢於誠實面對真實自我、有勇氣承認自身軟弱的人，"
                "Zoo 的力量才會在劇痛中誕生。"
            )},
            {"character": "旁白", "text": (
                "若是無法誠實面對自己，若是無法忍受那如同灼燒般的心理創傷與痛楚……"
                "Zoo 就永遠無法覺醒。"
            )},
            {"character": "旁白", "text": (
                "在這個「NO PAIN, NO GAIN」的世界中，存在著一個名為 Polis 的國度。"
            )},
            {"character": "旁白", "text": (
                "Polis 是「No Pain, No Gain」的忠實執行者。"
                "他們深信，沒有付出便沒有收穫，痛苦是成長的必然，"
                "任何無痛成長都只是不切實際的幻想。"
            )},
            {"character": "旁白", "text": (
                "故此，Polis 實行殘酷的精英教育，從小便要求人們不斷努力，突破自己，力爭上游。"
                "Polis 從不在意「弱者」，因為他們深信弱者在殘酷的世界中是無法生存的——"
                "「物競天擇，適者生存」，無法生存下去的人就只能被淘汰。"
                "對於 Polis 而言，這就是世界的法則，他們只是順天而行。"
            )},
            {"character": "旁白", "text": (
                "在 Polis 的精英制下，確實出現了一班超級精英，帶領整個國家走向繁榮。"
                "然而在風光繁榮的背後，同時出現了一班被 Polis 拋棄的弱者。"
                "他們或是智力不出眾，或是能力不出眾，或是外表不出眾，"
                "或是經歷失敗而無法翻身的人，又或是 Zoo 能力的覺醒失敗者。"
                "這班被拋棄的失敗者，只能每日靠撿垃圾為生，生存猶如處於地獄一般。"
            )},
            {"character": "旁白", "text": "在這班失敗者中，有一個名叫 Savio 的人。"},
            {"character": "Savio", "text": (
                "……我只是不想，再看見任何人，承受我曾經承受過的那種痛。"
            )},
            {"character": "旁白", "text": (
                "Savio 出生在 Polis 一個充滿強烈衝突與高壓的家庭中。"
                "從小看著至親之間的撕扯與冷酷，他無比渴望一個無衝突紛爭的世界。"
                "他不明白為何成長總是帶著痛苦，為何不能無痛成長？"
            )},
            {"character": "旁白", "text": (
                "事實上，Savio 本身早已習慣了面對痛苦。他不介意自己受苦，"
                "只是不希望他人要承受自己所遭遇過的痛苦。"
            )},
            {"character": "旁白", "text": (
                "Savio 本來被 Polis 判斷為 Zoo 能力覺醒失敗，因而被拋棄。"
                "然而事實上他並非覺醒失敗，而是覺醒了一種從來無人覺醒過的能力——"
                "Goat（代罪羔羊）：能「代替他人承受 Zoo 覺醒之痛」，"
                "接近無痛地幫助他人覺醒。"
            )},
            {"character": "Savio", "text": (
                "世界給了我這股力量……就是要證明——"
                "人是可以無痛成長的；或者至少……可以由我，來承擔一部分的痛。"
            )},
            {"character": "旁白", "text": (
                "憑著這股強大的力量，Savio 創立了名為 Oikos 的組織——意思就是「家」。"
                "他希望這個「家」能接納那些被 Polis 拋棄的人；"
                "同時他也決定……終有一天要推翻 Polis 的管治！"
            )},
        ],
    },
    # —— Act 1 after team join ——
    "iggy_stage0": {
        "story_id": "iggy_stage0",
        "chapter": "第一章 · Oikos",
        "title": "飛狐雪山",
        "current_stage": 1,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 0,
        "requires_team": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": "飛狐雪山的風雪如利刃般划過臉龐。"},
            {"character": "旁白", "text": (
                "你們緊了緊身上的防寒衣，背包裡沉甸甸的——那是一隻特別帶上山的「醬板鴨」。"
                "你們本想為山上有需要的野生狐狸帶來一點溫飽與生機。"
                "然而狐狸沒有出現；呈現在眼前的，是一片混亂的戰鬥痕跡，"
                "以及一個躺在雪堆中、滿是血痕與凍傷的年輕男子。"
            )},
            {"character": "旁白", "text": (
                "你們連忙圍上去。那名男子凍得嘴唇發紫，衣物破爛，"
                "呼吸微弱得幾乎感覺不到。"
            )},
            {"character": "旁白", "text": (
                "看著他極度虛弱、奄奄一息的樣子，你們決定先救人！"
                "為了幫他生火取暖，並把醬板鴨烤熱，"
                "你們開始在周圍的雪地裡搜尋——水，與木材。"
            )},
            {"character": "旁白", "text": (
                "請到場地四周，用 Web App 掃描標有 QR 的物資："
                "【水】與【木材】。"
                "（掃描「木材」時，山林可能會有危險——準備好戰鬥。）"
            )},
        ],
    },
    "iggy_act1_post_bubo": {
        "story_id": "iggy_act1_post_bubo",
        "chapter": "第一章 · Oikos",
        "title": "篝火與失憶",
        "current_stage": 1,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 0,
        "requires_team": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "升起的篝火漸漸散發出熱力，烤醬板鴨的香氣在寒風中瀰漫開來。"
                "經過剛才的一場大戰，你們早已飢腸轆轆，"
                "於是分著吃掉那隻烤熟的醬板鴨，補充消耗的體力。"
            )},
            {"character": "旁白", "text": (
                "在篝火的烘烤下，那名年輕男子緩緩睜開了眼睛。"
            )},
            {"character": "Iggy（重傷）", "text": "……？"},
            {"character": "旁白", "text": (
                "他的雙眼一片空洞與迷惘，重傷讓他連說話都艱難。"
                "他對自己的身份、為什麼會躺在雪堆裡完全沒有概念——"
                "整個人處於嚴重的解離性失憶與本能的恐懼中。"
            )},
            {"character": "旁白", "text": (
                "他體內似乎殘留著某種奇特的力量——"
                "當你們靠近他時，指尖能感受到一股微弱、卻帶著麻痺感與溫度的火星。"
            )},
            {"character": "旁白", "text": (
                "若要釐清他的身份，還需要在周圍搜集屬於他的隨身物品。"
                "請到場地掃描相關 QR——完成後，真相會慢慢浮現。"
            )},
        ],
    },
    "iggy_act1_identity": {
        "story_id": "iggy_act1_identity",
        "chapter": "第一章 · Oikos",
        "title": "名字 · 與逃離",
        "current_stage": 1,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 0,
        "requires_team": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "當你們擦去鐵片上的冰雪與血跡時，看見上面刻著一個名字：Iggy。"
            )},
            {"character": "旁白", "text": "「Iggy……這是你的名字嗎？」你們輕聲問道。"},
            {"character": "Iggy（重傷）", "text": "……我……不知道……"},
            {"character": "旁白", "text": (
                "那名男子呆呆地看著鐵片，眼神只有混亂與迷茫。"
                "他完全不清楚自己是誰，但既然鐵片上記錄著這個名字，"
                "你們便決定暫時稱呼他為「Iggy」。"
            )},
            {"character": "旁白", "text": (
                "就在此刻，遠處突然傳來警報聲與雷達掃描的轟鳴！"
            )},
            {"character": "旁白", "text": (
                "「全體巡邏隊注意！經過連日追查，治安局已鎖定恐怖組織 Oikos 成員"
                "在飛狐雪山的行蹤！發現任何嫌疑人，立刻逮捕或擊斃！」"
            )},
            {"character": "旁白", "text": (
                "Polis 巡邏兵刺耳的金屬靴聲正快速逼近。"
                "時間緊迫——這個被你們暫時稱為 Iggy 的男子重傷失憶、完全無法自保。"
                "你們不再猶豫，一手背起背包，一手架起迷茫重傷的 Iggy，"
                "在漫天風雪中拔腿狂奔，踏上了逃離 Polis 追捕的未知旅程……"
            )},
        ],
    },
    # —— Act 2 ——
    "iggy_stage1": {
        "story_id": "iggy_stage1",
        "chapter": "第二章 · 逃亡",
        "title": "抉擇與邊界",
        "current_stage": 2,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 1,
        "requires_team": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "吃過烤熱的醬板鴨後，原本奄奄一息的男青年總算恢復了少許氣力，"
                "嘴唇不再發紫，原本游離的眼神也稍微聚了焦。"
            )},
            {"character": "Iggy", "text": (
                "謝謝你們……但……我們非親非故的，實在不好意思要你們這樣照顧我……"
            )},
            {"character": "旁白", "text": (
                "話還未說完，一陣劇烈的胸悶與乾嘔猛然襲來！"
                "他痛苦地彎下腰，咳得渾身發抖——一口鮮血吐在潔白的雪地上。"
            )},
            {"character": "Iggy", "text": (
                "我真的……不好意思再麻煩你們了……我連自己是誰都想不起來……"
                "你們還是別管我了……咳……"
            )},
            {"character": "旁白", "text": (
                "即使身受重傷、記憶全失，他內心深處那種"
                "「害怕成為他人負擔、寧願自己吞下痛苦」的防禦機制依然在運作。"
            )},
            {
                "character": "旁白",
                "text": "面對這名吐血重傷、卻依然極力推拒善意的男子——你們必須做出選擇：",
                "choices": [
                    {
                        "text": "分支 A：尊重他的拒絕，準備離開",
                        "next_story_id": "iggy_act2_branch_leave",
                    },
                    {
                        "text": "分支 B：堅持留下，照顧他下山",
                        "next_story_id": "iggy_act2_branch_care",
                    },
                ],
            },
        ],
    },
    "iggy_act2_branch_leave": {
        "story_id": "iggy_act2_branch_leave",
        "chapter": "第二章 · 分支 A",
        "title": "離開——卻被包圍",
        "current_stage": 2,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 1,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "你們尊重他的決定離去，但沒走幾步即被 Polis 追兵包圍！"
            )},
            {"character": "旁白", "text": (
                "軍官冷酷喊道：「發現 Oikos 恐怖份子的目標！還有同黨在一起！"
                "一律視為同謀擊斃！」——完全不聽解釋。"
            )},
            {"character": "旁白", "text": (
                "⚔️ 請到遭遇列表挑戰「Act 2：Polis 追擊」——擊退追兵。"
                "（5 回合內存活即勝，或擊敗敵人。）"
            )},
            {"character": "旁白", "text": (
                "戰鬥後：看著倒地的士兵，你們大口喘氣。"
                "「可惡……完全不聽人講嘢！」"
                "你們看著性命危在旦夕的 Iggy——"
                "反正自己向來欣賞 Oikos「建立無痛世界」的理想；"
                "現在打了 Polis 士兵，已經洗濕咗個頭。"
                "不如帶他下山，嘗試聯絡 Oikos……甚至正式加入！"
            )},
        ],
    },
    "iggy_act2_branch_care": {
        "story_id": "iggy_act2_branch_care",
        "chapter": "第二章 · 分支 B",
        "title": "照顧——潛行下山",
        "current_stage": 2,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 1,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "「少廢話！看著一個人吐血死在面前卻袖手旁觀，我們做不到！」"
                "你們堅持留下。Iggy 在堅持下體力不支暈倒。"
            )},
            {"character": "旁白", "text": (
                "準備帶他下山時，你們發現 Polis 搜捕隊正拿着懸賞緝捕令，"
                "追捕這名 Oikos 成員——他就是你們一直憧憬的 Oikos 核心之一！"
            )},
            {"character": "旁白", "text": (
                "🧩 請完成探索任務「潛行下山」——避開 Polis 哨塔與雷達封鎖線，"
                "帶 Iggy 偷渡下山。"
            )},
        ],
    },
    # —— Act 3 ——
    "iggy_stage2": {
        "story_id": "iggy_stage2",
        "chapter": "第三章 · 記憶之路",
        "title": "村莊 · Julian · Albert",
        "current_stage": 3,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 2,
        "requires_team": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "順利擺脫追兵後，你們背著虛弱的 Iggy，"
                "來到飛狐雪山腳下的一座寧靜村莊。"
            )},
            {"character": "旁白", "text": (
                "為了尋找 Oikos 的線索，你們在村子裡到處打探——"
                "希望能把 Iggy 交還 Oikos，甚至加入這個渴望建立無痛世界的組織。"
            )},
            {"character": "旁白", "text": (
                "🧩 請完成「村莊情報」任務。成功後，一位婦人認出了 Iggy——"
                "他是 Oikos 內部要員，並好心收留你們。"
            )},
            {"character": "旁白", "text": (
                "平靜沒有維持多久。Polis 士兵闖入村莊搜查。"
                "你們轉身時發現——床榻空無一人，Iggy 又偷偷離開了！"
            )},
            {"character": "旁白", "text": (
                "🧩 請完成「搜尋 Iggy」任務。找到他後，Polis 強光掃來——"
                "⚔️ 進入村莊包圍戰。"
            )},
            {"character": "Julian", "text": (
                "別害怕，你們安全了。我叫 Julian……也是 Oikos 的成員。"
            )},
            {"character": "Julian", "text": (
                "Iggy 失去記憶，Zoo 力量也沉寂了。"
                "若要醫治他，必須找到最神秘的「神醫」——Albert 師兄。"
                "只有 Savio 比較清楚他在哪……不過附近紅牆上有定位的提示。"
            )},
            {"character": "旁白", "text": (
                "🎮 請依序完成 City Hunt：尋找 Albert Ching 1→5，"
                "最後前往彩虹站集合。"
            )},
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
            {"character": "旁白", "text": (
                "Julian 承受不了「承擔真實痛苦與責任」的重量，能力暴走。"
                "Oikos 成員集體失控——溫室崩裂成災難。"
            )},
            {"character": "Iggy", "text": "這次……我不逃了。我們一起，把有毒的共生燒斷。"},
            {"character": "Savio", "text": (
                "何必如此痛苦？回到我身邊。無痛的烏托邦才是愛。——脆弱，才是罪。"
            )},
            {"character": "Iggy", "text": (
                "愛有時需要衝突，需要必要的痛。"
                "我不再相信「絕對不造成任何痛楚」的神話。"
            )},
            {"character": "旁白", "text": "最後的領域在前方。擊敗 Savio，摧毀有毒體制。"},
        ],
    },
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
            {"character": "Marah", "text": (
                "我是 Marah。有人叫我控制狂——我叫它「必要的痛」。"
                "這次營會主線在 Iggy；若你仍選擇我，請以韌性面對界線。"
            )},
            {"character": "旁白", "text": "（主線以 Iggy Arc 為準；Marah 內容保留作對照與未來擴充。）"},
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
        "lines": [{"character": "Marah", "text": "暴政之毒與恩典解藥只有一線之隔——你站在哪邊？"}],
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
        "lines": [{"character": "Marah", "text": "強迫成長不是愛。但放任巨嬰也不是。"}],
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
        "lines": [{"character": "Marah", "text": "當痛楚成為尊重而非武器時，獅蠍才真正屬於你。"}],
    },
}

CONDITIONAL_NARRATIVE_FRAGMENTS = {
    "weakness_grace": {
        "fragment_id": "weakness_grace",
        "summary": "界線仍清晰。記得：能力是在人的軟弱上顯得完全（林後 12:9）。",
        "lines": [{"character": "旁白", "text": "你們仍走在光中。軟弱不是羞恥，而是讓恩典有空間停留的地方。"}],
    },
    "trauma_caution": {
        "fragment_id": "trauma_caution",
        "summary": "主角身上留有創傷——請彼此守望，在軟弱中同行。",
        "lines": [{"character": "旁白", "text": "裂縫正在加深。此刻需要的不是獨自硬撐，而是誠實與禱告。"}],
    },
    "trauma_critical": {
        "fragment_id": "trauma_critical",
        "summary": "創傷已逼近臨界——再受重創可能無法迎來真正的救贖結局。",
        "lines": [{"character": "旁白", "text": "陰影在主角心裡扎根。全隊需要放慢腳步，為彼此守住界線。"}],
    },
    "bad_ending_locked": {
        "fragment_id": "bad_ending_locked",
        "summary": "心理創傷過深，故事已走向陰影結局。",
        "lines": [{"character": "旁白", "text": "你們贏過不少戰役，卻輸給了未處理的傷。盼望仍在基督裡，但此行的結局已偏離。"}],
    },
}
