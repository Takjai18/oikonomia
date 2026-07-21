"""Combat feature unlock policy (story-stage gated abilities).

Zoo is locked until the team's story stage reaches ZOO_UNLOCK_STORY_STAGE.
Override with env OIKONOMIA_ZOO_UNLOCK_STAGE (integer). Use 0 to unlock at start.
"""
from __future__ import annotations

import os

# Default: unlock at story stage 2 (after stages 0 and 1).
_DEFAULT_ZOO_UNLOCK_STAGE = 2


def _parse_stage(raw, default):
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return default


def get_zoo_unlock_story_stage():
    """Read unlock stage (env override each call so tests can setenv)."""
    env = os.environ.get("OIKONOMIA_ZOO_UNLOCK_STAGE")
    if env is None or str(env).strip() == "":
        return _DEFAULT_ZOO_UNLOCK_STAGE
    return _parse_stage(env, _DEFAULT_ZOO_UNLOCK_STAGE)


# Module-level alias for docs / /api/version (evaluated at import; prefer getter).
ZOO_UNLOCK_STORY_STAGE = get_zoo_unlock_story_stage()
