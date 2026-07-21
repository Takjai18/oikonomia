"""GPS / task location definitions (explore tasks + minigames)."""

# Shared camp-area coords for non-GPS tasks (list UI only; GPS tasks use real verify).
_CAMP = {"lat": 22.3845, "lng": 114.2695, "radius": 80}

LOCATIONS = {
    # —— 實境任務 ——
    "loc1": {
        "name": "裂縫起點",
        "hint": "籃球場旁邊嘅大樹下",
        "lat": 22.3850,
        "lng": 114.2700,
        "radius": 40,
        "task_type": "gps",
        "description": (
            "Iggy 嘅第一段記憶似乎喺呢度。到達後先驗證定位，"
            "再影一張包含所有組員樣子嘅相（GPS 有時唔準，靠相片確認大家到場）。"
        ),
    },
    "loc2": {
        "name": "Judas 嘅低語",
        "hint": "室內活動室角落 · 小遊戲",
        "lat": 22.3845,
        "lng": 114.2695,
        "radius": 30,
        "task_type": "minigame",
        "minigame_id": "reverse_contrarian",
        "minigame_config": {"lives": 3, "clearStreak": 5},
        "description": "Judas 嘅法則同現實相反——唔好聽話，先通過測試。",
    },
    "loc3": {
        "name": "痛楚回音",
        "hint": "營地邊緣安靜位置",
        "lat": 22.3830,
        "lng": 114.2720,
        "radius": 50,
        "task_type": "photo",
        "description": "影一張代表「界線」嘅相。",
    },
    # —— 小遊戲任務（營會探索） ——
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
            "answers": ["界線", "神智", "韌性", "裂縫", "IGGY", "JUDAS"],
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
            "script": "界線不會自己守住。",
            "minSeconds": 3,
            "maxSeconds": 60,
        },
        "description": (
            "用聲音立約。讀出指定句子並錄音（最少 3 秒），"
            "試聽滿意後提交；錄音會交俾 GM 存檔。"
        ),
    },
}
