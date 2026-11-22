"""The slider's play / pause button: drawn one cell after the caption field when a
layer's SliderSpec sets `playing`, and pressed with the mouse or the slider_play key."""

from __future__ import annotations

import types

from terrascope.core.app.input import InputMixin
from terrascope.core.layer import SliderSpec
from terrascope.core.ui.constants import SLIDER_CAPTION_WIDTH
from terrascope.core.ui.map import slider_play_column, slider_track


def test_no_button_unless_the_layer_asks_for_one():
    spec = SliderSpec("RADAR", 7, 6, "LIVE", wide=True)
    assert slider_play_column(spec, 120, None, 0.0) is None
    assert slider_play_column(SliderSpec("RADAR", 7, 6, wide=True, playing=False, disabled=True), 120, None, 0.0) is None


def test_the_button_sits_after_the_caption_field():
    spec = SliderSpec("RADAR", 7, 6, "LIVE", wide=True, playing=False)
    first, length = slider_track(spec, 120, None, 0.0)
    assert slider_play_column(spec, 120, None, 0.0) == first + length + 1 + SLIDER_CAPTION_WIDTH


class _Layer:
    def __init__(self, playing):
        self.playing = playing
        self.pressed = 0

    def slider(self):
        return SliderSpec("RADAR", 7, 6, wide=True, playing=self.playing)

    def toggle_slider_play(self):
        self.pressed += 1


def _app(layer):
    app = InputMixin.__new__(InputMixin)
    app.world = types.SimpleNamespace(slider_layer=lambda: layer)
    return app


def test_the_key_presses_the_button():
    layer = _Layer(playing=False)
    _app(layer)._toggle_slider_play()
    assert layer.pressed == 1


def test_the_key_does_nothing_without_a_button():
    layer = _Layer(playing=None)
    _app(layer)._toggle_slider_play()
    assert layer.pressed == 0
