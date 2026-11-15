"""The "Unknown" origin country of an aircraft: the data keeps the English word,
the screen shows it translated (formatting.country_label), and the country
filter finds it by either text."""

from __future__ import annotations

import pytest

from terrascope.core import i18n
from terrascope.core.app.input import InputMixin
from terrascope.core.world import WorldMap
from terrascope.layers.flights import api
from terrascope.layers.flights.formatting import UNKNOWN_ORIGIN, country_label
from terrascope.layers.flights.layer import FlightsLayer
from terrascope.layers.flights.settings import _LABELS


@pytest.fixture
def language(monkeypatch):
    """Set the interface language for one test and go back to English afterwards."""
    monkeypatch.setattr(i18n.locale, "getlocale", lambda *args: (None, None))
    yield i18n.activate
    i18n.activate("en")


def _state(country):
    """One OpenSky state vector (17 fields): on the ground = False, country in field 2."""
    return ["abc123", "TEST1", country, 0, 0, 10.0, 20.0, 1000.0, False, 200.0,
            90.0, 0.0, None, 1000.0, "1200", False, 0]


class _Input(InputMixin):
    """Only what the country filter panel reads."""

    def __init__(self, world: WorldMap) -> None:
        self.world = world
        self.filter_buffer = ""
        self.filter_selected: set[str] = set()
        self.filter_scroll = 0
        self.mode = "filter"


@pytest.fixture
def flights_world():
    layer = FlightsLayer()
    layer.enabled = True
    layer.flights = api.normalize_states([_state(None), _state("Brazil")])
    return layer, WorldMap([], [layer])


def test_missing_country_is_stored_as_the_english_word(language):
    language("pt_BR")
    flights = api.normalize_states([_state(None)])
    assert flights[0]["origin_country"] == UNKNOWN_ORIGIN == "Unknown"


@pytest.mark.parametrize("lang, expected", [("en", "Unknown"), ("pt_BR", "Desconhecido")])
def test_country_label_translates_only_the_unknown_word(language, lang, expected):
    language(lang)
    assert country_label(UNKNOWN_ORIGIN) == expected


def test_other_country_names_are_returned_unchanged(language):
    language("pt_BR")
    assert country_label("Brazil") == "Brazil"


def test_info_box_shows_the_translated_country(language):
    language("pt_BR")
    layer = FlightsLayer()
    layer.selected = api.normalize_states([_state(None)])[0]
    layer._live = {}
    assert dict(layer.info_rows())[_LABELS["country"]] == "Desconhecido"


def test_info_box_keeps_the_english_word_in_english(language):
    language("en")
    layer = FlightsLayer()
    layer.selected = api.normalize_states([_state(None)])[0]
    layer._live = {}
    assert dict(layer.info_rows())[_LABELS["country"]] == "Unknown"


def test_filter_list_shows_the_translated_option(language, flights_world):
    language("pt_BR")
    _layer, world = flights_world
    lines = [text for text, _attr in _Input(world).filter_box_lines(None, 10)]
    assert "[ ] Desconhecido" in lines
    assert "[ ] Brazil" in lines


def test_filter_list_shows_english_options_in_english(language, flights_world):
    language("en")
    _layer, world = flights_world
    lines = [text for text, _attr in _Input(world).filter_box_lines(None, 10)]
    assert "[ ] Unknown" in lines


@pytest.mark.parametrize("typed", ["desc", "Desc", "unk", "UNKNOWN"])
def test_typing_either_text_finds_the_unknown_option(language, flights_world, typed):
    language("pt_BR")
    _layer, world = flights_world
    ui = _Input(world)
    ui.filter_buffer = typed
    assert ui.filter_suggestions() == ["Unknown"]


def test_applying_the_filter_keeps_the_value_and_shows_the_label(language, flights_world):
    language("pt_BR")
    layer, world = flights_world
    ui = _Input(world)
    ui.filter_selected = {"Unknown"}
    ui._apply_country_filter()
    assert layer.filter_countries == {"Unknown"}
    assert [flight["origin_country"] for flight in layer.visible_flights()] == ["Unknown"]
    assert world.filter_value == "Desconhecido"


def test_world_label_falls_back_to_the_option_when_no_layer_translates_it(language, flights_world):
    language("pt_BR")
    _layer, world = flights_world
    assert world.filter_label("Brazil") == "Brazil"
