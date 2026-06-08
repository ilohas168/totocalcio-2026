"""Generate report/SIMULATION_LOG.md — a full record of today's simulation:
the model, the final allocation, the complete per-country win/loss point flow,
participant evaluation, predictions, and the day's decisions."""
import sys
import json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from sim.tournament import load_data, simulate, GROUP_LETTERS, DATA
from optimize.allocate import (vec_from_dict, field_ownership, sample_unknowns,
                               popularity, known_vectors, outlier_vectors)

DATE = "2026-06-05"
d = load_data()
opp = json.loads((DATA / "opponents.json").read_text())
names, idx = d["names"], d["idx"]
res = simulate(n_sims=200_000, data=d, analyze=True)
ew, W = res["ewins"], res["wins"].astype(float)
reach, gp, rh, ra, wc = res["reach"], res["gplace"], res["r32_home"], res["r32_away"], res["wincnt"]
implied = (1.0 / d["odds"]); implied /= implied.sum()
fifa = np.array([d["teams"][n]["fifa_rank"] for n in names], dtype=float)
ewr = {int(c): r + 1 for r, c in enumerate(np.argsort(-ew))}

FINAL = json.loads((HERE / "final_allocation.json").read_text())["allocation"]
vu = vec_from_dict(FINAL, idx)
N = 17
kv = known_vectors(opp, idx); known_S = np.sum(kv, axis=0)
ov = outlier_vectors(opp, idx); vF = ov[0] if ov else np.zeros(48)

# two field models — both bake in the 6 public ballots (A–E chalk + contrarian F).
# A: the 10 still-unknown pile onto chalk like the known 5; B: FIFA-rank driven.
oppA = vF + known_S / 5.0 * 15.0                             # F + 15 chalk-like clones
oppB = field_ownership(opp, idx, implied, fifa, np.random.default_rng(1))  # FIFA-rank field
nwA = N * vu - (oppA + vu); enA = ew * nwA
nwB = N * vu - (oppB + vu); enB = ew * nwB

# participant scoreboard (FIFA field)
players = ([(k, opp["known"][k]) for k in "ABCDE"]
           + [("F", opp["outliers"]["F"]), ("あなた", FINAL)])
NP = len(players)              # 7 public ballots (incl. you)
n_unk = 17 - NP                # 10 still-unknown players
Vn = np.array([vec_from_dict(a, idx) for _, a in players])
rng = np.random.default_rng(99); pop = popularity(kv, implied, fifa)
P1 = np.zeros(NP); rank = np.zeros(NP); pnet = np.zeros(NP)
for _ in range(20):
    V = np.vstack([Vn, np.array(sample_unknowns(n_unk, pop, rng))])
    R = V @ W.T; sc = 17 * R - R.sum(0); top = np.argmax(sc, 0)
    for i in range(NP):
        P1[i] += np.mean(top == i); rank[i] += np.mean((sc > sc[i]).sum(0) + 1); pnet[i] += np.mean(sc[i])
P1 /= 20; rank /= 20; pnet /= 20
evs = [float(ew @ vec_from_dict(a, idx)) for _, a in players]

# P(1st) under "all like known 5" (you + F fixed, other 15 chalk)
rngA = np.random.default_rng(3); accA = []
for _ in range(40):
    ch = rngA.integers(0, 5, 15)
    Va = np.vstack([vu[None, :], vF[None, :], np.array([kv[k] for k in ch])])
    R = Va @ W.T; s = 17 * R - R.sum(0); accA.append(np.mean(np.argmax(s, 0) == 0))
P1A = 100 * np.mean(accA)

# ---- markdown -------------------------------------------------------------
def alloc_lines():
    return "\n".join(f"| {p} | {t} | {ew[idx[t]]:.2f} | #{ewr[idx[t]]} |"
                     for t, p in sorted(FINAL.items(), key=lambda kv: -kv[1]))

# full 48-country flow, sorted by expected net (model A)
flow_rows = ""
for c in np.argsort(-enA):
    fa = oppA[c] / 16; fb = oppB[c] / 16
    flow_rows += (f"| {names[c]} | {ew[c]:.2f} | {int(vu[c])} | {fa:.1f} | "
                  f"{nwA[c]:+.0f} | {enA[c]:+.0f} | {enB[c]:+.0f} |\n")

sb_rows = ""
for i in sorted(range(NP), key=lambda i: -P1[i]):
    nm = ("**あなた**" if players[i][0] == "あなた"
          else "F（大穴型）" if players[i][0] == "F" else players[i][0])
    sb_rows += f"| {nm} | {evs[i]:.0f} | {100*P1[i]:.1f}% | {rank[i]:.1f} | {pnet[i]:+.0f} |\n"

champ_rows = ""
for t in np.argsort(-reach[:, 5])[:12]:
    r = reach[t]
    champ_rows += (f"| {names[t]} | {100*r[1]:.0f}% | {100*r[2]:.0f}% | {100*r[3]:.0f}% | "
                   f"{100*r[4]:.0f}% | {100*r[5]:.1f}% |\n")

grp_rows = ""
for L in GROUP_LETTERS:
    o = sorted(d["groups"][L], key=lambda t: -gp[t, 0])
    a, b = o[0], o[1]
    grp_rows += (f"| {L} | {names[a]} ({100*gp[a,0]:.0f}%) | {names[b]} ({100*gp[b,0]:.0f}%) | "
                 f"{names[a]}/{names[b]} ({100*reach[a,0]:.0f}/{100*reach[b,0]:.0f}%) |\n")


def mwin(m):
    return int(np.argmax(wc[m]))


ko = d["bracket"]["knockout"]
def parts(m):
    if 73 <= m <= 88:
        return int(np.argmax(rh[m - 73])), int(np.argmax(ra[m - 73]))
    f1, f2 = ko[str(m)]; return mwin(f1), mwin(f2)


r32_rows = ""
for mm in d["bracket"]["r32"]:
    m = mm["match"]; h, a = parts(m); w = mwin(m)
    r32_rows += f"| M{m} | {names[h]} | {names[a]} | **{names[w]}** |\n"

totA, totB = enA.sum(), enB.sum()
champ = mwin(104); fin = parts(104)

MD = f"""# トトカルチョ 2026 — シミュレーション全記録
生成日: {DATE}　/　200,000回モンテカルロ　/　モデル: Elo×市場×FIFA ＋ 標高/暑熱/開催地補正　/　公表参加者: A〜E＋大穴F＋あなた

---

## 0. ゲームのルール
- 家族 **17人**、各自 **10カ国**に **10→1点**を配分。お金はかけない。
- ある国が**試合に勝つ**たび、その国に点を付けた人へ **他の全員がその点を支払う**（**ゼロサム**）。
- **「勝ち」** = グループ戦の勝利（引分けはノーカウント）＋ 決勝トーナメントの勝利（**PK勝ちも含む**）。
- 配点は事前公表OK。

## 1. 核心の数学
プレイヤー P の総得点 = Σ_C W_C·(N·v_P(C) − S_C)　（W_C=国Cの勝利数, v=配点, S_C=全員の合計配点, N=17）。
- **期待点（純収支）最大 ⇔ E[W]（期待勝利数）の高い順に配点**（相手に依存しない）。
- **1位確率最大は別物**：多数が本命に集中するため、**高E[W]×低所有**へ差別化するほど1位率が上がる。
- 1勝あたりの自分の増減 = **N·v_自分 − S_C**。相手の所有が厚い国は薄くなり、誰も持たない国は (N−1)×自分の点を独占。

## 2. モデル
- **強度** = World Football Elo・ブックメーカー優勝オッズ・FIFAランクの標準化ブレンド（0.35 / 0.45 / 0.20）。
- **試合** = レーティング差→得点ポアソン。グループのタイブレーク（勝点→得失点→総得点）を再現。
- **会場補正**（McSharry BMJ2007 / Nassis 2014 ほか）：
  - 標高 = 差1000mあたり **40Elo**（事前順応で割引）。発火するのは Mexico City 2240m と Guadalajara 1560m のみ。
  - 暑熱 = 気候適応差1℃あたり 18Elo（屋根+AC会場＝Dallas/Houston/Atlanta/Vancouverは無効）。
  - 開催地 = USA +90 / メキシコ +65（＋アステカ標高） / カナダ +65（3共催で希薄化）。
  - グループ戦の会場は A/B/D/K を**試合単位で正確化**（メキシコは3戦全て標高、コロンビアは2戦標高）。
- **対戦相手モデル**：公表済み6人（A〜E＋大穴F）は実データ、未公表10人は **FIFA世界ランク主導**で選ぶと仮定。**Fは大穴型（コントラリアン）なので未公表者の選好prior（事前分布）には混ぜない**＝「全員がFのように選ぶ」とは仮定しない。
- **較正**：sim優勝確率を市場に整合（スペイン≈14%、Spearman≈0.91）。

## 3. 確定配点（あなた）
| 点 | 国 | E[W] | E[W]順位 |
|--:|---|--:|--:|
{alloc_lines()}

期待ネット: **{totA:+.0f}点**（本命集中型フィールド・F込み）/ **{totB:+.0f}点**（FIFAランク主導フィールド・F込み）。
P(1位/17人): **{P1A:.0f}%**（本命集中型）/ **{100*P1[NP-1]:.0f}%**（FIFA主導）。均等なら5.9%。

## 4. 勝ち負けの点の動き（全48カ国）★
各国が **1勝するごとのあなたの増減**（`1勝`）と、大会通算の期待増減。
`通算A`＝相手が本命集中型の前提、`通算B`＝FIFAランク主導前提（いずれも公表6人＝A〜E＋大穴F込み）。**プラス＝あなたが受け取る／マイナス＝あなたが支払う。**

| 国 | E[W] | 僕 | 相手/人 | 1勝 | 通算A | 通算B |
|---|--:|--:|--:|--:|--:|--:|
{flow_rows}
> 「勝ち」（プラス）＝あなたが厚く張る or 相手が薄い国。「負け」（マイナス）＝相手が厚く張りあなたが薄い国（イングランド・フランス・オランダ）。
> あなたも相手も0点の国は増減0。合計はゼロサムの取り分＝あなたの期待ネット。

## 5. 参加者評価（公表6人＋あなた・17人ゼロサム）
| 参加者 | EV指数 | P(1位) | 平均順位 | 期待ネット |
|---|--:|--:|--:|--:|
{sb_rows}
- あなたが頭一つ抜けてトップ。全員が本命集中で山分けする中、**メキシコ/コロンビア/日本/モロッコの差別化**が効いている。
- 本命型(A〜E)の弱点共通：**オランダ過大評価・コロンビア見逃し・メキシコ軽視**。Bは純チャルクで最も勝てない。
- **F＝大穴型（コントラリアン）**：独9・蘭8・白7・クロアチア6など本命外に集中。あなたとはスペイン以外ほぼ非競合で**直接対決勝率78%**。普段は下位だが「ハマった世界線」では集団ごと抜く高分散（＝たまに大勝ち）。

## 6. 予想
### 6.1 グループ最終順位（予想1位 / 2位 / 進出率）
| 組 | 1位 | 2位 | 進出(1/2位) |
|---|---|---|---|
{grp_rows}
### 6.2 勝ち上がり・優勝確率（上位12）
| 国 | R16 | 準々 | 準決 | 決勝 | 優勝 |
|---|--:|--:|--:|--:|--:|
{champ_rows}
### 6.3 予想ブラケット
予想優勝 = **{names[champ]}**（{100*wc[104][champ]:.0f}%）、予想決勝 = **{names[fin[0]]} vs {names[fin[1]]}**。

| 試合 | 最有力(home) | 最有力(away) | 予想勝者 |
|---|---|---|---|
{r32_rows}

## 7. 今日の意思決定ログ
1. モデル構築（Elo×市場×FIFA＋会場補正）→ E[W]推定。**メキシコが標高+開催地でE[W]#4に急騰**。
2. 17人チャルク・フィールド前提で **GPP（1位確率）最適化**。差別化の柱＝メキシコ/コロンビア/日本/モロッコ。
3. **対戦相手モデルを市場寄り→FIFAランク主導に修正**（指摘反映）。これでフランス所有(9.3/人)が正しく効き、**フランス防御を確保**。
4. **ポルトガル=10**（応援優先・E[W]#5で正当）。
5. **モロッコ↔フランス入替**（防御強化・ほぼタダ）→ フランス4点。
6. **コロンビア↔日本入替**（日本5点に応援格上げ・−0.6pt）。
7. **同組ペア検証**（ポルトガル+コロンビア / ブラジル+モロッコ）：相関−0.05〜−0.07で無害、E[W]の質が勝るため**両方維持が正解**。
8. **イングランド防御**：6人で唯一の英・非保有＝最大の穴(−105)。**トルコ→イングランド1点**で塞ぐ（P(1位)不変・EV微増）。
9. → 確定配点（第3章）。
10. **参加者F（大穴型）公表**：既知6人として組込み（priorは非汚染）。Fとはスペイン以外ほぼ非競合・直接対決勝率78%・P(合計≥0)≈71%維持で、**配点はロックのまま**。新たな弱点はFが厚く張る独・蘭の深部進出のみ（各≈2.6%・低確率につき対応不要）。

## 8. 限界・前提
- P(1位)の絶対値は「自分のモデルが正しく相手は素朴」前提で楽観的。**相対構造と国別の得/損が頑健**。
- FIFA点(51位以下)・一部の本拠地標高/気候は概算。3位→R32割当はAnnex C近似。標高/暑熱は差分・上限付き(±110/±90 Elo)。
- 未公表10人の選好は仮定（公表済み6人＝A〜E＋大穴F）。直前に残りの公表が分かれば差し替え可。

## 9. 成果物・再現
- データ: `data/`（組分け・レーティング・会場・対戦相手・グループ日程）
- エンジン: `sim/tournament.py`（モンテカルロ）・`sim/calibrate.py`・`sim/sensitivity.py`
- 最適化: `optimize/allocate.py`・`optimize/custom.py`
- レポート/可視化: `report/REPORT.md`・`report/predictions.html`・`report/predict.py`・`report/make_html.py`・`report/document.py`
- 確定配点: `report/final_allocation.json`
- 再現: `.venv/bin/python report/document.py` で本書を再生成。
"""
(HERE / "SIMULATION_LOG.md").write_text(MD, encoding="utf-8")
print(f"wrote report/SIMULATION_LOG.md ({len(MD):,} chars)")
Fidx = next(i for i, (k, _) in enumerate(players) if k == "F")
print(f"  net A(known-like)={totA:+.0f}  net B(FIFA)={totB:+.0f}  "
      f"P1st A={P1A:.0f}%  B(you)={100*P1[NP-1]:.0f}%  F={100*P1[Fidx]:.0f}%  champion={names[champ]}")
