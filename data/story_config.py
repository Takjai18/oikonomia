"""Story stage threshold configuration — aligned to Iggy Arc (設定1)."""

# Progression still uses 4 bands (0–3). Acts map as:
#   stage 0 → Act 1
#   stage 1 → Act 2
#   stage 2 → Act 3–4
#   stage 3 → Act 5–6
STORY_STAGE_THRESHOLDS = {
    1: 4,   # Act 1：木＋水＋兩件隨身物
    2: 6,   # Act 2：潛行／Polis 等
    3: 12,  # Act 3：村莊＋Albert Ching 鏈
}

# Optional hard gates by location id (uncomment when task IDs are locked in).
STORY_STAGE_REQUIRED_TASKS = {
    # 1: ["act1_keepsake", "act1_sauce_duck"],
    # 2: ["act2_polis_survive"],
    # 3: ["act4_julian", "act6_savio"],
}

STORY_CONTENT = {
    "iggy": {
        0: {
            "title": "🔥 第一章 · 飛狐雪山",
            "content": (
                "風雪中遇見重傷失憶的男子。掃描 QR 取水與木材（木材觸發布布教學戰）；"
                "再搜集隨身物品，揭開名字「Iggy」，逃離 Polis 追捕。"
            ),
        },
        1: {
            "title": "🔥 第二章 · 抉擇與邊界",
            "content": (
                "Iggy 吐血仍推拒善意。選擇離開將迎戰 Polis；選擇照顧則潛行下山。"
            ),
        },
        2: {
            "title": "🔥 第三章 · 記憶之路",
            "content": (
                "村莊庇護、Julian 登場，City Hunt 尋找 Albert Ching（1→5），集合彩虹站。"
            ),
        },
        3: {
            "title": "🔥 Act 5–6：業火與偽神",
            "content": (
                "災難蔓延，Iggy 不再逃避，與你並肩燒斷有毒共生。"
                "最後一關：直面 Savio 的無痛烏托邦——打破無傷神話。"
            ),
        },
    },
    "marah": {
        0: {
            "title": "🌊 第一階段：智慧的開端",
            "content": "你選擇了 Marah 路線，開始以智慧同韌性去面對界線。（主線目前以 Iggy Arc 為營會主線。）",
        },
        1: {
            "title": "🌊 第二階段：低語的解析",
            "content": "Judas 嘅謎題開始出現。你正試圖理解 Marah 背後嘅意義。",
        },
        2: {
            "title": "🌊 第三階段：韌性的考驗",
            "content": "你開始面對更深層嘅情緒勒索同界線問題。",
        },
        3: {
            "title": "🌊 最終階段：覺醒",
            "content": "你已經掌握足夠嘅資訊，準備迎接最後嘅真相。",
        },
    },
}
