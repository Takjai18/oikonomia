"""GPS / task location definitions — Iggy Arc (設定1) + camp minigames."""

# Shared camp-area coords for non-GPS / pending-GPS tasks.
_CAMP = {"lat": 22.3845, "lng": 114.2695, "radius": 80}

# Placeholder HK MTR-ish coords for City Hunt (replace with precise pins when locked).
_MEI_FOO = {"lat": 22.3370, "lng": 114.1390, "radius": 120}
_SSP = {"lat": 22.3307, "lng": 114.1622, "radius": 100}
_KOWLOON_TONG = {"lat": 22.3370, "lng": 114.1760, "radius": 100}
_CHOI_HUNG = {"lat": 22.3347, "lng": 114.2090, "radius": 100}

LOCATIONS = {
    # ========== ACT 1 — 雪山救助 ==========
    "act1_keepsake": {
        "name": "Iggy 的貼身物品",
        "hint": "雪山記憶點 · 影相",
        **_CAMP,
        "task_type": "photo",
        "story_act": 1,
        "description": (
            "【Act 1】找出能確認 Iggy 身份的貼身物品（營會道具／GM 放置）。"
            "影一張清楚見到物品同至少一位隊員的相，提交完成。"
        ),
    },
    "act1_sauce_duck": {
        "name": "醬板鴨",
        "hint": "雪山補給 · 影相",
        **_CAMP,
        "task_type": "photo",
        "story_act": 1,
        "description": (
            "【Act 1】找出一隻醬板鴨（實體道具），「給 Iggy 吃」——"
            "影相記錄全組與醬板鴨，提交完成，幫他捱過艱難時刻。"
        ),
    },
    # ========== ACT 2 — 逃亡 / Polis ==========
    "act2_find_iggy": {
        "name": "找出隱藏的 Iggy",
        "hint": "Where’s Iggy · 小遊戲（圖片後補）",
        **_CAMP,
        "task_type": "minigame",
        "minigame_id": "spot_the_difference",
        "minigame_config": {"diffCount": 5, "timeLimitSec": 120},
        "story_act": 2,
        "description": (
            "【Act 2】在混亂場景中找出隱藏的 Iggy（類似 Where’s Wally；"
            "正式圖片後補——暫用找不同小遊戲代替）。"
        ),
    },
    "act2_maze": {
        "name": "逃亡迷宮",
        "hint": "迷宮 · 小遊戲",
        **_CAMP,
        "task_type": "minigame",
        "minigame_id": "sudoku",
        "minigame_config": {"maxHints": 3},
        "story_act": 2,
        "description": (
            "【Act 2】迷宮小遊戲（正式迷宮圖後補——暫以秩序方陣／數獨代表「找到出路」）。"
            "完成即視為帶隊脫出封鎖。"
        ),
    },
    "act2_polis_prep": {
        "name": "Polis 對峙前哨",
        "hint": "戰鬥前準備 · 影相",
        **_CAMP,
        "task_type": "photo",
        "story_act": 2,
        "description": (
            "【Act 2】與 Polis 開戰前，全組影一張「準備守住 5 回合」的合照，"
            "然後進入遭遇戰：enc_iggy_act2_polis（5 回合內存活即勝）。"
        ),
    },
    # ========== ACT 3 — City Hunt ==========
    "act3_hk_girl_pose": {
        "name": "餐廳港女 Pose",
        "hint": "City Hunt · 影相",
        **_CAMP,
        "task_type": "photo",
        "story_act": 3,
        "description": (
            "【Act 3 · City Hunt】餐廳全組經典港女 Pose："
            "雙手比心／托腮＋嘟嘴＋微微側頭。即場傳相／提交。"
        ),
    },
    "act3_meifoo_worldle": {
        "name": "美孚站 Worldle",
        "hint": "City Hunt · 美孚站",
        **_MEI_FOO,
        "task_type": "photo",
        "story_act": 3,
        "description": (
            "【Act 3】到達美孚站後，用手機玩 Worldle（或類似），"
            "限時約 3 分鐘估出「Mei Foo」。完成後影站內標誌＋隊員提交。"
        ),
    },
    "act3_meifoo_murals": {
        "name": "美孚今昔壁畫",
        "hint": "City Hunt · 轉車隧道壁畫",
        **_MEI_FOO,
        "task_type": "photo",
        "story_act": 3,
        "description": (
            "【Act 3】在美孚轉車隧道壁畫中，找出並影低其中 3 類："
            "① 中秋 ② 海灘／海景 ③ 現代居民生活。可簡短口述分別。"
        ),
    },
    "act3_ssp_find": {
        "name": "深水埗站尋物",
        "hint": "City Hunt · 深水埗站",
        **_SSP,
        "task_type": "photo",
        "story_act": 3,
        "description": (
            "【Act 3】在深水埗站完成 2–3 項（影相）："
            "城市的特性藝術品；月台綠色／特定色支柱數量；"
            "有「深水埗」字樣的舊款指示牌。（精確目標可由 GM 當日宣佈。）"
        ),
    },
    "act3_kowloontong_bagua": {
        "name": "九龍塘八乘八",
        "hint": "City Hunt · 藝術品解迷",
        **_KOWLOON_TONG,
        "task_type": "photo",
        "story_act": 3,
        "description": (
            "【Act 3】九龍塘「八乘八」藝術品：影最少 2 組「最有故事」的符號組合；"
            "全組 1 分鐘為其中一組編 20 字內短故事（寫在紙上或備註影相）。"
        ),
    },
    "act3_choihung_art": {
        "name": "彩虹站芭蕾舞者",
        "hint": "City Hunt · 站內藝術",
        **_CHOI_HUNG,
        "task_type": "photo",
        "story_act": 3,
        "description": (
            "【Act 3】優先站內：影「陶醉的芭蕾舞者」銅像＋彩虹條紋牆合照。"
            "（時間緊不建議出站彩虹邨。）"
        ),
    },
    # ========== ACT 4–6 戰鬥相關提示任務 ==========
    "act4_julian_gate": {
        "name": "血田前夜",
        "hint": "進入 Julian 戰前 · 影相",
        **_CAMP,
        "task_type": "photo",
        "story_act": 4,
        "description": (
            "【Act 4】全組影一張「準備迎戰 Julian／血田」的合照，"
            "然後挑戰遭遇戰 enc_iggy_act4_julian。"
        ),
    },
    "act5_return_camp": {
        "name": "到達營地",
        "hint": "Act 5 · GPS／影相",
        **_CAMP,
        "task_type": "gps",
        "story_act": 5,
        "description": (
            "【Act 5】業火蔓延後，全隊回到營地集合。"
            "到達指定範圍後驗證定位，並影全組合照提交。"
        ),
    },
    "act6_salvio_gate": {
        "name": "偽神領域入口",
        "hint": "最終戰前 · 影相",
        **_CAMP,
        "task_type": "photo",
        "story_act": 6,
        "description": (
            "【Act 6】打破無傷神話——全組影一張「我們選擇真實的痛」的合照，"
            "然後挑戰最終遭遇戰 enc_iggy_act6_salvio。"
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
