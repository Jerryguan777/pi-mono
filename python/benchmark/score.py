"""GAIA benchmark scoring — compare model answers to expected answers."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def normalize_answer(answer: str) -> str:
    """Normalize an answer for comparison."""
    answer = answer.strip()
    # Remove trailing punctuation
    answer = answer.rstrip(".")
    # Lowercase
    answer = answer.lower()
    # Normalize whitespace
    answer = re.sub(r"\s+", " ", answer)
    return answer


def answers_match(expected: str, actual: str) -> bool:
    """Check if two answers match (case-insensitive, whitespace-normalized)."""
    norm_expected = normalize_answer(expected)
    norm_actual = normalize_answer(actual)

    # Exact match after normalization
    if norm_expected == norm_actual:
        return True

    # Try numeric comparison
    try:
        exp_num = float(norm_expected.replace(",", ""))
        act_num = float(norm_actual.replace(",", ""))
        if abs(exp_num - act_num) < 1e-6:
            return True
    except (ValueError, TypeError):
        pass

    # Check if expected is contained in actual (for longer-form answers)
    if norm_expected in norm_actual:
        return True

    return False


def score_results(results_file: str) -> dict:
    """Score results from a JSONL file."""
    results = []
    with open(results_file, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))

    total = len(results)
    correct = 0
    errors = 0
    timeouts = 0
    incorrect = []

    for r in results:
        status = r.get("status", "")
        expected = r.get("expected_answer", "")
        actual = r.get("model_answer", "")

        if status == "error":
            errors += 1
            continue
        if status == "timeout":
            timeouts += 1
            continue

        if answers_match(expected, actual):
            correct += 1
        else:
            incorrect.append({
                "task_id": r.get("task_id", ""),
                "expected": expected,
                "actual": actual,
            })

    accuracy = correct / total if total > 0 else 0

    return {
        "total": total,
        "correct": correct,
        "incorrect": len(incorrect),
        "errors": errors,
        "timeouts": timeouts,
        "accuracy": accuracy,
        "incorrect_details": incorrect,
    }


def main() -> None:
    """Score results and print summary."""
    from benchmark.config import RESULTS_FILE

    results_file = sys.argv[1] if len(sys.argv) > 1 else RESULTS_FILE

    if not Path(results_file).exists():
        print(f"Results file not found: {results_file}")
        sys.exit(1)

    scores = score_results(results_file)

    print(f"\n{'='*50}")
    print(f"GAIA Benchmark Results")
    print(f"{'='*50}")
    print(f"Total tasks:    {scores['total']}")
    print(f"Correct:        {scores['correct']}")
    print(f"Incorrect:      {scores['incorrect']}")
    print(f"Errors:         {scores['errors']}")
    print(f"Timeouts:       {scores['timeouts']}")
    print(f"Accuracy:       {scores['accuracy']:.1%}")
    print(f"{'='*50}")

    if scores["incorrect_details"]:
        print(f"\nIncorrect answers:")
        for item in scores["incorrect_details"]:
            print(f"  Task {item['task_id'][:8]}...")
            print(f"    Expected: {item['expected']}")
            print(f"    Got:      {item['actual']}")


if __name__ == "__main__":
    main()
