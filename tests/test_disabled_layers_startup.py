"""Layers switched off with --disable-layer make no request, not even the startup warm-up.

core/main.py runs every startup stage in a background thread. These tests run that
real sequence (core.main._main, without curses) with urlopen replaced by a recorder
that fails every request, then check which feed hosts were asked for.
"""

from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request
from unittest import mock

import pytest

from terrascope.core import main as core_main
from terrascope.core.app import TerrascopeApp
from terrascope.core.registry import build_layers

OPENSKY_HOST = "opensky-network.org"
WEATHER_HOSTS = ("api.open-meteo.com", "api.rainviewer.com", "earthquake.usgs.gov")


class _InlineThread:
    """Runs the startup thread's target at once, so the whole sequence has run before _main returns."""

    def __init__(self, target=None, args=(), name=None, daemon=None, **_) -> None:
        self._target = target
        self._args = args

    def start(self) -> None:
        self._target(*self._args)


@pytest.fixture
def startup(monkeypatch):
    """Return run(disabled): start the app with those layers switched off, as cli.py does,
    and give back the layers plus every URL requested while it started."""
    # Live requests on, whatever the test machine's config or terrascope_OFFLINE says.
    for name, module in list(sys.modules.items()):
        if name.startswith("terrascope") and hasattr(module, "FETCH_NEW_DATA_FROM_API"):
            monkeypatch.setattr(module, "FETCH_NEW_DATA_FROM_API", True)

    requested: list[str] = []

    def no_network(request, timeout=None):
        requested.append(request.full_url if hasattr(request, "full_url") else str(request))
        raise urllib.error.URLError("no network in tests")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    monkeypatch.setattr(core_main, "Thread", _InlineThread)
    monkeypatch.setattr(TerrascopeApp, "run", lambda self: None)

    def run(disabled: set[str]):
        layers = build_layers()
        for layer in layers:
            if layer.name in disabled:
                layer.enabled = False
        core_main._main(mock.MagicMock(), layers, frozenset(disabled))
        return layers, requested

    return run


def _requests_to(urls: list[str], hosts: tuple[str, ...]) -> list[str]:
    return [url for url in urls if any(host in url for host in hosts)]


def test_startup_reaches_the_live_feeds_when_nothing_is_disabled(startup):
    # Control: proves the harness sees the real feeds, so the empty results below mean something.
    _, requested = startup(set())
    assert len(_requests_to(requested, (OPENSKY_HOST,))) == 1
    assert _requests_to(requested, ("api.rainviewer.com",))


@pytest.mark.parametrize(
    ("layer_name", "hosts"),
    [("flights", (OPENSKY_HOST,)), ("weather", WEATHER_HOSTS)],
)
def test_switched_off_layer_requests_nothing_from_its_feeds(startup, layer_name, hosts):
    _, requested = startup({layer_name})
    assert _requests_to(requested, hosts) == []


def test_switched_off_flights_fetch_once_switched_on(startup):
    layers, requested = startup({"flights"})
    flights = next(layer for layer in layers if layer.name == "flights")
    before = len(_requests_to(requested, (OPENSKY_HOST,)))

    flights.toggle()  # the layer's own toggle key
    flights.tick()
    deadline = time.monotonic() + 5
    while flights.refresh_in_progress and time.monotonic() < deadline:
        time.sleep(0.01)

    assert len(_requests_to(requested, (OPENSKY_HOST,))) > before
