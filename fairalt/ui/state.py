"""Session state: the run on screen, and the things the pages do to it."""
import time

import streamlit as st

import runstore
from questions import load_questions


def current():
    """The run on screen: the latest saved run the first time, then whatever is in the session."""
    if "results" not in st.session_state:
        files = runstore.results_files()
        st.session_state.results = None
        if files:
            load_run(files[0])
    return st.session_state.results


def load_run(path):
    st.session_state.results_path = str(path)
    st.session_state.results = runstore.load(path)


def save_run():
    runstore.save(st.session_state.results, st.session_state.results_path)


def start_blank_run():
    results = runstore.blank_run(load_questions())
    st.session_state.results = results
    st.session_state.results_path = str(runstore.save(results))


def replace_item(new):
    """Swap a re-checked question into the run on screen and save it."""
    items = st.session_state.results["items"]
    items[[it["id"] for it in items].index(new["id"])] = new
    save_run()


# ---------- the review timer: from seeing a checked description to approving it ----------

def track_review_time(item):
    if item.get("final_status") and not item["review"]["approved"]:
        if (st.session_state.get("review_timer") or (None,))[0] != item["id"]:
            st.session_state.review_timer = (item["id"], time.time())
    else:
        stop_review_timer()


def stop_review_timer():
    st.session_state.pop("review_timer", None)


# ---------- what a reviewer does ----------

def approve(item, text):
    timer = st.session_state.pop("review_timer", None)
    seconds = round(time.time() - timer[1]) if timer and timer[0] == item["id"] else None
    runstore.approve(item, st.session_state.get("reviewer", ""), text, seconds)
    save_run()


def unapprove(item):
    runstore.unapprove(item)
    save_run()


def publish(item):
    runstore.publish(item, st.session_state.results["run_id"])
    save_run()
