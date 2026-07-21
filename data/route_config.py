"""Story route policy (Iggy / Marah).

Camp default: every player and team is forced onto the Iggy route.
Restore dual-route choice by setting env:

  OIKONOMIA_FORCED_ROUTE=

Force Marah instead:

  OIKONOMIA_FORCED_ROUTE=marah
"""
from __future__ import annotations

import os

VALID_ROUTES = frozenset({"iggy", "marah"})

# Default "iggy" when env unset. Empty string disables force (dual route).
_raw = os.environ.get("OIKONOMIA_FORCED_ROUTE", "iggy")
if _raw is None:
    FORCED_ROUTE = "iggy"
else:
    cleaned = _raw.strip().lower()
    if cleaned == "":
        FORCED_ROUTE = None
    elif cleaned in VALID_ROUTES:
        FORCED_ROUTE = cleaned
    else:
        FORCED_ROUTE = "iggy"


def is_route_forced() -> bool:
    return FORCED_ROUTE in VALID_ROUTES


def is_route_allowed(route) -> bool:
    route = (route or "").strip().lower()
    if route not in VALID_ROUTES:
        return False
    if FORCED_ROUTE:
        return route == FORCED_ROUTE
    return True


def resolve_route(route=None):
    """Return forced route when set; otherwise a valid free-choice route or None."""
    if FORCED_ROUTE:
        return FORCED_ROUTE
    route = (route or "").strip().lower()
    return route if route in VALID_ROUTES else None


def allowed_routes():
    if FORCED_ROUTE:
        return (FORCED_ROUTE,)
    return tuple(sorted(VALID_ROUTES))
