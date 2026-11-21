"""WeatherLayer.city_places: the places that may get a label, which a subclass may replace."""

from __future__ import annotations

from terrascope.core.view import View
from terrascope.layers.weather.forecast import city_population_floor
from terrascope.layers.weather.layer import WeatherLayer


class FinerPlaces(WeatherLayer):
    """A layer that gives its own places, with an unknown population."""

    def city_places(self, view):
        yield (-46.53, -23.46, "Guarulhos", False, None, "Brazil")
        yield (-46.56, -23.46, "Guarulhos twin", False, None, "Brazil")  # label would overlap
        yield (-46.85, -23.52, "Barueri", False, None, "Brazil")


def test_the_default_places_follow_the_natural_earth_rules():
    layer = WeatherLayer()
    layer._capitals = [(-47.9, -15.8, "Brasilia", True, 4_000_000, "Brazil")]
    layer._cities = [(-46.6, -23.5, "Sao Paulo", False, 20_000_000, "Brazil"),
                     (-46.5, -23.4, "Tiny", False, 10, "Brazil")]
    zoom = 10.0
    assert city_population_floor(zoom) is not None  # the floor applies at this zoom
    names = [place[2] for place in layer.city_places(View(-50, -15, zoom, 120, 40))]
    assert "Brasilia" in names and "Sao Paulo" in names and "Tiny" not in names


def test_a_subclass_gives_its_own_places_and_the_overlap_rule_still_holds():
    layer = FinerPlaces()
    placed = layer._place_cities(View(-46.65, -23.5, 64, 160, 50))
    names = [city["name"] for city, _cell, _label, _icon in placed]
    assert names == ["Guarulhos", "Barueri"]
    assert placed[0][0]["population"] is None


def test_the_selected_place_comes_first_and_an_unknown_population_reads_not_available():
    layer = FinerPlaces()
    layer.selected = {"key": "Barueri|-23.52|-46.85", "name": "Barueri", "latitude": -23.52,
                      "longitude": -46.85, "capital": False, "population": None, "country": "Brazil"}
    placed = layer._place_cities(View(-46.65, -23.5, 64, 160, 50))
    assert placed[0][0]["name"] == "Barueri"
    rows = dict(layer.info_rows())
    assert "Barueri" in rows.values()
    assert all(value != "None" for value in rows.values())


def test_a_selected_place_without_population_or_capital_keys_still_draws():
    layer = FinerPlaces()
    layer.selected = {"key": "X|-23.50|-46.60", "name": "X", "latitude": -23.5, "longitude": -46.6}
    placed = layer._place_cities(View(-46.65, -23.5, 64, 160, 50))
    assert placed[0][0]["name"] == "X"
