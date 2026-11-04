"""Generate the 15 sample question images into data/images/.

These are original placeholder figures (no third-party content) whose answers
are known exactly. Swap any of them for OpenStax figures later and update
data/questions.json to match.

Run: python scripts/make_sample_images.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse, FancyArrow, Polygon, Rectangle

OUT = Path(__file__).resolve().parent.parent / "data" / "images"
OUT.mkdir(parents=True, exist_ok=True)


def save(fig, name):
    fig.savefig(OUT / name, dpi=110, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def q01_slope():
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([-1, 4], [-1, 9], color="tab:blue", lw=2)
    ax.plot([0, 3], [1, 7], "o", color="black")
    ax.annotate("(0, 1)", (0, 1), textcoords="offset points", xytext=(8, -12))
    ax.annotate("(3, 7)", (3, 7), textcoords="offset points", xytext=(8, -12))
    ax.set_xlim(-1, 5); ax.set_ylim(-1, 9)
    ax.set_xticks(range(-1, 6)); ax.set_yticks(range(-1, 10))
    ax.grid(True, alpha=0.4); ax.axhline(0, color="k", lw=1); ax.axvline(0, color="k", lw=1)
    ax.set_xlabel("x"); ax.set_ylabel("y")
    save(fig, "q01_slope.png")


def q02_bar():
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    rain = [62, 48, 71, 94, 83, 55]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(months, rain, color="tab:green")
    for i, v in enumerate(rain):
        ax.text(i, v + 1.5, str(v), ha="center")
    ax.set_title("Monthly Rainfall in Riverton"); ax.set_ylabel("Rainfall (mm)")
    ax.set_ylim(0, 110)
    save(fig, "q02_bar.png")


def q03_trend():
    years = [2015, 2016, 2017, 2018, 2019, 2020]
    enrol = [1200, 1260, 1310, 1395, 1440, 1520]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(years, enrol, marker="o", color="tab:purple")
    for x, y in zip(years, enrol):
        ax.annotate(str(y), (x, y), textcoords="offset points", xytext=(0, 8), ha="center")
    ax.set_title("Lakeside College Enrollment"); ax.set_xlabel("Year"); ax.set_ylabel("Students")
    ax.set_ylim(1100, 1600)
    save(fig, "q03_trend.png")


def q04_pie():
    labels = ["Housing 35%", "Food 20%", "Transport 15%", "Savings 10%", "Other 20%"]
    sizes = [35, 20, 15, 10, 20]
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.pie(sizes, labels=labels, startangle=90, counterclock=False)
    ax.set_title("Monthly Household Budget")
    save(fig, "q04_pie.png")


def q05_hist():
    bins = ["60–69", "70–79", "80–89", "90–100"]
    counts = [4, 9, 7, 3]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(bins, counts, width=1.0, edgecolor="black", color="tab:orange")
    ax.set_title("Exam Scores, Class 9B"); ax.set_xlabel("Score"); ax.set_ylabel("Number of students")
    ax.set_yticks(range(0, 11)); ax.grid(axis="y", alpha=0.4)
    save(fig, "q05_hist.png")


def q06_cell():
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.add_patch(Ellipse((0.5, 0.5), 0.9, 0.75, fill=False, lw=3, color="tab:green"))
    ax.add_patch(Circle((0.45, 0.52), 0.13, color="tab:purple", alpha=0.8))
    ax.add_patch(Circle((0.45, 0.52), 0.04, color="black"))
    ax.add_patch(Ellipse((0.72, 0.35), 0.16, 0.08, color="tab:red", alpha=0.7))
    ax.add_patch(Ellipse((0.25, 0.3), 0.14, 0.07, color="tab:red", alpha=0.7))
    ax.add_patch(Circle((0.7, 0.66), 0.08, color="lightblue", alpha=0.9))
    for label, xy, txt in [("A", (0.45, 0.52), (0.05, 0.95)), ("B", (0.94, 0.5), (0.98, 0.85)),
                           ("C", (0.72, 0.35), (0.95, 0.12)), ("D", (0.7, 0.66), (0.4, 0.97))]:
        ax.annotate(label, xy, xytext=txt, fontsize=14, fontweight="bold",
                    arrowprops=dict(arrowstyle="-", color="black"))
    ax.set_xlim(0, 1.05); ax.set_ylim(0, 1.05); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("Diagram of an animal cell")
    save(fig, "q06_cell.png")


def q07_circuit():
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot([0, 0, 6, 6, 0], [0, 4, 4, 0, 0], color="black", lw=2)
    # battery on left side
    ax.plot([0, 0], [1.6, 2.4], color="white", lw=4)
    ax.plot([-0.4, 0.4], [2.4, 2.4], color="black", lw=3)
    ax.plot([-0.2, 0.2], [1.6, 1.6], color="black", lw=3)
    ax.text(-0.6, 2.0, "12 V", ha="right", va="center", fontsize=12)
    ax.text(0.5, 2.5, "+", fontsize=12); ax.text(0.3, 1.3, "−", fontsize=12)
    for x, label in [(2, "2 Ω"), (4, "4 Ω")]:
        ax.add_patch(Rectangle((x - 0.5, 3.75), 1.0, 0.5, facecolor="white", edgecolor="black", lw=2))
        ax.text(x, 4.5, label, ha="center", fontsize=12)
    ax.set_xlim(-1.5, 7); ax.set_ylim(-0.5, 5); ax.axis("off"); ax.set_aspect("equal")
    ax.set_title("Circuit diagram")
    save(fig, "q07_circuit.png")


def q08_forces():
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.add_patch(Rectangle((-0.5, -0.5), 1, 1, facecolor="lightgray", edgecolor="black"))
    ax.add_patch(FancyArrow(0.5, 0, 2.0, 0, width=0.06, head_width=0.25, color="tab:blue"))
    ax.add_patch(FancyArrow(-0.5, 0, -1.0, 0, width=0.06, head_width=0.25, color="tab:red"))
    ax.text(1.5, 0.25, "10 N", ha="center", fontsize=12)
    ax.text(-1.0, 0.25, "4 N", ha="center", fontsize=12)
    ax.text(0, -0.75, "Box on a frictionless floor", ha="center")
    ax.set_xlim(-2, 3); ax.set_ylim(-1, 1); ax.set_aspect("equal"); ax.axis("off")
    save(fig, "q08_forces.png")


def q09_lens():
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.axhline(0, color="black", lw=1)
    ax.add_patch(Ellipse((0, 0), 0.8, 6, fill=False, color="tab:blue", lw=2))
    for f in (-10, 10):
        ax.plot(f, 0, "ko"); ax.text(f, -0.8, "F", ha="center")
    ax.add_patch(FancyArrow(-30, 0, 0, 2, width=0.3, head_width=1.2, head_length=0.5, color="tab:red"))
    ax.text(-30, 2.6, "Object", ha="center")
    ax.annotate("", (-30, -2), (0, -2), arrowprops=dict(arrowstyle="<->"))
    ax.text(-15, -2.6, "30 cm", ha="center")
    ax.annotate("", (0, -3.2), (10, -3.2), arrowprops=dict(arrowstyle="<->"))
    ax.text(5, -3.8, "f = 10 cm", ha="center")
    ax.text(0, 3.4, "Converging lens", ha="center")
    ax.set_xlim(-35, 35); ax.set_ylim(-4.2, 4.2); ax.axis("off")
    save(fig, "q09_lens.png")


def q10_supply_demand():
    q = [0, 80]
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    ax.plot(q, [10, 2], label="Demand", color="tab:blue", lw=2)
    ax.plot(q, [2, 10], label="Supply", color="tab:red", lw=2)
    ax.text(78, 2.4, "D", color="tab:blue", fontsize=12); ax.text(78, 9.3, "S", color="tab:red", fontsize=12)
    ax.set_xlabel("Quantity (thousands of units)"); ax.set_ylabel("Price ($)")
    ax.set_xticks(range(0, 81, 10)); ax.set_yticks(range(0, 11))
    ax.grid(True, alpha=0.4); ax.set_xlim(0, 80); ax.set_ylim(0, 11)
    ax.set_title("Market for Notebooks")
    save(fig, "q10_supply_demand.png")


def q11_scatter():
    hours = [1, 2, 2, 3, 4, 4, 5, 6, 6, 7, 8, 9]
    score = [52, 55, 60, 61, 66, 63, 70, 72, 76, 78, 83, 88]
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    ax.scatter(hours, score, color="tab:blue")
    ax.set_xlabel("Hours studied"); ax.set_ylabel("Test score")
    ax.set_title("Study Time and Test Scores"); ax.grid(True, alpha=0.3)
    save(fig, "q11_scatter.png")


def q12_pyramid():
    groups = ["0–9", "10–19", "20–29", "30–39", "40–49", "50–59", "60+"]
    male = [5.1, 5.6, 6.8, 6.0, 4.9, 3.8, 3.0]
    female = [4.9, 5.4, 7.2, 6.3, 5.0, 4.1, 3.9]
    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.barh(groups, [-m for m in male], color="tab:blue", label="Male")
    ax.barh(groups, female, color="tab:pink", label="Female")
    for i, (m, f) in enumerate(zip(male, female)):
        ax.text(-m - 0.2, i, f"{m}", va="center", ha="right", fontsize=8)
        ax.text(f + 0.2, i, f"{f}", va="center", fontsize=8)
    ax.set_xlim(-9, 9); ax.set_xticks([-8, -4, 0, 4, 8]); ax.set_xticklabels(["8", "4", "0", "4", "8"])
    ax.set_xlabel("Population (%)"); ax.set_ylabel("Age group"); ax.legend(loc="lower right")
    ax.set_title("Population Pyramid, Country X")
    save(fig, "q12_pyramid.png")


def q13_angle():
    fig, ax = plt.subplots(figsize=(5, 4))
    pts = [(0, 0), (6, 0), (2.2, 3.8)]
    ax.add_patch(Polygon(pts, fill=False, lw=2))
    ax.text(0.55, 0.2, "50°", fontsize=13)
    ax.text(5.0, 0.2, "60°", fontsize=13)
    ax.text(2.05, 3.05, "x", fontsize=15, style="italic")
    ax.set_xlim(-0.5, 6.5); ax.set_ylim(-0.5, 4.3); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("Triangle (not drawn to scale)")
    save(fig, "q13_angle.png")


def q14_river():
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.add_patch(Rectangle((0, 0), 10, 10, facecolor="#eef6e4"))
    xs = [1.5, 2.5, 3.2, 4.5, 5.2, 6.4, 7.3, 8.2]
    ys = [8.5, 7.9, 7.0, 6.2, 4.8, 4.0, 2.9, 2.0]
    ax.plot(xs, ys, color="tab:blue", lw=4)
    for mx in (0.8, 1.6, 2.4):
        ax.add_patch(Polygon([(mx - 0.4, 8.6), (mx, 9.4), (mx + 0.4, 8.6)], color="saddlebrown"))
    ax.text(1.6, 9.6, "Granite Mountains", ha="center", fontsize=9)
    ax.text(2.0, 7.4, "Source", fontsize=9)
    ax.add_patch(Ellipse((8.6, 1.6), 1.8, 1.1, color="tab:blue", alpha=0.6))
    ax.text(8.6, 0.6, "Lake Mira (mouth)", ha="center", fontsize=9)
    ax.text(5.6, 5.2, "Silver River", fontsize=9, rotation=-45)
    ax.annotate("N", xy=(9.2, 9.6), xytext=(9.2, 8.4), ha="center", fontsize=12, fontweight="bold",
                arrowprops=dict(arrowstyle="->", lw=2))
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("Map of the Silver River valley")
    save(fig, "q14_river.png")


def q15_timeline():
    events = [(1820, "Town founded"), (1838, "School built"), (1855, "Railway arrives"), (1871, "Bridge opens")]
    fig, ax = plt.subplots(figsize=(7, 2.6))
    ax.axhline(0, color="black", lw=2)
    for i, (yr, name) in enumerate(events):
        up = 1 if i % 2 == 0 else -1
        ax.plot([yr, yr], [0, 0.5 * up], color="gray")
        ax.plot(yr, 0, "o", color="tab:red")
        ax.text(yr, 0.6 * up, f"{name}\n{yr}", ha="center", va="bottom" if up > 0 else "top", fontsize=9)
    ax.set_xlim(1810, 1880); ax.set_ylim(-1.4, 1.4); ax.axis("off")
    ax.set_title("History of Millbrook")
    save(fig, "q15_timeline.png")


if __name__ == "__main__":
    for fn in [q01_slope, q02_bar, q03_trend, q04_pie, q05_hist, q06_cell, q07_circuit, q08_forces,
               q09_lens, q10_supply_demand, q11_scatter, q12_pyramid, q13_angle, q14_river, q15_timeline]:
        fn()
    print(f"Wrote {len(list(OUT.glob('*.png')))} images to {OUT}")
