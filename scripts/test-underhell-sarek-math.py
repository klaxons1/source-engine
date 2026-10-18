#!/usr/bin/env python3
"""Numerical tests compile the actual production math source with a host allocator adapter."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sdk', type=Path, default=ROOT / 'artifacts/dxvk-sarek-android-arm64')
    p.add_argument('--cxx', default=os.environ.get('CXX', 'c++'))
    args = p.parse_args()
    with tempfile.TemporaryDirectory(prefix='sarek-math-') as tmp:
        exe = Path(tmp) / 'test'
        flags = ['-std=c++14', '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-g']
        flags += ['-D' + d for d in ('UNDERHELL_SAREK=1', 'POSIX=1', 'LINUX=1', '_LINUX=1',
            'GNUC=1', 'PLATFORM_64BITS=1', 'NO_MEMOVERRIDE_NEW_DELETE', 'USE_SDL=1', '_DLL_EXT=.so')]
        flags += ['-I' + str(ROOT / d) for d in ('scripts/tests/sarek-math', 'materialsystem/shaderapidx9',
            'public', 'public/tier0', 'public/tier1', 'thirdparty/SDL')]
        flags += ['-I' + str(args.sdk / 'include' / d) for d in ('windows', 'directx')]
        subprocess.run([args.cxx, *flags, str(ROOT / 'scripts/tests/sarek-math/math.cpp'),
            str(ROOT / 'materialsystem/shaderapidx9/sarek_math.cpp'), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
