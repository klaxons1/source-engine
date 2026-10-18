#!/usr/bin/env python3
"""Host-GCC syntax checks for the Underhell client/server (not an Android build).

Run after git submodule update --init --recursive. By default checks imported
and modified translation units; --all checks the complete Underhell source set.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts/waifulib"))
import vpc_parser


def project(side):
    env = SimpleNamespace(SUBPROJECT_PATH=[str(ROOT / "game" / side)],
                          DEFINES=["POSIX", "_POSIX", "PLATFORM_POSIX", "LINUX", "_LINUX", "GNUC"])
    data = vpc_parser.parse_vpcs(env, [side + "_base.vpc", side + "_underhell.vpc"], "../..")
    includes = [(ROOT / "game" / side / p).resolve() for p in data["includes"]]
    includes += [ROOT / p for p in ("common", "public", "public/tier0", "public/tier1",
                                    "vgui2/include", "vgui2/controls", "game/shared",
                                    "thirdparty/SDL", "thirdparty/openal-soft/include")]
    defines = [d for d in data["defines"] if d != "PROTECTED_THINGS_ENABLE"]
    defines += ["PLATFORM_64BITS", "LINUX=1", "_LINUX=1", "POSIX=1", "_POSIX=1", "PLATFORM_POSIX=1",
                "GNUC", "NO_HOOK_MALLOC", "NO_MEMOVERRIDE_NEW_DELETE", "_GLIBCXX_USE_CXX11_ABI=0",
                "NDEBUG", "COMPILER_GCC", "USE_SDL", "TOGLES"]
    return data, ["-I" + str(p) for p in includes] + ["-D" + d for d in defines]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="check all translation units, not just ported ones")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--android-branches", action="store_true",
                        help="enable Android preprocessor paths with host GCC; NOT a cross-build")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "docs/underhell/upstream-port.json").read_text())
    changed = {(ROOT / entry["local"]).resolve() for entry in manifest["sources"]}
    changed.add(ROOT / "game/client/in_touch.cpp")
    jobs = []
    for side in ("client", "server"):
        data, flags = project(side)
        if args.android_branches:
            flags = [f for f in flags if not f.startswith("-DPLATFORM_POSIX")]
            flags += ["-DANDROID=1", "-D_ANDROID=1", "-D__ANDROID__=1"]
        if side == "client":
            data["sources"].append("in_touch.cpp")
        for name in data["sources"]:
            path = (ROOT / "game" / side / name).resolve()
            if path.suffix == ".cpp" and (args.all or path in changed):
                jobs.append((side, path, flags))

    def check(job):
        side, path, flags = job
        command = [args.compiler, "-fsyntax-only", "-std=c++11", "-fpermissive", "-w", "-fmax-errors=5"]
        result = subprocess.run(command + flags + [str(path)], capture_output=True, text=True)
        return side, path, result

    failures = 0
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for side, path, result in pool.map(check, jobs):
            print(("FAIL" if result.returncode else "PASS"), side, path.relative_to(ROOT), flush=True)
            if result.returncode:
                failures += 1
                print(result.stderr, file=sys.stderr, flush=True)
    print("{} translation-unit checks; {} failures".format(len(jobs), failures), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
