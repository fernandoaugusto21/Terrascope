"""The forecast box shows a provider's parts of the day where it has no hourly values."""

from __future__ import annotations

from terrascope.layers.weather.forecast import (
    FORECAST_ROWS,
    _periods_row,
    forecast_lines,
    forecast_vertical_lines,
    weather_icon,
)

PERIODS = [
    {"name": "Morning", "code": 0, "summary": "Clear"},
    {"name": "Afternoon", "code": 95, "summary": "Storms"},
    {"name": "Night", "code": 61, "summary": "Rain"},
]


def _day(**extra):
    day = {"date": "2026-11-21", "code": 95, "tmin": 18.0, "tmax": 29.0, "precip": None, "pop": None,
           "wind": None, "gust": None, "sunrise": None, "sunset": None, "uv": None, "hours": []}
    day.update(extra)
    return day


def _text(line):
    return "".join(piece[0] for piece in line)


def test_a_day_without_hours_shows_its_periods_in_place_of_the_chart():
    lines = forecast_lines([_day(periods=PERIODS)], 30)
    assert len(lines) == FORECAST_ROWS
    chart = lines[3]
    assert _text(chart).startswith(weather_icon(0)[0] + "Morn")
    for period in PERIODS:
        assert weather_icon(period["code"])[0] in _text(chart)
    assert len(_text(chart)) == 30  # cut and padded to the column


def test_each_period_is_drawn_in_its_icon_colour():
    row = _periods_row(PERIODS, 30)
    assert row[2][1] == weather_icon(95)[1] and row[3][1] == weather_icon(95)[1]


def test_hours_win_over_periods_and_no_periods_keeps_the_empty_chart():
    with_hours = _day(periods=PERIODS, hours=[["2026-11-21T00:00", 20.0, 0, 0, 0], ["2026-11-21T01:00", 21.0, 0, 0, 0]])
    assert weather_icon(0)[0] not in _text(forecast_lines([with_hours], 30)[3])
    assert _text(forecast_lines([_day()], 30)[3]).strip() == "—"


def test_bad_periods_are_ignored():
    assert _periods_row([None, {"code": 1}, {"name": "  "}, "x"], 30) is None
    assert _text(forecast_lines([_day(periods="nonsense")], 30)[3]).strip() == "—"


def test_the_narrow_sidebar_shows_the_periods_too():
    lines = forecast_vertical_lines([_day(periods=PERIODS)], 28, 20)
    assert any(weather_icon(95)[0] in _text(line) for line in lines)
