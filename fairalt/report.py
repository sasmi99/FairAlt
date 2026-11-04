"""Fairness Report: for each question, the final description, the tests it passed and who approved it."""
import html
from datetime import date

import impact
from runstore import summary

REPORT_TESTS = [
    ("students_correct", "Students' answers correct"),
    ("no_answer", "No answer in the description"),
    ("no_banned", "No banned words"),
    ("no_missing", "No missing facts"),
    ("consistent", "Consistent every try"),
]


def fairness_report(results):
    """The report as a self-contained HTML page. results["items"] are the questions to include."""
    s = summary(results)
    e = html.escape
    issued = date.today().strftime("%d %B %Y")
    published = sum(bool(it.get("review", {}).get("published")) for it in results["items"])
    cards = []
    for it in results["items"]:
        last = (it.get("attempts") or [{}])[-1]
        verdict = last.get("verdict") or {}
        review = it.get("review", {})
        level, why = impact.confidence(it)
        fair = it["final_status"] == "GREEN"
        if verdict.get("checks"):
            tests = [(label, verdict["checks"].get(key)) for key, label in REPORT_TESTS]
            if verdict.get("runs"):
                why += f"; Student B right {verdict['b_correct']} of {verdict['runs']} tries"
        else:  # a run from before the code checks existed
            tests = [("Students' answers correct", fair),
                     ("No answer in the description", verdict.get("status") not in ("RED", None)),
                     ("No missing facts", verdict.get("status") not in ("ORANGE", None))]
        checks = "".join(f'<li class="{"ok" if ok else "no"}">{"✓" if ok else "✗" if ok is False else "?"} {e(t)}</li>'
                         for t, ok in tests)
        if review.get("approved"):
            sign = (f'<div class="sign ok">Approved by <b>{e(review.get("approved_by") or "")}</b> '
                    f'on {e((review.get("approved_at") or "")[:10])}</div>')
        else:
            sign = '<div class="sign wait">Awaiting human approval</div>'
        if review.get("published"):
            sign += (f'<div class="cert">Report <b>{e(review["report_id"])}</b> · published '
                     f'{e(review["published_at"][:10])}</div>')
        else:
            sign += '<div class="sign wait">Not yet published</div>'
        cards.append(f"""
<section class="q">
  <div class="qhead"><span class="id">{e(it['id'].upper())}</span><span class="subj">{e(it.get('subject', ''))}</span>
    <span class="conf conf-{level.lower()}">{level} confidence · {e(why)}</span></div>
  <h3>{e(it['question'])}</h3>
  <p class="desc">{e(review.get('edited_alt_text') or it.get('final_alt_text') or '')}</p>
  <ul class="tests">{checks}</ul>
  {sign}
</section>""")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FairAlt Fairness Report</title>
<style>
  body {{ font-family: 'Plus Jakarta Sans', system-ui, -apple-system, "Segoe UI", sans-serif; color: #1B1550;
         margin: 0; background: #F5F3FC; }}
  .page {{ max-width: 920px; margin: 32px auto; background: #fff; border: 1px solid #E6E1F7; border-radius: 20px;
          overflow: hidden; box-shadow: 0 8px 30px rgba(27,21,80,.08); }}
  header {{ background: radial-gradient(circle at 90% 10%, rgba(123,97,255,.6), transparent 45%),
            linear-gradient(130deg, #0F0C4E, #2B1F94 70%, #4A33C9); color: #fff; padding: 36px 40px; }}
  .brand {{ font-weight: 800; letter-spacing: .02em; color: #C9BFFF; font-size: 14px; text-transform: uppercase; }}
  header h1 {{ margin: 6px 0 8px; font-size: 32px; }}
  header p {{ margin: 0; color: #DCD5FF; font-size: 15px; line-height: 1.5; max-width: 640px; }}
  .facts {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: #E6E1F7; }}
  .facts div {{ background: #fff; padding: 18px 20px; }}
  .facts b {{ display: block; font-size: 26px; color: #4A2FB8; }}
  .facts span {{ font-size: 13px; color: #5E5A80; }}
  main {{ padding: 8px 40px 24px; }}
  .q {{ border-bottom: 1px solid #EEEBFA; padding: 22px 0; break-inside: avoid; }}
  .q:last-child {{ border-bottom: none; }}
  .qhead {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; font-size: 12px; }}
  .id {{ font-weight: 800; color: #5B3CC4; }}
  .subj {{ color: #5E5A80; }}
  .conf {{ margin-left: auto; border-radius: 999px; padding: 2px 10px; font-weight: 600; }}
  .conf-high {{ background: #E3F5EC; color: #0F7A4B; }}
  .conf-medium {{ background: #ECE8FD; color: #4A2FB8; }}
  .conf-low {{ background: #FFF1DC; color: #94560A; }}
  h3 {{ margin: 8px 0 6px; font-size: 17px; }}
  .desc {{ margin: 0 0 10px; line-height: 1.6; background: #F7F5FF; border-left: 3px solid #5B3CC4;
           padding: 10px 14px; border-radius: 0 10px 10px 0; }}
  .tests {{ list-style: none; padding: 0; margin: 0 0 10px; display: grid; grid-template-columns: 1fr 1fr; gap: 4px 16px;
            font-size: 13px; }}
  .tests .ok {{ color: #0F7A4B; }} .tests .no {{ color: #B42828; }}
  .cert {{ display: inline-block; margin-top: 6px; font-size: 13px; color: #4A2FB8; background: #ECE8FD;
           border-radius: 999px; padding: 3px 12px; }}
  .sign {{ font-size: 13px; }} .sign.ok {{ color: #1B1550; }} .sign.wait {{ color: #94560A; font-weight: 600; }}
  footer {{ font-size: 12px; color: #5E5A80; padding: 18px 40px 28px; border-top: 1px solid #EEEBFA; line-height: 1.5; }}
  @media (max-width: 700px) {{ .facts {{ grid-template-columns: 1fr 1fr; }} .tests {{ grid-template-columns: 1fr; }}
    main, header, footer {{ padding-left: 20px; padding-right: 20px; }} }}
  @media print {{ body {{ background: #fff; }} .page {{ box-shadow: none; margin: 0; border: none; }} }}
</style></head><body><div class="page">
<header><div class="brand">FairAlt</div><h1>Fairness Report</h1>
<p>Each image description below was built from the facts in the image, checked by code for the answer, banned
words and missing facts, and tested by two AI students: one saw the image, one heard only the description, several
times. A judge confirmed the result with a quote, and a person approved it before it was published.</p></header>
<div class="facts">
  <div><b>{s['total']}</b><span>questions checked</span></div>
  <div><b>{s['fair_green']}</b><span>passed the fairness test</span></div>
  <div><b>{s['needs_human']}</b><span>flagged for closer review</span></div>
  <div><b>{published}</b><span>published with a report</span></div>
</div>
<main>{''.join(cards)}</main>
<footer>Issued {e(issued)} · run {e(results['run_id'])} · model {e(str(results.get('model', '')))}.<br>
AI checks are evidence, not a guarantee. A description is ready for use only once a person has approved it.</footer>
</div></body></html>
"""
