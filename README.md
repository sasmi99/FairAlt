# FairAlt

*Clarity without compromise.*

Students who use a screen reader hear a **description** of a test question's image instead of seeing
it. A bad description is unfair in one of two ways: it **gives the answer away**, or it **leaves out a
fact** the student needs.

FairAlt writes the description, then **proves it is fair** before a person approves it. Code makes the
simple decisions (is the answer right? is a banned word used? is a fact missing?) and the AI only
judges what code cannot. Anything uncertain goes to a human.

## How a question is checked

1. **Two writers.** A *standard AI* and *FairAlt* each get the same picture and question. The standard
   AI is told only to "write a description of this image for a blind student taking this test", with no
   fairness rules. FairAlt works differently:
   - it lists every fact in the image and marks each *printed*, *drawn* or *worked out*;
   - code removes worked-out facts, facts with a banned word, and facts containing the answer (unless the
     text is printed in the image, which a sighted student sees too);
   - it writes the description from the remaining facts only, without seeing the image.
2. **Two AI students test each description.**
   - **Student A** sees the image and the question. It is the reference: if it is wrong, the question
     itself is broken and goes to a person.
   - **Student B** hears the description and the question, no image, and answers **3 times**
     (`STUDENT_B_RUNS`). A smaller model can be set for Student B (`STUDENT_B_MODEL`) to make the test
     stricter.
3. **Code checks.** Are the answers right? Is a banned word used for this type of question
   (`data/banned_words.json`, e.g. "highest" for charts)? Is a value that Student A used missing from the
   description? Did Student B answer the same every time?
4. **Judge with proof.** An AI judge labels the description and must quote the exact words as proof. Code
   checks the quote is really in the description.
5. **Fix.** An unfair FairAlt description is rewritten, up to 3 versions. The fixer is told the exact
   problem, such as which banned word or which missing fact.
6. **A human decides when unsure.** The question goes to a person when the code and the judge disagree,
   Student B is right only some of the time, or the judge's quote is not in the description.

| Verdict | Meaning |
|---|---|
| 🟢 Fair | Both students reach the right answer, and Student B had to reason |
| 🔴 Gives answer away | The description states the answer or conclusion |
| 🟠 Missing information | Student A is right, but Student B cannot answer |
| Check failed | Student A is wrong, so the question cannot be checked |
| Unsure | The checks disagree or Student B was inconsistent; a person decides |

### The gate

Every question moves through five stages, and nothing goes live without a person:

**Waiting → Tested → Needs review → Approved → Published**

A teacher approves (and may edit) the description, then **Publish** issues a **Fairness Report** with an
ID such as `FA-20261104_124135-Q01`.

## The app

A sidebar holds the three pages, the **Run** picker and the run's details.

- **Overview**: a headline built from the run, four stat cards, the gate with a count per stage, and a
  table of questions with the Standard AI and FairAlt verdicts and each question's stage. It has filter
  tabs (All, To review, Approved, Published) and a search box. **Check all questions** runs every question;
  **Start empty run** lets you check them one at a time.
- **Review**: one question at a time. **Check this question** runs it live, step by step. The page shows both
  descriptions (the leaking words underlined, plus **Listen** to hear what a screen-reader student hears),
  a **Fairness checks** table (✓ / ✗ / ?) with the judge's proof, the facts that were kept or removed, both
  students' answers, then **Approve**, **Publish** and the question's **Fairness Report**.
- **Dashboard**: measured live from the run. Fair descriptions (FairAlt vs standard AI), time and cost per
  image against doing it by hand, an impact row (leaks stopped, saved on this run, fair first time,
  published), and a **Projected impact** calculator with sliders. The **Fairness Report** button covers all
  published questions.

Time and cost are measured, not assumed: AI time and tokens per question, plus how long the reviewer
took to approve. Only the by-hand figures (15 minutes per image, $30 per hour) are estimates; they are
the slider defaults in `impact.py`.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then set AI_PROVIDER and your key
streamlit run app.py
```

Without the UI:

```bash
python pipeline.py                  # all 15 questions, saves results/run_<timestamp>.json
python pipeline.py --only q01,q05   # just a few
python -m pytest -q                 # tests (no API key needed)
```

In our last real run with Claude Opus 5.5, a question took about 40 seconds on average, because Student B
answers 3 times for every version. For a live demo, check one or two questions and show the rest from a
saved run.

### Settings (`.env`)

| Setting | What it does |
|---|---|
| `AI_PROVIDER` | `anthropic` (API key), `claude_code` (your Claude subscription, via the `claude` CLI), `openai`, `azure`, or `mock` |
| `ANTHROPIC_API_KEY` | key for `anthropic` (keep `.env` private; it is git-ignored) |
| `CLAUDE_MODEL` | defaults to `claude-opus-5-5` |
| `CLAUDE_EFFORT` | how hard Claude thinks per call: `low`, `medium` or `high` |
| `STUDENT_B_RUNS` | how many times Student B answers each description (default 3) |
| `STUDENT_B_MODEL` | optional smaller model for Student B (empty means the main model) |
| `PRICE_IN_PER_1M`, `PRICE_OUT_PER_1M` | token prices, used for the cost figures |
| `CLAUDE_CODE_BIN` | path to `claude` if it is not on your PATH (for `claude_code`) |

`mock` gives offline, scripted answers so you can test the pipeline and the UI without a key.
**Mock numbers are not real results.** Never use them in a pitch.

Claude takes no temperature setting, so two real runs can differ slightly. Record demos from a saved run.

## Project layout

```
app.py             entry point: page setup and navigation
ui/                the Streamlit app
  overview.py      Overview page
  review.py        Review page
  dashboard.py     Dashboard page
  components.py    shared pieces: pills, formatters, Listen, top bar, sidebar
  state.py         session state and what a reviewer does (approve, publish)
  theme.py         page setup; style.css is the stylesheet
  nav.py           the page registry
runstore.py        the saved run: files, the gate, approve/publish, summaries (no Streamlit)
pipeline.py        runs a question end to end and saves the run
ai_client.py       the only code that calls the model
writer.py          the standard AI and FairAlt writers, and the fact lister
students.py        Student A (image) and Student B (description only, several tries)
checks.py          the code checks and the final decision
judge.py           the AI judge and the answer-in-text check
fixer.py           rewrites an unfair description
impact.py          time, cost, leak and scale-up numbers for the dashboard
report.py          the Fairness Report (HTML)
questions.py       loads data/questions.json
mock_ai.py         offline scripted provider for tests
prompts/           one .txt per AI step; edit these to tune behaviour
data/              questions.json, banned_words.json and images/
assets/            logo and icon
scripts/           make_sample_images.py regenerates the sample images
tests/             pytest tests
results/           saved runs (run_<timestamp>.json), git-ignored audio cache
```

## Sample data

The 15 sample figures in `data/images/` are original, generated by `scripts/make_sample_images.py`, so
they carry no third-party licence. Each question in `data/questions.json` has a `type` (Graphs, Charts,
Diagrams, Geometry, Maps & timelines) that decides which banned words apply.

To use OpenStax figures (CC BY 4.0) instead, put the image in `data/images/`, update the matching entry in
`data/questions.json` (`question`, `image`, `answer`, `answer_type`, `type`, `options` for multiple
choice), and set `source` to the attribution line, for example "OpenStax College Algebra 2e, CC BY 4.0".
The mock provider only knows the bundled questions, so use a real provider after you swap them.
