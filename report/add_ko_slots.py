"""Add WC2026 R32 group-position slot labels to the トーナメント結果 bracket.
Each R32 slot (verified by kickoff UTC against the official bracket) shows e.g.
'A②' (group A runner-up), 'E①' (group E winner), '3位' (a best-third), until the
real team is decided — then it switches to flags. Full label in the tooltip.
Applied to index.html + the editable source.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
files = [HERE.parent / "index.html", HERE / "Totocalcio_no_ai_new 2026.html"]

OLD = """  const f=(nm,win)=> nm
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
    });"""

NEW = """  const SLOT={"2026-06-28T19:00:00Z":["A②","B②"],"2026-06-29T20:30:00Z":["E①","3位","A/B/C/D/F"],"2026-06-30T01:00:00Z":["F①","C②"],"2026-06-29T17:00:00Z":["C①","F②"],"2026-06-30T21:00:00Z":["I①","3位","C/D/F/G/H"],"2026-06-30T17:00:00Z":["E②","I②"],"2026-07-01T01:00:00Z":["A①","3位","C/E/F/H/I"],"2026-07-01T16:00:00Z":["L①","3位","E/H/I/J/K"],"2026-07-02T00:00:00Z":["D①","3位","B/E/F/I/J"],"2026-07-01T20:00:00Z":["G①","3位","A/E/H/I/J"],"2026-07-02T23:00:00Z":["K②","L②"],"2026-07-02T19:00:00Z":["H①","J②"],"2026-07-03T03:00:00Z":["B①","3位","E/F/G/I/J"],"2026-07-03T22:00:00Z":["J①","H②"],"2026-07-04T01:30:00Z":["K①","3位","D/E/I/J/L"],"2026-07-03T18:00:00Z":["D②","G②"]};
  const slotJP=(c)=>c==='3位'?'3位':c[0]+'組'+(c[1]==='①'?'1位':'2位');
  const f=(nm,win,slot)=> nm
    ? `<span class="kf${win?' w':''}" title="${nm}" onclick="event.stopPropagation();openCountry('${esc(nm)}')">${FLAGS[nm]||'🏳'}</span>`
    : (slot?`<span class="kslot">${slot}</span>`:'<span class="kf tbd">·</span>');
  let h='';
  cols.forEach(([st,lab])=>{
    const ms=SCHEDULE.matches.filter(m=>m.stage===st); if(!ms.length) return;
    let cells='';
    ms.forEach(m=>{
      const fin=m.status==='FINISHED', hw=fin&&m.winner==='HOME_TEAM', aw=fin&&m.winner==='AWAY_TEAM';
      const s=SLOT[m.utc]||[];
      const sc=fin?`<span class="ks">${m.score[0]}-${m.score[1]}${m.pens?'p':''}</span>`:'<span class="ks tbd">–</span>';
      const hn=m.home||(s[0]?slotJP(s[0]):'?'), an=m.away||(s[1]?(s[2]?s[2]+'組の3位':slotJP(s[1])):'?');
      const t=`${hn} vs ${an}${fin?` ${m.score[0]}-${m.score[1]}`:''}`;
      cells+=`<div class="kocell" title="${t}">${f(m.home,hw,s[0])}${sc}${f(m.away,aw,s[1])}</div>`;
    });"""

NOTE_OLD = '<div class="note">決勝トーナメントの実際の対戦・結果（R32は6/28〜）。勝者を金でハイライト・横スクロール可。国旗クリックで日程。</div>'
NOTE_NEW = '<div class="note">決勝トーナメントの組合せ・結果。R32の枠＝<b>A①</b>:A組1位 / <b>A②</b>:A組2位 / <b>3位</b>:各組3位（決定するとチームに変わる）。勝者を金でハイライト・横スクロール可。</div>'

CSS = '.kslot{font-family:var(--mono);font-size:9.5px;font-weight:700;color:var(--muted);white-space:nowrap}\n</style>'

for f in files:
    h = f.read_text(encoding="utf-8")
    assert OLD in h, f"renderKO block not found in {f.name}"
    h = h.replace(OLD, NEW, 1)
    assert NOTE_OLD in h, f"note not found in {f.name}"
    h = h.replace(NOTE_OLD, NOTE_NEW, 1)
    assert "\n</style>" in h
    h = h.replace("\n</style>", "\n" + CSS, 1)
    f.write_text(h, encoding="utf-8")
    print(f"patched {f.name}")
