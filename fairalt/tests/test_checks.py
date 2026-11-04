"""The code checks: answers, banned words, missing facts, quotes, and the decision."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["AI_PROVIDER"] = "mock"

import checks
from questions import load_questions

Q = {q["id"]: q for q in load_questions()}


def test_answers_match_by_type():
    assert checks.answers_match(Q["q01"], "2")
    assert checks.answers_match(Q["q01"], "The slope is 2.0")
    assert not checks.answers_match(Q["q01"], "2.5")
    assert not checks.answers_match(Q["q01"], "CANNOT_ANSWER")
    assert checks.answers_match(Q["q14"], "South-east")
    assert checks.answers_match(Q["q12"], "20–29 age group")
    assert checks.answers_match(Q["q03"], "B) It increased every year")
    assert not checks.answers_match(Q["q03"], "C")


def test_banned_words_by_question_type():
    assert checks.banned_words(Q["q02"], "April has the highest bar") == ["highest"]     # Charts
    assert checks.banned_words(Q["q14"], "The river flows south-east") == ["south-east"]  # Maps
    assert checks.banned_words(Q["q01"], "A line rises from left to right") == []        # Graphs
    assert checks.banned_words(Q["q02"], "Mostly cloudy") == []                           # whole words only


def test_missing_facts_compares_numbers():
    used = ["point (0, 1)", "point (3, 7)", "the slope is 2"]
    assert checks.missing_facts(Q["q01"], "Points (0, 1) and (3, 7) are marked.", used) == []
    assert checks.missing_facts(Q["q01"], "Point (0, 1) is marked.", used) == ["point (3, 7)"]
    assert checks.missing_facts(Q["q03"], "1,200 students", ["2015: 1200"]) == ["2015: 1200"]  # 2015 missing


def test_verify_quote():
    text = "A line graph with a slope of 2 through (0, 1)."
    assert checks.verify_quote(text, "with a slope of 2")
    assert checks.verify_quote(text, "line graph ... slope of 2")
    assert not checks.verify_quote(text, "a gradient of 2")
    assert not checks.verify_quote(text, "")


def test_filter_facts_removes_what_gives_the_answer_away():
    facts = [{"fact": "Point (3, 7) is marked", "source": "drawn"},
             {"fact": "The slope is 2", "source": "inferred"},
             {"fact": "April has the highest rainfall", "source": "drawn"}]
    kept, removed = checks.filter_facts(Q["q02"], facts)
    assert [f["fact"] for f in kept] == ["Point (3, 7) is marked"]
    assert [r["why"] for r in removed] == ["worked out, not visible in the image", 'uses "highest"']
    # The answer printed in the image stays: the sighted student sees it too.
    kept, _ = checks.filter_facts(Q["q04"], [{"fact": "Housing 35%", "source": "printed"}])
    assert kept


def _code(**over):
    base = {"a_correct": True, "b_correct": 3, "runs": 3, "consistent": True, "answer_found": False,
            "answer_innocent": False, "banned": [], "missing": []}
    return {**base, **over}


def test_decide_code_and_judge():
    q, text = Q["q01"], "A line through (0, 1) and (3, 7) with a slope of 2."
    green = {"status": "GREEN", "reason": "", "quote": ""}
    assert checks.decide(q, text, _code(), green)["status"] == "GREEN"
    # Code decides banned words and missing facts, whatever the judge says.
    v = checks.decide(q, text, _code(banned=["slope of"]), green)
    assert v["status"] == "RED" and "slope of" in v["problems"][0] and v["checks"]["no_banned"] is False
    assert checks.decide(q, text, _code(missing=["point (3, 7)"]), green)["status"] == "ORANGE"
    # A leak needs a real quote; a made-up quote sends it to a human.
    assert checks.decide(q, text, _code(), {"status": "RED", "quote": "slope of 2"})["status"] == "RED"
    assert checks.decide(q, text, _code(), {"status": "RED", "quote": "gradient is two"})["status"] == "UNSURE"
    # Uncertain results go to a human.
    assert checks.decide(q, text, _code(b_correct=2), green)["status"] == "UNSURE"
    assert checks.decide(q, text, _code(answer_found=True), green)["status"] == "UNSURE"
    assert checks.decide(q, text, _code(answer_found=True, answer_innocent=True), green)["status"] == "GREEN"
    # The standard AI baseline trusts the judge on these.
    assert checks.decide(q, text, _code(answer_found=True), green, strict=False)["status"] == "GREEN"
    # Student A wrong: the question cannot be checked.
    assert checks.decide(q, text, _code(a_correct=False), None)["status"] == "INVALID"
