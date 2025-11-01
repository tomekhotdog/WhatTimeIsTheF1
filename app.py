from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import httpx
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

app = FastAPI()

# Cache configuration
race_cache: Dict[str, Optional[object]] = {"data": None, "timestamp": None}
CACHE_DURATION = timedelta(hours=1)

DATA_SOURCE_URL = "https://raw.githubusercontent.com/sportstimes/f1/main/_db/f1/2025.json"


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


# Mount static files at root, with HTML fallback (must be after API routes)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

