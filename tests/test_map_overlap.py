"""Map overlays on a fake screen: a legend must never cut a city label in half,
and status lines must stay above the attribution credits.

draw() runs for real against _Screen, which keeps the last character written to
each cell, so the assertions read what a terminal would show.
"""

from __future__ import annotations

import pytest

from terrascope.core.app.input import InputMixin
from terrascope.core.app.lifecycle import LifecycleMixin
from terrascope.core.app.rendering import RenderingMixin
from terrascope.core.app.shared import STATUS_OFFSET
from terrascope.core.layer import LayerRender, Marker, PanelBox, SidebarLine, SliderSpec
from terrascope.core.tabs import TABS
from terrascope.core.ui.colors import ColorManager
from terrascope.core.ui.constants import MAP_EDGE_PAD_Y, OSM_CREDIT, _SCALE_SYMBOLS
from terrascope.core.world import Frame

SCREEN_WIDTH = 120
LEGEND_TEXT = "CAMADAS DE TESTE"


def _tab(name: str) -> int:
    return next(index for index, tab in enumerate(TABS) if tab.name == name)


class _Screen:
    """Keeps the character last written to each cell, as a terminal would show it."""

    def __init__(self, height: int, width: int = SCREEN_WIDTH) -> None:
        self.height = height
        self.width = width
        self.cells: dict[tuple[int, int], str] = {}

    def getmaxyx(self):
        return self.height, self.width

    def erase(self):
        self.cells.clear()

    def refresh(self):
        pass

    def clearok(self, flag):
        pass

    def addnstr(self, y, x, text, n, attributes=0):
        if not 0 <= y < self.height:
            return
        for offset, char in enumerate(text[: max(0, n)]):
            if 0 <= x + offset < self.width:
                self.cells[(y, x + offset)] = char

    def row(self, y: int) -> str:
        return "".join(self.cells.get((y, x), " ") for x in range(self.width))

    def text(self) -> str:
        return "\n".join(self.row(y) for y in range(self.height))

    def find(self, needle: str):
        """(row, column) of the first occurrence of `needle` on screen, or None."""
        for y in range(self.height):
            x = self.row(y).find(needle)
            if x >= 0:
                return y, x
        return None


class _StubLayer:
    """A layer that only contributes legend lines, and optionally a bottom panel."""

    enabled = True

    def __init__(self, lines, name: str = "legend", panel: bool = False, credits=(), slider_spec=None) -> None:
        self.name = name
        self.panel_layout = (PanelBox("info", 1.0),) if panel else None
        self.selected = None
        self._lines = lines
        self._credits = credits  # as given: a plugin may return a str
        self._slider_spec = slider_spec

    def credits(self):
        return self._credits

    def slider(self):
        return self._slider_spec

    def legend_lines(self):
        return self._lines

    def loading_messages(self):
        return []


class _World:
    zoom = 1.0
    center_lat = 0.0
    dirty = False
    selected_layer = None
    selection_position = (0, 0)

    def __init__(self, layers, frame, slider=None) -> None:
        self.layers = layers
        self.frame = frame
        self._slider = slider

    def needs_render(self) -> bool:
        return False

    def render(self, width, height):
        raise AssertionError("the test frame is drawn as it is")

    def slider_layer(self):
        return self._slider

    def active_layers(self):
        return []


class _App(RenderingMixin, LifecycleMixin, InputMixin):
    """Just enough of the app for draw(): no welcome modal, no provinces."""

    def __init__(self, screen, world, tab, statuses, panel) -> None:
        self.stdscr = screen
        self.world = world
        self.active_tab = tab
        self.colors = ColorManager()  # disabled: every colour resolves to pair 0
        self._colors_reset_at = 0.0
        self.panel_visible = panel
        self.panel_orientation = "horizontal"
        self.mode = "normal"
        self.frame = world.frame
        self._frame_size = None
        self._pending_home_view = None
        self.welcome_visible = False
        self.province_choice = "no"
        self.province_state = "idle"
        self.map_statuses = dict(statuses)
        self.map_error = ""
        self.dismissed_statuses: set[str] = set()
        self.radar_status_expanded = True
        self.selected_timezone = None
        self.controls_expanded = False
        self.tz_dropdown_open = False
        self.tz_query = ""
        self.tz_index = 0
        self.forecast_scroll = 0
        self._forecast_city_key = None
        self.info_visible = False
        self.search_buffer = ""
        self.filter_buffer = ""
        self._legend_hits = []
        self._province_prompt_hits = []
        self._status_hits = []
        self._controls_layout = None
        self._dropdown_layout = None


def _draw(tab: int, height: int, *, markers=(), legend=(), statuses=None, panel=False, credits=(),
          slider=None, width: int = SCREEN_WIDTH, lon_span: float = 0.0, orientation: str = "horizontal"):
    """Run one draw() of the app on a fresh fake screen; returns (app, screen).
    `slider` is the SliderSpec of the active layer; `lon_span` > 0 draws a scale bar."""
    screen = _Screen(height, width)
    frame = Frame(
        country_lines=[],
        layers=[LayerRender(lines=None, line_color="#ffffff", markers=list(markers))],
        lon_span=lon_span,
        render_width=1,
    )
    # With the panel, the layer is the weather one: it owns the tab's bottom panel.
    layer = _StubLayer(list(legend), name="weather" if panel else "legend", panel=panel, credits=credits,
                       slider_spec=slider)
    world = _World([layer], frame, slider=layer if slider is not None else None)
    app = _App(screen, world, tab, statuses or {}, panel)
    app.panel_orientation = orientation
    app.draw()
    return app, screen


def _map_top_left(app, height: int, width: int = SCREEN_WIDTH) -> tuple[int, int]:
    """Screen (row, column) of the map box's top-left corner, as draw() lays it out."""
    top, left, _, _ = app.layout(height, width).map
    return top, left


# ---- legend against city labels -----------------------------------------------

@pytest.mark.parametrize(
    ("label", "column_offset", "shown"),
    [
        ("Belo Horizonte", -4, False),  # starts left of the legend and runs into it
        ("Belo Horizonte", 0, False),   # starts on the legend's first cell
        ("Recife", -6, True),           # ends right before the legend: untouched
    ],
)
def test_city_label_meeting_the_legend_is_left_out_whole(label, column_offset, shown):
    tab = _tab("map")
    height = 24
    legend = [SidebarLine(text=LEGEND_TEXT)]
    probe_app, probe = _draw(tab, height, legend=legend)
    legend_row, legend_col = probe.find(LEGEND_TEXT)
    box_top, box_left = _map_top_left(probe_app, height)
    area_row, area_col = box_top + 1, box_left + 2  # the map's first inner cell

    marker = Marker(
        x=legend_col + column_offset - area_col,
        y=legend_row - area_row,
        color="#ffffff",
        label=label,
    )
    _, screen = _draw(tab, height, markers=[marker], legend=legend)

    assert LEGEND_TEXT in screen.text()
    if shown:
        assert label in screen.text()
    else:
        assert label not in screen.text()
        assert label.split()[0] not in screen.text(), "a fragment of the label leaked out"


# ---- status lines against the attribution ------------------------------------

# With the bottom panel open the map is 8 to 10 rows high: five status lines
# reach the credit rows of the weather tab, as in the reported overlap.
@pytest.mark.parametrize("height", [20, 26])
@pytest.mark.parametrize("count", [1, 3, 5, 8])
def test_status_lines_stop_above_the_attribution(height, count):
    tab = _tab("weather")
    _, reference = _draw(tab, height, panel=True)  # same map, no statuses
    credit_row, _ = reference.find(TABS[tab].attribution)
    osm_row, _ = reference.find(OSM_CREDIT)
    assert credit_row == osm_row - 1

    statuses = {f"step-{index}": f"LOADING STEP {index}" for index in range(count)}
    app, screen = _draw(tab, height, panel=True, statuses=statuses)

    # The credit lines are exactly as drawn without any status line over them.
    assert screen.row(credit_row) == reference.row(credit_row)
    assert screen.row(osm_row) == reference.row(osm_row)

    top, _ = _map_top_left(app, height)
    first_status_row = top + STATUS_OFFSET[1]
    room = credit_row - first_status_row
    visible = [
        index for index in range(count)
        if screen.find(f"LOADING STEP {index}") is not None
    ]
    for index in visible:
        assert screen.find(f"LOADING STEP {index}")[0] < credit_row
    hidden = count - len(visible)
    if count <= room:
        assert hidden == 0
    else:
        # The status rows are full: the last one says how many it leaves out.
        assert hidden > 0
        summary = screen.find(f"+{hidden}")
        assert summary is not None and summary[0] == credit_row - 1


# ---- status lines against city labels ------------------------------------------

@pytest.mark.parametrize(("column_offset", "row_offset", "shown"), [
    (-3, 0, False),   # starts under the end of the status text: left out whole
    (0, 0, False),    # starts right against it (would read "...[X]Limeira"): left out
    (1, 0, True),     # one blank cell after it: untouched
    (-3, 1, True),    # the row below: untouched
])
def test_city_label_meeting_a_status_line_is_left_out_whole(column_offset, row_offset, shown):
    tab = _tab("weather")
    height = 24
    status = "WEATHER UNAVAILABLE"
    probe_app, probe = _draw(tab, height, statuses={"weather": status})
    status_row, status_col = probe.find(status)
    row_text = probe.row(status_row)
    end_col = status_col + len(status)
    if row_text[end_col:end_col + 4] == " [X]":
        end_col += 4
    box_top, box_left = _map_top_left(probe_app, height)
    area_row, area_col = box_top + 1, box_left + 2
    marker = Marker(x=end_col + column_offset - area_col, y=status_row + row_offset - area_row,
                    color="#ffffff", label="Limeira")
    _, screen = _draw(tab, height, markers=[marker], statuses={"weather": status})
    assert status in screen.text()
    if shown:
        assert "Limeira" in screen.text()
    else:
        assert "eira" not in screen.text(), "a fragment of the label leaked out"


def test_city_label_running_into_a_status_line_from_the_left_is_left_out_whole():
    tab = _tab("weather")
    height = 24
    status = "WEATHER UNAVAILABLE"
    # The label starts one cell left of the status text and runs into it.
    probe_app, probe = _draw(tab, height, statuses={"weather": status})
    status_row, status_col = probe.find(status)
    box_top, box_left = _map_top_left(probe_app, height)
    area_row, area_col = box_top + 1, box_left + 2
    marker = Marker(x=status_col - 1 - area_col, y=status_row - area_row, color="#ffffff", label="Limeira")
    _, screen = _draw(tab, height, markers=[marker], statuses={"weather": status})
    assert status in screen.text()
    assert "Limeira" not in screen.text() and "eira" not in screen.text()


# ---- city labels against the credits and the footer row (slider, scale) ------------

@pytest.mark.parametrize(("column_offset", "shown"), [
    (-4, False),  # runs over the end of the credit text: left out whole
    (0, False),   # starts right against it (would read "Open-Meteoreto"): left out
    (1, True),    # one blank cell after it: untouched
])
def test_city_label_meeting_the_credits_is_left_out_whole(column_offset, shown):
    tab = _tab("weather")
    height = 24
    probe_app, probe = _draw(tab, height)
    credit = TABS[tab].attribution.split(": ", 1)[-1]
    credit_row, credit_col = probe.find(credit)
    box_top, box_left = _map_top_left(probe_app, height)
    area_row, area_col = box_top + 1, box_left + 2
    marker = Marker(x=credit_col + len(credit) + column_offset - area_col, y=credit_row - area_row,
                    color="#ffffff", label="Ribeirao Preto")
    _, screen = _draw(tab, height, markers=[marker])
    assert credit in screen.text()
    if shown:
        assert "Ribeirao Preto" in screen.text()
    else:
        assert "Preto" not in screen.text(), "a fragment of the label leaked out"


@pytest.mark.parametrize(("column_offset", "shown"), [
    (0, False),   # right after the OSM credit: left out
    (2, True),    # with a blank cell between: kept (the footer row is free elsewhere)
])
def test_city_label_on_the_footer_row_keeps_clear_of_the_osm_credit(column_offset, shown):
    tab = _tab("weather")
    height = 24
    probe_app, probe = _draw(tab, height)
    osm_row, osm_col = probe.find(OSM_CREDIT)
    box_top, box_left = _map_top_left(probe_app, height)
    marker = Marker(x=osm_col + len(OSM_CREDIT) + column_offset - box_left - 2, y=osm_row - box_top - 1,
                    color="#ffffff", label="Jundiai")
    _, screen = _draw(tab, height, markers=[marker])
    assert ("Jundiai" in screen.text()) == shown


def test_layer_credits_go_above_the_tab_credits_and_the_statuses_stop_above_them():
    tab = _tab("weather")
    height = 26
    line = "Weather of Sao Paulo: CGE"
    statuses = {f"step-{index}": f"LOADING STEP {index}" for index in range(12)}
    app, screen = _draw(tab, height, credits=[line, line + " "], statuses=statuses)
    credit_row, _ = screen.find(TABS[tab].attribution.split(": ", 1)[-1])
    layer_row, _ = screen.find(line)
    assert layer_row == credit_row - 1
    assert screen.text().count(line) == 1   # once, even when two layers give it (or with spaces)
    for index in range(12):
        found = screen.find(f"LOADING STEP {index}")
        assert found is None or found[0] < layer_row


def test_a_credit_line_stops_before_the_legend_on_its_row():
    tab = _tab("weather")
    height = 24
    line = "Open-Meteo · forecast INMET: weather of " + "X" * 200
    legend = [SidebarLine(text=f"LEGEND LINE {index}") for index in range(12)]
    _, screen = _draw(tab, height, credits=[line], legend=legend)
    row, col = screen.find("Open-Meteo · forecast INMET")
    legend_cols = [found[1] for index in range(12) if (found := screen.find(f"LEGEND LINE {index}")) and found[0] == row]
    assert legend_cols, "the test needs a legend line on the credit row"
    assert "X" + "LEGEND" not in screen.row(row) and screen.row(row)[legend_cols[0] - 1] == " "


def test_a_plugin_credits_string_or_failure_does_not_break_the_drawing():
    tab = _tab("weather")
    _, screen = _draw(tab, 24, credits="INPE")   # a str, not a list: one line, not four
    row, col = screen.find("INPE")
    assert screen.row(row - 1)[col:col + 2].strip() == ""   # no one-letter lines stacked above

    class Broken(_StubLayer):
        def credits(self):
            raise KeyError("no data")

    screen = _Screen(24)
    frame = Frame(country_lines=[], layers=[LayerRender(lines=None, line_color="#ffffff")], lon_span=0.0, render_width=1)
    app = _App(screen, _World([Broken([])], frame), tab, {}, False)
    app.draw()
    assert screen.find(OSM_CREDIT) is not None


# ---- the OSM credit against the footer row (slider, scale bar) -----------------

def _radar(status: str = "") -> SliderSpec:
    """The radar slider of the weather tab: a long track, so its label starts far left."""
    return SliderSpec("RAINVIEWER", 13, 12, "LIVE", marker=12, wide=True, status=status)


def _footer_row(app, height: int, width: int = SCREEN_WIDTH) -> int:
    """Screen row of the map's footer row, the one the slider and scale bar share."""
    top, _, map_height, _ = app.layout(height, width).map
    return top + map_height - 2 - MAP_EDGE_PAD_Y


@pytest.mark.parametrize(("panel", "orientation"), [
    (False, "horizontal"),
    (True, "horizontal"),
    (True, "vertical"),   # a side panel narrows the map: the credit and the slider collide here
])
@pytest.mark.parametrize("status", ["", "LOADING RADAR"])
@pytest.mark.parametrize("width", [100, 110, 120, 130, 150])
def test_the_osm_credit_stays_whole_beside_a_slider(width, panel, orientation, status):
    tab = _tab("weather")
    height = 45
    app, screen = _draw(tab, height, width=width, panel=panel, orientation=orientation, slider=_radar(status))
    found = screen.find(OSM_CREDIT)
    assert found is not None, "the credit is cut or covered:\n" + screen.text()
    footer = _footer_row(app, height, width)
    assert found[0] in (footer - 1, footer)   # on the footer row, or moved up one row
    label = screen.find("RAINVIEWER")
    if label is None:   # too narrow for the slider's track: nothing is drawn, the credit keeps the footer row
        assert found[0] == footer
    else:
        assert label[0] == footer, "the slider keeps the footer row"


@pytest.mark.parametrize("width", [120, 130])
def test_the_credit_keeps_the_footer_row_when_the_slider_leaves_room(width):
    tab = _tab("weather")
    height = 45
    app, reference = _draw(tab, height, width=width)   # no slider: the old layout
    osm_row, osm_col = reference.find(OSM_CREDIT)
    assert osm_row == _footer_row(app, height, width)
    _, screen = _draw(tab, height, width=width, slider=_radar())
    assert screen.find(OSM_CREDIT) == (osm_row, osm_col)
    assert screen.find("RAINVIEWER")[0] == osm_row   # the slider shares the row, as before


def test_the_credit_block_moves_up_as_a_whole_when_the_footer_has_no_room():
    tab = _tab("weather")
    height = 45
    app, screen = _draw(tab, height, width=100, slider=_radar())
    footer = _footer_row(app, height, 100)
    osm_row, _ = screen.find(OSM_CREDIT)
    tab_credit, _ = screen.find(TABS[tab].attribution)
    assert osm_row == footer - 1
    assert tab_credit == osm_row - 1, "the tab's credit stays above the OSM credit"
    assert screen.find("RAINVIEWER")[0] == footer


def test_status_lines_stop_above_a_lifted_credit():
    tab = _tab("weather")
    height = 26
    _, reference = _draw(tab, height, width=100, slider=_radar())  # same map, no statuses
    credit_row, _ = reference.find(TABS[tab].attribution)
    osm_row, _ = reference.find(OSM_CREDIT)
    assert credit_row == osm_row - 1

    statuses = {f"step-{index}": f"LOADING STEP {index}." for index in range(12)}
    _, screen = _draw(tab, height, width=100, slider=_radar(), statuses=statuses)

    assert screen.row(credit_row) == reference.row(credit_row)
    assert screen.row(osm_row) == reference.row(osm_row)
    visible = [index for index in range(12) if screen.find(f"LOADING STEP {index}.") is not None]
    assert visible, "the test needs status lines on the map"
    for index in visible:
        assert screen.find(f"LOADING STEP {index}.")[0] < credit_row


@pytest.mark.parametrize(("column_offset", "shown"), [
    (0, False),   # right after the OSM credit, on the lifted row: left out
    (2, True),    # with a blank cell between: kept
])
def test_city_label_on_the_lifted_credit_keeps_clear_of_it(column_offset, shown):
    tab = _tab("weather")
    height = 45
    probe_app, probe = _draw(tab, height, width=100, slider=_radar())
    osm_row, osm_col = probe.find(OSM_CREDIT)
    box_top, box_left = _map_top_left(probe_app, height, 100)
    marker = Marker(x=osm_col + len(OSM_CREDIT) + column_offset - box_left - 2, y=osm_row - box_top - 1,
                    color="#ffffff", label="Jundiai")
    _, screen = _draw(tab, height, width=100, slider=_radar(), markers=[marker])
    assert ("Jundiai" in screen.text()) == shown


def test_a_legend_line_stops_above_a_lifted_credit():
    tab = _tab("weather")
    height = 45
    legend_text = "LEGEND " * 12   # wide enough to reach the credit's columns
    _, screen = _draw(tab, height, width=100, slider=_radar(), legend=[SidebarLine(text=legend_text.strip())])
    osm_row, _ = screen.find(OSM_CREDIT)
    legend = screen.find(legend_text.strip())
    assert legend is not None and legend[0] == osm_row - 1   # the legend stacks above the credit


@pytest.mark.parametrize("width", [76, 80, 84, 88])
def test_the_scale_bar_does_not_cut_the_credit(width):
    tab = _tab("weather")
    height = 45
    _, screen = _draw(tab, height, width=width, panel=True, orientation="vertical", lon_span=20.0)
    bar = _SCALE_SYMBOLS["end"] + _SCALE_SYMBOLS["fill"] * 3   # the bar's cap and fill, whatever the units
    assert screen.find(bar) is not None, "the test needs a scale bar"
    assert screen.find(OSM_CREDIT) is not None, "the scale bar covers the credit:\n" + screen.text()
