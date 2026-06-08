"""v5 tweaks:
 1. 次の3試合: spell out the timezone clearly — full toggle labels (日本時間 /
    米国 ET / スイス時間) and a bright chip beside each kickoff time.
 2. Participant popup: stop pinning the top — remove the inner-scroll cap so the
    whole popup scrolls together.
 3. Participant popup: visually separate countries the player DID assign points
    to (gold left bar) from the ones they did NOT (dimmed, below a divider).
Operates on both the report HTML and index.html.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
files = [HERE / "Totocalcio 2026.html", HERE.parent / "index.html"]

EDITS = [
    # 1. toggle labels -> full
    ('<div class="n3tz"><button class="n3tzb on" data-tz="jp">日本</button><button class="n3tzb" data-tz="us">米ET</button><button class="n3tzb" data-tz="ch">スイス</button></div>',
     '<div class="n3tz"><button class="n3tzb on" data-tz="jp">日本時間</button><button class="n3tzb" data-tz="us">米国 ET</button><button class="n3tzb" data-tz="ch">スイス時間</button></div>'),
    # 1. per-card time + bright tz chip
    ('<div class="n3when">${fmtD(m.utc,Z)} ${fmtT(m.utc,Z)} <span style="color:var(--faint)">${tzFull()}</span></div>',
     '<div class="n3when">${fmtD(m.utc,Z)} <b style="color:var(--txt)">${fmtT(m.utc,Z)}</b> <span class="n3tzlab">${tzFull()}</span></div>'),
    # 2. remove inner-scroll cap (desktop)
    ('.mdlist{display:flex;flex-direction:column;gap:4px;max-height:46vh;overflow-y:auto;overscroll-behavior:contain;padding-right:3px}',
     '.mdlist{display:flex;flex-direction:column;gap:4px}'),
    # 2. remove inner-scroll cap (mobile)
    ('.modalhead .mt{font-size:22px}.mdlist{max-height:42vh}}',
     '.modalhead .mt{font-size:22px}}'),
    # 3. legend mentions the distinction
    ('<div class="mdlegend">「配点」＝持ち点 ・ <b>「1勝」＝その国が1勝した時の増減</b>（行クリックで日程）</div>',
     '<div class="mdlegend"><b style="color:var(--gold2)">金の縦線＝配点した国</b> ・「1勝」＝その国が1勝した時の増減（行クリックで日程）</div>'),
    # 3. render: divider + pick/nopt classes
    ("""  const rows=d.rows.slice().sort((a,b)=>(b[2]-a[2])||(b[1]-a[1]));   // 配点 desc, then 期待勝利数
  let mh='';
  rows.forEach(r=>{
    const nm=r[0],ew=r[1],pts=r[2],oth=r[3],pw=r[4],tot=r[5];
    const cls=pw>0?'pos':(pw<0?'neg':'zero');
    mh+=`<div class="mditem" onclick="openCountry('${esc(nm)}')">`+""",
     """  const rows=d.rows.slice().sort((a,b)=>(b[2]-a[2])||(b[1]-a[1]));   // 配点 desc, then 期待勝利数
  let mh='', divShown=false;
  rows.forEach(r=>{
    const nm=r[0],ew=r[1],pts=r[2],oth=r[3],pw=r[4],tot=r[5];
    if(pts===0&&!divShown){ mh+='<div class="mddiv">― 配点なし（勝つと失点するリスク国）―</div>'; divShown=true; }
    const cls=pw>0?'pos':(pw<0?'neg':'zero');
    mh+=`<div class="mditem ${pts>0?'pick':'nopt'}" onclick="openCountry('${esc(nm)}')">`+"""),
    # CSS additions
    ('\n</style>',
     "\n.n3tzlab{color:#fff;background:rgba(246,196,81,.18);border:1px solid rgba(246,196,81,.45);border-radius:5px;padding:1px 7px;font-size:10.5px;margin-left:4px;font-weight:700}"
     "\n.mditem.pick{box-shadow:inset 3px 0 0 var(--gold)}"
     "\n.mditem.pick .mdpts b{color:var(--gold2)}"
     "\n.mditem.nopt{opacity:.55}"
     "\n.mddiv{font-family:var(--mono);font-size:10px;color:var(--faint);text-align:center;margin:11px 0 6px;letter-spacing:.04em;border-top:1px dashed var(--line);padding-top:9px}\n</style>"),
]

for f in files:
    h = f.read_text(encoding="utf-8")
    for old, new in EDITS:
        assert old in h, f"NOT FOUND in {f.name}: {old[:55]!r}"
        h = h.replace(old, new, 1)
    f.write_text(h, encoding="utf-8")
    print(f"patched {f.name} ({len(h):,} chars)")
