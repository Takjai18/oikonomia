"""Act 1 QR item → unified supplies task / combat hooks.

Physical QR payloads (act1-water, …) still identify items. Progress is tracked
under one explore task ``act1_supplies`` with a checklist of four scans.
"""

# Parent explore task (single card in 探索 / dashboard).
ACT1_SUPPLIES_TASK_ID = "act1_supplies"

# qr_code_value → hooks
# sub_key: progress key stored as a submission task_id (legacy-compatible)
# requires_stories: must have viewed these before this QR can be claimed
ACT1_QR_HOOKS = {
    "act1-wood": {
        "parent_task_id": ACT1_SUPPLIES_TASK_ID,
        "sub_key": "act1_wood",
        "label": "木材",
        "requires_stories": ["iggy_stage0"],
        "start_encounter": "enc_iggy_act1_bubo",
    },
    "act1-water": {
        "parent_task_id": ACT1_SUPPLIES_TASK_ID,
        "sub_key": "act1_water",
        "label": "水",
        "requires_stories": ["iggy_stage0"],
        "start_encounter": None,
    },
    "act1-goat-badge": {
        "parent_task_id": ACT1_SUPPLIES_TASK_ID,
        "sub_key": "act1_goat_badge",
        "label": "殘缺的山羊徽章",
        "requires_stories": ["iggy_act1_post_bubo"],
        "start_encounter": None,
    },
    "act1-iron-plate": {
        "parent_task_id": ACT1_SUPPLIES_TASK_ID,
        "sub_key": "act1_iron_plate",
        "label": "刻著 Iggy 的鐵片",
        "requires_stories": ["iggy_act1_post_bubo"],
        "start_encounter": None,
    },
}

# Checklist order for UI
ACT1_CHECKLIST = [
    {"qr": "act1-water", "sub_key": "act1_water", "label": "水", "phase": "supplies"},
    {"qr": "act1-wood", "sub_key": "act1_wood", "label": "木材", "phase": "supplies",
     "note": "掃描後觸發布布教學戰"},
    {"qr": "act1-goat-badge", "sub_key": "act1_goat_badge", "label": "山羊徽章", "phase": "identity"},
    {"qr": "act1-iron-plate", "sub_key": "act1_iron_plate", "label": "Iggy 鐵片", "phase": "identity"},
]

# All sub_keys that must be done for parent task completion
ACT1_ALL_SUB_KEYS = [c["sub_key"] for c in ACT1_CHECKLIST]
ACT1_IDENTITY_SUB_KEYS = ["act1_goat_badge", "act1_iron_plate"]
ACT1_SUPPLY_SUB_KEYS = ["act1_water", "act1_wood"]


def hooks_for_qr_code(qr_code_value):
    if not qr_code_value:
        return {}
    key = str(qr_code_value).strip().lower()
    # Also accept exact case variants via original map
    raw = ACT1_QR_HOOKS.get(str(qr_code_value).strip()) or ACT1_QR_HOOKS.get(key)
    return dict(raw or {})
