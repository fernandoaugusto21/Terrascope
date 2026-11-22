"""LayerRender.line_layers: more braille lines in their own colours, drawn in the
layer's turn before its `lines`, so a layer drawn later still covers them."""

from __future__ import annotations

import types

from terrascope.core.layer import LayerRender
from terrascope.core.ui.map import draw_layer_symbols

B = "⠀"   # blank braille cell
DOT = "⠁"


def _area(*renders):
    drawn = {}

    def put(row, col, text, color, bg):
        for offset, char in enumerate(text):
            drawn[(row, col + offset)] = (char, color)

    area = types.SimpleNamespace(
        frame=types.SimpleNamespace(layers=list(renders)),
        height=2, width=4, bg_row=lambda row: [None] * 4, put=put,
    )
    return area, drawn


def test_each_line_layer_keeps_its_colour():
    roads = LayerRender(None, "#000000", line_layers=[([DOT + B * 3, B * 4], "#ff0000"),
                                                      ([B + DOT + B * 2, B * 4], "#00ff00")])
    area, drawn = _area(roads)
    draw_layer_symbols(area)
    assert drawn == {(0, 0): (DOT, "#ff0000"), (0, 1): (DOT, "#00ff00")}


def test_a_later_layer_covers_them():
    roads = LayerRender(None, "#000000", line_layers=[([DOT * 2 + B * 2, B * 4], "#ff0000")])
    outlines = LayerRender([B + "⠂" + B * 2, B * 4], "#ffffff")
    area, drawn = _area(roads, outlines)
    draw_layer_symbols(area)
    assert drawn[(0, 0)] == (DOT, "#ff0000")
    assert drawn[(0, 1)] == ("⠂", "#ffffff")


def test_a_layer_without_them_draws_as_before():
    area, drawn = _area(LayerRender([DOT + B * 3], "#123456"))
    draw_layer_symbols(area)
    assert drawn == {(0, 0): (DOT, "#123456")}
