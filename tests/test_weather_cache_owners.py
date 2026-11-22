"""Weather layers sharing the cache file: each writes only its own cities, and a
sovereign layer's readings are not written over by another layer."""

from __future__ import annotations

import json

import pytest

from terrascope.layers.weather import city_weather, providers
from terrascope.layers.weather.city_weather import WeatherStationCache
from terrascope.layers.weather.layer import WeatherLayer
from terrascope.layers.weather.providers import WeatherReading

GUARULHOS = "Guarulhos|-23.40|-46.44"
KINSHASA = "Kinshasa|-4.33|15.31"
RECIFE = "Recife|-8.05|-34.90"


@pytest.fixture
def cache_file(monkeypatch, tmp_path):
    file = tmp_path / "weather_cache.json"
    monkeypatch.setattr(city_weather, "WEATHER_CACHE_FILE", file)
    monkeypatch.setattr(city_weather, "CACHE_DIR", tmp_path)
    return file


def _answer(monkeypatch, temperature: float, source: str = "Open-Meteo", fail: bool = False):
    def fetch_reading(latitude, longitude):
        if fail:
            raise city_weather.WeatherFetchError("handshake timed out")
        return WeatherReading(current={"temperature": temperature, "time": "2026-11-22T02:00"},
                              forecast=[{"date": "2026-11-22"}], current_source=source,
                              forecast_source=source)
    monkeypatch.setattr(providers, "fetch_reading", fetch_reading)


def _fetch(cache: WeatherStationCache, key: str) -> None:
    cache._in_progress.add(key)
    cache._fetch_worker(key, 0.0, 0.0)   # the worker body, run on this thread


def _saved(file) -> dict:
    return json.loads(file.read_text(encoding="utf-8"))


def test_a_layer_keeps_the_cities_another_layer_saved(cache_file, monkeypatch):
    core = WeatherStationCache(owner="weather")
    plugin = WeatherStationCache(owner="br_global_temp", sovereign=True)   # both loaded the empty file
    _answer(monkeypatch, 24.7)
    _fetch(core, KINSHASA)
    _answer(monkeypatch, 27.0)
    _fetch(plugin, RECIFE)               # its snapshot never had Kinshasa
    saved = _saved(cache_file)
    assert saved[KINSHASA]["temperature"] == 24.7 and saved[KINSHASA]["owner"] == "weather"
    assert saved[RECIFE]["owner"] == "br_global_temp"


def test_an_old_error_is_not_brought_back_by_another_layer(cache_file, monkeypatch):
    cache_file.write_text(json.dumps({KINSHASA: {"error": "handshake timed out", "fetched_at": 1.0,
                                                 "owner": "weather"}}), encoding="utf-8")
    core = WeatherStationCache(owner="weather")
    plugin = WeatherStationCache(owner="br_global_temp", sovereign=True)   # loaded the error too
    _answer(monkeypatch, 24.7)
    _fetch(core, KINSHASA)
    _fetch(plugin, RECIFE)
    assert not _saved(cache_file)[KINSHASA]["error"]


def test_the_sovereign_layer_wins_its_cities(cache_file, monkeypatch):
    core = WeatherStationCache(owner="weather")
    plugin = WeatherStationCache(owner="br_global_temp", sovereign=True)
    _answer(monkeypatch, 22.0)
    _fetch(core, GUARULHOS)                       # the core wrote it first
    _answer(monkeypatch, 23.1, source="INMET A701")
    _fetch(plugin, GUARULHOS)                     # the plugin replaces it
    assert _saved(cache_file)[GUARULHOS]["owner"] == "br_global_temp"
    _answer(monkeypatch, 21.0)
    _fetch(core, GUARULHOS)                       # the core may not write over it
    saved = _saved(cache_file)[GUARULHOS]
    assert saved["owner"] == "br_global_temp" and saved["temperature"] == 23.1
    assert core.get(GUARULHOS)["temperature"] == 21.0   # its own view still shows its reading


def test_an_entry_from_before_owners_may_be_replaced(cache_file, monkeypatch):
    cache_file.write_text(json.dumps({GUARULHOS: {"temperature": 20.0, "fetched_at": 1.0}}), encoding="utf-8")
    core = WeatherStationCache(owner="weather")
    _answer(monkeypatch, 22.0)
    _fetch(core, GUARULHOS)
    assert _saved(cache_file)[GUARULHOS]["temperature"] == 22.0


def test_a_failed_fetch_is_saved_under_its_owner(cache_file, monkeypatch):
    core = WeatherStationCache(owner="weather")
    _answer(monkeypatch, 0.0, fail=True)
    _fetch(core, KINSHASA)
    saved = _saved(cache_file)[KINSHASA]
    assert saved["error"] and saved["owner"] == "weather"


def test_the_layers_name_their_cache(cache_file):
    class Regional(WeatherLayer):
        name = "regional"
        weather_sovereign = True

    assert WeatherLayer().weather._owner == "weather" and not WeatherLayer().weather._sovereign
    regional = Regional()
    assert regional.weather._owner == "regional" and regional.weather._sovereign
