"""Per-tab zoom limit (`zoom_max`) and the detailed countries drawn from
map.zoom.detail_min on."""

from __future__ import annotations

import copy
import math
import types

import pytest

from terrascope.core import config
from terrascope.core.app import input as input_module
from terrascope.core.app.input import InputMixin
from terrascope.core.config import CFG, ConfigError, parse_tab_view, parse_tab_zoom_max
from terrascope.core.mapdata import make_ring
from terrascope.core.plugins import normalize_tab
from terrascope.core.tabs import Tab, _build
from terrascope.core.world import DETAIL_ZOOM_MIN, ZOOM_MAX, ZOOM_MIN, WorldMap, prepare_ring_set

# ---- parsing -------------------------------------------------------------

def test_no_zoom_max_means_none():
    assert parse_tab_zoom_max(None) is None


@pytest.mark.parametrize("value", [256, 256.0, 1024, ZOOM_MIN, 8])
def test_valid_zoom_max(value):
    assert parse_tab_zoom_max(value) == float(value)


@pytest.mark.parametrize("value", [True, "256", math.nan, math.inf, 0.5, 1025, -3])
def test_invalid_zoom_max_is_rejected(value):
    with pytest.raises(ConfigError):
        parse_tab_zoom_max(value, where="tab 'x' zoom_max")


def test_view_zoom_is_checked_against_the_tabs_zoom_max():
    view = {"lat": -23.5, "lon": -46.6, "zoom": 200}
    with pytest.raises(ConfigError):
        parse_tab_view(view)  # above map.zoom.max (64)
    assert parse_tab_view(view, zoom_max=256.0) == (-46.6, -23.5, 200.0)
    with pytest.raises(ConfigError):
        parse_tab_view({"lat": 0, "lon": 0, "zoom": 10}, zoom_max=8.0)


def test_built_in_tab_builds_with_its_zoom_max():
    item = {"name": "x", "label": "X", "color": "#000000", "zoom_max": 256}
    assert _build(item).zoom_max == 256.0
    assert _build({"name": "y", "label": "Y", "color": "#000000"}).zoom_max is None


def test_invalid_zoom_max_of_a_built_in_tab_fails_the_config_check():
    values = copy.deepcopy(CFG)
    values["tabs"]["items"][0]["zoom_max"] = 5000
    with pytest.raises(ConfigError):
        config.validate_config(values)


def test_built_in_view_may_use_its_tabs_zoom_max():
    values = copy.deepcopy(CFG)
    values["tabs"]["items"][0]["zoom_max"] = 256
    values["tabs"]["items"][0]["view"] = {"lat": -23.5, "lon": -46.6, "zoom": 128}
    config.validate_config(values)


def test_plugin_tab_keeps_its_zoom_max():
    item = {"name": "br", "label": "BR", "color": "#123456", "zoom_max": 256,
            "view": {"lat": -14, "lon": -52, "zoom": 3}}
    normalized = normalize_tab(item, set())
    assert normalized["zoom_max"] == 256.0
    assert _build(normalized).zoom_max == 256.0


def test_plugin_tab_with_a_bad_zoom_max_is_rejected():
    with pytest.raises(ValueError):
        normalize_tab({"name": "br", "label": "BR", "color": "#123456", "zoom_max": "a lot"}, set())


# ---- the world's limit -------------------------------------------------------

def test_world_zoom_stops_at_the_limit():
    world = WorldMap([], [])
    world.set_zoom_limit(256.0)
    for _ in range(40):
        world.zoom_in()
    assert world.zoom == 256.0
    world.set_zoom_limit(None)
    assert world.zoom == ZOOM_MAX  # zoomed out to the global limit
    for _ in range(5):
        world.zoom_in()
    assert world.zoom == ZOOM_MAX


def test_limit_below_zoom_min_is_raised_to_it():
    world = WorldMap([], [])
    world.set_zoom_limit(0.1)
    assert world.zoom_max == ZOOM_MIN


class _Stub(InputMixin):
    def __init__(self, world: WorldMap) -> None:
        self.world = world
        self.forced_off = frozenset()
        self.provinces_visible = False
        self.info_visible = False
        self._drag = None
        self.active_tab = None
        self._frame_size = (120, 40)
        self._pending_home_view = None
        self._colors_reset_at = 0.0
        self.colors = types.SimpleNamespace(reset=lambda: None)
        self.mode = "normal"
        self.filter_buffer = ""
        self.search_buffer = ""
        self.welcome_visible = False
        self.tz_dropdown_open = False
        self.panel_visible = True

    def cancel_input_mode(self) -> None:
        pass


@pytest.fixture
def tabs(monkeypatch):
    value = (
        Tab(name="plain", label="PLAIN", color="#000000", blurb=""),
        Tab(name="deep", label="DEEP", color="#000000", blurb="", view=(-46.6, -23.5, 3.0), zoom_max=256.0),
    )
    monkeypatch.setattr(input_module, "TABS", value)
    return value


def test_selecting_a_tab_applies_its_zoom_limit_and_leaving_it_restores_the_global_one(tabs):
    app = _Stub(WorldMap([], []))
    app.select_tab(1)
    assert app.world.zoom_max == 256.0
    for _ in range(40):
        app.world.zoom_in()
    assert app.world.zoom == 256.0
    app.select_tab(0)
    assert app.world.zoom_max == ZOOM_MAX
    assert app.world.zoom == ZOOM_MAX


# ---- detailed countries ------------------------------------------------------

def _square(size: float):
    return make_ring([(-size, -size), (size, -size), (size, size), (-size, size), (-size, -size)])


def test_detailed_countries_are_wanted_only_from_the_detail_zoom():
    world = WorldMap([], [])
    world.set_zoom_limit(1024.0)
    assert not world.wants_detail_countries
    world.set_view(0.0, 0.0, DETAIL_ZOOM_MIN)
    assert world.wants_detail_countries
    world.set_prepared_detail_countries(prepare_ring_set([_square(1.0)]))
    assert not world.wants_detail_countries


def test_detailed_countries_replace_the_normal_ones_only_from_the_detail_zoom():
    # Same zoom, with and without the detailed tier: only the tier changes.
    def coverage(zoom, with_detail):
        world = WorldMap([], [])
        world.set_zoom_limit(1024.0)
        world.set_prepared_countries(prepare_ring_set([_square(0.5)]))       # "normal"
        if with_detail:
            world.set_prepared_detail_countries(prepare_ring_set([_square(1.0)]))  # "detailed": 4x the area
        world.set_view(0.0, 0.0, zoom)
        return world.render(80, 40).land_cover.mean()

    at_detail = coverage(DETAIL_ZOOM_MIN, True) / coverage(DETAIL_ZOOM_MIN, False)
    below = coverage(DETAIL_ZOOM_MIN / 1.5, True) / coverage(DETAIL_ZOOM_MIN / 1.5, False)
    assert 3.0 < at_detail < 5.0   # the detailed square is drawn
    assert below == pytest.approx(1.0)  # below detail_min the normal one stays


def test_an_empty_detail_file_switches_the_detailed_countries_off(monkeypatch):
    from terrascope.core import world as world_module
    monkeypatch.setattr(world_module, "DETAIL_COUNTRIES_ENABLED", False)
    world = WorldMap([], [])
    world.set_zoom_limit(1024.0)
    world.set_view(0.0, 0.0, DETAIL_ZOOM_MIN * 4)
    assert not world.wants_detail_countries


def test_a_failed_detail_load_is_tried_again_after_the_retry_delay(monkeypatch):
    from terrascope.core.app import lifecycle

    started = []
    monkeypatch.setattr(lifecycle, "Thread", lambda **kwargs: types.SimpleNamespace(start=lambda: started.append(1)))
    clock = [1000.0]
    monkeypatch.setattr(lifecycle.time, "monotonic", lambda: clock[0])
    app = types.SimpleNamespace(detail_countries_state="idle", detail_countries_failed_at=0.0, map_data_queue=None)
    start = lambda: lifecycle.LifecycleMixin._start_detail_countries(app)
    start()
    assert started == [1] and app.detail_countries_state == "loading"
    start()  # already loading
    assert started == [1]
    app.detail_countries_state, app.detail_countries_failed_at = "failed", clock[0]
    clock[0] += lifecycle.DETAIL_RETRY_SECONDS - 1
    start()
    assert started == [1]
    clock[0] += 2
    start()
    assert started == [1, 1]


def test_tab_zoom_max_may_reach_a_global_limit_above_1024():
    limits = copy.deepcopy(CFG["map"])
    limits["zoom"]["max"] = 2048
    assert parse_tab_zoom_max(2048, map_settings=limits) == 2048.0
    with pytest.raises(ConfigError):
        parse_tab_zoom_max(2049, map_settings=limits)


# ---- a user's default.yaml from an older version -----------------------------

def test_settings_missing_from_an_old_user_default_file_come_from_the_bundled_one(tmp_path, monkeypatch):
    old = tmp_path / "default.yaml"
    old.write_text("map:\n  zoom:\n    min: 1\n    max: 32\n    step: 1.5\n    pan_step: 0.05\n"
                   "    province_min: 2\n", encoding="utf-8")
    monkeypatch.setattr(config, "DEFAULT_CONFIG_FILE", old)
    values = config._read_defaults()
    assert values["map"]["zoom"]["max"] == 32            # the user's value wins
    assert values["map"]["zoom"]["detail_min"] == 16     # added later: bundled value
    assert values["data"]["countries_detail_file"]
    config.validate_config(values)
