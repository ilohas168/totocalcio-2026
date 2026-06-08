"""v4 tweaks:
 1. Country popup now shows a results summary (W-D-L + goal diff from finished
    matches) on top of the per-match rows (which already carry the scores).
 2. Remove the 🃏 emoji shown next to Sumie in the standings.
 3. Remove the hero lede paragraph (生成日 / モンテカルロ / ゼロサム説明).
Operates on both the report HTML and index.html.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
files = [HERE / "Totocalcio 2026.html", HERE.parent / "index.html"]

OLD_SUB = """  const c=(typeof MATRIX!=='undefined'&&MATRIX.countries||[]).find(x=>x.nm===nm);
  document.getElementById('cmSub').textContent=
    (c?`期待勝利数 ${c.ew} · `:'')+`${ms.length}試合（決勝Tは勝ち上がりで追加）`;"""
NEW_SUB = """  let _w=0,_d=0,_l=0,_gf=0,_ga=0,_p=0;
  ms.forEach(x=>{ if(x.status==='FINISHED'&&x.score){_p++;
    const mine=x.home===nm?x.score[0]:x.score[1], opp=x.home===nm?x.score[1]:x.score[0];
    _gf+=mine;_ga+=opp; if(mine>opp)_w++; else if(mine<opp)_l++; else _d++; } });
  const c=(typeof MATRIX!=='undefined'&&MATRIX.countries||[]).find(x=>x.nm===nm);
  document.getElementById('cmSub').innerHTML=
    (_p?`<b style="color:var(--gold2)">${_w}勝${_d}分${_l}敗</b> 得失点${_gf-_ga>=0?'+':''}${_gf-_ga}（${_gf}-${_ga}） · `:'')
    +(c?`期待勝利数 ${c.ew} · `:'')+`全${ms.length}試合`;"""

OLD_JOKER = "    const nm=r.joker?`${r.name} 🃏`:r.name;"
NEW_JOKER = "    const nm=r.name;"

OLD_LEDE = ("""    <p class="lede">予想ダッシュボード &nbsp;·&nbsp; 生成 <b>2026-06-06</b> &nbsp;·&nbsp; <b>150,000回</b>モンテカルロ<br>
    Elo × 市場 × FIFA ＋ 標高 / 暑熱 / 開催地補正 &nbsp;·&nbsp; 家族<b>19人</b>のゼロサム配点ゲーム（全員確定）</p>
""")

for f in files:
    h = f.read_text(encoding="utf-8")
    for old, new in [(OLD_SUB, NEW_SUB), (OLD_JOKER, NEW_JOKER), (OLD_LEDE, "")]:
        assert old in h, f"NOT FOUND in {f.name}: {old[:50]!r}"
        h = h.replace(old, new, 1)
    f.write_text(h, encoding="utf-8")
    print(f"patched {f.name} ({len(h):,} chars)")
