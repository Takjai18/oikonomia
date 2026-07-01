"""
Oikonomia — Trauma & Narrative Fragment Orchestration Service
Phase 1.5 Step 2: Pure Service Layer Implementation
"""
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from models.protagonist import TRAUMA_BAD_ENDING_LIMIT
from models.settings import settings
from utils.db_tx import immediate_transaction, with_db_retry

VALID_PROTAGONIST_KEYS = frozenset({"iggy", "marah"})


@dataclass
class TraumaStatusSnapshot:
    team_id: str
    protagonist_key: str
    current_trauma: int
    trauma_band: str  # 'low' | 'medium' | 'high'
    narrative_fragment: str
    is_bad_ending_locked: bool


CONDITIONAL_NARRATIVE_FRAGMENTS = {
    "low": (
        "「我的恩典夠你用的。」在微小的動搖中，心理界線的裂縫正透出微光。"
        "創傷尚未生根，重建的根基依然穩固。"
    ),
    "medium": (
        "「因為我的能力是在人的軟弱上顯得完全。」防線雖有破損，痛楚正逼使全隊面對真實的自我，"
        "這是一場恩典的試煉。"
    ),
    "high": (
        "「所以我更喜歡誇自己的軟弱，好叫基督的能力覆庇我。」創傷已達臨界點。"
        "雖然陰影籠罩，但破碎的盡頭並非毀滅，而是神聖醫治的開端。"
    ),
}


def resolve_trauma_band(trauma_count: int) -> str:
    """權威創傷能帶分級"""
    if trauma_count <= 1:
        return "low"
    if trauma_count <= 3:
        return "medium"
    return "high"


def _tx_body(conn, clean_team: str, protagonist_key: str, delta: int, reason: str, now: str):
    row = conn.execute(
        "SELECT trauma_count FROM protagonist_states WHERE team_id = ? AND protagonist = ?",
        (clean_team, protagonist_key),
    ).fetchone()
    if not row:
        raise ValueError(f"Protagonist state missing: {clean_team}/{protagonist_key}")

    current_trauma = int(row[0] or 0)
    new_trauma = max(0, current_trauma + int(delta))

    updated = conn.execute(
        """UPDATE protagonist_states
           SET trauma_count = ?, last_updated = ?
           WHERE team_id = ? AND protagonist = ?""",
        (new_trauma, now, clean_team, protagonist_key),
    )
    if updated.rowcount != 1:
        raise RuntimeError(f"Failed to update trauma for {clean_team}/{protagonist_key}")

    conn.execute(
        """INSERT INTO protagonist_trauma_log
           (team_id, protagonist, delta, reason, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (clean_team, protagonist_key, int(delta), reason, now),
    )

    total_row = conn.execute(
        "SELECT COALESCE(SUM(trauma_count), 0) FROM protagonist_states WHERE team_id = ?",
        (clean_team,),
    ).fetchone()
    total_trauma = int(total_row[0] or 0)

    is_bad_ending = total_trauma > TRAUMA_BAD_ENDING_LIMIT
    if is_bad_ending:
        conn.execute(
            """UPDATE teams
               SET ending_type = 'bad_ending', ending_locked_at = ?
               WHERE team_id = ? AND COALESCE(ending_type, '') != 'bad_ending'""",
            (now, clean_team),
        )

    band = resolve_trauma_band(new_trauma)
    fragment = CONDITIONAL_NARRATIVE_FRAGMENTS[band]

    return TraumaStatusSnapshot(
        team_id=clean_team,
        protagonist_key=protagonist_key,
        current_trauma=new_trauma,
        trauma_band=band,
        narrative_fragment=fragment,
        is_bad_ending_locked=is_bad_ending,
    )


def apply_protagonist_trauma_pipeline(
    team_id: str,
    protagonist_key: str,
    delta: int,
    reason: str,
) -> TraumaStatusSnapshot:
    """
    權威創傷管線：在單一原子事務內更新創傷、寫入審計日誌、並計算當前神學劇情片段。
    防禦鎖定：一旦觸發 bad_ending 條件，立即寫入 SSOT 狀態防線。
    """
    clean_team = (team_id or "").strip().upper()
    if protagonist_key not in VALID_PROTAGONIST_KEYS:
        raise ValueError(f"Invalid protagonist key: {protagonist_key}")
    if not clean_team:
        raise ValueError("team_id is required")

    now = datetime.now().isoformat()
    db_path = settings.db_path

    def _run():
        with immediate_transaction(db_path) as conn:
            return _tx_body(conn, clean_team, protagonist_key, delta, reason, now)

    return with_db_retry(_run)