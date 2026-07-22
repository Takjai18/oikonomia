"""Cosmos / Oikonomia lore from 設定 doc (2026-07).

Worldbuilding SSOT for UI copy, GM notes, and narrative. Not all fields
are wired to combat mechanics yet (Zoo evolution tiers, NPC bosses beyond
encounters).
"""

WORLDVIEW = {
    "title": "Cosmos 的法則 (The Laws of Cosmos)",
    "laws": (
        "Cosmos 存在客觀、物理性的法則（責任之律、因果之律、尊重之律等）。"
        "試圖迴避現實與創傷、建立「無痛溫室」只會產生怪獸並引發系統性崩潰。"
    ),
    "zoo": (
        "Zoo（靈獸系統）是人類心理防禦機制與潛能的具象化。"
        "唯有直面真實自我、承擔現實摩擦力與個人責任的人，才能真正駕馭 Zoo 的力量。"
    ),
    "factions": {
        "polis": {
            "name": "Polis（城邦）",
            "summary": (
                "極端控制、律法主義與社會達爾文主義。"
                "主張「沒有痛苦就沒有成長」，強迫服從，踐踏自由意志，製造無情感的「空殼木偶」。"
            ),
        },
        "oikos": {
            "name": "Oikos（家）",
            "summary": (
                "有毒的無菌溫室。主張「愛就是消除一切負面感受」，"
                "過度拯救與保護，剝奪承擔後果的機會，養出極度索取、無法自理的「巨嬰」。"
            ),
        },
    },
}

# Character architecture matrix
CHARACTERS = {
    "iggy": {
        "display_name": "Iggy",
        "role": "protagonist",
        "archetype": "討好型／順從者 (Compliant / People-Pleaser)",
        "myth": (
            "「如果我能替他人承擔所有確定與痛苦，這就是我的價值所在。」"
            "恐懼衝突，誤以為說「不」是自私與傷害。"
        ),
        "zoo": {
            "name": "鳳凰 (Phoenix)",
            "early": "麻醉之炎——麻痺痛楚，但剝奪成長、製造巨嬰",
            "late": "涅槃之火——帶來痛苦但能燒斷病態共生、真正醫治",
        },
    },
    "marah": {
        "display_name": "Marah",
        "role": "protagonist",
        "archetype": "侵略型控制狂 (Aggressive Controller)",
        "myth": (
            "「我的真理絕對正確，痛楚能逼人屈服。」"
            "無視他人自由意志，強行灌入苦藥。"
        ),
        "zoo": {
            "name": "獅蠍 (Manticore)",
            "early": "暴政之毒——強迫成長",
            "late": "恩典解藥——尊重意志，在痛楚中提供緩衝",
        },
    },
    "savio": {
        "display_name": "Savio",
        "role": "antagonist",
        "archetype": "逃避者／彌賽亞情結 (Avoidant / Messiah Complex)",
        "myth": "「我可以代替別人承受一切痛苦，展現脆弱是軟弱的。」",
        "zoo": {
            "name": "山羊 (Goat / Agape)",
            "early": "無痛覺醒他人",
            "late": "吸收過量巨嬰負能量導致系統超載，黑化為被黑色臍帶纏繞的畸形巨獸",
        },
    },
    "julian": {
        "display_name": "Julian",
        "role": "npc",
        "archetype": "操縱型控制狂 (Manipulative Controller)",
        "myth": "「你必須為我的情緒與失敗負責。」擅長情緒勒索與道德綁架。",
        "zoo": {
            "name": "血田 (Akeldama)",
            "early": "種下他人身體組織（如斷指）",
            "late": "宿主能力爆發時收割共鳴，奪取其能力",
        },
    },
    "donna": {
        "display_name": "Donna",
        "role": "npc",
        "archetype": "無反應者 (Nonresponsive)",
        "myth": "「別人的死活與我無關，我只需要保護自己。」",
        "zoo": {
            "name": "冷漠封閉",
            "early": "從 Polis 叛逃後築起高牆",
            "late": "隔絕一切需求與關係",
        },
    },
    "simon": {
        "display_name": "Simon",
        "role": "faction_fighter",
        "archetype": "Oikos 戰力代表",
        "myth": "陣營對抗與戰鬥場景的壓迫來源之一。",
        "zoo": {"name": "（待補）", "early": "特定 Zoo 能力", "late": ""},
    },
    "samson": {
        "display_name": "Samson",
        "role": "faction_fighter",
        "archetype": "Polis / Oikos 戰力代表",
        "myth": "陣營對抗場景的物理／精神壓迫來源。",
        "zoo": {"name": "蜜獾等（設定中）", "early": "", "late": ""},
    },
    "eli": {
        "display_name": "Eli",
        "role": "faction_fighter",
        "archetype": "Polis / Oikos 戰力代表",
        "myth": "精神干擾／天氣控制等能力。",
        "zoo": {"name": "烏鴉等（設定中）", "early": "", "late": ""},
    },
}

# Six-act Iggy arc (mapped onto story stages 0–3 for progression engine)
IGGY_ACTS = {
    1: {
        "title": "飛狐雪山",
        "subtitle": "醬板鴨 · 木水 · 布布 · 身份",
        "story_stage": 0,
        "summary": (
            "飛狐雪山。玩家本帶醬板鴨想救助狐狸，卻遇見重傷男子。"
            "劇情引導玩家在場地掃描 QR 搜集木材與水、以及個人物品；"
            "掃描木材時立刻觸發雪山熊布布教學戰。"
        ),
        "tasks": [
            "掃描 QR：木材（立刻布布戰）、水",
            "掃描 QR：殘缺的山羊徵章、刻著 Iggy 的鐵片",
        ],
    },
    2: {
        "title": "虛妄的羔羊與引路人",
        "subtitle": "盲目犧牲與獲救",
        "story_stage": 1,
        "summary": (
            "逃亡中目擊 Polis 的殘暴拷問。Iggy 的討好者病態啟動，"
            "妄想用自我犧牲逃避焦慮與衝突。Julian 出現擊退敵人並拯救眾人。"
        ),
        "tasks": [
            "找出隱藏的 Iggy（Where’s Iggy 小遊戲，圖片後補）",
            "迷宮小遊戲",
            "與 Polis 戰鬥：5 個回合內不敗（生存勝利）",
        ],
    },
    3: {
        "title": "溫室的裂痕",
        "subtitle": "記憶重組與界線突破",
        "story_stage": 2,
        "summary": (
            "Julian 假意引導 Iggy 找回記憶。Iggy 接觸過去「拯救」過的 NPC，"
            "發現無底線包容只製造了巨嬰。在玩家引導下首次說「不」，點燃涅槃之火。"
        ),
        "tasks": ["City Hunt 系列任務（港鐵／車站實境）"],
    },
    4: {
        "title": "血田的獠牙",
        "subtitle": "背刺與真面目",
        "story_stage": 2,
        "summary": (
            "Iggy 能力剛覺醒，Julian 露出真面目，發動「血田」強行收割並奪取鳳凰之力。"
        ),
        "tasks": ["擊敗 Julian"],
    },
    5: {
        "title": "業火與重塑",
        "subtitle": "大災難與承擔",
        "story_stage": 3,
        "summary": (
            "Julian 無法承受涅槃之火背後「承擔真實痛苦與責任」的重量，能力暴走，"
            "引發 Oikos 成員（如 Simon）集體失控。Iggy 與玩家並肩，用涅槃之火燒斷有毒共生。"
        ),
        "tasks": ["到達營地"],
    },
    6: {
        "title": "打破無傷神話",
        "subtitle": "直面偽神與結局",
        "story_stage": 3,
        "summary": (
            "直面 Savio 的無痛烏托邦洗腦。Iggy 明白愛有時需要必要的衝突與痛楚，"
            "最終擊破 Savio 的領域，摧毀有毒體制。"
        ),
        "tasks": ["擊敗 Savio"],
    },
}
