"""Recompute every data layer of the curated 'Totocalcio 2026.html' from
opponents.json + final_allocation.json and splice it back in, keeping the curated
structure/CSS/render untouched. Re-runnable: when a new participant is revealed,
add them to opponents.json (known=normal / outliers=contrarian) and run this.

Replaces: const FLOW / BALLOTS / RIVALS / RIVDOM, the hero+ticker headline numbers,
the participant-count notes, and the decision-log step count.
"""
import json
import re
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from sim.tournament import load_data, simulate, DATA
from optimize.allocate import (known_vectors, outlier_vectors, popularity,
                               sample_unknowns, vec_from_dict)

FILE = HERE / "Totocalcio 2026.html"

d = load_data()
opp = json.loads((DATA / "opponents.json").read_text())
names, idx = d["names"], d["idx"]
N = opp["n_players"]
res = simulate(n_sims=300_000, data=d, analyze=True)
ew, W = res["ewins"], res["wins"].astype(float)
S = W.shape[0]
implied = (1.0 / d["odds"]); implied /= implied.sum()
fifa = np.array([d["teams"][n]["fifa_rank"] for n in names], dtype=float)
ewr = {int(c): r + 1 for r, c in enumerate(np.argsort(-ew))}
FINAL = json.loads((HERE / "final_allocation.json").read_text())["allocation"]
vme = vec_from_dict(FINAL, idx)

# public participants: normal known (informs prior) + outliers + you
known_items = list(opp["known"].items())                 # A,B,C,D,E,G,...
outlier_items = list(opp.get("outliers", {}).items())    # F
ballots = known_items + outlier_items + [("あなた", FINAL)]
labels = [k for k, _ in ballots]
outlier_set = {k for k, _ in outlier_items}
display_names = opp.get("display_names", {})
user_name = opp.get("user_name", "あなた")
def disp(lab):
    return user_name if lab == "あなた" else display_names.get(lab, lab)
Vn = np.array([vec_from_dict(a, idx) for _, a in ballots])
NP = len(ballots)
assert NP == N, f"field not fully known: NP={NP}, N={N}"   # all ballots known now
S_vec = Vn.sum(0)                           # total points on each team across all N players
PW = N * Vn - S_vec                          # (N,48) per-win swing for each player
moveset = np.where(S_vec > 0)[0]             # only teams someone bet on
moveset = moveset[np.argsort(-ew[moveset])]

# net distribution per participant — EXACT (only randomness is the tournament W; no field sampling)
NET = PW @ W.T                               # (N, S) net points per sim per player


def stats_for(i):
    arr = NET[i]
    r = lambda x: int(round(float(x)))
    return {"mean": r(arr.mean()), "median": r(np.median(arr)), "best": r(arr.max()),
            "worst": r(arr.min()), "p5": r(np.percentile(arr, 5)), "p25": r(np.percentile(arr, 25)),
            "p75": r(np.percentile(arr, 75)), "p95": r(np.percentile(arr, 95)),
            "pos": int(round(100 * float((arr >= 0).mean())))}


STATS = {lab: stats_for(i) for i, lab in enumerate(labels)}

# P(1st) / mean-rank — exact ranking by dot product W·v (ties split fairly)
Rd = Vn @ W.T                                # (N, S) each player's raw score
ismax = (Rd == Rd.max(0))
P1 = 100 * (ismax / ismax.sum(0)).mean(1)
rank = np.array([float(((Rd > Rd[i]).sum(0) + 1).mean()) for i in range(NP)])
EV = [int(round(float(ew @ Vn[i]))) for i in range(NP)]


def feature(alloc, rows, evscore):
    """Friendly, fun one-liner about a ballot's character — no judgemental wording
    (everyone reads it). rows = that player's FLOW rows [nm,ew,pts,oth,perwin,total]."""
    items = sorted(alloc.items(), key=lambda kv: -kv[1])
    top = items[0][0]                                    # the 10-pt pick
    posr = max(rows, key=lambda r: r[4])                 # best per-win swing = money-maker
    negr = min(rows, key=lambda r: r[4])                 # worst per-win swing = biggest hit
    toprank = ewr[idx[top]]
    nbold = sum(1 for t, _ in items[:5] if ewr[idx[t]] > 12)   # weak teams placed high
    if evscore >= 185:
        style = "鉄板の本命型"
    elif evscore <= 169 or nbold >= 2:
        style = "ロマン砲・一発狙い"
    elif toprank > 6:
        style = "推しに賭けるロマン派"
    else:
        style = "本命軸＋ひと工夫"
    earn = f"推し={top}でガッツリ稼ぐ" if posr[0] == top else f"推し={top}・稼ぎ頭は{posr[0]}"
    return f"{style}。{earn}。{negr[0]}が勝つと大ダメージ"


# ---- build JS data objects ------------------------------------------------
FLOW = {}
for i, lab in enumerate(labels):
    vi = Vn[i]; rows = []
    for c in moveset:
        oth = (S_vec[c] - vi[c]) / (N - 1)
        perwin = N * vi[c] - S_vec[c]
        rows.append([names[c], round(float(ew[c]), 2), int(vi[c]), round(float(oth), 1),
                     int(round(float(perwin))), int(round(float(ew[c] * perwin)))])
    FLOW[disp(lab)] = {"stats": STATS[lab], "rows": rows,
                       "you": lab == "あなた", "joker": lab in outlier_set}

BALLOTS = []
for lab, alloc in ballots:
    you = lab == "あなた"
    BALLOTS.append({"id": lab, "name": disp(lab), "you": you, "joker": lab in outlier_set,
                    "picks": [[p, nm] for nm, p in sorted(alloc.items(), key=lambda x: -x[1])]})

order = sorted(range(NP), key=lambda i: -STATS[labels[i]]["pos"])   # by P(net>=0) desc
RIVALS = []
for i in order:
    lab = labels[i]; s = STATS[lab]
    RIVALS.append({"id": lab, "name": disp(lab), "you": lab == "あなた", "joker": lab in outlier_set,
                   "ev": EV[i], "p1": round(float(P1[i]), 1), "rank": round(float(rank[i]), 1),
                   "diag": feature(dict(ballots[i][1]), FLOW[disp(lab)]["rows"], EV[i]), **s})
lo = min(r["worst"] for r in RIVALS); hi = max(r["best"] for r in RIVALS)

# cheat-sheet matrix: per-win swing (N*v - S_C) for every player x every owned country
MATRIX = {
    "countries": [{"nm": names[c], "ew": round(float(ew[c]), 2)} for c in moveset],
    "rows": [{"name": disp(lab),
              "pw": [int(round(float(N * Vn[i][c] - S_vec[c]))) for c in moveset]}
             for i, lab in enumerate(labels)],
}

# ---- LIVE: standings + schedule from real match results --------------------
# wins so far (country -> count) under the pool rule, written by fetch_matches.py
try:
    real_wins = json.loads((DATA / "results.json").read_text()).get("wins", {})
except FileNotFoundError:
    real_wins = {}
Wreal = np.array([real_wins.get(n, 0) for n in names], dtype=float)   # (48,)
live = PW @ Wreal                                   # (N,) actual zero-sum net so far
STANDINGS = sorted(
    [{"name": disp(lab), "you": lab == "あなた", "joker": lab in outlier_set,
      "score": int(round(float(live[i]))), "mean": STATS[lab]["mean"]}
     for i, lab in enumerate(labels)],
    key=lambda r: (-r["score"], -r["mean"]))

try:
    sched = json.loads((DATA / "schedule.json").read_text())
    SCHEDULE = {"matches": sched["matches"],
                "finished": sum(1 for m in sched["matches"] if m["status"] == "FINISHED"),
                "asof": ""}
except FileNotFoundError:
    SCHEDULE = {"matches": [], "finished": 0, "asof": ""}
print(f"live: {int(Wreal.sum())} wins counted · {SCHEDULE['finished']}/104 matches finished · "
      f"leader={STANDINGS[0]['name']} {STANDINGS[0]['score']:+d}")

# headline numbers (single real field — no scenarios)
you_i = labels.index("あなた")
net = STATS[labels[you_i]]["mean"]
P1you = int(round(P1[you_i]))
champ = int(np.bincount(res["champion"], minlength=48).argmax())
champ_pct = int(round(100 * (res["champion"] == champ).mean()))

print(f"participants={labels}  N={N} (fully known)")
print(f"you: P(1位)={P1you}%  net={net:+d}  champ={names[champ]} {champ_pct}%")
for r in RIVALS:
    print(f"  {r['id']:<5} EV{r['ev']} P1 {r['p1']:>4}%  mean {r['mean']:+5d} best {r['best']:+5d} worst {r['worst']:+5d}")

# ============ tournament prediction (groups / odds / consistent bracket) =====
import collections
gp = res["gplace"]; reach = res["reach"]
rh = res["r32_home"]; ra = res["r32_away"]; wc = res["wincnt"]
groups = d["groups"]
GLET = sorted(groups.keys())
ROUNDS = [("R32", [73, 75, 74, 77, 83, 84, 81, 82, 76, 78, 79, 80, 86, 88, 85, 87]),
          ("R16", [89, 90, 93, 94, 91, 92, 95, 96]),
          ("準々", [97, 98, 99, 100]), ("準決", [101, 102]), ("決勝", [104])]
ko = d["bracket"]["knockout"]

# R32 slots first: greedy-unique so no team appears twice in the bracket
used = set(); r32_slot = {}
for m in ROUNDS[0][1]:
    for slot, dist in (("h", rh[m - 73]), ("a", ra[m - 73])):
        for t in np.argsort(-dist):
            if int(t) not in used:
                r32_slot[(m, slot)] = int(t); used.add(int(t)); break
r32_set = set(r32_slot.values())                       # the 32 teams in the bracket

# GROUPS: qualified green-dot = team is in the predicted R32 (groups<->bracket agree)
G_DATA = {L: [[names[t], int(round(100 * gp[t, 0])), int(round(100 * gp[t, 1])),
               int(round(100 * reach[t, 0])), 1 if t in r32_set else 0]
              for t in sorted(groups[L], key=lambda t: -gp[t, 0])] for L in GLET}

# ODDS: top 16 by champion prob, cols R16/QF/SF/Final/Champ
ODDS = [(names[t], [int(round(100 * reach[t, k])) for k in range(1, 6)])
        for t in np.argsort(-reach[:, 5])[:16]]

# BRACKET: propagate favorites up from the unique R32 — each winner advances to
# the next round it feeds, so no team can appear twice in any round.
winner = {}; BK_DATA = []
for rname, ms in ROUNDS:
    rmatches = []
    for m in ms:
        if 73 <= m <= 88:
            a, b = r32_slot[(m, "h")], r32_slot[(m, "a")]
        else:
            f1, f2 = ko[str(m)]; a, b = winner[f1], winner[f2]
        win = 0 if wc[m][a] >= wc[m][b] else 1
        winner[m] = a if win == 0 else b
        rmatches.append([names[a], names[b], win])
    BK_DATA.append([rname, rmatches])
    dup = [x for x, c in collections.Counter([t for mt in rmatches for t in mt[:2]]).items() if c > 1]
    assert not dup, f"bracket duplicate in {rname}: {dup}"

bracket_champ = winner[104]
fin = (winner[101], winner[102])
runner = fin[0] if fin[1] == bracket_champ else fin[1]
champ = bracket_champ                                  # keep hero/odds/bracket consistent
champ_pct = int(round(100 * wc[104][bracket_champ]))   # wincnt is already a fraction
champ_name = names[bracket_champ]; runner_name = names[runner]
print(f"bracket: champion={champ_name} {champ_pct}%  runner-up={runner_name}  (consistency OK)")

# ---- splice into the HTML -------------------------------------------------
html = FILE.read_text(encoding="utf-8")


def sub1(pattern, repl, s, flags=re.S):
    # repl may be a plain string (used literally — backslashes are NOT special) or
    # a callable that receives the match and returns the replacement.
    fn = repl if callable(repl) else (lambda m: repl)
    s2, n = re.subn(pattern, fn, s, count=1, flags=flags)
    assert n == 1, f"pattern not found: {pattern[:60]}"
    return s2


html = sub1(r"const FLOW=\{.*?\};\nconst BALLOTS=",
            "const FLOW=" + json.dumps(FLOW, ensure_ascii=False) + ";\nconst BALLOTS=", html)
html = sub1(r"const BALLOTS=\[.*?\];",
            "const BALLOTS=" + json.dumps(BALLOTS, ensure_ascii=False) + ";", html)
html = sub1(r"const RIVALS=\[.*?\];",
            "const RIVALS=" + json.dumps(RIVALS, ensure_ascii=False) + ";", html)
html = sub1(r"const RIVDOM=\[[^\]]*\];", f"const RIVDOM=[{lo},{hi}];", html)
html = sub1(r"const MATRIX=\{.*?\};",
            "const MATRIX=" + json.dumps(MATRIX, ensure_ascii=False) + ";", html)
html = sub1(r"const STANDINGS=\[.*?\];",
            "const STANDINGS=" + json.dumps(STANDINGS, ensure_ascii=False) + ";", html)
html = sub1(r"const SCHEDULE=\{.*?\};",
            "const SCHEDULE=" + json.dumps(SCHEDULE, ensure_ascii=False) + ";", html)

# (everyone-mode: the top hero stats strip and the ticker per-player/champion
#  callouts were removed from the HTML, so there is nothing to inject there)

# notes — field is fully known (deadline passed, no unknowns to model)
ball_note = f'全{N}人の確定予想（締切後・全員ぶん）。'
html = sub1(r'(<section id="pick">.*?<div class="note">).*?(</div>)',
            lambda m: m.group(1) + ball_note + m.group(2), html)
riv_note = (f'全{N}人の確定フィールドで評価。<b>終了した試合の結果を織り込んで毎回再計算</b>。'
            f'ベスト/ワースト＝<b>数学的に起こりうる最高/最低（理論値）</b>、平均/分布＝残り試合のシミュレーション。')
html = sub1(r'(<section id="rivals">.*?<div class="note">).*?(</div>)',
            lambda m: m.group(1) + riv_note + m.group(2), html)
model_note = (f'相手モデル = 全{N}人の予想が確定（締切後）＝相手を推測する不確実性なし。'
              f'試合結果のみがランダム。較正：sim優勝確率≈市場（スペイン≈14%、Spearman≈0.91）。')
html = sub1(r'(<li>)相手モデル = .*?(</li>)', lambda m: m.group(1) + model_note + m.group(2), html)

# (the decision-log / caveats section was removed; nothing to regenerate there)

# --- tournament: groups / odds / bracket / champion (all from one sim) ---
g_js = "const G={\n" + ",\n".join(f"{L}:" + json.dumps(G_DATA[L], ensure_ascii=False)
                                   for L in GLET) + "\n};"
html = sub1(r"const G=\{.*?\};", g_js, html)
html = sub1(r"const BK=\[.*?\];", "const BK=" + json.dumps(BK_DATA, ensure_ascii=False) + ";", html)

odds_rows = ""
for nm, cols in ODDS:
    cells = "".join(f'<td data-o="{v}"{" data-champ" if k == 4 else ""}>{v}</td>'
                    for k, v in enumerate(cols))
    odds_rows += f'<tr><td class="l">{nm}</td>{cells}</tr>'
html = sub1(r'(id="oddsTbl"><thead>.*?</thead><tbody>).*?(</tbody>)',
            lambda m: m.group(1) + odds_rows + m.group(2), html)

fl = re.search(r"const FLAGS=\{(.*?)\};", html, re.S).group(1)
def flag_of(nm):
    mm = re.search(r'(?:"%s"|%s)\s*:\s*"([^"]+)"' % (re.escape(nm), re.escape(nm)), fl)
    return mm.group(1) if mm else ""
cf, rf = flag_of(champ_name), flag_of(runner_name)
html = sub1(r"cc\.innerHTML=`.*?`;",
            'cc.innerHTML=`<div class="lab">予想優勝</div><div class="ico">🏆</div>'
            f'<div class="cn"><span class="flag" style="font-size:28px">{cf}</span><br>{champ_name}</div>'
            f'<div class="pct">優勝確率 {champ_pct}% · 決勝 vs {rf} {runner_name}</div>`;', html)

# (everyone-mode: the hero champion stat & ticker champion callouts were removed;
#  the bracket section keeps its own champion card, injected just above)

FILE.write_text(html, encoding="utf-8")
(HERE.parent / "index.html").write_text(html, encoding="utf-8")   # repo root → GitHub Pages
print(f"\nrefreshed -> {FILE.name} (+ index.html) ({len(html):,} chars)")
