"""Phase 4 — generate the final report: REPORT.md, a chart, and allocations.json."""
import sys
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sim.tournament import simulate, load_data, DATA  # noqa: E402
from optimize.allocate import (  # noqa: E402
    ev_optimal, gpp_optimize, build_field_draws, field_ownership, p_first,
    ev_index, seeded_start, WEIGHTS,
)

N_SIMS = 80_000
EVAL_DRAWS = 20


def alloc_table(order, pts, names, ew, implied, fo):
    return [{"pts": int(pts[k]), "team": names[c], "ewins": round(float(ew[c]), 2),
             "market": round(100 * float(implied[c]), 1), "field": round(float(fo[c]), 1)}
            for k, c in enumerate(order)]


def main():
    d = load_data()
    opp = json.loads((DATA / "opponents.json").read_text())
    names, idx = d["names"], d["idx"]
    implied = (1.0 / d["odds"]); implied = implied / implied.sum()

    full = simulate(n_sims=N_SIMS, data=d)
    base = simulate(n_sims=N_SIMS, data=d, params={"w_elo": 1.0, "use_venue": False})
    ew, ew0, W = full["ewins"], base["ewins"], full["wins"].astype(float)
    champ = full["champion"]
    cp = np.bincount(champ, minlength=48) / N_SIMS

    fifa_rank = np.array([d["teams"][n]["fifa_rank"] for n in names], dtype=float)
    rng = np.random.default_rng(20260603)
    field_own = field_ownership(opp, idx, implied, fifa_rank, rng)
    fo = field_own / 16.0  # avg points per opponent on each team (0..10 scale)
    draws = build_field_draws(opp, idx, implied, fifa_rank, W, rng, n_draws=EVAL_DRAWS)

    # three allocations
    ev_o, ev_p = ev_optimal(ew)
    g_o, g_p, _ = gpp_optimize(ev_o, ev_p, W, draws)
    favs = [idx[n] for n in opp["user_favorites"]]
    # fan-tilt: pin Portugal/Japan/Türkiye up, force all 5 favorites in, optimize rest
    pin = {idx["Portugal"]: 7, idx["Japan"]: 5, idx["Türkiye"]: 4}
    f_o, f_p, _ = gpp_optimize(*seeded_start(favs, ew, pin=pin), W, draws,
                               force=set(favs), pinned=set(pin))

    allocs = {}
    for key, (o, pt) in {"ev": (ev_o, ev_p), "gpp": (g_o, g_p), "fan": (f_o, f_p)}.items():
        v = np.zeros(48); v[o] = pt
        allocs[key] = {"P1st": round(100 * p_first(v, W, draws), 1),
                       "EV_index": round(ev_index(v, ew), 1),
                       "picks": alloc_table(o, pt, names, ew, implied, fo)}

    (Path(__file__).resolve().parent / "allocations.json").write_text(
        json.dumps(allocs, indent=2, ensure_ascii=False))

    # ---- chart -----------------------------------------------------------
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        order = np.argsort(-ew)[:24]
        colors = ["#2ca02c" if fo[i] < 0.5 else ("#ff7f0e" if fo[i] < 3 else "#d62728")
                  for i in order]
        fig, ax = plt.subplots(figsize=(9, 8))
        y = np.arange(len(order))[::-1]
        ax.barh(y, ew[order], color=colors)
        for k, i in enumerate(order):
            ax.text(ew[i] + 0.03, y[k], f"field {fo[i]:.1f}/plyr | mkt {100*implied[i]:.0f}%",
                    va="center", fontsize=7)
        ax.set_yticks(y); ax.set_yticklabels([names[i] for i in order], fontsize=8)
        ax.set_xlabel("E[W] = expected wins")
        ax.set_title("2026 WC expected wins (green=unowned value, red=field chalk/trap)")
        fig.tight_layout()
        fig.savefig(Path(__file__).resolve().parent / "ewins.png", dpi=130)
        chart = "ewins.png"
    except Exception as e:
        chart = f"(chart skipped: {e})"

    # ---- markdown --------------------------------------------------------
    def fmt_alloc(key, title):
        a = allocs[key]
        rows = "\n".join(f"| {p['pts']} | {p['team']} | {p['ewins']} | {p['market']}% | {p['field']}/人 |"
                         for p in a["picks"])
        return (f"### {title}\n"
                f"**P(1位)≈{a['P1st']}%　EV指数={a['EV_index']}**\n\n"
                f"| 点 | 国 | E[W] | 市場 | フィールド所有 |\n|--:|---|--:|--:|--:|\n{rows}\n")

    order = np.argsort(-ew)
    ewr = {int(c): r for r, c in enumerate(order)}
    ew_rows = "\n".join(
        f"| {r+1} | {names[i]} | {ew[i]:.2f} | {ew[i]-ew0[i]:+.2f} | {100*cp[i]:.1f}% | "
        f"{100*implied[i]:.1f}% | {fo[i]:.1f}/人 |"
        for r, i in enumerate(order[:24]))

    # sensitivity: per-match win% impact of host / altitude / heat
    from scipy.stats import skellam
    from sim.tournament import _lambdas, _alt_adj, _heat_adj, DEFAULT_PARAMS
    PP, VP, BASE = DEFAULT_PARAMS, d["vp"], 1800.0
    w0 = float(skellam.sf(0, *_lambdas(BASE, BASE, PP)))

    def dpt(shift):
        return 100 * (float(skellam.sf(0, *_lambdas(BASE + shift, BASE, PP))) - w0)

    az = float(_alt_adj(2240, 150, 1.0, VP))
    usa, mex = VP["host_bonus"]["United States"], VP["host_bonus"]["Mexico"]
    hot = float(_heat_adj(20, 30, 30, VP))
    sens_rows = "\n".join([
        f"| 開催地アドバンテージ（USA, グループ戦） | +{usa:.0f} | {dpt(usa):+.1f}pt |",
        f"| 開催地アドバンテージ（メキシコ/カナダ） | +{mex:.0f} | {dpt(mex):+.1f}pt |",
        f"| 標高：高地適応国 vs 低地国 @アステカ2240m | +{az:.0f} | {dpt(az):+.1f}pt |",
        f"| メキシコ重ね掛け @アステカ（開催地+標高） | +{mex+az:.0f} | {dpt(mex+az):+.1f}pt |",
        f"| 暑熱：寒冷国 vs 暑熱適応国 @30℃開放会場 | {hot:.0f} | {dpt(hot):+.1f}pt |",
    ])
    fav_rows = "\n".join(
        f"| {n} | #{ewr[idx[n]]+1} | {fo[idx[n]]:.1f}/人 | {ew[idx[n]]:.2f} |"
        for n in opp["user_favorites"])

    md = f"""# トトカルチョ 2026 — 最終レポート

家族17人・ゼロサム・お金なしのワールドカップ予想（勝ち数配点）の**数理最適化**。

## 1. ゲームと数学
各人が10カ国に 10→1 点を配分。ある国が勝つ（グループの引分け除外／決勝TはPK勝ち込み）たび、
点を付けた人へ**他の全員がその点を支払う**（ゼロサム）。導出される最適性：

- **期待点（純収支）最大 ⇔ E[W]（期待勝利数）の大きい順に 10→1 を振る**（相手の配点に依存しない）。
- **1位確率最大は別物**：17人の多くが本命に集中するため、**高E[W]×低所有の国へ差別化**するほど1位確率が上がる。

## 2. データとモデル（3信号アンサンブル）
- レーティング = **Elo × 市場オッズ × FIFAランク** の標準化ブレンド（重み 0.35 / 0.45 / 0.20）。
- 試合 = レーティング差→得点ポアソン。グループのタイブレーク（勝点→得失点→総得点）を再現。
- 決勝T48チーム・12組・3位8チーム（Annex C相当の制約割当）・R32〜決勝＋3位決定戦を{N_SIMS:,}回シミュレート。
- **標高/暑熱補正**（McSharry BMJ2007 / Nassis 2014）：標高差1000mあたり**40Elo**（現代は事前順応するため割引、Mexico City 2240m / Guadalajara 1560m のみ発火）、
  暑熱は気候適応差1℃あたり18Elo（屋根+AC会場＝Dallas/Houston/Atlanta/Vancouverは無効）。高地適応国＝メキシコ・エクアドル・コロンビア。
- **開催地アドバンテージ**（歴代研究で3開催国に希薄化）：USA +90 / メキシコ +65（＋アステカ標高） / カナダ +65。
- **会場**：決勝Tは試合番号→都市で正確。グループ戦は標高/開催の重要組（A/B/D/K）を**試合単位で正確化**
  （メキシコは3戦全て標高＝アステカ2戦＋グアダラハラ1戦、コロンビアは2戦標高、南ア自体も高地適応で差分は小）。他組はクラスタ平均。
- **対戦相手モデル**：未公表の11人は**FIFA世界ランク主導**で選ぶと仮定（既知5人と整合）。各国へのフィールド所有を推定。
- 較正後の sim 優勝確率は市場と整合（スペイン≈市場14%、順位相関 Spearman≈0.91）。

## 3. 気候・開催地・標高は勝率をどれだけ動かすか
同レーティング同士の試合を基準に、各要因を per-match のEloシフト→勝率pt に換算：

| 要因 | Elo換算 | グループ勝率への影響 |
|---|--:|--:|
{sens_rows}

→ **標高が主役**（メキシコ/コロンビアに最大級）、暑熱はAC有無で効いたり消えたり、開催地は素直に上乗せ。
**歴代開催国**：23大会中6開催国が優勝(≈26%)、約83%がグループ突破（グループ敗退は南ア2010・カタール2022の2例のみ）、
準決勝到達率は開催国≈27% vs 同格非開催国≈12%。メキシコはアステカ(2200m)で1970・1986とも準々決勝、WC予選でも約49戦2敗の要塞。

## 4. 期待勝利数 E[W] ランキング（上位24）
`Δ` は「素のEloのみ・補正なし」モデルからの変化。

| # | 国 | E[W] | Δ | sim優勝% | 市場% | フィールド所有 |
|--:|---|--:|--:|--:|--:|--:|
{ew_rows}

## 5. 戦略の核心：ディフェンス＋差別化
- **フランス問題**：フィールドはFIFA#1フランスに**1人平均9.3点**、スペイン8.2、イングランド7.3を盛る。
  これらが勝つたび所有者へ支払うので、**持たない＝大失血**。だから本命は**外さず相応に確保（ディフェンス）**。
- ただしフランス(E[W]#6)・イングランド(#9)は**FIFAランクほど勝ち数は伸びない**ので、**フィールド平均よりやや軽め**が最適（持ちすぎても山分け）。
- **差別化の宝**：**メキシコ**(E[W]#4・所有1.4/人)・**コロンビア**(#7・0.1)・**日本**(#10・0.5)・**モロッコ**(#8・0.4)・**USA**(#15・1.4)は
  高E[W]なのにフィールドがほぼ無視。ここを厚く持つと(N−1)≒16倍の取り分をほぼ独占。

## 6. 推奨配点（3案）

{fmt_alloc("ev", "A. 期待点最大（手堅い・仏&英の両方を防御）")}
{fmt_alloc("gpp", "B. 1位確率最大（フランス防御＋差別化）★おすすめ")}
{fmt_alloc("fan", "C. 応援フル（推し5カ国全部・ただしフランス防御を捨てる）")}

**B案がおすすめ**：フィールドが1人平均9.3点も盛る**フランスを4点で確保して大失血を防ぎ**つつ、
メキシコ7・コロンビア5・日本2・モロッコ3と**フィールドが無視する高E[W]国**で差を作る（推しはポルトガル6・日本2入り）。
**C案**は推し5カ国を全部載せられるが**フランスを外す**ため、フランス暴騰シナリオに弱く P(1位)も約5pt低い。
フランスの保険をもっと厚くしたいなら France を6〜7点に上げる手もある（要望あれば再計算）。

## 7. あなたの推し査定（現モデル）
| 国 | E[W]順位 | フィールド所有 | E[W] |
|---|--:|--:|--:|
{fav_rows}

## 8. 限界・注意
- 未公表11人はFIFAランク主導の選好モデル。実際の傾向が分かれば差し替え可（公表ルールなので直前に更新できる）。
- P(1位)の絶対値は「自分のモデルが正しく、フィールドは素朴」という前提で楽観的。**相対比較と国別の得/損**が頑健な示唆。
- FIFAランク点（51位以下）と一部の本拠地標高/気候は概算。3位→R32割当はAnnex C近似。標高/暑熱は差分・上限付き（±110 / ±90 Elo）。

## 9. 再現
```
.venv/bin/python sim/tournament.py        # E[W]ランキング＋較正チェック
.venv/bin/python sim/sensitivity.py       # 標高/暑熱/開催地の勝率感度
.venv/bin/python sim/calibrate.py         # beta×ブレンド 較正グリッド
.venv/bin/python optimize/allocate.py     # 配点最適化
.venv/bin/python report/generate_report.py# 本レポート再生成
```
チャート: `report/{chart}`
"""
    (Path(__file__).resolve().parent / "REPORT.md").write_text(md)
    print("wrote report/REPORT.md, report/allocations.json, report/" + chart)
    for k in ("ev", "gpp", "fan"):
        a = allocs[k]
        print(f"  {k:>3}: P1st={a['P1st']}%  EV={a['EV_index']}  "
              + " ".join(f"{p['pts']}:{p['team']}" for p in a["picks"]))


if __name__ == "__main__":
    main()
