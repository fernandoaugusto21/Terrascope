"""The basemap's key in the sidebar lists only what the map draws: the PROVINCES
switch and the province line where province borders can show (the MAP tab), the
capital and city lines where the basemap's place names show."""

from __future__ import annotations

from terrascope.core.i18n import _
from terrascope.layers.basemap.layer import BaseMapLayer


def _key(provinces_here: bool, show_places: bool) -> list[str]:
    layer = BaseMapLayer()
    layer.detailed = True
    layer.provinces_ready = True
    layer.provinces_here = provinces_here
    layer.show_places = show_places
    return [line.text for line in layer.legend_lines()]


def test_map_tab_keeps_the_whole_key():
    texts = _key(provinces_here=True, show_places=True)
    assert texts[:4] == [_("PROVINCES"), _("COUNTRY BORDER"), _("PROVINCE"), _("CAPITAL")]
    assert any(text.startswith(_("CITY")) for text in texts)


def test_a_tab_without_province_borders_or_place_names_has_no_key():
    # The BRASIL tab of a plugin: detailed, no basemap place names, and province
    # borders never drawn there (the switch would change nothing on the map).
    assert _key(provinces_here=False, show_places=False) == []


def test_place_names_without_province_borders():
    texts = _key(provinces_here=False, show_places=True)
    assert _("PROVINCES") not in texts and _("PROVINCE") not in texts
    assert texts[:2] == [_("COUNTRY BORDER"), _("CAPITAL")]


def test_province_borders_without_place_names():
    texts = _key(provinces_here=True, show_places=False)
    assert texts == [_("PROVINCES"), _("COUNTRY BORDER"), _("PROVINCE")]
