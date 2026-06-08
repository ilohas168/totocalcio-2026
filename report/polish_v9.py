"""v9: split the '日程・結果' view into two separate views/tabs — 日程 (schedule)
and 結果 (group tables + knockout results). Now 4 tabs: ホーム / 日程 / 結果 /
AI予想・評価. Home gets a 3rd CTA button.
Operates on both the report HTML and index.html.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
files = [HERE / "Totocalcio 2026.html", HERE.parent / "index.html"]

EDITS = [
    # 1. rename the opening view (schedule lives alone now)
    ('  <div class="view" id="v-results" hidden>\n  <section id="schedule">',
     '  <div class="view" id="v-schedule" hidden>\n  <section id="schedule">'),
    # 2. close v-schedule after the schedule section, open a fresh v-results
    ('  </section>\n\n  <section id="groupres">',
     '  </section>\n  </div>\n\n  <div class="view" id="v-results" hidden>\n\n  <section id="groupres">'),
    # 3. tabs: 3 -> 4
    ('    <button class="tab" data-v="results">⚽ 日程・結果</button>',
     '    <button class="tab" data-v="schedule">📅 日程</button>\n    <button class="tab" data-v="results">📊 結果</button>'),
    # 4/5. switchView view lists
    ("['home','results','ai'].forEach(x=>{ const el=document.getElementById('v-'+x); if(el)el.hidden=(x!==v); });",
     "['home','schedule','results','ai'].forEach(x=>{ const el=document.getElementById('v-'+x); if(el)el.hidden=(x!==v); });"),
    ("switchView(['home','results','ai'].includes(iv)?iv:'home');",
     "switchView(['home','schedule','results','ai'].includes(iv)?iv:'home');"),
    # 6. CTA: 2 -> 3 buttons
    ('  <div class="ctarow">\n'
     '    <button class="ctabtn" data-v="results"><span class="ic">⚽</span><div><b>試合スケジュール・結果</b><span>日程 / グループ表 / トーナメント結果</span></div><span class="ar">→</span></button>\n'
     '    <button class="ctabtn" data-v="ai"><span class="ic">🤖</span><div><b>AI予想・参加者評価</b><span>優勝確率 / 各自の評価 / モデル</span></div><span class="ar">→</span></button>\n'
     '  </div>',
     '  <div class="ctarow">\n'
     '    <button class="ctabtn" data-v="schedule"><span class="ic">📅</span><div><b>対戦スケジュール</b><span>全104試合 / 3タイムゾーン</span></div><span class="ar">→</span></button>\n'
     '    <button class="ctabtn" data-v="results"><span class="ic">📊</span><div><b>結果</b><span>グループ表 / トーナメント結果</span></div><span class="ar">→</span></button>\n'
     '    <button class="ctabtn" data-v="ai"><span class="ic">🤖</span><div><b>AI予想・参加者評価</b><span>優勝確率 / 各自の評価 / モデル</span></div><span class="ar">→</span></button>\n'
     '  </div>'),
    # 7. CTA grid -> auto-fit (3 across on wide, wraps on narrow)
    ('.ctarow{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:36px 0 8px}',
     '.ctarow{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin:36px 0 8px}'),
    # 8/9. renumber sections now in the 結果 view
    ('<div class="num">02</div><div class="tt"><div class="ek">Group Tables · Live',
     '<div class="num">01</div><div class="tt"><div class="ek">Group Tables · Live'),
    ('<div class="num">04</div><div class="tt"><div class="ek">Knockout · Live',
     '<div class="num">02</div><div class="tt"><div class="ek">Knockout · Live'),
]

for f in files:
    h = f.read_text(encoding="utf-8")
    for old, new in EDITS:
        assert old in h, f"NOT FOUND in {f.name}: {old[:55]!r}"
        h = h.replace(old, new, 1)
    f.write_text(h, encoding="utf-8")
    print(f"patched {f.name} ({len(h):,} chars)")
