import impact


def item(qid, plain, final="GREEN", tries=1, approved=False, edited=None, **extra):
    return {"id": qid, "plain": {"verdict": {"status": plain}}, "final_status": final,
            "attempts": [{"verdict": {"status": final if final != "NEEDS_HUMAN" else "ORANGE"}}] * tries,
            "review": {"approved": approved, "edited_alt_text": edited}, **extra}


def test_scale_up_matches_worked_example():
    r = impact.scale_up(10_000, 30, 3, 40, 8 / 15)
    assert r["hours_saved"] == 4_500
    assert r["money_saved"] == 180_000
    assert round(r["leaks_prevented"]) == 5_333


def test_scale_up_subtracts_ai_cost():
    assert impact.scale_up(1_000, 30, 3, 40, 0.5, ai_cost=0.05)["money_saved"] == 450 * 40 - 50


def test_per_question_time_and_cost_prefer_item_measurements():
    items = [item("q01", "RED", seconds=20, usage={"calls": 7, "est_cost_usd": 0.04}),
             item("q02", "GREEN", seconds=40, usage={"calls": 7, "est_cost_usd": 0.06})]
    results = {"items": items, "duration_s": 999, "usage": {"est_cost_usd": 9}}
    assert impact.ai_seconds_per_question(results, items) == 30
    assert impact.ai_cost_per_question(results, items) == 0.05


def test_older_runs_fall_back_to_run_totals():
    items = [item(f"q{i:02}", "GREEN") for i in range(1, 9)]
    results = {"items": items, "duration_s": 60, "usage": {"est_cost_usd": 0.4}}
    assert impact.ai_seconds_per_question(results, items) == 30  # 60 s × 4 parallel ÷ 8
    assert impact.ai_cost_per_question(results, items) == 0.05


def test_review_time_uses_timed_approvals_only():
    items = [item("q01", "RED", approved=True), item("q02", "RED", approved=True), item("q03", "GREEN")]
    assert impact.review_seconds_per_question(items) is None
    items[0]["review"]["seconds"], items[1]["review"]["seconds"] = 60, 120
    assert impact.review_seconds_per_question(items) == 90


def test_confidence():
    assert impact.confidence(item("q01", "RED"))[0] == "High"
    assert impact.confidence(item("q04", "RED", tries=2))[0] == "Medium"
    assert impact.confidence(item("q03", "INVALID", final="NEEDS_HUMAN"))[0] == "Low"


def test_run_numbers_combine_ai_and_review_time():
    items = [item("q01", "RED", approved=True, seconds=30, usage={"calls": 7, "est_cost_usd": 0.10}),
             item("q02", "GREEN", seconds=30, usage={"calls": 7, "est_cost_usd": 0.10})]
    items[0]["review"]["seconds"] = 90
    n = impact.run_numbers({"items": items}, items, manual_min=15, hourly=30)
    assert n["leak_rate"] == 0.5
    assert n["tool_min"] == 2                      # 30 s of AI + 90 s of review
    assert n["tool_cost"] == 0.10 + 90 / 3600 * 30  # AI cost + the reviewer's time
    assert n["manual_cost"] == 7.5


def test_run_numbers_without_timing():
    items = [item("q01", "GREEN")]
    n = impact.run_numbers({"items": items}, items, 15, 30)
    assert n["tool_min"] is None and n["tool_cost"] is None


def test_leaks_and_fair_leaks():
    items = [item("q01", "RED"), item("q02", "GREEN")]
    items[0]["attempts"] = [{"verdict": {"status": "RED"}}]
    assert impact.leaks(items) == 1 and impact.fair_leaks(items) == 1
    items[0]["attempts"] = [{"verdict": {"status": "GREEN"}}]
    assert impact.fair_leaks(items) == 0
