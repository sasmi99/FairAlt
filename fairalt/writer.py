"""Step 1: write the description."""
from ai_client import ask, load_prompt
from questions import image_path, options_text


def write_plain(q):
    """The 'before': a standard AI description. It gets the same picture and
    question as FairAlt, with a plain instruction and no fairness rules."""
    prompt = load_prompt("0_plain_writer", question=q["question"], options_if_any=options_text(q))
    return ask(prompt, image_path(q), temperature=0.0)["alt_text"]


def list_facts(q):
    """List the facts in the image, each marked printed, drawn or inferred."""
    prompt = load_prompt("1a_list_facts", question=q["question"])
    return ask(prompt, image_path(q), temperature=0.0).get("facts", [])


def facts_text(facts):
    return "\n".join(f"- {f['fact']}" for f in facts) or "- (none)"


def write_fair(q, facts):
    """The 'after': alt text built only from the kept facts. The image is not
    sent, so the writer cannot add back what code removed.

    Returns the full JSON (alt_text, details_included, left_for_student).
    """
    prompt = load_prompt("1_fair_writer", question=q["question"], facts=facts_text(facts))
    return ask(prompt, temperature=0.2)
