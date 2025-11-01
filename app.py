from fastapi import FastAPI
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
CACHE_DURATION = timedelta(hours=1)

DATA_SOURCE_URL = "https://raw.githubusercontent.com/sportstimes/f1/main/_db/f1/2025.json"
BASE_URL = "https://whattimeisthef1.com"


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


@app.get("/api/next")
async def get_next_race():
    """
    API endpoint to get the next upcoming Formula 1 race.
    
    Returns:
        - {"status": "ok", "next": {...}} if a race is found
        - {"status": "season_over"} if no upcoming races
    """
    try:
        data = await get_race_data()
        races = data.get("races", [])
        now = datetime.now(timezone.utc)
        
        for race in races:
            sessions = race.get("sessions", {})
            
            # The race session is stored under the "gp" key
            start_time_str = sessions.get("gp")
            if not start_time_str:
                continue
            
            # Parse ISO format, handling both with and without 'Z'
            if start_time_str.endswith("Z"):
                start_time_str = start_time_str[:-1] + "+00:00"
            elif "+" not in start_time_str and "Z" not in start_time_str:
                start_time_str = start_time_str + "+00:00"
            
            try:
                start_time = datetime.fromisoformat(start_time_str)
            except ValueError:
                # Try parsing as UTC if ISO parse fails
                start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            
            if start_time > now:
                race_info = {
                    "name": race.get("name", "Unknown Race"),
                    "location": race.get("location", "Unknown Location"),
                    "country": race.get("country", ""),  # May not be present in all data
                    "startUtc": start_time.isoformat(),
                    "round": race.get("round"),
                    "url": race.get("url", ""),  # May not be present in all data
                }
                return {"status": "ok", "next": race_info}
        
        return {"status": "season_over"}
    
    except httpx.HTTPError as e:
        # Return cached data if available, even if expired
        if race_cache["data"] is not None:
            # Re-check cached data
            races = race_cache["data"].get("races", [])
            now = datetime.now(timezone.utc)
            
            for race in races:
                sessions = race.get("sessions", {})
                start_time_str = sessions.get("gp")
                if not start_time_str:
                    continue
                
                if start_time_str.endswith("Z"):
                    start_time_str = start_time_str[:-1] + "+00:00"
                elif "+" not in start_time_str:
                    start_time_str = start_time_str + "+00:00"
                
                try:
                    start_time = datetime.fromisoformat(start_time_str)
                except ValueError:
                    start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                
                if start_time > now:
                    race_info = {
                        "name": race.get("name", "Unknown Race"),
                        "location": race.get("location", "Unknown Location"),
                        "country": race.get("country", ""),
                        "startUtc": start_time.isoformat(),
                        "round": race.get("round"),
                        "url": race.get("url", ""),
                    }
                    return {"status": "ok", "next": race_info}
        
        return {"status": "season_over"}
    except Exception as e:
        # Log error and return season_over as fallback
        print(f"Error fetching race data: {e}")
        return {"status": "season_over"}


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

