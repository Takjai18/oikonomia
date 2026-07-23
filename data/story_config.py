"""Story stage threshold configuration — aligned to Iggy Arc (設定1)."""

# Progression still uses 4 bands (0–3). Acts map as:
#   stage 0 → Act 1
#   stage 1 → Act 2
#   stage 2 → Act 3–4
#   stage 3 → Act 5–6
STORY_STAGE_THRESHOLDS = {
    1: 2,   # Act 1：supplies parent + 逃離（sub-keys also count）
    2: 4,   # Act 2：分支 + 村莊起
    3: 10,  # Act 3–4：村莊＋CHing 鏈＋彩虹
}

# Soft gates (any listed task → stage at least N). Primary progression is unlock stories.
STORY_STAGE_REQUIRED_TASKS = {
    1: ["act1_escape", "act1_supplies"],
    2: ["act2_stealth", "act2_polis_fight"],
    3: ["act3_choihung_rally"],
}

STORY_CONTENT = {
    "iggy": {
        0: {
            "title": "🔥 第一章 · 飛狐雪山",
            "content": (
                "風雪中遇見重傷失憶的男子。先掃水與木材（木材→布布教學戰）；"
                "篝火後再搜集隨身物品，揭開「Iggy」，逃離 Polis。"
            ),
        },
        1: {
            "title": "🔥 第二章 · Avoidant",
            "content": (
                "Iggy 吐血仍推拒善意。離開→Polis 戰；照顧→潛行下山。"
            ),
        },
        2: {
            "title": "🔥 第三–四章 · 村莊與記憶",
            "content": (
                "村莊庇護、搜尋 Iggy、Julian 救場；再 City Hunt（CHing 1→5）解封記憶。"
            ),
        },
        3: {
            "title": "🔥 第五–六章 · Pain Alone / Necessary Pain",
            "content": (
                "彩虹站面具撕下；二次覺醒後前往西貢，迎戰暴走 Savio。"
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
