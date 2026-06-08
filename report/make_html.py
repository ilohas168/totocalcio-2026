"""Build report/predictions.html — one comprehensive dashboard:
final allocation, full per-country point flow, participant evaluation,
group/knockout predictions, bracket, model notes, and the decision log."""
import sys
import json
import base64
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from sim.tournament import load_data, simulate, GROUP_LETTERS, DATA
from optimize.allocate import (sample_unknowns, popularity, known_vectors,
                               outlier_vectors, field_ownership, vec_from_dict)

DATE = "2026-06-05"
_fa = HERE / "final_allocation.json"
FINAL = (json.loads(_fa.read_text())["allocation"] if _fa.exists() else
         {"Portugal": 10, "Spain": 9, "Argentina": 8, "Brazil": 7, "Mexico": 6,
          "Japan": 5, "France": 4, "Colombia": 3, "Morocco": 2, "England": 1})

d = load_data()
opp = json.loads((DATA / "opponents.json").read_text())
names, idx = d["names"], d["idx"]
res = simulate(n_sims=150_000, data=d, analyze=True)
ew, W = res["ewins"], res["wins"].astype(float)
gp, reach, rh, ra, wc = res["gplace"], res["reach"], res["r32_home"], res["r32_away"], res["wincnt"]
implied = (1.0 / d["odds"]); implied /= implied.sum()
fifa = np.array([d["teams"][n]["fifa_rank"] for n in names], dtype=float)
ewr = {int(c): r + 1 for r, c in enumerate(np.argsort(-ew))}

vu = vec_from_dict(FINAL, idx)
kv = known_vectors(opp, idx); known_S = np.sum(kv, axis=0)
ov = outlier_vectors(opp, idx); vF = ov[0] if ov else np.zeros(48)
# Field = 16 opponents. 6 are public (A–E chalk + contrarian F); the other 10
# are modelled. A = the 10 pile onto chalk like the known 5; B = FIFA-rank driven.
# F's real ballot is baked into both as a fixed competitor.
oppA = vF + known_S / 5.0 * 15.0
nwA = 17 * vu - (oppA + vu); enA = ew * nwA
oppB = field_ownership(opp, idx, implied, fifa, np.random.default_rng(1))
enB = ew * (17 * vu - (oppB + vu))
fo = oppA / 16.0


def diagnose(a):
    items = sorted(a.items(), key=lambda kv: -kv[1])
    over = max(items[:6], key=lambda kv: ewr[idx[kv[0]]])
    gems = [t for t in ["Mexico", "Colombia", "Japan", "Morocco"] if a.get(t, 0) >= 3]
    miss = [t for t in ["Mexico", "Colombia"] if a.get(t, 0) == 0]
    s = f"過大評価:{over[0]}(#{ewr[idx[over[0]]]})"
    if miss:
        s += "／穴逃し:" + "·".join(miss)
    if gems:
        s += "／差別化◎:" + "·".join(gems)
    return s


players = ([(k, opp["known"][k]) for k in "ABCDE"]
           + [("F", opp["outliers"]["F"]), ("あなた", FINAL)])
NP = len(players)              # 7 public ballots (incl. you)
n_unk = 17 - NP                # 10 still-unknown players
Vn = np.array([vec_from_dict(a, idx) for _, a in players])
rng = np.random.default_rng(99); pop = popularity(kv, implied, fifa)
P1 = np.zeros(NP); rank = np.zeros(NP); pnet = np.zeros(NP)
for _ in range(16):
    V = np.vstack([Vn, np.array(sample_unknowns(n_unk, pop, rng))])
    R = V @ W.T; sc = 17 * R - R.sum(0); top = np.argmax(sc, 0)
    for i in range(NP):
        P1[i] += np.mean(top == i); rank[i] += np.mean((sc > sc[i]).sum(0) + 1); pnet[i] += np.mean(sc[i])
P1 /= 16; rank /= 16; pnet /= 16
evs = [float(ew @ vec_from_dict(a, idx)) for _, a in players]
rngA = np.random.default_rng(3); accA = []
for _ in range(40):
    ch = rngA.integers(0, 5, 15)   # you + F fixed, other 15 chalk like the known 5
    Va = np.vstack([vu[None, :], vF[None, :], np.array([kv[k] for k in ch])])
    R = Va @ W.T; s = 17 * R - R.sum(0); accA.append(np.mean(np.argmax(s, 0) == 0))
P1A = 100 * np.mean(accA); P1B = 100 * P1[NP - 1]

# ---- per-participant point flow + net distribution (for the flow section) --
# S_C = total points the whole 17-player pool puts on a team (seat-independent).
# A = the 10 unknowns pile onto chalk like the known 5; B = FIFA-rank driven.
pub_lab = [p[0] for p in players]                      # A..E, F, あなた
sum7 = Vn.sum(0)                                       # the 7 public ballots
chalk = known_S / 5.0
rngFd = np.random.default_rng(7)
unkB_mean = np.mean([np.sum(sample_unknowns(n_unk, pop, rngFd), axis=0)
                     for _ in range(400)], axis=0)
ScA = sum7 + chalk * n_unk                             # 本命集中型 pool total
ScB = sum7 + unkB_mean                                 # FIFA pool total
moveset = np.where((sum7 > 0) | (ScB >= 1.5))[0]       # only teams anyone bets on
moveset = moveset[np.argsort(-ew[moveset])]            # shared order = strongest first
# net distribution per participant: best / worst / mean / percentiles
Wd = W if W.shape[0] <= 90_000 else W[:90_000]
rngDd = np.random.default_rng(11)
fieldsB = [sum7 + np.sum(sample_unknowns(n_unk, pop, rngDd), axis=0) for _ in range(12)]
flow_stats = []
for i in range(NP):
    vi = Vn[i]
    arr = np.concatenate([Wd @ (17 * vi - Sc) for Sc in fieldsB])
    flow_stats.append({
        "mean": arr.mean(), "median": float(np.median(arr)),
        "best": arr.max(), "worst": arr.min(),
        "p5": np.percentile(arr, 5), "p25": np.percentile(arr, 25),
        "p75": np.percentile(arr, 75), "p95": np.percentile(arr, 95),
        "pos": 100 * (arr >= 0).mean()})


def mwin(m):
    return int(np.argmax(wc[m]))


ko = d["bracket"]["knockout"]
def parts(m):
    if 73 <= m <= 88:
        return int(np.argmax(rh[m - 73])), int(np.argmax(ra[m - 73]))
    f1, f2 = ko[str(m)]; return mwin(f1), mwin(f2)


champ = mwin(104); fin = parts(104)


def b64(p):
    return base64.b64encode(Path(p).read_bytes()).decode() if Path(p).exists() else ""


# ---- cell helpers ---------------------------------------------------------
def gcell(p, scale=1.0, hue="46,160,67"):
    a = min(1.0, p / scale)
    return f'<td style="background:rgba({hue},{0.08+0.6*a:.2f})">{100*p:.0f}%</td>'


def fcell(v):
    if abs(v) < 1:
        return '<td class="z">0</td>'
    if v > 0:
        return f'<td style="background:rgba(46,160,67,{min(0.55,0.1+v/300):.2f})">+{v:.0f}</td>'
    return f'<td style="background:rgba(192,57,43,{min(0.55,0.1-v/300):.2f})">{v:.0f}</td>'


CSS = """
<style>
 *{box-sizing:border-box}
 body{font-family:-apple-system,'Hiragino Sans',sans-serif;max-width:1080px;margin:0 auto;
      padding:0 16px 70px;color:#1a1a1a;background:#fafafa;line-height:1.55}
 .nav{position:sticky;top:0;background:#08519c;display:flex;flex-wrap:wrap;gap:2px;padding:6px;
      z-index:10;border-radius:0 0 10px 10px;margin-bottom:8px;box-shadow:0 2px 6px rgba(0,0,0,.15)}
 .nav a{color:#fff;text-decoration:none;font-size:12.5px;padding:5px 11px;border-radius:6px}
 .nav a:hover{background:rgba(255,255,255,.22)}
 h1{font-size:23px;padding-top:12px;margin-bottom:2px}
 .sub{color:#777;font-size:12.5px;margin-top:0}
 section{scroll-margin-top:52px;margin-top:30px}
 h2{font-size:18px;color:#08519c;border-left:5px solid #08519c;padding-left:10px}
 .hero{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
 .chip{background:#fff;border:1px solid #d8e2ef;border-top:4px solid #08519c;border-radius:9px;
       padding:8px 12px;text-align:center;min-width:86px}
 .chip b{font-size:22px;color:#08519c;display:block;line-height:1}
 .chip span{font-size:13px;font-weight:700;display:block;margin-top:3px}
 .chip em{font-size:10px;color:#999;font-style:normal}
 .chip.def{border-top-color:#c0392b}
 .stat{background:#fff;border:1px solid #e2e2e2;border-radius:9px;padding:11px 15px;font-size:14px}
 .stat b{font-size:16px}
 table{border-collapse:collapse;width:100%;margin:9px 0;font-size:13px;background:#fff}
 th,td{border:1px solid #ebebeb;padding:4px 8px;text-align:center;font-variant-numeric:tabular-nums}
 th{background:#08519c;color:#fff;font-weight:600}
 td.l{text-align:left;font-weight:600}
 td.z{color:#c4c4c4}
 .pos{color:#0a7d2c;font-weight:700}.neg{color:#c0392b;font-weight:700}
 .you{background:#fff3cd!important}
 .grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
 .card{background:#fff;border:1px solid #e2e2e2;border-radius:8px;padding:6px 10px}
 .card h3{margin:6px 0;font-size:15px;color:#08519c}
 .adv{font-weight:700;color:#08519c}
 .bkt{display:flex;gap:10px;overflow-x:auto;background:#fff;border:1px solid #e2e2e2;border-radius:8px;padding:12px}
 .rnd{display:flex;flex-direction:column;justify-content:space-around;min-width:118px}
 .rname{text-align:center;font-weight:700;color:#08519c;font-size:12px;margin-bottom:4px}
 .mt{border:1px solid #cfd8e3;border-radius:5px;margin:4px 0;font-size:11px;overflow:hidden}
 .tm{padding:3px 6px;border-bottom:1px solid #eef;white-space:nowrap}
 .tm:last-child{border-bottom:none}
 .tm.win{font-weight:700;background:#e8f0fe;color:#08519c}
 .champ{font-size:18px;color:#08519c;font-weight:800}
 details{background:#fff;border:1px solid #e2e2e2;border-radius:8px;padding:8px 15px;margin:10px 0}
 summary{cursor:pointer;font-weight:700;color:#08519c;font-size:15px}
 details ul{margin:8px 0}
 img{max-width:100%;border:1px solid #e2e2e2;border-radius:8px;background:#fff;margin-top:8px}
 .muted{color:#777;font-size:12px}
 .bracketold{font-family:ui-monospace,monospace;font-size:12px;background:#fff;border:1px solid #e2e2e2;
             border-radius:8px;padding:10px;white-space:pre;overflow-x:auto}
 .flowsel{display:flex;align-items:center;gap:8px;margin:10px 0 4px}
 select{font-size:13px;font-weight:600;padding:5px 10px;border:1px solid #d8e2ef;border-radius:7px;
        background:#fff;color:#08519c;cursor:pointer}
</style>
"""

H = ['<!doctype html><html lang="ja"><meta charset="utf-8">',
     '<meta name="viewport" content="width=device-width,initial-scale=1">',
     '<title>トトカルチョ2026 ダッシュボード</title>', CSS, '<body>']

NAV = [("pick", "配点"), ("flow", "点の動き"), ("rivals", "参加者"), ("groups", "グループ"),
       ("odds", "勝ち上がり"), ("bracket", "ブラケット"), ("model", "モデル"), ("log", "記録")]
H.append('<nav class="nav">' + "".join(f'<a href="#{i}">{t}</a>' for i, t in NAV) + '</nav>')
H.append("<h1>⚽ トトカルチョ 2026 — 予想ダッシュボード</h1>")
H.append(f'<p class="sub">生成 {DATE}・150,000回モンテカルロ・Elo×市場×FIFA＋標高/暑熱/開催地・家族17人ゼロサム</p>')

# 1. final allocation (hero)
H.append('<section id="pick"><h2>🏆 確定配点（あなた）</h2><div class="hero">')
for t, p in sorted(FINAL.items(), key=lambda kv: -kv[1]):
    cls = "chip def" if t in ("France", "England") else "chip"
    tag = "（防御）" if t in ("France", "England") else ""
    H.append(f'<div class="{cls}"><b>{p}</b><span>{names[idx[t]]}{tag}</span><em>E[W]#{ewr[idx[t]]}</em></div>')
H.append('</div>')
H.append(f'<div class="stat">期待ネット <b class="pos">+{enA.sum():.0f}</b> / +{enB.sum():.0f} 点　｜　'
         f'P(1位/17人) <b>{P1A:.0f}%</b> / {P1B:.0f}%（均等 5.9%）　｜　'
         f'予想優勝 <b>{names[champ]}</b>（{100*wc[104][champ]:.0f}%）'
         f'<br><span class="muted">2値は相手＝本命集中型／FIFAランク主導（いずれも公表6人＝A〜E＋大穴F込み）の2前提</span></div></section>')

# 2. per-country point flow — switchable per participant
H.append('<section id="flow"><h2>📊 勝ち負けの点の動き（参加者切替）</h2>')
H.append('<p class="muted">各国が1勝するごとのその参加者の増減（1勝）と大会通算（A=本命集中型 / B=FIFA主導、両方とも公表6人＝A〜E＋大穴F込み）。'
         '<span class="pos">緑＝受け取る</span>／<span class="neg">赤＝支払う</span>。'
         '<b>点が動かない国（誰も賭けない弱小国）は省略</b>。下のメニューで参加者を切替。</p>')
disp_order = [NP - 1] + list(range(NP - 1))            # あなた first, then A..F
opts = "".join(
    f'<option value="{i}"{" selected" if i == NP - 1 else ""}>'
    f'{"あなた" if pub_lab[i] == "あなた" else "参加者" + pub_lab[i] + ("（大穴）" if pub_lab[i] == "F" else "")}'
    f'</option>' for i in disp_order)
H.append(f'<div class="flowsel"><span class="muted">参加者:</span>'
         f'<select id="flowsel" onchange="showFlow(this.value)">{opts}</select></div>')
for i in disp_order:
    st = flow_stats[i]; vi = Vn[i]
    lab = "あなた" if pub_lab[i] == "あなた" else "参加者" + pub_lab[i]
    mc = "pos" if st["mean"] >= 0 else "neg"
    pane = [f'<div class="flowpane" id="flow-{i}" style="display:{"block" if i == NP - 1 else "none"}">']
    pane.append(
        f'<div class="stat"><b>{lab}</b>：平均 <b class="{mc}">{st["mean"]:+.0f}</b>　｜　'
        f'ベスト <b class="pos">{st["best"]:+.0f}</b>　｜　ワースト <b class="neg">{st["worst"]:+.0f}</b>　｜　'
        f'P(合計≥0) <b>{st["pos"]:.0f}%</b>'
        f'<br><span class="muted">パーセンタイル　5% {st["p5"]:+.0f}・25% {st["p25"]:+.0f}・'
        f'中央 {st["median"]:+.0f}・75% {st["p75"]:+.0f}・95% {st["p95"]:+.0f}</span></div>')
    pane.append('<table><tr><th>国</th><th>E[W]</th><th>配点</th><th>他/人</th>'
                '<th>1勝</th><th>通算A</th><th>通算B</th></tr>')
    for c in moveset:
        pw = 17 * vi[c] - ScB[c]
        tA = ew[c] * (17 * vi[c] - ScA[c]); tB = ew[c] * (17 * vi[c] - ScB[c])
        oth = (ScB[c] - vi[c]) / 16
        pane.append(f'<tr><td class="l">{names[c]}</td><td>{ew[c]:.2f}</td><td>{int(vi[c])}</td>'
                    f'<td>{oth:.1f}</td>{fcell(pw)}{fcell(tA)}{fcell(tB)}</tr>')
    pane.append('</table></div>')
    H.append("".join(pane))
H.append('<p class="muted">通算＝期待値、ベスト/ワースト＝全シミュレーション中の最大/最小、'
         'パーセンタイル＝合計点の分布。未公表10人は固定配点が無いためモデル化（FIFA主導と仮定）。</p>')
H.append('</section>')

# 3. participants
H.append('<section id="rivals"><h2>🏅 参加者評価（公表6人＋あなた）</h2>')
H.append('<p class="muted">A〜Eは本命型、<b>F＝大穴型（コントラリアン）</b>。残り10人は未公表（FIFAランク主導と仮定）。'
         'P(1位)・順位・期待ネットは17人ゼロサムでのモンテカルロ評価。</p>')
H.append('<table><tr><th>参加者</th><th>EV指数</th><th>P(1位)</th><th>平均順位</th><th>期待ネット</th><th>診断</th></tr>')
for i in sorted(range(NP), key=lambda i: -P1[i]):
    cls = ' class="you"' if players[i][0] == "あなた" else ""
    nc = "pos" if pnet[i] >= 0 else "neg"
    dlabel = ("大穴集中（独・蘭・白・クロアチア）。ハマれば大勝ち、普段は下位"
              if players[i][0] == "F" else diagnose(players[i][1]))
    nm = "F 🃏" if players[i][0] == "F" else players[i][0]
    H.append(f'<tr{cls}><td class="l">{nm}</td><td>{evs[i]:.0f}</td>'
             f'<td class="adv">{100*P1[i]:.1f}%</td><td>{rank[i]:.1f}</td>'
             f'<td class="{nc}">{pnet[i]:+.0f}</td>'
             f'<td class="l" style="font-size:11px">{dlabel}</td></tr>')
H.append('</table></section>')

# 4. group predictions
H.append('<section id="groups"><h2>🗂️ グループ最終順位予想</h2><div class="grid">')
for L in GROUP_LETTERS:
    order = sorted(d["groups"][L], key=lambda t: -gp[t, 0])
    rows = ""
    for t in order:
        mark = "✅" if reach[t, 0] >= 0.5 else ""
        rows += (f'<tr><td class="l">{mark} {names[t]}</td>' + gcell(gp[t, 0]) +
                 gcell(gp[t, 1], .6) + f'<td class="adv">{100*reach[t,0]:.0f}%</td></tr>')
    H.append(f'<div class="card"><h3>Group {L}</h3><table>'
             f'<tr><th>国</th><th>1位</th><th>2位</th><th>進出</th></tr>{rows}</table></div>')
H.append('</div></section>')

# 5. progression / champion odds
H.append('<section id="odds"><h2>📈 勝ち上がり・優勝確率（上位16）</h2>')
H.append('<table><tr><th>国</th><th>R16</th><th>準々</th><th>準決</th><th>決勝</th><th>優勝</th></tr>')
for t in np.argsort(-reach[:, 5])[:16]:
    H.append("<tr><td class='l'>" + names[t] + "</td>" + gcell(reach[t, 1], .8) +
             gcell(reach[t, 2], .6) + gcell(reach[t, 3], .45) +
             gcell(reach[t, 4], .3, "8,81,156") + gcell(reach[t, 5], .2, "8,81,156") + "</tr>")
H.append("</table>")
prog = b64(HERE / "progression.png")
if prog:
    H.append(f'<img src="data:image/png;base64,{prog}">')
H.append('</section>')

# 6. knockout: R32 detail + bracket
H.append('<section id="bracket"><h2>🏟️ 予想決勝トーナメント</h2>')
H.append(f'<p>予想優勝 <span class="champ">{names[champ]}</span>（{100*wc[104][champ]:.0f}%）　'
         f'予想決勝 {names[fin[0]]} vs {names[fin[1]]}</p>')
ROUNDS = [("R32", [73, 75, 74, 77, 83, 84, 81, 82, 76, 78, 79, 80, 86, 88, 85, 87]),
          ("R16", [89, 90, 93, 94, 91, 92, 95, 96]),
          ("準々", [97, 98, 99, 100]), ("準決", [101, 102]), ("決勝", [104])]
cols = []
for rname, ms in ROUNDS:
    boxes = [f'<div class="rname">{rname}</div>']
    for m in ms:
        p1, p2 = parts(m); w = mwin(m)
        boxes.append(f'<div class="mt"><div class="tm {"win" if p1==w else ""}">{names[p1]}</div>'
                     f'<div class="tm {"win" if p2==w else ""}">{names[p2]}</div></div>')
    cols.append('<div class="rnd">' + "".join(boxes) + '</div>')
H.append('<div class="bkt">' + "".join(cols) + '</div>')
H.append('<p class="muted">各スロット＝最頻チーム、太字＝予想勝者。左R32→右決勝、横スクロール可。'
         '接戦/3位枠由来は確率が割れます。</p></section>')

# 7. model & math (collapsible)
H.append('<section id="model"><h2>🔬 モデルと数学</h2>')
H.append('''<details open><summary>核心の数学</summary>
<ul>
<li>総得点 = Σ 国Cの勝利数 ×（17×自分の配点 − 全員の合計配点）。<b>1勝あたりの増減 = 17×自分 − S_C</b>。</li>
<li><b>期待点最大 ⇔ E[W]（期待勝利数）順に配点</b>（相手に依存しない）。</li>
<li><b>1位確率最大は別物</b>：多数が本命集中で山分けするため、<b>高E[W]×低所有へ差別化</b>するほど1位率が上がる。</li>
</ul></details>
<details><summary>強度・会場・相手モデル</summary>
<ul>
<li>強度 = Elo × ブックメーカー優勝オッズ × FIFAランク（標準化ブレンド 0.35/0.45/0.20）。</li>
<li>試合 = レーティング差→得点ポアソン。グループのタイブレーク（勝点→得失点→総得点）再現。</li>
<li>標高 = 差1000mあたり40Elo（Mexico City 2240m / Guadalajara 1560mのみ発火、McSharry BMJ2007）。メキシコは3戦全て標高。</li>
<li>暑熱 = 気候適応差1℃あたり18Elo（屋根+AC会場は無効、Nassis 2014）。</li>
<li>開催地 = USA +90 / メキシコ +65（＋アステカ標高）/ カナダ +65（3共催で希薄化）。</li>
<li>相手モデル = 公表済み6人（A〜E＋大穴F）は実データ、未公表10人はFIFAランク主導で選ぶと仮定。Fは大穴型なので未公表者のprior（選好分布）には混ぜない（＝全員がFのように選ぶとは仮定しない）。較正：sim優勝確率≈市場（スペイン≈14%、Spearman≈0.91）。</li>
</ul></details></section>''')

# 8. decision log (collapsible)
H.append('''<section id="log"><h2>📝 今日の意思決定ログ</h2><details open><summary>10ステップ</summary><ol>
<li>モデル構築 → メキシコが標高+開催地でE[W]#4に急騰。</li>
<li>17人チャルク前提でGPP（1位確率）最適化。差別化の柱＝メキシコ/コロンビア/日本/モロッコ。</li>
<li>相手モデルを市場寄り→<b>FIFAランク主導</b>に修正 → フランス所有(9.3/人)が効き、フランス防御を確保。</li>
<li>ポルトガル=10（応援優先・E[W]#5で正当）。</li>
<li>モロッコ↔フランス入替（防御強化・ほぼタダ）→ フランス4点。</li>
<li>コロンビア↔日本入替（日本5点に格上げ・−0.6pt）。</li>
<li>同組ペア検証 → 相関−0.05〜−0.07で無害、両方維持が正解。</li>
<li>イングランド防御 → 唯一の英・非保有(−105)を、トルコ→イングランド1点で塞ぐ。</li>
<li>確定配点へ。</li>
<li><b>参加者F（大穴型）公表</b> → 既知6人として組込み（priorは非汚染）。Fとはスペイン以外ほぼ非競合・直接対決勝率78%で、<b>配点はロック維持</b>。新たな弱点はFが厚く持つ独・蘭の深部進出のみ（各2.6%・低確率で対応不要）。</li>
</ol></details>
<details><summary>限界・前提</summary><ul>
<li>P(1位)の絶対値は「自分のモデルが正しく相手は素朴」前提で楽観的。相対構造と国別の得/損が頑健。</li>
<li>FIFA点(51位以下)・一部の本拠地標高/気候は概算。3位→R32割当はAnnex C近似。</li>
<li>未公表10人の選好は仮定（公表済み6人＝A〜E＋大穴F）。残りが公表され次第差し替え可。</li>
</ul></details></section>''')

H.append('<script>function showFlow(v){'
         'document.querySelectorAll(".flowpane").forEach(function(e){e.style.display="none"});'
         'var t=document.getElementById("flow-"+v);if(t)t.style.display="block";}</script>')
H.append("</body></html>")
html = "\n".join(H)
(HERE / "predictions.html").write_text(html, encoding="utf-8")
print(f"wrote report/predictions.html ({len(html):,} chars)")
print(f"  flow: {len(moveset)} moving teams x {NP} participants  champion={names[champ]}  "
      f"netA={enA.sum():+.0f} netB={enB.sum():+.0f}  P1A={P1A:.0f}% P1B={P1B:.0f}%")
