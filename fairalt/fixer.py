"""Step 4: rewrite an unfair description."""
from ai_client import ask, load_prompt
from writer import facts_text


def fix(q, alt_text, verdict, history, facts=None):
    """Return {"alt_text", "what_changed"} for the next attempt.

    history is the list of earlier attempts (dicts with alt_text and verdict).
    """
    previous = [
        f'- "{h["alt_text"]}" ({h["verdict"]["status"]}: {h["verdict"].get("reason", "")})'
        for h in history
    ]
    prompt = load_prompt(
        "5_fixer",
        question=q["question"],
        alt_text=alt_text,
        status=verdict["status"],
        reason=verdict.get("reason", ""),
        problems="\n".join(f"- {p}" for p in verdict.get("problems") or []) or "- see the reason above",
        fix_hint=verdict.get("fix_hint", ""),
        facts=facts_text(facts or []),
        previous_attempts="\n".join(previous) if previous else "none",
    )
    return ask(prompt, temperature=0.4)
