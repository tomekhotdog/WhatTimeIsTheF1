# Formula 1 Next Race Countdown

A production-ready web application that displays the next upcoming Formula 1 race with a live countdown timer. Built with FastAPI backend and a modern, dark-themed frontend.

## Features

- ✅ Real-time countdown to the next F1 race
- ✅ Automatic timezone conversion to user's local time
- ✅ Beautiful dark F1-style theme
- ✅ 1-hour in-memory cache for race data
- ✅ Responsive design for mobile and desktop
- ✅ Direct link to race weekend details

## Project Structure

```
.
├── app.py              # FastAPI backend application
├── requirements.txt    # Python dependencies
├── Procfile           # Railway deployment configuration
├── README.md          # This file
└── static/
    └── index.html     # Frontend HTML/CSS/JS
```

## How to Run Locally

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

### Setup Steps

1. **Clone or navigate to the project directory:**

   ```bash
   cd WhatTimeIsTheF1
   ```

2. **Create a virtual environment (recommended):**

   ```bash
   pyenv virtualenv 3.11.6 what-time-is-the-f1
   pyenv activate what-time-is-the-f1
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**

   ```bash
   uvicorn app:app --reload
   ```

   The `--reload` flag enables auto-reload on code changes (useful for development).

5. **Access the application:**

   Open your browser and navigate to:
   ```
   http://localhost:8000
   ```

   The API endpoint is available at:
   ```
   http://localhost:8000/api/next
   ```

## How to Deploy on Railway

Railway makes deploying from GitHub incredibly simple. This is the easiest method and is recommended for most users.

### Deploy from GitHub (Recommended)

1. **Push your code to GitHub:**

   If you haven't already, create a repository and push your code:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```

2. **Sign up/Login to Railway:**

   Go to [railway.app](https://railway.app) and sign up or log in. You can sign up with your GitHub account for easier integration.

3. **Create a new project:**

   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository (`WhatTimeIsTheF1`)

4. **Railway automatically configures everything:**

   - Railway detects the `Procfile` and uses it to run your app
   - It installs dependencies from `requirements.txt`
   - It sets up the `$PORT` environment variable automatically
   - No additional configuration needed!

5. **Your app is live:**

   Railway provides a URL (like `https://your-app-name.up.railway.app`) where your app is accessible. Every time you push to GitHub, Railway automatically redeploys your app.

### Alternative: Using Railway CLI

If you prefer using the command line:

1. Install Railway CLI: `npm install -g @railway/cli`
2. Login: `railway login`
3. Initialize: `railway init`
4. Deploy: `railway up`

See [Railway CLI Docs](https://docs.railway.app/develop/cli) for more details.

### Notes for Railway Deployment

- The `Procfile` tells Railway how to run your application using uvicorn
- Railway automatically assigns a `$PORT` environment variable - the Procfile uses this
- No Dockerfile is needed - Railway detects Python applications and uses the Procfile
- Make sure `requirements.txt` is in the root directory
- Railway automatically deploys on every Git push to your connected branch

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
   - Fetches race data from: `https://raw.githubusercontent.com/sportstimes/f1/main/_db/f1/2025.json`
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
   - Race data is cached in memory for 1 hour
   - This reduces external API calls and improves response times
   - Cache is automatically refreshed after 1 hour

5. **Error Handling:**
   - If the external API is unavailable, the endpoint tries to return cached data
   - Falls back to `{"status": "season_over"}` if no cached data is available

## Frontend Features

- **Live Countdown:** Updates every second showing days, hours, minutes, and seconds
- **Timezone Conversion:** Automatically converts UTC race time to user's local timezone using JavaScript's `Date` API
- **Dark Theme:** Modern F1-inspired dark design with red accents
- **Responsive:** Works seamlessly on desktop, tablet, and mobile devices
- **Race Details Button:** Red button linking to the official F1 race weekend details page

## Technologies Used

- **Backend:**
  - FastAPI - Modern, fast web framework for building APIs
  - Uvicorn - ASGI server for running FastAPI (installed via requirements.txt)
  - httpx - Async HTTP client for fetching external data

- **Frontend:**
  - Vanilla HTML/CSS/JavaScript - No frameworks needed
  - Modern CSS with gradients and animations
  - Responsive design with CSS Flexbox

## Troubleshooting

### Issue: "Module not found" errors

**Solution:** Make sure your virtual environment is activated and all dependencies are installed:
```bash
pip install -r requirements.txt
```

### Issue: Port already in use

**Solution:** Use a different port:
```bash
uvicorn app:app --port 8001
```

### Issue: Race data not updating

**Solution:** The cache refreshes after 1 hour. For testing, you can restart the server or temporarily reduce the `CACHE_DURATION` in `app.py`.

### Issue: "No upcoming races" when there should be one

**Solution:** 
- Check that the data source URL is accessible
- Verify the current date/time on your system
- Check the browser console for JavaScript errors

## License

This project is open source and available for personal and commercial use.

## Contributing

Feel free to fork this project and submit pull requests for improvements!

