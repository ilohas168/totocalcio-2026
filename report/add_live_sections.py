"""One-time structural patch: add the LIVE sections (順位表 + 対戦スケジュール) to the
curated dashboard — markup, CSS, the country-fixtures popup, and render JS.

Data consts (STANDINGS / SCHEDULE) are left as empty placeholders here; they are
filled on every run by refresh_dashboard_data.py (which reads results.json +
schedule.json). Idempotent: re-running is a no-op once the marker is present.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILE = HERE / "Totocalcio 2026.html"
html = FILE.read_text(encoding="utf-8")

if 'id="standings"' in html:
    print("already patched — nothing to do")
    raise SystemExit(0)

# ---------------------------------------------------------------- CSS --------
CSS_ADD = r"""
/* ===== LIVE: STANDINGS (順位表) ===== */
.lbnote{font-size:12px;color:var(--faint);margin:-6px 0 16px;line-height:1.6}
.lb{display:flex;flex-direction:column;gap:7px}
.lbrow{display:grid;grid-template-columns:36px 1fr auto;align-items:center;gap:13px;
  background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:11px 16px;cursor:pointer;transition:border-color .15s}
.lbrow:hover{border-color:var(--line2)}
.lbrow.you{border-color:rgba(246,196,81,.45);background:linear-gradient(180deg,rgba(246,196,81,.06),var(--surface))}
.lbrk{font-family:var(--disp);font-size:23px;color:var(--faint);text-align:center;line-height:1}
.lbrow.top1 .lbrk{color:var(--gold)} .lbrow.top2 .lbrk{color:#cfd8ee} .lbrow.top3 .lbrk{color:#d99a5b}
.lbnm{font-weight:800;font-size:15px;letter-spacing:.01em}
.lbnm .jk{font-size:12px}
.lbsub{font-size:11px;color:var(--faint);margin-top:1px;font-family:var(--mono)}
.lbpts{font-family:var(--mono);font-size:19px;font-weight:700;text-align:right;white-space:nowrap}
.lbbar{grid-column:1/-1;height:4px;border-radius:3px;background:rgba(255,255,255,.05);overflow:hidden;margin-top:3px;position:relative}
.lbbar i{position:absolute;top:0;height:100%;border-radius:3px}
.lbbar .ctr{position:absolute;left:50%;top:-1px;bottom:-1px;width:1px;background:rgba(255,255,255,.18)}

/* ===== LIVE: SCHEDULE (日程) ===== */
.tzbar{display:flex;gap:7px;margin:-4px 0 14px;flex-wrap:wrap;align-items:center}
.tzbtn{font-family:var(--cond);text-transform:uppercase;letter-spacing:.1em;font-weight:700;font-size:12px;
  padding:7px 15px;border-radius:999px;border:1px solid var(--line2);background:var(--surface);color:var(--muted);cursor:pointer}
.tzbtn.on{background:var(--gold);color:#1a1304;border-color:var(--gold)}
.tzsep{width:1px;height:20px;background:var(--line2);margin:0 3px}
.scchip{margin-left:auto;display:none;align-items:center;gap:7px;font-size:12.5px;background:var(--surface2);
  border:1px solid var(--line2);border-radius:999px;padding:5px 8px 5px 12px}
.scchip.on{display:inline-flex}
.scchip b{cursor:pointer;color:var(--neg);font-size:14px}
.schedscroll{max-height:580px;overflow-y:auto;border:1px solid var(--line);border-radius:14px;background:var(--bg2);padding:4px 12px 12px}
.daygrp{margin-top:6px}
.dayhd{position:sticky;top:0;z-index:2;font-family:var(--cond);text-transform:uppercase;letter-spacing:.12em;font-weight:700;
  font-size:13px;color:var(--gold2);padding:11px 2px 7px;border-bottom:1px solid var(--line);margin-bottom:8px;
  background:linear-gradient(180deg,var(--bg2) 70%,transparent)}
.mrow{display:grid;grid-template-columns:52px 1fr auto;gap:13px;align-items:center;padding:9px 13px;
  border:1px solid var(--line);border-radius:11px;background:var(--surface);margin-bottom:6px}
.mtime{font-family:var(--mono);font-size:14px;color:var(--txt);font-weight:600;text-align:center}
.mteams{display:flex;align-items:center;gap:9px;flex-wrap:wrap;font-size:14px}
.mteams .tm{display:inline-flex;align-items:center;gap:5px;cursor:pointer}
.mteams .tm:hover{color:var(--gold2)}
.mteams .tm.tbd{color:var(--faint);cursor:default}
.mteams .vs{color:var(--faint);font-size:11px;font-family:var(--mono)}
.mteams .win{font-weight:800;color:var(--gold2)}
.mteams .mscore{font-family:var(--mono);font-weight:700;font-size:14px}
.mteams .mscore .pen{color:var(--faint);font-size:11px;font-weight:400}
.mbadge{font-family:var(--mono);font-size:10.5px;color:var(--faint);text-align:right;white-space:nowrap;line-height:1.4}
@media(max-width:560px){.mrow{grid-template-columns:46px 1fr;gap:10px}.mbadge{grid-column:2;text-align:left;margin-top:-2px}}
.cmsub{font-family:var(--mono);font-size:12px;color:var(--muted);margin:-2px 0 12px}
"""
html = html.replace("\n</style>", CSS_ADD + "</style>", 1)

# ---------------------------------------------------------------- NAV --------
html = html.replace(
    '<a href="#pick">配点</a>',
    '<a href="#standings">順位表</a><a href="#schedule">日程</a><a href="#pick">配点</a>', 1)

# ------------------------------------------------------------ SECTIONS -------
SECS = """  <!-- 01 STANDINGS (live) -->
  <section id="standings">
    <div class="shead"><div class="num">01</div><div class="tt"><div class="ek">Live Leaderboard</div><h2>順位表</h2></div>
      <div class="note">試合結果から自動集計する実際の順位（ゼロサム）。行を<b>クリックで個人詳細</b>。</div></div>
    <div class="lbnote" id="lbNote"></div>
    <div class="lb" id="lbBody"></div>
  </section>

  <!-- 02 SCHEDULE -->
  <section id="schedule">
    <div class="shead"><div class="num">02</div><div class="tt"><div class="ek">Match Schedule</div><h2>対戦スケジュール</h2></div>
      <div class="note">全104試合。時刻は選択タイムゾーン（米＝東部ET）。国名を<b>クリックでその国の日程</b>。</div></div>
    <div class="tzbar" id="tzbar">
      <button class="tzbtn on" data-tz="jp">🇯🇵 日本</button>
      <button class="tzbtn" data-tz="us">🇺🇸 米 ET</button>
      <button class="tzbtn" data-tz="ch">🇨🇭 スイス</button>
      <span class="tzsep"></span>
      <button class="tzbtn on" data-st="all">全試合</button>
      <button class="tzbtn" data-st="group">グループ</button>
      <button class="tzbtn" data-st="ko">決勝T</button>
      <span class="scchip" id="scChip"><span id="scChipNm"></span><b onclick="clearCountry()">✕</b></span>
    </div>
    <div class="schedscroll"><div id="schedBody"></div></div>
  </section>

"""
html = html.replace("  <!-- 01 BALLOTS -->", SECS + "  <!-- 03 BALLOTS -->", 1)

# renumber the existing seven sections (01..07 -> 03..09)
RENUM = [("01", "03", "All Schedine"), ("02", "04", "Point Swings"),
         ("03", "05", "The 19-Player Pool"), ("04", "06", "Final Standings"),
         ("05", "07", "Road to the Final"), ("06", "08", "Knockout"),
         ("07", "09", "The Math")]
for old, new, ek in RENUM:
    a = f'<div class="num">{old}</div><div class="tt"><div class="ek">{ek}'
    b = f'<div class="num">{new}</div><div class="tt"><div class="ek">{ek}'
    assert a in html, f"renumber anchor missing: {ek}"
    html = html.replace(a, b, 1)

# ------------------------------------------------------ COUNTRY POPUP --------
CMODAL = """<div class="modal" id="cmodal" onclick="if(event.target===this)closeCountry()"><div class="modalbox">
  <div class="modalhead"><span class="mt" id="cmTitle"></span><button class="modalx" onclick="closeCountry()">×</button></div>
  <div class="cmsub" id="cmSub"></div>
  <div id="cmBody"></div>
</div></div>

<script>"""
html = html.replace("\n<script>\nconst FLAGS=", "\n" + CMODAL + "\nconst FLAGS=", 1)

# -------------------------------------------------------- RENDER JS ----------
JS_ADD = r"""
// ======================= LIVE: standings + schedule =======================
const STANDINGS=[];
const SCHEDULE={"matches":[],"finished":0,"asof":""};
const TZ=[{id:'jp',label:'日本',zone:'Asia/Tokyo'},{id:'us',label:'米 ET',zone:'America/New_York'},{id:'ch',label:'スイス',zone:'Europe/Zurich'}];
const STAGE_JP={GROUP_STAGE:'グループ',LAST_32:'R32',LAST_16:'R16',QUARTER_FINALS:'準々決勝',SEMI_FINALS:'準決勝',THIRD_PLACE:'3位決定',FINAL:'決勝'};
let tzCur='jp', scStage='all', scCountry=null;
const esc=s=>(''+s).replace(/'/g,"\\'");
function zoneOf(){return (TZ.find(t=>t.id===tzCur)||TZ[0]).zone;}
function fmtD(utc,zone){return new Date(utc).toLocaleDateString('ja-JP',{timeZone:zone,month:'numeric',day:'numeric',weekday:'short'});}
function fmtT(utc,zone){return new Date(utc).toLocaleTimeString('en-GB',{timeZone:zone,hour:'2-digit',minute:'2-digit',hour12:false});}
function dKey(utc,zone){return new Date(utc).toLocaleDateString('en-CA',{timeZone:zone});}

// ---- standings ----
function renderStandings(){
  const wrap=document.getElementById('lbBody'); if(!wrap) return;
  const live=SCHEDULE.finished>0;
  const note=document.getElementById('lbNote');
  note.innerHTML=live
    ? `⚽️ <b>${SCHEDULE.finished}/104</b> 試合終了 — 実際の獲得点（勝ち＝グループ勝利 or 決勝T進出/PK勝ち）。サブは全シミュレーション平均。`
    : `⚽️ <b>大会開始前</b>。全員0点。<b>6/11開幕</b>後、試合結果を自動反映して順位が動きます。サブの「予想平均」は全シミュレーションの期待値（＝今の本命）。`;
  const mx=Math.max(1,...STANDINGS.map(r=>Math.abs(r.score)));
  let h='';
  STANDINGS.forEach((r,i)=>{
    const rk=i+1, cls=['lbrow']; if(r.you)cls.push('you'); if(rk<=3)cls.push('top'+rk);
    const sc=r.score, sg=(sc>=0?'+':'')+sc, pct=Math.abs(sc)/mx*50;
    const bar=sc>=0?`<i style="left:50%;width:${pct}%;background:var(--pos)"></i>`
                   :`<i style="left:${50-pct}%;width:${pct}%;background:var(--neg)"></i>`;
    const nm=r.joker?`${r.name} <span class="jk">🃏</span>`:r.name;
    h+=`<div class="${cls.join(' ')}" onclick="openModal('${esc(r.name)}')">`+
       `<div class="lbrk">${rk}</div>`+
       `<div><div class="lbnm">${nm}</div><div class="lbsub">予想平均 ${r.mean>=0?'+':''}${r.mean}</div></div>`+
       `<div class="lbpts ${sc>0?'pos':(sc<0?'neg':'')}">${live?sg:'—'}</div>`+
       `<div class="lbbar"><div class="ctr"></div>${live?bar:''}</div></div>`;
  });
  wrap.innerHTML=h;
}

// ---- schedule ----
function teamSpan(nm,win){
  if(!nm) return '<span class="tm tbd">未定</span>';
  return `<span class="tm${win?' win':''}" onclick="event.stopPropagation();openCountry('${esc(nm)}')"><span class="flag">${FLAGS[nm]||''}</span>${nm}</span>`;
}
function matchRow(m,zone){
  const fin=m.status==='FINISHED';
  const hw=fin&&m.winner==='HOME_TEAM', aw=fin&&m.winner==='AWAY_TEAM';
  const mid=fin
    ? `<span class="mscore">${m.score[0]}–${m.score[1]}${m.pens?` <span class="pen">PK ${m.pens[0]}-${m.pens[1]}</span>`:''}</span>`
    : '<span class="vs">vs</span>';
  const grp=m.group?` ${m.group.replace('GROUP_','')}組`:'';
  return `<div class="mrow"><div class="mtime">${fmtT(m.utc,zone)}</div>`+
    `<div class="mteams">${teamSpan(m.home,hw)} ${mid} ${teamSpan(m.away,aw)}</div>`+
    `<div class="mbadge">${STAGE_JP[m.stage]||m.stage}${grp}</div></div>`;
}
function renderSchedule(){
  const wrap=document.getElementById('schedBody'); if(!wrap) return;
  const zone=zoneOf();
  let ms=SCHEDULE.matches;
  if(scStage==='group') ms=ms.filter(m=>m.stage==='GROUP_STAGE');
  else if(scStage==='ko') ms=ms.filter(m=>m.stage!=='GROUP_STAGE');
  if(scCountry) ms=ms.filter(m=>m.home===scCountry||m.away===scCountry);
  let h='', cur='';
  ms.forEach(m=>{
    const dk=dKey(m.utc,zone);
    if(dk!==cur){ if(cur)h+='</div>'; cur=dk; h+=`<div class="daygrp"><div class="dayhd">${fmtD(m.utc,zone)}</div>`; }
    h+=matchRow(m,zone);
  });
  if(cur)h+='</div>';
  wrap.innerHTML=h||'<div class="lbnote">該当する試合がありません。</div>';
}
function clearCountry(){scCountry=null;document.getElementById('scChip').classList.remove('on');renderSchedule();}

// ---- country fixtures popup ----
function openCountry(nm){
  const zone=zoneOf();
  const ms=SCHEDULE.matches.filter(m=>m.home===nm||m.away===nm);
  document.getElementById('cmTitle').innerHTML=`<span class="flag">${FLAGS[nm]||''}</span> ${nm}`;
  const c=(typeof MATRIX!=='undefined'&&MATRIX.countries||[]).find(x=>x.nm===nm);
  document.getElementById('cmSub').textContent=
    (c?`期待勝利数 ${c.ew} · `:'')+`${ms.length}試合（決勝Tは勝ち上がりで追加）`;
  let h='';
  ms.forEach(m=>{ h+=`<div class="dayhd" style="position:static;border:none;padding:8px 2px 4px;margin:0">${fmtD(m.utc,zone)}</div>`+matchRow(m,zone); });
  document.getElementById('cmBody').innerHTML=h||'<div class="lbnote">日程未定。</div>';
  // let people jump to the full schedule filtered to this team
  scCountry=nm; document.getElementById('scChipNm').innerHTML=`<span class="flag">${FLAGS[nm]||''}</span> ${nm} のみ`;
  document.getElementById('scChip').classList.add('on'); renderSchedule();
  document.getElementById('cmodal').classList.add('open'); document.body.classList.add('noscroll');
}
function closeCountry(){document.getElementById('cmodal').classList.remove('open');document.body.classList.remove('noscroll');}

// ---- wire controls + initial render ----
(function(){
  document.querySelectorAll('#tzbar .tzbtn[data-tz]').forEach(b=>b.onclick=()=>{
    tzCur=b.dataset.tz; document.querySelectorAll('#tzbar .tzbtn[data-tz]').forEach(x=>x.classList.toggle('on',x===b)); renderSchedule();
  });
  document.querySelectorAll('#tzbar .tzbtn[data-st]').forEach(b=>b.onclick=()=>{
    scStage=b.dataset.st; document.querySelectorAll('#tzbar .tzbtn[data-st]').forEach(x=>x.classList.toggle('on',x===b)); renderSchedule();
  });
  // make odds-table & cheat-sheet country labels clickable -> fixtures
  document.querySelectorAll('#oddsTbl td.l').forEach(td=>{
    const nm=td.textContent.replace('›','').trim(); if(FLAGS[nm]!==undefined){td.style.cursor='pointer';td.onclick=()=>openCountry(nm);}
  });
  document.querySelectorAll('#matTbl th.cty').forEach(th=>{
    const t=th.getAttribute('title')||''; const nm=t.split(' ·')[0].trim();
    if(FLAGS[nm]!==undefined){th.style.cursor='pointer';th.onclick=()=>openCountry(nm);}
  });
  renderStandings(); renderSchedule();
})();
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeCountry();});
"""
html = html.replace("\n</script>", JS_ADD + "</script>", 1)

FILE.write_text(html, encoding="utf-8")
print(f"patched live sections -> {FILE.name} ({len(html):,} chars)")
