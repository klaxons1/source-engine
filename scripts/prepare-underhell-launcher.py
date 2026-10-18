#!/usr/bin/env python3
"""Brand the pinned Android mod template without modifying native libraries."""
import argparse
from pathlib import Path
import re
import xml.etree.ElementTree as ET

GAME = "underhell"
PACKAGE = "com.valvesoftware.source." + GAME
ANDROID = "{http://schemas.android.com/apk/res/android}"
ASSETS = Path(__file__).resolve().parent.parent / "assets/android"


def prepare(launcher):
    android = launcher / "android"
    # Only known template inputs or our already-prepared outputs are accepted.
    # A stale lostcoast template must not silently produce a mixed-package APK.
    changes = {}
    for name in ("LauncherActivity", "ExtractAssets", "UpdateService", "UpdateSystem"):
        path = android / "src/me/nillerusr" / (name + ".java")
        text = path.read_text(encoding="utf-8")
        if "com.valvesoftware.source.MOD_REPLACE_ME.R" not in text and PACKAGE + ".R" not in text:
            raise ValueError("Unexpected launcher Java package in " + str(path))
        text = text.replace("MOD_REPLACE_ME", GAME)
        if name == "LauncherActivity":
            if not re.search(r'MOD_NAME\s*=\s*"underhell"\s*;', text):
                raise ValueError("Launcher must pass the exact lowercase underhell gamedir")
            if 'putExtra( "gamedir", MOD_NAME )' not in text:
                raise ValueError("Launcher gamedir intent contract changed")
        if name == "LauncherActivity":
            start = text.find("\tprivate Intent prepareIntent(")
            end = text.find("\tpublic void onPause()", start)
            if start < 0 or end < 0:
                raise ValueError("Unexpected launcher startup method layout")
            text = text[:start] + (ASSETS / "launcher-start.java.inc").read_text(encoding="utf-8") + text[end:]
        changes[path] = text

    helper = "java/me/nillerusr/UnderhellLaunchContract.java"
    changes[android / "src/me/nillerusr/UnderhellLaunchContract.java"] = (ASSETS / helper).read_text(encoding="utf-8")

    path = android / "AndroidManifest.xml"
    text = path.read_text(encoding="utf-8")
    manifest = ET.fromstring(text)
    if manifest.get("package") not in ("com.valvesoftware.source.MOD_REPLACE_ME", PACKAGE):
        raise ValueError("Unexpected Android manifest package")
    if manifest.find("application").get(ANDROID + "label") != "@string/mod_name":
        raise ValueError("Application label no longer uses mod_name")
    text = text.replace("MOD_REPLACE_ME", GAME)
    # The companion reads nativeLibraryDir, not zip entries inside this APK.
    text = re.sub(r' android:extractNativeLibs="[^"]*"', "", text)
    text = text.replace("<application ", '<application android:extractNativeLibs="true" ', 1)
    changes[path] = text

    path = android / "res/values/updates.xml"
    text = path.read_text(encoding="utf-8")
    values = ET.fromstring(text)
    label = values.find("string[@name='mod_name']")
    if label is None or label.text not in ("APP_NAME", GAME):
        raise ValueError("Unexpected launcher display name")
    changes[path] = text.replace(">APP_NAME<", ">" + GAME + "<")

    # Validate every input first; don't leave a partially configured template.
    for path, text in changes.items():
        if "MOD_REPLACE_ME" in text or "APP_NAME" in text:
            raise ValueError("Unresolved placeholder in " + str(path))
    for path, text in changes.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print("Launcher: underhell; gamedir: underhell; package: " + PACKAGE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("launcher", type=Path)
    args = parser.parse_args()
    prepare(args.launcher)
