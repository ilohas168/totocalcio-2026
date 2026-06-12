"""Conditional ベストケース/ワーストケース refresh — run in CI between
fetch_matches.py and refresh_live.py.

best/worst = THEORETICAL bounds (sim.theoretical): the exact max/min final
score over all feasible completions of the tournament given the finished
results — deterministic, noise-free, monotone. mean/median/percentiles come
from a Monte-Carlo re-sim conditioned on the same finished results
(sim.tournament with fixed=...). Splices the stats into FLOW / RIVALS /
RIVDOM of both HTML files and writes data/live_stats.json (per-player means,
used by refresh_live.py as the standings tiebreak).

Cheap when nothing new finished: a fingerprint of the finished-match set is
stored in live_stats.json and the whole script no-ops if it matches.
Delete data/live_stats.json to force a recompute.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from sim.tournament import load_data, simulate, PAIRS_GROUP
from sim.theoretical import theoretical_bounds_all

DATA = ROOT / "data"
FILES = [HERE / "Totocalcio 2026.html", ROOT / "index.html"]
STATS_F = DATA / "live_stats.json"
N_SIMS = 300_000

# ---- fingerprint: skip everything if no new final result -------------------
sched = json.loads((DATA / "schedule.json").read_text(encoding="utf-8"))["matches"]
fin = [m for m in sched if m["status"] == "FINISHED" and m.get("score")
       and m.get("winner") is not None]
fp = hashlib.sha256(json.dumps(
    sorted(([m["id"], m["score"], m.get("pens"), m["winner"]] for m in fin),
           key=lambda r: r[0])).encode()).hexdigest()
if STATS_F.exists():
    try:
        if json.loads(STATS_F.read_text())["fingerprint"] == fp:
            print(f"cases: no new results ({len(fin)} finished) — skip")
            raise SystemExit(0)
    except (KeyError, ValueError):
        pass

# ---- build the conditioning from real results ------------------------------
d = load_data()
tidx = d["idx"]
groups_nm = json.loads((DATA / "groups.json").read_text())   # letter -> [4 names]
pair_of = {ij: k for k, ij in enumerate(PAIRS_GROUP)}
fx_group, fx_ko = {}, {}
for m in fin:
    h, a = m["home"], m["away"]
    if m["stage"] == "GROUP_STAGE":
        L = m["group"].replace("GROUP_", "")
        gl = groups_nm[L]
        i, j = gl.index(h), gl.index(a)
        gh, ga = m["score"]
        if i < j:
            fx_group[(L, pair_of[(i, j)])] = (gh, ga)
        else:
            fx_group[(L, pair_of[(j, i)])] = (ga, gh)
    else:
        if m["winner"] not in ("HOME_TEAM", "AWAY_TEAM"):
            continue
        w = tidx[h] if m["winner"] == "HOME_TEAM" else tidx[a]
        fx_ko.setdefault(m["stage"], []).append((tidx[h], tidx[a], w))

print(f"cases: conditioning on {len(fx_group)} group + "
      f"{sum(len(v) for v in fx_ko.values())} KO results, {N_SIMS} sims")
res = simulate(n_sims=N_SIMS, data=d, fixed={"group": fx_group, "ko": fx_ko})
W = res["wins"].astype(float)

# ---- per-player final-score distribution (same math as refresh_dashboard) --
opp = json.loads((DATA / "opponents.json").read_text(encoding="utf-8"))
FINAL = json.loads((HERE / "final_allocation.json").read_text(encoding="utf-8"))["allocation"]
N = opp["n_players"]
ballots = list(opp["known"].items()) + list(opp.get("outliers", {}).items()) + [("あなた", FINAL)]
display_names = opp.get("display_names", {})
user_name = opp.get("user_name", "あなた")
def disp(lab):
    return user_name if lab == "あなた" else display_names.get(lab, lab)

def vec(alloc):
    v = np.zeros(48)
    for c, pts in alloc.items():
        v[tidx[c]] = pts
    return v

assert len(ballots) == N, f"field not fully known: {len(ballots)} != {N}"
Vn = np.array([vec(a) for _, a in ballots])
S_vec = Vn.sum(0)
PW = N * Vn - S_vec
NET = PW @ W.T                                 # (players, sims) final net points

def stats_for(i):
    arr = NET[i]
    r = lambda x: int(round(float(x)))
    return {"mean": r(arr.mean()), "median": r(np.median(arr)), "best": r(arr.max()),
            "worst": r(arr.min()), "p5": r(np.percentile(arr, 5)), "p25": r(np.percentile(arr, 25)),
            "p75": r(np.percentile(arr, 75)), "p95": r(np.percentile(arr, 95)),
            "pos": int(round(100 * float((arr >= 0).mean())))}

STATS = {disp(lab): stats_for(i) for i, (lab, _) in enumerate(ballots)}

# best/worst -> exact theoretical bounds (noise-free; the MC extremes above are
# just samples and must lie inside them — assert that as a cross-check)
print(f"cases: solving theoretical bounds ({2 * len(ballots)} optimizations)…")
THEO = theoretical_bounds_all(PW, d=d, matches=sched)
for i, (lab, _) in enumerate(ballots):
    b, w = THEO[i]
    assert b >= NET[i].max() - 1e-6 and w <= NET[i].min() + 1e-6, \
        f"theoretical bounds inconsistent for {lab}: ({b},{w}) vs MC ({NET[i].max()},{NET[i].min()})"
    STATS[disp(lab)]["best"] = int(b)
    STATS[disp(lab)]["worst"] = int(w)

# ---- splice into both HTML files -------------------------------------------
STAT_KEYS = ("mean", "median", "best", "worst", "p5", "p25", "p75", "p95", "pos")
for f in FILES:
    html = f.read_text(encoding="utf-8")

    m = re.search(r"const FLOW=(\{.*?\});\nconst BALLOTS=", html, re.S)
    flow = json.loads(m.group(1))
    for nm in flow:
        flow[nm]["stats"] = STATS[nm]
    html = html[:m.start(1)] + json.dumps(flow, ensure_ascii=False) + html[m.end(1):]

    m = re.search(r"const RIVALS=(\[.*?\]);", html, re.S)
    rivals = json.loads(m.group(1))
    for r in rivals:
        r.update({k: STATS[r["name"]][k] for k in STAT_KEYS})
    html = html[:m.start(1)] + json.dumps(rivals, ensure_ascii=False) + html[m.end(1):]

    lo = min(s["worst"] for s in STATS.values())
    hi = max(s["best"] for s in STATS.values())
    html, n = re.subn(r"const RIVDOM=\[[^\]]*\];", f"const RIVDOM=[{lo},{hi}];", html, count=1)
    assert n == 1, "RIVDOM not found"
    f.write_text(html, encoding="utf-8")

STATS_F.write_text(json.dumps(
    {"fingerprint": fp, "finished": len(fin), "n_sims": N_SIMS,
     "mean": {nm: s["mean"] for nm, s in STATS.items()}},
    ensure_ascii=False), encoding="utf-8")
you = disp("あなた")
print(f"cases: refreshed {len(FILES)} files — {you}: best {STATS[you]['best']:+d} "
      f"worst {STATS[you]['worst']:+d} mean {STATS[you]['mean']:+d}")
