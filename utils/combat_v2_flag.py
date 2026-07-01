"""COMBAT_V2 feature flag — default ON; GM can persist off via data/.combat_v2."""
import os

_ON = frozenset({"1", "true", "yes", "on"})
_OFF = frozenset({"0", "false", "no", "off"})
_FLAG_NAME = ".combat_v2"


def _data_dir():
    return os.environ.get("DATA_DIR") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
    )


def flag_file_path(data_dir=None):
    return os.path.join(data_dir or _data_dir(), _FLAG_NAME)


def _parse_toggle(raw):
    if raw is None:
        return None
    val = str(raw).strip().lower()
    if val in _ON:
        return True
    if val in _OFF:
        return False
    return None


def is_combat_v2_enabled():
    """
    Combat V2 is ON by default.

    Precedence: COMBAT_V2 env (explicit) → data/.combat_v2 → default True.
    Env COMBAT_V2=0 forces off (deploy/emergency); env COMBAT_V2=1 forces on.
    """
    env_val = _parse_toggle(os.environ.get("COMBAT_V2"))
    if env_val is not None:
        return env_val

    path = flag_file_path()
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                file_val = _parse_toggle(fh.read())
                if file_val is not None:
                    return file_val
        except OSError:
            pass

    return True


def set_combat_v2_enabled(enabled):
    """Persist toggle for all workers (read on each request). Updates current process env."""
    data_dir = _data_dir()
    try:
        os.makedirs(data_dir, exist_ok=True)
    except OSError:
        pass
    path = flag_file_path(data_dir)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("1" if enabled else "0")
    try:
        os.chmod(path, 0o644)
    except OSError:
        pass
    os.environ["COMBAT_V2"] = "1" if enabled else "0"
    return enabled


def combat_v2_module_present():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.isfile(os.path.join(root, "static", "js", "combat", "index.js"))


def combat_v2_active():
    return is_combat_v2_enabled() and combat_v2_module_present()


def sync_combat_v2_env_from_storage():
    """Call at process startup so legacy os.environ readers stay consistent."""
    os.environ["COMBAT_V2"] = "1" if is_combat_v2_enabled() else "0"