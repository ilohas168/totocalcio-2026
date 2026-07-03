"""
2026 World Cup tournament Monte Carlo engine (fully vectorized over simulations).

Estimates E[W_C] = expected number of wins per country over the whole tournament
(a "win" = winning a GROUP match [group draws excluded] or a KNOCKOUT match
[shootout wins count]). Two special pool rules: the FINAL win counts double
(champion bonus) and the THIRD_PLACE playoff is a 番外 exhibition that never
counts. Also returns the JOINT win-count matrix (n_sims x 48).

Strength model:
  - base rating = standardized blend of World-Football Elo and market-implied
    strength (devigged outright odds), weight w_elo (calibration).
  - per-match venue adjustment: altitude (differential, gated >=1500m, Mexico
    City/Guadalajara) and heat (differential, roof/AC-aware), from the
    wc2026-venue-altitude research (McSharry BMJ2007 / Nassis 2014).
  - host advantage for the three hosts in their group matches.
  - match goals ~ Poisson with mean from the (adjusted) rating gap.
"""
from __future__ import annotations
import json
import itertools
from pathlib import Path
import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data"

DEFAULT_PARAMS = {
    "beta": 0.0035,     # rating gap -> goal supremacy scale (calibrated to market)
    "mu_total": 2.6,
    "shootout_p": 0.5,
    "min_lambda": 0.05,
    # strength ensemble weights (renormalized): Elo + market odds + FIFA ranking
    "w_elo": 0.35,
    "w_mkt": 0.45,
    "w_fifa": 0.20,
    "use_market": True,
    "use_venue": True,
}

SLOT_ORDER = [74, 77, 79, 80, 81, 82, 85, 87]
GROUP_LETTERS = list("ABCDEFGHIJKL")
LET2COL = {L: i for i, L in enumerate(GROUP_LETTERS)}
PAIRS_GROUP = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]  # round-robin order


# ----------------------------------------------------------------------------
# Data loading (teams, bracket, venues, per-team environment)
# ----------------------------------------------------------------------------
def load_data():
    groups = json.loads((DATA / "groups.json").read_text())
    teams = json.loads((DATA / "teams.json").read_text())
    bracket = json.loads((DATA / "bracket.json").read_text())
    meta = json.loads((DATA / "meta.json").read_text())
    venues = json.loads((DATA / "venues.json").read_text())
    env = json.loads((DATA / "teams_env.json").read_text())

    names = [t for L in GROUP_LETTERS for t in groups[L]]
    assert len(names) == 48 and len(set(names)) == 48
    idx = {n: i for i, n in enumerate(names)}
    elo = np.array([teams[n]["elo"] for n in names], dtype=float)
    odds = np.array([teams[n]["winner_odds"] for n in names], dtype=float)
    fifa = np.array([teams[n]["fifa_points"] for n in names], dtype=float)
    host = np.array([1.0 if n in meta["hosts"] else 0.0 for n in names])
    home_alt = np.array([env[n]["home_alt_m"] for n in names], dtype=float)
    climate = np.array([env[n]["climate_norm_c"] for n in names], dtype=float)
    group_cols = {L: np.array([idx[t] for t in groups[L]]) for L in GROUP_LETTERS}

    V, P = venues["venues"], venues["params"]
    hb = P.get("host_bonus", {})
    host_bonus = np.array([hb.get(n, P["host_adv"]) if n in meta["hosts"] else 0.0
                           for n in names])

    def eff_temp(city):
        v = V[city]
        if v["ac"]:
            return float(P["ac_temp_c"])
        return float(v["temp_c"]) + (P["humid_wbgt_add_c"] if v["humid"] else 0.0)

    def alt_factor(city):
        a = V[city]["altitude_m"]
        return (a / P["alt_ref_m"]) if a >= P["alt_threshold_m"] else 0.0

    gv = venues["group_venues"]
    group_alt = {L: float(np.mean([alt_factor(c) for c in gv[L]])) for L in GROUP_LETTERS}
    group_temp = {L: float(np.mean([eff_temp(c) for c in gv[L]])) for L in GROUP_LETTERS}
    ko = venues["knockout_venues"]
    ko_alt = {int(m): alt_factor(c) for m, c in ko.items()}
    ko_temp = {int(m): eff_temp(c) for m, c in ko.items()}

    # exact per-match group venues where known (A,B,D,K); else cluster-average
    fixtures = json.loads((DATA / "group_fixtures.json").read_text())
    group_pair_alt, group_pair_temp = {}, {}
    for L in GROUP_LETTERS:
        cities = fixtures.get(L)
        if cities:
            group_pair_alt[L] = [alt_factor(c) for c in cities]
            group_pair_temp[L] = [eff_temp(c) for c in cities]
        else:
            group_pair_alt[L] = [group_alt[L]] * 6
            group_pair_temp[L] = [group_temp[L]] * 6

    return dict(names=names, idx=idx, elo=elo, odds=odds, fifa=fifa, host=host,
                host_bonus=host_bonus, teams=teams, home_alt=home_alt, climate=climate,
                groups=group_cols, bracket=bracket, vp=P, group_alt=group_alt,
                group_temp=group_temp, group_pair_alt=group_pair_alt,
                group_pair_temp=group_pair_temp, ko_alt=ko_alt, ko_temp=ko_temp)


def make_ratings(d, w_elo=0.35, w_mkt=0.45, w_fifa=0.20, use_market=True):
    """Base rating = standardized 3-signal ensemble: World-Football Elo, market
    implied strength (devigged outright odds), and FIFA ranking points."""
    elo = d["elo"]
    ez = (elo - elo.mean()) / elo.std()
    if not use_market:
        return elo.copy()
    mz = np.log(1.0 / d["odds"]); mz = (mz - mz.mean()) / mz.std()
    fz = (d["fifa"] - d["fifa"].mean()) / d["fifa"].std()
    w = np.array([w_elo, w_mkt, w_fifa]); w = w / w.sum()
    bz = w[0] * ez + w[1] * mz + w[2] * fz
    return elo.mean() + bz * elo.std()


# ----------------------------------------------------------------------------
# Venue adjustments (per-match Elo deltas, differential)
# ----------------------------------------------------------------------------
def _alt_adj(ha, hb, factor, P):
    return np.clip(P["k_alt"] * (ha - hb) / 1000.0 * factor, -P["alt_cap"], P["alt_cap"])


def _heat_adj(ca, cb, temp, P):
    pa = np.maximum(-P["heat_cap"], -P["c_heat"] * np.maximum(0.0, temp - ca - P["comfort_margin_c"]))
    pb = np.maximum(-P["heat_cap"], -P["c_heat"] * np.maximum(0.0, temp - cb - P["comfort_margin_c"]))
    return np.clip(pa - pb, -P["heat_cap"], P["heat_cap"])


# ----------------------------------------------------------------------------
# Third-place -> R32 slot assignment table (approximates FIFA Annex C)
# ----------------------------------------------------------------------------
def build_third_assignment_table(bracket):
    allowed = {}
    for m in bracket["r32"]:
        for side in (m["home"], m["away"]):
            if isinstance(side, dict):
                allowed[m["match"]] = [LET2COL[g] for g in side["third_from"]]
    allowed_cols = [set(allowed[s]) for s in SLOT_ORDER]
    TABLE = np.full((4096, 8), -1, dtype=np.int64)
    for combo in itertools.combinations(range(12), 8):
        cset = set(combo)
        order = sorted(range(8), key=lambda sp: len(allowed_cols[sp] & cset))
        assign, used = {}, set()

        def bt(i):
            if i == len(order):
                return True
            sp = order[i]
            for g in sorted(allowed_cols[sp] & cset):
                if g not in used:
                    used.add(g); assign[sp] = g
                    if bt(i + 1):
                        return True
                    used.remove(g); del assign[sp]
            return False

        mask = 0
        for c in combo:
            mask |= (1 << c)
        if bt(0):
            TABLE[mask] = [assign[sp] for sp in range(8)]
    return TABLE


# ----------------------------------------------------------------------------
# Match goal model
# ----------------------------------------------------------------------------
def _lambdas(elo_a, elo_b, p):
    sup = (np.asarray(elo_a) - np.asarray(elo_b)) * p["beta"]
    base = p["mu_total"] / 2.0
    return (np.maximum(p["min_lambda"], base + sup / 2.0),
            np.maximum(p["min_lambda"], base - sup / 2.0))


def _play(elo_a, elo_b, rng, p, knockout, S):
    la, lb = _lambdas(elo_a, elo_b, p)
    ga = rng.poisson(la, size=S)
    gb = rng.poisson(lb, size=S)
    a_wins = ga > gb
    if knockout:
        flip = rng.random(S) < p["shootout_p"]
        a_wins = np.where(ga != gb, a_wins, flip)
    return a_wins, ga, gb


# ----------------------------------------------------------------------------
# Main simulation
# ----------------------------------------------------------------------------
KO_STAGE_OF = {**{m: "LAST_32" for m in range(73, 89)},
               **{m: "LAST_16" for m in range(89, 97)},
               **{m: "QUARTER_FINALS" for m in range(97, 101)},
               101: "SEMI_FINALS", 102: "SEMI_FINALS",
               103: "THIRD_PLACE", 104: "FINAL"}


def simulate(n_sims=50_000, params=None, seed=12345, data=None, table=None,
             analyze=False, fixed=None):
    """fixed (optional) conditions the simulation on real results:
      fixed["group"][(L, pair_idx)] = (goals_i, goals_j)  — goals for the teams at
        positions i,j of PAIRS within group L (every sim replays that exact score)
      fixed["ko"][stage] = [(home_id, away_id, winner_id), ...] — wherever a sim's
        knockout tie has that exact pairing, the real winner advances
      fixed["r32"][match_num] = (home_id, away_id) — real R32 pairing for that
        bracket slot, overriding the Annex-C third-place approximation so the
        Monte-Carlo bracket matches reality once the R32 draw is known
    """
    p = dict(DEFAULT_PARAMS, **(params or {}))
    d = data or load_data()
    if table is None:
        table = build_third_assignment_table(d["bracket"])
    fx_group = (fixed or {}).get("group", {})
    fx_ko = (fixed or {}).get("ko", {})
    fx_r32 = (fixed or {}).get("r32", {})
    rng = np.random.default_rng(seed)
    S = n_sims
    rating = make_ratings(d, p["w_elo"], p["w_mkt"], p["w_fifa"], p["use_market"])
    host_bonus, home_alt, climate = d["host_bonus"], d["home_alt"], d["climate"]
    VP = d["vp"]
    use_v = p["use_venue"]
    wins = np.zeros((S, 48), dtype=np.int32)
    gplace = np.zeros((48, 4)) if analyze else None   # group finish 1st..4th counts
    reach = np.zeros((48, 6)) if analyze else None    # R32,R16,QF,SF,Final,champ
    r32_home = np.zeros((16, 48)) if analyze else None
    r32_away = np.zeros((16, 48)) if analyze else None
    wincnt = {} if analyze else None   # match -> (48,) winner counts

    # --- Group stage ------------------------------------------------------
    PAIRS = PAIRS_GROUP
    gw_letter, gr_letter = {}, {}
    third_team = np.zeros((S, 12), dtype=np.int64)
    third_score = np.zeros((S, 12))
    for col, L in enumerate(GROUP_LETTERS):
        tids = d["groups"][L]
        base = rating[tids] + (host_bonus[tids] if use_v else 0.0)
        ha, ca = home_alt[tids], climate[tids]
        gpa, gpt = d["group_pair_alt"][L], d["group_pair_temp"][L]
        pts = np.zeros((S, 4)); gd = np.zeros((S, 4))
        gf = np.zeros((S, 4)); gwins = np.zeros((S, 4))
        for pidx, (i, j) in enumerate(PAIRS):
            if (L, pidx) in fx_group:            # match already played for real
                gi, gj = fx_group[(L, pidx)]
                ga = np.full(S, gi, dtype=np.int64)
                gb = np.full(S, gj, dtype=np.int64)
                aw = ga > gb
            else:
                gaf, gte = gpa[pidx], gpt[pidx]
                ei, ej = base[i], base[j]
                if use_v:
                    ei = ei + _alt_adj(ha[i], ha[j], gaf, VP) + _heat_adj(ca[i], ca[j], gte, VP)
                    ej = ej + _alt_adj(ha[j], ha[i], gaf, VP) + _heat_adj(ca[j], ca[i], gte, VP)
                aw, ga, gb = _play(ei, ej, rng, p, False, S)
            draw = ga == gb; jw = gb > ga
            pts[:, i] += 3 * aw + draw; pts[:, j] += 3 * jw + draw
            gd[:, i] += ga - gb;       gd[:, j] += gb - ga
            gf[:, i] += ga;            gf[:, j] += gb
            gwins[:, i] += aw;         gwins[:, j] += jw
        wins[:, tids] += gwins.astype(np.int32)
        comp = pts * 1e9 + (gd + 100) * 1e6 + gf * 1e3 + rating[tids] * 0.1
        order = np.argsort(-comp, axis=1)
        gw_letter[L] = tids[order[:, 0]]
        gr_letter[L] = tids[order[:, 1]]
        third_team[:, col] = tids[order[:, 2]]
        third_score[:, col] = np.take_along_axis(comp, order[:, 2:3], axis=1)[:, 0]
        if analyze:
            for r in range(4):
                gplace[:, r] += np.bincount(tids[order[:, r]], minlength=48)

    # --- Best 8 third-placed ----------------------------------------------
    t_order = np.argsort(-third_score, axis=1)
    qual = t_order[:, :8]
    qmask = np.zeros(S, dtype=np.int64)
    for k in range(8):
        qmask |= (1 << qual[:, k])
    assign_cols = table[qmask]
    rows = np.arange(S)
    slot_team = {SLOT_ORDER[sp]: third_team[rows, assign_cols[:, sp]] for sp in range(8)}

    pos = {}
    for L in GROUP_LETTERS:
        pos[L + "1"] = gw_letter[L]; pos[L + "2"] = gr_letter[L]

    def resolve(side, match):
        return slot_team[match] if isinstance(side, dict) else pos[side]

    def ko_play(a, b, m):
        ea, eb = rating[a], rating[b]
        if use_v:
            maf, mte = d["ko_alt"][m], d["ko_temp"][m]
            ea = ea + _alt_adj(home_alt[a], home_alt[b], maf, VP) + _heat_adj(climate[a], climate[b], mte, VP)
            eb = eb + _alt_adj(home_alt[b], home_alt[a], maf, VP) + _heat_adj(climate[b], climate[a], mte, VP)
        aw, _, _ = _play(ea, eb, rng, p, True, S)
        win, los = np.where(aw, a, b), np.where(aw, b, a)
        # condition on real knockout results: wherever a sim produced this exact
        # pairing, the real winner advances (PK wins count, per the pool rule)
        for (h, x, w) in fx_ko.get(KO_STAGE_OF[m], ()):
            mask = ((a == h) & (b == x)) | ((a == x) & (b == h))
            if mask.any():
                win = np.where(mask, w, win)
                los = np.where(mask, h + x - w, los)
        return win, los

    winner_of, loser_of = {}, {}
    for mi, m in enumerate(d["bracket"]["r32"]):
        if m["match"] in fx_r32:                 # real R32 draw known — use it exactly
            ha, hb = fx_r32[m["match"]]
            a = np.full(S, ha, dtype=np.int64); b = np.full(S, hb, dtype=np.int64)
        else:
            a = resolve(m["home"], m["match"]); b = resolve(m["away"], m["match"])
        win, los = ko_play(a, b, m["match"])
        winner_of[m["match"]] = win; loser_of[m["match"]] = los
        wins[rows, win] += 1
        if analyze:
            ba = np.bincount(a, minlength=48); bb = np.bincount(b, minlength=48)
            r32_home[mi] += ba; r32_away[mi] += bb
            reach[:, 0] += ba + bb
            wincnt[m["match"]] = np.bincount(win, minlength=48)
            reach[:, 1] += wincnt[m["match"]]

    ko = d["bracket"]["knockout"]
    for m in [89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 104]:
        f1, f2 = ko[str(m)]
        win, los = ko_play(winner_of[f1], winner_of[f2], m)
        winner_of[m] = win; loser_of[m] = los
        wins[rows, win] += 1
        if analyze:
            wincnt[m] = np.bincount(win, minlength=48)
    # champion bonus: winning the FINAL (104) counts as 2 wins
    wins[rows, winner_of[104]] += 1

    # third-place playoff (103) is a 番外 exhibition — it credits NO pool win
    # (win or lose is a no-count). Still simulated so analyze can report its odds.
    win, _ = ko_play(loser_of[101], loser_of[102], 103)
    if analyze:
        wincnt[103] = np.bincount(win, minlength=48)

    out = dict(wins=wins, ewins=wins.mean(axis=0), champion=winner_of[104],
               names=d["names"], data=d, params=p, rating=rating)
    if analyze:
        for m in [89, 90, 91, 92, 93, 94, 95, 96]:
            reach[:, 2] += np.bincount(winner_of[m], minlength=48)
        for m in [97, 98, 99, 100]:
            reach[:, 3] += np.bincount(winner_of[m], minlength=48)
        reach[:, 4] += np.bincount(winner_of[101], minlength=48)
        reach[:, 4] += np.bincount(winner_of[102], minlength=48)
        reach[:, 5] += np.bincount(winner_of[104], minlength=48)
        out.update(gplace=gplace / S, reach=reach / S,
                   r32_home=r32_home / S, r32_away=r32_away / S,
                   wincnt={m: c / S for m, c in wincnt.items()})
    return out


# ----------------------------------------------------------------------------
# Report / sanity check
# ----------------------------------------------------------------------------
def main():
    from scipy.stats import spearmanr
    d = load_data()
    names = d["names"]
    implied = (1.0 / d["odds"]); implied = implied / implied.sum()

    full = simulate(n_sims=60_000, data=d)               # market blend + venue
    base = simulate(n_sims=60_000, data=d,
                    params={"use_market": False, "use_venue": False})  # pure Elo, no venue
    ew, ew0 = full["ewins"], base["ewins"]
    champ = full["champion"]
    cp = np.bincount(champ, minlength=48) / len(champ)

    order = np.argsort(-ew)
    print(f"\n{'='*70}\n  CALIBRATED E[W] (Elo x market blend + altitude/heat), 60k sims\n{'='*70}")
    print(f"{'#':>3} {'Country':<18}{'E[W]':>6}{'Δvs Elo':>8}{'champ%':>8}{'mkt%':>7}")
    for r, i in enumerate(order[:24], 1):
        print(f"{r:>3} {names[i]:<18}{ew[i]:>6.2f}{ew[i]-ew0[i]:>+8.2f}"
              f"{100*cp[i]:>7.1f}%{100*implied[i]:>6.1f}%")
    print(f"\n  sum E[W]={ew.sum():.1f}   "
          f"Spearman(champ%,market%): blend={spearmanr(cp, implied).statistic:.3f}")

    mov = np.argsort(-(ew - ew0))
    print(f"\n  altitude/market WINNERS: " +
          ", ".join(f"{names[i]} {ew[i]-ew0[i]:+.2f}" for i in mov[:6]))
    print(f"  altitude/market LOSERS:  " +
          ", ".join(f"{names[i]} {ew[i]-ew0[i]:+.2f}" for i in mov[-6:]))


if __name__ == "__main__":
    main()
