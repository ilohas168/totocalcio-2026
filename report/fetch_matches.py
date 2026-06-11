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
import time
import urllib.request
import urllib.error
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

def api(path, retries=5):
    """GET with retry+backoff. The football-data.org server occasionally drops the
    connection (RemoteDisconnected) or rate-limits (429); those are transient, so
    retry a few times. Auth/not-found (401/403/404) fail fast."""
    req = urllib.request.Request(
        "https://api.football-data.org/v4" + path,
        headers={"X-Auth-Token": TOKEN, "User-Agent": "totocalcio-bot/1.0"})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == retries:
                raise                                    # auth / 4xx → fail fast
            wait = min(60, 6 * attempt)
            print(f"  HTTP {e.code} from API; retry {attempt}/{retries} in {wait}s")
            time.sleep(wait)
        except (urllib.error.URLError, OSError) as e:    # RemoteDisconnected / timeout / drop
            if attempt == retries:
                raise SystemExit(f"API unreachable after {retries} tries: {type(e).__name__}: {e}")
            wait = min(60, 6 * attempt)
            print(f"  {type(e).__name__} ({e}); retry {attempt}/{retries} in {wait}s")
            time.sleep(wait)

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
    w = sc.get("winner")  # HOME_TEAM / AWAY_TEAM / DRAW
    if st == "FINISHED":
        if ft.get("home") is None or ft.get("away") is None or w is None:
            # The API transiently flags a match FINISHED before the final
            # score/winner are published (seen after MEX–RSA on 2026-06-11).
            # Keep it as in-play so the page shows "vs" instead of null–null
            # and no win is credited until the result is actually confirmed.
            rec["status"] = "IN_PLAY"
            sched.append(rec)
            continue
        rec["score"] = [ft["home"], ft["away"]]
        pen = sc.get("penalties") or {}
        if pen.get("home") is not None:
            rec["pens"] = [pen["home"], pen["away"]]
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
