"""Code checks: the simple, exact decisions, so the AI only judges what code cannot.

- answers_match: is a student's answer right?
- banned_words: words that give the answer away for this type of question
- missing_facts: did the description include the values Student A used?
- verify_quote: is the judge's proof really in the description?
- filter_facts: drop listed facts that would give the answer away
- decide: combine the code checks and the judge into one status
"""
import json
import re
from pathlib import Path

from judge import answer_in_text, answer_token, normalise
from runstore import FAIR

BANNED_FILE = Path(__file__).resolve().parent / "data" / "banned_words.json"
UNSURE = "UNSURE"


def _squash(text):
    return re.sub(r"[\s\-]", "", normalise(text))


def answers_match(q, given):
    """True when a student's answer is the correct one (code, not AI)."""
    given = str(given or "").strip()
    if not given or given.upper().startswith("CANNOT_ANSWER"):
        return False
    answer = str(q["answer"]).strip()
    kind = q.get("answer_type")
    if kind == "number":
        nums = re.findall(r"-?\d+(?:\.\d+)?", given.replace(",", ""))
        try:
            return bool(nums) and abs(float(nums[0]) - float(answer)) < 1e-6
        except ValueError:
            return False
    if kind == "choice":
        if re.match(rf"^\(?{re.escape(answer)}\b", given, flags=re.IGNORECASE):
            return True
        option = answer_token(q)
        return bool(option) and _squash(option) in _squash(given)
    return _squash(answer) in _squash(given) or _squash(given) == _squash(answer)


def same_answers(answers):
    return len({_squash(a) for a in answers}) == 1


def _banned_lists():
    return json.loads(BANNED_FILE.read_text(encoding="utf-8"))


def banned_words(q, text):
    """Banned words for this question type (and for all types) found in the text."""
    lists = _banned_lists()
    words = lists.get("All", []) + lists.get(q.get("type", ""), []) + q.get("banned", [])
    norm = " " + normalise(text) + " "
    return [w for w in words if re.search(r"(?<!\w)" + re.escape(normalise(w)) + r"(?!\w)", norm)]


def _numbers(text):
    return set(re.findall(r"\d+(?:\.\d+)?", re.sub(r"(?<=\d),(?=\d{3})", "", str(text))))


def missing_facts(q, text, facts_used):
    """Facts Student A read from the image whose values are not in the description.

    Only numbers are compared (exact and reliable). Facts that contain the
    answer itself are skipped: the description must not include those.
    """
    have = _numbers(text)
    missing = []
    for fact in facts_used or []:
        if answer_in_text(q, fact):
            continue
        need = _numbers(fact)
        if need and not need <= have:
            missing.append(fact)
    return missing


def verify_quote(text, quote):
    """True when every part of the judge's quote appears in the description."""
    parts = [p.strip(" .\"'") for p in re.split(r"\.\.\.|…", quote or "")]
    parts = [p for p in parts if len(p) >= 2]
    return bool(parts) and all(normalise(p) in normalise(text) for p in parts)


def filter_facts(q, facts):
    """Split listed facts into kept and removed (with the reason).

    Removed: facts the lister marked as worked out rather than seen, facts
    with a banned word, and facts containing the answer unless that text is
    printed in the image (then the sighted student sees it too).
    """
    kept, removed = [], []
    for f in facts or []:
        text = str(f.get("fact", "")).strip() if isinstance(f, dict) else str(f).strip()
        source = (f.get("source") if isinstance(f, dict) else "") or "drawn"
        if not text:
            continue
        if source == "inferred":
            removed.append({"fact": text, "why": "worked out, not visible in the image"})
        elif banned_words(q, text):
            removed.append({"fact": text, "why": f'uses "{banned_words(q, text)[0]}"'})
        elif answer_in_text(q, text) and source != "printed":
            removed.append({"fact": text, "why": "contains the answer"})
        else:
            kept.append({"fact": text, "source": source})
    return kept, removed


def code_checks(q, text, a, runs, facts=None):
    """Everything code can decide about one description."""
    b_right = [answers_match(q, r.get("answer")) for r in runs]
    found = answer_in_text(q, text)
    # An answer match is innocent when the same text is printed in the image.
    innocent = found and any(f.get("source") == "printed" and answer_in_text(q, f["fact"]) for f in facts or [])
    return {
        "a_correct": answers_match(q, (a or {}).get("answer")),
        "b_correct": sum(b_right),
        "runs": len(runs),
        "consistent": same_answers([r.get("answer") for r in runs]),
        "answer_found": found,
        "answer_innocent": innocent,
        "banned": banned_words(q, text),
        "missing": missing_facts(q, text, (a or {}).get("facts_used")),
    }


def decide(q, text, code, verdict, strict=True):
    """Combine code checks and the judge's verdict into the final verdict.

    Code decides: wrong answers, banned words, missing facts. The judge
    decides leaks and missing information that code cannot see, and must
    quote the description as proof. strict=False (the standard AI baseline)
    trusts the judge where FairAlt would send the description to a human.
    """
    judge_status = verdict.get("status") if verdict else None
    quote = (verdict or {}).get("quote") or (verdict or {}).get("evidence") or ""
    quote_ok = verify_quote(text, quote) if quote else False
    k, n = code["b_correct"], code["runs"]
    problems, unsure, status = [], [], None

    if not code["a_correct"]:
        status = "INVALID"
        problems.append(f"The student who saw the image got it wrong (correct answer: {q['answer']}).")
    else:
        for w in code["banned"]:
            problems.append(f'Uses "{w}", which gives the answer away for {q.get("type", "this type of")} questions.')
            status = "RED"
        if judge_status == "RED":
            if quote_ok or not strict:
                problems.append(f'Gives the answer away: "{quote}".' if quote else "Gives the answer away.")
                status = "RED"
            else:
                unsure.append("The judge called it a leak, but its quote is not in the description.")
        for fact in code["missing"]:
            problems.append(f"Missing a fact the student needs: {fact}.")
            status = status or "ORANGE"
        if judge_status == "ORANGE":
            problems.append(f"Missing: {verdict.get('evidence') or verdict.get('reason', '')}")
            status = status or "ORANGE"
        if k == 0 and not status:
            problems.append("Student B could not reach the answer from the description.")
            status = "ORANGE"
        if not status:
            if strict and code["answer_found"] and not code["answer_innocent"] and judge_status != "RED":
                unsure.append("The answer appears word for word; the judge says it is not a leak.")
            if 0 < k < n:
                unsure.append(f"Student B was right {k} of {n} times.")
            if judge_status == "INVALID":
                unsure.append("The judge thinks the image-seeing student was wrong; the code check disagrees.")
            status = UNSURE if unsure and strict else FAIR

    leak = judge_status == "RED" and (quote_ok or not strict)
    checks = {
        "students_correct": code["a_correct"] and k == n,
        "no_answer": None if (unsure and code["answer_found"] and not code["answer_innocent"]) else not leak,
        "no_banned": not code["banned"],
        "no_missing": not code["missing"] and judge_status != "ORANGE" and k > 0,
        "consistent": code["consistent"] and k in (0, n),
    }
    return {
        **(verdict or {}),
        "status": status,
        "judge_status": judge_status,
        "evidence": quote,
        "quote_ok": quote_ok,
        "problems": problems,
        "unsure": unsure,
        "checks": checks,
        "b_correct": k,
        "runs": n,
        "banned": code["banned"],
        "missing": code["missing"],
        "answer_found_in_text": code["answer_found"],
    }
