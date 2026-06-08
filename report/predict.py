"""Predicted group outcomes + knockout bracket + how-far-each-team-goes,
from the current calibrated model."""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sim.tournament import load_data, simulate, GROUP_LETTERS

d = load_data()
res = simulate(n_sims=150_000, data=d, analyze=True)
names = d["names"]
gp, reach = res["gplace"], res["reach"]
rh, ra = res["r32_home"], res["r32_away"]
groups, bracket = d["groups"], d["bracket"]

print("=" * 60)
print("  GROUP STAGE — finishing probabilities (150k sims)")
print("=" * 60)
for L in GROUP_LETTERS:
    order = sorted(d["groups"][L], key=lambda t: -gp[t, 0])
    print(f"\n  Group {L}   {'win%':>16}{'2nd%':>6}{'3rd%':>6}{'adv%':>7}")
    for rank, t in enumerate(order):
        star = " *" if reach[t, 0] >= 0.5 else "  "
        print(f"   {rank+1}.{star}{names[t]:<14}{100*gp[t,0]:>10.0f}%{100*gp[t,1]:>5.0f}%"
              f"{100*gp[t,2]:>5.0f}%{100*reach[t,0]:>6.0f}%")

print("\n" + "=" * 60)
print("  PREDICTED ROUND OF 32 — most likely team in each slot")
print("=" * 60)
for mi, m in enumerate(bracket["r32"]):
    hm, am = int(np.argmax(rh[mi])), int(np.argmax(ra[mi]))
    print(f"  M{m['match']:>3}: {names[hm]:<14} ({100*rh[mi][hm]:>2.0f}%)  vs  "
          f"{names[am]:<14} ({100*ra[mi][am]:>2.0f}%)")

print("\n" + "=" * 60)
print("  HOW FAR EACH TEAM GOES — P(reach round)")
print("=" * 60)
print(f"  {'team':<16}{'R32':>6}{'R16':>6}{'QF':>6}{'SF':>6}{'Final':>7}{'WIN':>7}")
for t in np.argsort(-reach[:, 5])[:20]:
    r = reach[t]
    print(f"  {names[t]:<16}{100*r[0]:>5.0f}%{100*r[1]:>5.0f}%{100*r[2]:>5.0f}%"
          f"{100*r[3]:>5.0f}%{100*r[4]:>6.0f}%{100*r[5]:>6.1f}%")

# chart: P(reach round) stacked for top 16 by title odds
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    top = np.argsort(-reach[:, 5])[:16][::-1]
    labels = ["R16", "QF", "SF", "Final", "Champ"]
    cols = ["#cfe8ff", "#9ecae1", "#6baed6", "#3182bd", "#08519c"]
    fig, ax = plt.subplots(figsize=(9, 7))
    y = np.arange(len(top))
    for k, (lab, col) in enumerate(zip(labels, cols)):
        ax.barh(y, [100 * reach[t, k + 1] for t in top], color=col,
                label=lab, height=0.82, left=0)
    ax.set_yticks(y); ax.set_yticklabels([names[t] for t in top], fontsize=8)
    ax.set_xlabel("probability (%)"); ax.legend(ncol=5, fontsize=8, loc="lower right")
    ax.set_title("2026 WC — how far each team is expected to go (nested P)")
    fig.tight_layout()
    fig.savefig(Path(__file__).resolve().parent / "progression.png", dpi=130)
    print("\n  chart -> report/progression.png")
except Exception as e:
    print("chart skipped:", e)
