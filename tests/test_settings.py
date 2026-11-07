import json
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from euler.core import settings  # noqa: E402


def _point_at(tmp_path):
    return mock.patch.object(settings, "settings_path", return_value=tmp_path / "settings.json")


def test_first_launch_takes_installer_language(tmp_path):
    with _point_at(tmp_path), mock.patch.object(settings, "_installer_language", return_value="fr"):
        assert settings.load()["language"] == "fr"


def test_stored_language_beats_installer(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"language": "es"}), encoding="utf-8")
    with _point_at(tmp_path), mock.patch.object(settings, "_installer_language", return_value="fr"):
        assert settings.load()["language"] == "es"


def test_no_installer_value_leaves_language_unset(tmp_path):
    with _point_at(tmp_path), mock.patch.object(settings, "_installer_language", return_value=""):
        assert settings.load()["language"] == ""


def test_unknown_stored_keys_are_dropped(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"evil": 1, "model": "x"}), encoding="utf-8")
    with _point_at(tmp_path):
        loaded = settings.load()
    assert "evil" not in loaded and loaded["model"] == "x"


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    (tmp_path / "settings.json").write_text("{not json", encoding="utf-8")
    with _point_at(tmp_path), mock.patch.object(settings, "_installer_language", return_value=""):
        loaded = settings.load()
    assert loaded["model"] == settings.DEFAULTS["model"]
