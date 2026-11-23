"""The map legend's layout (core/ui/map.py): items wrap between themselves within a
width limit, title-only lines share a row, a layer that draws nothing in the view
leaves the legend, and the old signatures still work."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from terrascope.core.config import CFG
from terrascope.core.layer import LayerRender, SidebarLine, legend_shown
from terrascope.core.ui.constants import MAP_EDGE_PAD_X
from terrascope.core.ui.map import legend_placements
from terrascope.core.world import Frame
from test_map_overlap import SCREEN_WIDTH, _App, _Screen, _StubLayer, _tab, _World

SIX_CLASSES = (
    ("■", "#8a8f98", "observação"),
    ("■", "#ffd93d", "atenção"),
    ("■", "#ff9f43", "iminência de transbordamento"),
    ("■", "#ff4d4d", "alerta"),
    ("■", "#ffb347", "≈ alagamento, transitável"),
    ("■", "#e50000", "≈ alagamento, intransitável"),
)


def _area(width: int, height: int = 30):
    return SimpleNamespace(width=width, height=height)


def _room(width: int) -> int:
    return width - MAP_EDGE_PAD_X


def _limit(width: int) -> int:
    """The default width limit of the legend rows (map.legend in default.yaml)."""
    settings = CFG["map"]["legend"]
    wanted = max(int(settings["min_width"]), round(width * float(settings["max_width_fraction"])))
    return max(1, min(_room(width), wanted))


def _rows(placed) -> list[str]:
    return ["".join(text for text, _, _ in segments) for _row, _col, _width, _action, segments in placed]


def _six_line(**extra) -> SidebarLine:
    return SidebarLine(text="alagamentos do CGE", legend_items=SIX_CLASSES, **extra)


# ---- wrapping -------------------------------------------------------------------

@pytest.mark.parametrize("width", [80, 120, 200])
def test_items_wrap_onto_rows_within_the_limit_and_keep_the_switch_on_the_first(width):
    line = _six_line(choices=("ligado", "desligado"), choice_index=0, action="cge")
    placed = legend_placements(_area(width), [line])
    rows = _rows(placed)
    assert len(rows) >= 2, "six classes do not fit one row at this width"
    assert rows[0].startswith("alagamentos do CGE") and "[" in rows[0]
    assert placed[0][3] == "cge"
    assert all(action is None for _row, _col, _width, action, _segments in placed[1:])
    for row in rows[1:]:
        assert len(row) <= _limit(width)


@pytest.mark.parametrize("width", range(40, 221, 20))
def test_no_item_is_split_and_every_row_shares_the_right_edge(width):
    placed = legend_placements(_area(width), [_six_line()])
    rows = _rows(placed)
    for _glyph, _colour, label in SIX_CLASSES:
        assert sum(label in row for row in rows) == 1, (width, label, rows)
    assert {col + row_width for _row, col, row_width, _a, _s in placed} == {width - MAP_EDGE_PAD_X}


def test_continuation_rows_follow_the_title_row_in_order():
    placed = legend_placements(_area(120), [_six_line()])
    assert [row for row, *_ in placed] == list(range(placed[0][0], placed[0][0] + len(placed)))


def test_a_title_wider_than_the_limit_wraps_at_its_spaces_and_keeps_its_switch():
    line = SidebarLine(
        text="Temperatura das cidades, relativa (Open-Meteo) com muitos detalhes a mais",
        choices=("ligado", "desligado"), choice_index=0, action="temp",
    )
    placed = legend_placements(_area(80), [line])
    assert [action for _row, _col, _width, action, _segments in placed].count("temp") == 1
    assert all(width <= _room(80) for _row, _col, width, _a, _s in placed)
    assert sum("ligado" in row for row in _rows(placed)) == 1


def test_a_short_line_keeps_one_row_at_the_right_edge_as_before():
    line = SidebarLine(text="frio", swatches=("#5f86f0",))
    placed = legend_placements(_area(80), [line])
    assert len(placed) == 1
    _row, col, width, action, _segments = placed[0]
    assert (col + width, action) == (_room(80), None)
    assert _rows(placed) == ["frio ■"]


# ---- dropping ------------------------------------------------------------------

def test_lines_are_dropped_only_when_the_rows_run_out_and_from_the_end_of_the_list():
    lines = [SidebarLine(text=f"LAYER {index}", legend_items=SIX_CLASSES) for index in range(12)]
    height = 14
    placed = legend_placements(_area(120, height), lines)
    kept = sorted({int(text.split()[1]) for text in _rows(placed) if text.startswith("LAYER")})
    assert kept[0] == 0 and kept[-1] < 11  # the first lines stay, the last ones go
    assert kept == list(range(len(kept)))
    assert len(placed) <= height - 2


def test_nothing_is_dropped_while_the_rows_fit():
    lines = [SidebarLine(text=f"LAYER {index}", swatches=("#ffffff",)) for index in range(8)]
    assert len(legend_placements(_area(120, 30), lines)) == 8


# ---- title-only lines ----------------------------------------------------------

def test_consecutive_title_only_lines_share_a_row_joined_by_a_middle_dot():
    lines = [SidebarLine(text="municípios do IBGE"), SidebarLine(text="estados do IBGE")]
    assert _rows(legend_placements(_area(120), lines)) == ["municípios do IBGE · estados do IBGE"]


def test_title_only_lines_are_not_joined_past_the_limit():
    lines = [SidebarLine(text="x" * 30), SidebarLine(text="y" * 30)]
    assert len(legend_placements(_area(80), lines)) == 2  # 30 + 3 + 30 > the 40-column limit


def test_a_line_with_a_swatch_is_not_joined():
    lines = [SidebarLine(text="municípios do IBGE"), SidebarLine(text="frio", swatches=("#5f86f0",))]
    assert len(legend_placements(_area(120), lines)) == 2


def test_title_lines_of_a_different_weight_are_not_joined():
    lines = [SidebarLine(text="A", bold=True), SidebarLine(text="B")]
    assert len(legend_placements(_area(120), lines)) == 2


# ---- the width setting ------------------------------------------------------------

def test_the_limit_comes_from_the_settings(monkeypatch):
    legend = CFG["map"]["legend"]
    monkeypatch.setitem(legend, "max_width_fraction", 0.25)
    monkeypatch.setitem(legend, "min_width", 20)
    placed = legend_placements(_area(120), [_six_line()])
    assert all(len(row) <= 30 for row in _rows(placed)[1:])
    assert len(_rows(placed)) > 2


def test_the_minimum_width_wins_on_a_small_map(monkeypatch):
    legend = CFG["map"]["legend"]
    monkeypatch.setitem(legend, "max_width_fraction", 0.1)
    monkeypatch.setitem(legend, "min_width", 36)
    placed = legend_placements(_area(80), [_six_line()])
    assert all(len(row) <= 36 for row in _rows(placed)[1:])


# ---- layers that draw nothing in the view --------------------------------------

class _Plain:
    """A layer object from before legend_visible existed."""

    enabled = True

    def legend_lines(self):
        return []


class _Hidden(_StubLayer):
    def legend_visible(self) -> bool:
        return False


def test_legend_shown_defaults_to_true_and_follows_the_layers_answer():
    assert legend_shown(_Plain())
    assert not legend_shown(_Hidden([]))
    shown = _StubLayer([])
    shown.legend_visible = lambda: True
    assert legend_shown(shown)


def _draw_layers(layers, tab: int | None = None, height: int = 30, width: int = SCREEN_WIDTH):
    screen = _Screen(height, width)
    frame = Frame(
        country_lines=[],
        layers=[LayerRender(lines=None, line_color="#ffffff", markers=[]) for _ in layers],
        lon_span=0.0,
        render_width=1,
    )
    app = _App(screen, _World(layers, frame, slider=None), _tab("weather") if tab is None else tab, {}, False)
    app.panel_orientation = "horizontal"
    app.draw()
    return screen


def test_a_hidden_layers_lines_leave_the_map_and_the_others_stay():
    shown = _StubLayer([SidebarLine(text="SHOWN KEY LINE", swatches=("#ffffff",))], name="shown")
    hidden = _Hidden([SidebarLine(text="HIDDEN KEY LINE", swatches=("#ffffff",))], name="hidden")
    screen = _draw_layers([shown, hidden])
    assert screen.find("SHOWN KEY LINE") is not None
    assert screen.find("HIDDEN KEY LINE") is None


def test_a_layer_without_the_hook_is_drawn_as_before():
    plain = _StubLayer([SidebarLine(text="PLAIN KEY LINE", swatches=("#ffffff",))], name="plain")
    assert _draw_layers([plain]).find("PLAIN KEY LINE") is not None


# ---- the status lines the legend must not cover ---------------------------------

def test_the_legend_leaves_the_rows_a_status_line_keeps_clear():
    lines = [SidebarLine(text=f"LAYER {index}", swatches=("#ffffff",)) for index in range(4)]
    free = legend_placements(_area(120, 12), lines)
    top_row = min(row for row, *_ in free)
    placed = legend_placements(_area(120, 12), lines, keep_clear=[(top_row, 0, 120)])
    assert all(row != top_row for row, *_ in placed)
    assert len(placed) < len(free)


def test_a_status_line_clear_of_the_legend_columns_costs_the_legend_nothing():
    lines = [SidebarLine(text=f"LAYER {index}", swatches=("#ffffff",)) for index in range(4)]
    free = legend_placements(_area(120, 12), lines)
    placed = legend_placements(_area(120, 12), lines, keep_clear=[(free[0][0], 0, 10)])
    assert placed == free
