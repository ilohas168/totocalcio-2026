"""v8: replace the wide predicted-bracket with the workflow-winning compact design
(flag + 3-letter code, gold-filled winner rows + glowing dot, 64px columns,
space-around pyramid). All bracket CSS is scoped under .bkt so it no longer leaks
the bare .mt/.tm rules onto the modal title / schedule team spans. The champion
card stays refresh-managed (.lab/.ico/.cn/.pct) — only restyled compact.
Also makes the odds country column sticky was done separately.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
files = [HERE / "Totocalcio 2026.html", HERE.parent / "index.html"]

NEW_CSS = (
".bkt{display:flex;gap:7px;overflow-x:auto;padding:4px 2px 14px;align-items:stretch;scrollbar-color:var(--line2) transparent}\n"
".bkt .rnd{display:flex;flex-direction:column;min-width:64px;flex:none}\n"
".bkt .rname{font-family:var(--cond);text-transform:uppercase;letter-spacing:.08em;font-weight:700;font-size:10px;color:var(--gold2);text-align:center;padding-bottom:5px;margin-bottom:5px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg)}\n"
".bkt .rmatches{flex:1;display:flex;flex-direction:column;justify-content:space-around;gap:5px}\n"
".bkt .mt{border:1px solid var(--line);border-radius:7px;overflow:hidden;background:var(--surface)}\n"
".bkt .tm{display:flex;align-items:center;gap:5px;padding:3px 5px;line-height:1;border-bottom:1px solid var(--line);color:var(--muted)}\n"
".bkt .tm:last-child{border-bottom:none}\n"
".bkt .tm .fl{font-size:13px;filter:grayscale(.35);opacity:.85}\n"
".bkt .tm .cd{font-family:var(--mono);font-weight:700;font-size:10.5px;letter-spacing:.02em}\n"
".bkt .tm.win{color:var(--txt);background:linear-gradient(90deg,rgba(246,196,81,.20),rgba(246,196,81,.02))}\n"
".bkt .tm.win .fl{filter:none;opacity:1;text-shadow:0 0 7px rgba(246,196,81,.6)}\n"
".bkt .tm.win .cd{color:var(--gold2)}\n"
'.bkt .tm.win::after{content:"";width:5px;height:5px;border-radius:50%;background:var(--gold);margin-left:auto;box-shadow:0 0 6px rgba(246,196,81,.8)}\n'
".bkt .champcard{display:flex;flex-direction:column;justify-content:center;align-items:center;min-width:118px;flex:none;border:1px solid rgba(246,196,81,.5);border-radius:12px;background:radial-gradient(120% 90% at 50% 0%,rgba(246,196,81,.20),var(--surface));padding:16px 12px}\n"
".bkt .champcard .lab{font-family:var(--cond);text-transform:uppercase;letter-spacing:.16em;font-size:9.5px;color:var(--gold);text-align:center}\n"
".bkt .champcard .ico{font-size:30px;margin:6px 0 2px}\n"
".bkt .champcard .cn{font-family:var(--disp);font-size:21px;text-transform:uppercase;text-align:center;line-height:1.02;color:var(--gold2)}\n"
".bkt .champcard .pct{font-family:var(--mono);color:var(--muted);font-size:9.5px;margin-top:6px;text-align:center;line-height:1.5}"
)

NEW_JS = (
'const CODE={"South Korea":"KOR","United States":"USA","Ivory Coast":"CIV","Congo DR":"COD","Bosnia-Herzegovina":"BIH","Türkiye":"TUR","Czechia":"CZE","Netherlands":"NED","Switzerland":"SUI","Croatia":"CRO","Germany":"GER","Portugal":"POR","Uruguay":"URU","Paraguay":"PAR","Senegal":"SEN","England":"ENG","Algeria":"ALG","Austria":"AUT","Panama":"PAN","Ecuador":"ECU","Morocco":"MAR","Colombia":"COL","Belgium":"BEL","Argentina":"ARG","Brazil":"BRA","Mexico":"MEX","France":"FRA","Spain":"ESP","Japan":"JPN","Canada":"CAN","Iran":"IRN","Egypt":"EGY"};\n'
"function bcode(nm){if(CODE[nm])return CODE[nm];return (nm||'').replace(/[^A-Za-z]/g,'').toUpperCase().slice(0,3);}\n"
"const bkt=document.getElementById('bkt');\n"
"for(const [rn,mts] of BK){\n"
"  const col=document.createElement('div');col.className='rnd';\n"
"  let h=`<div class=\"rname\">${rn}</div><div class=\"rmatches\">`;\n"
"  for(const [a,b,win] of mts){\n"
"    h+=`<div class=\"mt\"><div class=\"tm${win===0?' win':''}\"><span class=\"fl\">${FLAGS[a]||''}</span><span class=\"cd\">${bcode(a)}</span></div><div class=\"tm${win===1?' win':''}\"><span class=\"fl\">${FLAGS[b]||''}</span><span class=\"cd\">${bcode(b)}</span></div></div>`;\n"
"  }\n"
"  h+=`</div>`;\n"
"  col.innerHTML=h;bkt.appendChild(col);\n"
"}"
)

css_pat = re.compile(r"\.bkt\{display:flex;gap:22px.*?\.champcard \.pct\{[^}]*\}", re.S)
js_pat = re.compile(r"const bkt=document\.getElementById\('bkt'\);.*?col\.innerHTML=h;bkt\.appendChild\(col\);\n\}", re.S)

for f in files:
    h = f.read_text(encoding="utf-8")
    h, n1 = css_pat.subn(NEW_CSS, h, count=1)
    assert n1 == 1, f"CSS block not matched in {f.name}"
    h, n2 = js_pat.subn(lambda m: NEW_JS, h, count=1)
    assert n2 == 1, f"JS render not matched in {f.name}"
    f.write_text(h, encoding="utf-8")
    print(f"patched {f.name} ({len(h):,} chars)")
