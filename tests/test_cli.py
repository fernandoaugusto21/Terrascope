"""The --lang flag and the translated help, run as the real command."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest


def _run(args, tmp_path, env_extra=None):
    env = dict(os.environ)
    for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG", "terrascope_CONFIG", "terrascope_LOCALE_DIR"):
        env.pop(name, None)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, "-m", "terrascope", *args],
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=120,
    )


def test_help_in_portuguese(tmp_path):
    result = _run(["--lang", "pt_BR", "--help"], tmp_path)
    assert result.returncode == 0, result.stderr
    assert "Idioma e formatos regionais" in result.stdout
    assert "Mostra esta ajuda e encerra." in result.stdout
    assert "Language and regional formats" not in result.stdout


def test_help_in_english_is_unchanged(tmp_path):
    result = _run(["--lang", "en", "--help"], tmp_path)
    assert result.returncode == 0, result.stderr
    assert "Language and regional formats" in result.stdout
    assert "Show this help and exit." in result.stdout


def test_lang_hyphen_form_is_accepted(tmp_path):
    result = _run(["--lang", "pt-BR", "--list-tabs"], tmp_path)
    assert result.returncode == 0, result.stderr


def test_auto_is_accepted_as_a_language(tmp_path):
    """The help and the config both document 'auto'; it means 'choose from the system'."""
    result = _run(["--lang", "auto", "--list-tabs"], tmp_path)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("value", ["AUTO", "Auto"])
def test_auto_is_accepted_in_any_case(tmp_path, value):
    result = _run(["--lang", value, "--list-tabs"], tmp_path)
    assert result.returncode == 0, result.stderr


def test_unsupported_language_is_an_error(tmp_path):
    # LANG pins the English fallback; without it the Windows UI language decides.
    result = _run(["--lang", "fr", "--list-tabs"], tmp_path, {"LANG": "en_US.UTF-8"})
    assert result.returncode == 2
    assert "unsupported language 'fr'" in result.stderr


def test_environment_selects_the_language_when_no_flag(tmp_path):
    result = _run(["--help"], tmp_path, {"LANG": "pt_BR.UTF-8"})
    assert result.returncode == 0, result.stderr
    assert "Idioma e formatos regionais" in result.stdout


@pytest.mark.parametrize("flag, value", [("--time-format", "12h"), ("--units", "imperial")])
def test_regional_flags_are_accepted(tmp_path, flag, value):
    result = _run(["--lang", "en", flag, value, "--dump-config"], tmp_path)
    assert result.returncode == 0, result.stderr
    assert f"{flag[2:].replace('-', '_')}" in result.stdout or value in result.stdout


# --- the help language when the language comes from a --config file -----------
# Precedence: --lang > app.language of --config > environment > default. The
# environment cases set LANG explicitly, because without it the help falls back
# to the Windows interface language and the result depends on the machine.

PT_HEADING = "Idioma e formatos regionais"
EN_HEADING = "Language and regional formats"


def _config(tmp_path, body, name="terrascope.yaml"):
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_help_follows_config_language_over_environment(tmp_path):
    config_file = _config(tmp_path, "app:\n  language: en\n")
    result = _run(["--config", config_file, "--help"], tmp_path, {"LANG": "pt_BR.UTF-8"})
    assert result.returncode == 0, result.stderr
    assert EN_HEADING in result.stdout
    assert PT_HEADING not in result.stdout


def test_help_follows_config_language_without_environment_language(tmp_path):
    config_file = _config(tmp_path, "app:\n  language: pt_BR\n")
    result = _run(["--config", config_file, "--help"], tmp_path, {"LANG": "en_US.UTF-8"})
    assert result.returncode == 0, result.stderr
    assert PT_HEADING in result.stdout
    assert EN_HEADING not in result.stdout


def test_lang_flag_beats_config_language(tmp_path):
    config_file = _config(tmp_path, "app:\n  language: pt_BR\n")
    result = _run(["--config", config_file, "--lang", "en", "--help"], tmp_path)
    assert result.returncode == 0, result.stderr
    assert EN_HEADING in result.stdout
    assert PT_HEADING not in result.stdout


def test_short_config_flag_sets_the_help_language(tmp_path):
    config_file = _config(tmp_path, "app:\n  language: pt_BR\n")
    result = _run(["-c", config_file, "--help"], tmp_path, {"LANG": "en_US.UTF-8"})
    assert result.returncode == 0, result.stderr
    assert PT_HEADING in result.stdout


def test_equals_config_flag_sets_the_help_language(tmp_path):
    config_file = _config(tmp_path, "app:\n  language: pt_BR\n")
    result = _run([f"--config={config_file}", "--help"], tmp_path, {"LANG": "en_US.UTF-8"})
    assert result.returncode == 0, result.stderr
    assert PT_HEADING in result.stdout


def test_last_config_file_that_sets_the_language_wins(tmp_path):
    first = _config(tmp_path, "app:\n  language: pt_BR\n", "first.yaml")
    second = _config(tmp_path, "app:\n  language: en\n", "second.yaml")
    result = _run(["--config", first, "--config", second, "--help"], tmp_path)
    assert result.returncode == 0, result.stderr
    assert EN_HEADING in result.stdout


def test_config_auto_defers_to_environment(tmp_path):
    config_file = _config(tmp_path, "app:\n  language: auto\n")
    result = _run(["--config", config_file, "--help"], tmp_path, {"LANG": "pt_BR.UTF-8"})
    assert result.returncode == 0, result.stderr
    assert PT_HEADING in result.stdout


def test_config_without_language_leaves_environment_in_charge(tmp_path):
    config_file = _config(tmp_path, "app:\n  frame_delay_ms: 40\n")
    result = _run(["--config", config_file, "--help"], tmp_path, {"LANG": "pt_BR.UTF-8"})
    assert result.returncode == 0, result.stderr
    assert PT_HEADING in result.stdout


def test_unreadable_config_is_still_reported_by_the_normal_path(tmp_path):
    missing = str(tmp_path / "missing.yaml")
    result = _run(["--config", missing, "--list-tabs"], tmp_path)
    assert result.returncode == 2
    assert "cannot read" in result.stderr


def test_config_flag_without_value_is_a_usage_error(tmp_path):
    result = _run(["--config"], tmp_path)
    assert result.returncode == 2
    assert "usage: terrascope [OPTIONS]" in result.stderr
    assert "expected one argument" in result.stderr
