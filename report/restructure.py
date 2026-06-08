"""Restructure the dashboard into 3 views:
  • ホーム      = next-3-matches + 順位表 + 早見表 + 参加者の予想 + 2 CTA buttons
  • 日程・結果  = 対戦スケジュール + グループ実況（結果）+ トーナメント結果(NEW)
  • AI予想・評価 = 参加者評価 + グループ予想 + 勝ち上がり + 予想決勝T + モデル
A sticky tab bar switches views (hash-routed). Only the home view shows on load.
Idempotent: guarded by a marker.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILE = HERE / "Totocalcio 2026.html"
INDEX = HERE.parent / "index.html"
html = FILE.read_text(encoding="utf-8")

if 'id="v-home"' in html:
    print("already restructured — nothing to do")
    raise SystemExit(0)

def sec(sid):
    m = re.search(r'  <section id="%s">.*?</section>' % sid, html, re.S)
    assert m, f"section not found: {sid}"
    return m.group(0)

hero = re.search(r'  <header class="hero">.*?</header>', html, re.S).group(0)
ticker = re.search(r'  <div class="ticker">.*?</div></div>', html, re.S).group(0)

NEXT3 = """  <section id="next3sec" class="next3sec">
    <div class="n3head"><span class="ek">Next 3 Matches</span><h3>次の3試合</h3></div>
    <div class="n3grid" id="n3"></div>
  </section>"""

KORES = """  <section id="koresults">
    <div class="shead"><div class="num">03</div><div class="tt"><div class="ek">Knockout · Live</div><h2>トーナメント結果</h2></div>
      <div class="note">決勝トーナメントの実際の対戦・結果（R32は6/28〜）。勝者をハイライト。国名クリックで日程。</div></div>
    <div class="kolist" id="koBody"></div>
  </section>"""

CTA = """  <div class="ctarow">
    <button class="ctabtn" data-v="results"><span class="ic">⚽</span><div><b>試合スケジュール・結果</b><span>日程 / グループ表 / トーナメント結果</span></div><span class="ar">→</span></button>
    <button class="ctabtn" data-v="ai"><span class="ic">🤖</span><div><b>AI予想・参加者評価</b><span>優勝確率 / 各自の評価 / モデル</span></div><span class="ar">→</span></button>
  </div>"""

home = "\n\n".join([hero, ticker, NEXT3, sec("standings"), sec("flow"), sec("pick"), CTA])
results = "\n\n".join([sec("schedule"), sec("results"), KORES])
ai = "\n\n".join([sec("rivals"), sec("groups"), sec("odds"), sec("bracket"), sec("model")])

NEWBODY = (f'  <div class="view" id="v-home">\n{home}\n  </div>\n\n'
           f'  <div class="view" id="v-results" hidden>\n{results}\n  </div>\n\n'
           f'  <div class="view" id="v-ai" hidden>\n{ai}\n  </div>')

# replace everything from the hero through the last section (model) with the views
old_region = re.search(r'  <header class="hero">.*</section>(?=\n\n  <div class="foot">)', html, re.S).group(0)
html = html.replace(old_region, NEWBODY, 1)

# ---- nav -> 3 view tabs ----
html = html.replace(
    '  <a href="#standings">順位表</a><a href="#results">結果</a><a href="#schedule">日程</a><a href="#pick">配点</a><a href="#flow">早見表</a><a href="#rivals">参加者</a>\n'
    '  <a href="#groups">グループ</a><a href="#odds">勝ち上がり</a><a href="#bracket">ブラケット</a>\n'
    '  <a href="#model">モデル</a>\n',
    '  <div class="tabs" id="tabs">\n'
    '    <button class="tab active" data-v="home">🏠 ホーム</button>\n'
    '    <button class="tab" data-v="results">⚽ 日程・結果</button>\n'
    '    <button class="tab" data-v="ai">🤖 AI予想・評価</button>\n'
    '  </div>\n', 1)

# ---- renumber section badges per view ----
for new, ek in [("02", "Point Swings"), ("03", "All Schedine"),       # home: flow, pick
                ("01", "Match Schedule"),                              # results: schedule
                ("01", "The 19-Player Pool"), ("02", "Final Standings"),
                ("03", "Road to the Final"), ("04", "Knockout"), ("05", "The Math")]:  # ai
    html = re.sub(r'<div class="num">\d\d</div><div class="tt"><div class="ek">' + re.escape(ek),
                  f'<div class="num">{new}</div><div class="tt"><div class="ek">{ek}', html, count=1)

# ---- CSS ----
CSS = r"""
/* ===== view tabs + views ===== */
.nav .tabs{display:flex;gap:6px;flex-wrap:wrap}
.tab{font-family:var(--cond);text-transform:uppercase;letter-spacing:.05em;font-weight:700;font-size:13px;
  padding:8px 15px;border-radius:9px;border:1px solid var(--line2);background:rgba(255,255,255,.04);color:var(--muted);cursor:pointer;transition:.15s}
.tab:hover{color:#fff;background:rgba(255,255,255,.08)}
.tab.active{color:#06101f;background:var(--gold);border-color:var(--gold);box-shadow:0 0 18px rgba(246,196,81,.4)}
.view{padding-top:8px}
.view[hidden]{display:none}
@media(max-width:520px){.tab{font-size:11.5px;padding:7px 11px}.nav .brandmark{font-size:13px}}

/* ===== next 3 matches ===== */
.next3sec{margin:18px 0 30px}
.n3head{display:flex;align-items:baseline;gap:12px;margin-bottom:13px}
.n3head .ek{font-family:var(--cond);text-transform:uppercase;letter-spacing:.2em;font-weight:700;font-size:11px;color:var(--gold2)}
.n3head h3{font-size:20px;font-weight:900}
.n3grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
@media(max-width:680px){.n3grid{grid-template-columns:1fr}}
.n3card{background:linear-gradient(160deg,var(--surface2),var(--surface));border:1px solid var(--line2);border-radius:14px;padding:14px 16px}
.n3when{font-family:var(--mono);font-size:12px;color:var(--gold2);margin-bottom:9px}
.n3teams{display:flex;align-items:center;gap:9px;flex-wrap:wrap;font-size:15px;font-weight:700}
.n3teams .tm{display:inline-flex;align-items:center;gap:6px;cursor:pointer}.n3teams .tm:hover{color:var(--gold2)}
.n3teams .tm.tbd{color:var(--faint);cursor:default}
.n3vs{color:var(--faint);font-size:11px;font-family:var(--mono);font-weight:400}
.n3stage{font-size:11px;color:var(--faint);margin-top:9px;font-family:var(--mono)}

/* ===== CTA buttons to the two sub-views ===== */
.ctarow{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:36px 0 8px}
@media(max-width:680px){.ctarow{grid-template-columns:1fr}}
.ctabtn{display:flex;align-items:center;gap:15px;text-align:left;cursor:pointer;width:100%;
  background:linear-gradient(120deg,var(--surface2),var(--surface));border:1px solid var(--line2);border-radius:16px;padding:18px 20px;transition:border-color .15s,transform .1s}
.ctabtn:hover{border-color:var(--gold);transform:translateY(-1px)}
.ctabtn .ic{font-size:30px;flex:none}
.ctabtn>div{flex:1;display:flex;flex-direction:column;gap:3px}
.ctabtn b{font-size:16px;font-weight:900;color:var(--txt)}
.ctabtn>div span{font-size:12px;color:var(--muted)}
.ctabtn .ar{font-family:var(--disp);font-size:24px;color:var(--gold);flex:none}

/* ===== knockout results ===== */
.kolist{display:flex;flex-direction:column;gap:13px}
.koround{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:10px 15px}
.korh{font-family:var(--cond);text-transform:uppercase;letter-spacing:.12em;font-weight:700;font-size:13px;color:var(--gold2);margin-bottom:6px}
.korn{color:var(--faint);font-size:11px;margin-left:6px;font-weight:400}
.korow{display:grid;grid-template-columns:58px 1fr;gap:12px;align-items:center;padding:7px 2px;border-top:1px solid var(--line)}
.korow:first-of-type{border-top:none}
.kot{font-family:var(--mono);font-size:11px;color:var(--faint)}
.koteams{display:flex;align-items:center;gap:9px;flex-wrap:wrap;font-size:14px}
.koteams .tm{display:inline-flex;align-items:center;gap:5px;cursor:pointer}.koteams .tm:hover{color:var(--gold2)}
.koteams .tm.tbd{color:var(--faint);cursor:default}
.koteams .win{font-weight:800;color:var(--gold2)}
.koteams .vs{color:var(--faint);font-size:11px;font-family:var(--mono)}
.koteams .mscore{font-family:var(--mono);font-weight:700}.koteams .mscore .pen{color:var(--faint);font-size:11px;font-weight:400}
"""
html = html.replace("\n</style>", CSS + "</style>", 1)

# ---- JS: tz handler also refreshes KO ----
html = html.replace(
    "tzCur=b.dataset.tz; document.querySelectorAll('#tzbar .tzbtn[data-tz]').forEach(x=>x.classList.toggle('on',x===b)); renderSchedule();",
    "tzCur=b.dataset.tz; document.querySelectorAll('#tzbar .tzbtn[data-tz]').forEach(x=>x.classList.toggle('on',x===b)); renderSchedule(); renderKO();", 1)

# ---- JS: render fns + view router ----
JS = r"""
// ======================= views: next-3 + knockout + router =======================
function renderNext3(){
  const wrap=document.getElementById('n3'); if(!wrap) return;
  const Z='Asia/Tokyo';
  const up=SCHEDULE.matches.filter(m=>m.status!=='FINISHED').slice(0,3);
  let h='';
  up.forEach(m=>{
    const tag=m.group?`${m.group.replace('GROUP_','')}組`:(STAGE_JP[m.stage]||'');
    h+=`<div class="n3card"><div class="n3when">${fmtD(m.utc,Z)} ${fmtT(m.utc,Z)} <span style="color:var(--faint)">日本時間</span></div>`+
       `<div class="n3teams">${teamSpan(m.home)} <span class="n3vs">vs</span> ${teamSpan(m.away)}</div>`+
       `<div class="n3stage">${tag}</div></div>`;
  });
  wrap.innerHTML=h||'<div class="lbnote">予定なし。</div>';
}
function renderKO(){
  const wrap=document.getElementById('koBody'); if(!wrap) return;
  const zone=zoneOf();
  const order=[['LAST_32','ラウンド32'],['LAST_16','ラウンド16'],['QUARTER_FINALS','準々決勝'],['SEMI_FINALS','準決勝'],['THIRD_PLACE','3位決定戦'],['FINAL','決勝']];
  let h='';
  order.forEach(([st,lab])=>{
    const ms=SCHEDULE.matches.filter(m=>m.stage===st); if(!ms.length) return;
    let rows='';
    ms.forEach(m=>{
      const fin=m.status==='FINISHED', hw=fin&&m.winner==='HOME_TEAM', aw=fin&&m.winner==='AWAY_TEAM';
      const mid=fin?`<span class="mscore">${m.score[0]}–${m.score[1]}${m.pens?` <span class="pen">PK ${m.pens[0]}-${m.pens[1]}</span>`:''}</span>`:'<span class="vs">vs</span>';
      rows+=`<div class="korow"><span class="kot">${fmtD(m.utc,zone)}</span><div class="koteams">${teamSpan(m.home,hw)} ${mid} ${teamSpan(m.away,aw)}</div></div>`;
    });
    h+=`<div class="koround"><div class="korh">${lab}<span class="korn">${ms.length}試合</span></div>${rows}</div>`;
  });
  wrap.innerHTML=h;
}
function switchView(v){
  ['home','results','ai'].forEach(x=>{ const el=document.getElementById('v-'+x); if(el)el.hidden=(x!==v); });
  document.querySelectorAll('#tabs .tab').forEach(b=>b.classList.toggle('active',b.dataset.v===v));
  if(('#'+v)!==location.hash) history.replaceState(null,'','#'+v);
  window.scrollTo(0,0);
}
(function(){
  renderNext3(); renderKO();
  document.querySelectorAll('[data-v]').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.v)));
  const iv=(location.hash||'').replace('#',''); switchView(['home','results','ai'].includes(iv)?iv:'home');
})();
"""
html = html.replace("\n</script>", JS + "</script>", 1)

FILE.write_text(html, encoding="utf-8")
INDEX.write_text(html, encoding="utf-8")
print(f"restructured -> {FILE.name} (+ index.html) ({len(html):,} chars)")
