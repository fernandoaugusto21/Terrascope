"""Ctrl+C ends terrascope quietly: exit status 130 and no traceback."""

from __future__ import annotations

import types

import pytest

from terrascope.core import cli


def test_ctrl_c_while_the_map_runs_exits_with_130_after_the_cleanup(monkeypatch):
    # As curses.wrapper does: the terminal is restored (finally) before the
    # KeyboardInterrupt from time.sleep() in the main loop reaches run().
    cleaned = []

    def interrupted_run():
        try:
            raise KeyboardInterrupt
        finally:
            cleaned.append(True)

    monkeypatch.setattr(cli, "_run", interrupted_run)
    with pytest.raises(SystemExit) as stop:
        cli.run()
    assert cleaned == [True]
    assert stop.value.code == cli.INTERRUPTED_EXIT_CODE == 130


def test_ctrl_c_during_startup_exits_with_130(monkeypatch):
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_run", interrupted)
    with pytest.raises(SystemExit) as stop:
        cli.run()
    assert stop.value.code == 130


def test_other_errors_are_not_swallowed(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "_run", broken)
    with pytest.raises(RuntimeError):
        cli.run()


@pytest.mark.parametrize("welcome", [False, True])
@pytest.mark.parametrize("mode", ["normal", "search"])
def test_ctrl_c_as_a_key_quits_from_anywhere(welcome, mode):
    from terrascope.core.app.input import CTRL_C_KEY, InputMixin

    app = types.SimpleNamespace(running=True, welcome_visible=welcome, mode=mode,
                                tz_dropdown_open=False, _drag=None)
    InputMixin.handle_key(app, CTRL_C_KEY)
    assert app.running is False
