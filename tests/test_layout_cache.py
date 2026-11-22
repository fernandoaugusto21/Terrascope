"""The memoised layout(): reused while its inputs are unchanged, recomputed when any changes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from terrascope.core.app import lifecycle
from terrascope.core.app.lifecycle import LifecycleMixin
from terrascope.core.layer import PanelBox
from terrascope.core.ui.layout import compute_layout as real_compute_layout

WEATHER_PANEL = (PanelBox("info", 0.3), PanelBox("rich", 0.7, "FORECAST"))


class Layer:
    def __init__(self, name, panel_layout=None, rows=()):
        self.name = name
        self.enabled = True
        self.panel_layout = panel_layout
        self.rows = list(rows)
        self.info_rows_calls = 0

    def info_rows(self):
        self.info_rows_calls += 1
        return list(self.rows)


class SizingLayer(Layer):
    """Sizes its own info box from its rows, as the weather layer does. It
    needs a panel_layout to own the tab's bottom row at all."""

    def __init__(self, name, rows=()):
        super().__init__(name, WEATHER_PANEL, rows)

    def panel_layout_for(self, available_height, panel_width):
        ratio = min(0.9, 0.2 + 0.1 * len(self.rows))
        return (PanelBox("info", ratio), PanelBox("rich", 1.0 - ratio, "FORECAST"))


class Host(LifecycleMixin):
    def __init__(self, layers, active_tab=0):
        self.world = SimpleNamespace(layers=layers, search_text="", filter_value="", selected_layer=None)
        self.info_visible = False
        self.active_tab = active_tab
        self.panel_visible = True
        self.panel_orientation = "horizontal"
        self.mode = "normal"


@pytest.fixture
def tabs(monkeypatch):
    fake = [
        SimpleNamespace(name="weather", layers=("weather",)),
        SimpleNamespace(name="map", layers=()),
        SimpleNamespace(name="flights", layers=("flights",)),
    ]
    monkeypatch.setattr(lifecycle, "TABS", fake)
    return fake


@pytest.fixture
def compute_calls(monkeypatch):
    calls = []

    def counting(*args, **kwargs):
        calls.append(args)
        return real_compute_layout(*args, **kwargs)

    monkeypatch.setattr(lifecycle, "compute_layout", counting)
    return calls


def _uncached(host, height, width):
    """The layout for the host's current state, computed from scratch."""
    host._layout_cache = None
    return host.layout(height, width)


def test_same_size_and_state_is_computed_once(tabs, compute_calls):
    host = Host([Layer("weather", WEATHER_PANEL)])
    first = host.layout(40, 120)
    second = host.layout(40, 120)
    assert first == second
    assert len(compute_calls) == 1


def test_a_new_size_is_computed_again(tabs, compute_calls):
    host = Host([Layer("weather", WEATHER_PANEL)])
    host.layout(40, 120)
    host.layout(41, 120)
    host.layout(41, 121)
    assert len(compute_calls) == 3
    assert host.layout(41, 121) == _uncached(host, 41, 121)


def test_panel_visibility_and_orientation_invalidate(tabs, compute_calls):
    host = Host([Layer("weather", WEATHER_PANEL)])
    shown = host.layout(40, 120)
    host.panel_visible = False
    hidden = host.layout(40, 120)
    assert hidden != shown  # a stale hit would have returned `shown`
    assert hidden == _uncached(host, 40, 120)
    host.panel_visible = True
    host.panel_orientation = "vertical"
    assert host.layout(40, 120) == _uncached(host, 40, 120)


def test_tab_change_invalidates(tabs, compute_calls):
    host = Host([Layer("weather", WEATHER_PANEL)])
    on_weather = host.layout(40, 120)
    host.active_tab = 1  # the map tab has no bottom panel
    on_map = host.layout(40, 120)
    assert on_map == _uncached(host, 40, 120)
    assert on_map != on_weather


def test_panel_owner_change_invalidates(tabs, compute_calls):
    weather = Layer("weather", WEATHER_PANEL)
    host = Host([weather])
    before = host.layout(40, 120)
    weather.enabled = False  # no owner left for the weather tab
    after = host.layout(40, 120)
    assert len(compute_calls) == 2
    assert after != before
    assert after == _uncached(host, 40, 120)


def test_flights_search_row_changes_with_mode_when_narrow(tabs, compute_calls):
    flights = Layer("flights", (PanelBox("info", 0.5), PanelBox("search", 0.5, "S", "h")))
    host = Host([flights], active_tab=2)
    normal = host.layout(40, 90)
    host.mode = "filter"
    filtering = host.layout(40, 90)
    assert filtering == _uncached(host, 40, 90)
    assert filtering != normal


def test_sized_vertical_panel_follows_its_live_rows(tabs, compute_calls):
    weather = SizingLayer("weather", rows=())
    host = Host([weather])
    host.panel_orientation = "vertical"
    before = host.layout(40, 120)
    assert host.layout(40, 120) == before
    assert len(compute_calls) == 1

    # Weather data arriving changes the info rows, and so the box heights.
    weather.rows = ["Temperature: 21 C", "Wind: 4 m/s", "Rain: 0 mm"]
    after = host.layout(40, 120)
    assert after != before  # a stale hit would have returned `before`
    assert after == _uncached(host, 40, 120)


def test_horizontal_layout_does_not_read_the_info_rows(tabs, compute_calls):
    weather = SizingLayer("weather", rows=["row"])
    host = Host([weather])
    for _ in range(5):
        host.layout(40, 120)
    assert weather.info_rows_calls == 0


class OwnRowsSizing(SizingLayer):
    """Sizes from `info_rows` when given, as the weather layer does."""

    def panel_layout_for(self, available_height, panel_width, info_rows=None):
        rows = self.rows if info_rows is None else info_rows
        ratio = min(0.9, 0.2 + 0.1 * len(rows))
        return (PanelBox("info", ratio), PanelBox("rich", 1.0 - ratio, "FORECAST"))


def _info_height(layout):
    return next(rect[2] for box, rect in layout.boxes if box.kind == "info")


def test_a_side_panel_sizes_its_info_box_for_another_layers_selection(tabs):
    owner = OwnRowsSizing("weather")                          # nothing selected in the owner
    region = Layer("br_inundation_cge", rows=[("REGION", "Sé")] * 6)
    host = Host([owner, region])
    host.panel_orientation = "vertical"
    alone = _info_height(host.layout(50, 170))
    host.world.selected_layer, host.info_visible = region, True
    assert _info_height(host.layout(50, 170)) > alone          # sized for the region's six rows
    host.info_visible = False
    assert _info_height(host.layout(50, 170)) == alone


def test_a_panel_layout_for_without_info_rows_still_works(tabs):
    owner = SizingLayer("weather")
    other = Layer("other", rows=[("A", "b")] * 6)
    host = Host([owner, other])
    host.panel_orientation = "vertical"
    host.world.selected_layer, host.info_visible = other, True
    assert _info_height(host.layout(50, 170)) > 0
