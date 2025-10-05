#!/usr/bin/env python3
# selftest_evaluate_20Q.py
"""
Self-test harness for evaluate_20Q.py when you have NO TA file.

What it does:
  1) Injects a fake 'test' module with a stub ValidatorModel so
     'from test import ValidatorModel' in evaluate_20Q.py succeeds.
  2) Imports evaluate_20Q and monkey-patches its guesser_agent with a
     deterministic one (asks "Is it an animal?" then guesses "lion").
  3) Runs evaluate_20Q.main() with -N games and checks the output format.

Usage:
  python selftest_evaluate_20Q.py -N 5 --max_rounds 5
"""

import argparse
import io
import re
import sys
import types
from contextlib import redirect_stdout
from importlib import import_module

def main():
    parser = argparse.ArgumentParser(description="Self-test for evaluate_20Q.py (no TA file needed).")
    parser.add_argument("-N", "--num", type=int, default=3, help="Number of games to run.")
    parser.add_argument("--max_rounds", type=int, default=5, help="Max Q+G rounds per game.")
    args = parser.parse_args()

    # ---- 1) Inject a fake 'test' module with ValidatorModel ----
    fake_test = types.ModuleType("test")

    class ValidatorModel:  # deterministic stub
        def __init__(self):
            self.target = "lion"

        def validate_question(self, q: str):
            ql = (q or "").lower()
            if "animal" in ql:
                return "yes"
            return "maybe"

        def validate_guess(self, g: str):
            return (g or "").strip().lower() == self.target

    fake_test.ValidatorModel = ValidatorModel
    sys.modules["test"] = fake_test

    # ---- 2) Import evaluate_20Q and patch its guesser_agent ----
    try:
        eval20q = import_module("evaluate_20Q")
    except ModuleNotFoundError:
        print("[ERROR] Couldn't import evaluate_20Q.py. Put this self-test in the same folder.", file=sys.stderr)
        sys.exit(1)

    def fake_guesser_agent(obs):
        tt = getattr(obs, "turnType", "").lower()
        if tt == "ask":
            return "Is it an animal?"
        return "lion"

    # Always patch to be deterministic (and offline-safe)
    eval20q.guesser_agent = fake_guesser_agent  # type: ignore[attr-defined]

    # ---- 3) Run evaluate_20Q.main() as if via CLI and capture stdout ----
    old_argv = sys.argv[:]
    sys.argv = ["evaluate_20Q.py", "-N", str(args.num), "--max_rounds", str(args.max_rounds)]

    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            eval20q.main()
    finally:
        sys.argv = old_argv

    output = buf.getvalue()
    print(output)  # show it so you can eyeball

    # ---- Validate output format (per-game lines + summary) ----
    # e.g. [Game 001] WIN in 1 rounds | final_guess='lion' | target='...'
    game_line_re = re.compile(
        r"^\[Game\s+\d{3}\]\s+(WIN|LOSS)\s+in\s+(\d+)\s+rounds\s+\|\s+final_guess='([^']*)'",
        re.IGNORECASE | re.MULTILINE,
    )
    games = game_line_re.findall(output)
    if len(games) != args.num:
        print(f"[FAIL] Expected {args.num} game lines, found {len(games)}.", file=sys.stderr)
        sys.exit(2)

    wins_in_lines = sum(1 for status, _, _ in games if status.upper() == "WIN")

    # e.g. Summary: 3/5 wins (60.0%)
    summary_re = re.compile(r"Summary:\s+(\d+)\s*/\s*(\d+)\s+wins\s*\(([\d.]+)%\)", re.IGNORECASE)
    sm = summary_re.search(output)
    if not sm:
        print("[FAIL] Summary line not found or malformed.", file=sys.stderr)
        sys.exit(3)

    summary_wins = int(sm.group(1))
    summary_total = int(sm.group(2))
    if summary_total != args.num:
        print(f"[FAIL] Summary total ({summary_total}) != requested N ({args.num}).", file=sys.stderr)
        sys.exit(4)
    if summary_wins != wins_in_lines:
        print(f"[FAIL] Summary wins ({summary_wins}) != counted wins in lines ({wins_in_lines}).", file=sys.stderr)
        sys.exit(5)

    print("[PASS] evaluate_20Q.py runs and the output format & summary look correct (with stubbed validator/guesser).")

if __name__ == "__main__":
    main()
