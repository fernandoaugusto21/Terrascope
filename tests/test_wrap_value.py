"""Wrapping of value text in the side panels (core/ui/wrap.py): breaks at spaces
only, never between a number and its unit, and the info box draws those lines."""

from __future__ import annotations

import textwrap

import pytest

from terrascope.core.ui.dialogs import _draw_label_value_rows
from terrascope.core.ui.wrap import wrap_value


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


def test_plain_words_wrap_as_textwrap_wraps_them():
    text = "alpha beta gamma delta epsilon"
    expected = textwrap.wrap(text, width=9, break_long_words=True, break_on_hyphens=False)
    assert wrap_value(text, 9) == expected


def test_empty_text_is_one_empty_line():
    assert wrap_value("", 10) == [""]


def test_a_word_longer_than_the_width_is_cut():
    assert wrap_value("x" * 12, 5) == ["xxxxx", "xxxxx", "xx"]


@pytest.mark.parametrize("width", [5, 8, 12, 16, 24, 26, 28, 30, 40])
def test_no_line_is_wider_than_the_width(width):
    text = "ativos: 1 · hoje: 1 20:21 a R JOSE DE ALENCAR (BRAS) · intransitável, 16,0 mm, 22–32 °C"
    assert all(len(line) <= width for line in wrap_value(text, width))


@pytest.mark.parametrize("pair", ["16,0 mm", "22–32 °C", "21,9 °C", "3 h", "45 %", "2 km", "1,2 km/h"])
def test_a_number_stays_on_the_line_of_its_unit(pair):
    """Whenever the pair fits in a line, it is not split, at any width around it."""
    for width in range(len(pair), 41):
        for prefix in ("", "chuva ", "mín "):
            text = f"{prefix}{pair} depois"
            lines = wrap_value(text, width)
            assert any(pair in line for line in lines), (width, lines)


def test_a_degree_sign_after_a_space_is_joined_to_its_number():
    assert wrap_value("mín 22–32 °C máx 21,9 °C", 10) == ["mín", "22–32 °C", "máx", "21,9 °C"]


def test_the_station_value_of_the_example_keeps_its_unit():
    assert wrap_value("chuva 16,0 mm", 8) == ["chuva", "16,0 mm"]


def test_a_unit_is_not_a_word_that_only_starts_with_one():
    # "mín" starts with m, "horas" with h: neither is a unit, so no join.
    assert wrap_value("mín 3 horas", 6) == ["mín 3", "horas"]


def test_a_pair_wider_than_the_line_falls_back_to_word_breaks():
    # "22–32 °C" (8 cells) cannot fit a 6-cell line: it breaks between its words.
    assert wrap_value("22–32 °C", 6) == ["22–32", "°C"]


def test_the_info_box_draws_the_lines_wrap_value_gives_at_a_narrow_width():
    # 24 columns: the value column is 7 wide, so "chuva 16,0 mm" wraps.
    window = _Window(height=8, width=24)
    _draw_label_value_rows(window, 0, 0, 8, 24, [("ESTAÇÃO", "chuva 16,0 mm")], label_width=12)
    value_x = 2 + 12 + 1  # label column, one space, then the value
    lines = wrap_value("chuva 16,0 mm", 24 - value_x - 2)
    assert lines == ["chuva", "16,0 mm"]
    drawn = [window.row(1 + offset)[value_x:] for offset in range(len(lines))]
    assert drawn == lines


def test_the_info_box_at_a_wider_width_keeps_a_short_value_on_one_line():
    window = _Window(height=5, width=44)
    _draw_label_value_rows(window, 0, 0, 5, 44, [("ESTAÇÃO", "chuva 16,0 mm")], label_width=12)
    assert window.row(1).endswith("chuva 16,0 mm")
    assert window.row(2).strip() == ""
