# Move hosting from Railway to Cloudflare

**Goal:** serve whattimeisthef1.com from a Cloudflare Worker (free plan) instead of the FastAPI app on Railway, with no visible change to the site.

**Why a Worker rewrite:** `app.py` is not a static site. It runs `/api/next` (F1 calendar from GitHub, cached 1h, next race + session statuses), `/api/weather` (Open-Meteo, cached 1h), and generates `/sitemap.xml` and `/robots.txt`. Cloudflare serves `static/` directly; a small JavaScript Worker handles only `/api/*`.

Approaches considered and not chosen:
- **Python Workers:** FastAPI/httpx support is still rough; a JS port of about 150 lines is simpler.
- **Pages + Functions:** works, but Cloudflare now recommends Workers with static assets for new projects.

## Cost

Free, as long as traffic stays within these limits (check https://developers.cloudflare.com/workers/platform/pricing/ before committing):

| Part | Cost |
|---|---|
| DNS | Free plan |
| Static files (`static/`) | Free, unlimited, don't count as Worker requests |
| Worker (`/api/*`) | Free up to 100,000 requests/day (about 50k+ page views); 10ms CPU per request, and time waiting on network calls doesn't count |
| Custom domain and SSL | Free |
| Workers Builds (deploy from GitHub) | Free tier includes a monthly allowance of build minutes |
| Domain registration | Unchanged: yearly renewal at your current registrar |

If you go over the free limit, API requests return errors until the daily reset; you are never billed automatically. The paid plan is $5/month.

## Current setup (checked with `dig`, 2026-10-25)

- Registrar and DNS: **Namecheap** (nameservers `dns1/dns2.registrar-servers.com`). Railway only told you which record to add; the record itself lives in Namecheap.
- `whattimeisthef1.com`: CNAME to `k1o5l8jv.up.railway.app`
- `www.whattimeisthef1.com`: A `162.255.119.7`, which is Namecheap's URL-redirect server, so `www` is probably a Namecheap "URL Redirect" to the root domain
- No MX records, so no email on this domain to preserve

## Steps

### 1. Set up the tools
- [x] Run wrangler as `npx wrangler@4.149.0 ...` (pinned version, no `package.json`). A `package.json` in the repo could make Railway detect a Node app and break the live site before the switch. Can move to `npm i -D wrangler` after Railway is shut down.
- [x] `npx wrangler@4.149.0 login`

### 2. Rewrite the backend as a Worker
Done 2026-10-25. `/api/next` and `/api/weather` were compared against `app.py` running locally at the same moment: identical JSON (timestamps are now `...000Z` instead of `+00:00`, and the frontend parses both). Static routes and 404s match too. Until Railway is shut down, any API logic change has to go into both `app.py` and `worker.js`.
- [x] `worker.js`: port `/api/next` and `/api/weather` from `app.py`
  - Keep the same response shapes (`{status: "ok", next: {...}}`, `{status: "season_over"}`, `{status: "ok", daily: [...]}`) so `static/index.html` needs no changes
  - Keep `SESSION_CONFIG` / `SESSION_ORDER`, session durations and the live/finished/upcoming logic as they are
  - Replace the in-memory caches with `fetch(url, { cf: { cacheTtl: 3600, cacheEverything: true } })`
  - Any other path falls through to the static files (`env.ASSETS.fetch(request)`)
- [x] `static/robots.txt`: plain file (same content as the current route)
- [x] `static/sitemap.xml`: plain file (single `/` entry; update `lastmod` by hand or drop it)
- [x] `wrangler.jsonc`:
  ```jsonc
  {
    "name": "whattimeisthef1",
    "main": "worker.js",
    "compatibility_date": "2026-10-01",
    "assets": { "directory": "./static", "binding": "ASSETS", "run_worker_first": ["/api/*"] }
  }
  ```
- [x] Update `README.md` (local dev and deploy instructions)

### 3. Test locally
- [x] `npx wrangler@4.149.0 dev` and open the local URL
- [ ] Countdown, session list, live state, weather and calendar links all work
- [x] `/api/next`, `/api/weather?lat=..&lon=..`, `/robots.txt`, `/sitemap.xml`, `/og-image.png`, `/favicon.svg` respond correctly

### 4. Deploy to a test URL
- [x] `npx wrangler@4.149.0 deploy` gives `https://whattimeisthef1.tomek-szymaniec.workers.dev` (deployed 2026-10-25)
- [x] Repeat the step 3 checks there. Railway is still serving the real domain.

### 5. Move DNS from Namecheap to Cloudflare
The domain stays registered at Namecheap; only the DNS moves.
- [ ] (Skipped) Optional, a day ahead: Namecheap → Domain List → Manage → **Advanced DNS**, lower the TTL on the records to 5 min (speeds up the switch)
- [x] Cloudflare dashboard: **Add a domain**, enter `whattimeisthef1.com`, choose the **Free** plan
- [x] Review the imported DNS records. Keep the root CNAME to `k1o5l8jv.up.railway.app` for now so the site stays up. The Namecheap URL redirect for `www` won't carry over; step 6 replaces it.
- [x] Namecheap → Domain List → Manage → **Nameservers**: change "Namecheap BasicDNS" to **Custom DNS**, enter the two Cloudflare nameservers, save
- [x] Wait until Cloudflare shows the domain as **Active** (usually under an hour, up to 24h). Check with `dig +short NS whattimeisthef1.com`.

### 6. Point the domain at the Worker
Root domain switched 2026-10-25 and checked via Cloudflare's nameservers: served by the Worker, with no Railway headers. Wrangler turned off the `workers.dev` test URL once the custom domain was added (set `"workers_dev": true` to bring it back).
- [x] In Cloudflare DNS, delete the root (`whattimeisthef1.com`) CNAME to Railway (Cloudflare won't attach a custom domain while a conflicting record exists)
- [x] Add to `wrangler.jsonc`, then run `npx wrangler@4.149.0 deploy`:
  ```jsonc
  "routes": [
    { "pattern": "whattimeisthef1.com", "custom_domain": true }
  ]
  ```
- [x] Cloudflare creates the DNS record and the SSL certificate on its own. Expect a minute or two of downtime between deleting the record and the deploy.
- [x] Redirect `www` to the root domain, replacing the Namecheap redirect (the canonical URL in `index.html` is the root domain):
  - DNS: delete any imported `www` record, then add `AAAA` `www` → `100::`, **Proxied** (orange cloud). It's a placeholder so Cloudflare receives the traffic.
  - Rules → **Redirect Rules** → create from the template "Redirect from WWW to root" (301)
- [x] SSL/TLS → Edge Certificates → **Always Use HTTPS** on. Without it, `http://www` returned 522 (the template only matches `https://`) and `http://` on the root domain was served without redirecting to HTTPS. Railway used to do this redirect for us.

### 7. Check the live site and shut down Railway
- [x] `https://whattimeisthef1.com` and `https://www.whattimeisthef1.com` load over HTTPS
- [x] `/api/next`, `/sitemap.xml`, `/robots.txt`, `/og-image.png` respond correctly
- [ ] Social link preview still shows the OG image (e.g. paste the URL into a chat app)
- [x] Railway shut down early, 2026-10-25: removed the custom domain in Railway, then deleted the Railway project
- [x] Delete the files only the old setup used: `app.py`, `requirements.txt`, `Procfile`, `run.sh`

### 8. Optional: deploy on every push
- [x] Added `package.json` pinning `wrangler` 4.149.0 (safe now that Railway is gone), so Workers Builds and local dev use the same version
- [x] Commit and push the migration to `main` (858b288)
- [x] Dashboard → Workers & Pages → `whattimeisthef1` → Settings → Builds → **Connect** → GitHub → `tomekhotdog/WhatTimeIsTheF1`
  - Branch: `main`; Build command: empty; Deploy command: `npx wrangler deploy` (default); Root directory: `/`
- [ ] Push a small change and check it appears on the Worker's **Deployments** tab and on the live site
