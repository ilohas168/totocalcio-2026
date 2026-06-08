"""How much do host advantage, altitude, and heat move WIN PROBABILITY?
Converts the model's per-match Elo adjustments into concrete W/D/L percentages
via the Poisson (Skellam) match model."""
import numpy as np
from scipy.stats import skellam
from tournament import _lambdas, _alt_adj, _heat_adj, DEFAULT_PARAMS, load_data

P = DEFAULT_PARAMS
d = load_data(); VP = d["vp"]


def wdl(ra, rb):
    la, lb = _lambdas(ra, rb, P)
    return skellam.sf(0, la, lb), skellam.pmf(0, la, lb), skellam.cdf(-1, la, lb)


def ko(ra, rb):
    w, dr, _ = wdl(ra, rb)
    return w + 0.5 * dr


BASE = 1800
print("="*68)
print("  Rating-gap -> win probability (between two otherwise-equal teams)")
print("="*68)
print(f"  {'gap (Elo)':>10}{'group win':>11}{'draw':>7}{'loss':>7}{'KO eff. win':>13}")
for g in [0, 30, 60, 100, 120, 165, 200]:
    w, dr, l = wdl(BASE + g, BASE)
    print(f"  {('+'+str(g)):>10}{100*w:>10.1f}%{100*dr:>6.1f}%{100*l:>6.1f}%{100*ko(BASE+g, BASE):>12.1f}%")

print("\n" + "="*68)
print("  Each factor as a per-match Elo shift, and the win% it buys")
print("="*68)


def show(label, shift, knockout=False):
    if knockout:
        v = ko(BASE + shift, BASE) - ko(BASE, BASE)
        print(f"  {label:<48} {('+'+str(round(shift)))+' Elo':>9}  ->  KO win {100*v:+.1f} pt")
    else:
        w0, _, _ = wdl(BASE, BASE)
        w1, _, _ = wdl(BASE + shift, BASE)
        print(f"  {label:<48} {('+'+str(round(shift)))+' Elo':>9}  ->  win {100*(w1-w0):+.1f} pt")


host = VP["host_adv"]
alt_azteca = float(_alt_adj(2240, 150, 1.0, VP))                 # Mexico vs lowland, Azteca
alt_guad = float(_alt_adj(2240, 150, 1560 / VP["alt_ref_m"], VP))  # Guadalajara 1560m
heat_hot = float(_alt_adj(0, 0, 0, VP))  # placeholder
heat_miami = float(_heat_adj(19, 30, 33 + VP["humid_wbgt_add_c"], VP))   # cool vs adapted, Miami(humid)
heat_mod = float(_heat_adj(20, 30, 30, VP))                              # cool vs adapted, 30C open

show("Host advantage (Mexico/USA/Canada at home, group)", host)
show("Altitude: acclimatized vs lowland @ Azteca 2240m", alt_azteca)
show("Altitude: acclimatized vs lowland @ Guadalajara 1560m", alt_guad)
show("Mexico STACKED @ Azteca (host + altitude)", host + alt_azteca)
show("Heat: cool team vs heat-adapted @ Miami (hot+humid)", heat_miami)
show("Heat: cool team vs heat-adapted @ 30C open venue", heat_mod)

print("\n  Worked example — Mexico vs an equal-rated European team:")
for where, shift in [("neutral US venue", 0.0),
                     ("Azteca group game (host+altitude)", host + alt_azteca),
                     ("Azteca knockout (altitude only)", alt_azteca)]:
    w, dr, l = wdl(BASE + shift, BASE)
    print(f"    {where:<38} win {100*w:4.1f}%  draw {100*dr:4.1f}%  loss {100*l:4.1f}%")
print("\n  (Elo->prob via the same Poisson model the simulation uses; "
      "altitude/heat are DIFFERENTIAL & capped at +-120 / +-90 Elo.)")
