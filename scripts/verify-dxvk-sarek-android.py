#!/usr/bin/env python3
"""Static ELF checks only. This does NOT test Android loading or Vulkan rendering."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def inspect_elf(library, tools):
    def run(tool, *args):
        return subprocess.check_output([str(tools / tool), *args, str(library)], text=True)

    header = run('llvm-readelf', '-h')
    if not re.search(r'Machine:\s+AArch64', header) or not re.search(r'Type:\s+DYN', header):
        raise ValueError('Expected an AArch64 ELF shared library')
    dynamic = run('llvm-readelf', '-d')
    needed = re.findall(r'\(NEEDED\).*\[(.*?)\]', dynamic)
    allowed = {'libdl.so', 'libandroid.so', 'libm.so', 'libc.so', 'liblog.so'}
    if set(needed) != allowed:
        raise ValueError(f'Unexpected dependencies (including missing system libraries): {needed}')
    if 'Library soname: [libdxvk_sarek_d3d9.so]' not in dynamic:
        raise ValueError('Wrong SONAME')
    segments = run('llvm-readelf', '-lW')
    aligns = re.findall(r'^\s*LOAD\s+.*\s(0x[0-9a-fA-F]+)\s*$', segments, re.M)
    if not aligns or any(int(a, 16) < 16384 for a in aligns):
        raise ValueError('Library LOAD segments must have at least 16 KiB alignment')
    symbols = run('llvm-nm', '-D', '--defined-only')
    exports = sorted(line.split()[-1] for line in symbols.splitlines() if line.strip())
    required = {'Direct3DCreate9', 'Direct3DCreate9Ex', 'DXVKSarekSetAndroidDisplay',
                'DXVKSarekSetAndroidWindowProvider', 'DXVKSarekNotifyAndroidSurface'}
    if not required <= set(exports):
        raise ValueError(f'Missing public exports: {required - set(exports)}')
    if any(name.startswith('_Z') for name in exports):
        raise ValueError('C++ internals leaked into the public ABI')
    undefined = run('llvm-nm', '-D', '--undefined-only')
    if re.search(r'\b(LoadLibrary[AW]?|GetProcAddress|FreeLibrary|GetModuleHandle[AW]?|CreateFile[AW]?|DeviceIoControl)\b', undefined):
        raise ValueError('Unresolved Win32 imports')
    return {
        'checks': 'PASS (static ELF inspection, NOT a device/runtime test)',
        'machine': 'AArch64', 'android_api': 26,
        'soname': 'libdxvk_sarek_d3d9.so', 'needed': needed,
        'load_segment_alignment': [int(a, 16) for a in aligns],
        'exports': exports, 'bytes': library.stat().st_size,
        'sha256': hashlib.sha256(library.read_bytes()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    parser.add_argument('--tools', required=True, type=Path, help='NDK LLVM bin directory')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    text = json.dumps(inspect_elf(args.library, args.tools), indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
