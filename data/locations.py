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
    # ========== ACT 1 — 飛狐雪山（QR 掃描完成） ==========
    "act1_wood": {
        "name": "木材",
        "hint": "搜集 · 掃描 QR → 布布戰",
        **_CAMP,
        "task_type": "qr",
        "story_act": 1,
        "qr_code_value": "act1-wood",
        "start_encounter": "enc_iggy_act1_bubo",
        "description": (
            "【主線 1.1 · 希望你能熬過這個冬天】找出「木材」並掃描 QR。"
            "掃描成功後立刻進入雪山熊「布布」教學戰"
            "（攻擊、防禦、擲骰；可全隊一起行動）。"
            "擊敗後再繼續生火、烤醬板鴨。"
        ),
    },
    "act1_water": {
        "name": "水",
        "hint": "搜集 · 掃描 QR",
        **_CAMP,
        "task_type": "qr",
        "story_act": 1,
        "qr_code_value": "act1-water",
        "description": (
            "【主線 1.1】找出「水」實體道具並掃描 QR。"
            "與木材一齊用於生火取暖、照顧傷者。"
        ),
    },
    "act1_goat_badge": {
        "name": "傷者隨身物 · 徽章",
        "hint": "個人物品 · 掃描 QR",
        **_CAMP,
        "task_type": "qr",
        "story_act": 1,
        "qr_code_value": "act1-goat-badge",
        "description": (
            "【主線 1.2 · 不明來歷】篝火劇情後才解鎖。"
            "找出殘缺山羊徽章並掃描 QR；與鐵片齊全後揭開身分。"
        ),
    },
    "act1_iron_plate": {
        "name": "傷者隨身物 · 鐵片",
        "hint": "個人物品 · 掃描 QR",
        **_CAMP,
        "task_type": "qr",
        "story_act": 1,
        "qr_code_value": "act1-iron-plate",
        "description": (
            "【主線 1.2 · 不明來歷】找出一塊金屬鐵片／名牌，掃描 QR。"
            "（內容在掃描與劇情中揭曉——請勿劇透隊友。）"
        ),
    },
    "act1_escape": {
        "name": "後有追兵",
        "hint": "逃離雪山 · 解難",
        **_CAMP,
        "task_type": "minigame",
        "minigame_id": "bilateral_brain",
        "minigame_config": {"targetStreak": 5, "roundMs": 3200},
        "story_act": 1,
        "description": (
            "【主線 1.3 · 後有追兵】Polis 治安局搜捕隊逼近！"
            "帶著虛弱失憶的 Iggy 逃離雪山——"
            "保持冷靜與專注，闖過封鎖（解難小遊戲）。"
        ),
    },
    # ========== ACT 2 — 逃亡 ==========
    "act2_stealth": {
        "name": "潛行下山",
        "hint": "分支 B · 避開哨塔",
        **_CAMP,
        "task_type": "minigame",
        "minigame_id": "spot_the_difference",
        "minigame_config": {"diffCount": 5, "timeLimitSec": 120},
        "story_act": 2,
        "description": (
            "【主線 2.1 · 分支 B】Stealth：避開 Polis 哨塔與雷達封鎖線，帶 Iggy 下山。"
            "（暫以找不同小遊戲代表潛行。）"
        ),
    },
    "act2_polis_fight": {
        "name": "Polis 追兵",
        "hint": "分支 A · 正式戰鬥",
        **_CAMP,
        "task_type": "photo",
        "story_act": 2,
        "description": (
            "【主線 2.1 · 分支 A】正式戰鬥：遭遇列表「Act 2：Polis 追擊」"
            "（5 回合內存活或擊敗追兵）。可先影合照再開戰。"
        ),
    },
    # ========== ACT 3 — 村莊 + Albert City Hunt ==========
    "act3_village_intel": {
        "name": "村莊情報",
        "hint": "打探 Oikos · 小遊戲",
        **_CAMP,
        "task_type": "minigame",
        "minigame_id": "wordle_custom",
        "minigame_config": {
            "maxGuesses": 6,
            "answers": ["OIKOS", "IGGY", "POLIS", "家", "山羊"],
        },
        "story_act": 3,
        "description": (
            "【主線 3 · 村莊避難】在村子裡打探 Oikos 線索。"
            "成功後會遇到了解內情的婦人。"
        ),
    },
    "act3_search_iggy": {
        "name": "搜尋 Iggy",
        "hint": "村莊巷弄 · 小遊戲",
        **_CAMP,
        "task_type": "minigame",
        "minigame_id": "spot_the_difference",
        "minigame_config": {"diffCount": 6, "timeLimitSec": 150},
        "story_act": 3,
        "description": (
            "【主線 3】Iggy 又怕連累大家偷偷跑掉——"
            "在村莊巷弄與廢墟中搜尋他，避開搜捕。"
        ),
    },
    "act3_village_battle": {
        "name": "村莊包圍戰",
        "hint": "戰鬥 · Polis",
        **_CAMP,
        "task_type": "photo",
        "story_act": 3,
        "description": (
            "【主線 3】後山被 Polis 包圍——挑戰遭遇戰「Polis 追擊」。"
            "危急時會有人出手……"
        ),
    },
    "albert_ching_1": {
        "name": "CHing 1 · 荃灣紅牆",
        "hint": "GPS 定位術",
        **_TSUEN_WAN,
        "task_type": "gps",
        "story_act": 4,
        "description": (
            "【主線 4.1】前往荃灣站外牆（印有景色的紅牆），"
            "開啟 GPS 驗證＝「施展定位術」。成功後解鎖下一提示。"
        ),
    },
    "albert_ching_2": {
        "name": "CHing 2 · 葵芳輪廓",
        "hint": "Worldle · 葵芳",
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
        "description": (
            "【主線 4.2】App 顯示社區邊界輪廓，猜出地點「葵芳」（最多 5 次）。"
            "答對後前往葵芳做結界任務。"
        ),
        "hint_media": "/static/mission_hints/albert_ching_2_kwaifong.svg",
    },
    "albert_ching_3": {
        "name": "CHing 3 · 葵芳結界",
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
        "description": (
            "【主線 4.3】語音密碼：「我叫做 Franchesca，今年係 19 歲半」。"
            "通過後解鎖美孚站。"
        ),
        "hint_media": "/static/mission_hints/albert_ching_3_password_hint.mp4",
    },
    "albert_ching_4": {
        "name": "CHing 4 · 美孚今昔",
        "hint": "壁畫 · 棄兒創傷",
        **_MEI_FOO,
        "task_type": "photo",
        "story_act": 4,
        "description": (
            "【主線 4.4】美孚站轉車隧道壁畫——解封第一道記憶（棄兒創傷）。"
            "影下對應細節並提交。"
        ),
        "hint_media": "/static/mission_hints/albert_ching_4_meifoo_hint.jpg",
    },
    "albert_ching_5": {
        "name": "CHing 5 · 九龍塘易經",
        "hint": "八乘八 · 再生火焰",
        **_KOWLOON_TONG,
        "task_type": "photo",
        "story_act": 4,
        "description": (
            "【主線 4.5】九龍塘「八乘八」藝術品——第三道記憶與再生火種。"
            "影符號組合；之後 Iggy 將重執 Phoenix Fire，並前往彩虹站。"
        ),
    },
    "act3_choihung_rally": {
        "name": "彩虹站集合",
        "hint": "與 Julian 會合",
        **_CHOI_HUNG,
        "task_type": "gps",
        "story_act": 5,
        "description": (
            "【主線 5】全體小隊立刻前往彩虹站，與 Julian 會合。"
            "（記憶任務完成後解鎖。）"
        ),
    },
    # ========== ACT 5–6 戰鬥相關提示任務 ==========
    "act4_julian_gate": {
        "name": "彩虹月台 · 迎戰",
        "hint": "Julian 戰前 · 影相",
        **_CHOI_HUNG,
        "task_type": "photo",
        "story_act": 5,
        "description": (
            "【Act 5】面具撕下之後——全組影一張準備迎戰的合照，"
            "然後挑戰遭遇戰 enc_iggy_act4_julian。"
        ),
    },
    "act5_return_camp": {
        "name": "前往西貢 SKORC",
        "hint": "Act 6 · 終局集合",
        **_CAMP,
        "task_type": "gps",
        "story_act": 6,
        "description": (
            "【Act 6 · Necessary Pain】Julian 敗亡引發連鎖反應。"
            "全隊前往 Oikos 總部——西貢戶外康樂中心（SKORC）集合。"
        ),
    },
    "act6_savio_gate": {
        "name": "迎戰暴走 Savio",
        "hint": "終局 BOSS 前 · 影相",
        **_CAMP,
        "task_type": "photo",
        "story_act": 6,
        "description": (
            "【Act 6】與 Iggy 並肩——全組影一張「我們選擇必要的痛」的合照，"
            "然後挑戰最終遭遇戰 enc_iggy_act6_savio。"
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
