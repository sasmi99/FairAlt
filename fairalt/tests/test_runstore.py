"""The saved run: new items, the gate, approving and publishing, summaries."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["AI_PROVIDER"] = "mock"

import runstore
from questions import load_questions

Q = load_questions()


def test_new_item_is_unchecked_and_complete():
    item = runstore.new_item(Q[0])
    assert item["id"] == "q01" and item["type"] == "Graphs"
    assert item["final_status"] is None and item["attempts"] == []
    assert item["review"] == {"approved": False, "approved_by": None, "approved_at": None, "edited_alt_text": None}


def test_blank_run_has_every_question():
    run = runstore.blank_run(Q)
    assert [it["id"] for it in run["items"]] == [q["id"] for q in Q]
    assert run["usage"] == {} and run["provider"] == "mock"
    assert runstore.checked(run) == (None, [])


def test_gate_stages_in_order():
    item = runstore.new_item(Q[0])
    assert runstore.stage(item) == "waiting"
    item["final_status"] = "GREEN"
    assert runstore.stage(item) == "tested"
    item["final_status"] = "NEEDS_HUMAN"
    assert runstore.stage(item) == "review"
    item["final_status"], item["final_alt_text"] = "GREEN", "A line."
    runstore.approve(item, " Sasmi ", "A line.", seconds=40)
    assert runstore.stage(item) == "approved"
    runstore.publish(item, "20261104_120000")
    assert runstore.stage(item) == "published"
    assert item["review"]["report_id"] == "FA-20261104_120000-Q01"
    runstore.unapprove(item)
    assert runstore.stage(item) == "tested"


def test_approve_records_edits_and_reviewer():
    item = runstore.new_item(Q[0])
    item["final_alt_text"] = "Original."
    runstore.approve(item, " Sasmi ", "Original.")
    assert item["review"]["approved_by"] == "Sasmi" and item["review"]["edited_alt_text"] is None
    assert runstore.final_text(item) == "Original."
    runstore.approve(item, "Sasmi", " Better. ")
    assert item["review"]["edited_alt_text"] == "Better." and runstore.final_text(item) == "Better."


def test_save_load_and_labels(tmp_path):
    run = runstore.blank_run(Q)
    path = runstore.save(run, tmp_path / "run_20261104_120102.json")
    assert runstore.load(path)["run_id"] == run["run_id"]
    assert runstore.run_label(path) == "04 Nov 2026, 12:01"
    assert runstore.run_label(path, seconds=True) == "04 Nov 2026, 12:01:02"
    assert runstore.run_label("results/other.json") == "other"
