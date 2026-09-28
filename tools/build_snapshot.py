#!/usr/bin/env python3
"""Build a copy of the report with a data snapshot embedded.

The report reads Tableau live when it is opened in Claude with the Tableau
Cloud connector; the snapshot is what it shows until that read arrives, or
when live access is not available.

Current format (with sales): run the two queries the report itself runs,
then build.

    python3 tools/build_snapshot.py --meta-query > q1.json        # run it, save as meta.json
    python3 tools/build_snapshot.py --pivot-query meta.json > q2.json  # run it, save as pivot.json
    python3 tools/build_snapshot.py --meta meta.json pivot.json

Older format (no sales): the JSON result of tools/tableau-query.json.

    python3 tools/build_snapshot.py result.json --as-of 2026-09-24T12:21:04Z

The repository copy of supplier-availability-report.html stays data-free
(this repository is public). The filled-in copy is written to
dist/supplier-availability-report.html, which git ignores.

The current format embeds stock status, lifetime sales, current stock and
days since first sale per store, so the built copy is internal: never send it
to a supplier.
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


LUID = "a7ab1f36-6a15-4c2c-8e7a-4ea0f74a1320"


def meta_query():
    return {"fields": [
        {"fieldCaption": "Store"},
        {"fieldCaption": "inS", "calculation": "SUM(IF [Items in Stock]='Yes' THEN 1 ELSE 0 END)"},
        {"fieldCaption": "asOf", "calculation": "MAX([Last Sale Date])"},
    ]}


def pivot_query(stores, day):
    """Same query as pivotQuery() in the report."""
    def lit(x):
        return '"' + str(x).replace('"', '""') + '"'

    def part(st):
        w = f"[Store]={lit(st)}"
        return (f"IFNULL(MAX(IF {w} THEN (IF [Items in Stock]='Yes' THEN 'Y' ELSE 'N' END) END)"
                f"+','+IFNULL(STR(INT(ROUND(MAX(IF {w} THEN [Lifetime Qty Sold] END),0))),'0')"
                f"+','+IFNULL(STR(INT(ROUND(MAX(IF {w} THEN [Current Stock] END),0))),'0')"
                f"+','+IFNULL(STR(MIN(IF {w} THEN DATEDIFF('day',[First Sale Date],#{day}#) END)),''),'-')")
    return {
        "fields": [
            {"fieldCaption": "Supplier Account", "fieldAlias": "a"}, {"fieldCaption": "Supplier Name", "fieldAlias": "sn"},
            {"fieldCaption": "Item Code", "fieldAlias": "c"}, {"fieldCaption": "Category (Sheet1)", "fieldAlias": "k"},
            {"fieldCaption": "Sub-Category (Sheet1)", "fieldAlias": "u"}, {"fieldCaption": "Rank", "fieldAlias": "t"},
            {"fieldCaption": "n", "calculation": "MIN([Item Name])"},
            {"fieldCaption": "p", "calculation": "+'|'+".join(part(s) for s in stores)},
        ],
        "filters": [{"field": {"fieldCaption": "Supplier Account"}, "filterType": "QUANTITATIVE_NUMERICAL",
                     "quantitativeFilterType": "MIN", "min": 1}],
    }


def meta_info(meta_rows):
    day = max(str(r.get("asOf") or "")[:10] for r in meta_rows)
    stores = [r["Store"] for r in meta_rows if r.get("Store") and float(r.get("inS") or 0) > 0]
    dead = [r["Store"] for r in meta_rows if r.get("Store") and not float(r.get("inS") or 0) > 0]
    return day, stores, dead


def as_of_from_day(day):
    """Newest sale date = the stock day: today -> now, an older day -> that day's close (Kuwait)."""
    import datetime as dt
    kuwait = dt.timezone(dt.timedelta(hours=3))
    now = dt.datetime.now(kuwait)
    if now.strftime("%Y-%m-%d") == day:
        return now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    close = dt.datetime.fromisoformat(day + "T23:59:00").replace(tzinfo=kuwait)
    return close.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rows_of(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["data"] if isinstance(data, dict) else data


def main():
    if sys.argv[1:2] == ["--meta-query"]:
        print(json.dumps({"datasourceLuid": LUID, "query": meta_query()}, indent=1))
        return
    if sys.argv[1:2] == ["--pivot-query"]:
        day, stores, _ = meta_info(rows_of(sys.argv[2]))
        print(json.dumps({"datasourceLuid": LUID, "query": pivot_query(stores, day)}, indent=1))
        return
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("result", help="JSON result of the pivot query, or of tools/tableau-query.json")
    p.add_argument("--meta", help="JSON result of the meta query (current format, with sales)")
    p.add_argument("--as-of", help="Stock snapshot time, ISO 8601 (older format only)")
    p.add_argument("--source", default="Tableau Cloud · Supplier's Availability Data")
    p.add_argument("--template", default=str(TEMPLATE), help="Report HTML to copy")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="Where to write the filled-in report")
    args = p.parse_args()

    if args.meta:
        day, stores, dead = meta_info(rows_of(args.meta))
        keys = ["a", "sn", "c", "k", "u", "t", "n", "p"]
        rows = [[r.get(k) for k in keys] for r in rows_of(args.result)]
        snapshot = {"v": 2, "asOf": as_of_from_day(day), "source": args.source, "stores": stores,
                    "deadStores": dead, "rows": rows}
        summary = f"{len(rows):,} items, stores {', '.join(stores)}, stock day {day}"
    else:
        if not args.as_of:
            p.error("--as-of is required for the older format")
        snapshot = build(rows_of(args.result), args.as_of, args.source)
        summary = f"{len(snapshot['items']):,} items, {len(snapshot['sup'])} suppliers, {len(snapshot['cat'])} categories"
    payload = to_script_json(snapshot)

    html = Path(args.template).read_text(encoding="utf-8")
    if not SNAPSHOT_RE.search(html):
        raise SystemExit(f'No <script id="snapshot" type="application/json"> block in {args.template}')
    html = SNAPSHOT_RE.sub(lambda m: m.group(1) + payload + m.group(3), html, count=1)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    print(f"{summary} -> {out} ({len(payload) / 1024:,.0f} KB of data)", file=sys.stderr)


if __name__ == "__main__":
    main()
