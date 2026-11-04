"""Dashboard page: what FairAlt achieves, measured live from the run, and a scale-up calculator."""
import html

import streamlit as st

import impact
import report
import runstore
from ui import state
from ui.components import VERDICTS, icon, minutes, money, pct, sidebar, topbar

# Colours for the fairness bars, in stack order. The order keeps amber away from
# green, so every neighbouring pair stays distinct for colour-blind readers.
BAR_STATUS = [("Fair", "#0ca30c"), ("Needs review", "#5B3CC4"), ("Missing information", "#fab219"),
              ("Gives answer away", "#d03b3b")]
FTE_HOURS_PER_YEAR = 1800  # one full-time person, for "staff for a year"


def render():
    state.stop_review_timer()
    results = state.current()
    sidebar(results)
    topbar("Dashboard")
    s, items = runstore.checked(results) if results else (None, [])
    if not s:
        st.info("No questions checked yet.")
        return

    st.session_state.setdefault("calc_images", 10_000)
    st.session_state.setdefault("calc_manual", impact.MANUAL_MINUTES)
    st.session_state.setdefault("calc_hourly", impact.HOURLY_COST)
    manual, hourly = st.session_state.calc_manual, st.session_state.calc_hourly
    nums = impact.run_numbers(results, items, manual, hourly)

    _header(results, items)
    st.markdown(
        '<div class="dgrid">'
        + _fairness_card(items)
        + _saving_card("schedule", "Time per image", nums["tool_min"], manual, "less time",
                       lambda x: f"{minutes(x)} min")
        + _saving_card("payments", "Cost per image", nums["tool_cost"], nums["manual_cost"], "lower cost", money)
        + "</div>", unsafe_allow_html=True)
    st.markdown(_impact_row(s, items, nums, manual), unsafe_allow_html=True)
    st.write("")
    _projected_impact(nums, manual, hourly)


def _header(results, items):
    n = len(items)
    head, btn = st.columns([4, 1.3], vertical_alignment="center")
    head.markdown(
        f'<div class="dash-head"><h2>FairAlt dashboard</h2><div class="dash-meta">'
        f'<span class="live"><i></i>Live</span>{n} question{"" if n == 1 else "s"} checked · '
        f"{html.escape(runstore.run_label(st.session_state.results_path))}</div></div>", unsafe_allow_html=True)
    published = [it for it in items if it["review"].get("published")]
    btn.download_button("Fairness Report", report.fairness_report({**results, "items": published}),
                        file_name=f"fairalt_report_{results['run_id']}.html", mime="text/html",
                        icon=":material/workspace_premium:", type="primary", width="stretch",
                        disabled=not published, help=f"{len(published)} published question"
                        f"{'' if len(published) == 1 else 's'} with a report")


def _bar_label(status):
    """The fairness bar a verdict counts towards."""
    return VERDICTS[status][0] if status in ("GREEN", "RED", "ORANGE") else "Needs review"


def _fairness_card(items):
    """Before/after: share of fair descriptions, as segmented bars."""
    n = len(items)
    groups = [("Standard AI", [_bar_label(((it.get("plain") or {}).get("verdict") or {}).get("status")) for it in items]),
              ("FairAlt", [_bar_label(it["final_status"]) for it in items])]
    rates = {g: labels.count("Fair") / n for g, labels in groups}
    rows, used = [], set()
    for g, labels in groups:
        segs = ""
        for name, colour in BAR_STATUS:
            k = labels.count(name)
            if k:
                used.add(name)
                segs += (f'<i style="flex:{k};background:{colour}" title="{name}: {k} of {n}">'
                         f'{k if k / n >= .08 else ""}</i>')
        rows.append(f'<div class="fbar-row"><div class="fbar-head"><span>{g}</span><b>{pct(rates[g])} fair</b></div>'
                    f'<div class="fbar">{segs}</div></div>')
    legend = "".join(f'<span><i style="background:{c}"></i>{name}</span>' for name, c in BAR_STATUS if name in used)
    gain = (rates["FairAlt"] - rates["Standard AI"]) * 100
    return (f'<div class="dcard dcard-wide"><div class="dcard-head">{icon("balance")}Fair descriptions</div>'
            f'<div class="dbig">{pct(rates["FairAlt"])}<span>fair with FairAlt</span></div>'
            f'<div class="delta">{"▲" if gain >= 0 else "▼"} {abs(gain):.0f} points vs standard AI</div>'
            f'{"".join(rows)}<div class="flegend">{legend}</div></div>')


def _saving_card(icon_name, title, fairalt, by_hand, word, fmt):
    """One saving: the percentage saved, then by-hand vs FairAlt bars on one scale.

    fairalt is None until the run has timing, and the card says so.
    """
    if fairalt is None:
        big, bar, fairalt_label, saved_label = "—", 0, "—", "Not measured yet"
    else:
        saved = 1 - fairalt / by_hand
        big, bar = pct(saved), max(0.0, min(100.0, (1 - saved) * 100))
        fairalt_label, saved_label = fmt(fairalt), f"{fmt(by_hand - fairalt)} saved per image"
    return (f'<div class="dcard"><div class="dcard-head">{icon(icon_name)}{title}</div>'
            f'<div class="dbig">{big}<span>{word}</span></div>'
            f'<div class="delta">{saved_label}</div><div class="cbars">'
            f'<div class="cbar-row"><div class="cbar-head"><span>By hand</span><b>{fmt(by_hand)}</b></div>'
            f'<div class="cbar"><i class="hand" style="width:100%"></i></div></div>'
            f'<div class="cbar-row"><div class="cbar-head"><span>FairAlt</span><b>{fairalt_label}</b></div>'
            f'<div class="cbar"><i class="fair" style="width:{bar:.2f}%"></i></div></div></div></div>')


def _impact_row(s, items, nums, manual):
    """What this run achieved: leaks stopped, money and time saved, fixes, the gate."""
    n = s["total"]
    fixed = s["fair_green"] - s["fair_first_try"]
    published = sum(bool(it["review"].get("published")) for it in items)
    if nums["tool_cost"] is not None:
        saved = money(n * (nums["manual_cost"] - nums["tool_cost"]))
        saved_sub = f"{n * (manual - nums['tool_min']) / 60:,.1f} staff hours across {n} questions"
    else:
        saved, saved_sub = "—", "not measured yet"
    cards = [
        ("t-rose", "shield", "Answer leaks stopped", f'{s["plain_red"]}',
         f'Standard AI leaked {s["plain_red"]} of {n} · FairAlt {impact.fair_leaks(items)}'),
        ("t-green", "savings", "Saved on this run", saved, saved_sub),
        ("t-violet", "bolt", "Fair first time", f'{s["fair_first_try"]}<small> / {n}</small>',
         f"{fixed} more fixed automatically" if fixed else "no rewrites needed"),
        ("t-indigo", "verified", "Published", f'{published}<small> / {n}</small>',
         f'<div class="kbar"><i style="width:{published / n * 100:.0f}%"></i></div>'),
    ]
    return ('<div class="tgrid">' + "".join(
        f'<div class="tcard {tone}"><div class="khead">{icon(sym)}{label}</div><div class="kval">{value}</div>'
        f'<div class="ksub">{sub}</div></div>' for tone, sym, label, value, sub in cards) + "</div>")


def _projected_impact(nums, manual, hourly):
    """Sliders for a bigger catalogue, and what that would save."""
    with st.container(key="card_calc"):
        st.markdown(f'<div class="dcard-head">{icon("trending_up")}Projected impact</div>', unsafe_allow_html=True)
        a, b, c = st.columns(3, gap="large")
        a.slider("Images", 1_000, 100_000, step=1_000, key="calc_images", format="%d")
        b.slider("Minutes per image by hand", 5, 90, step=1, key="calc_manual")
        c.slider("Staff cost per hour, USD", 10, 150, step=5, key="calc_hourly")
        images = st.session_state.calc_images
        if nums["tool_min"]:
            r = impact.scale_up(images, manual, nums["tool_min"], hourly, nums["leak_rate"], nums["ai_cost"])
            hours, saved, leaks = (f'{max(0, r["hours_saved"]):,.0f}', f'${max(0, r["money_saved"]):,.0f}',
                                   f'{r["leaks_prevented"]:,.0f}')
            people = f'≈ {max(0, r["hours_saved"]) / FTE_HOURS_PER_YEAR:,.1f} full-time staff for a year'
        else:
            hours = saved = leaks = "—"
            people = ""
        st.markdown(
            f"""<div class="calc-out"><div class="orb"></div>
<div class="calc-for">For {images:,} images</div>
<div class="calc-grid">
<div class="calc-item">{icon("schedule")}<div><div class="calc-lbl">Hours saved</div><div class="calc-num">{hours}</div>
  <div class="calc-sub">{people}</div></div></div>
<div class="calc-item">{icon("savings")}<div><div class="calc-lbl">Money saved</div><div class="calc-num good">{saved}</div>
  <div class="calc-sub">after AI cost</div></div></div>
<div class="calc-item">{icon("shield")}<div><div class="calc-lbl">Answer leaks prevented</div><div class="calc-num">{leaks}</div>
  <div class="calc-sub">at the {nums["leak_rate"]:.0%} leak rate measured</div></div></div>
</div></div>""", unsafe_allow_html=True)
