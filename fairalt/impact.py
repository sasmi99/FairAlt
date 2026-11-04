"""Business numbers for the dashboard: leaks, time, cost and scale-up.

Measured numbers come from a run's results; the by-hand time and staff cost
are slider inputs on the dashboard.
"""

# Starting values for the dashboard sliders
MANUAL_MINUTES = 15      # minutes for a trained person to write and check one test-image description
HOURLY_COST = 30         # staff cost in US dollars per hour (15 min x $30/h = $7.50 per image)
DEFAULT_WORKERS = 4      # older runs did not record how many questions ran in parallel


def _verdict(item):
    """The standard AI's verdict for a question."""
    return (item.get("plain") or {}).get("verdict") or {}


def leaks(items):
    """How many standard AI descriptions gave the answer away."""
    return sum(_verdict(it).get("status") == "RED" for it in items)


def fair_leaks(items):
    """How many FairAlt descriptions still gave the answer away after all rewrites."""
    return sum(((it.get("attempts") or [{}])[-1].get("verdict") or {}).get("status") == "RED" for it in items)


def ai_seconds_per_question(results, items):
    """Measured AI time for one question, or None when the run has no timing."""
    timed = [it["seconds"] for it in items if it.get("seconds")]
    if timed:
        return sum(timed) / len(timed)
    total = len(results.get("items", []))
    if results.get("duration_s") and total:
        # Older runs recorded only the wall time of the whole run, with questions in parallel.
        return results["duration_s"] * min(results.get("workers", DEFAULT_WORKERS), total) / total
    return None


def ai_cost_per_question(results, items):
    """Measured AI cost (USD) for one question, from the tokens the API reported."""
    costed = [it["usage"]["est_cost_usd"] for it in items if (it.get("usage") or {}).get("calls")]
    if costed:
        return sum(costed) / len(costed)
    total = len(results.get("items", []))
    cost = (results.get("usage") or {}).get("est_cost_usd")
    return cost / total if cost and total else None


def review_seconds_per_question(items):
    """Measured human review time, from approvals that were timed."""
    timed = [it["review"]["seconds"] for it in items if it["review"].get("approved") and it["review"].get("seconds")]
    return sum(timed) / len(timed) if timed else None


def run_numbers(results, items, manual_min, hourly):
    """Time and cost per image with FairAlt and by hand, plus the standard AI's leak rate.

    tool_min and tool_cost are None when the run has no timing yet.
    """
    ai_seconds = ai_seconds_per_question(results, items)
    ai_cost = ai_cost_per_question(results, items) or 0
    review_seconds = review_seconds_per_question(items) or 0
    tool_min = (ai_seconds + review_seconds) / 60 if ai_seconds else None
    return {
        "leak_rate": leaks(items) / len(items),
        "ai_seconds": ai_seconds,
        "ai_cost": ai_cost,
        "tool_min": tool_min,
        "tool_cost": ai_cost + review_seconds / 3600 * hourly if tool_min else None,
        "manual_cost": manual_min / 60 * hourly,
    }


def scale_up(images, manual_min, tool_min, hourly, leak_rate, ai_cost=0.0):
    hours_saved = images * (manual_min - tool_min) / 60
    return {
        "hours_saved": hours_saved,
        "money_saved": hours_saved * hourly - images * (ai_cost or 0),
        "leaks_prevented": images * leak_rate,
    }


def confidence(item):
    """How sure the check is about one final description."""
    if item["final_status"] != "GREEN":
        return "Low", "needs a closer human review"
    tries = len(item.get("attempts", []))
    if tries == 1:
        return "High", "fair on the first version"
    return "Medium", f"fair after {tries} versions"
