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
MARKERS = {"client": b"UNDERHELL_PORT_CLIENT_V1", "server": b"UNDERHELL_PORT_SERVER_V1"}
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
    parser.add_argument("--staging", type=Path)
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
