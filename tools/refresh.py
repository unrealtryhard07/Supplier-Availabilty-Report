#!/usr/bin/env python3
"""Read Tableau and write the report's data file, for the hosted copy.

Runs the same four queries as the report (and build_snapshot.py) against
Tableau's VizQL Data Service with a Personal Access Token, then writes one
JSON file in the snapshot format the report reads (v2 + daily history).

    TABLEAU_SERVER=https://prod-xx.online.tableau.com \\
    TABLEAU_SITE=yoursite \\
    TABLEAU_PAT_NAME=... TABLEAU_PAT_SECRET=... \\
    python3 tools/refresh.py --out site/data.json

Offline check with saved query results (no Tableau needed):

    python3 tools/refresh.py --from-files meta.json pivot.json hdates.json history.json --out data.json

The output holds every supplier's stock and sales: it is never committed and
nothing about its contents is printed, because Actions logs of a public
repository are public.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_snapshot as bs  # noqa: E402

API_VERSION = os.environ.get("TABLEAU_API_VERSION", "3.22")


def _post(url, body, headers, timeout=180):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


class Tableau:
    def __init__(self, server, site, pat_name, pat_secret):
        self.server = server.rstrip("/")
        body = {"credentials": {"personalAccessTokenName": pat_name, "personalAccessTokenSecret": pat_secret,
                                "site": {"contentUrl": site}}}
        try:
            res = _post(f"{self.server}/api/{API_VERSION}/auth/signin", body, {})
        except urllib.error.HTTPError as e:
            raise SystemExit(f"Tableau sign-in failed (HTTP {e.code}). Check TABLEAU_SERVER, TABLEAU_SITE and the token.")
        self.token = res["credentials"]["token"]

    def query(self, luid, query, tries=3):
        url = f"{self.server}/api/v1/vizql-data-service/query-datasource"
        for attempt in range(tries):
            try:
                res = _post(url, {"datasource": {"datasourceLuid": luid}, "query": query}, {"X-Tableau-Auth": self.token})
                return res.get("data", [])
            except urllib.error.HTTPError as e:
                if e.code < 500 or attempt == tries - 1:
                    detail = e.read().decode(errors="replace")[:300]
                    raise SystemExit(f"Tableau query failed (HTTP {e.code}): {detail}")
            except urllib.error.URLError:
                if attempt == tries - 1:
                    raise
            time.sleep(5 * (attempt + 1))
        return []

    def close(self):
        try:
            req = urllib.request.Request(f"{self.server}/api/{API_VERSION}/auth/signout", method="POST",
                                         headers={"X-Tableau-Auth": self.token})
            urllib.request.urlopen(req, timeout=30).read()
        except Exception:  # signing out is best effort
            pass


def build(meta, pivot, hdates, history):
    day, stores, dead = bs.meta_info(meta)
    keys = ["a", "sn", "c", "k", "u", "t", "n", "p"]
    snap = {"v": 2, "asOf": bs.as_of_from_day(day), "source": "Tableau Cloud · Supplier’s Availability Data",
            "stores": stores, "deadStores": dead, "rows": [[r.get(k) for k in keys] for r in pivot]}
    days = bs.history_days(hdates) if hdates is not None else []
    if days and history:
        snap["hist"] = {"days": days, "rows": [[r.get(k) for k in ("s", "t", "k", "h")] for r in history]}
    snap["refreshedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return snap, day, days


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="site/data.json")
    p.add_argument("--from-files", nargs=4, metavar=("META", "PIVOT", "HDATES", "HISTORY"))
    args = p.parse_args()
    t0 = time.time()

    if args.from_files:
        meta, pivot, hdates, history = (bs.rows_of(f) for f in args.from_files)
    else:
        env = {k: os.environ.get(k, "") for k in ("TABLEAU_SERVER", "TABLEAU_SITE", "TABLEAU_PAT_NAME", "TABLEAU_PAT_SECRET")}
        missing = [k for k, v in env.items() if not v and k != "TABLEAU_SITE"]
        if missing:
            raise SystemExit("Missing settings: " + ", ".join(missing))
        tab = Tableau(env["TABLEAU_SERVER"], env["TABLEAU_SITE"], env["TABLEAU_PAT_NAME"], env["TABLEAU_PAT_SECRET"])
        try:
            meta = tab.query(bs.LUID, bs.meta_query())
            day, stores, _ = bs.meta_info(meta)
            if not stores:
                raise SystemExit("Tableau returned no store with stock; keeping the previous data.")
            pivot = tab.query(bs.LUID, bs.pivot_query(stores, day))
            # The history is a bonus: without it the report still works.
            try:
                hdates = tab.query(bs.HISTORY_LUID, bs.history_dates_query())
                hd = bs.history_days(hdates)
                history = tab.query(bs.HISTORY_LUID, bs.history_query(hd)) if hd else []
            except SystemExit as e:
                print(f"History not read: {e}", file=sys.stderr)
                hdates, history = None, []
        finally:
            tab.close()

    if len(pivot) < 100:
        raise SystemExit(f"Only {len(pivot)} rows came back; keeping the previous data.")
    snap, day, days = build(meta, pivot, hdates, history)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(bs.to_script_json(snap), encoding="utf-8")
    # Counts only: never names or figures.
    print(f"OK: {len(snap['rows']):,} items, {len(snap['stores'])} stores, stock day {day}, "
          f"history {len(days)} days, {out.stat().st_size / 1e6:.1f} MB, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
