"""Act 1 QR item → task / combat hooks.

QR payload resolves to items.qr_code_value; after a successful claim we may
auto-complete a location task and/or start a tutorial combat.

Flow: story prompts players to search the field → scan 木 / 水 / 個人物品.
Scanning wood immediately starts the Bubuo (布布) tutorial fight.
"""

# qr_code_value → hooks
ACT1_QR_HOOKS = {
    "act1-wood": {
        "linked_task_id": "act1_wood",
        # Scan wood → immediate tutorial combat with 布布.
        "start_encounter": "enc_iggy_act1_bubo",
    },
    "act1-water": {
        "linked_task_id": "act1_water",
        "start_encounter": None,
    },
    "act1-goat-badge": {
        "linked_task_id": "act1_goat_badge",
        "start_encounter": None,
    },
    "act1-iron-plate": {
        "linked_task_id": "act1_iron_plate",
        "start_encounter": None,
    },
}


def hooks_for_qr_code(qr_code_value):
    if not qr_code_value:
        return {}
    return dict(ACT1_QR_HOOKS.get(str(qr_code_value).strip(), {}) or {})
