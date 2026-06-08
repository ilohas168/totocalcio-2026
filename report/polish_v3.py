"""v3 polish:
 1. 次の3試合 — add a timezone toggle (日本/米ET/スイス); all tz buttons app-wide
    now drive one shared setTZ() so home + schedule + KO stay in sync.
 2. トーナメント結果 — replace the long round-by-round list with a compact
    bracket graph (columns per round; flag + score cells; winner glows gold).
Operates on the report HTML, copies to index. Guarded by a marker.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILE = HERE / "Totocalcio 2026.html"
INDEX = HERE.parent / "index.html"
html = FILE.read_text(encoding="utf-8")

if 'class="kobr"' in html or "function setTZ" in html:
    print("already v3 — nothing to do")
    raise SystemExit(0)

def rep(old, new):
    global html
    assert old in html, f"NOT FOUND: {old[:70]!r}"
    html = html.replace(old, new, 1)

# ---- 1a. next-3 tz toggle in the header ----
rep('    <div class="n3head"><span class="ek">Next 3 Matches</span><h3>次の3試合</h3></div>',
    '    <div class="n3head"><span class="ek">Next 3 Matches</span><h3>次の3試合</h3>'
    '<div class="n3tz"><button class="n3tzb on" data-tz="jp">日本</button>'
    '<button class="n3tzb" data-tz="us">米ET</button>'
    '<button class="n3tzb" data-tz="ch">スイス</button></div></div>')

# ---- 1b. tzFull() + setTZ() helpers (shared) ----
rep("function zoneOf(){return (TZ.find(t=>t.id===tzCur)||TZ[0]).zone;}",
    "function zoneOf(){return (TZ.find(t=>t.id===tzCur)||TZ[0]).zone;}\n"
    "function tzFull(){return {jp:'日本時間',us:'米国時間 ET',ch:'スイス時間'}[tzCur]||'';}\n"
    "function setTZ(tz){tzCur=tz;document.querySelectorAll('[data-tz]').forEach(x=>x.classList.toggle('on',x.dataset.tz===tz));renderSchedule();renderKO();renderNext3();}")

# ---- 1c. next-3 uses current tz + dynamic label ----
rep("""function renderNext3(){
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
}""",
    """function renderNext3(){
  const wrap=document.getElementById('n3'); if(!wrap) return;
  const Z=zoneOf();
  const up=SCHEDULE.matches.filter(m=>m.status!=='FINISHED').slice(0,3);
  let h='';
  up.forEach(m=>{
    const tag=m.group?`${m.group.replace('GROUP_','')}組`:(STAGE_JP[m.stage]||'');
    h+=`<div class="n3card"><div class="n3when">${fmtD(m.utc,Z)} ${fmtT(m.utc,Z)} <span style="color:var(--faint)">${tzFull()}</span></div>`+
       `<div class="n3teams">${teamSpan(m.home)} <span class="n3vs">vs</span> ${teamSpan(m.away)}</div>`+
       `<div class="n3stage">${tag}</div></div>`;
  });
  wrap.innerHTML=h||'<div class="lbnote">予定なし。</div>';
}""")

# ---- 1d. wire ALL [data-tz] buttons to the shared setTZ ----
rep("""  document.querySelectorAll('#tzbar .tzbtn[data-tz]').forEach(b=>b.onclick=()=>{
    tzCur=b.dataset.tz; document.querySelectorAll('#tzbar .tzbtn[data-tz]').forEach(x=>x.classList.toggle('on',x===b)); renderSchedule(); renderKO();
  });""",
    "  document.querySelectorAll('[data-tz]').forEach(b=>b.onclick=()=>setTZ(b.dataset.tz));")

# ---- 2a. knockout list -> compact bracket graph ----
rep("""function renderKO(){
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
}""",
    """function renderKO(){
  const wrap=document.getElementById('koBody'); if(!wrap) return;
  const cols=[['LAST_32','R32'],['LAST_16','R16'],['QUARTER_FINALS','準々'],['SEMI_FINALS','準決'],['FINAL','決勝'],['THIRD_PLACE','3位']];
  const f=(nm,win)=> nm
    ? `<span class="kf${win?' w':''}" title="${nm}" onclick="event.stopPropagation();openCountry('${esc(nm)}')">${FLAGS[nm]||'🏳'}</span>`
    : '<span class="kf tbd">·</span>';
  let h='';
  cols.forEach(([st,lab])=>{
    const ms=SCHEDULE.matches.filter(m=>m.stage===st); if(!ms.length) return;
    let cells='';
    ms.forEach(m=>{
      const fin=m.status==='FINISHED', hw=fin&&m.winner==='HOME_TEAM', aw=fin&&m.winner==='AWAY_TEAM';
      const sc=fin?`<span class="ks">${m.score[0]}-${m.score[1]}${m.pens?'p':''}</span>`:'<span class="ks tbd">–</span>';
      const t=`${m.home||'?'} vs ${m.away||'?'}${fin?` ${m.score[0]}-${m.score[1]}`:''}`;
      cells+=`<div class="kocell" title="${t}">${f(m.home,hw)}${sc}${f(m.away,aw)}</div>`;
    });
    h+=`<div class="kocol"><div class="kocolh">${lab}<span class="kocn">${ms.length}</span></div><div class="kocells">${cells}</div></div>`;
  });
  wrap.innerHTML=`<div class="kobr">${h}</div>`;
}""")

# ---- 2b. note tweak ----
rep('決勝トーナメントの実際の対戦・結果（R32は6/28〜）。勝者をハイライト。国名クリックで日程。',
    '決勝トーナメントの実際の対戦・結果（R32は6/28〜）。勝者を金でハイライト・横スクロール可。国旗クリックで日程。')

# ---- CSS: replace knockout-list styles with bracket + add n3 toggle ----
rep("""/* ===== knockout results ===== */
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
.koteams .mscore{font-family:var(--mono);font-weight:700}.koteams .mscore .pen{color:var(--faint);font-size:11px;font-weight:400}""",
    """/* ===== next-3 tz toggle ===== */
.n3tz{display:flex;gap:5px;margin-left:auto;align-self:center}
.n3tzb{font-family:var(--cond);text-transform:uppercase;letter-spacing:.03em;font-weight:700;font-size:11px;padding:5px 11px;border-radius:999px;border:1px solid var(--line2);background:var(--surface);color:var(--muted);cursor:pointer}
.n3tzb.on{background:var(--gold);color:#1a1304;border-color:var(--gold)}
@media(max-width:680px){.n3head{flex-wrap:wrap}.n3tz{margin-left:0;width:100%}}
/* ===== knockout bracket (compact graph) ===== */
.kobr{display:flex;gap:10px;overflow-x:auto;padding-bottom:10px;align-items:stretch}
.kocol{display:flex;flex-direction:column;min-width:90px;flex:none}
.kocolh{font-family:var(--cond);text-transform:uppercase;letter-spacing:.08em;font-weight:700;font-size:11px;color:var(--gold2);text-align:center;margin-bottom:8px}
.kocn{color:var(--faint);font-size:9px;margin-left:4px}
.kocells{display:flex;flex-direction:column;justify-content:space-around;flex:1;gap:6px}
.kocell{display:flex;align-items:center;justify-content:center;gap:7px;background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:6px 7px}
.kocell:hover{border-color:var(--line2)}
.kf{font-size:17px;cursor:pointer;opacity:.9;filter:grayscale(.25)}
.kf.w{filter:none;opacity:1;text-shadow:0 0 9px rgba(246,196,81,.65)}
.kf.tbd{opacity:.3;cursor:default;filter:none}
.ks{font-family:var(--mono);font-size:12px;font-weight:700;color:var(--txt);min-width:30px;text-align:center}
.ks.tbd{color:var(--faint);font-weight:400}""")

FILE.write_text(html, encoding="utf-8")
INDEX.write_text(html, encoding="utf-8")
print(f"v3 -> {FILE.name} (+ index.html) ({len(html):,} chars)")
