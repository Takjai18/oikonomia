"""Act 1 QR item → task / combat hooks.

QR payload resolves to items.qr_code_value; after a successful claim we may
auto-complete a location task and/or start a tutorial combat.
"""

# qr_code_value → hooks
ACT1_QR_HOOKS = {
    "act1-lighter": {
        "linked_task_id": "act1_lighter",
        "start_encounter": None,
    },
    "act1-wood": {
        "linked_task_id": "act1_wood",
        # Scanning wood spawns the tutorial snow-bear fight.
        "start_encounter": "enc_iggy_act1_bubo",
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
