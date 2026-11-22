# Changelog

## Unreleased

- Add `LayerRender.line_layers`: more braille lines, each set in its own colour, drawn in the layer's turn before its `lines`. A layer can draw lines in several colours (one per road class, for example) and still sit under the outlines of a layer drawn after it, which markers could not do (they are drawn after every layer's lines).
- Add a play / pause button to the time slider: a layer whose `SliderSpec` sets `playing` gets a ▶ (■ while playing) after the caption, pressed with the mouse or the space key (`keys.slider_play`), which calls `Layer.toggle_slider_play()`. The glyphs are `ui.slider_play` and `ui.slider_pause`.
- Fix the basemap key in the sidebar listing what the map does not draw: on a tab other than MAP the PROVINCES switch changed nothing (province borders are only drawn on MAP), and a tab without the basemap's place names (`place_names: false`) still listed the capital and city colours. The key now shows only the lines the tab draws, and nothing when only the country border would be left (a plugin's BRASIL tab, for example).
- Fix the side panel's info box staying three rows high when it shows another layer's selection (a warning, a plugin layer's region) while the weather layer owns the panel: the box is sized from the selected layer's rows. `panel_layout_for` may take `info_rows=`; one without it still works.
- Fix weather layers sharing the cache file overwriting each other: each layer saved its whole in-memory snapshot, so one layer dropped the cities another had saved since, or brought back an old failed reading. A layer now merges only the cities it fetched into the file, tagged with its name, and a layer with `weather_sovereign = True` (a plugin's layer for its own region) is not written over by the others for the cities it fetches (for a day after its last reading; a failed fetch of the sovereign layer does not replace another layer's good reading). Two apps running at once can still overwrite each other.
- Fix "WEATHER UNAVAILABLE · RETRYING" staying on screen for good: it counted every city in the weather cache, so one failed city that no view labels any more (another tab's, or one read from the cache file) kept the notice on every tab although it was never retried. The notice and the retry now count only the cities the current view labels.
- Add `Layer.credits()`: a layer names the sources it shows now on their own lines above the tab's credits. The weather layer names the selected city's providers ("Weather of <city>: <sources>"), for sources whose terms ask to be named where their data shows. City labels now keep clear of every credit line and of the footer row (slider and scale bar), so a label no longer runs into the credits ("Open-Meteo" + "...reto").
- Show the parts of the day in the forecast box when a provider has no hourly values: a day's optional `periods` ([{"name", "code", "summary"}], e.g. morning, afternoon, night) replaces the empty hourly chart with each part's icon and name.
- Add `WeatherLayer.city_places(view)`: the places that may get a weather label, most important first. A subclass (for example a plugin layer) can give its own places; the label rules (selected first, overlap, screen edge, `max_labels`, one label per name) stay in the core. A place may have an unknown population, shown as N/A.
- Add weather providers: city weather comes from the providers that cover the place, asked by priority, with Open-Meteo as the last resort. Plugins register providers with the `terrascope.weather_providers` entry point; the current conditions and the forecast may come from different providers. The info box shows SOURCE and the forecast title names the forecast's provider; a provider's own words for the conditions are shown when it has them. The weather cache schema goes to 4, so cached cities are fetched again once.
- Add an optional `zoom_max` to a tab (built-in and plugin): the most zoomed-in level while that tab is active, up to 1024, so a regional tab can zoom in further than the world map.
- Draw coasts and country borders from Natural Earth 1:10m (`data.countries_detail_file`) from `map.zoom.detail_min` (16) on. The file is downloaded in the background the first time the view gets there; on failure the 1:50m outlines stay.
- Fill settings missing from the user's `default.yaml` (a copy made on the first launch) with the bundled defaults, so a setting added in a later version does not stop the app.
- Add `terminal.background` (`--background dark|light`): on Windows, dim text fades towards white on a light terminal instead of black, so it stays readable.
- Add an optional `view: {lat, lon, zoom}` to a tab: the map moves there each time the tab is opened, so a tab can start on its own region (built-in and plugin tabs).
- Add plugin entry points: installed packages can register layers (`terrascope.layers`) and top-row tabs (`terrascope.tabs`) without editing Terrascope. A broken plugin is skipped with a warning; `--list-layers` and `--list-tabs` show each entry's origin. See "Writing a plugin" in the README.
- Add translations (gettext) and Brazilian Portuguese (`pt_BR`): the interface, help, map labels, country names (from the downloaded file's `NAME_PT`), tab names and key texts follow the system language (`--lang`, `app.language`).
- Show the "Unknown" origin country of an aircraft translated in `pt_BR` (info box and country filter); the data and the filter values keep the English word.
- Add regional formats: 24 h clock, °C / km/h, decimal comma and `dd/mm/yyyy` dates in `pt_BR`, with `--time-format 12h` and `--units imperial` (or `app.time_format` / `app.units` in the config) to choose them explicitly (issue #24).
- Support Windows 10/11: `windows-curses` and `tzdata` are installed automatically on Windows, so the curses UI starts and the time zone selector lists every IANA zone.
- Fix mouse wheel zoom and drag-to-pan under PDCurses (`windows-curses`), which reports wheel and button-held motion events with an empty button state.
- Fix colours under PDCurses: the colour-pair budget was computed as 1 (every colour reused the first pair, losing the water/land fill), bold coloured text switched palette slots, and dim text was drawn at full brightness.
- Fix a layer switched off with `--disable-layer` still making requests at startup: `--disable-layer flights` fetched the OpenSky feed once anyway, using up its quota and showing HTTP 429 on the screen.
- Show the UTC offset instead of Windows' long localised zone name in the clock and the CLOCK panel.
- Build a standalone `windows_x86_64` zip with each release, with generated Scoop and winget manifests; add Windows to the CI matrix.
- Fix `--help` ignoring `app.language` in a `--config` file: the help now uses the language that file sets, after `--lang` and before the environment.

## 1.0.0

- First stable release of Terrascope.

## 0.2.3

- Handle malformed flight `last_contact` values and skip invalid cached history timestamps. (PR #8)
- Reject non-integer radar frame timestamps instead of failing later during rendering. (PR #9)
- Restrict search and country-filter shortcuts to the Planes tab, fixing the hidden modal freeze reported in issue #3.
- Update package-manager configuration: Homebrew reads the release version from `pyproject.toml` and supports `--HEAD`; the Arch recipe tracks `main` as `terrascope-git`.

## 0.2.1

- Switch the radar overlay to RainViewer's Weather Maps API.
- Improve weather forecast readability, chart sizing, and dynamic city details.
- Refine map footer spacing, panel controls, and weather error messages.
