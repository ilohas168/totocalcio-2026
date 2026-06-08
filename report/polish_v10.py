"""v10: make グループ最終順位予想 and 勝ち上がり・優勝確率 more compact.
 - Group cards: single-line rows (flag + name + tiny ①1位/②2位 + 進出%), smaller
   cards (228px) so more fit per row, tighter padding.
 - Odds table: shorter bars (24->17px), smaller font, tighter cell padding.
Operates on both the report HTML and index.html.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
files = [HERE / "Totocalcio 2026.html", HERE.parent / "index.html"]

NEW_GROUPS_CSS = (
".ggrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(228px,1fr));gap:10px}\n"
".gcard{background:var(--surface);border:1px solid var(--line);border-radius:12px;overflow:hidden}\n"
".gcard .gh{display:flex;align-items:center;justify-content:space-between;padding:7px 13px;background:linear-gradient(90deg,var(--surface2),transparent);border-bottom:1px solid var(--line)}\n"
".gcard .gh .gl{font-family:var(--disp);font-size:15px;letter-spacing:.04em}\n"
".gcard .gh .gl em{color:var(--gold);font-style:normal}\n"
".gcard .gh .hint{font-family:var(--cond);text-transform:uppercase;letter-spacing:.1em;font-size:9px;color:var(--faint)}\n"
".grow{display:grid;grid-template-columns:9px 1fr auto;align-items:center;gap:7px;padding:5px 13px;border-bottom:1px solid var(--line);position:relative}\n"
".grow:last-child{border-bottom:none}\n"
".grow .q{width:7px;height:7px;border-radius:50%;background:rgba(255,255,255,.12)}\n"
".grow.qual .q{background:var(--mex);box-shadow:0 0 8px rgba(47,208,122,.6)}\n"
".grow .gnm{display:flex;align-items:baseline;gap:5px;font-weight:700;font-size:12.5px;white-space:nowrap;overflow:hidden;min-width:0}\n"
".grow .gnm .tnm{overflow:hidden;text-overflow:ellipsis}\n"
".grow.qual .gnm{color:var(--txt)} .grow:not(.qual) .gnm{color:var(--muted)}\n"
".grow .gnm .sm{font-family:var(--mono);font-size:9px;color:var(--faint);font-weight:500;flex:none}\n"
".grow .adv{font-family:var(--mono);font-weight:700;font-size:12.5px;text-align:right}\n"
".grow .gbar{position:absolute;left:0;bottom:0;height:2px;width:0;background:var(--mex);opacity:.55;transition:width 1s cubic-bezier(.2,.7,.2,1)}\n"
".in .grow .gbar{width:var(--w)}"
)

NEW_ODDS_CSS = (
".oddsbar{position:relative;height:17px;border-radius:5px;background:rgba(255,255,255,.05);overflow:hidden;display:flex;align-items:center;min-width:54px}\n"
".oddsbar .of{position:absolute;left:0;top:0;bottom:0;width:0;border-radius:5px;background:linear-gradient(90deg,rgba(47,208,122,.55),rgba(47,208,122,.2));transition:width .9s cubic-bezier(.2,.7,.2,1)}\n"
".oddsbar.champ .of{background:linear-gradient(90deg,var(--gold),rgba(246,196,81,.35))}\n"
".in .oddsbar .of{width:var(--w)}\n"
".oddsbar .ov{position:relative;font-family:var(--mono);font-weight:700;font-size:10.5px;padding-left:6px;text-shadow:0 1px 3px rgba(0,0,0,.6)}\n"
"#oddsTbl td{padding:3px 5px}#oddsTbl th{padding:5px 5px;font-size:11px}"
)

OLD_ROW = ('    rows+=`<div class="grow${q?\' qual\':\'\'}"><span class="q"></span>'
           '<span class="gn"><span class="nmrow"><span class="flag">${FLAGS[nm]||\'\'}</span>${nm}</span>'
           '<span class="sm">1位 ${p1}% · 2位 ${p2}%</span></span>'
           '<span class="adv">${adv}%</span><span class="gbar" style="--w:${adv}%"></span></div>`;')
NEW_ROW = ('    rows+=`<div class="grow${q?\' qual\':\'\'}"><span class="q"></span>'
           '<span class="gnm"><span class="flag">${FLAGS[nm]||\'\'}</span><span class="tnm">${nm}</span>'
           '<span class="sm">①${p1} ②${p2}</span></span>'
           '<span class="adv">${adv}%</span><span class="gbar" style="--w:${adv}%"></span></div>`;')

OLD_NOTE = '<div class="note"><span style="color:var(--mex)">●</span> 進出予想。バー＝進出確率。小数字＝1位/2位率。</div>'
NEW_NOTE = '<div class="note"><span style="color:var(--mex)">●</span> 進出予想。％＝進出確率。<b>①</b>1位率 <b>②</b>2位率。</div>'

groups_css_pat = re.compile(r"\.ggrid\{display:grid.*?\.in \.grow \.gbar\{width:var\(--w\)\}", re.S)
odds_css_pat = re.compile(r"\.oddsbar\{position:relative;height:24px.*?\.oddsbar \.ov\{[^}]*rgba\(0,0,0,\.6\)\}", re.S)

for f in files:
    h = f.read_text(encoding="utf-8")
    h, n1 = groups_css_pat.subn(lambda m: NEW_GROUPS_CSS, h, count=1)
    h, n2 = odds_css_pat.subn(lambda m: NEW_ODDS_CSS, h, count=1)
    assert n1 == 1 and n2 == 1, f"CSS not matched in {f.name}: groups={n1} odds={n2}"
    assert OLD_ROW in h, f"group row render not found in {f.name}"
    h = h.replace(OLD_ROW, NEW_ROW, 1)
    assert OLD_NOTE in h, f"group note not found in {f.name}"
    h = h.replace(OLD_NOTE, NEW_NOTE, 1)
    f.write_text(h, encoding="utf-8")
    print(f"patched {f.name} ({len(h):,} chars)")
