"""Lightweight LIVE refresh — updates only 順位表 (standings) + 日程 (schedule)
from data/results.json + data/schedule.json. Pure standard library (no numpy / no
Monte-Carlo) so the GitHub Actions cron stays fast and cheap. Run after
fetch_matches.py. The heavy predictions never change post-deadline, so they (and
the embedded sim 'mean') are reused as-is.

Standings are exact zero-sum arithmetic:
    score_P = Σ_C  Wreal_C · ( N · v_P(C) − S_C )
where Wreal_C = real wins by country C so far, v_P(C) = points P placed on C,
S_C = total points all players placed on C, N = field size.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"
REPORT = HERE / "Totocalcio 2026.html"
INDEX = ROOT / "index.html"

opp = json.loads((DATA / "opponents.json").read_text(encoding="utf-8"))
FINAL = json.loads((HERE / "final_allocation.json").read_text(encoding="utf-8"))["allocation"]
N = opp["n_players"]
display_names = opp.get("display_names", {})
user_name = opp.get("user_name", "あなた")
outlier_set = set(opp.get("outliers", {}).keys())
ballots = list(opp["known"].items()) + list(opp.get("outliers", {}).items()) + [("あなた", FINAL)]
def disp(lab):
    return user_name if lab == "あなた" else display_names.get(lab, lab)

# S_C = total points every player placed on each country
S = {}
for _, alloc in ballots:
    for c, p in alloc.items():
        S[c] = S.get(c, 0) + p

wins = json.loads((DATA / "results.json").read_text(encoding="utf-8")).get("wins", {})

# reuse the sim 'mean' (expected net) already embedded — it is static post-deadline
mean_by = {}
m = re.search(r"const STANDINGS=(\[.*?\]);", REPORT.read_text(encoding="utf-8"), re.S)
if m:
    for r in json.loads(m.group(1)):
        mean_by[r["name"]] = r["mean"]

rows = []
for lab, alloc in ballots:
    nm = disp(lab)
    score = sum(w * (N * alloc.get(c, 0) - S.get(c, 0)) for c, w in wins.items())
    rows.append({"name": nm, "you": lab == "あなた", "joker": lab in outlier_set,
                 "score": int(score), "mean": mean_by.get(nm, 0)})
rows.sort(key=lambda r: (-r["score"], -r["mean"]))

sched = json.loads((DATA / "schedule.json").read_text(encoding="utf-8"))
SCHED = {"matches": sched["matches"],
         "finished": sum(1 for x in sched["matches"] if x["status"] == "FINISHED"),
         "asof": ""}

st_js = "const STANDINGS=" + json.dumps(rows, ensure_ascii=False) + ";"
sc_js = "const SCHEDULE=" + json.dumps(SCHED, ensure_ascii=False) + ";"
for f in (REPORT, INDEX):
    h = f.read_text(encoding="utf-8")
    h = re.sub(r"const STANDINGS=\[.*?\];", st_js, h, count=1, flags=re.S)
    h = re.sub(r"const SCHEDULE=\{.*?\};", sc_js, h, count=1, flags=re.S)
    f.write_text(h, encoding="utf-8")

print(f"live refresh: {SCHED['finished']}/104 finished · "
      f"{sum(wins.values())} wins · leader={rows[0]['name']} {rows[0]['score']:+d}")
