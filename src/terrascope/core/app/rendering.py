"""Screen drawing and resize handling."""

from __future__ import annotations

from dataclasses import dataclass, field

from terrascope.core.i18n import _

from .shared import (
    COLOR_RESET_MIN_SECONDS,
    DIM_ATTR,
    MIN_TERMINAL_HEIGHT,
    MIN_TERMINAL_WIDTH,
    STATUS_OFFSET,
    TABS,
    TIMEZONE_KEY,
    TERMINAL_TOO_SMALL_TEXT,
    attribution_top_row,
    concise_error_message,
    current_time_text,
    curses,
    download_progress,
    draw_box,
    draw_dropdown,
    draw_info_box,
    draw_live_box,
    draw_map_box,
    draw_map_overlay_text,
    map_area_origin,
    draw_rich_box,
    draw_tab_bar,
    draw_text_box,
    draw_welcome_modal,
    dropdown_rect,
    safe_addstr,
    startup_progress,
    time
)

def _fit_statuses(messages: list[str], room: int) -> list[str]:
    """The status lines that fit in `room` rows. When they do not all fit, the
    last row says how many are left out instead, e.g. "+3"."""
    if len(messages) <= room:
        return list(messages)
    if room <= 0:
        return []
    kept = room - 1
    return [*messages[:kept], f"+{len(messages) - kept}"]

@dataclass(frozen=True)
class StatusLine:
    """One status line over the map: where, what, how, and the click areas it adds."""
    row: int
    x: int
    text: str
    attr: int
    status_hits: list = field(default_factory=list)   # (row, start, end, key, action)
    prompt_hits: list = field(default_factory=list)   # (row, start, end, yes?)

class RenderingMixin:

    def _plan_statuses(
        self, map_top: int, map_left: int, map_height: int, map_width: int, progress_items,
    ) -> list[StatusLine]:
        """The status lines drawn at the map's top-left, worked out before the map is
        drawn so that place labels can keep clear of them (a label cut by a status
        line read as a broken word, e.g. "[X]eira"). Each entry has the screen row,
        x, text and attributes, plus the click areas it adds. `progress_items` is the
        download_progress() snapshot of this frame."""
        if self.welcome_visible:
            return []
        offset_x, offset_y = STATUS_OFFSET
        active_files = {
            item.filename for item in progress_items if item.state == "downloading"
        }
        statuses = []
        radar_unavailable = False
        province_prompt = (
            TABS[self.active_tab].name == "map"
            and self.province_choice != "no"
            and (self.province_choice is None or self.province_state == "failed")
        )
        error_words = (_("FAILED"), _("UNAVAILABLE"), _("ERROR"))
        # A copy: worker callbacks may add a status while this frame is drawn.
        for key, message in list(self.map_statuses.items()):
            if key == "RADAR" and any(
                word in message.upper() for word in error_words
            ):
                radar_unavailable = True
                continue
            related = {
                "MAP": {"ne_50m_admin_0_countries.geojson"},
                "BORDERS": {"ne_10m_admin_1_states_provinces_lines.geojson"},
            }.get(key, set())
            if not related.intersection(active_files):
                statuses.append(message)
        progress_labels = {
            "LIVE AIRCRAFT": _("AIRCRAFT"),
            "WEATHER RADAR": _("RADAR"),
            "CITY WEATHER": _("CITY WEATHER"),
            "RADAR HISTORY": _("RADAR HISTORY"),
        }
        for item in progress_items:
            if item.state not in {"downloading", "failed"}:
                continue
            name = progress_labels.get(item.filename)
            if name is None:
                raw = item.filename.removeprefix("ne_").replace(".geojson", "")
                if "admin_0_countries" in raw:
                    name = _("COUNTRIES") + " " + ("10M" if "10m" in raw else "50M")
                elif "admin_1_states_provinces" in raw:
                    name = _("BORDERS") + " " + ("10M" if "10m" in raw else "50M")
                elif "populated_places" in raw:
                    name = _("PLACES") + " " + ("10M" if "10m" in raw else "50M")
                elif "airports" in raw:
                    name = _("AIRPORTS")
                else:
                    name = raw.replace("_", " ").upper()
            if item.state == "failed":
                if item.filename == "WEATHER RADAR":
                    radar_unavailable = True
                    continue
                detail = f": {concise_error_message(item.error, 42)}" if item.error else ""
                statuses.append(f"{_('DOWNLOAD')} {name} {_('FAILED')}{detail}")
                continue
            elif item.total:
                amount = f"{max(0, min(100, int(item.downloaded * 100 / item.total))):3d}%"
            else:
                amount = " ??%"
            statuses.append(f"{_('LOADING')} {name} {amount}")
        if self.map_error:
            statuses.append(self.map_error)
        for layer in self.world.active_layers():
            for message in layer.loading_messages():
                if _("RADAR UNAVAILABLE").upper() in message.upper():
                    radar_unavailable = True
                else:
                    statuses.append(message)
        if radar_unavailable and TABS[self.active_tab].name == "weather":
            statuses.append(_("RADAR UNAVAILABLE"))
        planned: list[StatusLine] = []
        first_status_row = map_top + offset_y
        if province_prompt and self.frame is not None:
            prefix = _("STATE/PROVINCE BORDERS (~25MB)?  ")
            yes_text = _("[Y YES]")
            gap = "   "
            no_text = _("[N NO]")
            x = map_left + offset_x
            yes_left = x + len(prefix)
            no_left = yes_left + len(yes_text) + len(gap)
            planned.append(StatusLine(
                first_status_row, x, prefix + yes_text + gap + no_text, curses.A_BOLD,
                prompt_hits=[
                    (first_status_row, yes_left, yes_left + len(yes_text), True),
                    (first_status_row, no_left, no_left + len(no_text), False),
                ],
            ))
            first_status_row += 1
        unique_statuses = [
            message for message in dict.fromkeys(statuses)
            if message not in self.dismissed_statuses
            and not (self.province_choice == "no" and _("BORDERS") in message)
        ]
        # The status lines stop above the credits drawn at the map's bottom-left.
        status_room = attribution_top_row(
            map_top, map_height, TABS[self.active_tab].attribution, getattr(self, "_frame_credits", ())
        ) - first_status_row
        for index, message in enumerate(_fit_statuses(unique_statuses, status_room)):
            row = first_status_row + index
            status_key = message
            for marker in (_("FAILED:"), _("UNAVAILABLE:")):
                if marker in message:
                    prefix, detail = message.split(marker, 1)
                    message = f"{prefix}{marker} {concise_error_message(detail, 40)}"
                    break
            is_error = any(word in message.upper() for word in error_words)
            retryable = is_error and _("BORDERS") in message.upper()
            hits = []
            if message == _("RADAR UNAVAILABLE"):
                available = max(0, map_width - offset_x * 2)
                prefix = _("RADAR UNAVAILABLE")
                retry_text = _(" [R RETRY]") if self.radar_status_expanded else ""
                toggle_text = " [-]" if self.radar_status_expanded else " [+]"
                shown = (prefix + retry_text + toggle_text)[:available]
                control_x = map_left + offset_x + len(prefix)
                if self.radar_status_expanded:
                    if control_x + len(retry_text) <= map_left + offset_x + available:
                        hits.append((row, control_x + 1, control_x + len(retry_text), status_key, "retry-radar"))
                    control_x += len(retry_text)
                if control_x + len(toggle_text) <= map_left + offset_x + available:
                    hits.append((row, control_x + 1, control_x + len(toggle_text), status_key, "toggle-radar-status"))
                planned.append(StatusLine(row, map_left + offset_x, shown, curses.A_BOLD, status_hits=hits))
                continue
            suffix = " [R] [X]" if retryable else " [X]" if is_error else ""
            available = max(0, map_width - offset_x * 2)
            shown = message[: max(0, available - len(suffix))] + suffix
            if self.frame is None:
                continue
            if is_error and suffix:
                start = map_left + offset_x + len(shown) - 3
                hits.append((row, start, start + 3, status_key, "dismiss"))
                if retryable:
                    retry_start = map_left + offset_x + len(shown) - 7
                    hits.append((row, retry_start, retry_start + 3, status_key, "retry-provinces"))
            planned.append(StatusLine(
                row, map_left + offset_x, shown, curses.A_BOLD if is_error else DIM_ATTR, status_hits=hits,
            ))
        return planned

    def _layer_credits(self) -> list[str]:
        """The credit lines of the layers that are on (see Layer.credits). A
        plugin's credits() that fails or returns something odd adds nothing; one
        string is one line. Duplicates are dropped by attribution_lines."""
        lines: list[str] = []
        for layer in self.world.layers:
            if not getattr(layer, "enabled", False):
                continue
            credits = getattr(layer, "credits", None)
            if not callable(credits):
                continue
            try:
                given = credits()
            except Exception:  # a plugin bug must not stop the drawing
                continue
            if isinstance(given, str):
                given = [given]
            if isinstance(given, (list, tuple)):
                lines.extend(line for line in given if isinstance(line, str))
        return lines

    def draw(self) -> None:
        self.stdscr.erase()
        if (
            self.colors.exhausted
            and time.monotonic() - self._colors_reset_at > COLOR_RESET_MIN_SECONDS
        ):
            # The previous frame ran out of colour pairs: free them all and
            # rebuild just what is on screen now.
            self.colors.reset()
            self._colors_reset_at = time.monotonic()
        height, width = self.stdscr.getmaxyx()
        if (
            width < MIN_TERMINAL_WIDTH
            or height < MIN_TERMINAL_HEIGHT
        ):
            safe_addstr(self.stdscr, 0, 0, TERMINAL_TOO_SMALL_TEXT)
            self.stdscr.refresh()
            return
        layout = self.layout(height, width)
        map_top, map_left, map_height, map_width = layout.map
        self._controls_layout = None
        if layout.tabs is not None:
            clock_text = current_time_text(self.selected_timezone)
            if TABS[self.active_tab].name == "time":
                clock_text = f"{TIMEZONE_KEY} {_('TZ')} {clock_text}"
            self._controls_layout = draw_tab_bar(
                self.stdscr,
                layout.tabs,
                TABS,
                self.active_tab,
                self.colors,
                self.controls_expanded,
                clock_text,
                self.panel_orientation,
            )
        frame_size = (map_width - 4, map_height - 2)
        self.apply_pending_home_view(*frame_size)
        if self._frame_size != frame_size:
            self.world.dirty = True
        if self.frame is None or self.world.needs_render():
            self.frame = self.world.render(*frame_size)
            self._frame_size = frame_size
        progress_items = download_progress()   # one snapshot for the whole frame
        self._frame_credits = self._layer_credits()   # the same credits for the statuses and the map
        planned_statuses = self._plan_statuses(map_top, map_left, map_height, map_width, progress_items)
        # Map-area cells (row, first col, end col) of the status lines, one cell wider on
        # each side: a label must not touch them, nor start right against them.
        area_top, area_left = map_area_origin(map_top, map_left)
        status_cells = [
            (line.row - area_top, line.x - area_left - 1, line.x - area_left + len(line.text) + 1)
            for line in planned_statuses
        ]
        self._legend_hits = draw_map_box(
            self.stdscr,
            map_top,
            map_left,
            map_height,
            map_width,
            self.frame,
            self.colors,
            self.world.zoom,
            self.world.center_lat,
            panel_visible=self.panel_visible,
            panel_button=self.panel_allowed(),
            slider=self._slider_spec(),
            attribution=TABS[self.active_tab].attribution,
            credits=self._frame_credits,
            keep_clear=status_cells,
            legend=[
                line
                for layer in self.world.layers
                if layer.enabled
                for line in layer.legend_lines()
            ],
        )
        owner = self.panel_owner()
        if owner is not None and owner.name == "weather":
            selected = owner.selected
            city_key = selected.get("key") if isinstance(selected, dict) and "key" in selected else None
            if city_key != self._forecast_city_key:
                self.forecast_scroll = 0
                self._forecast_city_key = city_key
        for box, rect in layout.boxes:
            if box.kind == "info":
                selected = self.world.selected_layer if self.info_visible else None
                draw_info_box(
                    self.stdscr,
                    *rect,
                    selected,
                    self.world.selection_position,
                    self.colors,
                )
            elif box.kind == "search":
                draw_text_box(
                    self.stdscr, rect, box.title or _("SEARCH"), self.search_box_lines(box.hint)
                )
            elif box.kind == "filter":
                draw_text_box(
                    self.stdscr, rect, box.title or _("FILTER"),
                    self.filter_box_lines(box.hint, rect[2] - 3),
                )
            elif box.kind == "live" and owner is not None:
                draw_live_box(
                    self.stdscr, rect, _(box.title or ""), owner.live_rows(box.title)
                )
            elif box.kind == "rich" and owner is not None:
                title = owner.rich_title(box.title)
                if self.panel_orientation == "vertical" and owner.name == "weather":
                    title = f"{title} · {_('SCROLL')}"
                draw_rich_box(
                    self.stdscr,
                    rect,
                    title,
                    owner.rich_lines(
                        box.title,
                        max(0, rect[3] - 4),
                        max(0, rect[2] - 3),
                        vertical=self.panel_orientation == "vertical",
                        scroll=self.forecast_scroll,
                    ),
                    self.colors,
                )
        self._province_prompt_hits = []
        self._status_hits = []
        for line in planned_statuses:
            draw_map_overlay_text(
                self.stdscr, layout.map, self.frame, self.colors, line.row, line.x, line.text, line.attr,
            )
            self._status_hits.extend(line.status_hits)
            self._province_prompt_hits.extend(line.prompt_hits)

        self._dropdown_layout = None
        if self.tz_dropdown_open:
            if self._controls_layout is not None and layout.tabs is not None:
                tabs_top = layout.tabs[0]
                anchor_right = self._controls_layout.datetime_x + self._controls_layout.datetime_width
                rect = dropdown_rect(tabs_top + 1, anchor_right, height, width)
                self._dropdown_layout = draw_dropdown(
                    self.stdscr,
                    rect,
                    self.selected_timezone,
                    self.colors,
                    self.tz_query,
                    self.tz_index,
                )
            else:
                self.tz_dropdown_open = False  # the clock it hangs from is off screen

        self._welcome_rect = None
        self._welcome_link = None
        self._welcome_button = None
        self._welcome_province_yes = None
        self._welcome_province_no = None
        if self.welcome_visible:
            (
                self._welcome_rect,
                self._welcome_link,
                self._welcome_button,
                self._welcome_province_yes,
                self._welcome_province_no,
            ) = draw_welcome_modal(
                self.stdscr, height, width, self.colors, progress_items,
                startup_status=startup_progress(),
                province_prompt=(self.province_choice != "yes" or self.province_state == "failed"),
            )

        self.stdscr.refresh()

    def draw_resize_cover(self) -> None:
        """Placeholder shown while the terminal is being resized, instead of the
        map reflowing and tearing under the drag."""
        height, width = self.stdscr.getmaxyx()
        self.stdscr.erase()
        text = f" {_('RESIZING')}  {width} \u00d7 {height} "
        box_width = len(text) + 4
        box_height = 3
        if width > box_width + 1 and height > box_height + 1:
            top = (height - box_height) // 2
            left = (width - box_width) // 2
            draw_box(self.stdscr, top, left, box_height, box_width, "")
            safe_addstr(self.stdscr, top + 1, left + 2, text, curses.A_BOLD)
        else:
            safe_addstr(self.stdscr, 0, 0, f"{width}x{height}")
        self.stdscr.clearok(True)  # wipe whatever the terminal reflowed
        self.stdscr.refresh()
