# Hosting the report for everyone (free, refreshed hourly)

This sets the report up on Cloudflare Pages behind a company login. The data is
refreshed **every hour from 08:00 to 20:00 Kuwait time**.

```
GitHub Actions, hourly 08:07–20:07 Kuwait
  └─ tools/refresh.py ── reads Tableau (Personal Access Token)
       └─ uploads data.json to Cloudflare KV
Cloudflare Pages, built from this GitHub repository on every push to main
  https://<project>.pages.dev, behind Cloudflare Access (company email login)
  ├─ index.html: the report with no data inside (tools/build_site.py)
  └─ /data.json: served from KV by functions/data.json.js, only to signed-in people
```

The page loads `data.json` when it opens. While it stays open it checks for new
data every 10 minutes and when you come back to the tab. The pill at the top
shows when the data was last updated. It turns amber if an hourly update is
missing during the day.

**Cost.** Everything below fits the free plans:

- GitHub Actions minutes are free for public repositories.
- Cloudflare KV free plan: 1,000 writes a day; this uses 13.
- Cloudflare Access is free for up to 50 users.

**Safety.** The repository is public, so:

- No data is committed.
- The workflow logs show counts only.
- Tokens live in GitHub encrypted secrets.
- The data function refuses any request that did not come through Cloudflare
  Access, even before Access is set up.

## One-time setup (about 20 minutes)

### 1. Tableau

1. In Tableau Cloud open **My Account Settings → Personal Access Tokens**.
   Create a token named, for example, `supplier-report`. Copy the **name** and
   the **secret**.
   - Use an account that can query both data sources: "Supplier's Availability
     Data" and "Supplier Availability History".
2. Note your server and site from the browser address bar:
   `https://prod-xx.online.tableau.com/#/site/SITE/...`
   - Server = `https://prod-xx.online.tableau.com`
   - Site = `SITE`
3. For hourly data, the "Supplier's Availability Data" extract must also refresh
   hourly in Tableau (Data source → Extract refreshes). Otherwise every hourly
   run reads the same numbers.

Tokens expire after a period of no use or after a maximum lifetime your admin
sets. When one expires, the refresh fails and the pill turns amber. Create a
new token and replace the two secrets.

### 2. Cloudflare

1. **Workers & Pages → Create → Pages → Connect to Git.** Pick this repository
   and set:
   - Production branch: `main`
   - Framework preset: `None`
   - Build command: `python3 tools/build_site.py`
   - Build output directory: `cloudflare/public`
   - Root directory: leave empty (the repository root)

   Cloudflare then rebuilds the page on every push. The `functions/` folder at
   the root becomes the `/data.json` endpoint automatically. Pushes to other
   branches become preview deployments at `<branch>.<project>.pages.dev`.
2. **Storage & Databases → KV → Create namespace**, named
   `supplier-report-data`. Copy its **ID**.
3. In the Pages project open **Settings → Bindings → Add → KV namespace**.
   - Variable name `SAR_DATA`, namespace `supplier-report-data`.
   - Add it for Production (and Preview if you want previews to show data).
4. Copy your **Account ID** from the Workers & Pages overview (right-hand side).
5. **My Profile → API Tokens → Create Token → Custom token**:
   - Permission: *Account · Workers KV Storage · Edit*.
   - Account resources: your account.
   - Copy the token. It can only write the data, nothing else.
6. **Zero Trust** (pick a team name; choose the Free plan; Cloudflare may ask for
   a card to activate it).
   1. Go to **Access → Applications → Add an application → Self-hosted**.
   2. Domains: `<project>.pages.dev` **and** `*.<project>.pages.dev`. The second
      one covers preview deployments.
   3. Policy: **Allow**, Include → *Emails ending in* `@yourcompany.com`, or list
      the people.
   4. Login method: **One-time PIN**, a code sent by email.
   5. After saving, copy the application's **Audience (AUD) tag**.
7. Back in the Pages project, open **Settings → Variables and Secrets** and add
   (Production, and Preview too):
   - `ACCESS_TEAM_DOMAIN` = `yourteam.cloudflareaccess.com`
   - `ACCESS_AUD` = the AUD tag

   With these set, the function checks the signature of every login token, not
   just that one is there. Bindings and variables apply from the next
   deployment: use **Deployments → … → Retry deployment** once after adding them.

### 3. GitHub

In the repository open **Settings → Secrets and variables → Actions**.

| Kind | Name | Value |
|---|---|---|
| Secret | `TABLEAU_PAT_NAME` | token name from step 1 |
| Secret | `TABLEAU_PAT_SECRET` | token secret from step 1 |
| Secret | `CLOUDFLARE_API_TOKEN` | KV token from step 2.5 |
| Variable | `TABLEAU_SERVER` | e.g. `https://prod-xx.online.tableau.com` |
| Variable | `TABLEAU_SITE` | your site name |
| Variable | `CLOUDFLARE_ACCOUNT_ID` | from step 2.4 |
| Variable | `CF_KV_NAMESPACE_ID` | from step 2.2 |

Scheduled workflows only run from the default branch, so this work must be on
`main`. That also triggers the first Cloudflare build.

### 4. First run

1. Merge into `main`. Cloudflare builds and publishes the page; watch it under
   the project's **Deployments**.
2. **Actions → Refresh report data → Run workflow.** This loads the first data.
3. Open `https://<project>.pages.dev`, sign in with your company email, and the
   report appears.

After that, everything is automatic:

- The data refreshes every hour from 08:07 to 20:07 Kuwait time.
- The page rebuilds whenever something is pushed to `main`.

## Changing the schedule

Edit the `cron` line in `.github/workflows/refresh-data.yml`. Times are UTC;
Kuwait is UTC+3.

| Schedule | `cron` line |
|---|---|
| Every hour 08:00–20:00 Kuwait, every day (current) | `7 5-17 * * *` |
| The same, Sunday–Thursday only | `7 5-17 * * 0-4` |

GitHub may start scheduled runs a few minutes late at busy times.

## If something goes wrong

| What you see | Why | Fix |
|---|---|---|
| Amber pill: "hourly update has not arrived" | The refresh workflow failed | Open Actions → the failed run. "sign-in failed" means a token problem: renew the Tableau token. |
| "Sign in through Cloudflare Access" | Opened without logging in, or not on the allowed list | Add the person in the Access policy |
| "No data yet" | The refresh has never run | Run *Refresh report data* once |
| "SAR_DATA KV binding is missing" | Step 2.3 was skipped | Add the binding, then retry the latest deployment |
| The site shows Cloudflare’s 404 page | Wrong build settings | Build command `python3 tools/build_site.py`, output `cloudflare/public` (step 2.1) |
