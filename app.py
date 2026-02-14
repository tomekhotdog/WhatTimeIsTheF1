from fastapi import FastAPI, Query
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
import httpx
from pathlib import Path
from xml.etree import ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

app = FastAPI()

# Cache configuration
race_cache: Dict[str, Optional[object]] = {"data": None, "timestamp": None}
weather_cache: Dict[str, object] = {}  # key: "lat,lon", value: {"data": ..., "timestamp": ...}
CACHE_DURATION = timedelta(hours=1)

DATA_SOURCE_URL = "https://raw.githubusercontent.com/sportstimes/f1/main/_db/f1/2026.json"
BASE_URL = "https://whattimeisthef1.com"

# Session display names and estimated durations in minutes
SESSION_CONFIG = {
    "qualifying": {"label": "Qualifying", "duration_min": 60},
    "sprintQualifying": {"label": "Sprint Qualifying", "duration_min": 30},
    "sprint": {"label": "Sprint", "duration_min": 60},
    "gp": {"label": "Race", "duration_min": 120},
}

# Sessions to include, in chronological display order
SESSION_ORDER = ["sprintQualifying", "sprint", "qualifying", "gp"]


def get_latest_mtime() -> datetime:
    """Get the latest modification time from app.py and all files in static/."""
    latest = None
    files_to_check = [
        Path("app.py"),
        Path("static/index.html"),
    ]
    
    # Walk static directory recursively
    static_dir = Path("static")
    if static_dir.exists():
        for file_path in static_dir.rglob("*"):
            if file_path.is_file():
                files_to_check.append(file_path)
    
    for file_path in files_to_check:
        if file_path.exists():
            try:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
                if latest is None or mtime > latest:
                    latest = mtime
            except (OSError, ValueError):
                continue
    
    return latest if latest else datetime.now(timezone.utc)


def get_sitemap_entries() -> list[Dict[str, str]]:
    """Generate sitemap entries. Easy to extend with more URLs."""
    lastmod = get_latest_mtime()
    
    return [
        {
            "loc": f"{BASE_URL}/",
            "lastmod": lastmod,
            "changefreq": "daily",
            "priority": "1.0",
        }
    ]


def generate_sitemap_xml() -> str:
    """Generate XML sitemap from entries."""
    try:
        entries = get_sitemap_entries()
    except Exception as e:
        print(f"Error generating sitemap entries: {e}")
        # Fallback to minimal valid sitemap
        entries = [
            {
                "loc": f"{BASE_URL}/",
                "lastmod": datetime.now(timezone.utc),
                "changefreq": "daily",
                "priority": "1.0",
            }
        ]
    
    # Create XML structure
    urlset = ET.Element("urlset")
    urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")
    
    for entry in entries:
        url_elem = ET.SubElement(urlset, "url")
        ET.SubElement(url_elem, "loc").text = entry["loc"]
        # Format lastmod as YYYY-MM-DDTHH:MM:SSZ (no milliseconds)
        lastmod_str = entry["lastmod"].strftime("%Y-%m-%dT%H:%M:%SZ")
        ET.SubElement(url_elem, "lastmod").text = lastmod_str
        ET.SubElement(url_elem, "changefreq").text = entry["changefreq"]
        ET.SubElement(url_elem, "priority").text = entry["priority"]
    
    # Pretty print XML
    ET.indent(urlset, space="  ")
    xml_str = ET.tostring(urlset, encoding="utf-8", xml_declaration=True).decode("utf-8")
    return xml_str


async def fetch_race_data():
    """Fetch race data from the external API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(DATA_SOURCE_URL)
        response.raise_for_status()
        return response.json()


async def get_race_data():
    """Get race data, using cache if valid, otherwise fetch fresh data."""
    now = datetime.now(timezone.utc)

    if race_cache["data"] is None or race_cache["timestamp"] is None:
        race_cache["data"] = await fetch_race_data()
        race_cache["timestamp"] = now
    elif (now - race_cache["timestamp"]) > CACHE_DURATION:
        race_cache["data"] = await fetch_race_data()
        race_cache["timestamp"] = now

    return race_cache["data"]


def parse_race_time(start_time_str: str) -> Optional[datetime]:
    """Parse a race time string into a datetime, handling various formats."""
    if start_time_str.endswith("Z"):
        start_time_str = start_time_str[:-1] + "+00:00"
    elif "+" not in start_time_str and "Z" not in start_time_str:
        start_time_str = start_time_str + "+00:00"
    try:
        return datetime.fromisoformat(start_time_str)
    except ValueError:
        return None


def find_next_race(races: list, now: datetime) -> Optional[dict]:
    """Find the next upcoming race from a list of races.

    A race is 'next' if its GP session hasn't finished yet
    (start + duration is still in the future).
    """
    for race in races:
        raw_sessions = race.get("sessions", {})
        gp_time_str = raw_sessions.get("gp")
        if not gp_time_str:
            continue

        gp_time = parse_race_time(gp_time_str)
        if gp_time is None:
            continue

        gp_duration = timedelta(minutes=SESSION_CONFIG["gp"]["duration_min"])
        if gp_time + gp_duration < now:
            continue  # GP already finished

        # Build session list with statuses
        sessions = []
        for key in SESSION_ORDER:
            time_str = raw_sessions.get(key)
            if not time_str:
                continue
            session_time = parse_race_time(time_str)
            if session_time is None:
                continue
            duration = timedelta(minutes=SESSION_CONFIG[key]["duration_min"])
            end_time = session_time + duration

            if now >= session_time and now < end_time:
                status = "live"
            elif now >= end_time:
                status = "finished"
            else:
                status = "upcoming"

            sessions.append({
                "key": key,
                "label": SESSION_CONFIG[key]["label"],
                "startUtc": session_time.isoformat(),
                "durationMin": SESSION_CONFIG[key]["duration_min"],
                "status": status,
            })

        return {
            "name": race.get("name", "Unknown Race"),
            "location": race.get("location", "Unknown Location"),
            "country": race.get("country", ""),
            "latitude": race.get("latitude"),
            "longitude": race.get("longitude"),
            "startUtc": gp_time.isoformat(),
            "round": race.get("round"),
            "url": race.get("url", ""),
            "sessions": sessions,
        }
    return None


@app.get("/api/next")
async def get_next_race():
    """
    API endpoint to get the next upcoming Formula 1 race.
    Checks the current year first, then the next year if no races remain.
    """
    now = datetime.now(timezone.utc)

    try:
        data = await get_race_data()
    except Exception as e:
        print(f"Error fetching race data: {e}")
        # Try cached data
        if race_cache["data"] is not None:
            data = race_cache["data"]
        else:
            return {"status": "season_over"}

    race_info = find_next_race(data.get("races", []), now)
    if race_info:
        return {"status": "ok", "next": race_info}

    return {"status": "season_over"}


@app.get("/api/weather")
async def get_weather(lat: float = Query(...), lon: float = Query(...)):
    """Fetch weather forecast from Open-Meteo for given coordinates. Cached 1 hour."""
    cache_key = f"{lat:.4f},{lon:.4f}"
    now = datetime.now(timezone.utc)

    if cache_key in weather_cache:
        entry = weather_cache[cache_key]
        if (now - entry["timestamp"]) < CACHE_DURATION:
            return entry["data"]

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weathercode"
        f"&timezone=UTC"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        daily = data.get("daily", {})
        days = []
        dates = daily.get("time", [])
        for i, date in enumerate(dates):
            days.append({
                "date": date,
                "tempMax": daily["temperature_2m_max"][i],
                "tempMin": daily["temperature_2m_min"][i],
                "precipProb": daily["precipitation_probability_max"][i],
                "weatherCode": daily["weathercode"][i],
            })

        result = {"status": "ok", "daily": days}
        weather_cache[cache_key] = {"data": result, "timestamp": now}
        return result
    except Exception as e:
        print(f"Weather API error: {e}")
        return {"status": "error", "message": "Could not fetch weather data"}


@app.get("/sitemap.xml")
async def sitemap():
    """Generate and return the sitemap.xml."""
    xml_content = generate_sitemap_xml()
    return Response(
        content=xml_content,
        media_type="application/xml; charset=utf-8",
        headers={
            "Cache-Control": "public, max-age=3600",
        }
    )


@app.get("/robots.txt")
async def robots():
    """Return robots.txt content."""
    content = f"""User-agent: *
Allow: /
Sitemap: {BASE_URL}/sitemap.xml
"""
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "public, max-age=3600",
        }
    )

@app.get("/og-image.png")
def og_image():
    return FileResponse("static/og-image.png", media_type="image/png")

# Mount static files at root, with HTML fallback (must be after API routes)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

