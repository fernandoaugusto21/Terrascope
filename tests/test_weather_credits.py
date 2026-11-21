"""The selected city's weather sources are named on the map (WeatherLayer.credits)."""

from __future__ import annotations

from terrascope.layers.weather.config import _CITY_TEXT, WEATHER_SCHEMA
from terrascope.layers.weather.layer import WeatherLayer

CITY = {"key": "Guarulhos|-23.40|-46.44", "name": "Guarulhos", "latitude": -23.4, "longitude": -46.44,
        "capital": False, "population": None, "country": "Brazil"}


def _layer(sources, schema=WEATHER_SCHEMA):
    layer = WeatherLayer()
    layer.weather._entries[CITY["key"]] = {"temperature": 24.0, "fetched_at": 1e18, "schema": schema,
                                           "sources": sources, "forecast": []}
    return layer


def test_no_city_selected_no_credit():
    assert _layer({"current": "CGE", "forecast": "CGE"}).credits() == []


def test_the_selected_city_names_its_sources():
    layer = _layer({"current": "Open-Meteo", "forecast": "INMET"})
    layer.selected = CITY
    (line,) = layer.credits()   # in the language of the machine
    assert "Guarulhos" in line and line.endswith(f"Open-Meteo · {_CITY_TEXT['forecast_by']} INMET")


def test_an_old_reading_or_hidden_cities_give_no_credit():
    layer = _layer({"current": "CGE", "forecast": "CGE"}, schema=1)
    layer.selected = CITY
    assert layer.credits() == []
    layer = _layer({"current": "CGE", "forecast": "CGE"})
    layer.selected = CITY
    layer.show_cities = False
    assert layer.credits() == []
