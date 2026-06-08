"""v6 mobile fixes:
 1. Kill the horizontal page overflow that made the page scroll sideways and the
    CTA buttons look shifted. Root cause: the sticky nav is a direct <body> child
    (outside .wrap) yet still carried margin:0 -22px from when it lived inside the
    padded wrap — so it bled 22px past each edge. Fix: nav margin:0 + padding 22px
    (spans the viewport, content aligned with the sections, no overflow).
 2. 得失点早見表: the fixed first column ate half the phone width because the
    header label "参加者 ＼ 国（1勝あたり）" forced it wide. Shorten it (参加者＼国),
    make the header cell sticky too (aligns on scroll), and hard-clamp the first
    column to 76px on phones so the data columns get the room.
Operates on both the report HTML and index.html.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
files = [HERE / "Totocalcio 2026.html", HERE.parent / "index.html"]

OLD_MOBILE = """@media(max-width:560px){
  #matTbl td.l{max-width:80px;overflow:hidden;text-overflow:ellipsis;font-size:11px}
  #rivalTbl td.l{max-width:96px;overflow:hidden;text-overflow:ellipsis}
}"""
NEW_MOBILE = """#matTbl thead th:first-child{position:sticky;left:0;background:var(--surface);z-index:3}
@media(max-width:560px){
  #matTbl td.l,#matTbl thead th:first-child{width:76px;min-width:76px;max-width:76px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px}
  #matTbl td{padding:4px 4px;font-size:11px}
  #matTbl thead th.cty{min-width:26px;font-size:13px}
  #rivalTbl td.l{max-width:96px;overflow:hidden;text-overflow:ellipsis}
}"""

EDITS = [
    ("padding:9px 14px;margin:0 -22px 0;", "padding:9px 22px;margin:0;"),  # 1. nav no longer bleeds
    ("参加者 ＼ 国（1勝あたり）", "参加者＼国"),                              # 2. shorter matrix header
    (OLD_MOBILE, NEW_MOBILE),                                             # 2. sticky + clamp first column
]

for f in files:
    h = f.read_text(encoding="utf-8")
    for old, new in EDITS:
        if old not in h:
            print(f"  (skip, already applied in {f.name}): {old[:40]!r}")
            continue
        h = h.replace(old, new, 1)
    f.write_text(h, encoding="utf-8")
    print(f"ensured v6 state in {f.name} ({len(h):,} chars)")
