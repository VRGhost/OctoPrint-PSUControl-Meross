from pathlib import Path

import octoprint_psucontrol_meross


def test_import():
    """A simple test to confirm that the module is importable"""
    assert octoprint_psucontrol_meross.PSUControlMeross


def test_templates_exist():
    plugin_root = Path(octoprint_psucontrol_meross.__file__).resolve()
    templates_dir = plugin_root.parent / "templates"
    assert list(templates_dir.glob("*.jinja2"))
