"""Dim text on a dark or a light terminal background (PDCurses draws dim as a colour)."""

from __future__ import annotations

import copy
import curses
import os
import subprocess
import sys

import pytest

from terrascope.core import config
from terrascope.core.ui import colors
from terrascope.core.ui.colors import ColorManager
from terrascope.core.ui.constants import DIM_ATTR


class _FakeCurses:
    """Accepts colour pair calls without a terminal."""

    def init_pair(self, pair_id, fg, bg):
        pass

    def init_color(self, slot, r, g, b):
        raise curses.error("no palette changes in this test")

    @staticmethod
    def color_pair(pair_id):
        mask = curses.A_COLOR & 0xFFFFFFFF
        return pair_id << ((mask & -mask).bit_length() - 1)


@pytest.fixture
def fake_curses(monkeypatch):
    fake = _FakeCurses()
    monkeypatch.setattr(curses, "init_pair", fake.init_pair, raising=False)
    monkeypatch.setattr(curses, "init_color", fake.init_color, raising=False)
    monkeypatch.setattr(curses, "color_pair", fake.color_pair, raising=False)
    monkeypatch.setattr(curses, "COLORS", 256, raising=False)


def _manager(background: str) -> ColorManager:
    manager = ColorManager(background=background)
    manager.enabled = True
    return manager


def _dimmed_hex(manager: ColorManager, hex_color: str, background: str | None = None) -> str:
    """The foreground colour that DIM_ATTR produces for a cell drawn in hex_color."""
    attribute = manager.get_pair(hex_color, background)
    dimmed = manager.dimmed(attribute | DIM_ATTR)
    key = manager._key_by_pair[dimmed & curses.A_COLOR]
    return key.split("|", 1)[0]


def test_dim_fades_towards_black_on_a_dark_terminal(fake_curses):
    # Halfway from #203040 to black.
    assert _dimmed_hex(_manager("dark"), "#203040") == "#101820"


def test_dim_fades_towards_white_on_a_light_terminal(fake_curses):
    # Halfway from #203040 to white: lighter, so it stays readable on white.
    assert _dimmed_hex(_manager("light"), "#203040") == "#8f979f"


def test_dim_with_an_explicit_background_fades_towards_that_background(fake_curses):
    # The cell's own background wins over the terminal setting, on both.
    assert _dimmed_hex(_manager("dark"), "#ffffff", "#000000") == "#7f7f7f"
    assert _dimmed_hex(_manager("light"), "#ffffff", "#000000") == "#7f7f7f"


def test_background_defaults_to_the_config_value(monkeypatch):
    monkeypatch.setitem(colors.TERMINAL_CONFIG, "background", "dark")
    assert ColorManager().dim_target == (0, 0, 0)
    monkeypatch.setitem(colors.TERMINAL_CONFIG, "background", "light")
    assert ColorManager().dim_target == (255, 255, 255)


def test_background_setting_only_accepts_dark_or_light():
    for value in ("dark", "light"):
        candidate = copy.deepcopy(config.CFG)
        candidate["terminal"]["background"] = value
        config.validate_config(candidate)

    candidate = copy.deepcopy(config.CFG)
    candidate["terminal"]["background"] = "blue"
    with pytest.raises(config.ConfigError, match="terminal.background"):
        config.validate_config(candidate)


def test_background_flag_reaches_the_effective_config(tmp_path):
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "-m", "terrascope", "--lang", "en", "--background", "light", "--dump-config"],
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "background: light" in result.stdout
