#!/usr/bin/env python3
"""Fetch WC2026 fixtures + results from football-data.org.

Writes:
  data/schedule.json  — all 104 matches (utc time, stage, group, teams, status, score)
  data/results.json   — wins per country under the pool rule

Pool 'win' rule: group-stage win (a draw counts for nobody) OR any knockout
advance (round-of-32 → final, including a penalty-shootout win). Two special
pool rules: the FINAL win counts double (champion bonus, +1 extra) and the
THIRD_PLACE playoff is a 番外 exhibition that never counts (no win for anyone).

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

# Previously recorded results. fetch rebuilds schedule.json from scratch each
# run, so without this it has no memory: a finished match whose result the
# free-tier matches list momentarily drops back to IN_PLAY / FINISHED-with-null
# would be overwritten and "un-finish". That actually wiped Canada–Bosnia's
# confirmed 1-1 a full day later (2026-06-14). A finished football match never
# un-finishes, so a stored FINISHED-with-score is authoritative and is never
# downgraded by a flakier later response.
prev = {}
if (DATA / "schedule.json").exists():
    for m in json.loads((DATA / "schedule.json").read_text(encoding="utf-8")).get("matches", []):
        prev[m["id"]] = m

ms = api("/competitions/WC/matches")["matches"]
sched = []
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
    if st == "FINISHED" and ft.get("home") is not None and ft.get("away") is not None and w is not None:
        pen = sc.get("penalties") or {}
        if pen.get("home") is not None:
            # A shootout match: football-data folds the penalties into fullTime
            # (e.g. a 1-1 draw won 4-3 on pens is reported as fullTime 5-4). Store
            # the score that actually stood — the post-extra-time draw
            # (regularTime+extraTime) — and keep the shootout separately in pens.
            rt = sc.get("regularTime") or {}
            et = sc.get("extraTime") or {}
            if rt.get("home") is not None:
                rec["score"] = [(rt.get("home") or 0) + (et.get("home") or 0),
                                (rt.get("away") or 0) + (et.get("away") or 0)]
            else:                                   # fallback: back out pens from fullTime
                rec["score"] = [ft["home"] - pen["home"], ft["away"] - pen["away"]]
            rec["pens"] = [pen["home"], pen["away"]]
        else:
            rec["score"] = [ft["home"], ft["away"]]
        rec["winner"] = w
    else:
        # No usable final result this time. Keep a previously confirmed one if we
        # have it; otherwise a bare FINISHED (null score) shows as in-play so the
        # page renders "vs" rather than null–null, and credits no win yet.
        p = prev.get(m["id"])
        if p and p.get("status") == "FINISHED" and p.get("score"):
            rec = p
        elif st == "FINISHED":
            rec["status"] = "IN_PLAY"
    sched.append(rec)

# wins from the merged, authoritative records: group win or knockout advance
# (PK win included, since the API sets winner to the shootout winner). Two
# special pool rules apply to the last two matches:
#   - THIRD_PLACE: a 番外 exhibition — credits no win to anyone (skip it).
#   - FINAL: the champion's win counts double (+1 bonus), so 2 wins.
wins = {}
for rec in sched:
    if rec["stage"] == "THIRD_PLACE":            # exhibition — no pool win
        continue
    if rec.get("winner") in ("HOME_TEAM", "AWAY_TEAM"):
        adv = rec["home"] if rec["winner"] == "HOME_TEAM" else rec["away"]
        if adv:
            wins[adv] = wins.get(adv, 0) + (2 if rec["stage"] == "FINAL" else 1)

DATA.mkdir(exist_ok=True)
(DATA / "schedule.json").write_text(
    json.dumps({"matches": sched}, ensure_ascii=False), encoding="utf-8")
(DATA / "results.json").write_text(
    json.dumps({"wins": wins}, ensure_ascii=False), encoding="utf-8")

fin = sum(1 for m in sched if m["status"] == "FINISHED")
print(f"schedule.json: {len(sched)} matches ({fin} finished)")
print(f"results.json:  {sum(wins.values())} wins / {len(wins)} countries")
