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
from terrascope.core.layer import LayerRender, Marker, PanelBox, SidebarLine
from terrascope.core.tabs import TABS
from terrascope.core.ui.colors import ColorManager
from terrascope.core.ui.constants import OSM_CREDIT
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

    def __init__(self, lines, name: str = "legend", panel: bool = False) -> None:
        self.name = name
        self.panel_layout = (PanelBox("info", 1.0),) if panel else None
        self.selected = None
        self._lines = lines

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

    def __init__(self, layers, frame) -> None:
        self.layers = layers
        self.frame = frame

    def needs_render(self) -> bool:
        return False

    def render(self, width, height):
        raise AssertionError("the test frame is drawn as it is")

    def slider_layer(self):
        return None

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


def _draw(tab: int, height: int, *, markers=(), legend=(), statuses=None, panel=False):
    """Run one draw() of the app on a fresh fake screen; returns (app, screen)."""
    screen = _Screen(height)
    frame = Frame(
        country_lines=[],
        layers=[LayerRender(lines=None, line_color="#ffffff", markers=list(markers))],
        lon_span=0.0,
        render_width=1,
    )
    # With the panel, the layer is the weather one: it owns the tab's bottom panel.
    layer = _StubLayer(list(legend), name="weather" if panel else "legend", panel=panel)
    app = _App(screen, _World([layer], frame), tab, statuses or {}, panel)
    app.draw()
    return app, screen


def _map_top_left(app, height: int) -> tuple[int, int]:
    """Screen (row, column) of the map box's top-left corner, as draw() lays it out."""
    top, left, _, _ = app.layout(height, SCREEN_WIDTH).map
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
