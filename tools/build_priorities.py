#!/usr/bin/env python3
"""Build dist/availability-priorities.html with a saved Tableau snapshot inside.

The page reads Tableau live when it is opened in Claude with the Tableau Cloud
connector. The snapshot built here is what it shows before that read finishes,
or when live access is not available.

It runs two VizQL Data Service queries against "Supplier's Availability Data",
the same ones the page runs (see metaQuery/pivotQuery in the HTML):

    python3 tools/build_priorities.py --meta-query          # query 1, prints JSON
    python3 tools/build_priorities.py --pivot-query meta.json  # query 2, needs query 1's result
    python3 tools/build_priorities.py meta.json pivot.json  # writes dist/availability-priorities.html

The output holds every supplier's stock and sales: dist/ is git-ignored, keep it
out of the repository.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "availability-priorities.html"
OUT = ROOT / "dist" / "availability-priorities.html"
LUID = "a7ab1f36-6a15-4c2c-8e7a-4ea0f74a1320"


def meta_query():
    return {"fields": [
        {"fieldCaption": "Store"},
        {"fieldCaption": "inS", "calculation": "SUM(IF [Items in Stock]='Yes' THEN 1 ELSE 0 END)"},
        {"fieldCaption": "asOf", "calculation": "MAX([Last Sale Date])"},
    ]}


def lit(s):
    return '"' + str(s).replace('"', '""') + '"'


def pivot_query(stores, as_of):
    def part(s):
        w = f"[Store]={lit(s)}"
        return (f"IFNULL(MAX(IF {w} THEN (IF [Items in Stock]='Yes' THEN 'Y' ELSE 'N' END) END)"
                f"+','+IFNULL(STR(INT(ROUND(MAX(IF {w} THEN [Lifetime Qty Sold] END),0))),'0')"
                f"+','+IFNULL(STR(INT(ROUND(MAX(IF {w} THEN [Current Stock] END),0))),'0')"
                f"+','+IFNULL(STR(MIN(IF {w} THEN DATEDIFF('day',[First Sale Date],#{as_of}#) END)),''),'-')")
    return {
        "fields": [
            {"fieldCaption": "Supplier Account", "fieldAlias": "a"},
            {"fieldCaption": "Supplier Name", "fieldAlias": "sn"},
            {"fieldCaption": "Item Code", "fieldAlias": "c"},
            {"fieldCaption": "Category (Sheet1)", "fieldAlias": "k"},
            {"fieldCaption": "Sub-Category (Sheet1)", "fieldAlias": "u"},
            {"fieldCaption": "Rank", "fieldAlias": "t"},
            {"fieldCaption": "n", "calculation": "MIN([Item Name])"},
            {"fieldCaption": "p", "calculation": "+'|'+".join(part(s) for s in stores)},
        ],
        "filters": [{"field": {"fieldCaption": "Supplier Account"}, "filterType": "QUANTITATIVE_NUMERICAL",
                     "quantitativeFilterType": "MIN", "min": 1}],
    }


def rows_of(path):
    data = json.loads(Path(path).read_text())
    return data["data"] if isinstance(data, dict) else data


def meta_info(meta_rows):
    as_of = max(str(r.get("asOf") or "")[:10] for r in meta_rows)
    stores = [r["Store"] for r in meta_rows if r.get("Store") and float(r.get("inS") or 0) > 0]
    return as_of, stores


def main(argv):
    if argv[:1] == ["--meta-query"]:
        print(json.dumps({"datasourceLuid": LUID, "query": meta_query()}, indent=1))
        return
    if argv[:1] == ["--pivot-query"]:
        as_of, stores = meta_info(rows_of(argv[1]))
        print(json.dumps({"datasourceLuid": LUID, "query": pivot_query(stores, as_of)}, indent=1))
        return
    if len(argv) != 2:
        sys.exit(__doc__)
    as_of, stores = meta_info(rows_of(argv[0]))
    keys = ["a", "sn", "c", "k", "u", "t", "n", "p"]
    rows = [[r.get(k) for k in keys] for r in rows_of(argv[1])]
    snap = {"asOf": as_of, "stores": stores, "rows": rows}
    blob = json.dumps(snap, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text()
    marker = '<script id="snapshot" type="application/json">null</script>'
    assert marker in html, "snapshot marker missing from the template"
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html.replace(marker, f'<script id="snapshot" type="application/json">{blob}</script>'))
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB): {len(rows)} rows, stores {', '.join(stores)}, as of {as_of}")


if __name__ == "__main__":
    main(sys.argv[1:])
