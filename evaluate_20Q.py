#!/usr/bin/env python3
"""
evaluate_20Q.py

Run an automated 20 Questions evaluation using:
  - your guesser (LLM) from llm_20_questions.py
  - the TA-provided ValidatorModel from test.py (simulates the answerer)

Usage:
  python evaluate_20Q.py -N 100
"""

import argparse
import sys
from types import SimpleNamespace

# --- Import the validator (provided by TAs) ---
from test import ValidatorModel  # noqa: F401

# --- Import the LLM guesser agent ---
# Try the expected module name first; fall back to the driver file if needed.
from llm_20_questions import guesser_agent  # noqa: F401

ASK = "ask"
GUESS = "guess"


def _normalize_answer(ans):
    """
    Convert various possible ValidatorModel answer shapes into 'yes'/'no'/'maybe'.
    Supports bools, strings, and dicts with common keys.
    """
    if isinstance(ans, bool):
        return "yes" if ans else "no"

    if isinstance(ans, str):
        s = ans.strip().lower()
        if s in ("yes", "y", "true", "1"):
            return "yes"
        if s in ("no", "n", "false", "0"):
            return "no"
        if s in ("maybe", "unsure", "unknown", "not sure", "idk"):
            return "maybe"
        # Default fallback if string is unexpected
        return "maybe"

    if isinstance(ans, dict):
        for key in ("answer", "response", "label", "result", "status"):
            if key in ans:
                return _normalize_answer(ans[key])

    return "maybe"


def _parse_guess_result(res):
    """
    Convert various possible ValidatorModel guess-result shapes into a boolean (correct/incorrect).
    Accepts bools, strings, or dicts with common keys.
    """
    if isinstance(res, bool):
        return res

    if isinstance(res, str):
        s = res.strip().lower()
        return s in ("yes", "correct", "true", "right", "1", "match")

    if isinstance(res, dict):
        for key in ("correct", "is_correct", "match", "result"):
            if key in res:
                return bool(res[key])

    return False


def _maybe_get_target_word(vm):
    """
    If the ValidatorModel exposes the target word, try to fetch it for logging.
    This is optional and best-effort only.
    """
    for attr in ("target", "word", "answer", "label", "solution", "keyword", "gold", "ground_truth"):
        if hasattr(vm, attr):
            try:
                return getattr(vm, attr)
            except Exception:
                pass
    # Some validators expose a method
    for meth in ("get_target", "get_word", "get_answer"):
        if hasattr(vm, meth):
            try:
                return getattr(vm, meth)()
            except Exception:
                pass
    return None


def run_single_game(max_rounds=20):
    """
    Runs one full 20Q game (up to max_rounds) using:
      - guesser_agent() to generate questions/guesses
      - ValidatorModel to answer questions and validate guesses

    Returns:
      won (bool), final_guess (str), rounds_used (int), maybe_target (str|None)
    """
    # New random target each game (as per the TA-provided class behavior)
    validator = ValidatorModel()

    target = _maybe_get_target_word(validator)  # Optional, for logging

    questions = []
    answers = []
    guesses = []
    past_guesses_norm = set()

    def _norm(s: str) -> str:
        return s.casefold().strip()

    for qnum in range(1, max_rounds + 1):
        # --- ASK turn ---
        obs = SimpleNamespace(
            turnType=ASK,
            questions=questions,
            answers=answers,
            question_guesses=guesses,
            answer_guesses_list=answers,
        )
        question = (guesser_agent(obs) or "").strip()
        if not question:
            # If the LLM failed to ask something, treat as 'maybe' to keep going.
            question = "Is it related to a well-known person?"
        questions.append(question)

        # Validate question via the validator
        raw_ans = validator.validate_question(question)
        ans = _normalize_answer(raw_ans)
        answers.append(ans)

        # --- GUESS turn ---
        obs = SimpleNamespace(
            turnType=GUESS,
            questions=questions,
            answers=answers,
            question_guesses=guesses,
            answer_guesses_list=answers,
        )

        # Try to avoid duplicate guesses
        tries = 0
        guess = (guesser_agent(obs) or "").strip()
        if not guess:
            guess = "unknown"
        while _norm(guess) in past_guesses_norm and tries < 5:
            # Ask the LLM again for a new guess
            guess = (guesser_agent(obs) or "").strip() or "unknown"
            tries += 1

        past_guesses_norm.add(_norm(guess))
        guesses.append(guess)

        # Check guess via the validator
        raw_guess_res = validator.validate_guess(guess)
        correct = _parse_guess_result(raw_guess_res)
        if correct:
            return True, guess, qnum, target

    # If we get here, we didn't guess within max_rounds; report the last guess
    final_guess = guesses[-1] if guesses else ""
    return False, final_guess, max_rounds, target


def main():
    parser = argparse.ArgumentParser(description="Evaluate 20 Questions with a ValidatorModel.")
    parser.add_argument("-N", "--num", type=int, default=1, help="Number of games to play.")
    parser.add_argument("--max_rounds", type=int, default=20, help="Max Q/A rounds per game (default: 20).")
    args = parser.parse_args()

    total = args.num
    wins = 0
    results = []

    for i in range(1, total + 1):
        won, final_guess, rounds_used, target = run_single_game(max_rounds=args.max_rounds)
        wins += int(won)
        target_str = f" | target='{target}'" if target else ""
        status = "WIN" if won else "LOSS"
        print(f"[Game {i:03d}] {status} in {rounds_used} rounds | final_guess='{final_guess}'{target_str}")
        results.append((won, final_guess, rounds_used, target))

    print("\n" + "=" * 60)
    print(f"Summary: {wins}/{total} wins ({wins/total:.1%})")
    print("=" * 60)


if __name__ == "__main__":
    main()
