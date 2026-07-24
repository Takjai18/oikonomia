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
    "albert_ching_1": {
        "name": "Act 4 Mission 1",
        "hint": "GPS 驗證",
        **_TSUEN_WAN,
        "task_type": "gps",
        "story_act": 4,
        "mainline": True,
        "mainline_order": 70,
        "description": (
            "【Act 4 Mission 1】前往指定外牆位置，開啟 GPS 驗證定位。"
            "成功後解鎖下一任務。"
        ),
    },
    "albert_ching_2": {
        "name": "Act 4 Mission 2",
        "hint": "地圖輪廓",
        **_KWAI_FONG,
        "task_type": "minigame",
        "minigame_id": "mapdle_hk",
        "minigame_config": {
            "maxGuesses": 5,
            "winRadiusKm": 1.0,
            "targetName": "葵芳",
            "targetImage": "/static/mission_hints/albert_ching_2_kwaifong.svg",
        },
        "story_act": 4,
        "mainline": True,
        "mainline_order": 80,
        "description": (
            "【Act 4 Mission 2】App 顯示社區邊界輪廓，猜出正確地點（最多 5 次）。"
            "答對後前往該站做下一任務。"
        ),
        "hint_media": "/static/mission_hints/albert_ching_2_kwaifong.svg",
    },
    "albert_ching_3": {
        "name": "Act 4 Mission 3",
        "hint": "語音密碼",
        **_KWAI_FONG,
        "task_type": "minigame",
        "minigame_id": "voice_record",
        "minigame_config": {
            "prompt": (
                "先睇提示短片，再全隊輪流說出密碼（可每人一字／詞），"
                "限時內連貫完成並錄音提交。"
            ),
            "script": "我叫做 Franchesca，今年係 19 歲半",
            "minSeconds": 3,
            "maxSeconds": 15,
            "hintVideo": "/static/mission_hints/albert_ching_3_password_hint.mp4",
        },
        "story_act": 4,
        "mainline": True,
        "mainline_order": 90,
        "description": (
            "【Act 4 Mission 3】依提示完成語音密碼錄音。"
            "通過後解鎖下一站記憶任務。"
        ),
        "hint_media": "/static/mission_hints/albert_ching_3_password_hint.mp4",
    },
    "albert_ching_4": {
        "name": "Act 4 Mission 4",
        "hint": "壁畫 · 影相",
        **_MEI_FOO,
        "task_type": "photo",
        "story_act": 4,
        "mainline": True,
        "mainline_order": 100,
        "description": (
            "【Act 4 Mission 4】到指定轉車隧道壁畫前，"
            "影下對應細節並提交。完成後會播放完整記憶劇情。"
        ),
        "hint_media": "/static/mission_hints/albert_ching_4_meifoo_hint.jpg",
    },
    "albert_ching_5": {
        "name": "Act 4 Mission 5",
        "hint": "藝術品 · 影相",
        **_KOWLOON_TONG,
        "task_type": "photo",
        "story_act": 4,
        "mainline": True,
        "mainline_order": 110,
        "description": (
            "【Act 4 Mission 5】到指定藝術展品前影相提交。"
            "完成後會播放後續記憶與覺醒劇情。"
        ),
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
