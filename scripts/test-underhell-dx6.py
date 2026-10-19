#!/usr/bin/env python3
"""Compile the real legacy shader units and check isolated profile selection.

Host syntax / CPU policy checks, not an Android GPU rendering test.
"""
import concurrent.futures
import os
from pathlib import Path
import subprocess
import tempfile
from underhell_dx6 import shader_sources, MODULES

ROOT = Path(__file__).resolve().parents[1]


def main():
    compiler = os.environ.get('CXX', 'c++')
    directory = ROOT / 'materialsystem/stdshaders'
    sources = shader_sources(directory)
    flags = [compiler, '-fsyntax-only', '-std=gnu++11', '-DGNUC=1', '-DPOSIX', '-D_POSIX',
             '-DLINUX', '-D_LINUX', '-DUNDERHELL_SAREK_DX6=1', '-DSTDSHADER_DX6_DLL_EXPORT=1']
    flags += ['-I' + str(ROOT / name) for name in ('public', 'public/tier0', 'public/tier1',
                                                 'materialsystem/stdshaders', 'materialsystem')]

    def compile_shader(name):
        result = subprocess.run(flags + [str(directory / name)], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(name + '\n' + result.stderr)

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as workers:
        list(workers.map(compile_shader, sources))
    print('PASS: all 32 actual Source DX6 shader translation units compile (no VS/PS shader binaries)')

    header = (ROOT / 'public/materialsystem/imaterialsystem.h').read_text()
    start = header.index('#if defined(UNDERHELL_SAREK_DX6)')
    policy = header[start:header.index('#endif', start) + len('#endif')]
    with tempfile.TemporaryDirectory(prefix='underhell-dx6-') as tmp:
        cpp = Path(tmp) / 'minimum.cpp'
        cpp.write_text(policy + '\nstatic_assert(ABSOLUTE_MINIMUM_DXLEVEL == EXPECTED, "Wrong renderer floor");\nint main() {}\n')
        for name, definitions in (
            ('legacy', ['-DUNDERHELL_SAREK_DX6=1', '-DPOSIX=1', '-DEXPECTED=60']),
            ('normal-native-or-gles', ['-DPOSIX=1', '-DEXPECTED=90']),
            ('windows', ['-DEXPECTED=80'])):
            subprocess.run([compiler, '-std=c++11', '-fsyntax-only', str(cpp)] + definitions, check=True)
            print('PASS: actual minimum-DX policy:', name)
    launcher = (ROOT / 'launcher/launcher.cpp').read_text()
    for module in ('materialsystem_sarek_dx6', 'shaderapidx9_sarek_dx6'):
        assert '"' + module + '" DLL_EXT_STRING' in launcher
    system = (ROOT / 'materialsystem/shadersystem.cpp').read_text()
    branch = system.split('#ifdef UNDERHELL_SAREK_DX6', 1)[1].split('#endif', 1)[0]
    assert 'LoadShaderDLL("stdshader_dx6_sarek" DLL_EXT_STRING)' in branch and 'return;' in branch
    assert set(MODULES) == {'materialsystem_sarek_dx6', 'shaderapidx9_sarek_dx6', 'stdshader_dx6_sarek'}
    print('PASS: separate material system / native shaderapi / fixed-function dictionary, normal defaults unchanged')


if __name__ == '__main__':
    main()
