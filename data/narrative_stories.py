"""Narrative story content — Act 0–3 (Iggy / Oikos mainline)."""

NARRATIVE_PORTRAITS = {
    "Iggy": "/static/portraits/iggy.jpg",
    "Iggy（重傷）": "/static/portraits/act1_injured_iggy.jpg",
    "Marah": "/static/portraits/marah.png",
    "Julian": "/static/portraits/julian.png",
    "Savio": "/static/portraits/savio.png",
    "Donna": "/static/portraits/donna.png",
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
                "請打開探索中的「雪山物資與身分」，"
                "到場地四周掃描實體道具 QR：先找【水】與【木材】。"
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
        "unlock_only": True,
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
                "若要釐清他的身份，還需要搜集他的隨身物品——"
                "回到「雪山物資與身分」任務，掃描【山羊徽章】與【鐵片】。"
                "兩樣都掃完後，真相會慢慢浮現。"
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
        "unlock_only": True,
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
                "封鎖線上干擾密布——請完成 Act 1 Mission 2（全隊打地鼠），"
                "帶著他衝出雪山封鎖，踏上逃離 Polis 追捕的未知旅程……"
            )},
        ],
    },
    # —— Act 2 ——
    "iggy_stage1": {
        "story_id": "iggy_stage1",
        "chapter": "第二章 · Avoidant",
        "title": "吐血的推拒",
        "current_stage": 2,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 1,
        "requires_team": True,
        # Only after Act1 escape task (see TASK_STORY_UNLOCKS) — not by task-count alone.
        "unlock_only": True,
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
        "unlock_only": True,
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
                "⚔️ 請到探索完成「Polis 追兵」準備，並在遭遇列表挑戰"
                "「Act 2：Polis 追擊」——擊退追兵。"
                "（5 回合內存活即勝，或擊敗敵人。）"
            )},
            {"character": "旁白", "text": (
                "戰鬥勝利後，將繼續解鎖下山與村莊的劇情——"
                "現在，先守住這一仗。"
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
        "unlock_only": True,
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
                "帶 Iggy 偷渡下山。成功後將抵達山下村莊。"
            )},
        ],
    },
    "iggy_act2_post_polis": {
        "story_id": "iggy_act2_post_polis",
        "chapter": "第二章 · 分支 A",
        "title": "洗濕個頭",
        "current_stage": 2,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 1,
        "unlock_only": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "看著倒地的士兵，你們大口喘氣。"
                "「可惡……完全不聽人講嘢！」"
            )},
            {"character": "旁白", "text": (
                "你們看著性命危在旦夕的 Iggy——"
                "反正自己向來欣賞 Oikos「建立無痛世界」的理想；"
                "現在打了 Polis 士兵，已經洗濕咗個頭，沒有回頭路了。"
            )},
            {"character": "旁白", "text": (
                "不如帶他下山，嘗試聯絡 Oikos 其他成員——"
                "甚至可能被記上一功，正式加入 Oikos！"
            )},
        ],
    },
    # —— Act 3：村莊（分段，唔一次過劇透）——
    "iggy_stage2": {
        "story_id": "iggy_stage2",
        "chapter": "第三章 · Village",
        "title": "山下的村莊",
        "current_stage": 3,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 2,
        "requires_team": True,
        "unlock_only": True,  # after Act2 branch task complete
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "順利擺脫了 Polis 的追兵後，你們背著依然虛弱的 Iggy，"
                "來到了飛狐雪山腳下的一座寧靜村莊。"
            )},
            {"character": "旁白", "text": (
                "為了尋找 Oikos 的線索，你們在村子裡到處打探——"
                "希望找到能將 Iggy 交還給 Oikos 的方法，"
                "甚至希望有機會加入這個夢寐以求、渴望建立無痛世界的組織。"
            )},
            {"character": "旁白", "text": (
                "🧩 請完成 Act 3 Mission 1。"
            )},
        ],
    },
    "iggy_act3_shelter": {
        "story_id": "iggy_act3_shelter",
        "chapter": "第三章 · Village",
        "title": "庇護與逃脫",
        "current_stage": 3,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 2,
        "unlock_only": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "經過一番努力，你們終於找到一位了解 Oikos 的婦人。"
                "婦人看見你們懷中昏迷的男子，以及他隨身的羊頭徽章與鐵片名牌，驚呼出聲——"
                "她認出這名受傷男子就是 Iggy，而且是 Oikos 內部的要員！"
            )},
            {"character": "旁白", "text": (
                "婦人好心地收留了你們。在溫暖的木屋裡住了幾天，"
                "Iggy 身體逐漸復元，臉上恢復血色——"
                "只是記憶依然空白，眼神總帶著不安與迷惘。"
            )},
            {"character": "旁白", "text": (
                "然而平靜沒有維持多久。"
                "這天清晨，村莊外傳來雜亂刺耳的金屬靴聲，伴隨 Polis 士兵粗暴的喧嘩！"
            )},
            {"character": "旁白", "text": (
                "「全村人聽著！治安局收到消息，有 Oikos 可疑人物來到此村莊！"
                "任何人敢包庇恐怖份子，一律同罪！」"
            )},
            {"character": "旁白", "text": (
                "你們正商討對策，打算偷偷帶走 Iggy……"
                "轉過頭時卻震驚地發現——床榻空無一人，Iggy 已經偷偷離開了木屋！"
            )},
            {"character": "旁白", "text": (
                "「這個傻瓜……他又想一個人跑掉，以為這樣就不會連累大家嗎？！」"
                "🧩 請完成 Act 3 Mission 2。"
            )},
        ],
    },
    "iggy_act3_found_iggy": {
        "story_id": "iggy_act3_found_iggy",
        "chapter": "第三章 · Village",
        "title": "後山包圍",
        "current_stage": 3,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 2,
        "unlock_only": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "憑藉團隊配合，你們終於在村莊後山找到了 Iggy。"
                "然而還未鬆一口氣，幾束強光手電筒瞬間掃向你們！"
            )},
            {"character": "旁白", "text": "「在這裡！發現可疑目標！」"},
            {"character": "旁白", "text": (
                "⚔️ Polis 士兵圍攻過來——請完成 Act 3 Mission 3，並進入遭遇列表戰鬥。"
            )},
        ],
    },
    "iggy_act3_julian": {
        "story_id": "iggy_act3_julian",
        "chapter": "第三章 · Village",
        "title": "Julian 登場",
        "current_stage": 3,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 2,
        "unlock_only": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "順利擺脫 Polis 的追兵後，你們曾背著依然虛弱的 Iggy，"
                "來到飛狐雪山腳下的村莊庇護所。"
            )},
            {"character": "旁白", "text": (
                "然而 Iggy 那種「害怕成為負擔、習慣獨自逃避」的性格再次發作——"
                "深夜他偷偷溜走。當你們在後山找到他並被 Polis 包圍時……"
            )},
            {"character": "旁白", "text": (
                "戰鬥中追兵火力強大，你們逐漸陷入絕望。就在千鈞一髮之際——"
            )},
            {"character": "旁白", "text": "「血田·刺藤！」"},
            {"character": "旁白", "text": (
                "數根暗紅色的藤蔓突然爆裂而出，瞬間將 Polis 士兵重重抽飛！"
                "一道披著灰色斗篷的身影躍下——Oikos 的 Julian 師兄發動藤蔓，救走了大家！"
            )},
            {"character": "Julian", "text": (
                "別害怕，你們安全了。我叫 Julian……也是 Oikos 的成員。"
            )},
            {"character": "旁白", "text": (
                "甩開追兵後，Julian 沉重地表示："
                "Iggy 體內的 Zoo 力量完全沉寂，必須尋找神醫 Albert 師兄。"
            )},
            {"character": "Julian", "text": (
                "Albert 師兄為躲避搜捕，行蹤極神秘。"
                "整個 Oikos 裡，只有 Savio 比較清楚他在哪……"
            )},
            {"character": "Julian", "text": (
                "不過據我所知，在這條村莊附近有一塊紅色的牆，"
                "牆上面有著這個村莊附近的風景和建築。"
                "Albert 師兄說過，如果你將來有事找他，可以在那道牆施展定位……"
            )},
            {"character": "旁白", "text": (
                "🎮 請完成 Act 4 Mission 1（GPS 定位）。"
                "之後會一步步解鎖下一任務——故事會在每一步完整播放。"
            )},
        ],
    },
    "iggy_act4_redwall": {
        "story_id": "iggy_act4_redwall",
        "chapter": "第四章 · Memory",
        "title": "紅牆定位",
        "current_stage": 3,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 2,
        "unlock_only": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "在 Julian 的指引下，你們帶著 Iggy 來到了那道印著風景與建築的紅色外牆前。"
            )},
            {"character": "旁白", "text": (
                "當定位術成功施展的那一刻，App 浮現下一道線索——"
                "一幅社區邊界的輪廓，以及一串尚未說出口的語音密碼。"
            )},
            {"character": "旁白", "text": (
                "🎮 請依序完成 Act 4 Mission 2 與 Mission 3。"
                "通過後，那位一直在等你們的人會現身。"
            )},
        ],
    },
    "iggy_act4_map_clear": {
        "story_id": "iggy_act4_map_clear",
        "chapter": "第四章 · Memory",
        "title": "輪廓與結界",
        "current_stage": 3,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 2,
        "unlock_only": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "你們看穿了地圖輪廓背後的地點，並依照指示前往解結界。"
            )},
            {"character": "旁白", "text": (
                "語音密碼在空氣中串起——下一扇門即將打開。"
                "請完成 Act 4 Mission 3（若尚未完成）。"
            )},
        ],
    },
    "iggy_act4_albert_test": {
        "story_id": "iggy_act4_albert_test",
        "chapter": "第四章 · Memory",
        "title": "Albert 師兄",
        "current_stage": 3,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 2,
        "unlock_only": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "月台角落裡，Albert 師兄收起剛剛測試你們實力的短刃，"
                "眼神溫和卻無比透徹。"
            )},
            {"character": "旁白", "text": (
                "他打量著躲在你們身後、不敢正視大家的 Iggy，深深地嘆了一口氣。"
            )},
            {"character": "Albert", "text": (
                "大腦啟動了自我保護機制……過往那些不能承受的傷口，"
                "被他自己親手埋藏了。"
            )},
            {"character": "Albert", "text": (
                "要重新握緊體內那股火，你們必須帶他走一遍來時的路，"
                "讓他親眼看一看，自己究竟在逃避甚麼。"
            )},
            {"character": "旁白", "text": (
                "🎮 請完成 Act 4 Mission 4——"
                "到指定壁畫前，開始重組第一道記憶。"
            )},
        ],
    },
    "iggy_act4_meifoo": {
        "story_id": "iggy_act4_meifoo",
        "chapter": "第四章 · Memory",
        "title": "第一道記憶碎片",
        "current_stage": 3,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 2,
        "unlock_only": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "按照 Albert 師兄的指引，你們與 Iggy 來到轉車隧道的舊街壁畫前。"
                "舊式街景在昏暗燈光下顯得斑駁而沉寂。"
            )},
            {"character": "旁白", "text": (
                "Iggy 呆立在壁畫前，目光死死凝視畫中角落那座舊式唐樓的樓梯口。"
                "突然，他的呼吸變得無比急促，瞳孔劇烈收縮——"
                "整個人像被抽乾了空氣般，雙腿一軟，重重跪倒在地板上！"
            )},
            {"character": "旁白", "text": "「Iggy！」你們連忙扶住他。"},
            {"character": "旁白", "text": (
                "Iggy 雙手死死扣著腦袋，手指深深嵌進頭髮裡，"
                "整個人發抖得像寒風中的落葉。"
                "在他的視覺中，隧道的喧囂瞬間遠去，冰冷的雨聲在腦海中轟鳴——"
            )},
            {"character": "旁白", "text": (
                "那一夜的舊街，下著暴雨。一對男女冷酷地鬆開了他的小手，"
                "轉身走入雨幕中。任憑年幼的他如何在身後哭喊、追趕，"
                "那兩道背影再也沒有回過頭。"
            )},
            {"character": "Iggy", "text": (
                "是我不夠好……一定是那天我不夠聽話……我太笨了……他們才不要我的……"
            )},
            {"character": "Iggy", "text": (
                "如果不變得更加有用，如果不乖乖聽話……大家……"
                "大家最後都會像他們一樣，把我一個人扔在雨裡……"
                "我好害怕……我不想再一個人了……"
            )},
            {"character": "旁白", "text": (
                "你們蹲下身，沒有講任何大道理，只是緊緊握住他那雙凍得發冰的手，"
                "平靜地看著他的眼睛，輕輕搖頭："
            )},
            {"character": "旁白", "text": (
                "「那不是你的錯。當年轉身走掉的是他們，該感到羞愧的也是他們。"
                "你不需要為了讓別人留下來，而把自己折磨得面目全非。」"
            )},
            {"character": "旁白", "text": (
                "Iggy 身軀劇烈一震。掌心裡那股冰冷的死寂，"
                "隱隱約約泛起一絲微弱的溫熱。"
            )},
            {"character": "旁白", "text": "【第一道記憶碎片，重組完成】"},
            {"character": "旁白", "text": (
                "原來 Iggy 小時候被父母拋棄——那是誰湊大他呢？他隱隱約約說了聲「通渠佬」……請完成 Act 4 Mission 2。"
            )},
        ],
    },
    "iggy_act4_plumber": {
        "story_id": "iggy_act4_plumber",
        "chapter": "第四章 · Memory",
        "title": "第二道記憶碎片",
        "current_stage": 3,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 2,
        "unlock_only": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "按照 App 解鎖的提示，你們帶著 Iggy 來到舊區巷弄深處，"
                "找到了當年收留過他的恩人——老通渠佬。"
            )},
            {"character": "旁白", "text": (
                "看到長大後的 Iggy，老通渠佬抹了抹手上的油污，"
                "眼神裡滿是複雜與疼惜。他拉過兩張舊木凳，抽了一口煙，緩緩吐出煙霧："
            )},
            {"character": "通渠佬", "text": (
                "這孩子……從小就是這樣。當年我家裡天天吵架，破碗破碟飛滿地。"
                "這孩子明明嚇得躲在桌子下發抖，但只要一停下來，"
                "他就搶著把所有的地掃乾淨、把所有的責罵和懲罰都往自己身上攬……"
            )},
            {"character": "通渠佬", "text": (
                "他以為，只要自己受足了苦，只要自己扮演一個最完美的乖孩子，"
                "這個家就不會散。他太害怕被拋棄了，害怕到……"
                "寧願把自己的尊嚴和需要，踩在腳底下一遍又一遍地踐踏。"
            )},
            {"character": "旁白", "text": (
                "通渠佬的話如同一把鈍刀，深深刺進 Iggy 內心最隱密的地方。"
                "他僵硬地坐在木凳上，雙手緊緊交握，指關節因為用力過度而泛白。"
            )},
            {"character": "Iggy", "text": (
                "很可笑對吧……？我明明那麼害怕被孤立，害怕被大家遺棄……"
                "但我卻每天都在做著同一件事——"
                "我永遠第一個把自己的感覺拋棄掉。"
            )},
            {"character": "Iggy", "text": (
                "我不配去過快樂的生活……只要大家開心，"
                "只要大家不需要承受痛苦……即使我被碾碎了，"
                "即使大家根本不理解我、不感激我……至少……"
                "至少那證明了我還有一點點被留下來的價值，不是嗎……？"
            )},
            {"character": "旁白", "text": (
                "這就是 Iggy 最深層的矛盾與病態："
                "他極度渴望愛，卻自卑地認為真實的自己不值得被愛；"
                "唯有透過「主動代人受苦與犧牲」，才能換取自己在世界上的微薄存在感。"
            )},
            {"character": "旁白", "text": (
                "你們扶住他發抖的肩膀，眼神堅定："
                "「一個只能靠你不斷委屈自己、不斷流血才能維持的關係，"
                "從來就不是真正的家。你的價值，不需要靠你全身是傷來證明。」"
            )},
            {"character": "旁白", "text": (
                "Iggy 眼角的淚水終於潰堤。心中那道築了多年的自我防禦高牆，"
                "轟然塌陷了一角。"
            )},
            {"character": "旁白", "text": "【第二道記憶碎片，重組完成】"},
            {"character": "旁白", "text": (
                "通渠佬說 Iggy 常把「天行健，君子以自強不息」掛在口邊——"
                "哪個車站與這句有關？請完成 Act 4 Mission 3（GPS 定位）。"
            )},
        ],
    },
    "iggy_act4_phoenix": {
        "story_id": "iggy_act4_phoenix",
        "chapter": "第四章 · Memory",
        "title": "再生火焰",
        "current_stage": 3,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 2,
        "unlock_only": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "最後，你們與 Iggy 抵達象徵天地運轉、天行健自強不息的「八乘八」藝術展品前。"
                "Albert 師兄早已等候在此。"
            )},
            {"character": "Albert", "text": (
                "Savio 老師用他的力量替大家遮風擋雨，"
                "讓所有人活在不需要面對現實的溫室裡。但你不同，Iggy。"
            )},
            {"character": "Albert", "text": (
                "你當年坐在這裡，看著易經的變化，自己參透了這個世界的客觀法則——"
                "天地萬物，有陰就有陽，有晝就有夜。"
                "沒有經過寒冬摩擦的種子，永遠開不出花來。"
            )},
            {"character": "旁白", "text": (
                "Albert 師兄突然拔出短刃，眼神一厲，再次向你們與 Iggy 發動攻擊——"
                "第二次測試戰！"
            )},
            {"character": "旁白", "text": (
                "金屬交鳴聲迴響！Albert 的每一招都直逼 Iggy 的面門，大聲呵斥："
            )},
            {"character": "Albert", "text": (
                "看清楚眼前的現實！同伴正在為你流血！"
                "你還要繼續躲在『討好別人』和『自我憐憫』的廢墟裡嗎？！"
                "誠實地面對你的軟弱！承認你也會累、你也會痛！然後，站起來！"
            )},
            {"character": "旁白", "text": (
                "Iggy 看著擋在他身前、傷痕累累卻依然對他笑著的你們，"
                "又看了看自己那雙只會推開別人的雙手。"
                "那一瞬間，他不再逃避，不再假裝堅強，也不再試圖討好任何人。"
            )},
            {"character": "Iggy", "text": (
                "我……我真的很痛……我真的快要撐不下去了啊啊啊——！"
            )},
            {"character": "旁白", "text": (
                "那是他這輩子第一次，赤裸裸地在所有人面前"
                "宣洩出壓抑了十幾年的痛苦與軟弱！"
            )},
            {"character": "旁白", "text": (
                "轟——！極致耀眼的純白光芒從 Iggy 體內轟然爆發！"
                "他誠實地接納了自己的傷口與軟弱。"
                "不再是為了討好別人而燃燒，而是為了守護同伴與真實的自己而戰！"
            )},
            {"character": "旁白", "text": (
                "那一股沉寂已久、帶著溫暖與強大生命力的「再生火焰 (Phoenix Fire)」，"
                "如璀璨的金色羽翼般在他背後騰空而起！"
            )},
            {"character": "旁白", "text": (
                "戰鬥瞬間平息。Albert 師兄收招立定，"
                "看著身上沐浴著金白色火焰、雙眼重獲神采的 Iggy，露出了欣慰的微笑。"
            )},
            {"character": "旁白", "text": (
                "【系統廣播】恭喜！記憶任務完成！Iggy 已重執再生火焰！"
                "【最終目標】請全體小隊立刻前往集合點，與 Julian 會合！"
            )},
            {"character": "Iggy", "text": (
                "走吧……這一次，我不會再跑了。"
            )},
            {"character": "旁白", "text": (
                "🎮 請完成 Act 5 Mission 1（集合 GPS）。"
            )},
        ],
    },
    "iggy_act5_betrayal": {
        "story_id": "iggy_act5_betrayal",
        "chapter": "第五章 · Pain Alone",
        "title": "彩虹月台 · 面具撕下",
        "current_stage": 4,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 3,
        "unlock_only": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "彩虹站月台上，披著灰色斗篷的 Julian 站在中央。"
                "他拍了拍 Iggy 的肩膀：「怎麼樣……你的記憶還有 Zoo 能力，是不是已經全部恢復了？」"
            )},
            {"character": "Iggy", "text": (
                "我想起了一點……但尚未完全恢復。"
                "特別是雪山那一戰……腦海裡還是一片混亂。"
            )},
            {"character": "Julian", "text": "那看來……我不需要再演下去了。"},
            {"character": "旁白", "text": (
                "話音未落，短刃直刺 Iggy 心口！"
                "Julian 雙眼布滿血絲——那是 Simon 的能力：「蜜獾·狂化重擊」！"
            )},
            {"character": "Julian", "text": (
                "我的 Zoo 是「變色龍」——可以借用他人甘願交出的力量。"
                "我一路扮演好人，只因失憶的你無法交出完整的鳳凰之力。"
                "現在……甘願交出，還是一起死在這裡？"
            )},
            {"character": "旁白", "text": (
                "⚔️ 請完成 Act 5 Mission 2，並挑戰遭遇列表中的 Julian 戰。"
                "（此戰將揭開真相——堅持到最後。）"
            )},
        ],
    },
    "iggy_act6_approach": {
        "story_id": "iggy_act6_approach",
        "chapter": "第六章 · Necessary Pain",
        "title": "黑色臍帶",
        "current_stage": 4,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 3,
        "unlock_only": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "擊敗 Julian 後，煙塵散去——天空染上不祥的紫黑色，"
                "無數黑色氣息如血管在雲層中蠕動。"
            )},
            {"character": "旁白", "text": (
                "「這是 Oikos 成員的集體暴走！"
                "Savio 當年用 Goat 能力代大家承受覺醒之痛，"
                "那些被剝奪的後果全數沉積在他體內——"
                "Julian 敗亡引發連鎖，負能量正反噬 Savio！」"
            )},
            {"character": "旁白", "text": (
                "唯有前往 Oikos 總部——西貢戶外康樂中心（SKORC），"
                "擊敗暴走的 Savio，用涅槃金焰燒斷病態臍帶。"
            )},
            {"character": "Iggy", "text": (
                "雖然這是我這輩子做過最痛苦的決定……但這一次，我絕不逃避！"
                "Savio 老師，讓我來為你切斷這有毒的鎖鏈！"
            )},
            {"character": "旁白", "text": (
                "🎮 請完成 Act 6 Mission 1 與 Mission 2，挑戰最終遭遇戰。"
            )},
        ],
    },
    "iggy_ending_victory": {
        "story_id": "iggy_ending_victory",
        "chapter": "結局 · Victory",
        "title": "健康的界線",
        "current_stage": 4,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 3,
        "unlock_only": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "痛楚與現實的摩擦力重回每個人身上。"
                "信徒們雖然因直面現實而呻吟，但雙眼重獲自由意志的光芒。"
            )},
            {"character": "Savio", "text": (
                "我……我終於不用再替所有人承擔了嗎……"
            )},
            {"character": "Iggy", "text": (
                "是的。你累了，該卸下這個虛假的救世主重擔了。"
                "各人擔當自己的擔子。"
            )},
            {"character": "旁白", "text": (
                "Cosmos 世界重獲健康的界線法則。"
                "——完——"
            )},
        ],
    },
    "iggy_stage3": {
        "story_id": "iggy_stage3",
        "chapter": "ACT 5–6",
        "title": "業火與重塑",
        "current_stage": 4,
        "total_stages": 6,
        "route": "iggy",
        "min_stage": 3,
        "unlock_only": True,
        "skippable": True,
        "replayable": True,
        "lines": [
            {"character": "旁白", "text": (
                "主線已進入終局。若你尚未完成彩虹站與西貢任務，"
                "請依探索列表逐步推進——故事會在關鍵節點自動出現。"
            )},
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
