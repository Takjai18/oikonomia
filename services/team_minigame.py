"""Team-synced minigame sessions (poll-based, file-backed).

Used by 潛行下山 (flash_memory) and 村莊情報 (mastermind).
"""
from __future__ import annotations

import json
import os
import random
import string
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from models.settings import settings
from models.squad import get_squad, get_team_members
from utils.helpers import normalize_team_id

_LOCK = threading.RLock()

ALPHANUM = string.digits + string.ascii_uppercase
MASTERMIND_COLORS = ["R", "B", "G", "Y", "P", "O"]


def _path() -> str:
    base = os.path.dirname(settings.db_path or "") or "."
    return os.path.join(base, "team_minigames.json")


def _now() -> float:
    return time.time()


def _iso() -> str:
    return datetime.now().isoformat()


def _load() -> dict:
    path = _path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f) or {}
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    path = _path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)
    os.replace(tmp, path)


def _session_key(team_id: str, task_id: str) -> str:
    return f"{normalize_team_id(team_id)}::{task_id}"


def _team_member_ids(team_id: str) -> List[str]:
    members = get_team_members(team_id) or []
    out = []
    for m in members:
        sid = (m or {}).get("squad_id")
        if sid and not str(sid).startswith("protagonist:"):
            out.append(sid)
    return out


def _member_names(team_id: str) -> Dict[str, str]:
    names = {}
    for m in get_team_members(team_id) or []:
        sid = (m or {}).get("squad_id")
        if sid:
            names[sid] = (m or {}).get("display_name") or sid
    return names


def _public_joined(sess: dict, names: dict) -> List[dict]:
    joined = sess.get("joined") or {}
    now = _now()
    rows = []
    for sid, meta in joined.items():
        last = float((meta or {}).get("last_seen") or 0)
        rows.append({
            "squad_id": sid,
            "display_name": names.get(sid) or (meta or {}).get("name") or sid,
            "online": (now - last) < 25,
            "won": bool((meta or {}).get("won")),
            "lost": bool((meta or {}).get("lost")),
            "guesses": int((meta or {}).get("guesses") or 0),
            "answered": sid in (sess.get("answers") or {}),
        })
    return rows


def _flash_code_length(round_num: int) -> int:
    # Round 1 → 2 chars, grows to ~7 by round 10
    return min(8, 1 + max(1, int(round_num)))


def _gen_flash_code(length: int) -> str:
    # Mix digits + letters; early rounds prefer digits-heavy
    if length <= 2:
        pool = string.digits
    elif length <= 4:
        pool = string.digits + string.ascii_uppercase[:10]
    else:
        pool = ALPHANUM
    return "".join(random.choice(pool) for _ in range(length))


def _gen_mastermind_secret(length: int = 4) -> List[str]:
    return [random.choice(MASTERMIND_COLORS) for _ in range(length)]


def score_mastermind(secret: List[str], guess: List[str]) -> dict:
    """green=exact, white=wrong pos, red=neither."""
    n = len(secret)
    used_s = [False] * n
    used_g = [False] * n
    green = 0
    white = 0
    for i in range(n):
        if i < len(guess) and guess[i] == secret[i]:
            green += 1
            used_s[i] = True
            used_g[i] = True
    for i in range(n):
        if i >= len(guess) or used_g[i]:
            continue
        for j in range(n):
            if used_s[j]:
                continue
            if guess[i] == secret[j]:
                white += 1
                used_s[j] = True
                break
    red = max(0, n - green - white)
    return {"green": green, "white": white, "red": red, "exact": green == n}


def _ensure_flash_phase(sess: dict) -> None:
    """Advance show→input→result on poll when timers expire."""
    if sess.get("game_id") != "flash_memory" or sess.get("status") != "playing":
        return
    phase = sess.get("phase")
    started = float(sess.get("phase_started_at") or 0)
    now = _now()
    if phase == "show":
        show_s = float(sess.get("show_seconds") or 0.8)
        if now >= started + show_s:
            sess["phase"] = "input"
            sess["phase_started_at"] = now
            sess["answers"] = {}
    elif phase == "input":
        # 20s to answer; or all active members answered
        input_s = float(sess.get("input_seconds") or 20)
        joined = sess.get("joined") or {}
        answers = sess.get("answers") or {}
        active = [
            sid for sid, meta in joined.items()
            if (now - float((meta or {}).get("last_seen") or 0)) < 30
        ]
        if not active:
            active = list(joined.keys())
        all_in = active and all(s in answers for s in active)
        if all_in or now >= started + input_s:
            _resolve_flash_round(sess)
    elif phase == "result":
        result_s = float(sess.get("result_seconds") or 3)
        if now >= started + result_s:
            if sess.get("status") == "playing":
                _start_flash_round(sess, int(sess.get("round") or 1) + 1)


def _start_flash_round(sess: dict, round_num: int) -> None:
    total = int(sess.get("total_rounds") or 10)
    if round_num > total:
        sess["status"] = "won"
        sess["phase"] = "done"
        sess["code"] = None
        return
    length = _flash_code_length(round_num)
    # Flash duration 0.5–1.0s, shorter as rounds progress slightly
    show = max(0.5, min(1.0, 1.05 - round_num * 0.04))
    sess["round"] = round_num
    sess["phase"] = "show"
    sess["code"] = _gen_flash_code(length)
    sess["show_seconds"] = round(show, 2)
    sess["phase_started_at"] = _now()
    sess["answers"] = {}
    sess["last_round_result"] = None


def _resolve_flash_round(sess: dict) -> None:
    code = str(sess.get("code") or "").strip().upper()
    answers = sess.get("answers") or {}
    correct_ids = []
    for sid, ans in answers.items():
        if str(ans or "").strip().upper() == code:
            correct_ids.append(sid)
    min_ok = int(sess.get("min_correct") or 2)
    # If only 1 player in team, require that 1
    joined_n = max(1, len(sess.get("joined") or {}))
    need = min(min_ok, joined_n)
    ok = len(correct_ids) >= need
    sess["last_round_result"] = {
        "round": sess.get("round"),
        "code": code,
        "correct_count": len(correct_ids),
        "correct_ids": correct_ids,
        "need": need,
        "passed": ok,
        "answers": {k: str(v) for k, v in answers.items()},
    }
    log = list(sess.get("round_log") or [])
    log.append(sess["last_round_result"])
    sess["round_log"] = log[-12:]
    sess["phase"] = "result"
    sess["phase_started_at"] = _now()
    sess["code"] = None  # hide after resolve
    if not ok:
        sess["status"] = "lost"


def _new_session_blob(team_id: str, task_id: str, game_id: str, config: Optional[dict] = None) -> dict:
    cfg = dict(config or {})
    sess = {
        "key": _session_key(team_id, task_id),
        "team_id": team_id,
        "task_id": task_id,
        "game_id": game_id,
        "status": "lobby",
        "host": None,
        "joined": {},
        "expected": _team_member_ids(team_id),
        "created_at": _iso(),
        "config": cfg,
        "min_correct": int(cfg.get("minCorrect") or cfg.get("min_correct") or 2),
        "total_rounds": int(cfg.get("totalRounds") or cfg.get("total_rounds") or 10),
        "max_guesses": int(cfg.get("maxGuesses") or cfg.get("max_guesses") or 10),
        "code_length": int(cfg.get("codeLength") or cfg.get("code_length") or 4),
    }
    if game_id == "mastermind":
        sess["secret"] = _gen_mastermind_secret(sess["code_length"])
        sess["player_history"] = {}
    if game_id == "memory_match":
        # Wave time limits (seconds): round1, round2, round3
        waves = cfg.get("waveTimesSec") or cfg.get("wave_times_sec") or [60, 50, 45]
        try:
            sess["wave_times"] = [int(x) for x in waves][:3]
        except (TypeError, ValueError):
            sess["wave_times"] = [60, 50, 45]
        while len(sess["wave_times"]) < 3:
            sess["wave_times"].append(45)
        # Half of team (ceil) must fully clear all 3 waves
        sess["half_mode"] = True
        sess["phase"] = "lobby"
    return sess


def get_or_create_session(team_id: str, task_id: str, game_id: str, config: Optional[dict] = None) -> dict:
    team_id = normalize_team_id(team_id)
    key = _session_key(team_id, task_id)
    with _LOCK:
        data = _load()
        sess = data.get(key)
        if sess and sess.get("game_id") != game_id:
            sess = None
        if not sess:
            sess = _new_session_blob(team_id, task_id, game_id, config)
            data[key] = sess
            _save(data)
        return dict(sess)


def join_session(team_id: str, task_id: str, game_id: str, squad_id: str, config: Optional[dict] = None) -> dict:
    team_id = normalize_team_id(team_id)
    key = _session_key(team_id, task_id)
    names = _member_names(team_id)
    with _LOCK:
        data = _load()
        sess = data.get(key)
        # Fresh lobby after loss / wrong game. Keep "won" so submit_task can validate.
        recreate = (
            not sess
            or sess.get("game_id") != game_id
            or sess.get("status") == "lost"
            or ((config or {}).get("force_new") and sess.get("status") != "playing")
        )
        if recreate:
            sess = _new_session_blob(team_id, task_id, game_id, config)
            data[key] = sess

        joined = dict(sess.get("joined") or {})
        meta = dict(joined.get(squad_id) or {})
        meta["name"] = names.get(squad_id) or squad_id
        meta["last_seen"] = _now()
        # Preserve won/lost progress for mastermind mid-game
        joined[squad_id] = meta
        sess["joined"] = joined
        sess["expected"] = _team_member_ids(team_id)
        if not sess.get("host"):
            sess["host"] = squad_id
        sess["updated_at"] = _iso()
        if sess.get("game_id") == "flash_memory":
            _ensure_flash_phase(sess)
        data[key] = sess
        _save(data)
        return _public_status(sess, squad_id)


def start_session(team_id: str, task_id: str, squad_id: str) -> dict:
    team_id = normalize_team_id(team_id)
    key = _session_key(team_id, task_id)
    with _LOCK:
        data = _load()
        sess = data.get(key)
        if not sess:
            raise ValueError("找不到遊戲房間，請先加入")
        if sess.get("status") not in ("lobby", "lost"):
            return _public_status(sess, squad_id)
        joined = sess.get("joined") or {}
        if len(joined) < 1:
            raise ValueError("至少需要 1 名玩家加入")
        expected = list(sess.get("expected") or [])
        online = [
            sid for sid, meta in joined.items()
            if (_now() - float((meta or {}).get("last_seen") or 0)) < 25
        ]
        game_id = sess.get("game_id")

        if game_id == "memory_match":
            need_start = max(1, (len(expected) + 1) // 2) if expected else 1
            if len(online) < need_start:
                raise ValueError(
                    f"至少需要 {need_start} 名隊員同時進入再開始（半隊）"
                )
        else:
            # flash_memory / mastermind: full team must be online
            if expected:
                missing = [s for s in expected if s not in online]
                if missing:
                    names = _member_names(team_id)
                    label = "、".join(names.get(s, s) for s in missing[:5])
                    raise ValueError(f"請全隊都打開此任務再開始。尚未進入：{label}")
            elif len(online) < 1:
                raise ValueError("沒有在線隊員")

        sess["status"] = "playing"
        sess["started_at"] = _iso()
        if game_id == "flash_memory":
            _start_flash_round(sess, 1)
        elif game_id == "mastermind":
            sess["phase"] = "play"
            sess["secret"] = _gen_mastermind_secret(int(sess.get("code_length") or 4))
            sess["player_history"] = {}
            for sid in joined:
                joined[sid] = {**joined[sid], "won": False, "lost": False, "guesses": 0}
            sess["joined"] = joined
        elif game_id == "memory_match":
            sess["phase"] = "play"
            for sid in joined:
                joined[sid] = {
                    **joined[sid],
                    "won": False,
                    "lost": False,
                    "wave": 0,
                }
            sess["joined"] = joined
            sess["need_winners"] = _half_need(sess)
            sess["winners_count"] = 0
        data[key] = sess
        _save(data)
        return _public_status(sess, squad_id)


def poll_status(team_id: str, task_id: str, squad_id: str) -> dict:
    team_id = normalize_team_id(team_id)
    key = _session_key(team_id, task_id)
    with _LOCK:
        data = _load()
        sess = data.get(key)
        if not sess:
            return {"success": False, "error": "尚未建立遊戲", "status": None}
        # touch last_seen
        joined = dict(sess.get("joined") or {})
        if squad_id in joined:
            joined[squad_id] = {**joined[squad_id], "last_seen": _now()}
            sess["joined"] = joined
        if sess.get("game_id") == "flash_memory":
            _ensure_flash_phase(sess)
        data[key] = sess
        _save(data)
        return _public_status(sess, squad_id)


def submit_flash_answer(team_id: str, task_id: str, squad_id: str, answer: str) -> dict:
    team_id = normalize_team_id(team_id)
    key = _session_key(team_id, task_id)
    with _LOCK:
        data = _load()
        sess = data.get(key)
        if not sess or sess.get("game_id") != "flash_memory":
            raise ValueError("遊戲不存在")
        _ensure_flash_phase(sess)
        if sess.get("status") != "playing" or sess.get("phase") != "input":
            raise ValueError("現在不能提交答案")
        answers = dict(sess.get("answers") or {})
        answers[squad_id] = str(answer or "").strip().upper()
        sess["answers"] = answers
        # Early resolve if all online answered
        _ensure_flash_phase(sess)
        data[key] = sess
        _save(data)
        return _public_status(sess, squad_id)


def _half_need(sess: dict) -> int:
    expected = list(sess.get("expected") or [])
    n = len(expected) or len(sess.get("joined") or {}) or 1
    return max(1, (n + 1) // 2)  # ceil(n/2)


def report_memory_wave(
    team_id: str, task_id: str, squad_id: str, wave: int, success: bool,
) -> dict:
    """Player finished one memory-match wave (1–3). Success advances their wave count."""
    team_id = normalize_team_id(team_id)
    key = _session_key(team_id, task_id)
    with _LOCK:
        data = _load()
        sess = data.get(key)
        if not sess or sess.get("game_id") != "memory_match":
            raise ValueError("遊戲不存在")
        if sess.get("status") not in ("playing", "lobby"):
            if sess.get("status") == "won":
                return _public_status(sess, squad_id)
            raise ValueError("遊戲尚未開始或已結束")
        # Auto-start if still lobby (first report) — allow play without host button for small teams
        if sess.get("status") == "lobby":
            sess["status"] = "playing"
            sess["phase"] = "play"
            sess["started_at"] = _iso()

        joined = dict(sess.get("joined") or {})
        if squad_id not in joined:
            raise ValueError("請先加入遊戲")
        meta = dict(joined[squad_id])
        if meta.get("won"):
            return _public_status(sess, squad_id)

        try:
            w = int(wave)
        except (TypeError, ValueError):
            raise ValueError("無效波次")
        if w < 1 or w > 3:
            raise ValueError("波次必須是 1–3")

        cur = int(meta.get("wave") or 0)
        if success:
            # Must complete in order
            if w != cur + 1:
                raise ValueError(f"請先完成第 {cur + 1} 輪")
            meta["wave"] = w
            if w >= 3:
                meta["won"] = True
        else:
            # Failed a wave — stay on same wave for retry (no team fail)
            meta["last_fail_wave"] = w

        joined[squad_id] = meta
        sess["joined"] = joined

        need = _half_need(sess)
        winners = sum(1 for s, m in joined.items() if (m or {}).get("won"))
        sess["winners_count"] = winners
        sess["need_winners"] = need
        if winners >= need:
            sess["status"] = "won"
            sess["phase"] = "done"

        data[key] = sess
        _save(data)
        return _public_status(sess, squad_id)


def submit_mastermind_guess(
    team_id: str, task_id: str, squad_id: str, guess: List[str],
) -> dict:
    team_id = normalize_team_id(team_id)
    key = _session_key(team_id, task_id)
    with _LOCK:
        data = _load()
        sess = data.get(key)
        if not sess or sess.get("game_id") != "mastermind":
            raise ValueError("遊戲不存在")
        if sess.get("status") != "playing":
            raise ValueError("遊戲尚未開始或已結束")
        joined = dict(sess.get("joined") or {})
        if squad_id not in joined:
            raise ValueError("請先加入遊戲")
        meta = dict(joined[squad_id])
        if meta.get("won"):
            raise ValueError("你已破解密碼")
        if meta.get("lost"):
            raise ValueError("你已用盡次數")
        secret = list(sess.get("secret") or [])
        g = [str(x).upper() for x in (guess or [])]
        if len(g) != len(secret):
            raise ValueError(f"請輸入 {len(secret)} 個顏色")
        score = score_mastermind(secret, g)
        history = list((sess.get("player_history") or {}).get(squad_id) or [])
        history.append({"guess": g, **score})
        ph = dict(sess.get("player_history") or {})
        ph[squad_id] = history
        sess["player_history"] = ph
        guesses = len(history)
        meta["guesses"] = guesses
        max_g = int(sess.get("max_guesses") or 10)
        if score.get("exact"):
            meta["won"] = True
        elif guesses >= max_g:
            meta["lost"] = True
        joined[squad_id] = meta
        sess["joined"] = joined

        # Team outcome: all joined must win; any lost → team lost when all done
        members = list(joined.keys())
        if members and all((joined[s] or {}).get("won") for s in members):
            sess["status"] = "won"
            sess["phase"] = "done"
        elif members and any((joined[s] or {}).get("lost") for s in members):
            # Wait until all finished or one lost ends team? User: all must finish in 10.
            # If anyone fails, team fails.
            sess["status"] = "lost"
            sess["phase"] = "done"

        data[key] = sess
        _save(data)
        pub = _public_status(sess, squad_id)
        pub["last_score"] = score
        pub["my_history"] = history
        return pub


def reset_session(team_id: str, task_id: str, game_id: str, config: Optional[dict] = None) -> dict:
    team_id = normalize_team_id(team_id)
    key = _session_key(team_id, task_id)
    with _LOCK:
        data = _load()
        if key in data:
            del data[key]
            _save(data)
    return get_or_create_session(team_id, task_id, game_id, {**(config or {}), "force_new": True})


def is_session_won(team_id: str, task_id: str) -> bool:
    team_id = normalize_team_id(team_id)
    key = _session_key(team_id, task_id)
    with _LOCK:
        sess = _load().get(key) or {}
        return sess.get("status") == "won"


def _public_status(sess: dict, squad_id: str) -> dict:
    names = _member_names(sess.get("team_id") or "")
    joined_pub = _public_joined(sess, names)
    expected = sess.get("expected") or []
    online_ids = {r["squad_id"] for r in joined_pub if r.get("online")}
    phase = sess.get("phase")
    show_code = None
    show_remaining = None
    if sess.get("game_id") == "flash_memory" and sess.get("status") == "playing":
        if phase == "show" and sess.get("code"):
            show_code = sess.get("code")
            started = float(sess.get("phase_started_at") or 0)
            show_s = float(sess.get("show_seconds") or 0.8)
            show_remaining = max(0, round(started + show_s - _now(), 2))
        input_remaining = None
        if phase == "input":
            started = float(sess.get("phase_started_at") or 0)
            input_s = float(sess.get("input_seconds") or 20)
            input_remaining = max(0, round(started + input_s - _now(), 2))
    else:
        input_remaining = None

    my = (sess.get("joined") or {}).get(squad_id) or {}
    my_history = []
    if sess.get("game_id") == "mastermind":
        my_history = list((sess.get("player_history") or {}).get(squad_id) or [])

    need_winners = int(sess.get("need_winners") or _half_need(sess))
    winners_count = int(sess.get("winners_count") or sum(
        1 for r in joined_pub if r.get("won")
    ))

    return {
        "success": True,
        "task_id": sess.get("task_id"),
        "game_id": sess.get("game_id"),
        "status": sess.get("status"),
        "phase": phase,
        "host": sess.get("host"),
        "is_host": sess.get("host") == squad_id,
        "round": sess.get("round"),
        "total_rounds": sess.get("total_rounds") or 10,
        "min_correct": sess.get("min_correct") or 2,
        "max_guesses": sess.get("max_guesses") or 10,
        "code_length": sess.get("code_length") or 4,
        "show_code": show_code,
        "show_remaining": show_remaining,
        "input_remaining": input_remaining if sess.get("game_id") == "flash_memory" else None,
        "last_round_result": sess.get("last_round_result"),
        "members": joined_pub,
        "expected_count": len(expected) or len(joined_pub),
        "joined_count": len(sess.get("joined") or {}),
        "online_count": len(online_ids),
        "all_online": bool(expected) and all(s in online_ids for s in expected),
        "my_squad_id": squad_id,
        "my_won": bool(my.get("won")),
        "my_lost": bool(my.get("lost")),
        "my_guesses": int(my.get("guesses") or 0),
        "my_wave": int(my.get("wave") or 0),
        "my_history": my_history,
        "my_answered": squad_id in (sess.get("answers") or {}),
        "can_submit_task": sess.get("status") == "won",
        "colors": MASTERMIND_COLORS if sess.get("game_id") == "mastermind" else None,
        "wave_times": sess.get("wave_times") or [60, 50, 45],
        "need_winners": need_winners,
        "winners_count": winners_count,
    }
