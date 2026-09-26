#!/usr/bin/env node
/*
  Render supplier availability report pages to PNG with headless Chromium.

  One-time setup:   npm install && npx playwright install chromium

  node tools/render-reports.js --supplier "Dairy"               suppliers matching a name, dist/ snapshot
  node tools/render-reports.js --supplier 200123 --supplier "Foods"
  node tools/render-reports.js --all --csv tableau-export.csv    every supplier from today's export
  node tools/render-reports.js --csv stock.csv --csv item-master.csv --supplier "Trading"

  Options
    --csv <file>       Tableau export, or the SQL stock report plus the Google Sheet
                       item master (repeat the flag). Omit to use the snapshot built
                       into dist/supplier-availability-report.html.
    --html <file>      Report file to drive (default: dist/ copy if present).
    --as-of <iso>      Stock position printed on the reports (default: newest file time).
    --supplier <text>  Supplier name fragment or account number. Repeatable.
    --all              Every supplier with active listings.
    --out <dir>        Output folder (default: reports/<stock date>).
    --scale <n>        Pixel density, default 2 (2160 px wide images).
*/
'use strict';
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const { execSync } = require('child_process');

function loadPlaywright() {
  try { return require('playwright'); } catch { /* fall through to a global install */ }
  const globalRoot = execSync('npm root -g').toString().trim();
  return require(path.join(globalRoot, 'playwright'));
}

function parseArgs(argv) {
  const opts = { csv: [], supplier: [], all: false, out: null, scale: 2, asOf: null, html: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => { if (i + 1 >= argv.length) throw new Error(`${a} needs a value`); return argv[++i]; };
    if (a === '--csv') opts.csv.push(next());
    else if (a === '--supplier') opts.supplier.push(next());
    else if (a === '--all') opts.all = true;
    else if (a === '--out') opts.out = next();
    else if (a === '--scale') opts.scale = Number(next()) || 2;
    else if (a === '--as-of') opts.asOf = next();
    else if (a === '--html') opts.html = next();
    else if (a === '--help' || a === '-h') { console.log(fs.readFileSync(__filename, 'utf8').split('*/')[0]); process.exit(0); }
    else throw new Error(`Unknown option ${a}`);
  }
  if (!opts.all && !opts.supplier.length) throw new Error('Pass --supplier <name or account> (repeatable) or --all.');
  return opts;
}

const safeName = (s) => String(s).replace(/[\\/:*?"<>|]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 90);

(async () => {
  const opts = parseArgs(process.argv.slice(2));
  const { chromium } = loadPlaywright();
  const root = path.resolve(__dirname, '..');
  const built = path.join(root, 'dist', 'supplier-availability-report.html');
  const html = path.resolve(opts.html || (fs.existsSync(built) ? built : path.join(root, 'supplier-availability-report.html')));
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 1400, height: 1000 }, deviceScaleFactor: opts.scale });
    // The export and Excel libraries are only needed in the browser UI.
    await page.route(/cdn\.jsdelivr\.net|cdnjs\.cloudflare\.com/, (route) => route.abort());
    page.on('pageerror', (err) => console.error('Page error:', err.message));
    await page.goto(pathToFileURL(html).href);
    await page.evaluate(() => window.SAR.ready);

    if (opts.csv.length) {
      const files = opts.csv.map((f) => ({
        name: path.basename(f),
        base64: fs.readFileSync(f).toString('base64'),
        lastModified: fs.statSync(f).mtimeMs,
      }));
      const res = await page.evaluate(({ files, asOf }) => window.SAR.loadFileContents(files, asOf), { files, asOf: opts.asOf });
      console.log(`Loaded ${res.listings} listings for ${res.suppliers} suppliers.`);
      res.warnings.forEach((w) => console.log(`  note: ${w}`));
    }

    await page.evaluate(() => window.SAR.capture(true));
    const meta = await page.evaluate(() => window.SAR.meta());
    const all = await page.evaluate(() => window.SAR.suppliers());
    let chosen = all;
    if (!opts.all) {
      chosen = [];
      for (const q of opts.supplier) {
        const ql = q.toLowerCase();
        const hits = all.filter((s) => s.acct === q || s.name.toLowerCase().includes(ql));
        if (!hits.length) console.warn(`No supplier matches "${q}".`);
        hits.forEach((s) => { if (!chosen.includes(s)) chosen.push(s); });
      }
    }
    if (!all.length) throw new Error(`${path.basename(html)} has no data. Pass --csv with today's export.`);
    if (!chosen.length) throw new Error('Nothing to render.');

    const outDir = path.resolve(opts.out || path.join('reports', meta.ymd || 'report'));
    fs.mkdirSync(outDir, { recursive: true });
    let images = 0;
    for (const s of chosen) {
      const n = await page.evaluate((acct) => window.SAR.render(acct), s.acct);
      const pages = await page.$$('#pages .page');
      for (let i = 0; i < pages.length; i++) {
        const suffix = n > 1 ? ` - page ${i + 1} of ${n}` : '';
        const file = path.join(outDir, `${meta.ymd} ${safeName(s.name)}${suffix}.png`);
        await pages[i].screenshot({ path: file });
        images++;
      }
      console.log(`${(s.pct * 100).toFixed(1).padStart(5)}%  ${s.name}  (${n} ${n === 1 ? 'page' : 'pages'})`);
    }
    console.log(`\n${images} images in ${outDir}`);
  } finally {
    await browser.close();
  }
})().catch((err) => { console.error(err.message || err); process.exit(1); });
