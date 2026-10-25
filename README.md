# Formula 1 Next Race Countdown

A web application that displays the next upcoming Formula 1 race with a live countdown timer. Static frontend plus a small Cloudflare Worker for the API, served from [whattimeisthef1.com](https://whattimeisthef1.com).

## Features

- ✅ Real-time countdown to the next F1 race
- ✅ Automatic timezone conversion to user's local time
- ✅ Beautiful dark F1-style theme
- ✅ 1-hour cache for race and weather data
- ✅ Responsive design for mobile and desktop
- ✅ Direct link to race weekend details

## Project Structure

```
.
├── worker.js          # Cloudflare Worker: /api/next and /api/weather
├── wrangler.jsonc     # Cloudflare Worker configuration (incl. custom domain)
├── package.json       # Pins the wrangler version
├── static/            # Served as-is by Cloudflare
│   ├── index.html     # Frontend HTML/CSS/JS
│   ├── robots.txt
│   ├── sitemap.xml
│   ├── favicon.svg
│   └── og-image.png
└── README.md          # This file
```

## How to Run Locally

### Prerequisites

- Node.js 20 or higher

### Quick Start

```bash
npm install
npm run dev
```

This serves the site and the Worker with auto-reload at [http://localhost:8787](http://localhost:8787).

The API endpoint is available at [http://localhost:8787/api/next](http://localhost:8787/api/next).

## How to Deploy on Cloudflare

Every push to `main` deploys automatically through Cloudflare Workers Builds (connected to this GitHub repo in the Cloudflare dashboard: Worker → Settings → Builds). Build logs are on the Worker's **Deployments** tab.

To deploy by hand from your machine:

```bash
npx wrangler login    # once
npm run deploy
```

Static files in `static/` are served directly by Cloudflare. Only `/api/*` requests run the Worker (`run_worker_first` in `wrangler.jsonc`). Domain and DNS setup (done in the Cloudflare dashboard, not in this repo):

- The domain is registered at Namecheap, with its nameservers pointed at Cloudflare.
- `whattimeisthef1.com` is attached to the Worker as a custom domain (`routes` in `wrangler.jsonc`).
- `www` is a proxied `AAAA` placeholder record (`100::`), redirected to the root domain by a Redirect Rule ("Redirect from WWW to root" template).
- **Always Use HTTPS** is on (SSL/TLS → Edge Certificates). The `www` redirect only matches `https://`, so without it `http://www` fails with a 522.
- Backup address, in case the domain lapses: https://whattimeisthef1.tomek-szymaniec.workers.dev (`workers_dev` in `wrangler.jsonc`).

## How the API Works

### Endpoint: `GET /api/next`

Returns information about the next upcoming Formula 1 race.

#### Response Format

**Success Response (race found):**

```json
{
  "status": "ok",
  "next": {
    "name": "Bahrain Grand Prix",
    "location": "Sakhir",
    "country": "Bahrain",
    "startUtc": "2025-03-02T15:00:00+00:00",
    "round": 1,
    "url": "https://www.formula1.com/en/racing/2025/Bahrain.html"
  }
}
```

**Season Over Response:**

```json
{
  "status": "season_over"
}
```

#### How It Works

1. **Data Source:**
   - Fetches race data from: `https://raw.githubusercontent.com/sportstimes/f1/main/_db/f1/2026.json`
   - This is a community-maintained JSON file with Formula 1 schedule information

2. **Data Processing:**
   - Parses the JSON to extract all races from the `"races"` array
   - For each race, extracts the `"gp"` (Grand Prix) session time from the `"sessions"` object
   - Extracts the race start time (in UTC ISO format, e.g., `"2025-03-16T04:00:00Z"`)
   - Builds a simplified race object with: name, location, country (if available), startUtc, round, and url (if available)

3. **Next Race Selection:**
   - Compares each race's start time with the current UTC time
   - Returns the first race where `start_time > current_time`
   - If no future races are found, returns `{"status": "season_over"}`

4. **Caching:**
   - Race data is cached by Cloudflare for 1 hour (`cf.cacheTtl` on the fetch)
   - This reduces external API calls and improves response times
   - Cache is automatically refreshed after 1 hour

5. **Error Handling:**
   - If the external API is unavailable, the endpoint tries to return the last data it fetched
   - Falls back to `{"status": "season_over"}` if no cached data is available

## Frontend Features

- **Live Countdown:** Updates every second showing days, hours, minutes, and seconds
- **Timezone Conversion:** Automatically converts UTC race time to user's local timezone using JavaScript's `Date` API
- **Dark Theme:** Modern F1-inspired dark design with red accents
- **Responsive:** Works seamlessly on desktop, tablet, and mobile devices
- **Race Details Button:** Red button linking to the official F1 race weekend details page

## Technologies Used

- **Backend:**
  - Cloudflare Workers - runs `/api/*` and serves the static files
  - Wrangler - Cloudflare's CLI for local dev and deploys

- **Frontend:**
  - Vanilla HTML/CSS/JavaScript - No frameworks needed
  - Modern CSS with gradients and animations
  - Responsive design with CSS Flexbox

## Troubleshooting

### Issue: Port already in use

**Solution:** Use a different port:
```bash
npm run dev -- --port 8788
```

### Issue: Race data not updating

**Solution:** Cloudflare caches the data source for 1 hour. Locally, restart `wrangler dev`.

### Issue: "No upcoming races" when there should be one

**Solution:** 
- Check that the data source URL is accessible
- Verify the current date/time on your system
- Check the browser console for JavaScript errors
- Check Worker logs: `npx wrangler tail`

## License

This project is open source and available for personal and commercial use.

## Contributing

Feel free to fork this project and submit pull requests for improvements!

