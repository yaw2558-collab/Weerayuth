"""Consistency checks for the ThaiCustoms desktop installers.

The Windows (.iss) and Mac (build-dmg.sh) installers are separate scripts;
they must ship the same product name and open the same URL, and the icon
assets they reference must exist. Run from thai-customs/:

    ..\\.venv\\Scripts\\python -m pytest desktop/test_desktop.py -q
"""

import re
from pathlib import Path

HERE = Path(__file__).parent
APP_NAME = "ThaiCustoms"
APP_URL = "https://gateway-1008099094873.asia-southeast1.run.app"


def test_windows_installer_name_and_url():
    iss = (HERE / "windows" / "installer.iss").read_text(encoding="utf-8")
    m = re.search(r'#define\s+AppName\s+"([^"]+)"', iss)
    assert m, "AppName #define missing in installer.iss"
    assert m.group(1) == APP_NAME, f"Windows app name is {m.group(1)!r}"
    assert APP_URL in iss, "app URL missing in installer.iss"
    assert re.search(r"^UsePreviousGroup\s*=\s*no\s*$", iss, re.M), (
        "installer.iss must set UsePreviousGroup=no so upgrades follow renames"
    )


def test_mac_launcher_name_and_url():
    sh = (HERE / "macos" / "build-dmg.sh").read_text(encoding="utf-8")
    m = re.search(r'APP_NAME="([^"]+)"', sh)
    assert m, "APP_NAME missing in build-dmg.sh"
    assert m.group(1) == APP_NAME, f"Mac app name is {m.group(1)!r}"
    assert APP_URL in sh, "app URL missing in build-dmg.sh"


def test_icon_assets_exist():
    assert (HERE / "assets" / "logo.ico").stat().st_size > 0
    assert (HERE / "assets" / "logo-1024.png").stat().st_size > 0
