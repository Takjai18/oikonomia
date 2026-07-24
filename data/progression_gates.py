"""Progressive unlock gates for explore tasks & story encounters.

Design:
  - Tasks only appear after the related story has been viewed (or prior tasks done).
  - Combats only appear after the related story/branch (or QR trigger).
  - Side camp minigames stay always visible (optional fun, not mainline spoilers).
  - GM unlock mode (services.progression) bypasses all gates for a chosen player.
"""

# ---------------------------------------------------------------------------
# Task gates (location id → requirements)
# Empty / missing entry for side activities = always visible.
# ---------------------------------------------------------------------------
# requires_stories: ALL of these story_ids must be viewed by the squad
# requires_tasks:   ALL of these task_ids must be completed by the team
# requires_any_tasks: at least ONE of these completed
# requires_any_stories: at least ONE of these viewed
# requires_encounters: ALL of these encounter_ids completed by the team
# hide_until_unlocked: if True and no requires_* met → hidden (default True for mainline)

TASK_GATES = {
    # —— Act 1 統一物資任務（看完飛狐雪山序幕後出現；checklist 內再分階段）——
    "act1_supplies": {
        "requires_stories": ["iggy_stage0"],
    },
    # —— Act 1.3：後有追兵（身分揭曉後）——
    "act1_escape": {
        "requires_stories": ["iggy_act1_identity"],
    },
    # —— Act 2 分支 ——
    "act2_polis_fight": {
        "requires_any_stories": ["iggy_act2_branch_leave"],
    },
    "act2_stealth": {
        "requires_any_stories": ["iggy_act2_branch_care"],
    },
    # —— Act 3 村莊（逐步解鎖）——
    "act3_village_intel": {
        "requires_stories": ["iggy_stage2"],
    },
    "act3_search_iggy": {
        "requires_stories": ["iggy_act3_shelter"],
    },
    "act3_village_battle": {
        "requires_stories": ["iggy_act3_found_iggy"],
    },
    # —— Act 4 City Hunt 鏈 ——
    "albert_ching_1": {
        "requires_stories": ["iggy_act3_julian"],
    },
    "albert_ching_2": {
        "requires_tasks": ["albert_ching_1"],
    },
    "albert_ching_3": {
        "requires_tasks": ["albert_ching_2"],
    },
    "albert_ching_4": {
        "requires_tasks": ["albert_ching_3"],
    },
    "albert_ching_5": {
        "requires_tasks": ["albert_ching_4"],
    },
    "act3_choihung_rally": {
        "requires_tasks": ["albert_ching_5"],
    },
    # —— Act 5–6 ——
    "act4_julian_gate": {
        "requires_stories": ["iggy_act5_betrayal"],
    },
    "act5_return_camp": {
        "requires_encounters": ["enc_iggy_act4_julian"],
    },
    "act6_savio_gate": {
        "requires_stories": ["iggy_act6_approach"],
    },
}

# Side / optional camp tasks — always visible (not mainline spoilers).
SIDE_TASK_PREFIXES = ("loc_",)

# ---------------------------------------------------------------------------
# Encounter gates (beyond story_stage number)
# ---------------------------------------------------------------------------
# hide_from_list: never show in /encounters (QR / auto-start only), unless unlock mode
# requires_stories / requires_any_stories / requires_tasks / requires_encounters

ENCOUNTER_GATES = {
    "enc_iggy_act1_bubo": {
        "requires_stories": ["iggy_stage0"],
        # Prefer QR wood path; list after wood sub-scan or parent supplies unlocked.
        "requires_any_tasks": ["act1_wood", "act1_supplies"],
    },
    "enc_iggy_act2_polis": {
        "requires_any_stories": ["iggy_act2_branch_leave", "iggy_act3_found_iggy"],
    },
    "enc_iggy_act4_julian": {
        "requires_any_stories": ["iggy_act5_betrayal"],
        "requires_tasks": ["act3_choihung_rally"],
    },
    "enc_iggy_act6_savio": {
        "requires_stories": ["iggy_act6_approach"],
    },
    # Legacy placeholders — hide from normal play
    "enc_iggy_01_leech": {
        "hidden": True,
    },
    "enc_iggy_02_boundary": {
        "hidden": True,
    },
}

# After a task is newly completed → grant these story unlocks to the team.
TASK_STORY_UNLOCKS = {
    "act1_supplies": [],  # identity story granted when badge+iron done (items route)
    "act1_escape": ["iggy_stage1"],
    "act2_stealth": ["iggy_stage2"],
    "act2_polis_fight": ["iggy_stage2"],
    "act3_village_intel": ["iggy_act3_shelter"],
    "act3_search_iggy": ["iggy_act3_found_iggy"],
    "act3_village_battle": ["iggy_act3_julian"],
    # After each City Hunt step: full narrative beat (auto-play via pending story)
    "albert_ching_1": ["iggy_act4_redwall"],
    "albert_ching_2": ["iggy_act4_map_clear"],
    "albert_ching_3": ["iggy_act4_albert_test"],
    "albert_ching_4": ["iggy_act4_meifoo"],
    # After Mission 5: plumber memory then phoenix (order in PROGRESSIVE_UNLOCK_ORDER)
    "albert_ching_5": ["iggy_act4_plumber", "iggy_act4_phoenix"],
    "act3_choihung_rally": ["iggy_act5_betrayal"],
    "act4_julian_gate": [],
    "act6_savio_gate": [],
}

# After encounter victory → already handled by next_story_unlock in JSON;
# extra mapping for village fight reusing polis encounter if needed:
ENCOUNTER_STORY_UNLOCKS = {
    "enc_iggy_act1_bubo": ["iggy_act1_post_bubo"],
    # Branch A fight → post dialogue, then village opener (queue order respected in story.py).
    "enc_iggy_act2_polis": ["iggy_act2_post_polis", "iggy_stage2"],
    "enc_iggy_act4_julian": ["iggy_act6_approach"],
    "enc_iggy_act6_savio": ["iggy_ending_victory"],
}
