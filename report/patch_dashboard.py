"""One-shot patcher for the curated 'Totocalcio 2026.html' dashboard.
- Replaces the solo pick ladder (section 01) with an all-participants ballot grid
  (your card is just one highlighted card among 7 -> de-emphasised).
- Rebuilds the point-flow table (section 02) as a participant-switchable view with
  a best/worst/avg/percentile stat strip; zero-movement nations are dropped.
Keeps the existing dark-theme look; only adds CSS for the new dropdown/cards/stat.
Data is recomputed from the live model so the numbers stay correct.
"""
import json
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from sim.tournament import load_data, simulate, DATA
from optimize.allocate import (known_vectors, outlier_vectors, popularity,
                               sample_unknowns, vec_from_dict)

FILE = HERE / "Totocalcio 2026.html"

# ---- model + data ---------------------------------------------------------
d = load_data()
opp = json.loads((DATA / "opponents.json").read_text())
names, idx = d["names"], d["idx"]
res = simulate(n_sims=150_000, data=d)
ew, W = res["ewins"], res["wins"].astype(float)
implied = (1.0 / d["odds"]); implied /= implied.sum()
fifa = np.array([d["teams"][n]["fifa_rank"] for n in names], dtype=float)
FINAL = json.loads((HERE / "final_allocation.json").read_text())["allocation"]

kv = known_vectors(opp, idx); known_S = np.sum(kv, axis=0)
ballots = ([(k, opp["known"][k]) for k in "ABCDE"]
           + [("F", opp["outliers"]["F"]), ("あなた", FINAL)])
labels = [b[0] for b in ballots]
Vn = np.array([vec_from_dict(b[1], idx) for b in ballots])
NP = len(ballots); n_unk = 17 - NP
pop = popularity(kv, implied, fifa)
sum7 = Vn.sum(0); chalk = known_S / 5.0
rng = np.random.default_rng(7)
unkB = np.mean([np.sum(sample_unknowns(n_unk, pop, rng), axis=0) for _ in range(400)], axis=0)
ScA = sum7 + chalk * n_unk            # 本命集中型 pool total (17 ballots)
ScB = sum7 + unkB                     # FIFA-driven pool total
moveset = np.where((sum7 > 0) | (ScB >= 1.5))[0]
moveset = moveset[np.argsort(-ew[moveset])]

# net distribution per participant -> best/worst/avg/percentiles
Wd = W[:90_000]
rngD = np.random.default_rng(11)
fields = [sum7 + np.sum(sample_unknowns(n_unk, pop, rngD), axis=0) for _ in range(16)]


def stats_for(vi):
    arr = np.concatenate([Wd @ (17 * vi - Sc) for Sc in fields])
    r = lambda x: int(round(float(x)))
    return {"mean": r(arr.mean()), "median": r(np.median(arr)),
            "best": r(arr.max()), "worst": r(arr.min()),
            "p5": r(np.percentile(arr, 5)), "p25": r(np.percentile(arr, 25)),
            "p75": r(np.percentile(arr, 75)), "p95": r(np.percentile(arr, 95)),
            "pos": int(round(100 * float((arr >= 0).mean())))}


FLOW = {}
for i, lab in enumerate(labels):
    vi = Vn[i]
    rows = []
    for c in moveset:
        pw = 17 * vi[c] - ScB[c]
        tA = ew[c] * (17 * vi[c] - ScA[c]); tB = ew[c] * (17 * vi[c] - ScB[c])
        oth = (ScB[c] - vi[c]) / 16
        rows.append([names[c], round(float(ew[c]), 2), int(vi[c]),
                     round(float(oth), 1), int(round(float(pw))),
                     int(round(float(tA))), int(round(float(tB)))])
    FLOW[lab] = {"stats": stats_for(vi), "rows": rows}

BALLOTS = []
for lab, alloc in ballots:
    picks = sorted(alloc.items(), key=lambda x: -x[1])
    BALLOTS.append({"id": lab, "you": lab == "あなた", "joker": lab == "F",
                    "picks": [[p, nm] for nm, p in picks]})

# ---- HTML fragments -------------------------------------------------------
CSS_ADD = """
/* SWITCHABLE FLOW CONTROL */
.flowctl{display:flex;align-items:center;gap:14px 16px;flex-wrap:wrap;margin-bottom:16px}
.flowctl .flab{font-family:var(--cond);text-transform:uppercase;letter-spacing:.12em;font-weight:700;
  font-size:12px;color:var(--gold)}
select{font-family:var(--cond);font-weight:600;font-size:14px;letter-spacing:.04em;
  background:var(--surface2);color:var(--gold);border:1px solid var(--line2);border-radius:9px;
  padding:8px 14px;cursor:pointer;outline:none}
select:hover{border-color:var(--gold)}
.flowstat{display:flex;flex-wrap:wrap;align-items:center;gap:6px 18px;font-family:var(--mono);
  font-size:12px;color:var(--muted)}
.flowstat b{font-size:14.5px}
.flowstat .pctl{flex-basis:100%;color:var(--faint);font-size:11px;letter-spacing:.01em}
@media(min-width:721px){.flowstat .pctl{flex-basis:auto;margin-left:auto}}

/* BALLOT GRID */
.bgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(176px,1fr));gap:13px}
.bcard{background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden;
  transition:.2s}
.bcard:hover{border-color:var(--line2);transform:translateY(-2px)}
.bcard.you{border-color:rgba(246,196,81,.55);box-shadow:0 0 0 1px rgba(246,196,81,.22),0 0 22px rgba(246,196,81,.1)}
.bcard .bh{font-family:var(--cond);text-transform:uppercase;letter-spacing:.08em;font-weight:700;
  font-size:14.5px;padding:11px 15px;background:linear-gradient(90deg,var(--surface2),transparent);
  border-bottom:1px solid var(--line);color:var(--muted)}
.bcard.you .bh,.bcard.joker .bh{color:var(--gold)}
.bl{list-style:none;padding:7px 0 9px}
.bl li{display:flex;align-items:center;gap:8px;padding:3px 15px;font-size:12.5px}
.bl .bp{font-family:var(--disp);font-size:16px;color:var(--muted);width:22px;text-align:center;flex:none}
.bcard.you .bl .bp{color:var(--gold)}
.bl .flag{margin:0}
.bl .bn{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
"""

BALLOTS_BLOCK = """<!-- 01 BALLOTS -->
  <section id="pick">
    <div class="shead"><div class="num">01</div><div class="tt"><div class="ek">All Schedine · 7 Public Ballots</div><h2>参加者の予想（全配点）</h2></div>
      <div class="note">公表6人（A〜E＋<span style="color:var(--gold)">大穴F</span>）＋あなたの 10→1 配点。<span style="color:var(--gold)">金＝あなた</span>。残り10人は未公表。</div></div>
    <div class="bgrid" id="bgrid"></div>
  </section>

  """

FLOW_BLOCK = """<!-- 02 FLOW -->
  <section id="flow">
    <div class="shead"><div class="num">02</div><div class="tt"><div class="ek">Point Swings · Per Participant</div><h2>勝ち負けの点の動き</h2></div>
      <div class="note">参加者を切替。各国が1勝するごとの増減と大会通算（A＝本命集中型 / B＝FIFA主導、F込み）。<span class="pos">緑＝受取</span> / <span class="neg">赤＝支払</span>。点が動かない弱小国は省略。</div></div>
    <div class="flowctl">
      <span class="flab">参加者</span>
      <select id="flowSel"></select>
      <div class="flowstat" id="flowStat"></div>
    </div>
    <div class="tbl-wrap">
    <table id="flowTbl"><thead><tr><th style="text-align:left">国 / Nation</th><th>E[W]</th><th>配点</th><th>他/人</th><th>1勝</th><th>通算A</th><th>通算B</th></tr></thead><tbody id="flowBody"></tbody></table>
    </div>
  </section>

  """

DATA_JS = ("const FLOW=" + json.dumps(FLOW, ensure_ascii=False) + ";\n"
           "const BALLOTS=" + json.dumps(BALLOTS, ensure_ascii=False) + ";\n")

RENDER_JS = r"""
// ===== participant ballots (section 01) =====
(function(){
  const bg=document.getElementById('bgrid');
  BALLOTS.forEach(p=>{
    const c=document.createElement('div');
    c.className='bcard'+(p.you?' you':'')+(p.joker?' joker':'');
    let lis='';
    p.picks.forEach(([pt,nm])=>{lis+=`<li><span class="bp">${pt}</span><span class="flag">${FLAGS[nm]||''}</span><span class="bn">${nm}</span></li>`;});
    const tag=p.you?'あなた YOU':(p.joker?'F 🃏 大穴':'参加者 '+p.id);
    c.innerHTML=`<div class="bh">${tag}</div><ol class="bl">${lis}</ol>`;
    bg.appendChild(c);
  });
})();
// ===== switchable point-flow (section 02) =====
function fmtSigned(v){return (v>=0?'+':'')+v;}
function flowCell(v){
  if(!v) return '<td class="z">0</td>';
  const a=Math.min(.6,.13+Math.abs(v)/300*.55);
  const bg=v>0?`linear-gradient(90deg,rgba(55,219,130,${a}),rgba(55,219,130,${a*.25}))`
              :`linear-gradient(90deg,rgba(255,93,108,${a}),rgba(255,93,108,${a*.25}))`;
  const col=v>0?'#bff7d6':'#ffc6cd';
  return `<td class="hcell" style="background:${bg};color:${col};border-radius:5px">${fmtSigned(v)}</td>`;
}
function renderFlow(key){
  const d=FLOW[key]; if(!d) return;
  const body=document.getElementById('flowBody'); body.innerHTML='';
  d.rows.forEach(r=>{
    const nm=r[0],ew=r[1],pts=r[2],oth=r[3],pw=r[4],tA=r[5],tB=r[6];
    const tr=document.createElement('tr');
    const pc=pts?(''+pts):'<span class="z">0</span>';
    tr.innerHTML=`<td class="l"><span class="flag">${FLAGS[nm]||''}</span>${nm}</td>`+
      `<td>${ew.toFixed(2)}</td><td>${pc}</td><td>${oth.toFixed(1)}</td>`+
      flowCell(pw)+flowCell(tA)+flowCell(tB);
    body.appendChild(tr);
  });
  const s=d.stats;
  document.getElementById('flowStat').innerHTML=
    `<span>平均 <b class="${s.mean>=0?'pos':'neg'}">${fmtSigned(s.mean)}</b></span>`+
    `<span>ベスト <b class="pos">${fmtSigned(s.best)}</b></span>`+
    `<span>ワースト <b class="neg">${fmtSigned(s.worst)}</b></span>`+
    `<span>P(合計≥0) <b>${s.pos}%</b></span>`+
    `<span class="pctl">パーセンタイル 5% ${fmtSigned(s.p5)} · 25% ${fmtSigned(s.p25)} · 中央 ${fmtSigned(s.median)} · 75% ${fmtSigned(s.p75)} · 95% ${fmtSigned(s.p95)}</span>`;
}
(function(){
  const sel=document.getElementById('flowSel');
  Object.keys(FLOW).forEach(k=>{
    const o=document.createElement('option');o.value=k;
    o.textContent=(k==='あなた'?'あなた YOU':(k==='F'?'F 🃏 大穴':'参加者 '+k));
    sel.appendChild(o);
  });
  sel.value='あなた';
  sel.addEventListener('change',e=>renderFlow(e.target.value));
  renderFlow('あなた');
})();
"""

# ---- apply ----------------------------------------------------------------
html = FILE.read_text(encoding="utf-8")

# 1) CSS
html = html.replace("\n</style>", CSS_ADD + "</style>", 1)

# 2) section 01 (replace solo ladder with ballot grid)
head, rest = html.split("<!-- 01 PICK -->", 1)
_old, after01 = rest.split("<!-- 02 FLOW -->", 1)
html = head + BALLOTS_BLOCK + "<!-- 02 FLOW -->" + after01

# 3) section 02 (switchable flow)
head2, rest2 = html.split("<!-- 02 FLOW -->", 1)
_old2, after02 = rest2.split("<!-- 03 RIVALS -->", 1)
html = head2 + FLOW_BLOCK + "<!-- 03 RIVALS -->" + after02

# 4) JS: only flag the odds table on load (flow is now dynamic)
html = html.replace(
    "document.querySelectorAll('#flowTbl td.l, #oddsTbl td.l').forEach(prependFlag);",
    "document.querySelectorAll('#oddsTbl td.l').forEach(prependFlag);")

# 5) remove the old static flow recolor block (handled now inside renderFlow)
old_recolor = """// FLOW heat recolor by value
document.querySelectorAll('#flowTbl .hcell').forEach(td=>{
  const v=parseInt(td.textContent.replace('+',''),10);if(!v){return;}
  const a=Math.min(.6,.13+Math.abs(v)/300*.55);
  if(v>0){td.style.background=`linear-gradient(90deg,rgba(55,219,130,${a}),rgba(55,219,130,${a*.25}))`;td.style.color='#bff7d6';}
  else{td.style.background=`linear-gradient(90deg,rgba(255,93,108,${a}),rgba(255,93,108,${a*.25}))`;td.style.color='#ffc6cd';}
  td.style.borderRadius='5px';
});
"""
assert old_recolor in html, "recolor block not found"
html = html.replace(old_recolor, "")

# 6) inject data + render before </script>
html = html.replace("</script>", DATA_JS + RENDER_JS + "</script>", 1)

# 7) bump generation date
html = html.replace("2026-06-05", "2026-06-06")

FILE.write_text(html, encoding="utf-8")
print(f"patched -> {FILE.name} ({len(html):,} chars)")
print(f"  participants={labels}")
print(f"  moveset={len(moveset)} teams; FLOW keys={list(FLOW)}; BALLOTS={len(BALLOTS)}")
print("  stats:", {k: FLOW[k]["stats"]["mean"] for k in FLOW})
