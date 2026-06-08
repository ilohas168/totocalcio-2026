"""Grid-search the goal-supremacy scale (beta) and Elo/market blend (w_elo) to
best match the bookmaker champion-probability distribution. Lock the winner into
DEFAULT_PARAMS."""
import numpy as np
from tournament import load_data, simulate, build_third_assignment_table

d = load_data()
table = build_third_assignment_table(d["bracket"])
implied = (1.0 / d["odds"]); implied = implied / implied.sum()
names = d["names"]

betas = [0.0030, 0.0035, 0.0040, 0.0045]
ws = [0.25, 0.35, 0.45, 0.55]

print(f"  L1 distance of sim champ% to market champ% (lower=better), 25k sims")
print("  w_elo \\ beta " + "".join(f"{b:>9.4f}" for b in betas))
best = (1e9, None)
results = {}
for w in ws:
    row = []
    for b in betas:
        res = simulate(n_sims=25_000, data=d, table=table,
                       params={"beta": b, "w_elo": w})
        cp = np.bincount(res["champion"], minlength=48) / 25_000
        l1 = float(np.abs(cp - implied).sum())
        results[(w, b)] = (l1, cp)
        row.append(l1)
        if l1 < best[0]:
            best = (l1, (w, b))
    print(f"  {w:>5.2f}       " + "".join(f"{x:>9.3f}" for x in row))

w, b = best[1]
print(f"\n  BEST: w_elo={w}, beta={b}  (L1={best[0]:.3f})")
cp = results[(w, b)][1]
order = np.argsort(-cp)
print(f"\n  champion% at best calibration vs market:")
for i in order[:12]:
    print(f"    {names[i]:<16} sim {100*cp[i]:>5.1f}%   market {100*implied[i]:>5.1f}%")
