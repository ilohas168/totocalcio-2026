"""Custom allocation: Portugal pinned at 10, Türkiye included, France kept for
defense. Optimizes the rest for P(1st) vs the FIFA-ranking field, and prints
variants so the cost of each constraint is visible."""
import sys
import json
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sim.tournament import simulate, load_data, DATA
from optimize.allocate import (build_field_draws, field_ownership, gpp_optimize,
                               seeded_start, p_first, ev_index, ev_optimal)

d = load_data()
opp = json.loads((DATA / "opponents.json").read_text())
names, idx = d["names"], d["idx"]
res = simulate(n_sims=80_000, data=d)
ew, W = res["ewins"], res["wins"].astype(float)
implied = (1.0 / d["odds"]); implied /= implied.sum()
fifa_rank = np.array([d["teams"][n]["fifa_rank"] for n in names], dtype=float)
rng = np.random.default_rng(2026)
draws = build_field_draws(opp, idx, implied, fifa_rank, W, rng, n_draws=20)
fo = field_ownership(opp, idx, implied, fifa_rank, rng) / 16.0


def report(label, order, pts):
    v = np.zeros(48); v[order] = pts
    print(f"\n{label}\n  P(1st)={100*p_first(v, W, draws):.1f}%   EV={ev_index(v, ew):.1f}")
    for c, p in sorted(zip(order, pts), key=lambda x: -x[1]):
        tag = "  <-favorite" if names[c] in opp["user_favorites"] else (
              "  <-France(defense)" if names[c] == "France" else "")
        print(f"    {int(p):>2} -> {names[c]:<14} E[W]={ew[c]:.2f}  field {fo[c]:.1f}/player{tag}")


pin = {idx["Portugal"]: 10}

# B for reference
g_o, g_p, _ = gpp_optimize(*ev_optimal(ew), W, draws)
report("REFERENCE B (recommended so far)", g_o, g_p)

# Requested: Portugal=10, Türkiye in, France defended, optimize rest
force = {idx["Portugal"], idx["Türkiye"], idx["France"]}
o, p = seeded_start(list(force), ew, pin=pin)
o, p, _ = gpp_optimize(o, p, W, draws, force=force, pinned=set(pin))
report("REQUESTED: Portugal=10 + Türkiye + France(defense)", o, p)

# Variant: Portugal=10 + all 5 favorites + France defended
favs = [idx[n] for n in opp["user_favorites"]]
force2 = set(favs) | {idx["France"]}
o2, p2 = seeded_start(favs, ew, pin=pin)
o2, p2, _ = gpp_optimize(o2, p2, W, draws, force=force2, pinned=set(pin))
report("VARIANT: Portugal=10 + all 5 favorites + France(defense)", o2, p2)
