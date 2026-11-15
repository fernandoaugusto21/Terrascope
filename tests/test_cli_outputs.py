"""Translated output of the information commands (--list-layers, --list-tabs,
--list-keys, --show-paths, --clear-cache) and the CLI's validation errors
(core/cli.py). English output must not change."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

import pytest

from terrascope.core import cli, config, i18n, plugins


@pytest.fixture
def language():
    yield
    i18n.activate("en")


class FakeLayer:
    def __init__(self, name, enabled, toggle_key, origin):
        self.name = name
        self.enabled = enabled
        self.toggle_key = toggle_key
        self.origin = origin


# --- in-process: information commands -------------------------------------------------

def test_layer_list_in_portuguese(language, capsys):
    i18n.activate("pt_BR")
    cli.print_layer_list([FakeLayer("planes", True, "p", "built-in"),
                          FakeLayer("demo", False, "", "plugin:demo-dist")])
    assert capsys.readouterr().out == "planes\tligado\tP\tintegrado\ndemo\tdesligado\t-\tplugin:demo-dist\n"


def test_layer_list_in_english_is_unchanged(language, capsys):
    i18n.activate("en")
    cli.print_layer_list([FakeLayer("planes", True, "p", "built-in"),
                          FakeLayer("demo", False, "", "plugin:demo-dist")])
    assert capsys.readouterr().out == "planes\ton\tP\tbuilt-in\ndemo\toff\t-\tplugin:demo-dist\n"


def test_tab_list_translates_native_and_plugin_blurbs(entry_points, fake_entry_point, language, capsys):
    provided = [{"name": "demo", "label": "DEMO", "color": "#123456",
                 "blurb": "live aircraft", "layers": ["basemap"]}]
    entry_points[plugins.TAB_GROUP] = [fake_entry_point("demo", lambda: provided)]
    i18n.activate("pt_BR")
    cli.print_tab_list()
    out = capsys.readouterr().out
    assert "the plain world map" not in out
    assert "*1\tmap\tbasemap\to mapa-múndi simples" in out
    assert "\tintegrado\n" in out
    assert "aeronaves ao vivo\tplugin:terrascope-demo\n" in out


def test_tab_list_in_english_is_unchanged(entry_points, language, capsys):
    i18n.activate("en")
    cli.print_tab_list()
    first = capsys.readouterr().out.splitlines()[0]
    assert first == ("*1\tmap\tbasemap\tthe plain world map (zoom in for state / province borders "
                     "and detailed cities)\tbuilt-in")


def test_key_list_in_portuguese(language, capsys):
    i18n.activate("pt_BR")
    cli.print_key_list()
    out = capsys.readouterr().out
    assert "sair" in out  # quit
    assert "alternar painel" in out  # toggle panel
    assert "selecionar aba" in out
    assert "arrastar = mover, roda = zoom, clique = selecionar" in out
    assert "quit" not in out


def test_key_list_in_english_is_unchanged(language, capsys):
    i18n.activate("en")
    cli.print_key_list()
    out = capsys.readouterr().out
    assert "quit" in out
    assert "toggle panel" in out
    assert "drag = pan, wheel = zoom, click = select" in out


def test_every_key_action_name_is_in_the_catalogue_list():
    """Each action of app.keys is translated by --list-keys through KEY_ACTION_TEXTS,
    so pybabel extract must see it."""
    listed = set(cli.KEY_ACTION_TEXTS)
    for action in config.CFG["app"]["keys"]:
        assert action.replace("_", " ") in listed, action


def test_paths_in_portuguese_are_aligned(language, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "LOADED_FILES", [tmp_path / "a.yaml", tmp_path / "b.yaml"])
    monkeypatch.setattr(config, "FETCH_NEW_DATA_FROM_API", False)
    i18n.activate("pt_BR")
    cli.print_paths()
    lines = capsys.readouterr().out.splitlines()
    column = max(len(label) for label in ("pasta do cache", "arquivo de log",
                                          "arquivos de config", "requisições ao vivo")) + 1
    assert lines[0] == "pasta do cache".ljust(column) + str(tmp_path)
    assert lines[1] == "arquivo de log".ljust(column) + str(tmp_path / config.CFG["app"]["log_file"])
    assert lines[2] == "arquivos de config".ljust(column) + str(tmp_path / "a.yaml")
    assert lines[3] == " " * column + str(tmp_path / "b.yaml")
    assert lines[4] == "requisições ao vivo".ljust(column) + "desligado (offline)"


def test_paths_in_english_keep_the_previous_layout(language, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "LOADED_FILES", [tmp_path / "a.yaml", tmp_path / "b.yaml"])
    monkeypatch.setattr(config, "FETCH_NEW_DATA_FROM_API", False)
    i18n.activate("en")
    cli.print_paths()
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == f"cache dir      {tmp_path}"
    assert lines[2] == f"config files   {tmp_path / 'a.yaml'}"
    assert lines[3] == " " * 15 + str(tmp_path / "b.yaml")
    assert lines[4] == "live requests  off (offline)"


def test_clear_cache_messages_in_portuguese(language, monkeypatch, tmp_path, capsys):
    cache = tmp_path / "cache"
    monkeypatch.setattr(config, "CACHE_DIR", cache)
    i18n.activate("pt_BR")

    cli.clear_cache()
    assert capsys.readouterr().out == f"nada a limpar: {cache} não existe\n"

    cache.mkdir()
    (cache / "a.geojson").write_text("x", encoding="utf-8")
    (cache / "b.tmp").write_text("y", encoding="utf-8")
    cli.clear_cache()
    assert capsys.readouterr().out == f"Removidos 2 itens do cache de {cache}\n"

    (cache / "c.geojson").write_text("z", encoding="utf-8")
    cli.clear_cache()
    assert capsys.readouterr().out == f"Removido 1 item do cache de {cache}\n"


def test_clear_cache_messages_in_english(language, monkeypatch, tmp_path, capsys):
    cache = tmp_path / "cache"
    monkeypatch.setattr(config, "CACHE_DIR", cache)
    i18n.activate("en")

    cache.mkdir()
    (cache / "a.geojson").write_text("x", encoding="utf-8")
    cli.clear_cache()
    assert capsys.readouterr().out == f"removed 1 cached item from {cache}\n"


# --- in-process: validation errors -------------------------------------------------------

@pytest.mark.parametrize("parse, text, message", [
    (cli.INT, "x", "'x' não é um inteiro"),
    (cli.FLOAT, "abc", "'abc' não é um número"),
    (cli.FLOAT, "nan", "'nan' não é um número finito"),
    (cli.POS_INT, "0", "deve ser >= 1"),
    (cli.NONNEG_INT, "-1", "deve ser >= 0"),
    (cli._number(float, 0, 1), "2", "deve ser <= 1"),
    (cli._color, "red", "'red' não é uma cor como #rrggbb"),
    (cli._color_alpha, "red", "'red' não é uma cor como #rrggbb ou #rrggbbaa (ou 'none')"),
    (cli._pair, "1", "'1' não são dois inteiros como 2,1"),
    (cli._pair, "-1,2", "os valores devem ser >= 0"),
])
def test_value_errors_in_portuguese(language, parse, text, message):
    i18n.activate("pt_BR")
    with pytest.raises(argparse.ArgumentTypeError) as caught:
        parse(text)
    assert str(caught.value) == message


@pytest.mark.parametrize("parse, text, message", [
    (cli.INT, "x", "'x' is not an integer"),
    (cli.POS_INT, "0", "must be >= 1"),
    (cli._color, "red", "'red' is not a colour like #rrggbb"),
    (cli._pair, "-1,2", "values must be >= 0"),
])
def test_value_errors_in_english_are_unchanged(language, parse, text, message):
    i18n.activate("en")
    with pytest.raises(argparse.ArgumentTypeError) as caught:
        parse(text)
    assert str(caught.value) == message


# --- real command runs -----------------------------------------------------------------

def _run(args, tmp_path, lang_env=None):
    env = dict(os.environ)
    for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG", "terrascope_CONFIG", "terrascope_LOCALE_DIR"):
        env.pop(name, None)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(lang_env or {})
    return subprocess.run(
        [sys.executable, "-m", "terrascope", *args],
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=120,
    )


def test_list_tabs_command_in_portuguese(tmp_path):
    result = _run(["--lang", "pt_BR", "--list-tabs"], tmp_path)
    assert result.returncode == 0, result.stderr
    assert "o mapa-múndi simples" in result.stdout
    assert "integrado" in result.stdout
    assert "the plain world map" not in result.stdout


def test_list_tabs_command_in_english(tmp_path):
    result = _run(["--lang", "en", "--list-tabs"], tmp_path)
    assert result.returncode == 0, result.stderr
    assert "the plain world map" in result.stdout
    assert "built-in" in result.stdout


def test_list_layers_command_in_portuguese(tmp_path):
    result = _run(["--lang", "pt_BR", "--list-layers"], tmp_path)
    assert result.returncode == 0, result.stderr
    assert "\tintegrado" in result.stdout
    assert "\tligado\t" in result.stdout or "\tdesligado\t" in result.stdout
    assert "built-in" not in result.stdout


def test_unknown_tab_is_an_error_in_portuguese(tmp_path):
    result = _run(["--lang", "pt_BR", "--tab", "nope", "--list-tabs"], tmp_path)
    assert result.returncode == 2
    assert "aba desconhecida 'nope'" in result.stderr


def test_offline_and_online_error_in_portuguese(tmp_path):
    result = _run(["--lang", "pt_BR", "--offline", "--online", "--list-tabs"], tmp_path)
    assert result.returncode == 2
    assert "--offline e --online não podem ser usados juntos" in result.stderr


def test_unknown_set_key_error_in_portuguese(tmp_path):
    result = _run(["--lang", "pt_BR", "--set", "not.a.key=1", "--list-tabs"], tmp_path)
    assert result.returncode == 2
    assert "--set: configuração desconhecida 'not.a.key'" in result.stderr


def test_unknown_set_key_error_in_english(tmp_path):
    result = _run(["--lang", "en", "--set", "not.a.key=1", "--list-tabs"], tmp_path)
    assert result.returncode == 2
    assert "--set: unknown setting 'not.a.key'" in result.stderr


def test_bad_flag_value_error_in_portuguese(tmp_path):
    result = _run(["--lang", "pt_BR", "--frame-delay", "-1", "--list-tabs"], tmp_path)
    assert result.returncode == 2
    assert "deve ser >= 0" in result.stderr


def test_unsupported_language_error_follows_the_system_language(tmp_path):
    result = _run(["--lang", "fr", "--list-tabs"], tmp_path, {"LANG": "pt_BR.UTF-8"})
    assert result.returncode == 2
    assert "idioma não suportado 'fr'" in result.stderr
