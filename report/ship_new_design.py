"""Ship the Claude-Design no-AI redesign as production index.html.

The design file is a React/Babel live-editing prototype: the real dashboard is the
plain <script> (block 0); the chosen look (mood=midnight / accent=tricolor /
disp=block) is applied at runtime by a TweaksPanel editor via <html> data-attrs.

For production we:
  • bake those attrs statically onto <html> (so #tweak-overrides CSS applies with no JS)
  • strip the editor apparatus: the 3 dev-CDN scripts (React/ReactDOM/Babel), the two
    <script type="text/babel"> blocks, and the #tweak-root mount
  • keep block 0 (the dashboard) + all CSS incl. #tweak-overrides

Output: index.html. The editable source stays at report/Totocalcio_no_ai_new 2026.html.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "Totocalcio_no_ai_new 2026.html"
OUT = HERE.parent / "index.html"
html = SRC.read_text(encoding="utf-8")

# 1. bake the chosen design knobs onto <html>
assert '<html lang="ja">' in html
html = html.replace('<html lang="ja">',
                    '<html lang="ja" data-mood="midnight" data-accent="tricolor" data-disp="block">', 1)

# 2. remove the editor mount point
html = html.replace('<div id="tweak-root"></div>\n', '', 1)

# 3. remove the 3 dev-CDN script tags (react / react-dom / babel)
html, n_cdn = re.subn(r'<script src="https://unpkg\.com/[^"]*"[^>]*></script>\n?', '', html)

# 4. remove the two <script type="text/babel"> editor blocks
html, n_babel = re.subn(r'<script type="text/babel">.*?</script>\n?', '', html, flags=re.S)

OUT.write_text(html, encoding="utf-8")
remaining = html.count('<script')
print(f"shipped -> index.html  (removed {n_cdn} CDN + {n_babel} babel blocks; {remaining} <script> left)")
print(f"baked: data-mood=midnight data-accent=tricolor data-disp=block")
assert n_cdn == 3 and n_babel == 2 and remaining == 1, "unexpected counts — check the strip"
