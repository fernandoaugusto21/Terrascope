"""The "weather unavailable" notice and the retry count only the cities the view labels."""

from __future__ import annotations

import time

import pytest

from terrascope.core.i18n import _
from terrascope.core.view import View
from terrascope.layers.weather import city_weather, layer as weather_layer
from terrascope.layers.weather.layer import WeatherLayer


def notice() -> str:  # the language may change between tests
    return _("WEATHER UNAVAILABLE · RETRYING")


class OnePlace(WeatherLayer):
    def city_places(self, view):
        yield (-46.53, -23.46, "Guarulhos", False, None, "Brazil")


@pytest.fixture
def layer(monkeypatch, tmp_path):
    monkeypatch.setattr(city_weather, "WEATHER_CACHE_FILE", tmp_path / "weather.json")
    monkeypatch.setattr(weather_layer, "FETCH_NEW_DATA_FROM_API", True)
    layer = OnePlace()
    layer.enabled = True
    layer._startup_weather_ready = True
    started = []
    monkeypatch.setattr(layer.weather, "ensure_fresh", lambda key, lat, lon: started.append(key))
    layer.started = started
    long_ago = time.time() - 24 * 3600
    layer.weather._entries = {
        "Kinshasa|-4.32|15.31": {"error": "handshake timed out", "fetched_at": long_ago},
    }
    return layer


VIEW = View(-46.65, -23.5, 64, 160, 50)


def test_a_failed_city_outside_the_view_shows_no_notice_and_forces_no_redraw(layer):
    assert notice() not in layer.loading_messages()   # before any redraw nothing is labelled
    layer.build(VIEW)
    assert layer.started == ["Guarulhos|-23.46|-46.53"]
    assert notice() not in layer.loading_messages()
    layer.dirty = False
    layer._last_retry_scan = 0.0
    layer.tick()
    assert not layer.dirty
    # The whole cache still knows the old failure.
    assert layer.weather.failed_count() == 1 and layer.weather.first_error() == "handshake timed out"


def test_a_failed_city_in_the_view_shows_the_notice_and_is_retried(layer):
    key = "Guarulhos|-23.46|-46.53"
    layer.weather._entries[key] = {"error": "HTTP 503", "fetched_at": time.time() - 3600}
    layer.build(VIEW)
    assert notice() in layer.loading_messages()
    assert layer.weather.first_error(layer._weather_keys) == "HTTP 503"
    layer.dirty = False
    layer._last_retry_scan = 0.0
    layer.tick()
    assert layer.dirty


def test_cities_switched_off_clear_the_notice(layer):
    layer.weather._entries["Guarulhos|-23.46|-46.53"] = {"error": "HTTP 503", "fetched_at": time.time()}
    layer.build(VIEW)
    assert notice() in layer.loading_messages()
    layer.show_cities = False
    layer.build(VIEW)
    assert notice() not in layer.loading_messages()


def test_offline_nothing_is_retried_so_no_notice(layer, monkeypatch):
    monkeypatch.setattr(weather_layer, "FETCH_NEW_DATA_FROM_API", False)
    layer.weather._entries["Guarulhos|-23.46|-46.53"] = {"error": "HTTP 503", "fetched_at": time.time()}
    layer.build(VIEW)
    assert layer.started == [] and notice() not in layer.loading_messages()
