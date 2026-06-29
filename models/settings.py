"""Shared runtime configuration for model layer (set once from app.py)."""


class ModelSettings:
    db_path = None
    upload_folder = None
    legacy_upload_folder = None
    default_protagonist = None
    squad_attributes = None
    max_inventory_slots = 5
    encounters_dir = None
    item_effect_stat_map = None
    item_effect_labels = None
    encounter_cache = None
    near_death_minutes = 15
    combat_action_types = None
    attack_action_types = None
    dice_multipliers = None
    combat_attack_base_damage = 10


settings = ModelSettings()


def configure(**kwargs):
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)