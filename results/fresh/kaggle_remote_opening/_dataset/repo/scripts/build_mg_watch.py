"""Build the Mother-Goose sell-point viewer: scripts/fragments/mg_watch_page.html + results/fresh/mg_watch/data.json
(from scripts/mg_watch_extract.py) -> results/fresh/mg_watch/mother-goose-sell-points.html (self-contained)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
page = (ROOT / 'scripts/fragments/mg_watch_page.html').read_text(encoding='utf-8')
# a JSON island must never contain a closing script tag
data = (ROOT / 'results/fresh/mg_watch/data.json').read_text(encoding='utf-8').replace('</', '<' + chr(92) + '/')
out = ROOT / 'results/fresh/mg_watch/mother-goose-sell-points.html'
html = page.replace('__DATA__', data)
out.write_text(html, encoding='utf-8')                     # the Artifact page (the publish skeleton adds the head)
local = out.with_name('mother-goose-sell-points-local.html')  # opens straight from disk
local.write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">' + html,
                 encoding='utf-8')
print(out, round(out.stat().st_size / 1e6, 2), 'MB;', local.name)
