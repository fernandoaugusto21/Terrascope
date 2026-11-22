"""Open-Meteo fetching and per-city weather cache."""

from __future__ import annotations

import json
import math
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Collection
from terrascope.core.config import CACHE_DIR, FETCH_NEW_DATA_FROM_API, USER_AGENT
from terrascope.core.i18n import _
from terrascope.core.ui import hex_to_rgb
from terrascope.layers.weather.config import (
    CITY_CONFIG,
    FORECAST_DAYS_AHEAD,
    MAX_CONCURRENT_WEATHER_REQUESTS,
    WEATHER_API_URL,
    WEATHER_CACHE_FILE,
    WEATHER_CODES,
    WEATHER_REFRESH_INTERVAL_SECONDS,
    WEATHER_RETRY_INTERVAL_SECONDS,
    WEATHER_SCHEMA,
    WEATHER_TIMEOUT_SECONDS,
    _CITY_TEXT,
    _COLOR_STEPS,
)

# ---------------------------------------------------------------------------
# Open-Meteo weather API
# ---------------------------------------------------------------------------

class WeatherFetchError(Exception):
    pass

def describe_weather_code(code) -> str:
    try:
        return WEATHER_CODES.get(int(code), _CITY_TEXT["unknown_weather"])
    except (TypeError, ValueError):
        return _CITY_TEXT["unknown_weather"]

def describe_conditions(code, summary=None) -> str:
    """A provider's own words for the conditions when it has them (e.g. a national
    weather service), otherwise the text of the WMO code."""
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    return describe_weather_code(code)

def _as_finite(value) -> float | None:
    # Feed values arrive as whatever JSON gave us. Coerce here so a
    # string never reaches min/max or :.0f formatting in the layer.
    # Explicit None keeps the callers honest about missing readings.
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None

def temperature_to_color(
    temperature: float | None, cold_c: float, hot_c: float
) -> str | None:
    """Map a Celsius reading onto the cold -> hot gradient in CITY_CONFIG,
    scaled between cold_c and hot_c (typically the coldest and hottest
    readings currently known across all cities -- see
    WeatherStationCache.temperature_range), so a city's marker/label
    reflects how hot or cold it is *relative to the other cities*, not a
    fixed absolute threshold.

    Returns None when the reading is missing or not a finite number, so
    callers can fall back to a neutral default color. The type check sits
    here rather than at each call site because entries loaded from older
    cache files can hold strings, and the range is built from the valid
    ones only, which leaves those legacy values to be colored on their own.
    """
    temp = _as_finite(temperature)
    if temp is None:
        return None
    temperature = temp
    span = hot_c - cold_c
    if span <= 0:
        # Only one distinct temperature known so far -- nothing to scale
        # against yet.
        fraction = 0.5
    else:
        fraction = (temperature - cold_c) / span
        fraction = max(0.0, min(1.0, fraction))
    fraction = round(fraction * _COLOR_STEPS) / _COLOR_STEPS
    cold_r, cold_g, cold_b = hex_to_rgb(CITY_CONFIG["temperature_cold_color"])
    hot_r, hot_g, hot_b = hex_to_rgb(CITY_CONFIG["temperature_hot_color"])
    red = round(cold_r + (hot_r - cold_r) * fraction)
    green = round(cold_g + (hot_g - cold_g) * fraction)
    blue = round(cold_b + (hot_b - cold_b) * fraction)
    return f"#{red:02x}{green:02x}{blue:02x}"

DAILY_FIELDS = (
    "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
    "precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,"
    "sunrise,sunset,uv_index_max"
)
HOURLY_FIELDS = "temperature_2m,weather_code,precipitation_probability,wind_speed_10m"
_WEATHER_CACHE_WRITE_LOCK = threading.Lock()
# How long another weather layer's saved reading of a city is kept from being
# written over (see WeatherStationCache._may_replace).
SOVEREIGN_HOLD_SECONDS = 24 * 3600

def fetch_weather_snapshot(latitude: float, longitude: float) -> dict:
    """Fetch Open-Meteo's current conditions plus a multi-day forecast.

    Returns {"current": {...}, "daily": {...}, "hourly": {...}}. Current
    conditions use Open-Meteo's current object and are normalized to the field
    names consumed by the renderer. "daily" and "hourly" are arrays-of-values
    blocks covering today plus the next FORECAST_DAYS_AHEAD days (parse_forecast
    below turns them into per-day dicts).
    """
    query = (
        f"{WEATHER_API_URL}?latitude={latitude:.4f}&longitude={longitude:.4f}"
        "&current=temperature_2m,wind_speed_10m,wind_direction_10m,weather_code&timezone=auto"
        f"&daily={DAILY_FIELDS}&hourly={HOURLY_FIELDS}"
        f"&forecast_days={FORECAST_DAYS_AHEAD + 1}"
    )
    request = urllib.request.Request(
        query, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=WEATHER_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read())
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
    ) as error:
        raise WeatherFetchError(f"{_('Weather request failed: ')}{error}") from error
    current = payload.get("current")
    if not isinstance(current, dict):
        # Accept responses from older Open-Meteo versions during migration.
        current = payload.get("current_weather")
    if not isinstance(current, dict):
        raise WeatherFetchError(_("Weather response missing current_weather"))
    daily = payload.get("daily")
    hourly = payload.get("hourly")
    return {
        "current": {
            "temperature": current.get("temperature_2m", current.get("temperature")),
            "windspeed": current.get("wind_speed_10m", current.get("windspeed")),
            "winddirection": current.get("wind_direction_10m", current.get("winddirection")),
            "weathercode": current.get("weather_code", current.get("weathercode")),
            "time": current.get("time"),
        },
        "daily": daily if isinstance(daily, dict) else {},
        "hourly": hourly if isinstance(hourly, dict) else {},
    }

# ---------------------------------------------------------------------------
# Weather cache
# ---------------------------------------------------------------------------

def _series(block: dict, *names: str) -> list:
    """The first of `names` that is a list in an Open-Meteo block (the API
    knows some fields under an old and a new name)."""
    for name in names:
        value = block.get(name)
        if isinstance(value, list):
            return value
    return []

def _item(values: list, index: int):
    return values[index] if 0 <= index < len(values) else None

def parse_forecast(daily: dict, hourly: dict) -> list[dict]:
    """Per-day dicts, today first, at most FORECAST_DAYS_AHEAD + 1 of them.
    Each has the day's code / tmax / tmin / precip (mm) / pop (rain chance, %) /
    wind and gust (km/h) / sunrise / sunset / uv, and "hours": one
    [hour, temperature, weathercode, rain chance %, wind km/h] row per hour."""
    hour_times = _series(hourly, "time")
    hour_columns = (
        _series(hourly, "temperature_2m"),
        _series(hourly, "weathercode", "weather_code"),
        _series(hourly, "precipitation_probability"),
        _series(hourly, "windspeed_10m", "wind_speed_10m"),
    )
    hours_by_date: dict[str, list] = {}
    for index, stamp in enumerate(hour_times):
        stamp = str(stamp)
        try:
            hour = int(stamp[11:13])
        except ValueError:
            continue
        row = [hour] + [_item(column, index) for column in hour_columns]
        hours_by_date.setdefault(stamp[:10], []).append(row)
    columns = {
        "code": _series(daily, "weathercode", "weather_code"),
        "tmax": _series(daily, "temperature_2m_max"),
        "tmin": _series(daily, "temperature_2m_min"),
        "precip": _series(daily, "precipitation_sum"),
        "pop": _series(daily, "precipitation_probability_max"),
        "wind": _series(daily, "windspeed_10m_max", "wind_speed_10m_max"),
        "gust": _series(daily, "windgusts_10m_max", "wind_gusts_10m_max"),
        "sunrise": _series(daily, "sunrise"),
        "sunset": _series(daily, "sunset"),
        "uv": _series(daily, "uv_index_max"),
    }
    days = []
    for index, day_text in enumerate(_series(daily, "time")[: FORECAST_DAYS_AHEAD + 1]):
        day = {name: _item(values, index) for name, values in columns.items()}
        day["date"] = day_text
        day["hours"] = hours_by_date.get(str(day_text), [])
        days.append(day)
    return days

class WeatherStationCache:
    """Fetches and caches a current-weather reading (plus a short forecast)
    per city, on demand.

    Nothing is fetched until a city is actually visible or selected (see
    CitiesLayer.build), and a city already fetched recently is served from
    cache instead of being re-requested on every render.

    Readings are persisted to WEATHER_CACHE_FILE, so a fresh process starts
    from the last known data instead of empty, and a failed fetch falls
    back to whatever was last successfully read (from this run or a past
    one) rather than showing nothing. A city whose last attempt errored is
    retried on the much shorter WEATHER_RETRY_INTERVAL_SECONDS cadence
    instead of the normal refresh interval.

    Several weather layers (the built-in one, a plugin's) share the cache file.
    Each writes only the cities it fetched itself, merged into the file, and
    tags them with its `owner`. A `sovereign` cache (a plugin layer for its own
    region, say) replaces any other owner's reading of a city it fetched, except
    a good reading with a failed one; any other cache leaves a reading another
    owner wrote within SOVEREIGN_HOLD_SECONDS alone. So one layer never drops,
    or brings back, what another layer saved (within one process: the lock
    is not shared between two running apps).
    """

    def __init__(
        self,
        on_update: Callable[[], None] | None = None,
        owner: str = "",
        sovereign: bool = False,
    ) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, dict] = self._load_from_disk()
        self._in_progress: set[str] = set()
        self._on_update = on_update
        self._owner = owner
        self._sovereign = sovereign

    @staticmethod
    def _load_from_disk() -> dict[str, dict]:
        try:
            text = WEATHER_CACHE_FILE.read_text(encoding="utf-8")
        except OSError:
            return {}
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        clean = {}
        for key, entry in data.items():
            if not isinstance(key, str) or not isinstance(entry, dict):
                continue
            try:
                fetched_at = float(entry["fetched_at"])
            except (KeyError, TypeError, ValueError):
                continue
            if math.isfinite(fetched_at):
                clean[key] = {**entry, "fetched_at": fetched_at}
        return clean

    def _may_replace(self, saved: dict | None, entry: dict) -> bool:
        """Whether this cache may write `entry` over `saved`, the file's reading of a city."""
        if saved is None or (saved.get("owner") or "") in ("", self._owner):
            return True
        if self._sovereign:
            # A failed fetch does not wipe out another layer's good reading.
            return not (entry.get("error") and not saved.get("error"))
        # Another owner's reading: kept, unless it is a day old (its layer no longer
        # keeps that city fresh, so the sovereignty has lapsed).
        try:
            age = time.time() - float(saved.get("fetched_at", 0))
        except (TypeError, ValueError):
            return True
        return age >= SOVEREIGN_HOLD_SECONDS

    def _save_entry(self, city_key: str, entry: dict) -> None:
        """Merge one city this cache fetched into the file, keeping every other city
        as the file has it (another layer may have written them since)."""
        try:
            with _WEATHER_CACHE_WRITE_LOCK:
                on_disk = self._load_from_disk()
                if not self._may_replace(on_disk.get(city_key), entry):
                    return
                on_disk[city_key] = entry
                self._write_file(on_disk)
        except OSError:
            # Persistence is a nice-to-have; a failed write shouldn't take
            # down weather fetching.
            pass

    @staticmethod
    def _write_file(entries: dict[str, dict]) -> None:
        """Atomic write of the cache file. Call with _WEATHER_CACHE_WRITE_LOCK held."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = WEATHER_CACHE_FILE.with_suffix(WEATHER_CACHE_FILE.suffix + ".tmp")
        temp_path.write_text(json.dumps(entries), encoding="utf-8")
        temp_path.replace(WEATHER_CACHE_FILE)

    def get(self, city_key: str) -> dict | None:
        with self._lock:
            entry = self._entries.get(city_key)
            return dict(entry) if entry is not None else None

    def temperature_range(self) -> tuple[float, float] | None:
        """The (coldest, hottest) temperature currently known across every
        cached city -- not just the visible ones -- so the color gradient
        stays anchored to the actual coldest/hottest city we've read, and
        doesn't jump terrascope as the map is panned. Returns None until at
        least one reading is known.
        """
        with self._lock:
            # Entries predating the coercion below may hold strings,
            # so filter again here instead of trusting stored types.
            temperatures = [
                temp
                for entry in self._entries.values()
                if (temp := _as_finite(entry.get("temperature"))) is not None
            ]
        if not temperatures:
            return None
        return min(temperatures), max(temperatures)

    def _is_stale(self, city_key: str) -> bool:
        entry = self._entries.get(city_key)
        if entry is None:
            return True
        if entry.get("schema") != WEATHER_SCHEMA and not entry.get("error"):
            return True  # saved by an older version: fetch the multi-day forecast
        interval = (
            WEATHER_RETRY_INTERVAL_SECONDS
            if entry.get("error")
            else WEATHER_REFRESH_INTERVAL_SECONDS
        )
        return time.time() - entry["fetched_at"] >= interval

    def has_pending_retry(self, keys: Collection[str] | None = None) -> bool:
        """True if some cached city errored last time and is now due for
        another attempt. Lets the layer force a redraw so that retry
        actually gets kicked off even when nothing else is happening.
        With `keys`, only those cities count (the ones a redraw would retry).
        """
        now = time.time()
        with self._lock:
            return any(
                city_key not in self._in_progress
                and now - entry.get("fetched_at", 0) >= WEATHER_RETRY_INTERVAL_SECONDS
                for city_key, entry in self._failed(keys)
            )

    def loading_count(self, keys: Collection[str] | None = None) -> int:
        """Fetches running now: all of them, or only those of `keys`."""
        with self._lock:
            if keys is None:
                return len(self._in_progress)
            return sum(city_key in self._in_progress for city_key in keys)

    def _failed(self, keys: Collection[str] | None):
        """(key, entry) of the cities whose last attempt errored, among `keys` or the
        whole cache. Call with the lock held."""
        if keys is None:
            pairs = self._entries.items()
        else:  # the view's few keys, not every city ever cached
            pairs = ((key, self._entries.get(key)) for key in keys)
        return ((key, entry) for key, entry in pairs if entry and entry.get("error"))

    def failed_count(self, keys: Collection[str] | None = None) -> int:
        """Cities whose last attempt errored: every cached one, or only `keys`.
        The cache also holds cities read from disk or labelled in another view,
        which are not retried until a view labels them again."""
        with self._lock:
            return sum(1 for _pair in self._failed(keys))

    def first_error(self, keys: Collection[str] | None = None) -> str:
        with self._lock:
            return next((str(entry["error"]) for _key, entry in self._failed(keys)), "")

    def ensure_fresh(self, city_key: str, latitude: float, longitude: float) -> None:
        """Kick off a background fetch for this city if it's missing or
        stale. Returns immediately either way; check get() for the result.
        """
        with self._lock:
            if city_key in self._in_progress:
                return
            if len(self._in_progress) >= MAX_CONCURRENT_WEATHER_REQUESTS:
                return
            if not self._is_stale(city_key):
                return
            self._in_progress.add(city_key)
        thread = threading.Thread(
            target=self._fetch_worker,
            args=(city_key, latitude, longitude),
            daemon=True,
        )
        thread.start()

    def _fetch_worker(self, city_key: str, latitude: float, longitude: float) -> None:
        from terrascope.layers.weather.providers import fetch_reading

        try:
            error = ""
            current = None
            forecast: list = []
            sources = {"current": "", "forecast": ""}
            try:
                # The providers that cover this place (a regional source first,
                # Open-Meteo last); see providers.py.
                reading = fetch_reading(latitude, longitude)
                current = reading.current
                forecast = reading.forecast
                sources = {"current": reading.current_source, "forecast": reading.forecast_source}
                if current is None and reading.errors:
                    # Only part of the answer: retry soon, not at the full interval.
                    error = "; ".join(reading.errors)
            except WeatherFetchError as fetch_error:
                error = str(fetch_error)
            with self._lock:
                previous = self._entries.get(city_key, {})
                # Coerce on the way in. A bad feed value keeps the previous good
                # reading instead of poisoning the cache, but only from the same
                # provider: another source's old wind or time must not be shown
                # under the new source's name.
                same_source = (previous.get("sources") or {}).get("current") == sources["current"]
                kept = previous if same_source else {}
                fresh_temp = _as_finite(current.get("temperature")) if current else None
                fresh_wind = _as_finite(current.get("windspeed")) if current else None
                fresh_dir = _as_finite(current.get("winddirection")) if current else None
                if current:
                    previous = {**previous, **{name: kept.get(name) for name in
                                               ("temperature", "windspeed", "winddirection")}}
                self._entries[city_key] = {
                    "temperature": (
                        fresh_temp
                        if fresh_temp is not None
                        else previous.get("temperature")
                    ),
                    "windspeed": (
                        fresh_wind
                        if fresh_wind is not None
                        else previous.get("windspeed")
                    ),
                    "winddirection": (
                        fresh_dir
                        if fresh_dir is not None
                        else previous.get("winddirection")
                    ),
                    "weathercode": (
                        current.get("weathercode")
                        if current
                        else previous.get("weathercode")
                    ),
                    "observed_at": (
                        current.get("time")
                        if current
                        else previous.get("observed_at")
                    ),
                    "summary": (
                        current.get("summary")
                        if current
                        else previous.get("summary")
                    ),
                    "forecast": forecast if forecast else previous.get("forecast", []),
                    "sources": {
                        "current": sources["current"] if current else (previous.get("sources") or {}).get("current", ""),
                        "forecast": sources["forecast"] if forecast else (previous.get("sources") or {}).get("forecast", ""),
                    },
                    "schema": WEATHER_SCHEMA if (current or forecast) else previous.get("schema"),
                    "fetched_at": time.time(),
                    "error": error,
                    "owner": self._owner,
                }
                entry_to_save = dict(self._entries[city_key])
            self._save_entry(city_key, entry_to_save)
            if self._on_update is not None:
                self._on_update()
        finally:
            with self._lock:
                self._in_progress.discard(city_key)
