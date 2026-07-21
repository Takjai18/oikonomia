"""Story stage threshold configuration — aligned to Iggy Arc (設定1)."""

# Progression still uses 4 bands (0–3). Acts map as:
#   stage 0 → Act 1
#   stage 1 → Act 2
#   stage 2 → Act 3–4
#   stage 3 → Act 5–6
STORY_STAGE_THRESHOLDS = {
    1: 2,   # Act 1 完成：至少 2 個任務（貼身物品 + 醬板鴨）
    2: 5,   # Act 2：小遊戲／Polis 戰等
    3: 8,   # Act 3 City Hunt + Julian 後進入最終
}

# Optional hard gates by location id (uncomment when task IDs are locked in).
STORY_STAGE_REQUIRED_TASKS = {
    # 1: ["act1_keepsake", "act1_sauce_duck"],
    # 2: ["act2_polis_survive"],
    # 3: ["act4_julian", "act6_salvio"],
}

STORY_CONTENT = {
    "iggy": {
        0: {
            "title": "🔥 Act 1：雪山與醬板鴨",
            "content": (
                "Iggy 與 Marah 交戰時 Zoo 失控並落敗，墜入雪山，失去能力與記憶。"
                "你在雪山上遇見他——先確認他是誰，再找出一隻醬板鴨幫他捱過這一關。"
            ),
        },
        1: {
            "title": "🔥 Act 2：虛妄的羔羊與引路人",
            "content": (
                "逃亡中目擊 Polis 的殘暴。Iggy 的討好者模式被觸發，想用自我犧牲換取「和平」。"
                "Julian 出現……他是救星，還是另一條鎖鏈？"
            ),
        },
        2: {
            "title": "🔥 Act 3–4：溫室裂痕與血田",
            "content": (
                "記憶重組逼你看清：無底線的「愛」只會製造巨嬰。"
                "當 Iggy 首次說出「不」、點燃涅槃之火，血田的獠牙也同時露出。"
            ),
        },
        3: {
            "title": "🔥 Act 5–6：業火與偽神",
            "content": (
                "災難蔓延，Iggy 不再逃避，與你並肩燒斷有毒共生。"
                "最後一關：直面 Salvio 的無痛烏托邦——打破無傷神話。"
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
