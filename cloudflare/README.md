# Hosting the report for everyone (free, refreshed hourly)

This runs the report as a Cloudflare Worker behind a company login. The data is
refreshed **every hour from 08:00 to 20:00 Kuwait time**.

```
GitHub Actions, hourly 08:07–20:07 Kuwait
  └─ tools/refresh.py ── reads Tableau (Personal Access Token)
       └─ uploads data.json to Cloudflare KV
Cloudflare Worker "supplier-availabilty-report", built from GitHub on every push (wrangler.jsonc)
  https://supplier-availabilty-report.<account>.workers.dev, behind Cloudflare Access
  ├─ the page: static assets built by tools/build_site.mjs, no data inside
  └─ /data.json: worker/index.js reads it from KV, only for signed-in people
```

The page loads `data.json` when it opens. While it stays open it checks for new
data every 10 minutes and when you come back to the tab. The pill at the top
shows when the data was last updated. It turns amber if an hourly update is
missing during the day.

**Cost.** Everything below fits the free plans:

- GitHub Actions minutes are free for public repositories.
- Workers free plan: 100,000 requests a day. Static pages don't count.
- Cloudflare KV free plan: 1,000 writes a day; this uses 13.
- Cloudflare Access is free for up to 50 users.

**Safety.** The repository is public, so:

- No data is committed.
- The workflow logs show counts only.
- Tokens live in GitHub encrypted secrets.
- `/data.json` refuses any request that did not come through Cloudflare Access,
  even before Access is set up.

## Setup

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
   hourly in Tableau (Data source → Extract refreshes).

Tokens expire after a period of no use or after a maximum lifetime your admin
sets. When one expires, the refresh fails and the pill turns amber. Create a
new token and replace the two secrets.

### 2. Cloudflare

1. **Worker (done).** It was created from this GitHub repository and is named
   `supplier-availabilty-report`. It builds on every push. `wrangler.jsonc` in
   the repository tells it what to build. Keep the dashboard build settings at
   their defaults: no build command, deploy command `npx wrangler deploy`.
2. **Storage & Databases → KV → Create namespace**, named
   `supplier-report-data`. Copy its **ID** into `wrangler.jsonc`:

   ```jsonc
   "kv_namespaces": [
     { "binding": "SAR_DATA", "id": "<the ID>" }
   ],
   ```

   The ID is not a secret: it is useless without an API token. Bindings must be
   in this file, because every deploy replaces bindings set in the dashboard.
3. Copy your **Account ID** from the Workers & Pages overview (right-hand side).
4. **My Profile → API Tokens → Create Token → Custom token**:
   - Permission: *Account · Workers KV Storage · Edit*.
   - Account resources: your account.
   - Copy the token. It can only write the data, nothing else.
5. **Company login.**
   1. Open the Worker → **Settings → Domains & Routes**.
   2. Next to `workers.dev`, choose **Enable Cloudflare Access**. Do the same for
      **Preview URLs**.
   3. Open **Manage Cloudflare Access**. Set the policy to *Allow* → *Emails
      ending in* `@yourcompany.com`, or list the people. Use the **One-time
      PIN** login method.
   4. Copy the application's **Audience (AUD) tag**.

   Cloudflare may ask you to pick a Zero Trust team name and the Free plan the
   first time.
6. In the Worker open **Settings → Variables and Secrets** and add:
   - `ACCESS_TEAM_DOMAIN` = `yourteam.cloudflareaccess.com`
   - `ACCESS_AUD` = the AUD tag

   With these, `/data.json` also checks each login token's signature, audience
   and expiry. `keep_vars` in `wrangler.jsonc` stops deploys from removing them.

### 3. GitHub

In the repository open **Settings → Secrets and variables → Actions**.

| Kind | Name | Value |
|---|---|---|
| Secret | `TABLEAU_PAT_NAME` | token name from step 1 |
| Secret | `TABLEAU_PAT_SECRET` | token secret from step 1 |
| Secret | `CLOUDFLARE_API_TOKEN` | KV token from step 2.4 |
| Variable | `TABLEAU_SERVER` | e.g. `https://prod-xx.online.tableau.com` |
| Variable | `TABLEAU_SITE` | your site name |
| Variable | `CLOUDFLARE_ACCOUNT_ID` | from step 2.3 |
| Variable | `CF_KV_NAMESPACE_ID` | from step 2.2 |

Scheduled workflows only run from the default branch, so this work must be on
`main`.

### 4. First run

1. Merge into `main`. Cloudflare builds and deploys the Worker; watch it under
   the Worker's **Deployments** or **Builds**.
2. **Actions → Refresh report data → Run workflow.** This loads the first data.
3. Open the `workers.dev` address, sign in with your company email, and the
   report appears.

After that, everything is automatic:

- The data refreshes every hour from 08:07 to 20:07 Kuwait time.
- The page redeploys whenever something is pushed to `main`.

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
| "SAR_DATA KV binding is missing" | No KV ID in `wrangler.jsonc` | Step 2.2, then push |
| Cloudflare build fails | Build settings changed in the dashboard | Clear the build command; keep the deploy command `npx wrangler deploy` |
