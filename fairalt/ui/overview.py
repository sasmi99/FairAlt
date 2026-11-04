"""Overview page: the run at a glance, the gate, and the list of questions."""
import html

import streamlit as st

import impact
import pipeline
import runstore
from questions import DATA, by_id, load_questions
from ui import nav, state
from ui.components import icon, sidebar, topbar, vpill

PAGE_SIZE = 8
TABLE_WIDTHS = [0.5, 0.7, 3.3, 1.85, 1.2, 1.75, 1.1]


def render():
    results = state.current()
    sidebar(results)
    query = topbar("Overview", search=True)
    if not results:
        state.start_blank_run()
        st.rerun()

    items = results["items"]
    s, done = runstore.checked(results)
    _hero(results, s, len(items))
    st.markdown(_kpis(results, s, done), unsafe_allow_html=True)

    errors = [it for it in items if it.get("error")]
    if errors and len(errors) == len(done):
        st.error(f"This run could not reach the AI model. {errors[0]['needs_human_reason']}")
    _question_table(items, query)


def _hero(results, s, n):
    with st.container(key="hero_main"):
        st.markdown(_hero_text(s, n), unsafe_allow_html=True)
        a, b, _ = st.columns([1.3, 1.3, 3])
        if a.button("Check all questions", icon=":material/play_arrow:", type="primary", width="stretch"):
            _check_all()
        if b.button("Start empty run", icon=":material/add:", width="stretch"):
            state.start_blank_run()
            st.rerun()


def _hero_text(s, n):
    when = html.escape(runstore.run_label(st.session_state.results_path))
    if not s:
        return (f'<div class="h-eyebrow">New run · {n} questions · {when}</div>'
                f"<h1>{n} questions ready to check</h1>"
                "<p>Each description is tested by two AI students: one sees the image, one only hears the "
                "description.</p>")
    done, fair, red = s["total"], s["fair_green"], s["plain_red"]
    if fair == done:
        lead = "Every description keeps the facts a student needs and none of them gives the answer away."
    else:
        lead = f"{done - fair} still {'needs' if done - fair == 1 else 'need'} a closer human review."
    if red:
        lead += (f" A standard AI description leaked the answer on {red} of the same {done} "
                 f"question{'' if done == 1 else 's'}.")
    return (f'<div class="h-eyebrow">Latest run · {done} of {n} questions checked · {when}</div>'
            f"<h1>{fair} of {done} image descriptions are fair for screen-reader students</h1><p>{lead}</p>")


def _kpis(results, s, items):
    if not s:
        return ""
    n, ai_s = s["total"], impact.ai_seconds_per_question(results, items)
    approved_pct = s["approved"] / n * 100
    cards = [
        ("verified", "FairAlt fair", f'{s["fair_green"]}<small> / {n}</small>',
         f'<b>{s["fair_first_try"]}</b> fair on the first version'),
        ("gpp_bad", "Standard AI leaks", f'{s["plain_red"]}<small> / {n}</small>',
         "all gave the answer away" if s["plain_red"] and s["plain_red"] == s["plain_unfair"]
         else f'{s["plain_orange"]} more missed information'),
        ("timer", "Avg. check time", f'{ai_s:.0f}<small> s</small>' if ai_s else "—",
         "per question, write → judge"),
        ("how_to_reg", "Approved by reviewer", f'{s["approved"]}<small> / {n}</small>',
         f'<div class="kbar"><i style="width:{approved_pct:.0f}%"></i></div>'),
    ]
    return '<div class="kgrid">' + "".join(
        f'<div class="kcard"><div class="khead">{icon(sym)}{label}</div><div class="kval">{value}</div>'
        f'<div class="ksub">{sub}</div></div>' for sym, label, value, sub in cards) + "</div>"


def _gate_strip(items):
    """The gate at a glance: how many questions are at each stage."""
    counts = {key: 0 for key, _, _ in runstore.GATES}
    for it in items:
        counts[runstore.stage(it)] += 1
    stages = "".join(
        f'<div class="gs gs-{key}{" on" if counts[key] else ""}"><span>{icon(sym)}{label}</span><b>{counts[key]}</b></div>'
        + ('<i class="gs-arrow">›</i>' if key != "published" else "")
        for key, label, sym in runstore.GATES)
    return f'<div class="gstrip">{stages}</div>'


def _status_pill(it):
    key = runstore.stage(it)
    _, label, sym = next(g for g in runstore.GATES if g[0] == key)
    return f'<span class="sp sp-{key}">{icon(sym)}{label}</span>'


def _question_table(items, query):
    in_stage = lambda *keys: [it for it in items if runstore.stage(it) in keys]
    to_review, approved, published = in_stage("tested", "review"), in_stage("approved"), in_stage("published")
    with st.container(key="card_qtable"):
        head, tabs = st.columns([2.4, 2.8], vertical_alignment="center")
        head.markdown('<div class="t-title">Questions</div>'
                      '<div class="t-sub">Standard AI vs FairAlt verdicts for each question in this run</div>',
                      unsafe_allow_html=True)
        st.markdown(_gate_strip(items), unsafe_allow_html=True)
        views = {f"All {len(items)}": items, f"To review {len(to_review)}": to_review,
                 f"Approved {len(approved)}": approved, f"Published {len(published)}": published}
        view = tabs.segmented_control("Show", list(views), default=list(views)[0], key="q_view",
                                      label_visibility="collapsed") or list(views)[0]
        rows = views.get(view, items)
        if query:
            q = query.lower()
            rows = [it for it in rows if q in it["question"].lower() or q in it.get("subject", "").lower()
                    or q in it["id"]]

        cols = st.columns(TABLE_WIDTHS)
        for col, label in zip(cols, ["#", "Image", "Question", "Standard AI", "FairAlt", "Status", ""]):
            col.markdown(f'<span class="th">{label}</span>', unsafe_allow_html=True)
        show_all = st.session_state.get("show_all") or query
        shown = rows if show_all else rows[:PAGE_SIZE]
        for it in shown:
            _question_row(it)
        if not shown:
            st.markdown('<p class="muted" style="padding:14px 0">No questions here yet.</p>', unsafe_allow_html=True)
        f1, f2 = st.columns([6, 1], vertical_alignment="center")
        f1.markdown(f'<span class="muted">Showing {len(shown)} of {len(rows)} question{"" if len(rows) == 1 else "s"}</span>',
                    unsafe_allow_html=True)
        if len(rows) > PAGE_SIZE and not query:
            if f2.button("Show less" if show_all else "Show all", width="stretch"):
                st.session_state.show_all = not show_all
                st.rerun()


def _question_row(it):
    with st.container(key=f"qrow_{it['id']}"):
        c = st.columns(TABLE_WIDTHS, vertical_alignment="center")
        c[0].markdown(f'<span class="qid">{it["id"].upper().replace("Q0", "Q")}</span>', unsafe_allow_html=True)
        c[1].image(str(DATA / it["image"]), width=54)
        kind = by_id().get(it["id"], {}).get("type", "")
        c[2].markdown(f'<div class="qq">{html.escape(it["question"])}</div>'
                      f'<div class="qm">{html.escape(it.get("subject", ""))}'
                      f'{" · " + html.escape(kind) if kind else ""}</div>', unsafe_allow_html=True)
        c[3].markdown(vpill(((it.get("plain") or {}).get("verdict") or {}).get("status")), unsafe_allow_html=True)
        c[4].markdown(vpill(it.get("final_status")), unsafe_allow_html=True)
        c[5].markdown(_status_pill(it), unsafe_allow_html=True)
        if c[6].button("Review", key=f"open_{it['id']}", type="tertiary", icon=":material/arrow_forward:",
                       icon_position="right"):
            st.session_state.qid = it["id"]
            st.switch_page(nav.PAGES["review"])


def _check_all():
    questions = load_questions()
    with st.status("Checking questions…", expanded=True) as status:
        bar = st.progress(0.0)

        def on_progress(done, total, it):
            bar.progress(done / total, text=f"{done} of {total} questions checked")

        res = pipeline.run(questions, workers=4, progress=on_progress)
        path = runstore.save(res)
        status.update(label="Check complete", state="complete", expanded=False)
    state.load_run(path)
    st.rerun()
