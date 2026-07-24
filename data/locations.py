"""GPS / task location definitions — Iggy Arc (設定1) + camp minigames."""

# Shared camp-area coords for non-GPS / pending-GPS tasks.
_CAMP = {"lat": 22.3845, "lng": 114.2695, "radius": 80}

# Placeholder HK coords for City Hunt (replace with precise pins when locked).
_TSUEN_WAN = {"lat": 22.3736, "lng": 114.1178, "radius": 120}  # 荃灣站外牆一帶
_KWAI_FONG = {"lat": 22.3570, "lng": 114.1278, "radius": 120}
_MEI_FOO = {"lat": 22.3370, "lng": 114.1390, "radius": 120}
_KOWLOON_TONG = {"lat": 22.3370, "lng": 114.1760, "radius": 100}
_CHOI_HUNG = {"lat": 22.3347, "lng": 114.2090, "radius": 100}

LOCATIONS = {
    # ========== ACT 1 ==========
    "act1_supplies": {
        "name": "Act 1 Mission 1",
        "hint": "掃描現場 QR",
        **_CAMP,
        "task_type": "qr",
        "story_act": 1,
        "mainline": True,
        "mainline_order": 10,
        "qr_checklist": True,
        "description": (
            "【Act 1 Mission 1】在場地掃描四樣實體道具 QR。\n"
            "先掃水與木材（木材可能觸發教學戰）；之後再掃其餘兩樣。"
            "四樣齊全即完成本任務。"
        ),
    },
    "act1_escape": {
        "name": "Act 1 Mission 2",
        "hint": "全隊 · 打地鼠",
        **_CAMP,
        "task_type": "minigame",
        "minigame_id": "whack_a_mole",
        "minigame_config": {
            "timeLimitSec": 60,
            "targetHits": 45,
            "minWinners": 2,
        },
        "story_act": 1,
        "mainline": True,
        "mainline_order": 20,
        "description": (
            "【Act 1 Mission 2】封鎖線上的干擾信號如地鼠般冒出——"
            "全隊一起打地鼠：60 秒內打中 45 隻。"
            "至少 2 人通關即可完成任務（失敗可重試）。"
        ),
    },
    # ========== ACT 2 ==========
    "act2_stealth": {
        "name": "Act 2 Mission 1",
        "hint": "全隊 · 記憶閃光",
        **_CAMP,
        "task_type": "minigame",
        "minigame_id": "flash_memory",
        "minigame_config": {
            "totalRounds": 5,
            "minCorrect": 2,
            "minShowSeconds": 0.5,
        },
        "story_act": 2,
        "mainline": True,
        "mainline_order": 30,
        "description": (
            "【Act 2 Mission 1 · 分支】全隊同時進行記憶閃光："
            "螢幕短暫顯示字串（每輪至少 0.5 秒），記住後輸入。"
            "共 5 輪，每輪至少 2 人答對。"
        ),
    },
    "act2_polis_fight": {
        "name": "Act 2 Mission 2",
        "hint": "分支 · 遭遇戰",
        **_CAMP,
        "task_type": "photo",
        "story_act": 2,
        "mainline": True,
        "mainline_order": 30,
        "description": (
            "【Act 2 Mission 2 · 分支】影合照後，"
            "到遭遇列表挑戰 Act 2 追擊戰（撐過回合或擊退）。"
        ),
    },
    # ========== ACT 3 ==========
    "act3_village_intel": {
        "name": "Act 3 Mission 1",
        "hint": "全隊 · 解碼",
        **_CAMP,
        "task_type": "minigame",
        "minigame_id": "mastermind",
        "minigame_config": {
            "codeLength": 4,
            "maxGuesses": 10,
            "themeTitle": "Act 3 Mission 1 · 解碼",
            "themeHint": (
                "全隊一起進入。綠釘＝位置正確；白釘＝顏色對但位置錯；"
                "紅釘＝錯誤。每人最多 10 次，全隊都破解才算完成。"
            ),
        },
        "story_act": 3,
        "mainline": True,
        "mainline_order": 40,
        "description": (
            "【Act 3 Mission 1】全隊以 Mastermind 破解線索密碼（綠／白／紅釘）。"
            "每人 10 次內都要破解。"
        ),
    },
    "act3_search_iggy": {
        "name": "Act 3 Mission 2",
        "hint": "全隊 · 三輪記憶配對",
        **_CAMP,
        "task_type": "minigame",
        "minigame_id": "memory_match",
        "minigame_config": {
            "pairs": 8,
            "previewSec": 2,
            "waveTimesSec": [60, 50, 45],
        },
        "story_act": 3,
        "mainline": True,
        "mainline_order": 50,
        "description": (
            "【Act 3 Mission 2】記憶配對三輪：60 → 50 → 45 秒。"
            "每輪開始有 2 秒預覽。半隊完成三輪即過關。"
        ),
    },
    "act3_village_battle": {
        "name": "Act 3 Mission 3",
        "hint": "遭遇戰",
        **_CAMP,
        "task_type": "photo",
        "story_act": 3,
        "mainline": True,
        "mainline_order": 60,
        "description": (
            "【Act 3 Mission 3】後山危機——影合照後挑戰遭遇列表中的追擊戰。"
        ),
    },
    # —— Act 4：記憶主線（3 個任務）——
    "albert_ching_1": {
        "name": "Act 4 Mission 1",
        "hint": "美孚壁畫 · 答題（全組一次機會）",
        **_MEI_FOO,
        "task_type": "quiz",
        "story_act": 4,
        "mainline": True,
        "mainline_order": 70,
        "answer": "6",
        "answer_aliases": ["6", "六", "六枝", "6枝", "6 枝"],
        "one_team_attempt": True,
        "stat_points_reward": 5,
        "description": (
            "【Act 4 Mission 1】童年對 Iggy 是不能磨滅的創傷——"
            "或許帶他到童年生活的地方，有助找回記憶、面對過去。\n\n"
            "提示：美孚相片（見提示圖）\n"
            "問題：在畫中，蛋糕上共有多少蠟燭？\n"
            "⚠ 全組只有 1 次作答機會，請勿亂估。"
        ),
        "hint_media": "/static/mission_hints/albert_ching_4_meifoo_hint.jpg",
        "reward_hint": "原來 Iggy 小時候被父母拋棄——那是誰湊大他呢？他隱隱約約說了聲「通渠佬」……",
    },
    "albert_ching_2": {
        "name": "Act 4 Mission 2",
        "hint": "通渠佬電話 · 答題（全組一次機會）",
        **_CAMP,
        "task_type": "quiz",
        "story_act": 4,
        "mainline": True,
        "mainline_order": 80,
        "answer": "6562275",
        "answer_normalize": "digits",
        "one_team_attempt": True,
        "stat_points_reward": 5,
        "description": (
            "【Act 4 Mission 2】Iggy 說出了通渠佬——"
            "或許找到他會有助恢復記憶。要怎樣聯絡？難道在車站附近可以找到電話嗎？\n\n"
            "任務：找出通渠佬的電話號碼。\n"
            "⚠ 全組只有 1 次作答機會。"
        ),
        "reward_hint": (
            "原來 Iggy 一直是這樣長大……通渠佬說 Iggy 常把"
            "「天行健，君子以自強不息」掛在口邊——哪個車站與這句有關？"
        ),
    },
    "albert_ching_3": {
        "name": "Act 4 Mission 3",
        "hint": "自強不息 · GPS",
        **_KOWLOON_TONG,
        "task_type": "gps",
        "story_act": 4,
        "mainline": True,
        "mainline_order": 90,
        "stat_points_reward": 5,
        "description": (
            "【Act 4 Mission 3】找出與「天行健，君子以自強不息」有關的車站，"
            "到達該站並展開定位術（GPS 驗證 + 全組影相）。"
        ),
    },
    # Legacy slots kept non-mainline so old progress data does not break gates
    "albert_ching_4": {
        "name": "Act 4 Legacy 4",
        "hint": "（已停用）",
        **_MEI_FOO,
        "task_type": "photo",
        "story_act": 4,
        "mainline": False,
        "description": "舊任務欄位，已由 Act 4 Mission 1–3 取代。",
    },
    "albert_ching_5": {
        "name": "Act 4 Legacy 5",
        "hint": "（已停用）",
        **_KOWLOON_TONG,
        "task_type": "photo",
        "story_act": 4,
        "mainline": False,
        "description": "舊任務欄位，已由 Act 4 Mission 1–3 取代。",
    },
    # —— Act 3 支線（隨主線開啟）——
    "act3_side_kong_pose": {
        "name": "Act 3 Side 1",
        "hint": "港 Pose 食飯相",
        **_CAMP,
        "task_type": "photo",
        "story_act": 3,
        "mainline": False,
        "side_quest": True,
        "mainline_order": 45,
        "stat_points_reward": 10,
        "description": (
            "【Act 3 支線 1】全組組員均以港 Pose 影食飯相"
            "（可參考提示圖 kong_lui_pose）。"
        ),
        "hint_media": "/static/mission_hints/act3_kong_pose_hint.svg",
    },
    "act3_side_squares": {
        "name": "Act 3 Side 2",
        "hint": "荃灣打卡地標 · 紅圈是甚麼",
        **_TSUEN_WAN,
        "task_type": "quiz",
        "story_act": 3,
        "mainline": False,
        "side_quest": True,
        "mainline_order": 46,
        "answer": "紅van",
        "answer_aliases": [
            "紅van", "紅Van", "紅VAN", "紅 van",
            "紅van", "紅色van", "紅色Van", "紅色VAN",
            "red van", "redvan", "van", "紅Van",
        ],
        "one_team_attempt": True,
        "stat_points_reward": 10,
        "description": (
            "【Act 3 支線 2】提示：荃灣打卡地標。\n"
            "找出被紅圈圈住的是甚麼？\n"
            "⚠ 全組只有 1 次作答機會，請勿亂估。"
        ),
        "hint_media": "/static/mission_hints/act3_tsuenwan_redvan.jpg",
    },
    "act4_side_shirt": {
        "name": "Act 4 Side 1",
        "hint": "彩虹站 · 模仿藝術品影相",
        **_CHOI_HUNG,
        "task_type": "photo",
        "story_act": 4,
        "mainline": False,
        "side_quest": True,
        "mainline_order": 95,
        "stat_points_reward": 10,
        "description": (
            "【Act 4 Mission 3 支線】請到達彩虹站，"
            "請 3 位組員分別模仿提示圖中 3 件藝術品的動作，然後影相提交。"
        ),
        "hint_media": "/static/mission_hints/act4_choihung_statues.jpg",
    },
    "act3_choihung_rally": {
        "name": "Act 5 Mission 1",
        "hint": "GPS 集合",
        **_CHOI_HUNG,
        "task_type": "gps",
        "story_act": 5,
        "mainline": True,
        "mainline_order": 120,
        "description": (
            "【Act 5 Mission 1】全體小隊前往指定車站集合。"
        ),
    },
    # ========== ACT 5–6 ==========
    "act4_julian_gate": {
        "name": "Act 5 Mission 2",
        "hint": "戰前 · 影相",
        **_CHOI_HUNG,
        "task_type": "photo",
        "story_act": 5,
        "mainline": True,
        "mainline_order": 130,
        "description": (
            "【Act 5 Mission 2】全組影一張迎戰合照，"
            "然後挑戰遭遇列表中的 Julian 戰。"
        ),
    },
    "act5_return_camp": {
        "name": "Act 6 Mission 1",
        "hint": "終局集合 · GPS",
        **_CAMP,
        "task_type": "gps",
        "story_act": 6,
        "mainline": True,
        "mainline_order": 140,
        "description": (
            "【Act 6 Mission 1】全隊前往終局集合點。"
        ),
    },
    "act6_savio_gate": {
        "name": "Act 6 Mission 2",
        "hint": "終局戰前 · 影相",
        **_CAMP,
        "task_type": "photo",
        "story_act": 6,
        "mainline": True,
        "mainline_order": 150,
        "description": (
            "【Act 6 Mission 2】全組影合照後，"
            "挑戰最終遭遇戰。"
        ),
    },
    # ========== 營會探索小遊戲（保留） ==========
    "loc_illusion_01": {
        "name": "幻象迴廊",
        "hint": "視覺陷阱 · 小遊戲",
        **_CAMP,
        "task_type": "minigame",
        "minigame_id": "color_illusion_trap",
        "minigame_config": {"passScore": 4},
        "description": "前方出現干擾視覺的屏障，你需要看破表象才能繼續前進。",
    },
    "loc_diff_01": {
        "name": "虛實裂縫",
        "hint": "找不同 · 小遊戲",
        **_CAMP,
        "task_type": "minigame",
        "minigame_id": "spot_the_difference",
        "minigame_config": {"diffCount": 5, "timeLimitSec": 90},
        "description": "空間產生了微小的變異，請找出兩張景象的不同之處。",
    },
    "loc_brain_01": {
        "name": "神智測試儀",
        "hint": "一心二用 · 小遊戲",
        **_CAMP,
        "task_type": "minigame",
        "minigame_id": "bilateral_brain",
        "minigame_config": {"targetStreak": 5, "roundMs": 3500},
        "description": "證明你能保持左右腦的高度專注與分工。",
    },
    "loc_sudoku_01": {
        "name": "秩序方陣",
        "hint": "數獨 · 小遊戲",
        **_CAMP,
        "task_type": "minigame",
        "minigame_id": "sudoku",
        "minigame_config": {"maxHints": 3},
        "description": "找回絕對的數字規律才能解開鎖鏈。",
    },
    "loc_2048_01": {
        "name": "資源聚合站",
        "hint": "2048 · 合併至 256",
        **_CAMP,
        "task_type": "minigame",
        "minigame_id": "g2048",
        "minigame_config": {"winTile": 256},
        "description": "系統能量嚴重分散，請將基礎能量方塊疊加合併至 256 以上。",
    },
    "loc_password_01": {
        "name": "記憶金庫",
        "hint": "密碼 Wordle · 小遊戲",
        **_CAMP,
        "task_type": "minigame",
        "minigame_id": "wordle_custom",
        "minigame_config": {
            "maxGuesses": 6,
            "answers": ["界線", "神智", "韌性", "裂縫", "IGGY", "PHOENIX"],
        },
        "description": "終端機需要輸入特定長度的關鍵詞，只有營會的參與者才知道答案。",
    },
    "loc_map_01": {
        "name": "地理定位儀",
        "hint": "Worldle 式 · 睇輪廓估地方",
        **_CAMP,
        "task_type": "minigame",
        "minigame_id": "mapdle_hk",
        "minigame_config": {"maxGuesses": 6, "winRadiusKm": 0.5},
        "description": (
            "螢幕顯示一個香港地方嘅輪廓（同 Worldle 一樣）。"
            "從名單揀地方去估；每次會顯示距離、方向箭嘴同接近度 %。"
        ),
    },
    "loc_voice_01": {
        "name": "聲線契約",
        "hint": "錄音 · 小遊戲",
        **_CAMP,
        "task_type": "minigame",
        "minigame_id": "voice_record",
        "minigame_config": {
            "prompt": "請允許麥克風權限，然後大聲讀出下面句子並錄音提交。",
            "script": "界線不會自己守住。愛有時需要必要的痛。",
            "minSeconds": 3,
            "maxSeconds": 60,
        },
        "description": (
            "用聲音立約。讀出指定句子並錄音（最少 3 秒），"
            "試聽滿意後提交；錄音會交俾 GM 存檔。"
        ),
    },
}
