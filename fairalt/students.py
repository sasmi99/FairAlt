"""Step 2: Student A (sees the image) and Student B (hears only the description)."""
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import ai_client
from ai_client import ask, load_prompt
from questions import image_path, options_text

_cache = {}
_cache_lock = threading.Lock()


def student_a(q):
    """Answer with the real image. Cached per question, since the image never changes."""
    key = (q["id"], q["image"], q["question"])
    with _cache_lock:
        if key in _cache:
            return _cache[key]
    prompt = load_prompt("2_student_a", question=q["question"], options_if_any=options_text(q))
    result = ask(prompt, image_path(q), temperature=0.0)
    with _cache_lock:
        _cache[key] = result
    return result


def student_b(q, alt_text):
    """Answer from the description only; no image is sent.

    STUDENT_B_MODEL in .env can set a smaller model, which makes the test
    stricter: a weaker student needs everything spelled out.
    """
    prompt = load_prompt(
        "3_student_b",
        alt_text=alt_text,
        question=q["question"],
        options_if_any=options_text(q),
    )
    return ask(prompt, temperature=0.7, model=os.getenv("STUDENT_B_MODEL") or None)


def student_b_tries():
    return max(1, int(os.getenv("STUDENT_B_RUNS", "3")))


def student_b_runs(q, alt_text, n=None):
    """Student B answers n separate times (in parallel) for a confidence score."""
    counter = ai_client.current_tracking()

    def one(_):
        ai_client.use_tracking(counter)  # count these calls towards this question
        return student_b(q, alt_text)

    n = n or student_b_tries()
    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(one, range(n)))

