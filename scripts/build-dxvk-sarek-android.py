#!/usr/bin/env python3
"""Pinned native Android/ARM64 Sarek D3D9 experiment. Does NOT build/change an APK."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = ROOT / 'scripts/experimental/dxvk-sarek'
PINS = {
    'sarek': ('https://github.com/pythonlover02/dxvk-sarek.git', '0c0e8f6f62c7cb37dbf5d38413517efa00c08fef'),
    'native': ('https://github.com/fbraz3/dxvk.git', '870371520577d3781690f167ec33c45a0f17fd43'),
    'directx': ('https://github.com/Joshua-Ashton/mingw-directx-headers.git', '9df86f2341616ef1888ae59919feaa6d4fad693d'),
    'glslang': ('https://github.com/KhronosGroup/glslang.git', '77551c429f86c0e077f26552b7c1c0f12a9f235e'),
}


def run(*cmd, cwd=None, env=None):
    print('+', ' '.join(map(str, cmd)), flush=True)
    subprocess.run(list(map(str, cmd)), cwd=cwd, env=env, check=True)


def capture(*cmd):
    return subprocess.check_output(list(map(str, cmd)), text=True).strip()


def fetch(cache, name, suffix=''):
    url, revision = PINS[name]
    dest = cache / (name + '-' + revision[:12] + suffix)
    # Never reset or clean an existing checkout. A wrong revision is an error.
    if not (dest / '.git').exists():
        dest.mkdir(parents=True, exist_ok=True)
        run('git', 'init', '-q', dest)
    try:
        head = capture('git', '-C', dest, 'rev-parse', '--verify', 'HEAD')
    except subprocess.CalledProcessError:
        run('git', '-C', dest, 'fetch', '--depth', '1', url, revision)
        run('git', '-C', dest, 'checkout', '--detach', 'FETCH_HEAD')
        head = capture('git', '-C', dest, 'rev-parse', 'HEAD')
    if head != revision:
        raise RuntimeError(f'Refusing to overwrite unexpected checkout: {dest}')
    if name != 'sarek':
        run('git', '-C', dest, 'diff', '--exit-code', 'HEAD', '--')
    return dest


def copy_tree(src, dst):
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.git'))


def prepare(cache):
    patch = SUPPORT / 'android-arm64.patch'
    digest = hashlib.sha256(patch.read_bytes()).hexdigest()
    source = fetch(cache, 'sarek', '-' + digest[:12])
    stamp = source / '.underhell-android-patch'
    if not stamp.exists():
        run('git', '-C', source, 'apply', '--check', patch)
        run('git', '-C', source, 'apply', patch)
        for path in ('src/util/util_android_compat.h', 'src/wsi/android/wsi_android.cpp',
                     'src/d3d9/d3d9.android.map'):
            run('git', '-C', source, 'add', '-N', path)
        stamp.write_text(digest + '\n')
    if stamp.read_text().strip() != digest:
        raise RuntimeError('Patch stamp mismatch')
    actual = capture('git', '-C', source, 'diff', '--binary', '--full-index', '--no-ext-diff',
                     'HEAD', '--', '.', ':!include/native')
    if actual != patch.read_text().strip():
        raise RuntimeError(f'Experimental source has unexpected local edits: {source}')
    native = fetch(cache, 'native')
    directx = fetch(cache, 'directx')
    copy_tree(native / 'include/native/windows', source / 'include/native/windows')
    copy_tree(directx, source / 'include/native/directx')
    run('git', '-C', source, 'submodule', 'update', '--init', '--depth', '1')
    return source, native, directx, digest


def host_tests(source, cache, compiler):
    exe = cache / 'wsi-host-test'
    run(compiler, '-std=c++17', '-Wall', '-Wextra', '-Wno-unused-parameter',
        '-Wno-missing-field-initializers', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
        '-I' + str(ROOT / 'scripts/tests/sarek-android'), '-I' + str(source / 'src'),
        '-I' + str(source / 'include/native/windows'), '-I' + str(source / 'include/vulkan/include'),
        '-include', source / 'src/util/util_android_compat.h',
        ROOT / 'scripts/tests/sarek-android/wsi.cpp', source / 'src/wsi/android/wsi_android.cpp',
        source / 'src/util/util_string.cpp', '-o', exe)
    run(exe)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk', type=Path, default=os.getenv('ANDROID_NDK_HOME') or os.getenv('ANDROID_NDK_ROOT'))
    parser.add_argument('--cache', type=Path, default=ROOT / '.cache/dxvk-sarek-android')
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/dxvk-sarek-android-arm64')
    parser.add_argument('--jobs', type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument('--host-cxx', default='c++')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    cache = args.cache.resolve()
    if cache == ROOT or ROOT.is_relative_to(cache) or cache.is_relative_to(ROOT / '.git'):
        parser.error('--cache must not be the repository root or its ancestor')
    cache.mkdir(parents=True, exist_ok=True)
    if not args.prepare_only and not args.ndk:
        parser.error('--ndk or ANDROID_NDK_HOME is required (tested: NDK 23.1.7779620)')
    source, native, directx, digest = prepare(cache)
    host_tests(source, cache, args.host_cxx)
    if args.prepare_only:
        print(f'Prepared source and passed host-only tests: {source}')
        return
    ndk = Path(args.ndk).resolve()
    tools = ndk / 'toolchains/llvm/prebuilt/linux-x86_64/bin'
    for tool in ('aarch64-linux-android26-clang', 'aarch64-linux-android26-clang++',
                 'llvm-ar', 'llvm-strip', 'llvm-readelf', 'llvm-nm'):
        if not (tools / tool).exists():
            raise RuntimeError(f'Missing NDK Linux host tool: {tools / tool}')
    for tool in ('cmake', 'ninja', 'meson'):
        if not shutil.which(tool):
            raise RuntimeError(f'Install {tool} and add it to PATH')
    glslang = fetch(cache, 'glslang')
    glslang_build = cache / 'glslang-host'
    run('cmake', '-S', glslang, '-B', glslang_build, '-G', 'Ninja',
        '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_TESTING=OFF', '-DENABLE_OPT=OFF',
        '-DENABLE_HLSL=OFF', '-DENABLE_GLSLANG_BINARIES=ON',
        '-DCMAKE_C_COMPILER=' + str(shutil.which('cc')),
        '-DCMAKE_CXX_COMPILER=' + str(shutil.which(args.host_cxx)))
    run('cmake', '--build', glslang_build, '--target', 'glslangValidator', '-j', args.jobs)
    cross = cache / 'android-arm64.ini'
    cross.write_text(f"""[binaries]
c = '{tools}/aarch64-linux-android26-clang'
cpp = '{tools}/aarch64-linux-android26-clang++'
ar = '{tools}/llvm-ar'
strip = '{tools}/llvm-strip'
[host_machine]
system = 'android'
cpu_family = 'aarch64'
cpu = 'aarch64'
endian = 'little'
[properties]
needs_exe_wrapper = true
""")
    env = dict(os.environ, PATH=str(glslang_build / 'StandAlone') + os.pathsep + os.environ['PATH'])
    build = cache / ('android-build-' + digest[:12])
    setup = ['meson', 'setup']
    if (build / 'meson-private/coredata.dat').exists():
        setup.append('--reconfigure')
    run(*setup, build, source, '--cross-file', cross, '--buildtype', 'release',
        '-Denable_d3d9=true', '-Denable_dxgi=false', '-Denable_d3d8=false',
        '-Denable_ddraw=false', '-Denable_d3d10=false', '-Denable_d3d11=false', env=env)
    run('ninja', '-C', build, '-j', args.jobs, env=env)
    output = args.output.resolve()
    if output == ROOT or ROOT.is_relative_to(output) or output.is_relative_to(ROOT / '.git'):
        raise RuntimeError('Output must not be the repository root, an ancestor or .git')
    output.mkdir(parents=True, exist_ok=True)
    library = output / 'libdxvk_sarek_d3d9.so'
    shutil.copy2(build / 'src/d3d9/libdxvk_sarek_d3d9.so', library)
    run(tools / 'llvm-strip', '--strip-unneeded', library)
    run(sys.executable, ROOT / 'scripts/verify-dxvk-sarek-android.py', library,
        '--tools', tools, '--output', output / 'elf-check.json')
    copy_tree(source / 'include/native/windows', output / 'include/windows')
    copy_tree(source / 'include/native/directx', output / 'include/directx')
    shutil.copy2(SUPPORT / 'android-host.h', output / 'include/android-host.h')
    licenses = output / 'licenses'
    licenses.mkdir(exist_ok=True)
    for src, name in ((source / 'LICENSE', 'DXVK-Sarek.txt'), (native / 'LICENSE', 'DXVK-native.txt'),
                      (directx / 'COPYING.MinGW-w64.txt', 'DirectX-MinGW.txt'),
                      (directx / 'README.md', 'DirectX-header-license-explanation.md'),
                      (ndk / 'NOTICE.toolchain', 'Android-NDK-toolchain.txt'),
                      (ndk / 'NOTICE', 'Android-NDK.txt'),
                      (SUPPORT / 'licenses/LGPL-2.1.txt', 'LGPL-2.1.txt')):
        shutil.copy2(src, licenses / name)
    for relative in ('scripts/build-dxvk-sarek-android.py', 'scripts/verify-dxvk-sarek-android.py',
                     'scripts/experimental/dxvk-sarek/android-arm64.patch',
                     'scripts/experimental/dxvk-sarek/android-host.h',
                     'scripts/experimental/dxvk-sarek/licenses/LGPL-2.1.txt',
                     'scripts/tests/sarek-android/wsi.cpp',
                     'scripts/tests/sarek-android/android/native_window.h',
                     'docs/underhell/DXVK_SAREK_ANDROID.md'):
        target = output / 'repo-support' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    shutil.copy2(ROOT / 'docs/underhell/DXVK_SAREK_ANDROID.md', output / 'README.md')
    manifest = {
        'status': 'EXPERIMENTAL: compiled, not tested on Android hardware, not integrated into Underhell',
        'sources': {name: {'url': url, 'commit': rev} for name, (url, rev) in PINS.items()},
        'patch_sha256': digest, 'ndk': (ndk / 'source.properties').read_text(),
        'compiler': capture(tools / 'aarch64-linux-android26-clang++', '--version'),
        'meson': capture('meson', '--version'), 'cmake': capture('cmake', '--version').splitlines()[0],
        'glslang': capture(glslang_build / 'StandAlone/glslangValidator', '--version'),
        'android_api': 26, 'abi': 'arm64-v8a',
        'host_tests': 'PASS: WSI mock/UTF-8 with ASan+UBSan; no GPU test',
        'apk_changed': False, 'runtime_tested': False,
        'sarek_submodules': capture('git', '-C', source, 'submodule', 'status'),
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    archive = output.with_name(output.name + '.tar.xz')
    with tarfile.open(archive, 'w:xz') as tar:
        tar.add(output, arcname=output.name)
    print(f'Native library package: {archive}\nSHA256: {hashlib.sha256(archive.read_bytes()).hexdigest()}')
    print('NOT an APK. Loading, presentation, pause/resume and performance remain untested on a device.')


if __name__ == '__main__':
    main()
