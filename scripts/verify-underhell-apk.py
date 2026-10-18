#!/usr/bin/env python3
"""Verify final APK identity and native game modules, not just source branding."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

PACKAGE = "com.valvesoftware.source.underhell"
MARKERS = {"client": b"UNDERHELL_PORT_CLIENT_V1", "server": b"UNDERHELL_PORT_SERVER_V1",
           "shaderapidx9": b"UNDERHELL_RENDERER_ASTC_V1"}
ABIS = {"arm64-v8a": (2, 183), "armeabi-v7a": (1, 40)}


def verify(apk, badging, staging=None):
    if not re.search(r"^package: name='" + re.escape(PACKAGE) + r"'(?:\s|$)", badging, re.M):
        raise ValueError("APK package is not " + PACKAGE)
    labels = re.findall(r"^application-label(?:-[^:]+)?:'([^']*)'", badging, re.M)
    if not labels or any(label != "underhell" for label in labels):
        raise ValueError("APK application labels must all be exactly lowercase underhell")
    report = {"package": PACKAGE, "label": "underhell", "libraries": {}}
    with zipfile.ZipFile(apk) as archive:
        members = archive.namelist()
        if len(members) != len(set(members)):
            raise ValueError("APK contains duplicate ZIP entries")
        if staging is not None:
            name = "assets/extras_dir.vpk"
            if not (staging / name).is_file() or name not in members or archive.read(name) != (staging / name).read_bytes():
                raise ValueError("APK is missing/stale Underhell touch texture VPK")
            report["touch_vpk_sha256"] = hashlib.sha256(archive.read(name)).hexdigest()
        native_manifest = "assets/underhell-vulkan.json"
        sarek_name = "lib/arm64-v8a/libshaderapidx9_sarek.so"
        if native_manifest in members or sarek_name in members:
            if native_manifest not in members:
                raise ValueError("Incomplete Vulkan APK: missing provenance/hash manifest")
            runtime = json.loads(archive.read(native_manifest))
            if runtime.get("sarek") != "0c0e8f6f62c7cb37dbf5d38413517efa00c08fef" or runtime.get("adrenotools") != "8fae8ce254dfc1344527e05301e43f37dea2df80":
                raise ValueError("Unexpected Sarek/libadrenotools provenance")
            hashes = runtime.get("libraries_sha256", {})
            required_runtime = {"lib" + n + ".so" for n in ("SDL2", "hidapi", "dxvk_sarek_d3d9", "adrenotools", "hook_impl", "main_hook", "file_redirect_hook", "gsl_alloc_hook")}
            if set(hashes) != required_runtime:
                raise ValueError("Incomplete Vulkan runtime manifest")
            for module in sorted(required_runtime | {"libshaderapidx9_sarek.so", "liblauncher_sarek.so"}):
                name = "lib/arm64-v8a/" + module
                if name not in members:
                    raise ValueError("Incomplete Vulkan APK: missing " + name)
                data = archive.read(name)
                if len(data) < 64 or data[:6] != b"\x7fELF\x02\x01" or int.from_bytes(data[18:20], "little") != 183:
                    raise ValueError("Invalid Vulkan ARM64 library: " + name)
                digest = hashlib.sha256(data).hexdigest()
                if module in hashes and digest != hashes[module]:
                    raise ValueError("Stale/replaced Vulkan runtime library: " + name)
                if staging is not None and (not (staging / name).is_file() or hashlib.sha256((staging / name).read_bytes()).hexdigest() != digest):
                    raise ValueError("Vulkan library differs from staged build: " + name)
                marker = {"libshaderapidx9_sarek.so": b"UNDERHELL_SAREK_SHADERAPI_V1", "liblauncher_sarek.so": b"UNDERHELL_SAREK_LAUNCHER_V1"}.get(module)
                if marker and marker not in data:
                    raise ValueError("Wrong native Vulkan engine module: " + name)
                report["libraries"][name] = digest
            dex = b"".join(archive.read(n) for n in members if re.fullmatch(r"classes[0-9]*\.dex", n))
            for klass in (b"Lme/nillerusr/UnderhellSarekActivity;", b"Lme/nillerusr/UnderhellVulkanSettingsActivity;", b"Lorg/libsdl/app/SDLActivity;"):
                if klass not in dex:
                    raise ValueError("Missing owned Vulkan Java lifecycle/settings class")
            report["vulkan"] = "Packaged integration verified; Android execution/GPU tests still required"
        for module, marker in MARKERS.items():
            required = "lib/arm64-v8a/lib" + module + ".so"
            if required not in members:
                raise ValueError("APK is missing " + required)
        abis = {name.split('/')[1] for name in members if name.startswith("lib/") and name.endswith(".so")}
        for abi in sorted(abis):
            if abi not in ABIS:
                raise ValueError("Unverified native ABI: " + abi)
            for module, marker in MARKERS.items():
                name = "lib/" + abi + "/lib" + module + ".so"
                if name not in members:
                    raise ValueError("Incomplete Underhell ABI: " + name)
                data = archive.read(name)
                elf_class, machine = ABIS[abi]
                if (len(data) < 64 or data[:4] != b"\x7fELF" or data[4] != elf_class
                        or data[5] != 1 or int.from_bytes(data[18:20], "little") != machine):
                    raise ValueError("Invalid ELF architecture: " + name)
                if marker not in data:
                    raise ValueError("Stock/wrong native module (Underhell identity missing): " + name)
                digest = hashlib.sha256(data).hexdigest()
                if staging is not None:
                    source = staging / name
                    if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                        raise ValueError("Packaged library differs from installed build output: " + name)
                report["libraries"][name] = digest
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    args = parser.parse_args()
    tools = []
    for version in sorted((args.sdk / "build-tools").iterdir(), reverse=True):
        for name in ("aapt", "aapt2"):
            tool = version / name
            if tool.is_file():
                tools.append(tool)
    if not tools:
        raise ValueError("SDK does not contain aapt/aapt2 for APK identity verification")
    result = subprocess.run([str(tools[0]), "dump", "badging", str(args.apk)],
                            check=True, capture_output=True, text=True)
    print(json.dumps(verify(args.apk, result.stdout, args.staging), indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        print("Underhell APK verification failed: " + str(error), file=sys.stderr)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            message = str(error).replace("%", "%25").replace("\n", "%0A").replace("\r", "%0D")
            print("::error title=Underhell APK verification::" + message)
        sys.exit(1)
