"""Runs every question through the checks and saves the run.

Flow for one question: list the facts in the image -> code removes facts
that give the answer away -> write the description from what is left ->
code checks + Student A and Student B (3 tries) -> judge with a quote as
proof -> fix with the exact problems (up to 3 versions) -> anything
uncertain goes to a human.

Usage:
  python pipeline.py                     # all questions
  python pipeline.py --only q01,q04      # a few questions
  python pipeline.py --workers 1         # one question at a time
"""
import argparse
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import ai_client
import checks
import runstore
from fixer import fix
from judge import judge
from questions import QUESTIONS_FILE, load_questions
from runstore import FAIR, NEEDS_HUMAN
from students import student_a, student_b_runs, student_b_tries
from writer import list_facts, write_fair, write_plain

MAX_ATTEMPTS = 3


def test_description(q, alt, a, facts=None, strict=True, step=None, label="the description"):
    """Student B's tries, the code checks and the judge for one description."""
    step = step or (lambda msg: None)
    step(f"Student B is answering from {label} ({student_b_tries()} tries)")
    runs = student_b_runs(q, alt)
    code = checks.code_checks(q, alt, a, runs, facts)
    if code["a_correct"]:
        step(f"The judge is checking {label}")
        verdict = judge(q, alt, a, runs, code["b_correct"])
    else:
        verdict = None  # code already knows the question cannot be checked
    return runs, checks.decide(q, alt, code, verdict, strict)


def write_and_fix(q, a, facts, max_attempts, step):
    """FairAlt's description, tested and rewritten until it is fair (up to max_attempts versions).

    Returns the writer's draft and the history of versions tried.
    """
    draft = write_fair(q, facts)
    alt, what_changed, history = draft["alt_text"], None, []
    for attempt in range(1, max_attempts + 1):
        runs, verdict = test_description(q, alt, a, facts, step=step, label=f"version {attempt}")
        history.append({"attempt": attempt, "alt_text": alt, "student_b": runs[0], "student_b_runs": runs,
                        "verdict": verdict, "what_changed": what_changed})
        if verdict["status"] in (FAIR, "INVALID", checks.UNSURE) or attempt == max_attempts:
            break
        step(f"Version {attempt} was not fair, so it is being rewritten")
        fixed = fix(q, alt, verdict, history, facts)
        alt, what_changed = fixed["alt_text"], fixed.get("what_changed")
    return draft, history


def final_decision(history):
    """The question's final status and, when a person must look, the reason."""
    last = history[-1]["verdict"]
    if last["status"] == FAIR:
        return FAIR, None
    if last["status"] == "INVALID":
        return NEEDS_HUMAN, " ".join(last["problems"])
    if last["status"] == checks.UNSURE:
        return NEEDS_HUMAN, "Not sure: " + " ".join(last["unsure"])
    return NEEDS_HUMAN, f"Still not fair after {len(history)} versions: " + " ".join(last["problems"])


def process_question(q, max_attempts=MAX_ATTEMPTS, on_step=None):
    """Check one question. on_step(message) is called before each AI step."""
    step = on_step or (lambda msg: None)
    ai_client.start_tracking()
    started = time.time()
    item = runstore.new_item(q)
    try:
        step("Student A is answering from the image")
        a = student_a(q)
        item["student_a"] = a

        # BEFORE: standard AI alt text, put through the same test
        step("Standard AI is writing a description")
        plain = write_plain(q)
        runs, verdict = test_description(q, plain, a, strict=False, step=step, label="the standard description")
        item["plain"] = {"alt_text": plain, "student_b": runs[0], "student_b_runs": runs, "verdict": verdict}

        # AFTER: FairAlt, built from facts
        step("FairAlt is listing the facts in the image")
        kept, removed = checks.filter_facts(q, list_facts(q))
        item["facts"] = {"kept": kept, "removed": removed}
        step("FairAlt is writing a description from the remaining facts")
        draft, history = write_and_fix(q, a, kept, max_attempts, step)
        item["writer_notes"] = {k: draft.get(k) for k in ("details_included", "left_for_student")}
        item["attempts"] = history
        item["final_alt_text"] = history[-1]["alt_text"]
        item["final_status"], item["needs_human_reason"] = final_decision(history)
    except Exception as e:  # keep the run going; a human looks at this one
        item["final_status"] = NEEDS_HUMAN
        item["needs_human_reason"] = f"Error during check: {e}"
        item["error"] = traceback.format_exc()
    item["seconds"] = round(time.time() - started, 1)  # AI time for this question
    item["usage"] = ai_client.tracked_usage()
    return item


def run(questions=None, workers=4, progress=None, max_attempts=MAX_ATTEMPTS):
    """Run all questions and return the results dict.

    progress(done, total, item) is called after each question finishes.
    """
    questions = questions if questions is not None else load_questions()
    ai_client.reset_usage()
    started = time.time()
    order = {q["id"]: i for i, q in enumerate(questions)}
    items = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(process_question, q, max_attempts) for q in questions]
        for fut in as_completed(futures):
            item = fut.result()
            items.append(item)
            if progress:
                progress(len(items), len(questions), item)
    items.sort(key=lambda it: order[it["id"]])

    return runstore.new_run(
        items,
        questions_file=str(QUESTIONS_FILE.relative_to(runstore.ROOT)),
        max_attempts=max_attempts,
        workers=max(1, workers),
        duration_s=round(time.time() - started, 1),
        usage=ai_client.usage_summary(),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="comma-separated question ids")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--attempts", type=int, default=MAX_ATTEMPTS)
    args = parser.parse_args()

    questions = load_questions()
    if args.only:
        wanted = set(args.only.split(","))
        questions = [q for q in questions if q["id"] in wanted]

    print(f"Provider: {ai_client.provider()}  Model: {ai_client.model_name()}  Questions: {len(questions)}")

    def show(done, total, it):
        plain = it.get("plain", {}).get("verdict", {}).get("status", "-")
        tries = len(it.get("attempts", []))
        print(f"[{done:>2}/{total}] {it['id']}  plain: {plain:<7} final: {it['final_status']:<11} tries: {tries}"
              + (f"  ({it['needs_human_reason']})" if it.get("needs_human_reason") else ""))

    results = run(questions, workers=args.workers, progress=show, max_attempts=args.attempts)
    path = runstore.save(results)
    s = runstore.summary(results)
    u = results["usage"]
    print(f"\nPlain AI unfair: {s['plain_unfair']}/{s['total']}  "
          f"(leak {s['plain_red']}, missing {s['plain_orange']})")
    print(f"FairAlt: {s['fair_green']}/{s['total']} fair "
          f"({s['fair_first_try']} first try), {s['needs_human']} need a human")
    print(f"AI calls: {u['calls']}  tokens in/out: {u['prompt_tokens']}/{u['completion_tokens']}"
          + (f"  est. cost ${u['est_cost_usd']}" if u["est_cost_usd"] else ""))
    print(f"Took {results['duration_s']}s. Saved to {path.relative_to(runstore.ROOT)}")


if __name__ == "__main__":
    main()
