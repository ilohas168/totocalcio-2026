"""v7: timezone control inside the country popup, fully synced app-wide.

The app already shares one global `tzCur` (every [data-tz] button calls setTZ,
which flips ALL toggles and re-renders). This adds:
 - a tz toggle (日本時間 / 米国 ET / スイス時間) inside the country popup,
 - openCountry() split into a re-renderable renderCountry() keyed off cmCountry,
 - setTZ() now also re-renders the open country popup,
so setting the timezone anywhere (schedule / next-3 / country popup) updates
everything at once — no need to switch it again.
Operates on both the report HTML and index.html.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
files = [HERE / "Totocalcio 2026.html", HERE.parent / "index.html"]

EDITS = [
    # 1. toggle inside the country popup
    ('  <div class="cmsub" id="cmSub"></div>\n  <div id="cmBody"></div>',
     '  <div class="cmsub" id="cmSub"></div>\n'
     '  <div class="cmtz"><button class="cmtzb on" data-tz="jp">日本時間</button>'
     '<button class="cmtzb" data-tz="us">米国 ET</button>'
     '<button class="cmtzb" data-tz="ch">スイス時間</button></div>\n'
     '  <div id="cmBody"></div>'),
    # 2. openCountry -> cmCountry + renderCountry()
    ('function openCountry(nm){\n  const zone=zoneOf();',
     'let cmCountry=null;\nfunction renderCountry(){\n  const nm=cmCountry; if(!nm) return;\n  const zone=zoneOf();'),
    ("  document.getElementById('cmBody').innerHTML=h||'<div class=\"lbnote\">日程未定。</div>';\n"
     "  document.getElementById('cmodal').classList.add('open'); document.body.classList.add('noscroll');",
     "  document.getElementById('cmBody').innerHTML=h||'<div class=\"lbnote\">日程未定。</div>';\n"
     "}\nfunction openCountry(nm){\n  cmCountry=nm; renderCountry();\n"
     "  document.getElementById('cmodal').classList.add('open'); document.body.classList.add('noscroll');"),
    # 3. setTZ re-renders the open country popup
    ('renderSchedule();renderKO();renderNext3();}',
     "renderSchedule();renderKO();renderNext3();if(document.getElementById('cmodal').classList.contains('open'))renderCountry();}"),
    # 4. clear cmCountry on close
    ("function closeCountry(){document.getElementById('cmodal').classList.remove('open');",
     "function closeCountry(){cmCountry=null;document.getElementById('cmodal').classList.remove('open');"),
    # 5. toggle CSS
    ('\n</style>',
     "\n.cmtz{display:flex;gap:6px;margin:-2px 0 12px;flex-wrap:wrap}"
     "\n.cmtzb{font-family:var(--cond);text-transform:uppercase;letter-spacing:.03em;font-weight:700;font-size:11px;padding:5px 12px;border-radius:999px;border:1px solid var(--line2);background:var(--surface);color:var(--muted);cursor:pointer}"
     "\n.cmtzb.on{background:var(--gold);color:#1a1304;border-color:var(--gold)}\n</style>"),
]

for f in files:
    h = f.read_text(encoding="utf-8")
    for old, new in EDITS:
        assert old in h, f"NOT FOUND in {f.name}: {old[:50]!r}"
        h = h.replace(old, new, 1)
    f.write_text(h, encoding="utf-8")
    print(f"patched {f.name} ({len(h):,} chars)")
