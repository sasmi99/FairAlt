"""Loading the question set and small helpers shared by the steps."""
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
QUESTIONS_FILE = DATA / "questions.json"


def load_questions(path=QUESTIONS_FILE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def by_id():
    """The bundled questions keyed by id."""
    return {q["id"]: q for q in load_questions()}


def image_path(q):
    return DATA / q["image"]


def options_text(q):
    """The options block for multiple-choice prompts, or an empty string."""
    if not q.get("options"):
        return ""
    return "Options:\n" + "\n".join(q["options"])
