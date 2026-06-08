"""Second polish pass on the curated dashboard:
 1. Standings (順位表): compact rows, only top-3 decorated (podium + medals).
 2. Participant popup: countries in 配点 order, mobile-first list (no h-scroll),
    the per-win swing is the big coloured number; country rows open its schedule.
 3. Cheat-sheet (早見表): clamp the name column width on phones.
 4. Participant eval (参加者評価): sticky name column when scrolling.
 5. NEW section 02 「グループ実況（結果）」: real group tables from live results.
 6. Schedule timezone labels spelled out (日本時間 / 米国時間 ET / スイス時間).
 7. Fix: opening a country popup no longer permanently filters the full schedule.
Idempotent-ish: guarded by a marker; operates on the report HTML, copies to index.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILE = HERE / "Totocalcio 2026.html"
INDEX = HERE.parent / "index.html"
html = FILE.read_text(encoding="utf-8")

if 'id="results"' in html:
    print("already polished — nothing to do")
    raise SystemExit(0)

def rep(old, new, n=1):
    global html
    assert html.count(old) >= n, f"NOT FOUND: {old[:70]!r}"
    html = html.replace(old, new, n)

# ============================================================ 1+7. NAV ======
rep('<a href="#standings">順位表</a><a href="#schedule">日程</a><a href="#pick">配点</a>',
    '<a href="#standings">順位表</a><a href="#results">結果</a><a href="#schedule">日程</a><a href="#pick">配点</a>')

# ===================================================== 5. NEW SECTION 02 =====
NEW_SEC = """  <!-- 02 GROUP RESULTS (live) -->
  <section id="results">
    <div class="shead"><div class="num">02</div><div class="tt"><div class="ek">Group Tables · Live</div><h2>グループ実況（結果）</h2></div>
      <div class="note">実際の試合結果から自動集計するグループ順位。<span style="color:var(--mex)">●</span>＝上位2（突破）。国名クリックでその国の日程。</div></div>
    <div class="grtables" id="grBody"></div>
  </section>

  <!-- 03 SCHEDULE -->
"""
rep("  <!-- 02 SCHEDULE -->\n", NEW_SEC)

# renumber section badges (schedule 02->03, then the seven content sections +1)
for old, new, ek in [("02", "03", "Match Schedule"), ("03", "04", "All Schedine"),
                     ("04", "05", "Point Swings"), ("05", "06", "The 19-Player Pool"),
                     ("06", "07", "Final Standings"), ("07", "08", "Road to the Final"),
                     ("08", "09", "Knockout"), ("09", "10", "The Math")]:
    rep(f'<div class="num">{old}</div><div class="tt"><div class="ek">{ek}',
        f'<div class="num">{new}</div><div class="tt"><div class="ek">{ek}')

# ===================================================== 6. TZ LABELS + CHIP ===
rep('      <button class="tzbtn on" data-tz="jp">🇯🇵 日本</button>\n'
    '      <button class="tzbtn" data-tz="us">🇺🇸 米 ET</button>\n'
    '      <button class="tzbtn" data-tz="ch">🇨🇭 スイス</button>\n'
    '      <span class="tzsep"></span>\n'
    '      <button class="tzbtn on" data-st="all">全試合</button>\n'
    '      <button class="tzbtn" data-st="group">グループ</button>\n'
    '      <button class="tzbtn" data-st="ko">決勝T</button>\n'
    '      <span class="scchip" id="scChip"><span id="scChipNm"></span><b onclick="clearCountry()">✕</b></span>\n',
    '      <button class="tzbtn on" data-tz="jp">🇯🇵 日本時間</button>\n'
    '      <button class="tzbtn" data-tz="us">🇺🇸 米国時間 ET</button>\n'
    '      <button class="tzbtn" data-tz="ch">🇨🇭 スイス時間</button>\n'
    '      <span class="tzsep"></span>\n'
    '      <button class="tzbtn on" data-st="all">全試合</button>\n'
    '      <button class="tzbtn" data-st="group">グループ</button>\n'
    '      <button class="tzbtn" data-st="ko">決勝T</button>\n')

# ===================================================== 2. MODAL MARKUP =======
rep('<div class="tbl-wrap"><table id="modalTbl"><thead><tr><th style="text-align:left">国 / Nation</th><th>期待勝利数</th><th>配点</th><th>平均点</th><th>1勝</th><th>通算</th></tr></thead><tbody id="modalBody"></tbody></table></div>',
    '<div class="mdlegend">「配点」＝持ち点 ・ <b>「1勝」＝その国が1勝した時の増減</b>（行クリックで日程）</div><div class="mdlist" id="modalBody"></div>')

# 2. openModal render -> compact 配点-ordered list
rep("""  const body=document.getElementById('modalBody'); body.innerHTML='';
  d.rows.forEach(r=>{
    const nm=r[0],ew=r[1],pts=r[2],oth=r[3],pw=r[4],tot=r[5];
    const tr=document.createElement('tr');
    const pc=pts?(''+pts):'<span class="z">0</span>';
    tr.innerHTML=`<td class="l"><span class="flag">${FLAGS[nm]||''}</span>${nm}</td>`+
      `<td>${ew.toFixed(2)}</td><td>${pc}</td><td>${oth.toFixed(1)}</td>`+
      flowCell(pw)+flowCell(tot);
    body.appendChild(tr);
  });""",
    """  const rows=d.rows.slice().sort((a,b)=>(b[2]-a[2])||(b[1]-a[1]));   // 配点 desc, then 期待勝利数
  let mh='';
  rows.forEach(r=>{
    const nm=r[0],ew=r[1],pts=r[2],oth=r[3],pw=r[4],tot=r[5];
    const cls=pw>0?'pos':(pw<0?'neg':'zero');
    mh+=`<div class="mditem" onclick="openCountry('${esc(nm)}')">`+
      `<div class="mdtop"><div class="mdc"><span class="flag">${FLAGS[nm]||''}</span><span>${nm}</span></div>`+
      `<div class="mdpts">配点 <b>${pts||0}</b></div>`+
      `<div class="mdpw ${cls}">${pw>0?'+':''}${pw}</div></div>`+
      `<div class="mdsub">1勝の増減 · 期待勝利数 ${ew.toFixed(2)} · 通算 ${tot>=0?'+':''}${tot}</div></div>`;
  });
  document.getElementById('modalBody').innerHTML=mh;""")

# 2/4/7. close handlers keep background locked while the other modal is still open
rep("""function closeModal(){
  document.getElementById('modal').classList.remove('open');
  document.body.classList.remove('noscroll');
}""",
    """function closeModal(){
  document.getElementById('modal').classList.remove('open');
  if(!document.getElementById('cmodal').classList.contains('open'))document.body.classList.remove('noscroll');
}""")

# ===================================================== 1. STANDINGS RENDER ===
rep("""function renderStandings(){
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
}""",
    """function renderStandings(){
  const wrap=document.getElementById('lbBody'); if(!wrap) return;
  const live=SCHEDULE.finished>0;
  document.getElementById('lbNote').innerHTML=live
    ? `⚽️ <b>${SCHEDULE.finished}/104</b> 試合終了 — 実際の獲得点（ゼロサム）。行クリックで個人詳細。`
    : `⚽️ <b>大会開始前</b>。<b>6/11開幕</b>後、結果を自動反映して順位が動きます。「予想」＝全シミュレーション平均（＝今の本命）。`;
  const medal=['🥇','🥈','🥉'];
  let h='';
  STANDINGS.forEach((r,i)=>{
    const rk=i+1, top=rk<=3, cls=['lbrow']; if(top)cls.push('podium','top'+rk); if(r.you)cls.push('you');
    const sc=r.score, sg=(sc>=0?'+':'')+sc;
    const nm=r.joker?`${r.name} 🃏`:r.name;
    h+=`<div class="${cls.join(' ')}" onclick="openModal('${esc(r.name)}')">`+
       `<div class="lbrk">${top?`<span class="lbmedal">${medal[i]}</span>`:rk}</div>`+
       `<div class="lbmid"><span class="lbnm">${nm}</span><span class="lbsub">予想 ${r.mean>=0?'+':''}${r.mean}</span></div>`+
       `<div class="lbpts ${sc>0?'pos':(sc<0?'neg':'')}">${live?sg:'—'}</div></div>`;
  });
  wrap.innerHTML=h;
}""")

# ===================================================== 5. renderGroups (+ drop clearCountry) ==
rep("function clearCountry(){scCountry=null;document.getElementById('scChip').classList.remove('on');renderSchedule();}",
    """// ---- live group tables (built from real results in SCHEDULE) ----
function renderGroups(){
  const wrap=document.getElementById('grBody'); if(!wrap) return;
  const gm={};
  SCHEDULE.matches.forEach(m=>{
    if(m.stage!=='GROUP_STAGE'||!m.group) return;
    const L=m.group.replace('GROUP_',''); gm[L]=gm[L]||{};
    [m.home,m.away].forEach(t=>{ if(t&&!gm[L][t]) gm[L][t]={p:0,w:0,d:0,l:0,gf:0,ga:0}; });
    if(m.status==='FINISHED'&&m.score){
      const hs=m.score[0],as=m.score[1],H=gm[L][m.home],A=gm[L][m.away];
      H.p++;A.p++;H.gf+=hs;H.ga+=as;A.gf+=as;A.ga+=hs;
      if(hs>as){H.w++;A.l++;} else if(hs<as){A.w++;H.l++;} else {H.d++;A.d++;}
    }
  });
  let h='';
  Object.keys(gm).sort().forEach(L=>{
    const ts=Object.entries(gm[L]).map(([nm,s])=>({nm,...s,gd:s.gf-s.ga,pts:s.w*3+s.d}));
    const played=ts.some(t=>t.p>0);
    ts.sort((a,b)=> b.pts-a.pts || b.gd-a.gd || b.gf-a.gf || a.nm.localeCompare(b.nm));
    let rows='';
    ts.forEach((t,i)=>{
      const adv=played?(i<2?'adv':(i===2?'adv3':'')):'';
      rows+=`<tr class="${adv}"><td class="grpos">${i+1}</td>`+
        `<td class="grnm" onclick="openCountry('${esc(t.nm)}')"><span class="flag">${FLAGS[t.nm]||''}</span>${t.nm}</td>`+
        `<td>${t.p}</td><td>${t.gd>0?'+':''}${t.gd}</td><td class="grpt">${t.pts}</td></tr>`;
    });
    h+=`<div class="grcard"><div class="grhd">${L}組</div>`+
       `<table class="grtbl"><thead><tr><th></th><th class="grnm"></th><th>試</th><th>差</th><th>点</th></tr></thead>`+
       `<tbody>${rows}</tbody></table></div>`;
  });
  wrap.innerHTML=h;
}""")

# 7. openCountry: drop the schedule side-effect (was the persistent-filter bug)
rep("""  // let people jump to the full schedule filtered to this team
  scCountry=nm; document.getElementById('scChipNm').innerHTML=`<span class="flag">${FLAGS[nm]||''}</span> ${nm} のみ`;
  document.getElementById('scChip').classList.add('on'); renderSchedule();
  document.getElementById('cmodal').classList.add('open'); document.body.classList.add('noscroll');""",
    """  document.getElementById('cmodal').classList.add('open'); document.body.classList.add('noscroll');""")
rep("function closeCountry(){document.getElementById('cmodal').classList.remove('open');document.body.classList.remove('noscroll');}",
    "function closeCountry(){document.getElementById('cmodal').classList.remove('open');if(!document.getElementById('modal').classList.contains('open'))document.body.classList.remove('noscroll');}")

# drop the now-unused scCountry filter + var
rep("let tzCur='jp', scStage='all', scCountry=null;", "let tzCur='jp', scStage='all';")
rep("  if(scCountry) ms=ms.filter(m=>m.home===scCountry||m.away===scCountry);\n", "")

# render the new groups section on load
rep("  renderStandings(); renderSchedule();\n})();",
    "  renderStandings(); renderGroups(); renderSchedule();\n})();")

# ===================================================== CSS: standings block ==
new_lb = """/* ===== LIVE: STANDINGS (順位表) — compact, top-3 podium ===== */
.lbnote{font-size:12px;color:var(--faint);margin:-6px 0 14px;line-height:1.6}
.lb{display:flex;flex-direction:column;gap:5px}
.lbrow{display:grid;grid-template-columns:30px 1fr auto;align-items:center;gap:11px;
  background:var(--surface);border:1px solid var(--line);border-radius:9px;padding:7px 13px;cursor:pointer;transition:border-color .15s}
.lbrow:hover{border-color:var(--line2)}
.lbrk{font-family:var(--mono);font-size:13px;font-weight:700;color:var(--faint);text-align:center;line-height:1}
.lbmid{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap;min-width:0}
.lbnm{font-weight:700;font-size:13.5px}
.lbsub{font-size:10.5px;color:var(--faint);font-family:var(--mono)}
.lbpts{font-family:var(--mono);font-size:14px;font-weight:700;text-align:right;white-space:nowrap}
.lbpts.pos{color:var(--pos)}.lbpts.neg{color:var(--neg)}
.lbrow.podium{padding:11px 15px;border-radius:13px;grid-template-columns:40px 1fr auto}
.lbrow.podium .lbnm{font-size:16.5px}
.lbrow.podium .lbpts{font-size:17px}
.lbmedal{font-size:22px;line-height:1}
.lbrow.top1{border-color:rgba(246,196,81,.5);background:linear-gradient(110deg,rgba(246,196,81,.14),var(--surface) 62%)}
.lbrow.top2{border-color:rgba(207,216,238,.38);background:linear-gradient(110deg,rgba(207,216,238,.1),var(--surface) 62%)}
.lbrow.top3{border-color:rgba(217,154,91,.42);background:linear-gradient(110deg,rgba(217,154,91,.12),var(--surface) 62%)}
.lbrow.you{box-shadow:inset 0 0 0 1px rgba(246,196,81,.5)}
"""
html = re.sub(r"/\* ===== LIVE: STANDINGS \(順位表\) ===== \*/.*?(?=\n/\* ===== LIVE: SCHEDULE)",
              new_lb, html, count=1, flags=re.S)
assert ".lbrow.podium" in html, "standings CSS block not replaced"

# ===================================================== CSS: extras ==========
CSS_EXTRA = """
/* ===== popup detail list (mobile-first, no h-scroll) ===== */
.mdlegend{font-size:11px;color:var(--faint);margin:-2px 0 11px;line-height:1.5}
.mdlist{display:flex;flex-direction:column;gap:6px}
.mditem{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:8px 13px;cursor:pointer;transition:border-color .15s}
.mditem:hover{border-color:var(--line2)}
.mdtop{display:grid;grid-template-columns:1fr auto auto;align-items:center;gap:12px}
.mdc{display:flex;align-items:center;gap:7px;font-size:14px;font-weight:700;min-width:0}
.mdc span:last-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mdpts{font-family:var(--mono);font-size:12px;color:var(--muted);white-space:nowrap}
.mdpts b{font-size:15px;color:var(--txt)}
.mdpw{font-family:var(--mono);font-size:18px;font-weight:700;min-width:50px;text-align:right}
.mdpw.pos{color:var(--pos)}.mdpw.neg{color:var(--neg)}.mdpw.zero{color:var(--faint)}
.mdsub{font-family:var(--mono);font-size:10px;color:var(--faint);margin-top:4px}

/* ===== live group tables (results) ===== */
.grtables{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
@media(max-width:900px){.grtables{grid-template-columns:repeat(2,1fr)}}
@media(max-width:540px){.grtables{grid-template-columns:1fr}}
.grcard{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:10px 13px}
.grhd{font-family:var(--cond);text-transform:uppercase;letter-spacing:.12em;font-weight:700;font-size:13px;color:var(--gold2);margin-bottom:5px}
.grtbl{width:100%;border-collapse:collapse;font-size:12.5px}
.grtbl th{font-size:10px;color:var(--faint);font-weight:600;padding:2px 4px;text-align:center}
.grtbl td{padding:4px 4px;text-align:center;font-family:var(--mono);font-variant-numeric:tabular-nums}
.grtbl tbody tr{border-top:1px solid var(--line)}
.grtbl td.grnm,.grtbl th.grnm{text-align:left;font-family:var(--sans);font-weight:600;cursor:pointer;white-space:nowrap;max-width:120px;overflow:hidden;text-overflow:ellipsis}
.grtbl td.grnm{display:flex;align-items:center;gap:6px}
.grtbl td.grnm:hover{color:var(--gold2)}
.grtbl td.grpos{color:var(--faint);width:16px}
.grtbl td.grpt{font-weight:700;color:var(--txt)}
.grtbl tr.adv td.grpos{color:var(--mex)}.grtbl tr.adv td.grnm{color:#eafff2}
.grtbl tr.adv3 td.grpos{color:var(--gold2)}

/* ===== mobile: clamp sticky name columns so the data columns get room ===== */
#rivalTbl td.l,#rivalTbl thead th:first-child{position:sticky;left:0;background:var(--surface);z-index:1}
#rivalTbl thead th:first-child{z-index:2}
@media(max-width:560px){
  #matTbl td.l{max-width:80px;overflow:hidden;text-overflow:ellipsis;font-size:11px}
  #rivalTbl td.l{max-width:96px;overflow:hidden;text-overflow:ellipsis}
}
"""
rep("\n</style>", CSS_EXTRA + "</style>")

FILE.write_text(html, encoding="utf-8")
INDEX.write_text(html, encoding="utf-8")
print(f"polished v2 -> {FILE.name} (+ index.html) ({len(html):,} chars)")
