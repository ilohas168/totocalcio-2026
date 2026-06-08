"""Build the AI予想なし (no-AI) version from the AI backup.

Removes everything derived from the Monte-Carlo simulation / AI prediction:
 - sections グループ最終順位予想 / 勝ち上がり・優勝確率 / 予想決勝トーナメント / モデルと数学
 - participant-eval columns P(0点以上) / 平均 / 分布 / 予想の特徴 (keeps ベスト・ワースト)
 - modal stat 平均・P, the percentile graph, and the 期待勝利数・通算 sub
 - 期待勝利数 in the cheat-sheet header tooltip + country popup; cheat-sheet columns
   re-ordered alphabetically (was expected-wins order)
 - standings pre-tournament order is now neutral (score, then name)
 - foot Monte-Carlo line; AI予想・評価 tab/button -> 参加者評価

Writes: report/Totocalcio 2026 (AIなし).html  and  index.html  (both no-AI).
Leaves report/Totocalcio 2026.html (AI) untouched.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = HERE / "Totocalcio 2026 (AI版).html"
OUT_NAMED = HERE / "Totocalcio 2026 (AIなし).html"
OUT_INDEX = ROOT / "index.html"

html = SRC.read_text(encoding="utf-8")

def rep(old, new):
    global html
    assert old in html, f"NOT FOUND: {old[:60]!r}"
    html = html.replace(old, new, 1)

def resub(pat, new, flags=re.S):
    global html
    html, n = re.subn(pat, lambda m: new, html, count=1, flags=flags)
    assert n == 1, f"REGEX NOT MATCHED: {pat[:60]!r}"

# ============ remove the 4 AI sections (groups / odds / bracket / model) ============
resub(r'\n\n  <section id="groups">.*?</section>\n  </div>', '\n  </div>')

# ============ remove their render JS (these would error on null elements) ============
resub(r'// GROUPS\nconst G=\{.*?gg\.appendChild\(c\);\n\}', '// (group prediction removed — no-AI version)')
resub(r'// BRACKET\nconst BK=\[.*?bkt\.appendChild\(cc\);', '// (predicted bracket removed — no-AI version)')

# ============ participant evaluation -> ベスト/ワースト only ============
rep('<div class="note">全19人の確定フィールドで評価（相手の推測なし）。平均/ベスト/ワースト/分布＝全シミュレーションの合計点。</div>',
    '<div class="note">各自の配点での、最も有利／不利な展開での通算得失点。名前を<b>クリックで個人詳細</b>。</div>')
rep('<table id="rivalTbl"><thead><tr><th style="text-align:left">参加者</th><th style="text-align:left">P(0点以上)</th><th>平均</th><th>ベスト</th><th>ワースト</th><th style="text-align:left">分布 5–95% ・中央</th><th style="text-align:left">予想の特徴</th></tr></thead><tbody id="rivalBody"></tbody></table>',
    '<table id="rivalTbl"><thead><tr><th style="text-align:left">参加者</th><th>ベスト</th><th>ワースト</th></tr></thead><tbody id="rivalBody"></tbody></table>')
rep("""  RIVALS.forEach(r=>{
    const tr=document.createElement('tr');
    const lab=r.name;
    const mc=r.mean>=0?'pos':'neg';
    tr.innerHTML=
      `<td class="l" onclick="openModal(&#39;${lab}&#39;)">${lab} ›</td>`+
      `<td class="barcell"><span class="v">${r.pos}%</span><div class="track"><div class="fill" style="--w:${r.pos}%"></div></div></td>`+
      `<td class="${mc}">${sg(r.mean)}</td>`+
      `<td class="pos">${sg(r.best)}</td>`+
      `<td class="neg">${sg(r.worst)}</td>`+
      `<td>${bx(r)}</td>`+
      `<td class="diag">${r.diag}</td>`;
    body.appendChild(tr);
  });""",
    """  RIVALS.slice().sort((a,b)=>a.name.localeCompare(b.name)).forEach(r=>{
    const tr=document.createElement('tr');
    const lab=r.name;
    tr.innerHTML=
      `<td class="l" onclick="openModal(&#39;${lab}&#39;)">${lab} ›</td>`+
      `<td class="pos">${sg(r.best)}</td>`+
      `<td class="neg">${sg(r.worst)}</td>`;
    body.appendChild(tr);
  });""")

# ============ modal popup: drop AI bits ============
rep("""      `<div class="mdc"><span class="flag">${FLAGS[nm]||''}</span><span class="mdnm">${nm}</span>`+
      `<span class="mdmeta">期待${ew.toFixed(2)}・通算${tot>=0?'+':''}${tot}</span></div>`+""",
    """      `<div class="mdc"><span class="flag">${FLAGS[nm]||''}</span><span class="mdnm">${nm}</span></div>`+""")
rep("""  document.getElementById('modalStat').innerHTML=
    `<span>平均 <b class="${s.mean>=0?'pos':'neg'}">${fmtSigned(s.mean)}</b></span>`+
    `<span>ベスト <b class="pos">${fmtSigned(s.best)}</b></span>`+
    `<span>ワースト <b class="neg">${fmtSigned(s.worst)}</b></span>`+
    `<span>P(0点以上) <b>${s.pos}%</b></span>`;
  document.getElementById('modalGraph').innerHTML=pgraph(s);""",
    """  document.getElementById('modalStat').innerHTML=
    `<span>ベスト <b class="pos">${fmtSigned(s.best)}</b></span>`+
    `<span>ワースト <b class="neg">${fmtSigned(s.worst)}</b></span>`;""")
rep('  <div class="pgraph" id="modalGraph"></div>\n', '')

# ============ cheat-sheet matrix: no 期待勝利数 tooltip + alphabetical column order ============
rep("""(function(){
  const t=document.getElementById('matTbl'); if(!t||!MATRIX.countries) return;
  let head='<thead><tr><th style="text-align:left">参加者＼国</th>';
  MATRIX.countries.forEach(c=>{head+=`<th class="cty" title="${c.nm} · 期待勝利数 ${c.ew}">${FLAGS[c.nm]||c.nm.slice(0,3)}</th>`;});
  head+='</tr></thead><tbody>';
  let body='';
  MATRIX.rows.forEach(r=>{
    body+=`<tr><td class="l" onclick="openModal('${r.name}')">${r.name} ›</td>`;
    r.pw.forEach(v=>{body+=matCell(v);});
    body+='</tr>';
  });
  t.innerHTML=head+body+'</tbody>';
})();""",
    """(function(){
  const t=document.getElementById('matTbl'); if(!t||!MATRIX.countries) return;
  const ord=MATRIX.countries.map((c,i)=>i).sort((a,b)=>MATRIX.countries[a].nm.localeCompare(MATRIX.countries[b].nm));
  let head='<thead><tr><th style="text-align:left">参加者＼国</th>';
  ord.forEach(i=>{const c=MATRIX.countries[i];head+=`<th class="cty" title="${c.nm}">${FLAGS[c.nm]||c.nm.slice(0,3)}</th>`;});
  head+='</tr></thead><tbody>';
  let body='';
  MATRIX.rows.forEach(r=>{
    body+=`<tr><td class="l" onclick="openModal('${r.name}')">${r.name} ›</td>`;
    ord.forEach(i=>{body+=matCell(r.pw[i]);});
    body+='</tr>';
  });
  t.innerHTML=head+body+'</tbody>';
})();""")
rep('列は期待勝利数順・横スクロール可。名前を<b>クリックで個人詳細</b>。',
    '横スクロール可。名前を<b>クリックで個人詳細</b>。')

# ============ modal country list: neutral order (配点, then name — not exp-wins) ============
rep("  const rows=d.rows.slice().sort((a,b)=>(b[2]-a[2])||(b[1]-a[1]));   // 配点 desc, then 期待勝利数",
    "  const rows=d.rows.slice().sort((a,b)=>(b[2]-a[2])||a[0].localeCompare(b[0]));   // 配点 desc, then name")

# ============ country popup: drop 期待勝利数 ============
rep("+(c?`期待勝利数 ${c.ew} · `:'')+`全${ms.length}試合`;", "+`全${ms.length}試合`;")

# ============ standings: neutral pre-tournament order (score, then name) ============
rep("  STANDINGS.forEach((r,i)=>{",
    "  STANDINGS.slice().sort((a,b)=>b.score-a.score||a.name.localeCompare(b.name)).forEach((r,i)=>{")

# ============ foot / tab / CTA ============
rep('    <span>TOTOCALCIO 2026 · 予想ダッシュボード</span>\n    <span>150,000× MONTE CARLO · GENERATED 2026-06-06</span>',
    '    <span>TOTOCALCIO 2026 · 家族ワールドカッププール</span>\n    <span>FIFA WORLD CUP 2026 · 19 PLAYERS · ZERO-SUM</span>')
rep('<button class="tab" data-v="ai">🤖 AI予想・評価</button>',
    '<button class="tab" data-v="ai">👥 参加者評価</button>')
rep('<button class="ctabtn" data-v="ai"><span class="ic">🤖</span><div><b>AI予想・参加者評価</b><span>優勝確率 / 各自の評価 / モデル</span></div><span class="ar">→</span></button>',
    '<button class="ctabtn" data-v="ai"><span class="ic">👥</span><div><b>参加者評価</b><span>各自のベスト／ワーストケース</span></div><span class="ar">→</span></button>')

# ============ misc: page title + dead pgraph caption ============
rep('<title>TOTOCALCIO 2026 — 予想ダッシュボード</title>',
    '<title>TOTOCALCIO 2026 — 家族ワールドカッププール</title>')
rep('📊 合計点の分布（全シミュレーション）', '📊 合計点の分布')

OUT_NAMED.write_text(html, encoding="utf-8")
OUT_INDEX.write_text(html, encoding="utf-8")
left = sum(html.count(t) for t in ["期待勝利数", "シミュレーション", "MONTE", "優勝確率", "進出確率"])
print(f"no-AI built -> index.html + {OUT_NAMED.name} ({len(html):,} chars)")
print(f"residual AI-term count (期待勝利数/シミュ/MONTE/優勝確率/進出確率): {left}")
