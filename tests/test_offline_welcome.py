"""Offline start with an empty cache: the first-run card ends on a final state
instead of QUEUED at 0%, and Esc leaves it for the (empty) map."""

from __future__ import annotations

import types

import pytest

from terrascope.core import i18n, mapdata
from terrascope.core.app.input import InputMixin
from terrascope.core.ui.dialogs import draw_welcome_modal
from terrascope.core.world import WorldMap

COLORS = types.SimpleNamespace(get_pair=lambda *_args: 0)


class FakeWindow:
    """Records what the card would draw as (row, column, text)."""

    def __init__(self, height: int, width: int) -> None:
        self.height = height
        self.width = width
        self.drawn: list[tuple[int, int, str]] = []

    def getmaxyx(self):
        return self.height, self.width

    def addstr(self, y, x, text, attributes=0):
        self.drawn.append((y, x, text))

    def addnstr(self, y, x, text, count, attributes=0):
        self.drawn.append((y, x, text[:count]))


@pytest.fixture
def empty_offline_cache(tmp_path, monkeypatch):
    """Offline, with an empty cache directory and a fresh progress table."""
    i18n.activate("en")
    monkeypatch.setattr(mapdata, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(mapdata, "FETCH_NEW_DATA_FROM_API", False)
    monkeypatch.setattr(mapdata, "_DOWNLOAD_PROGRESS", {
        key: mapdata.DownloadProgress(item.filename)
        for key, item in mapdata._DOWNLOAD_PROGRESS.items()
    })
    yield
    i18n.activate("en")


def _try_offline_download(filename: str) -> None:
    with pytest.raises(mapdata.MapDataError, match="offline mode"):
        mapdata.download_map(filename)


def test_offline_download_without_cache_ends_as_unavailable(empty_offline_cache):
    _try_offline_download(mapdata.MAP_FILE)

    step, _percent, state, error = mapdata.startup_progress()
    assert (step, state, error) == (mapdata.MAP_FILE, "unavailable", "")


def test_no_offline_map_file_is_left_waiting(empty_offline_cache):
    _try_offline_download(mapdata.MAP_FILE)
    _try_offline_download(mapdata.PLACES_FILE)

    states = {item.filename: item.state for item in mapdata.download_progress()}
    assert states[mapdata.MAP_FILE] == "unavailable"
    assert states[mapdata.PLACES_FILE] == "unavailable"


@pytest.mark.parametrize(
    "language, headline",
    [
        ("en", "OFFLINE, NO CACHE  /  WORLD MAP"),
        ("pt_BR", "OFFLINE, SEM CACHE  /  MAPA-MÚNDI"),
    ],
)
def test_welcome_card_shows_the_final_state_not_queued(empty_offline_cache, language, headline):
    _try_offline_download(mapdata.MAP_FILE)
    i18n.activate(language)

    window = FakeWindow(40, 120)
    draw_welcome_modal(
        window, 40, 120, COLORS, mapdata.download_progress(),
        startup_status=mapdata.startup_progress(),
    )

    shown = [text for _row, _col, text in window.drawn]
    assert any(headline in text for text in shown), shown
    assert not any("QUEUED" in text or "NA FILA" in text for text in shown), shown


class _Welcome(InputMixin):
    """Only the attributes that handle_key() reads while the welcome card is open."""

    def __init__(self, world: WorldMap) -> None:
        self.world = world
        self.welcome_visible = True
        self.running = True
        self._drag = None
        self._welcome_province_yes = None
        self._welcome_province_no = None


def test_esc_leaves_the_card_for_the_empty_map(empty_offline_cache):
    _try_offline_download(mapdata.MAP_FILE)
    world = WorldMap([], [])
    app = _Welcome(world)

    app.handle_key(27)  # Esc

    assert app.welcome_visible is False
    assert app.running is True
    assert world.render(80, 24) is not None  # the map draws with no countries loaded
