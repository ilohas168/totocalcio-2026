"""
Allocation optimizer for the 17-player family totocalcio.

Objectives (see README math):
  - EV-optimal: maximize expected NET points. Reduces to rank-by-E[W],
    INDEPENDENT of opponents (the -sum_C W_C*S_C and ownership terms are
    constant w.r.t. your choice). This is the "steady" play.
  - 1st-place / GPP-optimal: maximize P(finishing 1st) among 17 players.
    With a chalk-heavy field, player ranking within a simulated tournament is
    decided by the raw dot product W[s]·v, so DIFFERENTIATION toward high-E[W],
    low-owned teams raises P(1st). This is the "glory" play.

The field = 5 known allocations + 11 modeled unknowns (chalk + noise, drawn from
a popularity prior built from known ownership and market odds).
"""
from __future__ import annotations
import sys
import json
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sim.tournament import simulate, load_data, DATA  # noqa: E402

WEIGHTS = np.arange(10, 0, -1)


# ----------------------------------------------------------------------------
# Allocations <-> 48-vectors
# ----------------------------------------------------------------------------
def vec_from_dict(alloc, idx):
    v = np.zeros(48)
    for name, pts in alloc.items():
        v[idx[name]] = pts
    return v


def alloc_from_order(order, pts, names):
    return {names[c]: int(pts[k]) for k, c in enumerate(order)}


def ev_optimal(ewins):
    o = np.argsort(-ewins)[:10]
    return list(o), list(WEIGHTS)


# ----------------------------------------------------------------------------
# Opponent field model
# ----------------------------------------------------------------------------
def known_vectors(opp, idx):
    """The 'normal' known players, whose behaviour informs the popularity prior."""
    return [vec_from_dict(a, idx) for a in opp["known"].values()]


def outlier_vectors(opp, idx):
    """Known but idiosyncratic players (e.g. the contrarian F). They count as real
    competitors in the field, but are kept OUT of the prior so they do not distort
    our model of how the still-unknown players pick (don't assume the rest copy F)."""
    return [vec_from_dict(a, idx) for a in opp.get("outliers", {}).values()]


def popularity(known_vecs, implied, fifa_rank):
    """Prior over how an unknown family member allocates. The family are casual
    fans who pick mostly by FIFA WORLD RANKING, so FIFA rank dominates, anchored
    by how the 5 known players actually allocated (and a little market signal)."""
    def norm(x):
        return x / x.sum()
    s_known = np.sum(known_vecs, axis=0)
    fifa_pop = 1.0 / fifa_rank                      # FIFA #1 most likely picked
    p = 0.50 * norm(fifa_pop) + 0.40 * norm(s_known) + 0.10 * norm(implied)
    return p + 1e-4


def sample_unknowns(n, pop, rng, sigma=0.55):
    """Each unknown picks top-10 by noisy popularity, weights 10..1 by that order."""
    out = []
    for _ in range(n):
        noisy = np.log(pop) + rng.normal(0, sigma, size=48)
        order = np.argsort(-noisy)[:10]
        v = np.zeros(48)
        v[order] = WEIGHTS
        out.append(v)
    return out


def build_field_draws(opp, idx, implied, fifa_rank, W, rng, n_draws=6):
    """Returns a list of opp_scores arrays, each shape (16, S): the known players
    (normal + outliers) plus freshly-sampled unknown FIFA-ranking-driven opponents,
    projected onto W. The prior is built from the NORMAL known players only."""
    kv = known_vectors(opp, idx)
    ov = outlier_vectors(opp, idx)
    fixed = kv + ov
    n_unknown = opp["n_players"] - 1 - len(fixed)
    pop = popularity(kv, implied, fifa_rank)
    fixed_scores = np.array([W @ v for v in fixed])           # (len(fixed), S)
    draws = []
    for _ in range(n_draws):
        uv = sample_unknowns(n_unknown, pop, rng)
        unk_scores = np.array([W @ v for v in uv])            # (n_unknown, S)
        draws.append(np.vstack([fixed_scores, unk_scores]))   # (16, S)
    return draws


def field_ownership(opp, idx, implied, fifa_rank, rng, reps=400):
    """Expected total points the 16 opponents place on each team (known + modeled),
    i.e. S_C across the field. Used to size the defensive (anti-France) picks."""
    kv = known_vectors(opp, idx)
    ov = outlier_vectors(opp, idx)
    fixed = kv + ov
    n_unknown = opp["n_players"] - 1 - len(fixed)
    pop = popularity(kv, implied, fifa_rank)
    s_fixed = np.sum(fixed, axis=0)
    unk = np.mean([np.sum(sample_unknowns(n_unknown, pop, rng), axis=0)
                   for _ in range(reps)], axis=0)
    return s_fixed + unk


# ----------------------------------------------------------------------------
# Objectives
# ----------------------------------------------------------------------------
def first_place_share(r, opp_scores):
    greater = (opp_scores > r).sum(0)
    equal = (opp_scores == r).sum(0)
    return np.where(greater == 0, 1.0 / (1.0 + equal), 0.0).mean()


def p_first(v, W, draws):
    r = W @ v
    return float(np.mean([first_place_share(r, d) for d in draws]))


def ev_index(v, ewins):
    """Proportional to expected net points (drops the (N-1) factor & constant)."""
    return float(ewins @ v)


def gpp_optimize(start_order, start_pts, W, draws, force=frozenset(),
                 pinned=frozenset(), max_iter=30):
    """Local search maximizing P(1st). `force` = teams kept in the 10; `pinned`
    = teams whose point value is also frozen (used for the fan-tilt)."""
    chosen, pts = list(start_order), list(start_pts)
    forced = set(force) | set(pinned)
    pinset = set(pinned)

    def vec(ch, pt):
        v = np.zeros(48); v[ch] = pt; return v

    def sc(ch, pt):
        return p_first(vec(ch, pt), W, draws)

    best = sc(chosen, pts)
    for _ in range(max_iter):
        cb, cand = best, None
        for k, c in enumerate(chosen):
            if c in forced:
                continue
            for u in set(range(48)) - set(chosen):
                nc = chosen.copy(); nc[k] = u
                s = sc(nc, pts)
                if s > cb:
                    cb, cand = s, (nc, pts.copy())
        for a in range(10):
            if chosen[a] in pinset:
                continue
            for b in range(a + 1, 10):
                if chosen[b] in pinset:
                    continue
                npt = pts.copy(); npt[a], npt[b] = npt[b], npt[a]
                s = sc(chosen, npt)
                if s > cb:
                    cb, cand = s, (chosen.copy(), npt)
        if cand is None:
            break
        chosen, pts, best = cand[0], cand[1], cb
    order = [c for _, c in sorted(zip(pts, chosen), reverse=True)]
    pord = sorted(pts, reverse=True)
    return order, pord, best


def seeded_start(must_include, ewins, pin=None):
    """Seed = pinned teams (at fixed weights) + must_include + highest-E[W]
    fillers; remaining weights handed out by descending E[W]."""
    pin = dict(pin or {})
    chosen = [int(t) for t in pin]
    for t in list(must_include) + [int(c) for c in np.argsort(-ewins)]:
        if len(chosen) >= 10:
            break
        if int(t) not in chosen:
            chosen.append(int(t))
    chosen = chosen[:10]
    used = {int(w) for w in pin.values()}
    rem = [int(w) for w in WEIGHTS if int(w) not in used]
    nonpin = sorted([c for c in chosen if c not in pin], key=lambda c: -ewins[c])
    pmap = {int(t): int(w) for t, w in pin.items()}
    for c, w in zip(nonpin, rem):
        pmap[c] = w
    return chosen, [pmap[c] for c in chosen]


# ----------------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------------
def print_alloc(title, order, pts, names, ewins, field_own, W, draws):
    v = np.zeros(48); v[order] = pts
    print(f"\n  {title}:  P(1st)={100*p_first(v, W, draws):.1f}%  EV={ev_index(v, ewins):.1f}")
    for k, c in enumerate(order):
        print(f"    {int(pts[k]):>2} -> {names[c]:<16} E[W]={ewins[c]:.2f}  "
              f"field {field_own[c]:>4.0f}pt ({field_own[c]/16:.1f}/player)")


def main(n_sims=60_000, n_draws=8, seed=7):
    d = load_data()
    opp = json.loads((DATA / "opponents.json").read_text())
    res = simulate(n_sims=n_sims, data=d)
    names, ew, W, idx = d["names"], res["ewins"], res["wins"].astype(float), d["idx"]
    implied = (1.0 / d["odds"]); implied = implied / implied.sum()
    fifa_rank = np.array([d["teams"][n]["fifa_rank"] for n in names], dtype=float)
    rng = np.random.default_rng(seed)
    draws = build_field_draws(opp, idx, implied, fifa_rank, W, rng, n_draws)
    field_own = field_ownership(opp, idx, implied, fifa_rank, rng)
    ewr = {int(c): r for r, c in enumerate(np.argsort(-ew))}

    N = opp["n_players"]
    print(f"\n{'='*74}\n  TOTOCALCIO OPTIMIZER — N={N}, field = 5 known + {N-6} FIFA-rank pickers"
          f"\n{'='*74}")
    print(f"  fair share if all {N} equal = {100/N:.1f}%")

    # The "France problem": expected total points the field places on each team
    print(f"\n  FIELD OWNERSHIP — pts the other 16 are expected to pile on each team:")
    print(f"  (every win by these teams is paid to their owners; not owning them = bleed)")
    for c in np.argsort(-field_own)[:12]:
        print(f"    {names[c]:<16} {field_own[c]:>4.0f} pt total ({field_own[c]/16:>4.1f}/player)"
              f"  FIFA#{int(fifa_rank[c]):<2}  E[W]={ew[c]:.2f} (#{ewr[c]+1})")

    ev_o, ev_p = ev_optimal(ew)
    print_alloc("EV-optimal (max expected points)", ev_o, ev_p, names, ew, field_own, W, draws)
    g_o, g_p, _ = gpp_optimize(ev_o, ev_p, W, draws)
    print_alloc("GPP-optimal (max P(1st), now defends the chalk)",
                g_o, g_p, names, ew, field_own, W, draws)

    # value vs the FIFA-picking field: E[W] rank far better than FIFA rank
    edge = sorted(range(48), key=lambda c: (fifa_rank[c] - (ewr[c] + 1)), reverse=True)
    print(f"\n{'-'*74}\n  EDGES — field underweights (E[W] rank >> FIFA rank): overweight these\n{'-'*74}")
    for c in edge[:8]:
        print(f"    {names[c]:<16} E[W]#{ewr[c]+1:<2} vs FIFA#{int(fifa_rank[c]):<2}"
              f"  field {field_own[c]:.0f}pt  E[W]={ew[c]:.2f}")
    print(f"\n{'-'*74}\n  TRAPS — field overweights (FIFA rank >> E[W] rank): underweight vs field\n{'-'*74}")
    for c in edge[-6:][::-1]:
        print(f"    {names[c]:<16} FIFA#{int(fifa_rank[c]):<2} vs E[W]#{ewr[c]+1:<2}"
              f"  field {field_own[c]:.0f}pt ({field_own[c]/16:.1f}/player)  E[W]={ew[c]:.2f}")


if __name__ == "__main__":
    main()
