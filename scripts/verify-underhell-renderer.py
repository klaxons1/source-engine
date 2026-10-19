#!/usr/bin/env python3
"""Reject a renderer which would bind to the companion's already-loaded TOGL."""
from pathlib import Path
import os
import re
import subprocess
import sys


def verify(library):
    data = library.read_bytes()
    if b'UNDERHELL_RENDERER_ASTC_V1' not in data:
        raise ValueError('Missing private Underhell renderer identity')
    tool = os.environ.get('READELF', 'readelf')
    dynamic = subprocess.check_output([tool, '-d', str(library)], text=True)
    if re.search(r'NEEDED.*\[libtogl\.so\]', dynamic):
        raise ValueError('Renderer still depends on the stock libtogl.so')
    if 'SYMBOLIC' not in dynamic:
        raise ValueError('Renderer must bind both its data and functions locally (-Bsymbolic)')
    symbols = subprocess.check_output([tool, '--dyn-syms', '--wide', str(library)], text=True)
    if not re.search(r'GLOBAL\s+DEFAULT\s+\d+\s+CreateInterface\b', symbols):
        raise ValueError('Shaderapi factory is missing/not exported')
    relocs = subprocess.check_output([tool, '-r', '--wide', str(library)], text=True)
    if re.search(r'\b(?:gGL|ToGLConnectLibraries|_Z\w*ToGLConnectLibraries\w*)\b', relocs):
        raise ValueError('Private GL entrypoints still have interposable dynamic relocations')
    print('Private shaderapi ELF: identity, factory, local symbol binding, no stock TOGL dependency: PASS')


if __name__ == '__main__':
    verify(Path(sys.argv[1]))
