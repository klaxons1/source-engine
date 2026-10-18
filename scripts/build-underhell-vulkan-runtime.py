#!/usr/bin/env python3
"""Build/package the owned SDL lifecycle, real Sarek and libadrenotools (not the engine targets)."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache/underhell-vulkan'
ADRENO = '8fae8ce254dfc1344527e05301e43f37dea2df80'
BYPASS = 'aa3975893d83ef1bc84c321ec60c65fbf1287887'
NDK = '6dcd51aede6a404a9917d9a159ed0c12fd9c8c08'
THIRDPARTY = 'c5b901ecef515ea068fa8b8a19ca5cd5353905cb'
RUNTIME_LIBRARIES = ('SDL2', 'hidapi', 'dxvk_sarek_d3d9', 'adrenotools', 'hook_impl',
                     'main_hook', 'file_redirect_hook', 'gsl_alloc_hook')


def run(*args, **kwargs):
    print('+', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, **kwargs)


def capture(*args):
    return subprocess.check_output(list(map(str, args)), text=True).strip()


def checkout(name, url, revision, sparse=None):
    dest = CACHE / name
    if not (dest / '.git').exists():
        run('git', 'clone', '--filter=blob:none', '--no-checkout', url, dest)
        if sparse:
            run('git', '-C', dest, 'sparse-checkout', 'set', '--no-cone', *sparse)
        run('git', '-C', dest, 'fetch', '--depth', '1', 'origin', revision)
        run('git', '-C', dest, 'checkout', '--detach', revision)
    if capture('git', '-C', dest, 'rev-parse', 'HEAD') != revision:
        raise RuntimeError('Unexpected dependency revision: ' + str(dest))
    return dest


def apply_patch(source, patch):
    stamp = source / '.underhell-patch-sha256'
    digest = hashlib.sha256(patch.read_bytes()).hexdigest()
    if stamp.exists():
        if stamp.read_text().strip() != digest:
            raise RuntimeError('Stale patched source; use a new digest-keyed cache directory')
        return
    run('git', 'apply', '--check', patch, cwd=source)
    run('git', 'apply', patch, cwd=source)
    stamp.write_text(digest + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk', type=Path, default=os.getenv('ANDROID_SAREK_NDK_HOME'))
    parser.add_argument('--sdk', type=Path, default=ROOT / 'artifacts/dxvk-sarek-android-arm64')
    parser.add_argument('--staging', type=Path, default=ROOT / 'srceng-mod-launcher/android')
    parser.add_argument('--jobs', type=int, default=min(4, os.cpu_count() or 1))
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    CACHE.mkdir(parents=True, exist_ok=True)
    ndk = args.ndk.resolve() if args.ndk else checkout('ndk-r23-' + NDK[:12],
        'https://github.com/khadas/android_common_common14-5.15_prebuilts_ndk-r23', NDK,
        ['/build/cmake/', '/sources/android/cpufeatures/', '/toolchains/llvm/prebuilt/linux-x86_64/',
         '/source.properties', '/NOTICE', '/NOTICE.toolchain'])
    if '23.1.7779620' not in (ndk / 'source.properties').read_text():
        raise RuntimeError('Use the tested NDK 23.1.7779620 for the Vulkan runtime')
    if capture('git', '-C', ROOT / 'thirdparty', 'rev-parse', 'HEAD') != THIRDPARTY:
        raise RuntimeError('Owned SDL must match the pinned thirdparty/SDL Java sources')
    run(sys.executable, ROOT / 'scripts/build-dxvk-sarek-android.py', '--ndk', ndk,
        '--output', args.sdk.resolve(), '--jobs', args.jobs)
    run(sys.executable, ROOT / 'scripts/test-underhell-sarek-math.py', '--sdk', args.sdk.resolve())
    adreno_patch = ROOT / 'scripts/experimental/adrenotools-underhell.patch'
    key = hashlib.sha256(adreno_patch.read_bytes()).hexdigest()[:12]
    adreno = checkout('adrenotools-' + ADRENO[:12] + '-' + key,
        'https://github.com/bylaws/libadrenotools', ADRENO)
    run('git', '-C', adreno, 'submodule', 'update', '--init', '--recursive')
    if capture('git', '-C', adreno / 'lib/linkernsbypass', 'rev-parse', 'HEAD') != BYPASS:
        raise RuntimeError('Unexpected liblinkernsbypass revision')
    apply_patch(adreno, adreno_patch)
    if capture('git', '-C', adreno, 'diff', '--binary', '--full-index', 'HEAD') != adreno_patch.read_text().strip():
        raise RuntimeError('Unexpected local adrenotools edits')
    sdl_patch = ROOT / 'scripts/experimental/sdl-underhell-vulkan.patch'
    sdl_key = hashlib.sha256(sdl_patch.read_bytes()).hexdigest()[:12]
    sdl_source = ROOT / 'thirdparty/SDL-src'
    sdl = CACHE / ('sdl-source-' + THIRDPARTY[:12] + '-' + sdl_key)
    if not sdl.exists():
        shutil.copytree(sdl_source, sdl, ignore=shutil.ignore_patterns('.git'))
        try:
            apply_patch(sdl, sdl_patch)
        except Exception:
            # Keep diagnostics, never reuse a partially prepared source tree.
            sdl.rename(sdl.with_name(sdl.name + '-failed-' + str(os.getpid())))
            raise
    else:
        apply_patch(sdl, sdl_patch)
    options = ['-G', 'Ninja', '-DCMAKE_POLICY_VERSION_MINIMUM=3.5',
        '-DCMAKE_TOOLCHAIN_FILE=' + str(ndk / 'build/cmake/android.toolchain.cmake'),
        '-DANDROID_ABI=arm64-v8a', '-DANDROID_STL=c++_static', '-DCMAKE_BUILD_TYPE=Release',
        '-DCMAKE_SHARED_LINKER_FLAGS=-Wl,-z,max-page-size=16384']
    adreno_build = CACHE / ('adrenotools-build-' + key)
    sdl_build = CACHE / ('sdl-build-' + sdl_key)
    run('cmake', '-S', adreno, '-B', adreno_build, *options,
        '-DANDROID_PLATFORM=android-28', '-DBUILD_SHARED_LIBS=ON', '-DCMAKE_CXX_STANDARD=17')
    run('cmake', '--build', adreno_build, '-j', args.jobs)
    run('cmake', '-S', sdl, '-B', sdl_build, *options,
        '-DANDROID_PLATFORM=android-26', '-DSDL_SHARED=ON', '-DSDL_STATIC=OFF', '-DVIDEO_VULKAN=ON')
    if '#define SDL_VIDEO_VULKAN 1' not in (sdl_build / 'include/SDL_config.h').read_text():
        raise RuntimeError('Owned SDL must support explicit Vulkan windows; refusing an EGL fallback')
    run('cmake', '--build', sdl_build, '-j', args.jobs)
    staging = args.staging.resolve()
    libs = staging / 'lib/arm64-v8a'
    libs.mkdir(parents=True, exist_ok=True)
    paths = {'SDL2': sdl_build / 'libSDL2.so', 'hidapi': sdl_build / 'libhidapi.so',
             'dxvk_sarek_d3d9': args.sdk.resolve() / 'libdxvk_sarek_d3d9.so',
             'adrenotools': adreno_build / 'libadrenotools.so'}
    for name in ('hook_impl', 'main_hook', 'file_redirect_hook', 'gsl_alloc_hook'):
        paths[name] = adreno_build / 'src/hook' / ('lib' + name + '.so')
    tools = ndk / 'toolchains/llvm/prebuilt/linux-x86_64/bin'
    hashes = {}
    for name, source in paths.items():
        target = libs / source.name
        shutil.copy2(source, target)
        run(tools / 'llvm-strip', '--strip-unneeded', target)
        dynamic = capture(tools / 'llvm-readelf', '-d', target)
        if 'libc++_shared.so' in dynamic:
            raise RuntimeError('Do not introduce a companion C++ runtime conflict: ' + name)
        required_export = {'SDL2': 'SDL_UnderhellSetSurfaceCallback',
            'adrenotools': 'adrenotools_underhell_custom_driver_loaded'}.get(name)
        if required_export and required_export not in capture(tools / 'llvm-nm', '-D', '--defined-only', target).split():
            raise RuntimeError('Missing mandatory native lifecycle/driver-status export: ' + name)
        hashes[target.name] = hashlib.sha256(target.read_bytes()).hexdigest()
    notices = staging / 'assets/licenses'
    shutil.copytree(args.sdk.resolve() / 'licenses', notices, dirs_exist_ok=True)
    shutil.copy2(adreno / 'LICENSE', notices / 'libadrenotools.txt')
    shutil.copy2(adreno / 'lib/linkernsbypass/LICENSE', notices / 'liblinkernsbypass.txt')
    shutil.copy2(sdl / 'LICENSE.txt', notices / 'SDL2.txt')
    report = {'status': 'runtime libraries built; engine link/APK/device verification separate',
        'sarek': '0c0e8f6f62c7cb37dbf5d38413517efa00c08fef', 'adrenotools': ADRENO,
        'linkernsbypass': BYPASS, 'thirdparty': THIRDPARTY, 'ndk': NDK,
        'adrenotools_patch': key, 'sdl_patch': sdl_key, 'libraries_sha256': hashes}
    (staging / 'assets/underhell-vulkan.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Vulkan runtime staged. This does NOT prove game rendering on Android.')


if __name__ == '__main__':
    main()
