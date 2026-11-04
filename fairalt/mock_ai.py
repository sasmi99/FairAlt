"""Offline stand-in for the AI model (AI_PROVIDER=mock).

Returns scripted replies so the pipeline and dashboard can be built and
tested without an API key. The script covers every path: leaks, missing
info, fixes that take 1-3 tries, an innocent number match, and one question
that still needs a human. Numbers from a mock run are NOT real results.
"""
import json
import os
import re
import time
from pathlib import Path

from questions import load_questions

LEAK, MISSING, FAIR = "leak", "missing", "fair"

# Per question: the plain alt text, then the fair writer's draft and each
# fixer rewrite in order. "note" is the leak evidence or the missing detail.
SCRIPT = {
    "q01": {
        "plain": ("A line graph showing a straight line with a slope of 2 passing through the points (0, 1) and (3, 7) on a grid.", LEAK, "with a slope of 2"),
        "drafts": [
            ("Coordinate grid with x from -1 to 5 and y from -1 to 9. A straight line rises from left to right. Two points on the line are marked and labeled: (0, 1) and (3, 7).", FAIR, ""),
        ],
    },
    "q02": {
        "plain": ("Bar chart of monthly rainfall in Riverton from January to June, with April having the highest rainfall at 94 mm.", LEAK, "April having the highest rainfall"),
        "drafts": [
            ("Bar chart titled Monthly Rainfall in Riverton. The vertical axis shows rainfall in millimetres from 0 to 100. There are six bars, one per month, January to June.", MISSING, "the height or value of each bar"),
            ("Bar chart titled Monthly Rainfall in Riverton, showing rainfall in millimetres for six months. Each bar has its value printed above it: January 62, February 48, March 71, April 94, May 83, June 55.", FAIR, ""),
        ],
    },
    "q03": {
        "plain": ("Line graph showing Lakeside College enrollment steadily increasing from 1200 students in 2015 to 1520 in 2020.", LEAK, "steadily increasing"),
        "drafts": [
            ("Line graph titled Lakeside College Enrollment. Horizontal axis: Year, 2015 to 2020. Vertical axis: Students, 1100 to 1600. Six points joined by a line, each labeled: 2015, 1200; 2016, 1260; 2017, 1310; 2018, 1395; 2019, 1440; 2020, 1520.", FAIR, ""),
        ],
    },
    "q04": {
        "plain": ("Pie chart of a monthly household budget divided into housing, food, transport, savings and other categories.", MISSING, "the percentage of each slice"),
        "drafts": [
            ("Pie chart titled Monthly Household Budget with five labeled slices: Housing 35%, Food 20%, Transport 15%, Savings 10%, Other 20%.", FAIR, ""),
        ],
    },
    "q05": {
        "plain": ("Histogram of exam scores for Class 9B, showing that most students scored between 70 and 79, with 10 students scoring 80 or above.", LEAK, "10 students scoring 80 or above"),
        "drafts": [
            ("Histogram titled Exam Scores, Class 9B. Four bars for score ranges 60-69, 70-79, 80-89 and 90-100. A total of 10 students scored in the top two ranges.", LEAK, "A total of 10 students scored in the top two ranges"),
            ("Histogram titled Exam Scores, Class 9B. The vertical axis shows number of students from 0 to 10 with gridlines. Four touching bars: 60-69 reaches 4, 70-79 reaches 9, 80-89 reaches 7, 90-100 reaches 3.", FAIR, ""),
        ],
    },
    "q06": {
        "plain": ("Diagram of an animal cell with labeled parts A, B, C and D, showing the nucleus, cell membrane, mitochondria and a vacuole.", MISSING, "which letter points to which structure"),
        "drafts": [
            ("Labeled diagram of an animal cell. A large oval outline forms the cell boundary; label B points to this outline. Inside, near the centre, is a large purple circle with a smaller dark dot at its centre; label A points to it. Two small red oval shapes sit in the lower part; label C points to one. A pale blue circle in the upper right is labeled D.", FAIR, ""),
        ],
    },
    "q07": {
        "plain": ("A simple series circuit with a 12 volt battery and two resistors of 2 ohms and 4 ohms.", FAIR, ""),
        "drafts": [
            ("Circuit diagram showing a single loop. On the left side is a battery labeled 12 V. Along the top wire are two resistors in a row, labeled 2 Ω and 4 Ω. There are no branches.", FAIR, ""),
        ],
    },
    "q08": {
        "plain": ("Diagram of a box with two opposing forces of 10 N and 4 N, resulting in a net force of 6 N to the right.", LEAK, "a net force of 6 N to the right"),
        "drafts": [
            ("A box on a frictionless floor, shown from the side. Two arrows act on it along the same horizontal line: an arrow pointing right labeled 10 N, and an arrow pointing left labeled 4 N.", FAIR, ""),
        ],
    },
    "q09": {
        "plain": ("Ray diagram of a converging lens with an object placed in front of it.", MISSING, "the object distance and focal length"),
        "drafts": [
            ("Diagram of a converging lens on a horizontal axis, with focal points marked F on each side. An upright arrow labeled Object stands to the left of the lens.", MISSING, "the labeled distances: object to lens, and focal length"),
            ("Diagram of a converging lens on a horizontal axis, with focal points marked F on each side. An upright arrow labeled Object stands to the left of the lens. The distance from the object to the lens is labeled 30 cm. The distance from the lens to the focal point on the right is labeled f = 10 cm.", FAIR, ""),
        ],
    },
    "q10": {
        "plain": ("Supply and demand graph for notebooks showing the market reaches equilibrium where the supply and demand curves cross at a price of $6.", LEAK, "cross at a price of $6"),
        "drafts": [
            ("Supply and demand graph titled Market for Notebooks. Price in dollars, 0 to 10, on the vertical axis; quantity in thousands of units, 0 to 80, on the horizontal axis. A downward-sloping line labeled D and an upward-sloping line labeled S cross each other.", MISSING, "where each line starts and ends"),
            ("Supply and demand graph titled Market for Notebooks. Price in dollars, 0 to 10, on the vertical axis; quantity in thousands of units, 0 to 80, on the horizontal axis. Line D runs from a price of 10 at quantity 0 down to 2 at quantity 80. Line S runs from a price of 2 at quantity 0 up to 10 at quantity 80. The lines meet at the equilibrium price of 6 dollars.", LEAK, "meet at the equilibrium price of 6 dollars"),
            ("Supply and demand graph titled Market for Notebooks. Price in dollars, 0 to 10, on the vertical axis; quantity in thousands of units, 0 to 80, on the horizontal axis, with gridlines every 1 dollar and every 10 thousand units. Line D runs from (0, $10) down to (80, $2). Line S runs from (0, $2) up to (80, $10).", FAIR, ""),
        ],
    },
    "q11": {
        "plain": ("Scatter plot showing a strong positive correlation between hours studied and test scores.", LEAK, "a strong positive correlation"),
        "drafts": [
            ("Scatter plot titled Study Time and Test Scores. Horizontal axis: hours studied, 1 to 9. Vertical axis: test score, about 50 to 90. Twelve points: (1, 52), (2, 55), (2, 60), (3, 61), (4, 66), (4, 63), (5, 70), (6, 72), (6, 76), (7, 78), (8, 83), (9, 88).", FAIR, ""),
        ],
    },
    "q12": {
        "plain": ("Population pyramid of Country X showing male and female population by age group.", MISSING, "the percentage for each bar"),
        "drafts": [
            ("Population pyramid titled Population Pyramid, Country X. Seven age groups from 0-9 at the bottom to 60+ at the top. Blue bars to the left show males, pink bars to the right show females.", MISSING, "the female percentage for each age group"),
            ("Population pyramid titled Population Pyramid, Country X. Seven age groups from 0-9 at the bottom to 60+ at the top. Blue bars to the left show males, pink bars to the right show females. The female bars are longest around the young adult age groups and shortest at the top.", MISSING, "exact female values; 'young adult' could be 20-29 or 30-39"),
            ("Population pyramid titled Population Pyramid, Country X. Seven age groups from 0-9 at the bottom to 60+ at the top. Blue bars to the left show males, pink bars to the right show females. The female bar for 20-29, at 7.2%, is the longest of all.", LEAK, "The female bar for 20-29 ... is the longest of all"),
        ],
    },
    "q13": {
        "plain": ("A triangle with angles of 50°, 60° and 70°.", LEAK, "70°"),
        "drafts": [
            ("Triangle, with a note that it is not drawn to scale. The bottom-left angle is labeled 50°, the bottom-right angle is labeled 60°, and the top angle is labeled x.", FAIR, ""),
        ],
    },
    "q14": {
        "plain": ("A map of a river valley with the Silver River flowing southeast from the Granite Mountains to Lake Mira.", LEAK, "flowing southeast"),
        "drafts": [
            ("Map titled Map of the Silver River valley, with an arrow labeled N pointing to the top of the page. The Granite Mountains are in the top-left corner, and the river's source is labeled just below them. The Silver River winds from there to Lake Mira in the bottom-right corner, which is labeled as the river's mouth.", FAIR, ""),
        ],
    },
    "q15": {
        "plain": ("A timeline of the history of Millbrook with four events.", MISSING, "the names and years of the events"),
        "drafts": [
            ("Timeline titled History of Millbrook, running left to right. Four events are marked with their years: Town founded, 1820; School built, 1838; Railway arrives, 1855; Bridge opens, 1871.", FAIR, ""),
        ],
    },
}

_by_text = {}
_by_question = {}
_by_image = {}


def _index():
    if _by_text:
        return
    for q in load_questions():
        _by_question[q["question"]] = q
        _by_image[Path(q["image"]).name] = q
        s = SCRIPT.get(q["id"])
        if not s:
            continue
        _by_text[s["plain"][0]] = (q, s["plain"], None)
        for i, d in enumerate(s["drafts"]):
            _by_text[d[0]] = (q, d, i)


def _line(prompt, label):
    m = re.search(rf"^{re.escape(label)}\s*(.*)$", prompt, flags=re.MULTILINE)
    return m.group(1).strip() if m else ""


def _question(prompt=None, image_path=None):
    _index()
    if image_path:
        q = _by_image.get(Path(image_path).name)
    else:
        q = _by_question.get(_line(prompt, "Question:"))
    if not q or q["id"] not in SCRIPT:
        raise ValueError("Mock provider has no script for this question. Use a real AI_PROVIDER.")
    return q


def _entry(alt_text):
    _index()
    hit = _by_text.get(alt_text.strip())
    if not hit:
        raise ValueError("Mock provider does not recognise this description (was it edited?).")
    return hit


def _student_b(prompt):
    q, (text, outcome, note), _ = _entry(_line(prompt, "Image description:"))
    if outcome == MISSING:
        return {"answer": "CANNOT_ANSWER", "reasoning": "The description does not give the details I need.",
                "answer_given_in_description": False, "missing": note}
    if outcome == LEAK:
        return {"answer": q["answer"], "reasoning": "The description says it directly, so no working was needed.",
                "answer_given_in_description": True, "missing": ""}
    return {"answer": q["answer"], "reasoning": "I worked it out from the values and labels in the description.",
            "answer_given_in_description": False, "missing": ""}


def _sentences(text):
    return [p.strip() for p in re.split(r"(?<=[.;])\s+(?=[A-Z])", text) if p.strip()]


def _facts(q):
    """The facts in the question's drafts, one per sentence. Sentences from
    leaking drafts are marked inferred, so the code check removes them."""
    facts, seen = [], set()
    for text, outcome, _ in SCRIPT[q["id"]]["drafts"]:
        for f in _sentences(text):
            if f not in seen:
                seen.add(f)
                facts.append({"fact": f, "source": "inferred" if outcome == LEAK else "printed"})
    return facts


def _facts_used(q):
    """Student A's facts: the sentences with values in the first fair draft."""
    fair = next((d[0] for d in SCRIPT[q["id"]]["drafts"] if d[1] == FAIR), "")
    return [f for f in _sentences(fair) if re.search(r"\d", f)]


def _judge(prompt):
    q, (text, outcome, note), _ = _entry(_line(prompt, "Image description:"))
    found = "answer text found in description: yes" in prompt
    if outcome == LEAK:
        return {"status": "RED", "reason": "The description states the conclusion the question asks for.",
                "quote": note, "evidence": note, "fix_hint": "Remove the conclusion; keep the raw values and labels."}
    if outcome == MISSING:
        return {"status": "ORANGE", "reason": "Student A answered correctly, but Student B could not.",
                "evidence": note, "fix_hint": f"Add {note}."}
    reason = "Both students reached the correct answer by reasoning from the details."
    if found:
        reason += " The answer text appears only as a printed label the sighted student also sees, so it is not a leak."
    return {"status": "GREEN", "reason": reason, "quote": "", "evidence": "", "fix_hint": ""}


def _fixer(prompt):
    q, _, i = _entry(_line(prompt, "Current description:"))
    drafts = SCRIPT[q["id"]]["drafts"]
    nxt = drafts[min((i or 0) + 1, len(drafts) - 1)]
    changed = "Removed the stated conclusion." if _line(prompt, "Problem found:").startswith("RED") \
        else "Added the missing visible details."
    return {"alt_text": nxt[0], "what_changed": changed}


def respond(prompt, image_path=None):
    time.sleep(float(os.getenv("MOCK_DELAY", "0.05")))
    head = prompt.lstrip()[:60]
    if head.startswith("Write a description of this image"):
        return {"alt_text": SCRIPT[_question(image_path=image_path)["id"]]["plain"][0]}
    if head.startswith("You list the facts"):
        return {"facts": _facts(_question(image_path=image_path))}
    if head.startswith("You write alt text"):
        q = _question(prompt)
        return {"alt_text": SCRIPT[q["id"]]["drafts"][0][0], "details_included": [],
                "left_for_student": "the reasoning the question asks for"}
    if head.startswith("You are a student"):
        q = _question(prompt)
        return {"answer": q["answer"], "reasoning": "Read the values from the image and worked it out.",
                "facts_used": _facts_used(q)}
    if head.startswith("You are a blind student"):
        return _student_b(prompt)
    if head.startswith("You check whether"):
        return _judge(prompt)
    if head.startswith("You improve alt text"):
        return _fixer(prompt)
    raise ValueError("Mock provider does not recognise this prompt.")


def dump(path):
    """Debug helper: write the script out as JSON."""
    Path(path).write_text(json.dumps(SCRIPT, indent=2, ensure_ascii=False))
