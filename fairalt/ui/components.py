"""Small pieces every page uses: formatters, pills, the answer highlight, Listen, top bar and sidebar."""
import hashlib
import html
import re
from pathlib import Path

import streamlit as st

import ai_client
import runstore
from ui import state

AUDIO = runstore.RESULTS / "audio"

# status -> (label, colour, icon): the one place the verdict words are defined
VERDICTS = {
    "GREEN": ("Fair", "green", "check"),
    "RED": ("Gives answer away", "red", "close"),
    "ORANGE": ("Missing information", "orange", "remove"),
    "INVALID": ("Check failed", "grey", "error"),
    "NEEDS_HUMAN": ("Needs review", "violet", "flag"),
    "UNSURE": ("Unsure", "violet", "help"),
}


# ---------- formatting ----------

def icon(name, cls="", tip=""):
    label = f' role="img" aria-label="{tip}" title="{tip}"' if tip else ' aria-hidden="true"'
    return f'<span class="msr {cls}"{label}>{name}</span>'


def pct(x):
    return f"{x * 100:.1f}%" if 0.99 <= x < 1 else f"{x:.0%}"


def money(x):
    return f"${x:,.2f}" if abs(x) < 10 else f"${x:,.0f}"


def minutes(x):
    return f"{x:.1f}".rstrip("0").rstrip(".")


def section(title):
    st.markdown(f'<div class="section"><span class="section-dot"></span><h3>{html.escape(title)}</h3></div>',
                unsafe_allow_html=True)


# ---------- verdict pills ----------

def pill(status):
    label, colour, _ = VERDICTS.get(status, ("Not checked", "grey", ""))
    return f'<span class="pill pill-{colour}">{html.escape(label)}</span>'


def approval_pill(item):
    if item["review"]["approved"]:
        return '<span class="pill pill-green">Approved</span>'
    return '<span class="pill pill-grey">Pending</span>'


def vpill(status):
    """A verdict with its icon, or a dash when the question has none yet."""
    if status not in VERDICTS:
        return '<span class="dash">—</span>'
    label, colour, sym = VERDICTS[status]
    return f'<span class="vp vp-{colour}">{icon(sym)}{html.escape(label)}</span>'


def highlight(text, verdict):
    """Escape the description and mark the words that give the answer away."""
    safe = html.escape(text or "")
    if not verdict:
        return safe
    parts = []
    if verdict.get("status") == "RED" or verdict.get("judge_status") == "RED":
        parts += re.split(r"\.\.\.|…", verdict.get("evidence") or "")  # the judge's quote first, then banned words
    parts += [w for w in verdict.get("banned") or [] if not any(w.lower() in p.lower() for p in parts)]
    for part in parts:
        part = part.strip(" .\"'")
        if len(part) >= 2:
            safe = re.sub(re.escape(html.escape(part)), lambda m: f'<mark class="leak">{m.group(0)}</mark>',
                          safe, flags=re.IGNORECASE)
    return safe


# ---------- Listen: read the question and description aloud ----------

def speech_file(text):
    AUDIO.mkdir(parents=True, exist_ok=True)
    path = AUDIO / f"{hashlib.sha1(text.encode()).hexdigest()[:16]}.mp3"
    if not path.exists():
        from gtts import gTTS

        gTTS(text, lang="en").save(str(path))
    return path


def listen(question, description, key):
    """Play the question and description the way a screen reader user hears them."""
    if st.button("Listen", icon=":material/volume_up:", key=f"listen_{key}"):
        st.session_state.playing = key
    if st.session_state.get("playing") == key:
        try:
            with st.spinner("Preparing audio…"):
                path = speech_file(f"Question. {question} Image description. {description}")
            st.audio(str(path), format="audio/mp3", autoplay=True)
        except Exception:
            st.warning("Audio needs an internet connection the first time it is played.")


# ---------- page frame ----------

def topbar(page, search=False):
    """Breadcrumb on the left; on the overview, a question search on the right."""
    left, right = st.columns([3, 1.4], vertical_alignment="center")
    left.markdown(f'<div class="crumb">FairAlt <span>/</span> <b>{html.escape(page)}</b></div>',
                  unsafe_allow_html=True)
    if search:
        return right.text_input("Search questions", key="q_search", placeholder="Search questions",
                                label_visibility="collapsed", icon=":material/search:")
    return ""


def sidebar(results):
    """Run picker and run details under the page links."""
    with st.sidebar:
        files = runstore.results_files()
        if files:
            names = [f.name for f in files]
            cur = Path(st.session_state.get("results_path", files[0])).name
            labels = [runstore.run_label(n) for n in names]
            # Two runs in the same minute would look identical, so show seconds for those.
            shown = {n: (runstore.run_label(n, seconds=True) if labels.count(lbl) > 1 else lbl)
                     for n, lbl in zip(names, labels)}
            choice = st.selectbox("Run", names, index=names.index(cur) if cur in names else 0,
                                  format_func=shown.get)
            if choice != cur:
                state.load_run(runstore.RESULTS / choice)
                st.rerun()
        items = (results or {}).get("items", [])
        if results:
            subjects = {it.get("subject", "") for it in items}
            st.markdown(
                f'<div class="runcard"><b>Run · {html.escape(runstore.run_label(st.session_state.results_path))}</b>'
                f'<span>{len(items)} questions · {len(subjects)} subjects</span>'
                f'<span class="model"><i></i>{html.escape(str(results.get("model") or ai_client.model_name()))}</span>'
                "</div>", unsafe_allow_html=True)
        awaiting = sum(runstore.stage(it) in ("tested", "review") for it in items)
        if awaiting:
            # Count of descriptions waiting for a reviewer, shown next to "Review" in the sidebar.
            st.markdown(f'<style>[data-testid="stSidebarNav"] a[href$="/review"]::after {{ content: "{awaiting}"; }}'
                        "</style>", unsafe_allow_html=True)
