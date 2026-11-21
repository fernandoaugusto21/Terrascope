# providers.py — WHO ANSWERS FOR THE WEATHER OF A PLACE
# Responsible for: the WeatherProvider contract, the built-in Open-Meteo
# provider, the providers that plugins register ("terrascope.weather_providers"
# entry points) and fetch_reading(), which asks them in order for one place.
# A provider says which places it covers and returns what it has: the current
# conditions, the forecast, or both. The first covering provider that has each
# part wins, so a regional source can answer the forecast while another one
# answers the current conditions. Open-Meteo covers every place and comes last.
# Not here: the per-city cache (city_weather.py) or the drawing (forecast.py).

from __future__ import annotations

import numbers
import threading
from dataclasses import dataclass, field

PROVIDER_GROUP = "terrascope.weather_providers"

@dataclass
class WeatherReading:
    """What a provider knows about one place.

    current: {"temperature" (°C), "windspeed" (km/h), "winddirection" (degrees),
              "weathercode" (WMO), "time", optional "summary" (the source's own
              words for the conditions)}, or None when the provider has no
              current conditions.
    forecast: per-day dicts, today first, as parse_forecast() returns them
              ("date", "code", "tmax", "tmin", "precip", "pop", "wind", "gust",
              "sunrise", "sunset", "uv", "hours"); any of them may be None, and
              a day may add "summary" and "periods" ([{"name", "code"}, ...],
              the parts of the day, each drawn as the icon of its WMO code and
              its name in place of the hourly chart when the day has no hourly
              temperatures; other keys, such as the provider's own words in
              "summary", are kept but not drawn). [] when the provider has no forecast.
    current_source / forecast_source: the name shown for each part.
    errors: set by fetch_reading(), the failures of the providers asked (a
            partial reading with errors is retried soon, not at the full interval).
    """
    current: dict | None = None
    forecast: list[dict] = field(default_factory=list)
    current_source: str = ""
    forecast_source: str = ""
    errors: list[str] = field(default_factory=list)

class WeatherProvider:
    """A source of weather for some places. Subclasses set `name` and `priority`
    and implement covers() and fetch(). Both run in a background thread.
    fetch() raises WeatherFetchError when the source fails; a reading with only
    one of the two parts is fine (the next covering provider fills the other)."""

    name = ""
    priority = 0  # higher is asked first; the built-in Open-Meteo is the last resort

    def covers(self, latitude: float, longitude: float) -> bool:
        return False

    def fetch(self, latitude: float, longitude: float) -> WeatherReading:
        raise NotImplementedError

class OpenMeteoProvider(WeatherProvider):
    """The global model, for every place: current conditions and forecast."""

    name = "Open-Meteo"
    priority = -1000

    def covers(self, latitude: float, longitude: float) -> bool:
        return True

    def fetch(self, latitude: float, longitude: float) -> WeatherReading:
        from terrascope.layers.weather.city_weather import fetch_weather_snapshot, parse_forecast

        snapshot = fetch_weather_snapshot(latitude, longitude)
        return WeatherReading(
            current=snapshot["current"],
            forecast=parse_forecast(snapshot["daily"], snapshot["hourly"]) if snapshot["daily"] else [],
            current_source=self.name,
            forecast_source=self.name,
        )

_PLUGIN_PROVIDERS: list[WeatherProvider] | None = None
_PLUGIN_LOCK = threading.Lock()

def _load_plugin_providers() -> list[WeatherProvider]:
    """The providers of the "terrascope.weather_providers" entry points. Each entry
    point is a callable returning an iterable of WeatherProvider instances. A
    broken one is skipped with a warning, as for layers and tabs."""
    from terrascope.core.plugins import discover, origin_of, warn

    loaded: list[WeatherProvider] = []
    for entry_point in discover(PROVIDER_GROUP):
        origin = origin_of(entry_point)
        try:
            made = list(entry_point.load()())
            for provider in made:
                if not isinstance(provider, WeatherProvider):
                    raise TypeError(f"{provider!r} is not a WeatherProvider")
                if isinstance(provider.priority, bool) or not isinstance(provider.priority, numbers.Real):
                    raise TypeError(f"{provider.name or provider!r}: priority must be a number")
        except Exception as error:
            warn("ignoring weather provider plugin %s (%s): %s", entry_point.name, origin, error)
            continue
        loaded.extend(made)
    return loaded

def plugin_providers() -> list[WeatherProvider]:
    """The plugin providers, highest priority first, loaded and sorted once (on
    the first weather fetch)."""
    global _PLUGIN_PROVIDERS
    if _PLUGIN_PROVIDERS is None:
        with _PLUGIN_LOCK:
            if _PLUGIN_PROVIDERS is None:
                _PLUGIN_PROVIDERS = sorted(_load_plugin_providers(), key=lambda provider: -provider.priority)
    return _PLUGIN_PROVIDERS

_FALLBACK = OpenMeteoProvider()

def providers() -> list[WeatherProvider]:
    """Every provider in the order they are asked: highest priority first, then
    the built-in Open-Meteo."""
    return [*plugin_providers(), _FALLBACK]

def fetch_reading(latitude: float, longitude: float, chain: list[WeatherProvider] | None = None) -> WeatherReading:
    """Ask the providers that cover the place, in order, until both the current
    conditions and the forecast are known. Raises WeatherFetchError when no
    provider gave either part."""
    from terrascope.layers.weather.city_weather import WeatherFetchError

    reading = WeatherReading()
    errors: list[str] = []
    for provider in providers() if chain is None else chain:
        try:
            if not provider.covers(latitude, longitude):
                continue
            answer = provider.fetch(latitude, longitude)
            if not isinstance(answer, WeatherReading):
                raise TypeError(f"fetch() returned {type(answer).__name__}, not a WeatherReading")
        except WeatherFetchError as error:
            errors.append(f"{provider.name}: {error}")
            continue
        except Exception as error:  # a plugin bug must not stop the others
            errors.append(f"{provider.name}: {type(error).__name__}: {error}")
            continue
        if reading.current is None and answer.current:
            reading.current = answer.current
            reading.current_source = answer.current_source or provider.name
        if not reading.forecast and answer.forecast:
            reading.forecast = answer.forecast
            reading.forecast_source = answer.forecast_source or provider.name
        if reading.current is not None and reading.forecast:
            break
    if reading.current is None and not reading.forecast:
        raise WeatherFetchError("; ".join(errors) or "no weather provider covers this place")
    reading.errors = errors
    return reading
