#!/usr/bin/env python3
"""Fetch WC2026 fixtures + results from football-data.org.

Writes:
  data/schedule.json  — all 104 matches (utc time, stage, group, teams, status, score)
  data/results.json   — wins per country under the pool rule

Pool 'win' rule: group-stage win (a draw counts for nobody) OR any knockout
advance (round-of-32 → final, including a penalty-shootout win).

Run locally:  python report/fetch_matches.py   (reads FOOTBALL_DATA_TOKEN from env or .env)
In CI:        set FOOTBALL_DATA_TOKEN as a secret env var.
"""
import os
import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"

# --- token: env var (CI) or .env (local) ----------------------------------
TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN")
if not TOKEN and (ROOT / ".env").exists():
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("FOOTBALL_DATA_TOKEN="):
            TOKEN = line.split("=", 1)[1].strip()
if not TOKEN:
    raise SystemExit("FOOTBALL_DATA_TOKEN not set (env var or .env)")

# --- API team name → our canonical name -----------------------------------
NAME_FIX = {"Cape Verde Islands": "Cape Verde", "Turkey": "Türkiye"}
def canon(n):
    return NAME_FIX.get(n, n) if n else None

def api(path):
    req = urllib.request.Request(
        "https://api.football-data.org/v4" + path,
        headers={"X-Auth-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

ms = api("/competitions/WC/matches")["matches"]
sched, wins = [], {}
for m in ms:
    home = canon(m["homeTeam"].get("name"))
    away = canon(m["awayTeam"].get("name"))
    st = m["status"]
    rec = {"id": m["id"], "utc": m["utcDate"], "stage": m["stage"],
           "group": m.get("group"), "md": m.get("matchday"),
           "home": home, "away": away, "status": st}
    sc = m.get("score") or {}
    ft = sc.get("fullTime") or {}
    if st == "FINISHED":
        rec["score"] = [ft.get("home"), ft.get("away")]
        pen = sc.get("penalties") or {}
        if pen.get("home") is not None:
            rec["pens"] = [pen["home"], pen["away"]]
        w = sc.get("winner")  # HOME_TEAM / AWAY_TEAM / DRAW
        rec["winner"] = w
        adv = home if w == "HOME_TEAM" else (away if w == "AWAY_TEAM" else None)
        if adv:                       # group win or knockout advance (incl. penalties)
            wins[adv] = wins.get(adv, 0) + 1
    sched.append(rec)

DATA.mkdir(exist_ok=True)
(DATA / "schedule.json").write_text(
    json.dumps({"matches": sched}, ensure_ascii=False), encoding="utf-8")
(DATA / "results.json").write_text(
    json.dumps({"wins": wins}, ensure_ascii=False), encoding="utf-8")

fin = sum(1 for m in sched if m["status"] == "FINISHED")
print(f"schedule.json: {len(sched)} matches ({fin} finished)")
print(f"results.json:  {sum(wins.values())} wins / {len(wins)} countries")
