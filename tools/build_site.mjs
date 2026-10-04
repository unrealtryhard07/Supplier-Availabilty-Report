#!/usr/bin/env node
// Build the hosted page: the report with no data inside, pointed at data.json.
//
//     node tools/build_site.mjs        # writes cloudflare/public/index.html
//
// Runs on every Cloudflare build (wrangler.jsonc → build.command). The page
// loads /data.json when it opens (served by worker/index.js from Cloudflare KV,
// behind Cloudflare Access) and checks for a newer one every 10 minutes;
// tools/refresh.py writes that data every hour.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'supplier-availability-report.html'), 'utf8');
const re = /<script id="snapshot" type="application\/json">[\s\S]*?<\/script>/;
if (!re.test(html)) throw new Error('No snapshot block in the report template');
const out = join(root, 'cloudflare', 'public', 'index.html');
mkdirSync(dirname(out), { recursive: true });
const page = html.replace(re, '<script id="snapshot" type="application/json" data-src="data.json">{}</script>');
writeFileSync(out, page);
console.log(`Wrote cloudflare/public/index.html (${Math.round(page.length / 1024)} KB, no data inside)`);
