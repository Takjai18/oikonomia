"""Load production secrets from data/ files (PythonAnywhere Web workers)."""
import os


def load_production_secrets(project_dir=None):
    """
    Populate SECRET_KEY and GM_PIN from data/.secret_key and data/.gm_pin.

    Web tab workers do not inherit shell exports from pa-update.sh.
    Idempotent — safe to call from wsgi.py and app.py.
    """
    if project_dir:
        default_data = os.path.join(project_dir, "data")
        os.environ.setdefault("DATA_DIR", default_data)

    data_dir = os.environ.get("DATA_DIR")
    if not data_dir:
        return

    try:
        os.makedirs(data_dir, exist_ok=True)
    except OSError:
        pass

    for filename, env_key in ((".secret_key", "SECRET_KEY"), (".gm_pin", "GM_PIN")):
        if os.environ.get(env_key, "").strip():
            continue
        path = os.path.join(data_dir, filename)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                value = fh.read().strip()
                if value:
                    os.environ[env_key] = value
        except OSError:
            continue

    # COMBAT_V2: Web tab env OR data/.combat_v2 (PA workers don't inherit shell export)
    if not os.environ.get("COMBAT_V2", "").strip():
        flag_path = os.path.join(data_dir, ".combat_v2")
        if os.path.isfile(flag_path):
            try:
                with open(flag_path, encoding="utf-8") as fh:
                    if fh.read().strip().lower() in ("1", "true", "yes", "on"):
                        os.environ["COMBAT_V2"] = "1"
            except OSError:
                pass