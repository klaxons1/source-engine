#!/usr/bin/env python3
"""Offline regression checks for Underhell branding and case-sensitive wiring."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import warnings
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


branding = load("underhell_branding", "prepare-underhell-launcher.py")
content_check = load("underhell_content", "check-underhell-content.py")


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.launcher = Path(self.tmp.name)
        self.android = self.launcher / "android"
        for name in ("LauncherActivity", "ExtractAssets", "UpdateService", "UpdateSystem"):
            path = self.android / "src/me/nillerusr" / (name + ".java")
            path.parent.mkdir(parents=True, exist_ok=True)
            text = "import com.valvesoftware.source.MOD_REPLACE_ME.R;\n"
            if name == "LauncherActivity":
                text += 'public static String MOD_NAME = "MOD_REPLACE_ME";\n'
                text += 'i.putExtra( "gamedir", MOD_NAME );\n'
            path.write_text(text)
        (self.android / "AndroidManifest.xml").write_text(
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
            'package="com.valvesoftware.source.MOD_REPLACE_ME">'
            '<application android:label="@string/mod_name"/></manifest>')
        values = self.android / "res/values/updates.xml"
        values.parent.mkdir(parents=True)
        values.write_text('<resources><string name="mod_name">APP_NAME</string></resources>')
        self.native = self.android / "lib/arm64-v8a/libclient.so"
        self.native.parent.mkdir(parents=True)
        self.native.write_bytes(b"native library must not be overwritten")

    def test_branding_and_exact_lowercase_gamedir(self):
        branding.prepare(self.launcher)
        java = (self.android / "src/me/nillerusr/LauncherActivity.java").read_text()
        self.assertIn('MOD_NAME = "underhell";', java)
        self.assertIn('putExtra( "gamedir", MOD_NAME )', java)
        manifest = ET.parse(self.android / "AndroidManifest.xml").getroot()
        self.assertEqual(manifest.get("package"), "com.valvesoftware.source.underhell")
        label = ET.parse(self.android / "res/values/updates.xml").find("string[@name='mod_name']")
        self.assertEqual(label.text, "underhell")
        self.assertEqual(self.native.read_bytes(), b"native library must not be overwritten")
        before = {p: p.read_bytes() for p in self.android.rglob("*") if p.is_file()}
        branding.prepare(self.launcher)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_rejects_stale_lostcoast_package_without_partial_writes(self):
        path = self.android / "AndroidManifest.xml"
        path.write_text(path.read_text().replace("MOD_REPLACE_ME", "lostcoast"))
        before = {p: p.read_bytes() for p in self.android.rglob("*") if p.is_file()}
        with self.assertRaises(ValueError):
            branding.prepare(self.launcher)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_rejects_mixed_case_gamedir(self):
        path = self.android / "src/me/nillerusr/LauncherActivity.java"
        path.write_text(path.read_text().replace('"MOD_REPLACE_ME";', '"Underhell";'))
        with self.assertRaises(ValueError):
            branding.prepare(self.launcher)


    def test_apk_entrypoint_with_pinned_dependencies_and_native_libs(self):
        root = self.launcher / "checkout with spaces"
        (root / "scripts").mkdir(parents=True)
        launcher = root / "srceng-mod-launcher"
        launcher.mkdir()
        shutil.copytree(self.android, launcher / "android")
        for name in ("build-apk.sh", "prepare-underhell-launcher.py"):
            shutil.copy2(ROOT / "scripts" / name, root / "scripts" / name)
        (root / "assets/android").mkdir(parents=True)
        shutil.copy2(ROOT / "assets/android/underhell.png", root / "assets/android/underhell.png")
        bin_dir = root / "bin"
        bin_dir.mkdir()
        programs = {
            "git": '#!/bin/sh\necho "$*" >> "$TEST_LOG"\nif [ "$1" = clone ]; then for last do :; done; mkdir -p "$last"; fi\n',
            "convert": '#!/bin/sh\nfor last do :; done; printf icon > "$last"\n',
        }
        for name, text in programs.items():
            path = bin_dir / name
            path.write_text(text)
            path.chmod(0o755)
        waf = launcher / "waf"
        waf.write_text('#!/bin/sh\nset -e\nif [ "$1" = build ]; then mkdir -p build/android; printf apk > build/android/mod-signed.apk; fi\n')
        log = root / "git-commands"
        env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ["PATH"], TEST_LOG=str(log))
        for _ in range(2):
            subprocess.run(["sh", str(root / "scripts/build-apk.sh")], cwd=self.launcher, env=env,
                           check=True, capture_output=True, text=True)
        self.assertEqual((launcher / "build/android/underhell.apk").read_bytes(), b"apk")
        self.assertEqual((launcher / "android/lib/arm64-v8a/libclient.so").read_bytes(),
                         b"native library must not be overwritten")
        commands = log.read_text()
        self.assertIn("2174bf02eb7f46b457538dccecf3cbc42b6057d5", commands)
        self.assertIn("9c474caf7be38a887574291f611152fc24a7afe3", commands)
        self.assertNotIn("pull", commands)


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "underhell"
        self.root.mkdir()
        (self.root / "gameinfo.txt").write_text('"GameInfo" {}')

    def test_accepts_lowercase_root(self):
        errors, _ = content_check.audit(self.root)
        self.assertEqual(errors, [])

    def test_rejects_uppercase_root(self):
        wrong = self.root.with_name("Underhell")
        self.root.rename(wrong)
        errors, _ = content_check.audit(wrong)
        self.assertTrue(any("exactly 'underhell'" in e for e in errors))

    def test_rejects_gameinfo_case_mismatch(self):
        (self.root / "gameinfo.txt").rename(self.root / "GameInfo.txt")
        errors, _ = content_check.audit(self.root)
        self.assertTrue(any("gameinfo.txt" in e for e in errors))

    def test_reports_resource_case_mismatch_without_renaming(self):
        directory = self.root / "models/weapons"
        directory.mkdir(parents=True)
        asset = directory / "V_KICK_JAKE_CASUAL.MDL"
        asset.write_bytes(b"fixture")
        errors, _ = content_check.audit(self.root)
        self.assertTrue(any("Case mismatch: code requests models/weapons/v_kick_jake_casual.mdl" in e for e in errors))
        self.assertTrue(asset.exists())


class BuildDiagnosticsTests(unittest.TestCase):
    def test_preserves_failure_code_and_escapes_annotation(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "config.log"
            log.write_text("compiler detail 100%\nnext line\n")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/run-android-waf.py"), "--config-log", str(log),
                 sys.executable, "-c", "print('compile failed'); raise SystemExit(7)"],
                env=dict(os.environ, GITHUB_ACTIONS="true"), capture_output=True, text=True)
            self.assertEqual(result.returncode, 7)
            self.assertIn("compile failed", result.stdout)
            self.assertIn("::error title=Android Waf failure::", result.stdout)
            self.assertIn("100%25%0Anext line", result.stdout)

    def test_success_has_no_error_annotation(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/run-android-waf.py"), sys.executable, "-c", "print('ok')"],
            env=dict(os.environ, GITHUB_ACTIONS="true"), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "ok\n")


class FreeAimTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++"), "host C++ compiler not installed")
    def test_touch_uses_angular_deltas_without_double_sensitivity(self):
        source = (ROOT / "game/client/in_mouse.cpp").read_text()
        start = source.index("static Vector2D g_vecUHFreeAimCursor;")
        end = source.index("// Cliento sub_10014D80", start)
        functions = source[start:end]
        stub = r"""
#include <algorithm>
#include <cassert>
#include <cmath>
using std::min;
struct Vector2D {
    float x = 0, y = 0;
    void Init() { x = y = 0; }
    float Length() const { return std::sqrt(x*x + y*y); }
    void operator/=(float f) { x /= f; y /= f; }
    void operator*=(float f) { x *= f; y *= f; }
};
struct TestVar {
    float value;
    float GetFloat() const { return value; }
    bool GetBool() const { return value != 0; }
};
struct CUserCmd { short mousedx = 0, mousedy = 0; };
TestVar cam_ots_freeaim_enable = {1}, cam_ots_freeaim_move_max = {0.1f};
TestVar m_yaw = {0.022f}, pitch = {0.022f};
TestVar *m_pitch = &pitch;
"""
        test = r"""
int main() {
    Vector2D cursor;
    UH_FreeAimUpdateTouchCursor(0.9f, -0.45f);
    assert(UH_FreeAimGetCursor(cursor));
    assert(std::fabs(cursor.x - 0.01f) < 0.000001f);
    assert(std::fabs(cursor.y + 0.005f) < 0.000001f);
    cam_ots_freeaim_enable.value = 0;
    UH_FreeAimUpdateTouchCursor(1, 1);
    assert(!UH_FreeAimGetCursor(cursor));
    assert(g_vecUHFreeAimCursor.Length() == 0);
    cam_ots_freeaim_enable.value = 1;
    CUserCmd cmd;
    UH_FreeAimUpdateCursor(2, -3, &cmd);
    assert(cmd.mousedx == 2 && cmd.mousedy == -3);
    UH_FreeAimGetCursor(cursor);
    assert(std::fabs(cursor.x - 0.022f * 2 / 90) < 0.000001f);
    assert(std::fabs(cursor.y + 0.022f * 3 / 90) < 0.000001f);
    UH_FreeAimUpdateTouchCursor(1000, 1000);
    UH_FreeAimGetCursor(cursor);
    assert(std::fabs(cursor.Length() - 0.1f) < 0.000001f);
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            cpp = Path(tmp) / "freeaim.cpp"
            cpp.write_text(stub + functions + test)
            binary = Path(tmp) / "freeaim"
            subprocess.run(["g++", "-std=c++11", str(cpp), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


class BuildTests(unittest.TestCase):
    def test_underhell_source_lists_and_exact_case(self):
        sys.path.insert(0, str(ROOT / "scripts/waifulib"))
        import vpc_parser
        for side in ("client", "server"):
            env = SimpleNamespace(SUBPROJECT_PATH=[str(ROOT / "game" / side)],
                                  DEFINES=["POSIX", "_POSIX", "LINUX", "_LINUX", "GNUC"])
            original = Path.cwd()
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", ResourceWarning)
                    result = vpc_parser.parse_vpcs(env, [side + "_base.vpc", side + "_underhell.vpc"], "../..")
            finally:
                os.chdir(original)
            self.assertIn("UNDERHELL", result["defines"])
            self.assertIn("HL2_EPISODIC", result["defines"])
            sources = {(ROOT / "game" / side / p).resolve() for p in result["sources"]}
            self.assertEqual(len(sources), len(result["sources"]), "duplicate translation units")
            for source in sources:
                self.assertTrue(source.is_file(), str(source))
            for directory in (ROOT / "game" / side / "underhell", ROOT / "game/shared/underhell"):
                for source in directory.rglob("*.cpp"):
                    self.assertIn(source.resolve(), sources, str(source))

    def test_native_and_apk_builds_select_underhell(self):
        for arch in ("aarch64", "armv7a"):
            native = (ROOT / ("scripts/build-android-" + arch + ".sh")).read_text()
            self.assertIn("--build-games=underhell", native)
        apk = (ROOT / "scripts/build-apk.sh").read_text()
        self.assertIn("prepare-underhell-launcher.py", apk)
        self.assertNotIn("export PACKAGE=lostcoast", apk)
        self.assertNotIn("export APP_NAME=\"Half-Life 2\"", apk)
        self.assertNotIn("\ngit pull", apk)

    def test_all_seven_upstream_commits_are_recorded(self):
        manifest = json.loads((ROOT / "docs/underhell/upstream-port.json").read_text())
        self.assertEqual(len(manifest["commits"]), 7)
        self.assertEqual(manifest["head"], "11117664a94b27df7cb05cec5ff82457c60126e5")
        for entry in manifest["sources"]:
            self.assertTrue((ROOT / entry["local"]).is_file(), entry["local"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
