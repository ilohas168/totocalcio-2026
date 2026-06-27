"""Exact theoretical best/worst-case final score per player.

The pool score is Σ_C PW(C)·W_C where W_C = wins of country C (group wins;
knockout advances incl. PK). Two special pool rules: the FINAL win counts
double (champion bonus) and the THIRD_PLACE playoff is a 番外 exhibition that
never counts. Given the finished results, every remaining group match is a free
3-way choice (home/draw/away) and every remaining knockout match a free 2-way
choice (PK makes any winner possible), with scorelines free.
The theoretical best (worst) is the exact maximum (minimum) of the player's
final score over all feasible completions — a combinatorial optimization, not
a simulation, so the value is deterministic, noise-free, and monotone as
results arrive.

Modeling notes (all deterministic, documented approximations):
- Scorelines are unbounded, so goal-difference of any team with a remaining
  non-draw match is effectively free; tie-orders that come down to fair play /
  drawing of lots are treated as free (lots IS free).
- Third-place → R32 slot mapping reuses the project's Annex-C approximation
  table (data/bracket.json + build_third_assignment_table). Once the real R32
  pairings appear in data/schedule.json they are used instead.

Phase 1 (group stage unfinished): one small MILP per player per direction
(pulp/CBC, a few thousand binaries, solves in seconds).
Phase 2 (groups done): plain dynamic programming over the real bracket.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pulp

from sim.tournament import (DATA, GROUP_LETTERS, LET2COL, PAIRS_GROUP,
                            SLOT_ORDER, build_third_assignment_table, load_data)

BIG_GD = 999
KO_STAGES = {"LAST_32": list(range(73, 89)), "LAST_16": list(range(89, 97)),
             "QUARTER_FINALS": [97, 98, 99, 100], "SEMI_FINALS": [101, 102],
             "THIRD_PLACE": [103], "FINAL": [104]}


# ---------------------------------------------------------------------------
# parsing real results out of data/schedule.json
# ---------------------------------------------------------------------------
def parse_results(matches, d):
    """-> (group_fixed {L: {pidx:(gi,gj)}}, ko_fixed {stage:[(h,a,w)]}, r32_real {utc-ordered pairings})"""
    tidx = d["idx"]
    gnames = {L: [d["names"][t] for t in d["groups"][L]] for L in GROUP_LETTERS}
    pair_of = {ij: k for k, ij in enumerate(PAIRS_GROUP)}
    gfix, kfix = {}, {}
    r32_real = []          # real R32 pairings (team ids) once football-data fills them in
    for m in matches:
        if m["stage"] == "LAST_32" and m.get("home") and m.get("away"):
            r32_real.append((tidx[m["home"]], tidx[m["away"]]))
        if m["status"] != "FINISHED" or not m.get("score") or m.get("winner") is None:
            continue
        if m["stage"] == "GROUP_STAGE":
            L = m["group"].replace("GROUP_", "")
            gl = gnames[L]
            i, j = gl.index(m["home"]), gl.index(m["away"])
            gh, ga = m["score"]
            if i < j:
                gfix.setdefault(L, {})[pair_of[(i, j)]] = (gh, ga)
            else:
                gfix.setdefault(L, {})[pair_of[(j, i)]] = (ga, gh)
        else:
            if m["winner"] not in ("HOME_TEAM", "AWAY_TEAM"):
                continue
            w = tidx[m["home"]] if m["winner"] == "HOME_TEAM" else tidx[m["away"]]
            kfix.setdefault(m["stage"], []).append((tidx[m["home"]], tidx[m["away"]], w))
    return gfix, kfix, r32_real


# ---------------------------------------------------------------------------
# group-stage enumeration: feasible (1st,2nd,3rd, third-pts) profiles
# ---------------------------------------------------------------------------
def _order_ok(perm, pts, lo, hi, gf, rigid):
    """Is this 4-team ranking achievable? pts must be non-increasing; inside an
    equal-points cluster a weakly-decreasing GD choice must exist within each
    team's [lo,hi] GD range (free goals); a fully rigid cluster additionally
    respects fixed (gd, gf) lexicographic order (exact ties free = lots)."""
    for a, b in zip(perm, perm[1:]):
        if pts[a] < pts[b]:
            return False
    i = 0
    while i < 4:
        j = i
        while j + 1 < 4 and pts[perm[j + 1]] == pts[perm[i]]:
            j += 1
        cluster = perm[i:j + 1]
        if len(cluster) > 1:
            if all(rigid[c] for c in cluster):
                for a, b in zip(cluster, cluster[1:]):
                    if (lo[a], gf[a]) < (lo[b], gf[b]):   # lo==hi==fixed gd here
                        return False
            else:
                u = BIG_GD * 2
                for c in cluster:
                    v = min(u, hi[c])
                    if v < lo[c]:
                        return False
                    u = v
        i = j + 1
    return True


def group_profiles(L, d, gfix):
    """Enumerate completions of group L.
    -> dict key=(first,second,third local idx, third pts) ->
         dict wins-tuple -> witness (combo, perm)   [combo: outcomes of open pairs]"""
    fixed = gfix.get(L, {})
    rem = [p for p in range(6) if p not in fixed]
    bp, bg, bf, bw = [0] * 4, [0] * 4, [0] * 4, [0] * 4   # pts, gd, gf, wins (from fixed)
    for p, (gi, gj) in fixed.items():
        i, j = PAIRS_GROUP[p]
        bg[i] += gi - gj; bg[j] += gj - gi
        bf[i] += gi;      bf[j] += gj
        if gi > gj:   bp[i] += 3; bw[i] += 1
        elif gj > gi: bp[j] += 3; bw[j] += 1
        else:         bp[i] += 1; bp[j] += 1
    out = {}
    for combo in itertools.product((0, 1, 2), repeat=len(rem)):   # 0 home,1 draw,2 away
        pts, wins = bp[:], bw[:]
        nw, nl = [0] * 4, [0] * 4                                 # open wins/losses per team
        for p, o in zip(rem, combo):
            i, j = PAIRS_GROUP[p]
            if o == 0:   pts[i] += 3; wins[i] += 1; nw[i] += 1; nl[j] += 1
            elif o == 2: pts[j] += 3; wins[j] += 1; nw[j] += 1; nl[i] += 1
            else:        pts[i] += 1; pts[j] += 1
        lo = [bg[a] + nw[a] - (BIG_GD if nl[a] else 0) for a in range(4)]
        hi = [bg[a] + (BIG_GD if nw[a] else 0) - nl[a] for a in range(4)]
        rigid = [nw[a] == 0 and nl[a] == 0 and
                 all(a not in PAIRS_GROUP[p] for p in rem) for a in range(4)]
        wt = tuple(wins)
        for perm in itertools.permutations(range(4)):
            if _order_ok(perm, pts, lo, hi, bf, rigid):
                key = (perm[0], perm[1], perm[2], pts[perm[2]])
                out.setdefault(key, {}).setdefault(wt, (combo, perm))
    return out, rem


# ---------------------------------------------------------------------------
# Phase 1: MILP over group profiles + third-qualifier mask + free knockout
# ---------------------------------------------------------------------------
def _optimize_milp(PW, d, gfix, table, profiles):
    prob = pulp.LpProblem("theo", pulp.LpMaximize)
    tidx_of = {L: list(d["groups"][L]) for L in GROUP_LETTERS}

    # group profile choice
    x, pts3, t1, t2, t3 = {}, {}, {}, {}, {}
    obj = []
    for L in GROUP_LETTERS:
        prof, _ = profiles[L]
        keys = list(prof)
        for k in keys:
            x[L, k] = pulp.LpVariable(f"x_{L}_{k[0]}{k[1]}{k[2]}_{k[3]}", cat="Binary")
            v = max(sum(w * PW[t] for w, t in zip(wt, tidx_of[L])) for wt in prof[k])
            obj.append(v * x[L, k])
        prob += pulp.lpSum(x[L, k] for k in keys) == 1
        pts3[L] = pulp.lpSum(k[3] * x[L, k] for k in keys)
        for role, store in ((0, t1), (1, t2), (2, t3)):
            for a in range(4):
                e = pulp.lpSum(x[L, k] for k in keys if k[role] == a)
                store[L, tidx_of[L][a]] = e

    # third-qualifier mask (Annex-C approximation table)
    masks = []
    for combo in itertools.combinations(range(12), 8):
        mask = 0
        for c in combo:
            mask |= 1 << c
        if table[mask][0] >= 0:
            masks.append((mask, set(combo), table[mask]))
    mv = {mask: pulp.LpVariable(f"m_{mask}", cat="Binary") for mask, _, _ in masks}
    prob += pulp.lpSum(mv.values()) == 1
    q = {L: pulp.lpSum(mv[mask] for mask, cset, _ in masks if LET2COL[L] in cset)
         for L in GROUP_LETTERS}

    # qualification must respect third-place points (GD/goals free unless both
    # groups are fully finished, where the fixed comparator applies)
    rigid3 = {}
    for L in GROUP_LETTERS:
        if len(gfix.get(L, {})) != 6:
            continue
        prof, _ = profiles[L]
        keys = list(prof)
        if len(keys) != 1:           # dead-heat ties exist -> order genuinely free (lots)
            continue
        k = keys[0]
        a = k[2]
        bg = [0] * 4; bf = [0] * 4
        for p, (gi, gj) in gfix[L].items():
            i, j = PAIRS_GROUP[p]
            bg[i] += gi - gj; bg[j] += gj - gi; bf[i] += gi; bf[j] += gj
        rigid3[L] = (k[3], bg[a], bf[a])
    for g in GROUP_LETTERS:
        for h in GROUP_LETTERS:
            if g == h:
                continue
            if g in rigid3 and h in rigid3:
                if rigid3[h] > rigid3[g]:        # h's third strictly outranks g's
                    prob += q[g] <= q[h]
            else:
                prob += pts3[g] - pts3[h] >= -9 * (1 - q[g] + q[h])

    # third-slot occupancy: w = (slot assigned to group) AND (team is its third)
    occ3 = {}                                    # slot-pos -> {team: expr}
    for sp in range(8):
        occ3[sp] = {}
        for L in GROUP_LETTERS:
            z = pulp.lpSum(mv[mask] for mask, _, assign in masks
                           if assign[sp] == LET2COL[L])
            for a in range(4):
                t = tidx_of[L][a]
                wvar = pulp.LpVariable(f"w_{sp}_{L}_{a}", 0, 1)
                prob += wvar <= z
                prob += wvar <= t3[L, t]
                prob += wvar >= z + t3[L, t] - 1
                occ3[sp].setdefault(t, []).append(wvar)
    slot_pos = {m: sp for sp, m in enumerate(SLOT_ORDER)}

    # knockout chain
    def presence_r32(side, mnum):
        if isinstance(side, dict):
            return {t: pulp.lpSum(v) for t, v in occ3[slot_pos[mnum]].items()}
        L, pos = side[0], side[1]
        store = t1 if pos == "1" else t2
        return {t: store[L, t] for t in tidx_of[L]}

    win = {}
    for mt in d["bracket"]["r32"]:
        mnum = mt["match"]
        ph = presence_r32(mt["home"], mnum)
        pa = presence_r32(mt["away"], mnum)
        win[mnum] = {t: pulp.LpVariable(f"win_{mnum}_{t}", cat="Binary")
                     for t in set(ph) | set(pa)}
        for t, v in win[mnum].items():
            prob += v <= ph.get(t, 0) + pa.get(t, 0)
        prob += pulp.lpSum(win[mnum].values()) == 1
        obj += [PW[t] * v for t, v in win[mnum].items()]
    ko = d["bracket"]["knockout"]
    for mnum in [89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 104]:
        f1, f2 = ko[str(mnum)]
        ph = {t: v for t, v in win[f1].items()}
        pa = {t: v for t, v in win[f2].items()}
        win[mnum] = {t: pulp.LpVariable(f"win_{mnum}_{t}", cat="Binary")
                     for t in set(ph) | set(pa)}
        for t, v in win[mnum].items():
            prob += v <= ph.get(t, 0) + pa.get(t, 0)
        prob += pulp.lpSum(win[mnum].values()) == 1
        obj += [PW[t] * v for t, v in win[mnum].items()]
    # champion bonus: the FINAL (104) win counts double — count its winner once
    # more. The THIRD_PLACE playoff is a 番外 exhibition that never counts, so it
    # contributes no variable and no objective term at all.
    obj += [PW[t] * v for t, v in win[104].items()]

    prob += pulp.lpSum(obj)
    status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal", f"MILP status {pulp.LpStatus[status]}"
    val = int(round(pulp.value(prob.objective)))

    _verify_milp(PW, d, profiles, x, mv, masks, win, val)
    return val


def _verify_milp(PW, d, profiles, x, mv, masks, win, val):
    """Re-derive the score from the chosen solution by independent bookkeeping."""
    tidx_of = {L: list(d["groups"][L]) for L in GROUP_LETTERS}
    total = 0
    chosen = {}
    for (L, k), var in x.items():
        if var.value() and var.value() > 0.5:
            chosen[L] = k
            total += max(sum(w * PW[t] for w, t in zip(wt, tidx_of[L]))
                         for wt in profiles[L][0][k])
    assert len(chosen) == 12
    mask_row = next(assign for mask, _, assign in masks if mv[mask].value() > 0.5)
    # winner of each KO match must actually be in that match
    slot_team = {SLOT_ORDER[sp]: tidx_of[GROUP_LETTERS[mask_row[sp]]][chosen[GROUP_LETTERS[mask_row[sp]]][2]]
                 for sp in range(8)}
    def r32_side(side, mnum):
        if isinstance(side, dict):
            return slot_team[mnum]
        L, pos = side[0], side[1]
        return tidx_of[L][chosen[L][0 if pos == "1" else 1]]
    winner = {}
    for mt in d["bracket"]["r32"]:
        mnum = mt["match"]
        a, b = r32_side(mt["home"], mnum), r32_side(mt["away"], mnum)
        w = next(t for t, v in win[mnum].items() if v.value() > 0.5)
        assert w in (a, b), f"match {mnum}: winner {w} not in ({a},{b})"
        winner[mnum] = w; total += PW[w]
    ko = d["bracket"]["knockout"]
    for mnum in [89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 104]:
        f1, f2 = ko[str(mnum)]
        a, b = winner[f1], winner[f2]
        w = next(t for t, v in win[mnum].items() if v.value() > 0.5)
        assert w in (a, b), f"match {mnum}: winner {w} not in ({a},{b})"
        winner[mnum] = w; total += PW[w]
    total += PW[winner[104]]   # FINAL counts double (champion bonus)
    assert int(round(total)) == val, f"verification {total} != objective {val}"


# ---------------------------------------------------------------------------
# Phase 2: groups finished — plain DP over the (real) bracket
# ---------------------------------------------------------------------------
def _optimize_ko_dp(PW, d, gfix, kfix, r32_real, table):
    tidx_of = {L: list(d["groups"][L]) for L in GROUP_LETTERS}
    banked, rank = 0.0, {}
    thirds = {}
    for L in GROUP_LETTERS:
        gl = tidx_of[L]
        pts, gd, gf, wins = [0] * 4, [0] * 4, [0] * 4, [0] * 4
        for p, (gi, gj) in gfix[L].items():
            i, j = PAIRS_GROUP[p]
            gd[i] += gi - gj; gd[j] += gj - gi; gf[i] += gi; gf[j] += gj
            if gi > gj:   pts[i] += 3; wins[i] += 1
            elif gj > gi: pts[j] += 3; wins[j] += 1
            else:         pts[i] += 1; pts[j] += 1
        banked += sum(wins[a] * PW[gl[a]] for a in range(4))
        order = sorted(range(4), key=lambda a: (-pts[a], -gd[a], -gf[a], d["names"][gl[a]]))
        rank[L] = [gl[a] for a in order]
        a3 = order[2]
        thirds[L] = (pts[a3], gd[a3], gf[a3])
    # leaves: real pairings if known, else Annex-C approximation
    if len(r32_real) == 16:
        leaves = {m["match"]: pair for m, pair in
                  zip(d["bracket"]["r32"], _match_real(d, r32_real, rank))}
    else:
        q8 = sorted(GROUP_LETTERS, key=lambda L: thirds[L], reverse=True)[:8]
        mask = 0
        for L in q8:
            mask |= 1 << LET2COL[L]
        assign = table[mask]
        slot_team = {SLOT_ORDER[sp]: rank[GROUP_LETTERS[assign[sp]]][2] for sp in range(8)}
        leaves = {}
        for mt in d["bracket"]["r32"]:
            def side(s, mn=mt["match"]):
                return slot_team[mn] if isinstance(s, dict) else rank[s[0]][0 if s[1] == "1" else 1]
            leaves[mt["match"]] = (side(mt["home"]), side(mt["away"]))

    forced = {s: list(v) for s, v in kfix.items()}
    def force_of(stage, a, b):
        for (h, x_, w) in forced.get(stage, ()):
            if {h, x_} == {a, b}:
                return w
        return None

    f = {}                       # match -> {winner: best downstream-exclusive value}
    for mnum, (a, b) in leaves.items():
        w = force_of("LAST_32", a, b)
        cand = [w] if w is not None else [a, b]
        f[mnum] = {t: PW[t] for t in cand}
    ko = d["bracket"]["knockout"]
    stage_of = {m: s for s, ms in KO_STAGES.items() for m in ms}
    for mnum in [89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102]:
        f1, f2 = ko[str(mnum)]
        f[mnum] = {}
        for a, va in f[f1].items():
            for b, vb in f[f2].items():
                w = force_of(stage_of[mnum], a, b)
                for t in ([w] if w is not None else [a, b]):
                    v = va + vb + PW[t]
                    if v > f[mnum].get(t, -1e18):
                        f[mnum][t] = v
    # FINAL counts double (champion bonus); the THIRD_PLACE playoff is a 番外
    # exhibition that never counts, so it contributes nothing.
    best = -1e18
    for w1, v1 in f[101].items():
        for w2, v2 in f[102].items():
            wf = force_of("FINAL", w1, w2)
            vf = 2 * (PW[wf] if wf is not None else max(PW[w1], PW[w2]))
            best = max(best, v1 + v2 + vf)
    return int(round(banked + best))


def _match_real(d, r32_real, rank):
    """Order the 16 real pairings to match bracket.json's r32 list by the
    deterministic slots (X1/X2); third-slots get whatever pairing remains."""
    fixed_side = {}
    for mt in d["bracket"]["r32"]:
        for s in (mt["home"], mt["away"]):
            if not isinstance(s, dict):
                fixed_side.setdefault(mt["match"], []).append(rank[s[0]][0 if s[1] == "1" else 1])
    pairs = list(r32_real)
    out = []
    for mt in d["bracket"]["r32"]:
        anchors = fixed_side.get(mt["match"], [])
        hit = next((p for p in pairs if any(a in p for a in anchors)), None)
        if hit is None:
            hit = pairs[0]
        pairs.remove(hit)
        out.append(hit)
    return out


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def theoretical_bounds_all(PW_rows, d=None, matches=None, table=None):
    """PW_rows: iterable of (48,) per-win swing vectors. -> [(best, worst), ...]"""
    d = d or load_data()
    if matches is None:
        matches = json.loads((DATA / "schedule.json").read_text(encoding="utf-8"))["matches"]
    table = table if table is not None else build_third_assignment_table(d["bracket"])
    gfix, kfix, r32_real = parse_results(matches, d)
    groups_done = all(len(gfix.get(L, {})) == 6 for L in GROUP_LETTERS)
    assert groups_done or not kfix, "KO results before groups finished?"

    res = []
    if groups_done:
        for PW in PW_rows:
            PW = np.asarray(PW, dtype=float)
            best = _optimize_ko_dp(PW, d, gfix, kfix, r32_real, table)
            worst = -_optimize_ko_dp(-PW, d, gfix, kfix, r32_real, table)
            res.append((best, worst))
    else:
        profiles = {L: group_profiles(L, d, gfix) for L in GROUP_LETTERS}
        for PW in PW_rows:
            PW = np.asarray(PW, dtype=float)
            best = _optimize_milp(PW, d, gfix, table, profiles)
            worst = -_optimize_milp(-PW, d, gfix, table, profiles)
            res.append((best, worst))
    return res


if __name__ == "__main__":
    import time
    d = load_data()
    opp = json.loads((DATA / "opponents.json").read_text())
    FINAL = json.loads((Path(__file__).resolve().parent.parent / "report" /
                        "final_allocation.json").read_text())["allocation"]
    N = opp["n_players"]
    ballots = list(opp["known"].items()) + list(opp.get("outliers", {}).items()) + [("あなた", FINAL)]
    Vn = np.zeros((len(ballots), 48))
    for i, (_, alloc) in enumerate(ballots):
        for c, p in alloc.items():
            Vn[i, d["idx"][c]] = p
    PWm = N * Vn - Vn.sum(0)
    t0 = time.time()
    out = theoretical_bounds_all(PWm)
    for (lab, _), (b, w) in zip(ballots, out):
        print(f"{lab:<14} best {b:+6d}  worst {w:+6d}")
    print(f"{time.time()-t0:.1f}s for {2*len(ballots)} solves")
