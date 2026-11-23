# wrap.py — WRAPPING OF VALUE TEXT IN THE SIDE PANELS
# Responsible for: wrap_value(), the line breaking of a box's value text (the
# info boxes of the layers, their panel_layout_for() height, the modal bodies).
# It breaks at spaces only, and never between a number and the unit that follows
# it ("16,0 mm", "22–32 °C", "21,9 °C", "3 h"), so a value never shows a number
# on one line and its unit on the next. A word longer than the width is cut.
# Edit this file to: change which words count as units, or the breaking rules.
# Not here: drawing the boxes (dialogs.py), the layers' text (the layers).

from __future__ import annotations

import re

# A word that is a unit of measure or a degree / percent sign. A letter unit must
# not be followed by another letter, so "mín" is not "m" and "horas" not "h". The
# single capitals (A, V, W) are left out: "20:21 A ..." is an article, not an amp.
_UNIT_WORD = re.compile(
    r"(?:[°º%‰]|(?:mm|cm|km|m|h|min|s|kt|mi|ft|mph|hPa|dBZ|kWh)(?![^\W\d_]))"
)

def _unbreakable_groups(words: list[str]) -> list[str]:
    """Join each word to the one before it when that word ends with a digit and
    this one is a unit: the space between them is not a break point."""
    groups: list[str] = []
    for word in words:
        if groups and groups[-1][-1:].isdigit() and _UNIT_WORD.match(word):
            groups[-1] = f"{groups[-1]} {word}"
        else:
            groups.append(word)
    return groups

def wrap_value(text: str, width: int) -> list[str]:
    """`text` as lines of at most `width` cells, breaking at spaces only (see the
    module header). Always at least one line (an empty one for empty text)."""
    width = max(1, int(width))
    lines: list[str] = []
    current = ""
    for group in _unbreakable_groups(str(text).split()):
        if len(group) > width:
            # Too long to keep whole: fall back to its own words, breaking between them.
            pieces = group.split(" ")
        else:
            pieces = [group]
        for piece in pieces:
            while len(piece) > width and not current:
                lines.append(piece[:width])
                piece = piece[width:]
            if not current:
                current = piece
            elif len(current) + 1 + len(piece) <= width:
                current = f"{current} {piece}"
            else:
                lines.append(current)
                current = piece
                while len(current) > width:
                    lines.append(current[:width])
                    current = current[width:]
    if current or not lines:
        lines.append(current)
    return lines
