"""Augment section 03 (参加者評価) of the curated dashboard with
best / worst / average / percentile distribution per participant.

No re-simulation: EV指数 / P(1位) / 平均順位 / 診断 are parsed from the existing
static table; the net distribution stats (mean/best/worst/p5..p95) are taken from
the FLOW object already embedded by patch_dashboard.py — guaranteeing the rivals
section and the flow section show identical numbers. The static table is replaced
by a dynamic render that adds the new columns plus a compact box-plot.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILE = HERE / "Totocalcio 2026.html"
html = FILE.read_text(encoding="utf-8")

# ---- pull the embedded FLOW stats ----------------------------------------
FLOW = json.loads(re.search(r"const FLOW=(\{.*?\});\nconst BALLOTS=", html, re.S).group(1))

# ---- parse the existing static rival rows --------------------------------
tbl = re.search(r'<table id="rivalTbl">.*?</table>', html, re.S).group(0)
rows = [tr for tr in re.findall(r"<tr.*?</tr>", tbl, re.S) if 'td class="l"' in tr]
RIVALS = []
for tr in rows:
    you = 'class="you"' in tr
    joker = 'class="joker"' in tr
    lcell = re.search(r'<td class="l">(.*?)</td>', tr, re.S).group(1)
    if you:
        pid = "あなた"
    elif joker:
        pid = "F"
    else:
        pid = re.sub(r"<[^>]+>", "", lcell).strip()
    ev = int(re.search(r'<td class="l">.*?</td><td>(\d+)</td>', tr, re.S).group(1))
    p1 = float(re.search(r'data-w="([\d.]+)"', tr).group(1))
    rank = float(re.search(r'data-w="[\d.]+".*?</td><td>([\d.]+)</td>', tr, re.S).group(1))
    diag = re.search(r'<td class="diag">(.*?)</td>', tr, re.S).group(1).strip()
    s = FLOW[pid]["stats"]
    RIVALS.append({"id": pid, "you": you, "joker": joker, "ev": ev, "p1": p1,
                   "rank": rank, "diag": diag, **s})

lo = min(r["worst"] for r in RIVALS)
hi = max(r["best"] for r in RIVALS)

# ---- new table shell (dynamic body) --------------------------------------
NEW_TBL = ('<table id="rivalTbl"><thead><tr>'
           '<th style="text-align:left">参加者</th><th>EV指数</th>'
           '<th style="text-align:left">P(1位)</th><th>平均順位</th>'
           '<th>平均</th><th>ベスト</th><th>ワースト</th>'
           '<th style="text-align:left">分布 5–95% ・中央</th>'
           '<th style="text-align:left">診断</th>'
           '</tr></thead><tbody id="rivalBody"></tbody></table>')
html = html.replace(tbl, NEW_TBL, 1)

# update the section note
html = html.replace(
    "残り10人は未公表（FIFAランク主導と仮定）。17人ゼロサム評価。</div>",
    "残り10人は未公表（FIFAランク主導と仮定）。平均/ベスト/ワースト/分布＝全シミュレーションの合計点。</div>",
    1)

# ---- CSS: box-plot --------------------------------------------------------
CSS_ADD = """
/* PARTICIPANT DISTRIBUTION BOX-PLOT */
.bx{position:relative;height:22px;min-width:158px;background:rgba(255,255,255,.04);border-radius:5px}
.bx .zero{position:absolute;top:0;bottom:0;width:1px;background:rgba(255,255,255,.22)}
.bx .wk{position:absolute;top:50%;height:2px;transform:translateY(-50%);
  background:var(--line2);border-radius:2px}
.bx .pt{position:absolute;top:50%;width:1px;height:9px;transform:translateY(-50%);background:var(--muted)}
.bx .bxbox{position:absolute;top:4px;bottom:4px;border-radius:3px;
  background:linear-gradient(90deg,rgba(246,196,81,.5),rgba(246,196,81,.22));
  border:1px solid rgba(246,196,81,.55)}
.bx .med{position:absolute;top:2px;bottom:2px;width:2px;background:#fff;border-radius:2px}
"""
html = html.replace("\n</style>", CSS_ADD + "</style>", 1)

# ---- render JS ------------------------------------------------------------
DATA_JS = ("const RIVALS=" + json.dumps(RIVALS, ensure_ascii=False) + ";\n"
           "const RIVDOM=[" + str(lo) + "," + str(hi) + "];\n")

RENDER_JS = r"""
// ===== participant evaluation (section 03) with dist box-plot =====
(function(){
  const body=document.getElementById('rivalBody'); if(!body) return;
  const maxp1=Math.max.apply(null,RIVALS.map(r=>r.p1));
  const lo=RIVDOM[0],hi=RIVDOM[1];
  const X=v=>Math.max(0,Math.min(100,(v-lo)/(hi-lo)*100));
  const sg=v=>(v>=0?'+':'')+v;
  function bx(r){
    const z=X(0),wl=X(r.worst),wr=X(r.best),b1=X(r.p25),b2=X(r.p75),md=X(r.median),q5=X(r.p5),q95=X(r.p95);
    const t=`ワースト ${r.worst} · 5% ${r.p5} · 25% ${r.p25} · 中央 ${r.median} · 75% ${r.p75} · 95% ${r.p95} · ベスト ${r.best}`;
    return `<div class="bx" title="${t}">`+
      `<div class="zero" style="left:${z}%"></div>`+
      `<div class="wk" style="left:${wl}%;width:${(wr-wl)}%"></div>`+
      `<div class="pt" style="left:${q5}%"></div><div class="pt" style="left:${q95}%"></div>`+
      `<div class="bxbox" style="left:${b1}%;width:${Math.max(1.2,b2-b1)}%"></div>`+
      `<div class="med" style="left:${md}%"></div></div>`;
  }
  RIVALS.forEach(r=>{
    const tr=document.createElement('tr');
    if(r.you) tr.className='you';
    const lab=r.you?'あなた YOU':(r.joker?'<span class="joker">F</span> 🃏':r.id);
    const mc=r.mean>=0?'pos':'neg';
    tr.innerHTML=
      `<td class="l">${lab}</td>`+
      `<td>${r.ev}</td>`+
      `<td class="barcell"><span class="v">${r.p1}%</span><div class="track"><div class="fill" style="--w:${(r.p1/maxp1*100).toFixed(0)}%"></div></div></td>`+
      `<td>${r.rank.toFixed(1)}</td>`+
      `<td class="${mc}">${sg(r.mean)}</td>`+
      `<td class="pos">${sg(r.best)}</td>`+
      `<td class="neg">${sg(r.worst)}</td>`+
      `<td>${bx(r)}</td>`+
      `<td class="diag">${r.diag}</td>`;
    body.appendChild(tr);
  });
})();
"""
html = html.replace("</script>", DATA_JS + RENDER_JS + "</script>", 1)

FILE.write_text(html, encoding="utf-8")
print(f"patched rivals -> {FILE.name} ({len(html):,} chars)")
print(f"  participants={[r['id'] for r in RIVALS]}")
print(f"  domain=[{lo},{hi}]")
for r in RIVALS:
    print(f"   {r['id']:<5} mean {r['mean']:+5d}  best {r['best']:+5d}  worst {r['worst']:+5d}  "
          f"p5 {r['p5']:+5d}  med {r['median']:+5d}  p95 {r['p95']:+5d}")
