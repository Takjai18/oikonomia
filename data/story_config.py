"""Story stage threshold configuration."""

STORY_STAGE_THRESHOLDS = {
    1: 2,   # Stage 1：至少 N 個任務 — 可改
    2: 4,   # Stage 2：至少 N 個任務 — 可改
    3: 6,   # Stage 3（最終）：至少 N 個任務 — 可改
}

STORY_STAGE_REQUIRED_TASKS = {
    # 1: ["loc1"],
    # 2: ["loc2"],
    # 3: ["loc3"],
}

STORY_CONTENT = {
    "iggy": {
        0: {"title": "🔥 第一階段：裂縫的開端", "content": "你踏入了 Oikonomia 的世界，Iggy 的第一段記憶正喺度等待被找回。"},
        1: {"title": "🔥 第二階段：痛楚的回音", "content": "你開始感受到 Iggy 曾經承受過嘅界線與痛楚。Judas 的低語開始出現。"},
        2: {"title": "🔥 第三階段：界線的崩壞", "content": "Iggy 嘅世界開始出現裂痕。你必須決定係咪繼續陪佢走落去。"},
        3: {"title": "🔥 最終階段：救贖或崩壞", "content": "你已經深入 Iggy 嘅核心。最後嘅選擇將會決定一切。"},
    },
    "marah": {
        0: {"title": "🌊 第一階段：智慧的開端", "content": "你選擇了 Marah 路線，開始以智慧同韌性去面對界線。"},
        1: {"title": "🌊 第二階段：低語的解析", "content": "Judas 嘅謎題開始出現。你正試圖理解 Marah 背後嘅意義。"},
        2: {"title": "🌊 第三階段：韌性的考驗", "content": "你開始面對更深層嘅情緒勒索同界線問題。"},
        3: {"title": "🌊 最終階段：覺醒", "content": "你已經掌握足夠嘅資訊，準備迎接最後嘅真相。"},
    },
}
