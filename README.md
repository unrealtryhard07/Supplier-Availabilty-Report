# Supplier Availability Report

A daily availability report for each supplier, built to be sent as images,
with a priorities view of all suppliers for the team. Open
`supplier-availability-report.html` in Chrome or Edge (or the published copy in
Claude), pick a supplier, and export the pages as PNG files.

## All suppliers view

The report opens on **All suppliers**: suppliers with **Sales qty** (Lifetime
Qty Sold), **GMV** (Lifetime GMV, KWD), the cumulative contribution of each
(running total from the biggest down, with the row's own share under it), and
availability per store and in all stores.

- Choose **Top suppliers (90% of sales qty)**, **Top suppliers (90% of GMV)**
  or **All suppliers**. A top group is every supplier up to and including the
  one that takes the running total past 90%.
- Click any column header to sort (again to reverse). Click a supplier to open
  its report; "← All suppliers" brings you back to the same place.
- **Categories** below, with the same columns and sorting. Click a category for
  its sub-categories and a sub-category for its products (OUT per store).
  Cumulative contribution runs within each level; hover a row for its share of
  all sales qty and GMV.
- Filter by store or category. Four figures on top: availability, how many
  suppliers make 90% of sales qty and of GMV, and the critical and
  below-target supplier-store cells.
- **Excel** and **PDF** buttons on each table download it as it is on screen
  (scope, filters, sort). The categories Excel holds every category,
  sub-category and product; the categories PDF holds categories and
  sub-categories plus the products you have opened.
- The view uses the Circle look of Allocation Control: light page, white
  cards, magenta for what is selected.

## Deep analysis

The **Deep analysis** button (top bar, after Export images) opens one page that
combines today's stock and sales with the daily "Supplier Availability History"
source. It has the same supplier, store and category filters as the overview,
and every table downloads as Excel or PDF.

- **The story in numbers**: plain sentences worked out from the data.
- **Availability trend**: every day since 28 Sep 2026 (the days before are one
  backfilled copy and are left out). Each day's change is split in two:
  - *real change*: in-stock change on supplier/store/category cells whose
    listings did not change;
  - *range change*: the rest, i.e. listings removed or added.
  A bridge chart shows the same split from the first day to today.
- **Heat map**: availability per day by store, category or supplier.
- **Movers**: suppliers that gained or lost the most listings in stock, like
  for like, plus the biggest range changes.
- **Supplier reliability**: days on the target, real change, like-for-like
  swing, and a verdict (steady, improving, mixed, volatile, slipping, never on
  target).
- **Run-out radar**: listings in stock that run out within the 3-day delivery
  time, with a list of suppliers to call today.
  - Sells per day = GMV 90D ÷ the lifetime average price ÷ 90 (or the
    product's age, if younger).
  - Days of cover = current stock ÷ sells per day.
- **Ghost stock**: listings in stock with no sale for 30+ days (or never).
  They are ranked by lifetime GMV, so the shelves worth most are counted first.
- **Momentum vs availability**: suppliers plotted by availability and sales
  momentum (GMV per day over the last 90 days vs the lifetime average), sized by
  GMV 90D. Also shows Discount 90D ÷ GMV 90D.
- **Category scorecard** and **Concentration** (how many suppliers make 50, 80
  and 90% of sales qty and GMV).

When opened in Claude with the Tableau Cloud connector, the report reads
"Supplier's Availability Data" and "Supplier Availability History" live (Load data → Reload from Tableau to
refresh). Otherwise it shows the snapshot built into the copy.

## What a supplier receives

At most two images per supplier: page 1 is a complete summary, page 2 the
detail. Every export also includes the complete out-of-stock list as a CSV
file the supplier can open in Excel. (Settings can switch to all pages.)

- **Verdict band** in red (Critical), amber (Below target) or green
  (On target), with one plain sentence, e.g. *"120 of your 258 products are
  out of stock in at least one store."*
- **Overall availability**: the headline figure, with a bar against the target.
- **Six key figures** in plain words: products, products with gaps, products
  missing everywhere, weakest store, top sellers in stock, and rank.
- **Where you are losing**: categories as bars against the target, biggest
  sellers first.
- **Availability by store**: one card per store. Each square is one listing
  and red squares are empty shelves.
- **Availability by category and store**: the same grid as the old Excel report.
  Category and sub-category come from the Google Sheet. Cells are colored by
  status and show `% available` and `in stock / listed`.
- **Out-of-stock action list**: every SKU that is out somewhere. SKUs missing
  in every store come first, then the best sellers. `OUT` marks the
  exact stores to restock.

Pages are 1080 px wide (exported at 2160 px) and never taller than 1620 px, so
they stay readable on a phone. Large suppliers get extra pages, and table
headers repeat on every page.

## How the numbers work

- **Listing** = one SKU in one store. **Availability** = listings in stock ÷
  active listings. A listing is in stock when the store holds at least one unit.
- Items tiered **TD** or **TP/TS** in the Google Sheet are left out.
  Change this under Settings.
- **Stores with no stock anywhere are hidden automatically.** Qibla has
  listings but zero stock across the whole network, so it is not counted yet.
  It appears on its own once it starts holding stock.
- Suppliers are grouped by **Supplier Account**. Where the sheet spells one
  account two ways (e.g. `Co` and `CO.`), both share one report under the
  most used spelling.
- Percentages are rounded **down**, so 84.96% shows as 84.9% (amber), never
  as a green 85%.
- Status: On target 85% and above, Below target 80–84.99%, Critical under
  80%. Both lines are under Settings.

## Daily routine

1. In Tableau, open any unfiltered view built on **Supplier's Availability
   Data**, choose **Download → Data**, open the **Full data** tab with all
   fields shown, and download it as CSV. The fields used are Store, Item Code,
   Item Name, Items in Stock, Items in Book, Supplier Account, Supplier Name,
   Rank, Category (Sheet1) and Sub-Category (Sheet1). Or skip Tableau and load
   both source reports together: the SQL stock report plus the Google Sheet
   item master (CSV or Excel).
2. Open `supplier-availability-report.html`, click **Load data** and drop the
   file(s). Check the **Stock position** time; it is printed on every page.
3. The sidebar lists every supplier, worst first. Click one to preview it.
4. Click **Export images** for the supplier on screen. To do several at once,
   tick them in the sidebar and use **Export selected**, which saves one ZIP.
   Ticks are remembered for tomorrow.

Files are read inside the browser and never uploaded anywhere. The export
buttons load a small image library from the internet, so they need a
connection.

## Batch rendering (optional)

For automation, `tools/render-reports.js` drives the same page in headless
Chromium:

```sh
npm install && npx playwright install chromium
node tools/render-reports.js --csv tableau-export.csv --all
node tools/render-reports.js --csv stock.csv --csv item-master.csv --supplier "Dairy" --supplier 200123
```

Images go to `reports/<stock date>/`.

## Refreshing the built-in snapshot from Tableau

The report runs four VizQL Data Service queries. Two go to "Supplier's
Availability Data": the stores, then one row per supplier item with stock,
sales, GMV 90D, discount and last sale per store. Two go to "Supplier
Availability History": the days, then one row per supplier, store and category
with listings and in-stock for each day. To build a copy with them inside:

```sh
python3 tools/build_snapshot.py --meta-query                  # run it, save the result as meta.json
python3 tools/build_snapshot.py --pivot-query meta.json       # run it, save the result as pivot.json
python3 tools/build_snapshot.py --history-dates-query         # run it, save the result as hdates.json
python3 tools/build_snapshot.py --history-query hdates.json   # run it, save the result as history.json
python3 tools/build_snapshot.py --meta meta.json pivot.json --history hdates.json history.json
```

This writes `dist/supplier-availability-report.html` with the data inside,
so it opens ready to use with no file to load.

## Keep supplier data out of this repository

This repository is public. `supplier-availability-report.html` here holds no
data. `dist/` (the filled-in copy) and `reports/` (rendered images) are in
`.gitignore` because they contain every supplier's stock position. Never send
the filled-in HTML or its link to a supplier: it contains all suppliers. Send
the exported images.

## Tableau version

`tools/build_tableau_workbook.py` generates the same report as a Tableau
workbook on the published data source "Supplier's Availability Data": a
**Supplier Report** dashboard (the one-image summary) and a **Detail**
dashboard (category grid and full out-of-stock list), with a supplier picker.
Page 1 lists the 15 most urgent products; the Detail page has all of them.
To send a supplier their report, pick them in the Supplier box, then use
**Download → Image** (or PDF) on each dashboard.
It is published on Tableau Cloud as *Supplier Availability Report* in the
Commercial Department project. To rebuild it:

```sh
TABLEAU_SERVER=<pod>.online.tableau.com TABLEAU_SITE=<site> \
DEFAULT_SUPPLIER="<supplier to open on>" python3 tools/build_tableau_workbook.py
```

The output goes to `tableau/` (git-ignored) and is published with Tableau's
REST API or the Tableau MCP publish tool. Target %, critical % and delivery
days are workbook parameters.
