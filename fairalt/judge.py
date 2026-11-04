"""Step 3: red / orange / green."""
import json
import re

from ai_client import ask, load_prompt
from questions import options_text

STATUSES = ("GREEN", "ORANGE", "RED", "INVALID")


def normalise(text):
    text = str(text).lower().replace("–", "-").replace("—", "-")
    text = re.sub(r"[^\w\s.-]", " ", text)
    return re.sub(r"\s+", " ", text).strip(" .")


def answer_token(q):
    """The text to look for in the description.

    For multiple choice that is the option's wording ("Positive"), not the
    letter, since a bare letter would match almost any sentence.
    """
    answer = str(q["answer"]).strip()
    if q.get("answer_type") == "choice" and q.get("options"):
        for opt in q["options"]:
            m = re.match(r"^\s*([A-Za-z0-9]+)[).:]\s*(.+)$", opt)
            if m and m.group(1).lower() == answer.lower():
                return m.group(2)
        return None
    return answer


def answer_in_text(q, alt_text):
    """Code check: does the correct answer appear word-for-word in the alt text?"""
    token = answer_token(q)
    if not token or len(normalise(token)) < 1:
        return False
    # Whole words only, and "2" must not match inside "2.5" or "12".
    pattern = r"(?<![\w.])" + re.escape(normalise(token)) + r"(?!\w|\.\d)"
    return re.search(pattern, normalise(alt_text)) is not None


def judge(q, alt_text, a, runs, b_correct):
    """The AI judge: a colour plus a quote from the description as proof.

    runs are Student B's tries; b_correct is how many the code marked right.
    """
    found = answer_in_text(q, alt_text)
    prompt = load_prompt(
        "4_judge",
        question=q["question"],
        options_if_any=options_text(q),
        correct_answer=str(q["answer"]),
        answer_type=q.get("answer_type", "short text"),
        alt_text=alt_text,
        student_a_json=json.dumps(a, ensure_ascii=False),
        student_b_json=json.dumps(runs, ensure_ascii=False),
        runs=str(len(runs)),
        b_correct=str(b_correct),
        answer_found_in_text="yes" if found else "no",
    )
    verdict = ask(prompt, temperature=0.0)
    status = str(verdict.get("status", "")).upper().strip()
    # A model sometimes echoes "GREEN | ORANGE"; take the first valid word.
    verdict["status"] = next((s for s in STATUSES if s in status.split() or s == status), "INVALID")
    verdict["answer_found_in_text"] = found
    return verdict
