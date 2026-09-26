#!/usr/bin/env python3
"""Build a copy of the report with a data snapshot embedded.

Input is the JSON result of the VizQL query in tools/tableau-query.json
(one row per supplier item, per-store status pivoted into strings).

    python3 tools/build_snapshot.py result.json --as-of 2026-09-24T12:21:04Z

The repository copy of supplier-availability-report.html stays data-free
(this repository is public). The filled-in copy is written to
dist/supplier-availability-report.html, which git ignores.

Only what the report needs is embedded: stock status per store, and a coarse
1-9 demand band per store derived from "Items in Book" (used to order the
out-of-stock list). Stock quantities and raw sales figures are left out.
"""
import argparse
import collections
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "supplier-availability-report.html"
DEFAULT_OUT = ROOT / "dist" / "supplier-availability-report.html"
STORES = ["Egaila", "Hawally", "Jahra", "Salmiya", "Qibla"]

INVISIBLE = dict.fromkeys(map(ord, "​‎‏﻿"), None)
SPACES = re.compile(r"[\s  ]+")
SNAPSHOT_RE = re.compile(
    r'(<script id="snapshot" type="application/json">)(.*?)(</script>)', re.S
)


def clean(text):
    if text is None:
        return ""
    return SPACES.sub(" ", str(text).translate(INVISIBLE)).strip()


def clean_supplier(name):
    name = clean(name)
    # "Ali.Abdulwahab.Al.Mutawa.Commercial" -> "Ali Abdulwahab Al Mutawa Commercial"
    if " " not in name and "." in name:
        name = clean(name.replace(".", " "))
    return name


def demand_bands(book):
    """'119|1351|0||' -> '7|9|0|0|0': log2 bands, enough to rank items."""
    out = []
    for part in (book or "").split("|")[: len(STORES)]:
        try:
            n = float(part)
        except ValueError:
            n = 0
        out.append(str(0 if n <= 0 else min(9, 1 + int(math.log2(n)))))
    out += ["0"] * (len(STORES) - len(out))
    return "|".join(out)


def build(rows, as_of, source):
    names = collections.defaultdict(collections.Counter)
    for r in rows:
        names[r["a"]][clean_supplier(r["sn"])] += 1
    # One report per supplier account; the most used spelling names it.
    sup_name = {a: c.most_common(1)[0][0] for a, c in names.items()}
    sup_list = sorted(sup_name.items(), key=lambda kv: kv[1].lower())
    sup_index = {a: i for i, (a, _) in enumerate(sup_list)}

    cats, subs = {}, {}

    def idx(table, value):
        value = clean(value) or "Uncategorised"
        if value not in table:
            table[value] = len(table)
        return table[value]

    items = []
    for r in rows:
        status = r["s"]
        if len(status) != len(STORES):
            raise SystemExit(f"Unexpected status string {status!r} for item {r['c']}")
        items.append([
            sup_index[r["a"]],
            clean(r["c"]),
            clean(r.get("n")) or clean(r.get("d")),
            idx(cats, r.get("k")),
            idx(subs, r.get("u")),
            clean(r.get("t")) or "",
            status,
            "",
            demand_bands(r.get("b")),
        ])
    return {
        "v": 1,
        "asOf": as_of,
        "source": source,
        "stores": STORES,
        "sup": [[a, n] for a, n in sup_list],
        "cat": list(cats),
        "sub": list(subs),
        "items": items,
    }


def to_script_json(snapshot):
    text = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
    # "<" only occurs inside strings, so escaping it keeps valid JSON and
    # guarantees the text can never close the <script> element early.
    return text.replace("<", "\\u003c")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("result", help="JSON result of the VizQL query ({\"data\": [...]})")
    p.add_argument("--as-of", required=True, help="Stock snapshot time, ISO 8601 (the extract refresh time)")
    p.add_argument("--source", default="Tableau Cloud · Supplier's Availability Data")
    p.add_argument("--template", default=str(TEMPLATE), help="Report HTML to copy")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="Where to write the filled-in report")
    args = p.parse_args()

    rows = json.loads(Path(args.result).read_text(encoding="utf-8"))["data"]
    snapshot = build(rows, args.as_of, args.source)
    payload = to_script_json(snapshot)

    html = Path(args.template).read_text(encoding="utf-8")
    if not SNAPSHOT_RE.search(html):
        raise SystemExit(f'No <script id="snapshot" type="application/json"> block in {args.template}')
    html = SNAPSHOT_RE.sub(lambda m: m.group(1) + payload + m.group(3), html, count=1)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    print(
        f"{len(snapshot['items']):,} items, {len(snapshot['sup'])} suppliers, "
        f"{len(snapshot['cat'])} categories -> {out} ({len(payload) / 1024:,.0f} KB of data)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
