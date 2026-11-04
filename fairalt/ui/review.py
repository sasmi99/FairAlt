"""Review page: one question at a time, from the image to approval and publishing."""
import html
import time

import streamlit as st

import pipeline
import report
from questions import DATA, by_id
from runstore import final_text
from ui import state
from ui.components import approval_pill, highlight, icon, listen, pill, section, sidebar, topbar

CHECKS = [
    ("students_correct", "Students' answers correct"),
    ("no_answer", "No answer in the description"),
    ("no_banned", "No banned words"),
    ("no_missing", "No missing facts"),
    ("consistent", "Consistent every try"),
]


def render():
    results = state.current()
    sidebar(results)
    topbar("Review")
    if not results:
        state.start_blank_run()
        results = st.session_state.results

    it = _pick_question(results["items"])
    state.track_review_time(it)
    plain = it.get("plain") or {}
    attempts = it.get("attempts") or []
    last = attempts[-1] if attempts else {}

    st.write("")
    _question_header(it)
    if not it.get("final_status"):
        return

    _descriptions(it, plain, attempts, last)
    if last:
        _fairness_checks(plain.get("verdict") or {}, last["verdict"])
        _facts(it.get("facts"))
        _students(it, last)
    if len(attempts) > 1:
        _earlier_versions(attempts[:-1])
    _approval(results, it)


# ---------- choosing and checking a question ----------

def _pick_question(items):
    ids = [it["id"] for it in items]
    by_ids = {it["id"]: it for it in items}
    if st.session_state.get("qid") not in by_ids:
        st.session_state.qid = ids[0]

    idx = ids.index(st.session_state.qid)
    sel, prev, nxt = st.columns([6, 1, 1], vertical_alignment="bottom")
    choice = sel.selectbox("Question", ids, index=idx, format_func=lambda i: f"{i.upper()} · {by_ids[i]['question']}")
    if choice != st.session_state.qid:
        st.session_state.qid = choice
        st.rerun()
    if prev.button("Previous", icon=":material/chevron_left:", disabled=idx == 0, width="stretch"):
        st.session_state.qid = ids[idx - 1]
        st.rerun()
    if nxt.button("Next", icon=":material/chevron_right:", disabled=idx == len(ids) - 1, width="stretch"):
        st.session_state.qid = ids[idx + 1]
        st.rerun()
    return by_ids[st.session_state.qid]


def _check_question(item):
    """Run the full check for one question, showing each step, and save it into the run."""
    started = time.time()
    with st.status("Checking this question…", expanded=True) as status:
        new = pipeline.process_question(by_id()[item["id"]], on_step=lambda msg: st.write(f"{msg}…"))
        if new.get("error"):
            status.update(label="The check could not finish", state="error")
        else:
            status.update(label=f"Checked in {int(time.time() - started)} seconds", state="complete", expanded=False)
    state.replace_item(new)
    st.rerun()


def _question_header(it):
    left, right = st.columns([5, 6], gap="large")
    with left, st.container(key="card_image"):
        st.image(str(DATA / it["image"]), width="stretch", alt=final_text(it) or it["question"])
        st.caption(by_id().get(it["id"], it).get("source", ""))
    with right:
        st.markdown(f'<div class="eyebrow">{html.escape(it.get("subject", ""))} · {it["id"].upper()}</div>',
                    unsafe_allow_html=True)
        st.markdown(f"## {it['question']}")
        if it.get("options"):
            st.markdown("\n".join(f"- {o}" for o in it["options"]))
        st.markdown(f'<p class="muted">Correct answer: <b style="color:#1B1550">{html.escape(str(it["answer"]))}</b></p>',
                    unsafe_allow_html=True)
        if it.get("final_status"):
            st.markdown(f'{pill(it["final_status"])} &nbsp; {approval_pill(it)}', unsafe_allow_html=True)
        if it.get("needs_human_reason"):
            st.warning(it["needs_human_reason"], icon=":material/flag:")
        st.write("")
        if it.get("final_status"):
            again = st.button("Check again", icon=":material/refresh:")
        else:
            again = st.button("Check this question", icon=":material/play_arrow:", type="primary")
        if again:
            _check_question(it)


# ---------- what the check found ----------

def _descriptions(it, plain, attempts, last):
    section("Descriptions")
    c1, c2 = st.columns(2, gap="medium")
    with c1, st.container(key="card_plain"):
        st.markdown(f":material/smart_toy: &nbsp;**Standard AI** &nbsp; {pill((plain.get('verdict') or {}).get('status'))}",
                    unsafe_allow_html=True)
        if plain:
            st.markdown(f'<div class="desc">{highlight(plain["alt_text"], plain["verdict"])}</div>',
                        unsafe_allow_html=True)
            st.markdown(f'<p class="why"><b>Why:</b> {html.escape(plain["verdict"].get("reason", ""))}</p>',
                        unsafe_allow_html=True)
            listen(it["question"], plain["alt_text"], f"plain_{it['id']}")
    with c2, st.container(key="card_fair"):
        st.markdown(f":material/verified: &nbsp;**FairAlt** &nbsp; {pill(it['final_status'])}", unsafe_allow_html=True)
        if last:
            st.markdown(f'<div class="desc">{highlight(final_text(it), last["verdict"])}</div>', unsafe_allow_html=True)
            note = last["verdict"].get("reason", "")
            if len(attempts) > 1:
                note += f" Improved over {len(attempts)} versions."
            st.markdown(f'<p class="why"><b>Why:</b> {html.escape(note)}</p>', unsafe_allow_html=True)
            listen(it["question"], final_text(it), f"fair_{it['id']}")


def _mark(value):
    if value is True:
        return f'<span class="ck ck-yes" title="Passed">{icon("check")}</span>'
    if value is False:
        return f'<span class="ck ck-no" title="Failed">{icon("close")}</span>'
    return f'<span class="ck ck-unsure" title="Not sure">{icon("question_mark")}</span>'


def _check_detail(key, v):
    if key == "students_correct" and v.get("runs"):
        return f'Student B right {v["b_correct"]} of {v["runs"]}'
    if key == "no_banned" and v.get("banned"):
        return ", ".join(f'"{w}"' for w in v["banned"])
    if key == "no_missing" and v.get("missing"):
        return f'{len(v["missing"])} missing'
    if key == "consistent" and v.get("runs"):
        return f'same answer {v["runs"]} times' if (v.get("checks") or {}).get("consistent") else "answers differed"
    return ""


def _proof(plain_v, fair_v):
    """The judge's quote for the first description it called a leak, and whether the quote is real."""
    v = fair_v if fair_v.get("judge_status") == "RED" else plain_v if plain_v.get("judge_status") == "RED" else None
    if not v:
        return ""
    who = "FairAlt" if v is fair_v else "Standard AI"
    ok = v.get("quote_ok")
    return (f'<div class="proof">{icon("format_quote")}<span>Judge\'s proof ({who}): '
            f'<b>"{html.escape(v.get("evidence") or "")}"</b></span>'
            f'<em class="{"ok" if ok else "bad"}">{"found in the description" if ok else "not found in the description"}</em></div>')


def _fairness_checks(plain_v, fair_v):
    """Checklist: Standard AI vs FairAlt, each test with a tick, a cross or a question mark."""
    if not fair_v.get("checks"):
        return  # a run from before these checks existed
    section("Fairness checks")
    rows = "".join(
        f'<tr><td>{label}</td>'
        + "".join(f'<td>{_mark((v.get("checks") or {}).get(key))}<small>{html.escape(_check_detail(key, v))}</small></td>'
                  for v in (plain_v, fair_v))
        + "</tr>" for key, label in CHECKS)
    notes = "".join(f'<li>{html.escape(p)}</li>' for p in (fair_v.get("problems") or []) + (fair_v.get("unsure") or []))
    with st.container(key="card_checks"):
        st.markdown(f'<div class="tablewrap"><table class="ctable"><thead><tr><th>Test</th><th>Standard AI</th>'
                    f'<th>FairAlt</th></tr></thead><tbody>{rows}</tbody></table></div>{_proof(plain_v, fair_v)}'
                    + (f'<ul class="cnotes">{notes}</ul>' if notes else ""), unsafe_allow_html=True)


def _facts(facts):
    if not facts:
        return
    kept, removed = facts.get("kept", []), facts.get("removed", [])
    with st.expander(f"Facts listed from the image: {len(kept)} kept, {len(removed)} removed",
                     icon=":material/list_alt:"):
        st.markdown("".join(f'<div class="fact">{icon("check")}{html.escape(f["fact"])}</div>' for f in kept)
                    + "".join(f'<div class="fact off">{icon("close")}<s>{html.escape(f["fact"])}</s>'
                              f'<em>{html.escape(f["why"])}</em></div>' for f in removed),
                    unsafe_allow_html=True)


def _students(it, last):
    section("Student test")
    a, b = it.get("student_a") or {}, last.get("student_b") or {}
    verdict = last["verdict"]
    c1, c2 = st.columns(2, gap="medium")
    for col, key, sym, title, ans in [
        (c1, "a", ":material/visibility:", "Student A · sees the image", a),
        (c2, "b", ":material/hearing:", "Student B · hears only the description", b),
    ]:
        with col, st.container(key=f"card_student_{key}"):
            st.markdown(f"{sym} &nbsp;**{title}**")
            tries = ""
            if key == "b" and verdict.get("runs"):
                tries = f'<span class="tries">right in {verdict["b_correct"]} of {verdict["runs"]} tries</span>'
            st.markdown(f'<span class="ans">Answer <b>{html.escape(str(ans.get("answer", "")))}</b></span>{tries}'
                        f'<p class="muted">{html.escape(str(ans.get("reasoning", "")))}</p>',
                        unsafe_allow_html=True)


def _earlier_versions(earlier):
    with st.expander(f"Earlier versions ({len(earlier)})", icon=":material/history:"):
        for att in earlier:
            st.markdown(f"**Version {att['attempt']}** &nbsp; {pill(att['verdict']['status'])}", unsafe_allow_html=True)
            st.markdown(f'<div class="desc">{highlight(att["alt_text"], att["verdict"])}</div>'
                        f'<p class="muted">{html.escape(att["verdict"].get("reason", ""))}</p>',
                        unsafe_allow_html=True)


# ---------- the human step ----------

def _approval(results, it):
    section("Approval")
    with st.container(key="card_approval"):
        r = it["review"]
        if r["approved"]:
            _approved(results, it, r)
        else:
            _approve_form(it)


def _approved(results, it, r):
    st.markdown(f":material/check_circle: &nbsp;Approved by **{html.escape(r['approved_by'] or '')}** "
                f"on {r['approved_at'][:16].replace('T', ' at ')}")
    a, b, _ = st.columns([1.4, 1.4, 2.2], vertical_alignment="center")
    if r.get("published"):
        st.markdown(f'<div class="published">{icon("verified")}Published · report '
                    f'<b>{html.escape(r["report_id"])}</b> · {r["published_at"][:10]}</div>', unsafe_allow_html=True)
        a.download_button("Fairness Report", report.fairness_report({**results, "items": [it]}),
                          file_name=f"fairalt_report_{it['id']}.html", mime="text/html",
                          icon=":material/workspace_premium:", type="primary", width="stretch")
    elif a.button("Publish", icon=":material/verified:", type="primary", width="stretch",
                  help="Issue the Fairness Report and mark this question ready to publish"):
        state.publish(it)
        st.rerun()
    if b.button("Undo approval", icon=":material/undo:", width="stretch"):
        state.unapprove(it)
        st.rerun()


def _approve_form(it):
    text = st.text_area("Final description", value=final_text(it), height=120, key=f"edit_{it['id']}")
    n, b = st.columns([3, 1], vertical_alignment="bottom")
    name = n.text_input("Reviewer name", value=st.session_state.get("reviewer", ""))
    st.session_state.reviewer = name
    if b.button("Approve", icon=":material/check:", type="primary", width="stretch",
                disabled=not name.strip() or not text.strip()):
        state.approve(it, text)
        st.rerun()
