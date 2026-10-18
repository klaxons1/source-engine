#!/bin/sh
set -e
# Native codec and real query/upload-policy regression tests, with an independent
# ASTC decoder. Test-only wheels stay out of the launcher and the source tree.
python3 -m pip install --quiet --target .cache/underhell-port/renderer-test-python texture2ddecoder==1.0.6
PYTHONPATH="$PWD/.cache/underhell-port/renderer-test-python${PYTHONPATH:+:$PYTHONPATH}" python3 scripts/tests-underhell-renderer.py
# Required target libraries, headers and physics sources are submodules.
git submodule update --init --recursive
# Separate modern-toolchain runtime: static C++ and C/COM boundaries only.
# Keep the established r10e/GNUSTL toolchain for the Source/game modules.
python3 -m pip install --quiet --target .cache/underhell-port/vulkan-build-python cmake==3.31.6 ninja==1.11.1.4 meson==1.8.0
export PYTHONPATH="$PWD/.cache/underhell-port/vulkan-build-python${PYTHONPATH:+:$PYTHONPATH}"
export PATH="$PWD/.cache/underhell-port/vulkan-build-python/bin:$PATH"
python3 scripts/build-underhell-vulkan-runtime.py
export ANDROID_NDK_HOME=$PWD/android-ndk-r10e/
export PATH="$PWD/clang+llvm-11.1.0-x86_64-linux-gnu-ubuntu-16.04/bin:$PATH"
python3 scripts/run-android-waf.py --config-log build/config.log ./waf configure -T release --build-games=underhell --prefix=srceng-mod-launcher/android --android=aarch64,host,21 --target=../aarch64 --enable-opus --togles --disable-warns --sarek-sdk="$PWD/artifacts/dxvk-sarek-android-arm64"
# Fail fast on the new renderer before compiling the unchanged game modules.
python3 scripts/run-android-waf.py ./waf install --target=shaderapidx9 --strip
python3 scripts/verify-underhell-renderer.py srceng-mod-launcher/android/lib/arm64-v8a/libshaderapidx9.so
python3 scripts/run-android-waf.py ./waf install --target=shaderapidx9_sarek,launcher_sarek --strip
python3 scripts/run-android-waf.py ./waf install --target=client,server --strip

if [ -e "srceng-mod-launcher/android/lib/arm64-v8a/README.md" ]; then
	rm srceng-mod-launcher/android/lib/arm64-v8a/README.md
fi
