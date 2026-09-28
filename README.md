# Supplier Availability Report

A daily availability report for each supplier, built to be sent as images.
Open `supplier-availability-report.html` in Chrome or Edge, load today's
stock, pick a supplier, and export the pages as PNG files.

## What a supplier receives

At most two images per supplier: page 1 is a complete summary, page 2 the
detail. Every export also includes the complete out-of-stock list as a CSV
file the supplier can open in Excel. (Settings can switch to all pages.)

- **Verdict band** in red (Critical), amber (Below target) or green
  (On target), with one plain sentence, e.g. *"84 of your 480 store listings
  are out of stock right now. Restock 60 listings to reach the 95% target."*
- **Overall availability**: the headline figure, with a bar against the target.
- **What we need from you**: a delivery deadline and your contact details
  (set once in Settings).
- **Six key figures** in plain words: products, products with gaps, products
  missing everywhere, empty shelves, top sellers in stock, and rank.
- **Where you are losing**: categories as bars against the target.
- **Restock these first**: the eight most urgent products, top sellers first.
- **Availability by store**: one card per store. Each square is one listing
  and red squares are empty shelves.
- **Availability by category and store**: the same grid as the old Excel report.
  Category and sub-category come from the Google Sheet. Cells are colored by
  status and show `% available` and `in stock / listed`.
- **Out-of-stock action list**: every SKU that is out somewhere. SKUs missing
  in every store come first, then best-selling tiers first. `OUT` marks the
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
- Percentages are rounded **down**, so 94.96% shows as 94.9% (amber), never
  as a green 95%.
- Defaults: target 95%, critical below 80% (your old red line). Both are
  under Settings.

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

`tools/tableau-query.json` is the VizQL Data Service query that pulls one row
per supplier item from the published data source. Save its JSON result, then:

```sh
python3 tools/build_snapshot.py result.json --as-of 2026-09-24T12:21:04Z
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

## Availability Priorities (internal operations page)

`availability-priorities.html` is the internal, action-oriented version for the
commercial team: which suppliers, stores, categories and items to fix first.
It is not for sending to suppliers (it shows every supplier).

- **Data**: reads the Tableau data source "Supplier's Availability Data" live
  through the viewer's Tableau Cloud connector when opened in Claude. A saved
  snapshot can be built in with `tools/build_priorities.py` (see its header);
  the built copy goes to `dist/`, which stays out of this repository.
- **Status**: Target ≥ 85%, Below target 80–84.99%, Critical ≤ 79.99%.
- **Sales importance**: average units per day = Lifetime Qty Sold ÷ days since
  first sale (at least 30). The source has no single-day sales column.
- **Priority**: lost sales per day = daily sales of listings that are out of
  stock now. Used to order the drilldown and the fix-first lists.
- **Sections**: summary tiles; supplier × store matrix (suppliers by sales,
  weighted Total column and row); every supplier ranked by sales with the
  suppliers that make the first 90% marked Focus; Category → Sub-category →
  Store → Item drilldown; stores by lost sales; empty shelves losing the most
  sales; supplier-store cells to escalate. Clicking a supplier, store or cell
  filters the whole page.
