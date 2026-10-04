#!/usr/bin/env python3
"""Build the hosted page: the report with no data inside, pointed at data.json.

    python3 tools/build_site.py            # writes cloudflare/public/index.html

The page loads /data.json when it opens (served by functions/data.json.js
from Cloudflare KV, behind Cloudflare Access) and checks for a newer one every
10 minutes. tools/refresh.py writes that data every hour.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "supplier-availability-report.html"
OUT = ROOT / "cloudflare" / "public" / "index.html"


def main():
    html = TEMPLATE.read_text(encoding="utf-8")
    new, n = re.subn(r'<script id="snapshot" type="application/json">.*?</script>',
                     '<script id="snapshot" type="application/json" data-src="data.json">{}</script>', html, count=1, flags=re.S)
    if n != 1:
        raise SystemExit("No snapshot block in the report template")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(new, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(new) / 1024:,.0f} KB, no data inside)")


if __name__ == "__main__":
    main()
