"""Builds the GitHub Pages site into _site/: the landing page plus the live demo.

The demo is the real web UI from dropper/static, with site/demo/demo.js answering its API calls
in the browser. Run `python site/build.py` and open _site/index.html through any static server,
for example `python -m http.server -d _site`.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
STATIC = ROOT / "dropper" / "static"
OUT = ROOT / "_site"

BAR = """<div class="demo-bar"><span class="dot" aria-hidden="true"></span><b>Live demo</b>
  <span>Made-up games and streams, and the clock runs fast. Changes stay in this browser.</span>
  <a href="../" target="_top">About Dropper</a><a href="https://github.com/MKI002/dropper-app" target="_top">Get it on GitHub</a></div>"""


def version() -> str:
    digest = hashlib.sha1()
    for path in sorted([*STATIC.rglob("*"), *(SITE / "demo").rglob("*")]):
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()[:10]


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SITE, OUT, ignore=shutil.ignore_patterns("build.py", "__pycache__"))
    shutil.copytree(STATIC, OUT / "demo" / "static")
    v = version()
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    html = html.replace("<title>Dropper</title>", "<title>Dropper · Live demo</title>")
    html = html.replace('<link rel="stylesheet" href="static/css/app.css?v=__ASSET_VERSION__">',
                        '<link rel="stylesheet" href="static/css/app.css?v=__ASSET_VERSION__">\n'
                        '  <link rel="stylesheet" href="demo.css?v=__ASSET_VERSION__">')
    html = html.replace("<body>", "<body>\n  " + BAR, 1)
    html = html.replace('  <script src="static/js/i18n.js', '  <script src="demo.js?v=__ASSET_VERSION__"></script>\n  <script src="static/js/i18n.js', 1)
    html = html.replace("__ASSET_VERSION__", v)
    for needle in ("demo.css", "demo.js", "demo-bar"):
        if needle not in html:
            raise SystemExit(f"demo page is missing {needle}: did dropper/static/index.html change?")
    (OUT / "demo" / "index.html").write_text(html, encoding="utf-8")
    (OUT / ".nojekyll").write_text("")
    print(f"built {OUT} (assets {v})")


if __name__ == "__main__":
    main()
