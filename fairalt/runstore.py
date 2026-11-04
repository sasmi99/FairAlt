"""The saved run: its file, its questions, and what happens to a question after it is checked.

No Streamlit in here, so the pipeline, the app and the tests all share it.
"""
import json
from datetime import datetime
from pathlib import Path

import ai_client

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"

FAIR, NEEDS_HUMAN = "GREEN", "NEEDS_HUMAN"
QUESTION_FIELDS = ("id", "subject", "type", "question", "image", "answer", "answer_type", "options", "source")

# The gate every question moves through: (key, label, icon)
GATES = [("waiting", "Waiting", "hourglass_empty"), ("tested", "Tested", "science"),
         ("review", "Needs review", "flag"), ("approved", "Approved", "how_to_reg"),
         ("published", "Published", "verified")]


# ---------- the run file ----------

def results_files():
    return sorted(RESULTS.glob("run_*.json"), reverse=True)


def run_label(path, seconds=False):
    try:
        return datetime.strptime(Path(path).stem[4:], "%Y%m%d_%H%M%S").strftime(
            "%d %b %Y, %H:%M:%S" if seconds else "%d %b %Y, %H:%M")
    except ValueError:
        return Path(path).stem


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(results, path=None):
    RESULTS.mkdir(exist_ok=True)
    path = Path(path) if path else RESULTS / f"run_{results['run_id']}.json"
    path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def new_run(items, **fields):
    """A results dict for these items. fields (duration, usage, ...) go between the header and the items."""
    now = datetime.now()
    return {"run_id": now.strftime("%Y%m%d_%H%M%S"), "created_at": now.isoformat(timespec="seconds"),
            "provider": ai_client.provider(), "model": ai_client.model_name(), **fields, "items": items}


# ---------- one question ----------

def new_review():
    return {"approved": False, "approved_by": None, "approved_at": None, "edited_alt_text": None}


def new_item(q):
    """A question that has not been checked yet."""
    item = {k: q.get(k) for k in QUESTION_FIELDS}
    item.update(final_status=None, attempts=[], review=new_review())
    return item


def blank_run(questions):
    """A run with every question unchecked, for checking questions one at a time."""
    return new_run([new_item(q) for q in questions], usage={}, duration_s=0)


def final_text(item):
    return item["review"].get("edited_alt_text") or item.get("final_alt_text") or ""


def stage(item):
    """Where a question is in the gate: waiting, tested, review, approved or published."""
    r = item["review"]
    if r.get("published"):
        return "published"
    if r["approved"]:
        return "approved"
    if item.get("final_status") == NEEDS_HUMAN:
        return "review"
    return "tested" if item.get("final_status") else "waiting"


def approve(item, reviewer, text, seconds=None):
    """A reviewer approves the description, with their edits if they changed it."""
    text = text.strip()
    item["review"] = {"approved": True, "approved_by": reviewer.strip(),
                      "approved_at": datetime.now().isoformat(timespec="seconds"),
                      "edited_alt_text": text if text != item.get("final_alt_text", "") else None,
                      "seconds": seconds}


def unapprove(item):
    item["review"] = new_review()


def publish(item, run_id):
    """The last gate: an approved question gets its Fairness Report ID and is ready to use."""
    item["review"].update(published=True, published_at=datetime.now().isoformat(timespec="seconds"),
                          report_id=f"FA-{run_id}-{item['id'].upper()}")


# ---------- a whole run ----------

def checked(results):
    """The questions checked so far, and their summary (None when there are none)."""
    done = [it for it in results["items"] if it.get("final_status")]
    return (summary({"items": done}) if done else None), done


def summary(results):
    items = results["items"]
    plain = [(it.get("plain") or {}).get("verdict", {}).get("status") for it in items]
    return {
        "total": len(items),
        "plain_unfair": sum(s in ("RED", "ORANGE") for s in plain),
        "plain_red": plain.count("RED"),
        "plain_orange": plain.count("ORANGE"),
        "fair_green": sum(it["final_status"] == FAIR for it in items),
        "fair_first_try": sum(it["final_status"] == FAIR and len(it.get("attempts", [])) == 1 for it in items),
        "needs_human": sum(it["final_status"] == NEEDS_HUMAN for it in items),
        "approved": sum(it["review"]["approved"] for it in items),
    }
