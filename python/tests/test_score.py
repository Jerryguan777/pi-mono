"""Tests for benchmark scoring."""

import json
import os
import tempfile

from benchmark.score import answers_match, normalize_answer, score_results


def test_normalize_answer():
    assert normalize_answer("  Hello World.  ") == "hello world"
    assert normalize_answer("42") == "42"
    assert normalize_answer("  multiple   spaces  ") == "multiple spaces"


def test_answers_match_exact():
    assert answers_match("hello", "hello")
    assert answers_match("Hello", "hello")
    assert answers_match("  hello  ", "hello")


def test_answers_match_numeric():
    assert answers_match("42", "42")
    assert answers_match("42.0", "42")
    assert answers_match("1,000", "1000")


def test_answers_match_contained():
    assert answers_match("42", "The answer is 42")
    assert answers_match("paris", "The capital is Paris")


def test_answers_no_match():
    assert not answers_match("hello", "world")
    assert not answers_match("42", "43")


def test_score_results():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps({"task_id": "1", "expected_answer": "42", "model_answer": "42", "status": "success"}) + "\n")
        f.write(json.dumps({"task_id": "2", "expected_answer": "hello", "model_answer": "world", "status": "success"}) + "\n")
        f.write(json.dumps({"task_id": "3", "expected_answer": "test", "model_answer": "", "status": "error"}) + "\n")
        f.write(json.dumps({"task_id": "4", "expected_answer": "test", "model_answer": "", "status": "timeout"}) + "\n")
        tmp_path = f.name

    try:
        scores = score_results(tmp_path)
        assert scores["total"] == 4
        assert scores["correct"] == 1
        assert scores["incorrect"] == 1
        assert scores["errors"] == 1
        assert scores["timeouts"] == 1
        assert scores["accuracy"] == 0.25
    finally:
        os.unlink(tmp_path)
