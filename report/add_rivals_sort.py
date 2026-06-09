"""Make 参加者評価 sortable: click ベスト / ワースト / 参加者 headers to sort
(toggles asc/desc, ▲▼ indicator). Applied to the new-design public page + its source.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
files = [HERE.parent / "index.html", HERE / "Totocalcio_no_ai_new 2026.html"]

OLD_HEAD = ('<table id="rivalTbl"><thead><tr><th style="text-align:left">参加者</th>'
            '<th>ベスト</th><th>ワースト</th></tr></thead><tbody id="rivalBody"></tbody></table>')
NEW_HEAD = ('<table id="rivalTbl"><thead><tr>'
            '<th class="rsort" data-sort="name" onclick="sortRivals(\'name\')" style="text-align:left">参加者<span class="sind"></span></th>'
            '<th class="rsort" data-sort="best" onclick="sortRivals(\'best\')">ベスト<span class="sind"></span></th>'
            '<th class="rsort" data-sort="worst" onclick="sortRivals(\'worst\')">ワースト<span class="sind"></span></th>'
            '</tr></thead><tbody id="rivalBody"></tbody></table>')

NEW_JS = (
"// ===== participant evaluation — sortable by name / best / worst =====\n"
"let rivSort={key:'name',dir:1};\n"
"function sortRivals(key){ if(rivSort.key===key) rivSort.dir=-rivSort.dir; else rivSort={key,dir:key==='best'?-1:1}; renderRivals(); }\n"
"function renderRivals(){\n"
"  const body=document.getElementById('rivalBody'); if(!body) return;\n"
"  const sg=v=>(v>=0?'+':'')+v, k=rivSort.key, dir=rivSort.dir;\n"
"  const arr=RIVALS.slice().sort((a,b)=>(k==='name'?a.name.localeCompare(b.name):(a[k]-b[k]))*dir);\n"
"  body.innerHTML='';\n"
"  arr.forEach(r=>{\n"
"    const tr=document.createElement('tr'), lab=r.name;\n"
"    tr.innerHTML=`<td class=\"l\" onclick=\"openModal(&#39;${lab}&#39;)\">${lab} ›</td>`+`<td class=\"pos\">${sg(r.best)}</td>`+`<td class=\"neg\">${sg(r.worst)}</td>`;\n"
"    body.appendChild(tr);\n"
"  });\n"
"  document.querySelectorAll('#rivalTbl th[data-sort]').forEach(th=>{const sk=th.dataset.sort,a=th.querySelector('.sind');th.classList.toggle('sorted',sk===k);if(a)a.textContent=sk===k?(dir>0?' ▲':' ▼'):'';});\n"
"}\n"
"renderRivals();"
)

CSS = (".rsort{cursor:pointer;user-select:none;white-space:nowrap}"
       ".rsort:hover{color:var(--gold2)}"
       "#rivalTbl th.sorted{color:var(--gold)}"
       "#rivalTbl .sind{font-size:9px;margin-left:1px}\n</style>")

iife_pat = re.compile(
    r"// ===== participant evaluation \(section 03\) with dist box-plot =====\n"
    r"\(function\(\)\{.*?\}\)\(\);", re.S)

for f in files:
    h = f.read_text(encoding="utf-8")
    assert OLD_HEAD in h, f"header not found in {f.name}"
    h = h.replace(OLD_HEAD, NEW_HEAD, 1)
    h, n = iife_pat.subn(lambda m: NEW_JS, h, count=1)
    assert n == 1, f"rivals IIFE not matched in {f.name}"
    assert "\n</style>" in h, f"</style> not found in {f.name}"
    h = h.replace("\n</style>", "\n" + CSS, 1)
    f.write_text(h, encoding="utf-8")
    print(f"patched {f.name}")
