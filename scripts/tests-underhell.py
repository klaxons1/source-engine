#!/usr/bin/env python3
"""Offline regression checks for Underhell branding and case-sensitive wiring."""
import importlib.util
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import warnings
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


branding = load("underhell_branding", "prepare-underhell-launcher.py")
content_check = load("underhell_content", "check-underhell-content.py")
apk_check = load("underhell_apk", "verify-underhell-apk.py")
touch_tests = load("underhell_touch_tests", "tests-underhell-touch.py")
TouchTests = touch_tests.TouchTests
java_tests = load("underhell_java_tests", "test-underhell-launch-contract.py")


def elf_fixture(marker, machine=183):
    header = bytearray(64)
    header[:4] = b"\x7fELF"
    header[4:6] = bytes([2 if machine == 183 else 1, 1])
    header[18:20] = machine.to_bytes(2, "little")
    return bytes(header) + marker



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
            if name == "ExtractAssets":
                text += 'public static final String VPK_CHSM = "";\n'
            if name == "LauncherActivity":
                text += 'public static String MOD_NAME = "MOD_REPLACE_ME";\n'
                text += '\tpublic void onCreate() {\n\t\tLinearLayout body = ( LinearLayout ) findViewById( R.id.body );\n}\n'
                text += '\tpublic void saveSettings( SharedPreferences.Editor editor ) {\neditor.putString( "argv", argv );\n}\n'
                text += '\tprivate Intent prepareIntent( Intent i ) {\n'
                text += 'i.putExtra( "gamedir", MOD_NAME );\n}\n'
                text += '\tpublic void startSource( View view ) {}\n\tpublic void onPause() {}\n'
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
        self.native.write_bytes(elf_fixture(apk_check.MARKERS["client"]))
        self.server = self.native.with_name("libserver.so")
        self.server.write_bytes(elf_fixture(apk_check.MARKERS["server"]))
        self.native.with_name("libshaderapidx9.so").write_bytes(elf_fixture(apk_check.MARKERS["shaderapidx9"]))

    def test_branding_and_exact_lowercase_gamedir(self):
        branding.prepare(self.launcher)
        java = (self.android / "src/me/nillerusr/LauncherActivity.java").read_text()
        self.assertIn('MOD_NAME = "underhell";', java)
        self.assertIn('putExtra( "gamedir", MOD_NAME )', java)
        manifest = ET.parse(self.android / "AndroidManifest.xml").getroot()
        self.assertEqual(manifest.get("package"), "com.valvesoftware.source.underhell")
        self.assertEqual(manifest.find("application").get(branding.ANDROID + "extractNativeLibs"), "true")
        runner = manifest.find("application/activity[@" + branding.ANDROID + "name='me.nillerusr.UnderhellSarekActivity']")
        self.assertIsNotNone(runner)
        self.assertEqual(runner.get(branding.ANDROID + "process"), ":sarek")
        self.assertEqual(runner.get(branding.ANDROID + "exported"), "false")
        self.assertIn("UnderhellVulkanSettingsActivity", java)
        self.assertIn("FLAG_ACTIVITY_CLEAR_TASK", java)
        self.assertIn("UnderhellLaunchContract.requireLibraries", java)
        self.assertIn('getBoolean("underhell_astc", false)', java)
        self.assertIn('editor.putBoolean("underhell_astc", underhellAstc.isChecked())', java)
        self.assertEqual(java.count("new android.widget.CheckBox(this)"), 1)
        for notice in (ROOT / "assets/android/licenses").glob("*.txt"):
            self.assertEqual((self.android / "assets/licenses" / notice.name).read_bytes(), notice.read_bytes())
        self.assertIn('putExtra( "argv", argv )', java)
        self.assertIn('putExtra("render_height", mPref.getInt("underhell_render_height", 720))', java)
        staged_sdl = (self.android / "src/org/libsdl/app/SDLActivity.java").read_text()
        pristine_sdl = (ROOT / "thirdparty/SDL-src/android-project/app/src/main/java/org/libsdl/app/SDLActivity.java").read_text()
        for axis, dimension in (("X", "Width"), ("Y", "Height")):
            old = "event.get" + axis + "(i) / m" + dimension
            new = "event.get" + axis + "(i) / Math.max(1, v.get" + dimension + "())"
            self.assertEqual(pristine_sdl.count(old), 3)
            self.assertNotIn(old, staged_sdl)
            self.assertEqual(staged_sdl.count(new), 3)
        for font in (ROOT / "assets/android/fonts").iterdir():
            self.assertEqual((self.android / "assets/fonts" / font.name).read_bytes(), font.read_bytes())
        label = ET.parse(self.android / "res/values/updates.xml").find("string[@name='mod_name']")
        self.assertEqual(label.text, "underhell")
        self.assertEqual(self.native.read_bytes(), elf_fixture(apk_check.MARKERS["client"]))
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
        for name in ("build-apk.sh", "prepare-underhell-launcher.py", "verify-underhell-apk.py", "test-underhell-launch-contract.py", "test-underhell-fonts.py", "build-underhell-touch-assets.py", "tests-underhell-touch.py"):
            shutil.copy2(ROOT / "scripts" / name, root / "scripts" / name)
        shutil.copytree(ROOT / "assets", root / "assets")
        sdl_java = Path("thirdparty/SDL-src/android-project/app/src/main/java")
        shutil.copytree(ROOT / sdl_java, root / sdl_java)
        (root / "game/client/underhell").mkdir(parents=True)
        for name in ("uh_touch_assets.h", "uh_touch_controls.inl"):
            shutil.copy2(ROOT / "game/client/underhell" / name, root / "game/client/underhell" / name)
        shutil.copytree(ROOT / "scripts/tests", root / "scripts/tests")
        bin_dir = root / "bin"
        bin_dir.mkdir()
        programs = {
            "git": '#!/bin/sh\necho "$*" >> "$TEST_LOG"\nif [ "$1" = clone ]; then for last do :; done; mkdir -p "$last"; fi\n',
            "javac": "#!/bin/sh\nexit 0\n",
            "java": "#!/bin/sh\nexit 0\n",
            "convert": '#!/bin/sh\nfor last do :; done; printf icon > "$last"\n',
        }
        for name, text in programs.items():
            path = bin_dir / name
            path.write_text(text)
            path.chmod(0o755)
        waf = launcher / "waf"
        waf.write_text("#!/usr/bin/env python3\nimport sys, pathlib, zipfile\n"
                       "if sys.argv[1] == 'build':\n"
                       " pathlib.Path('build/android').mkdir(parents=True, exist_ok=True)\n"
                       " with zipfile.ZipFile('build/android/mod-signed.apk','w') as z:\n"
                       "  for p in pathlib.Path('android').rglob('*'):\n"
                       "   if p.is_file() and (p.suffix == '.so' or p.name == 'extras_dir.vpk'): z.write(p, str(p.relative_to('android')))\n")
        aapt = launcher / "android-sdk/build-tools/test/aapt"
        aapt.parent.mkdir(parents=True)
        aapt.write_text("#!/bin/sh\nprintf \"package: name='com.valvesoftware.source.underhell'\\napplication-label:'underhell'\\n\"\n")
        aapt.chmod(0o755)
        log = root / "git-commands"
        env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ["PATH"], TEST_LOG=str(log))
        for key in ("JAVA", "JAVAC", "JAVA_COMPILER_JAR"):
            env.pop(key, None)
        for _ in range(2):
            subprocess.run(["sh", str(root / "scripts/build-apk.sh")], cwd=self.launcher, env=env,
                           check=True, capture_output=True, text=True)
        apk_check.verify(launcher / "build/android/underhell.apk",
                         "package: name='com.valvesoftware.source.underhell'\napplication-label:'underhell'", launcher / "android")
        self.assertEqual((launcher / "android/lib/arm64-v8a/libclient.so").read_bytes(),
                         elf_fixture(apk_check.MARKERS["client"]))
        commands = log.read_text()
        self.assertIn("2174bf02eb7f46b457538dccecf3cbc42b6057d5", commands)
        self.assertIn("9c474caf7be38a887574291f611152fc24a7afe3", commands)
        self.assertNotIn("pull", commands)


class JavaLaunchTests(unittest.TestCase):
    @unittest.skipUnless((os.environ.get("JAVA") or shutil.which("java")) and
                         (os.environ.get("JAVA_COMPILER_JAR") or os.environ.get("JAVAC") or shutil.which("javac")),
                         "Java runtime/compiler not installed")
    def test_real_java_launch_contract(self):
        java_tests.run()


class ApkIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.apk = self.root / "underhell.apk"
        self.badging = "package: name='com.valvesoftware.source.underhell' versionCode='1'\napplication-label:'underhell'\n"
        self.libraries = {"lib/arm64-v8a/lib" + name + ".so": elf_fixture(marker)
                          for name, marker in apk_check.MARKERS.items()}

    def pack(self, libraries=None):
        with zipfile.ZipFile(self.apk, "w") as archive:
            for name, data in (self.libraries if libraries is None else libraries).items():
                archive.writestr(name, data)
            archive.writestr("assets/extras_dir.vpk", b"touch VPK fixture")

    def test_valid_native_modules_and_staging_hashes(self):
        self.pack()
        for name, data in self.libraries.items():
            path = self.root / "android" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        extra = self.root / "android/assets/extras_dir.vpk"
        extra.parent.mkdir(parents=True)
        extra.write_bytes(b"touch VPK fixture")
        result = apk_check.verify(self.apk, self.badging, self.root / "android")
        self.assertEqual(len(result["libraries"]), 3)

    def test_rejects_absent_or_stale_embedded_touch_assets(self):
        stage = self.root / "android"
        for name, data in self.libraries.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.pack()
        with self.assertRaisesRegex(ValueError, "touch texture VPK"):
            apk_check.verify(self.apk, self.badging, stage)
        vpk = stage / "assets/extras_dir.vpk"
        vpk.parent.mkdir(parents=True)
        vpk.write_bytes(b"different generation")
        with self.assertRaisesRegex(ValueError, "touch texture VPK"):
            apk_check.verify(self.apk, self.badging, stage)
        with zipfile.ZipFile(self.apk, "w") as archive:
            for name, data in self.libraries.items():
                archive.writestr(name, data)
        vpk.write_bytes(b"touch VPK fixture")
        with self.assertRaisesRegex(ValueError, "touch texture VPK"):
            apk_check.verify(self.apk, self.badging, stage)

    def test_rejects_old_package_and_wrong_label(self):
        self.pack()
        for bad in (self.badging.replace("source.underhell", "source.lostcoast"),
                    self.badging.replace("label:'underhell'", "label:'Underhell'"),
                    self.badging + "application-label-ru:'Half-Life 2'\n"):
            with self.assertRaises(ValueError):
                apk_check.verify(self.apk, bad)

    def test_rejects_missing_server_or_wrong_case(self):
        for names in ({k:v for k,v in self.libraries.items() if "shaderapidx9" not in k},
                      {"lib/arm64-v8a/libclient.so": self.libraries["lib/arm64-v8a/libclient.so"]},
                      {key.replace("libserver.so", "libServer.so"): value for key, value in self.libraries.items()}):
            self.pack(names)
            with self.assertRaises(ValueError):
                apk_check.verify(self.apk, self.badging)

    def test_rejects_stock_libraries_and_wrong_abi(self):
        for bad in (elf_fixture(b"stock client"), elf_fixture(apk_check.MARKERS["client"], machine=40)):
            self.pack(dict(self.libraries, **{"lib/arm64-v8a/libclient.so": bad}))
            with self.assertRaises(ValueError):
                apk_check.verify(self.apk, self.badging)

    def test_bundled_fonts_have_real_latin_and_cyrillic_glyphs(self):
        subprocess.run([sys.executable, str(ROOT / "scripts/test-underhell-fonts.py")], check=True)

    def test_vulkan_apk_requires_complete_runtime_provenance_hashes_and_java(self):
        libraries = dict(self.libraries)
        runtime = {"sarek": "0c0e8f6f62c7cb37dbf5d38413517efa00c08fef",
                   "adrenotools": "8fae8ce254dfc1344527e05301e43f37dea2df80", "libraries_sha256": {}}
        for module in ("SDL2", "hidapi", "dxvk_sarek_d3d9", "adrenotools", "hook_impl", "main_hook", "file_redirect_hook", "gsl_alloc_hook"):
            data = elf_fixture(module.encode())
            libraries["lib/arm64-v8a/lib" + module + ".so"] = data
            runtime["libraries_sha256"]["lib" + module + ".so"] = hashlib.sha256(data).hexdigest()
        libraries["lib/arm64-v8a/libshaderapidx9_sarek.so"] = elf_fixture(b"UNDERHELL_SAREK_SHADERAPI_V1")
        libraries["lib/arm64-v8a/liblauncher_sarek.so"] = elf_fixture(b"UNDERHELL_SAREK_LAUNCHER_V1")
        libraries["assets/underhell-vulkan.json"] = json.dumps(runtime).encode()
        for font in (ROOT / "assets/android/fonts").iterdir():
            if font.is_file(): libraries["assets/fonts/" + font.name] = font.read_bytes()
        libraries["classes.dex"] = b"Lme/nillerusr/UnderhellSarekActivity;Lme/nillerusr/UnderhellVulkanSettingsActivity;Lorg/libsdl/app/SDLActivity;"
        self.pack(libraries)
        self.assertIn("vulkan", apk_check.verify(self.apk, self.badging))
        for missing in ("assets/underhell-vulkan.json", "lib/arm64-v8a/libmain_hook.so", "classes.dex", "assets/fonts/dejavusans.ttf", "assets/fonts/LICENSE_DEJAVU.txt"):
            self.pack({k: v for k, v in libraries.items() if k != missing})
            with self.assertRaises(ValueError):
                apk_check.verify(self.apk, self.badging)
        broken = dict(libraries)
        broken["lib/arm64-v8a/libSDL2.so"] = elf_fixture(b"wrong SDL build")
        self.pack(broken)
        with self.assertRaisesRegex(ValueError, "Stale/replaced"):
            apk_check.verify(self.apk, self.badging)
        for name in ("dejavusans.ttf", "LiberationMono-Regular.ttf", "LICENSE_DEJAVU.txt"):
            broken = dict(libraries)
            broken["assets/fonts/" + name] = b"corrupted font or license"
            self.pack(broken)
            with self.assertRaisesRegex(ValueError, "bundled font"):
                apk_check.verify(self.apk, self.badging)
        broken = dict(libraries)
        runtime["sarek"] = "ordinary dxvk-native"
        broken["assets/underhell-vulkan.json"] = json.dumps(runtime).encode()
        self.pack(broken)
        with self.assertRaisesRegex(ValueError, "provenance"):
            apk_check.verify(self.apk, self.badging)

    def test_rejects_stale_staging(self):
        self.pack()
        with self.assertRaises(ValueError):
            apk_check.verify(self.apk, self.badging, self.root / "wrong-build-output")


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

    def test_hud_uses_portable_bounded_wide_formatting(self):
        for path in (ROOT / "game/client/underhell").rglob("*.cpp"):
            self.assertIsNone(re.search(r"\bswprintf\s*\(", path.read_text()), str(path))
        for name in ("hud_uhbattery.cpp", "hud_hermitcards.cpp"):
            self.assertIn("V_swprintf_safe(", (ROOT / "game/client/underhell" / name).read_text())

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
