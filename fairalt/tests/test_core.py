"""Tests for the parts that do not need a real AI model.

Run: python -m pytest -q
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["AI_PROVIDER"] = "mock"
os.environ["MOCK_DELAY"] = "0"

import pytest

import pipeline
import runstore
from ai_client import load_prompt, parse_json
from judge import answer_in_text
from questions import image_path, load_questions

Q = {q["id"]: q for q in load_questions()}


@pytest.mark.parametrize("qid, text, expected", [
    ("q01", "A line with a slope of 2", True),
    ("q01", "A line through the points (0, 1) and (3, 7)", False),   # no bare "2"
    ("q01", "y ranges from -1 to 9, slope 2.", True),
    ("q01", "a value of 2.5 is marked", False),                       # 2.5 is not 2
    ("q13", "A triangle with angles of 50°, 60° and 70°.", True),
    ("q12", "The female bar for 20–29 is the longest", True),         # en dash
    ("q14", "the river flows Southeast to the lake", True),
    ("q11", "Scatter plot showing a strong positive correlation", True),  # choice -> option wording
    ("q06", "Label A points to a circle", False),                     # bare letters are never checked
    ("q04", "Housing 35%, Food 20%", True),                           # innocent match; the judge decides
])
def test_answer_in_text(qid, text, expected):
    assert answer_in_text(Q[qid], text) is expected


def test_parse_json_handles_fences_and_prose():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Here you go: {"a": {"b": 2}} thanks') == {"a": {"b": 2}}
    with pytest.raises(json.JSONDecodeError):
        parse_json("no json here")


def test_load_prompt_fills_placeholders_but_keeps_json_braces():
    text = load_prompt("3_student_b", alt_text="ALT", question="QUESTION?", options_if_any="")
    assert "Image description: ALT" in text and "Question: QUESTION?" in text
    assert '"answer": "... or CANNOT_ANSWER"' in text
    assert "{alt_text}" not in text


def test_questions_have_images_and_required_fields():
    assert len(Q) == 15
    for q in Q.values():
        assert image_path(q).exists(), q["id"]
        for field in ("id", "question", "image", "answer", "answer_type", "source"):
            assert q.get(field), (q["id"], field)
        if q["answer_type"] == "choice":
            assert q.get("options"), q["id"]


def test_mock_pipeline_end_to_end(tmp_path):
    results = pipeline.run(workers=4)
    s = runstore.summary(results)
    assert s["total"] == 15
    assert s["fair_green"] + s["needs_human"] == 15
    by_id = {it["id"]: it for it in results["items"]}
    assert [it["id"] for it in results["items"]] == sorted(by_id)   # original order kept
    assert len(by_id["q10"]["attempts"]) == 3 and by_id["q10"]["final_status"] == "GREEN"
    assert by_id["q12"]["final_status"] == "NEEDS_HUMAN"
    assert by_id["q04"]["attempts"][0]["verdict"]["answer_found_in_text"] is True
    path = runstore.save(results, tmp_path / "run.json")
    assert json.loads(path.read_text())["items"][0]["review"]["approved"] is False
