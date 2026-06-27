#!/usr/bin/env python3
"""Quick combat resolve smoke test — imports from app.py (not a separate module)."""
import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

from app import resolve_player_phase, get_combat, DB_PATH

COMBAT_ID = int(os.environ.get("COMBAT_ID", "1"))

print("=== 開始測試戰鬥 ===")
print(f"DB: {DB_PATH}")
print(f"Combat ID: {COMBAT_ID}")

combat_before = get_combat(COMBAT_ID)
if not combat_before:
    print(f"ERROR: combat {COMBAT_ID} not found")
    sys.exit(1)

print(f"戰鬥前 Enemy HP: {combat_before['enemy_hp']}")
print(f"當前狀態: {combat_before['status']}")
print(f"Phase Actions: {combat_before['phase_actions']}")

combat_after, winner = resolve_player_phase(COMBAT_ID)

print("\n=== 解析結果 ===")
print(f"winner: {winner}")
print(f"status: {combat_after.get('status') if combat_after else None}")
print(f"enemy_hp: {combat_after.get('enemy_hp') if combat_after else None}")

combat_final = get_combat(COMBAT_ID)
print(f"\n戰鬥後 Enemy HP: {combat_final['enemy_hp']}")
print(f"新狀態: {combat_final['status']}")
print("Logs:")
for log in combat_final.get("logs") or []:
    msg = log.get("message") if isinstance(log, dict) else str(log)
    print(" -", msg)