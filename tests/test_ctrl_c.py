"""Ctrl+C ends terrascope quietly (no traceback) and the way the platform expects."""

from __future__ import annotations

import os
import signal
import types

import pytest

from terrascope.core import cli
from terrascope.core.app.runtime import RuntimeMixin
from terrascope.core.app.shared import KEYS


def test_ctrl_c_during_startup_ends_as_an_interrupt(monkeypatch):
    ended = []
    monkeypatch.setattr(cli, "exit_interrupted", lambda: ended.append(True))

    def interrupted(argv):
        raise KeyboardInterrupt  # Ctrl+C while the first options are read

    monkeypatch.setattr(cli, "_early_options", interrupted)
    cli.run()  # no traceback: the interrupt is handled
    assert ended == [True]


def test_other_errors_are_not_swallowed(monkeypatch):
    def broken(argv):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "_early_options", broken)
    with pytest.raises(RuntimeError):
        cli.run()


@pytest.mark.skipif(os.name != "nt", reason="Windows exit status")
def test_windows_exit_status_is_the_ctrl_c_one():
    with pytest.raises(SystemExit) as stop:
        cli.exit_interrupted()
    assert stop.value.code == cli.WINDOWS_CTRL_C_EXIT == 0xC000013A


@pytest.mark.skipif(os.name != "posix", reason="POSIX signal")
def test_posix_kills_itself_with_sigint(monkeypatch):
    sent = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: sent.append((pid, sig)))
    monkeypatch.setattr(signal, "signal", lambda sig, handler: None)
    with pytest.raises(SystemExit):
        cli.exit_interrupted()
    assert sent == [(os.getpid(), signal.SIGINT)]


class _App(RuntimeMixin):
    """RuntimeMixin.run() with a recording setup / loop and stub terminal."""

    def __init__(self, fail_in):
        self.fail_in = fail_in
        self.restored = []
        self.stdscr = types.SimpleNamespace(clear=lambda: None, refresh=lambda: None)
        self.colors = types.SimpleNamespace(restore=lambda: self.restored.append("palette"))

    def setup(self):
        if self.fail_in == "setup":
            raise KeyboardInterrupt

    def _loop(self):
        if self.fail_in == "loop":
            raise KeyboardInterrupt

    def restore_stderr(self):
        self.restored.append("stderr")


@pytest.mark.parametrize("fail_in", ["setup", "loop"])
def test_the_terminal_is_restored_when_ctrl_c_hits_setup_or_the_loop(fail_in):
    app = _App(fail_in)
    with pytest.raises(KeyboardInterrupt):
        app.run()
    assert app.restored == ["palette", "stderr"]


@pytest.mark.parametrize("welcome", [False, True])
@pytest.mark.parametrize("mode", ["normal", "search"])
def test_ctrl_c_as_a_key_stops_from_anywhere_as_an_interrupt(welcome, mode):
    from terrascope.core.app.input import InputMixin

    app = types.SimpleNamespace(running=True, interrupted=False, welcome_visible=welcome, mode=mode,
                                tz_dropdown_open=False, _drag=None)
    InputMixin.handle_key(app, 3)
    assert 3 in KEYS["interrupt"]
    assert app.running is False and app.interrupted is True


def test_launch_turns_an_interrupted_app_into_keyboard_interrupt(monkeypatch):
    import curses

    from terrascope.core import main

    monkeypatch.setattr(curses, "wrapper", lambda function, *args: True)  # _main returned "interrupted"
    with pytest.raises(KeyboardInterrupt):
        main.launch([], set())
    monkeypatch.setattr(curses, "wrapper", lambda function, *args: False)
    main.launch([], set())
