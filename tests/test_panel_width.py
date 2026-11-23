"""The side panel grows on a wide terminal (core/ui/layout.py): it keeps PANEL_WIDTH
on a narrow one, and an info box in a widened panel measures its label column."""

from __future__ import annotations

import copy

import pytest

from terrascope.core.config import CFG, ConfigError, validate_config
from terrascope.core.layer import Layer
from terrascope.core.ui import layout as layout_module
from terrascope.core.ui.constants import INFO_BOX_LABEL_WIDTH, OUTER_MARGIN, PANEL_WIDTH
from terrascope.core.ui.dialogs import draw_info_box
from terrascope.core.ui.layout import BOX_GAP, compute_layout, info_label_width, side_panel_width


class _Window:
    """Keeps the character last written to each cell, as a terminal would show it."""

    def __init__(self, height: int, width: int) -> None:
        self.height, self.width = height, width
        self.cells: dict[tuple[int, int], str] = {}

    def getmaxyx(self):
        return self.height, self.width

    def addnstr(self, y, x, text, n, attributes=0):
        for offset, char in enumerate(str(text)[: max(0, n)]):
            if 0 <= y < self.height and 0 <= x + offset < self.width:
                self.cells[(y, x + offset)] = char

    def row(self, y: int) -> str:
        return "".join(self.cells.get((y, x), " ") for x in range(self.width)).rstrip()


class _InfoLayer(Layer):
    name = "info-test"

    def __init__(self, rows) -> None:
        self._rows = rows

    def info_rows(self):
        return self._rows


# ---- the width -----------------------------------------------------------------

@pytest.mark.parametrize("width, expected", [(100, 32), (159, 32), (160, 32), (180, 37), (200, 42), (220, 44), (300, 44)])
def test_the_side_panel_keeps_its_width_until_160_columns_then_grows_to_44(width, expected):
    assert side_panel_width(width) == expected
    assert PANEL_WIDTH == 32


def test_the_side_panel_width_comes_from_the_settings(monkeypatch):
    monkeypatch.setattr(layout_module, "PANEL_MAX_WIDTH", 40)
    assert side_panel_width(300) == 40
    monkeypatch.setattr(layout_module, "PANEL_GROW_FROM", 120)
    assert side_panel_width(120) == 32


def _side_box(width: int, height: int = 40):
    layout = compute_layout(height, width, True, panel_orientation="vertical")
    (box, rect), = layout.boxes[:1]
    return rect, layout.map


@pytest.mark.parametrize("width", [100, 160])
def test_a_narrow_or_medium_terminal_lays_out_as_before(width):
    rect, map_rect = _side_box(width)
    margin_x = OUTER_MARGIN[0]
    assert rect[1] == margin_x and rect[3] == PANEL_WIDTH
    assert map_rect[1] == margin_x + PANEL_WIDTH + BOX_GAP


@pytest.mark.parametrize("width, panel", [(100, 32), (160, 32), (220, 44)])
def test_the_map_keeps_room_beside_the_panel(width, panel):
    rect, map_rect = _side_box(width)
    assert rect[3] == panel
    assert map_rect[3] == width - 2 * OUTER_MARGIN[0] - panel - BOX_GAP
    assert map_rect[3] >= 28  # the map's width today, never less


def test_the_widened_panel_is_wider_than_the_narrow_one_on_a_wide_terminal():
    assert _side_box(220)[0][3] > _side_box(100)[0][3]


# ---- the label column --------------------------------------------------------------

def test_a_narrow_panel_and_the_bottom_row_keep_the_fixed_label_column():
    rows = [("ESTAÇÃO", "chuva 16,0 mm")]
    assert info_label_width(rows, PANEL_WIDTH, side_panel=True) == INFO_BOX_LABEL_WIDTH
    assert info_label_width(rows, 44, side_panel=False) == INFO_BOX_LABEL_WIDTH


def test_a_widened_panel_measures_the_longest_label_shown():
    rows = [("ESTAÇÃO", "chuva"), ("ALAGAMENTOS", "1"), ("REGION", "Mooca")]
    assert info_label_width(rows, 44, side_panel=True) == len("ALAGAMENTOS")


def test_the_measured_label_column_is_capped():
    rows = [("A VERY LONG LABEL THAT GOES ON AND ON", "x")]
    assert info_label_width(rows, 44, side_panel=True) == 16


def test_a_widened_panel_with_no_rows_still_has_a_column():
    assert info_label_width([], 44, side_panel=True) == 1


def _draw(width: int, rows):
    window = _Window(height=8, width=width)
    draw_info_box(window, 0, 0, 8, width, _InfoLayer(rows), side_panel=True)
    return window


def test_a_value_gets_the_room_a_widened_panel_adds():
    rows = [("ESTAÇÃO", "chuva forte 16,0 mm")]  # 20 cells
    narrow = _draw(PANEL_WIDTH, rows)
    wide = _draw(44, rows)
    assert "chuva forte 16,0 mm" in wide.row(1)  # one line at 44 columns
    assert "chuva forte 16,0 mm" not in narrow.row(1)  # wrapped at 32 ...
    assert "16,0 mm" in narrow.row(2)  # ... and the number stays with its unit


def test_the_value_starts_after_the_measured_label_on_a_widened_panel():
    rows = [("ALAGAMENTOS", "1")]
    window = _draw(44, rows)
    label = len("ALAGAMENTOS")
    assert window.row(1).startswith("│ ALAGAMENTOS 1")  # the box's own left border first
    assert window.cells[(1, 2 + label + 1)] == "1"


# ---- the settings ---------------------------------------------------------------

@pytest.mark.parametrize("key, value", [("panel_width", 15), ("panel_width", 81), ("panel_max_width", 30)])
def test_the_side_panel_settings_are_checked(key, value):
    values = copy.deepcopy(CFG)
    values["ui"][key] = value
    with pytest.raises(ConfigError):
        validate_config(values)


def test_the_default_side_panel_settings_are_valid():
    validate_config()
