# 引き継ぎメモ（Claude向け）

家族でやるワールドカップ・トトカルチョの予測＆ライブダッシュボード。このファイルは
作業を引き継ぐ Claude への説明。コードのコメント・コミットは英語、会話は日本語。

## このプロジェクトは何か

- 2026 FIFAワールドカップの家族プール（19人）。各自が10カ国を選び 10→1 点を配分。
- ある国が**1勝するたび**、その国に点を置いた人へ他全員が点を払う**ゼロサム精算**。
  「勝ち」＝グループ戦の勝利（引き分けはノーカウント）＋決勝トーナメントの勝ち上がり
  （PK勝ち含む）。
- 各参加者の通算得点 = `Σ_C W_C·(N·v_P(C) − S_C)`
  （`W_C`=国Cの勝利数、`v_P(C)`=PがCに置いた点、`S_C`=全員がCに置いた点の合計、`N`=19）。
- 配点の最適化は「期待勝利数 E[W_C] が大きい国に大きい点」に帰着（README.md に詳説）。

**公開先**: https://ilohas168.github.io/totocalcio-2026/ （GitHub Pages, repo ルートの `index.html`）
**リポジトリ**: https://github.com/ilohas168/totocalcio-2026

## 現在の状況（2026-06-14 時点）

- グループ戦が進行中。8試合終了。勝利: Mexico, South Korea, United States, Scotland, Australia 各1。
- 順位トップ3: Daiji・Ana +196 / Yoshiaki・Kengo +158 / Shinichiro（＝オーナー本人, "you"）+63。
- 本人の理論ベスト/ワースト: +2277 / −2186。
- 大会期間中はライブ更新が回り続けている（下記パイプライン）。

## リポジトリ構成（重要ファイル）

- `index.html` — 公開ダッシュボード本体（"family" デザイン）。**GitHub Pages はこれを配信**。
- `report/Totocalcio 2026.html` — もう一つの（旧）デザイン版。**ライブ系のJS変更は両方に同じ内容で入れる**。
- `data/*.json` — `schedule.json`（全104試合）, `results.json`（国→勝利数）, `opponents.json`
  （参加者の配点）, `groups.json`/`bracket.json`/`teams.json`/`venues.json` ほか, `live_stats.json`
  （再計算のフィンガープリント＋平均）。
- `report/fetch_matches.py` — football-data.org から取得 → `schedule.json` + `results.json` を書く。
- `report/refresh_cases.py` — ベスト/ワーストの**理論値**＋平均/分位点の再計算。両HTMLに反映。
- `report/refresh_live.py` — 順位表＋日程の差し込み（標準ライブラリのみ・軽量）。
- `report/refresh_dashboard_data.py` — 予測レイヤ全部（グループ/オッズ/ブラケット/FLOW/RIVALS等）の
  再生成。**参加者や配点が変わったときだけ**手動で回す。ライブ更新には含まれない。
- `sim/tournament.py` — モンテカルロ・エンジン。`simulate(fixed=...)` で実結果を固定して条件付き化。
- `sim/theoretical.py` — ベスト/ワーストの**厳密最適化**（グループ戦中=CBC MILP, グループ終了後=ブラケットDP）。
- `optimize/` — 配点最適化（`allocate.py`, `custom.py`）。
- `.github/workflows/update.yml` — ライブ更新の CI。
- `requirements.txt` — Python依存（numpy, pulp, scipy）。

## ライブ更新パイプライン

CI (`update.yml`) が大会期間（2026-06-08〜07-21）に回す。1回の実行で:

```
fetch_matches.py        # 結果取得 → schedule.json / results.json
refresh_cases.py        # 理論ベスト/ワースト + 条件付きMCの平均・分位点（新結果が無ければ即スキップ）
refresh_live.py         # 順位表 + 日程を両HTMLに差し込み
→ git commit & push     # 変更があれば自動コミット → Pages 再デプロイ
```

- トリガー: `schedule: */15`（だが **GitHub に強く間引かれて実際は1.6〜4.7時間おき**）＋ `workflow_dispatch`（手動/外部）。
- **保留中の改善**: cron-job.org から `workflow_dispatch` を15分おきに叩いて安定化する計画（fine-grained PAT が必要）。
  オーナーが設定する予定だったが、実施済みかは要確認。未設定なら更新は数時間おきのまま。
- 反映遅延の公称は「試合終了から通常30分前後、最大3時間ほど」。UIにもそう明記してある。

## ベスト/ワースト＝理論値（重要な設計判断）

- 表示する「ベストケース（現時点）/ワーストケース（現時点）」は、終了済みの全試合を実結果に固定した上で、
  残り試合の**全ての起こりうる組み合わせ**に対する得点の**厳密な最大/最小**（`sim/theoretical.py`）。
  決定的・ノイズなし・単調（可能性が実際に消えたときだけ動く）。
- 平均・中央値・分位点・分布グラフは引き続き条件付きモンテカルロ（`sim/tournament.py` の `simulate(fixed=...)`）。
- **なぜモンテカルロの最大値をやめたか**: MCの最大値は引き直すだけで±100揺れ、「メキシコが勝ったのに
  ベストが下がった」という直感に反する挙動が出た。オーナーが理論値を明示的に選択。**勝手にMC/p99に戻さない**。
- 再計算コスト ≈ 2.5分（19人×ベスト/ワースト＝38最適化）。新結果が無いときは `live_stats.json` の
  フィンガープリントで丸ごとスキップ。強制再計算したいなら `data/live_stats.json` を消す。

## 既知の落とし穴

1. **football-data.org 無料版のデータ揺れ**:
   - 試合終了直後に `FINISHED` だがスコア/勝者が null の状態を返すことがある（最大〜2h）。
   - さらに、**一度終了した試合を1日後に IN_PLAY へ巻き戻す**ことがある（Canada–Bosnia で発生）。
   - 対策: `fetch_matches.py` は前回の `schedule.json` とマージし、**確定済み（FINISHED＋スコア）を二度と未終了に戻さない**。
   - 表示側にも時間ガード `isOver(m)`（FINISHED か、キックオフから>3.5h）。固まった試合を「これから」に出さない。
2. **HTMLは2ファイル**: `index.html` と `report/Totocalcio 2026.html`。ライブJSの変更は必ず両方に。
3. **編集後はJS構文チェック**: 各HTMLの `<script>` を抽出して `node --check`。
4. **push前にrebase**: CIが頻繁に自動コミットするので `git pull --rebase origin main` してから push。

## 開発環境セットアップ

```
git clone https://github.com/ilohas168/totocalcio-2026.git && cd totocalcio-2026
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# .env を用意（gitignore。APIトークン。GH Actions のシークレットにも登録済み）:
#   FOOTBALL_DATA_TOKEN=...
```

- ライブ確認: `python report/fetch_matches.py && python report/refresh_cases.py && python report/refresh_live.py`
- 自動更新はどのマシンとも無関係に回る（トークンはCIのシークレットにある）。ローカルの `.env` は
  ローカルでテストするときだけ必要。

## 直近でやったこと（コミット参照）

- ベスト/ワーストを理論値へ切替（`sim/theoretical.py` 追加）。
- 順位表の同点同順位（タイは全員同順位、次は人数ぶん飛ぶ）＋3位タイもメダル。
- 日程を「これから」だけに、終了試合は結果ページに直近3試合（新しい順）、薄字でグループ/回戦バッジ。
- 個人ポップアップ: タイトル横に現在の得点＋順位、配点国の横に（x勝）（1勝以上のみ）。
- ビュー間スワイプ移動（ポップアップ中・横スクロール表内・縦移動は無効）。
- `fetch_matches.py` のun-finish防止マージ／`isOver` 時間ガード。
- `requirements.txt` 追加。
