"""Weather providers: chosen by the place, asked in priority order, Open-Meteo last;
each part (current conditions, forecast) comes from the first provider that has it."""

from __future__ import annotations

import types

import pytest

from terrascope.layers.weather import providers as providers_module
from terrascope.layers.weather.city_weather import WeatherFetchError, WeatherStationCache
from terrascope.layers.weather.providers import (
    OpenMeteoProvider, WeatherProvider, WeatherReading, fetch_reading,
)

DAY = {"date": "2026-11-21", "code": 3, "tmax": 31.0, "tmin": 21.0, "hours": []}
NOW = {"temperature": 29.9, "windspeed": 5.0, "winddirection": 160.0, "weathercode": 3, "time": "2026-11-21T12:00"}


class _Fake(WeatherProvider):
    def __init__(self, name, priority, area, current=None, forecast=None, error=None):
        self.name, self.priority, self.area = name, priority, area
        self._current, self._forecast, self._error, self.calls = current, forecast or [], error, 0

    def covers(self, latitude, longitude):
        west, south, east, north = self.area
        return west <= longitude <= east and south <= latitude <= north

    def fetch(self, latitude, longitude):
        self.calls += 1
        if self._error:
            raise self._error
        return WeatherReading(current=self._current, forecast=self._forecast)


CITY = (-47.0, -24.0, -46.3, -23.3)
COUNTRY = (-74.0, -34.0, -34.0, 5.0)
WORLD = (-180.0, -90.0, 180.0, 90.0)


def test_the_regional_provider_answers_for_its_area():
    city = _Fake("CITY", 200, CITY, current=NOW, forecast=[DAY])
    world = _Fake("WORLD", -1000, WORLD, current=dict(NOW, temperature=1.0), forecast=[DAY])
    reading = fetch_reading(-23.55, -46.63, [city, world])
    assert (reading.current_source, reading.forecast_source) == ("CITY", "CITY")
    assert world.calls == 0                       # both parts known: nobody else is asked
    outside = fetch_reading(-22.9, -43.2, [city, world])
    assert outside.current_source == "WORLD"      # the city provider does not cover Rio


def test_a_forecast_only_provider_leaves_the_current_conditions_to_the_next():
    country = _Fake("COUNTRY", 100, COUNTRY, forecast=[dict(DAY, summary="Pancadas de chuva")])
    world = _Fake("WORLD", -1000, WORLD, current=NOW, forecast=[dict(DAY, code=0)])
    reading = fetch_reading(-23.4, -46.5, [country, world])
    assert reading.forecast_source == "COUNTRY" and reading.forecast[0]["summary"] == "Pancadas de chuva"
    assert reading.current_source == "WORLD" and reading.current["temperature"] == 29.9


def test_a_failing_provider_falls_through_and_a_plugin_bug_does_not_stop_the_chain():
    broken = _Fake("BROKEN", 300, CITY, error=RuntimeError("bug"))
    failing = _Fake("FAILING", 200, CITY, error=WeatherFetchError("HTTP 503"))
    world = _Fake("WORLD", -1000, WORLD, current=NOW, forecast=[DAY])
    reading = fetch_reading(-23.55, -46.63, [broken, failing, world])
    assert reading.current_source == "WORLD"


def test_no_answer_at_all_is_a_fetch_error_with_every_reason():
    failing = _Fake("FAILING", 200, CITY, error=WeatherFetchError("HTTP 503"))
    with pytest.raises(WeatherFetchError, match="FAILING: HTTP 503"):
        fetch_reading(-23.55, -46.63, [failing])


def test_plugin_providers_come_first_by_priority_and_open_meteo_last(monkeypatch):
    low, high = _Fake("LOW", 10, WORLD), _Fake("HIGH", 200, WORLD)
    monkeypatch.setattr(providers_module, "_PLUGIN_PROVIDERS", None)
    monkeypatch.setattr(providers_module, "_load_plugin_providers", lambda: [low, high])
    chain = providers_module.providers()
    assert [provider.name for provider in chain] == ["HIGH", "LOW", "Open-Meteo"]
    assert isinstance(chain[-1], OpenMeteoProvider)


def test_broken_plugin_entry_points_are_skipped(monkeypatch):
    good = _Fake("GOOD", 1, WORLD)

    class _EntryPoint:
        def __init__(self, name, value):
            self.name, self.value, self.dist = name, value, None

        def load(self):
            if isinstance(self.value, Exception):
                raise self.value
            return self.value

    points = [
        _EntryPoint("good", lambda: [good]),
        _EntryPoint("import_error", ImportError("missing")),
        _EntryPoint("wrong_type", lambda: ["not a provider"]),
    ]
    import terrascope.core.plugins as plugins
    monkeypatch.setattr(plugins, "discover", lambda group: points)
    warnings = []
    monkeypatch.setattr(plugins, "warn", lambda *args: warnings.append(args))
    assert providers_module._load_plugin_providers() == [good]
    assert len(warnings) == 2


def test_the_cache_keeps_the_sources_and_a_forecast_only_answer(monkeypatch, tmp_path):
    from terrascope.layers.weather import city_weather

    monkeypatch.setattr(city_weather, "WEATHER_CACHE_FILE", tmp_path / "weather.json")
    reading = WeatherReading(current=dict(NOW, summary="Sol entre nuvens"), forecast=[DAY],
                             current_source="CGE", forecast_source="CGE")
    monkeypatch.setattr(providers_module, "fetch_reading", lambda lat, lon: reading)
    cache = WeatherStationCache()
    cache._fetch_worker("sp", -23.55, -46.63)
    entry = cache.get("sp")
    assert entry["sources"] == {"current": "CGE", "forecast": "CGE"}
    assert entry["summary"] == "Sol entre nuvens" and entry["forecast"] == [DAY]


def test_the_info_box_and_the_forecast_title_name_the_sources():
    from terrascope.layers.weather.layer import WeatherLayer

    from terrascope.layers.weather.config import WEATHER_SCHEMA

    entry = dict(NOW, forecast=[DAY], schema=WEATHER_SCHEMA, summary=None, observed_at="x",
                 sources={"current": "Open-Meteo", "forecast": "INMET"})
    layer = types.SimpleNamespace(
        weather=types.SimpleNamespace(get=lambda key: entry),
        selected={"name": "Guarulhos", "key": "g"},
        _selected_kind=lambda: "city",
    )
    rows = dict(WeatherLayer._weather_rows(layer, "g"))
    assert any("INMET" in value and "Open-Meteo" in value for value in rows.values())
    assert WeatherLayer.rich_title(layer, "FORECAST").endswith("INMET")


def test_a_provider_returning_something_else_falls_through():
    class _Wrong(_Fake):
        def fetch(self, latitude, longitude):
            return None

    world = _Fake("WORLD", -1000, WORLD, current=NOW, forecast=[DAY])
    reading = fetch_reading(-23.55, -46.63, [_Wrong("WRONG", 50, WORLD), world])
    assert reading.current_source == "WORLD"
    assert any("WRONG" in error for error in reading.errors)


def test_a_provider_with_a_priority_that_is_not_a_number_is_skipped(monkeypatch):
    class _EntryPoint:
        name, dist = "bad", None

        def load(self):
            return lambda: [_Fake("BAD", "high", WORLD)]

    import terrascope.core.plugins as plugins
    monkeypatch.setattr(plugins, "discover", lambda group: [_EntryPoint()])
    warnings = []
    monkeypatch.setattr(plugins, "warn", lambda *args: warnings.append(args))
    assert providers_module._load_plugin_providers() == [] and warnings


def test_a_partial_answer_with_failures_is_retried_soon(monkeypatch, tmp_path):
    from terrascope.layers.weather import city_weather

    monkeypatch.setattr(city_weather, "WEATHER_CACHE_FILE", tmp_path / "weather.json")
    country = _Fake("COUNTRY", 100, COUNTRY, forecast=[DAY])
    world = _Fake("WORLD", -1000, WORLD, error=WeatherFetchError("HTTP 503"))
    monkeypatch.setattr(providers_module, "fetch_reading",
                        lambda lat, lon: fetch_reading(lat, lon, [country, world]))
    cache = WeatherStationCache()
    cache._fetch_worker("g", -23.4, -46.5)
    entry = cache.get("g")
    assert entry["forecast"] == [DAY] and "WORLD: HTTP 503" in entry["error"]


def test_old_wind_from_another_source_is_not_kept_under_the_new_one(monkeypatch, tmp_path):
    from terrascope.layers.weather import city_weather

    monkeypatch.setattr(city_weather, "WEATHER_CACHE_FILE", tmp_path / "weather.json")
    cache = WeatherStationCache()
    first = WeatherReading(current=NOW, forecast=[DAY], current_source="Open-Meteo", forecast_source="Open-Meteo")
    second = WeatherReading(current={"temperature": 25.0, "weathercode": 3}, forecast=[DAY],
                            current_source="CGE", forecast_source="CGE")
    for reading in (first, second):
        monkeypatch.setattr(providers_module, "fetch_reading", lambda lat, lon, r=reading: r)
        cache._fetch_worker("sp", -23.55, -46.63)
    entry = cache.get("sp")
    assert entry["temperature"] == 25.0 and entry["windspeed"] is None
