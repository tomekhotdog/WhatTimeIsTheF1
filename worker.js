// Cloudflare Worker: handles /api/* and falls through to static assets for everything else.

const DATA_SOURCE_URL = "https://raw.githubusercontent.com/sportstimes/f1/main/_db/f1/2026.json";
const CACHE_TTL_SECONDS = 3600;

// Session display names and estimated durations in minutes
const SESSION_CONFIG = {
  qualifying: { label: "Qualifying", durationMin: 60 },
  sprintQualifying: { label: "Sprint Qualifying", durationMin: 30 },
  sprint: { label: "Sprint", durationMin: 60 },
  gp: { label: "Race", durationMin: 120 },
};

// Sessions to include, in chronological display order
const SESSION_ORDER = ["sprintQualifying", "sprint", "qualifying", "gp"];

// Last successful race data in this isolate, used if the data source is down
let lastRaceData = null;

/** Fetch JSON through Cloudflare's cache, kept for an hour. */
async function fetchCachedJson(url) {
  const response = await fetch(url, {
    cf: { cacheTtl: CACHE_TTL_SECONDS, cacheEverything: true },
  });
  if (!response.ok) {
    throw new Error(`${url} returned ${response.status}`);
  }
  return response.json();
}

/** Parse a race time string into a Date, treating times without an offset as UTC. */
function parseRaceTime(value) {
  const hasOffset = value.endsWith("Z") || /[+-]\d{2}:?\d{2}$/.test(value);
  const date = new Date(hasOffset ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * Find the next upcoming race from a list of races.
 *
 * A race is 'next' if its GP session hasn't finished yet
 * (start + duration is still in the future).
 */
function findNextRace(races, now) {
  const nowMs = now.getTime();
  for (const race of races) {
    const rawSessions = race.sessions || {};
    if (!rawSessions.gp) continue;

    const gpTime = parseRaceTime(rawSessions.gp);
    if (gpTime === null) continue;

    const gpEnd = gpTime.getTime() + SESSION_CONFIG.gp.durationMin * 60000;
    if (gpEnd < nowMs) continue; // GP already finished

    // Build session list with statuses
    const sessions = [];
    for (const key of SESSION_ORDER) {
      if (!rawSessions[key]) continue;
      const sessionTime = parseRaceTime(rawSessions[key]);
      if (sessionTime === null) continue;

      const { label, durationMin } = SESSION_CONFIG[key];
      const start = sessionTime.getTime();
      const end = start + durationMin * 60000;

      let status;
      if (nowMs >= start && nowMs < end) {
        status = "live";
      } else if (nowMs >= end) {
        status = "finished";
      } else {
        status = "upcoming";
      }

      sessions.push({ key, label, startUtc: sessionTime.toISOString(), durationMin, status });
    }

    return {
      name: race.name || "Unknown Race",
      location: race.location || "Unknown Location",
      country: race.country || "",
      latitude: race.latitude ?? null,
      longitude: race.longitude ?? null,
      startUtc: gpTime.toISOString(),
      round: race.round ?? null,
      url: race.url || "",
      sessions,
    };
  }
  return null;
}

async function handleNext() {
  let data;
  try {
    data = await fetchCachedJson(DATA_SOURCE_URL);
    lastRaceData = data;
  } catch (e) {
    console.error(`Error fetching race data: ${e}`);
    if (lastRaceData === null) {
      return Response.json({ status: "season_over" });
    }
    data = lastRaceData;
  }

  const raceInfo = findNextRace(data.races || [], new Date());
  if (raceInfo) {
    return Response.json({ status: "ok", next: raceInfo });
  }
  return Response.json({ status: "season_over" });
}

/** Fetch weather forecast from Open-Meteo for given coordinates. Cached 1 hour. */
async function handleWeather(url) {
  const lat = Number.parseFloat(url.searchParams.get("lat"));
  const lon = Number.parseFloat(url.searchParams.get("lon"));
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    return Response.json({ status: "error", message: "lat and lon are required numbers" }, { status: 422 });
  }

  const forecastUrl =
    "https://api.open-meteo.com/v1/forecast" +
    `?latitude=${lat}&longitude=${lon}` +
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weathercode" +
    "&timezone=UTC";

  try {
    const data = await fetchCachedJson(forecastUrl);
    const daily = data.daily || {};
    const days = (daily.time || []).map((date, i) => ({
      date,
      tempMax: daily.temperature_2m_max[i],
      tempMin: daily.temperature_2m_min[i],
      precipProb: daily.precipitation_probability_max[i],
      weatherCode: daily.weathercode[i],
    }));
    return Response.json({ status: "ok", daily: days });
  } catch (e) {
    console.error(`Weather API error: ${e}`);
    return Response.json({ status: "error", message: "Could not fetch weather data" });
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/api/next") return handleNext();
    if (url.pathname === "/api/weather") return handleWeather(url);

    return env.ASSETS.fetch(request);
  },
};
