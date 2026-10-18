#!/bin/sh
set -e
# Native codec and real query/upload-policy regression tests, with an independent
# ASTC decoder. Test-only wheels stay out of the launcher and the source tree.
python3 -m pip install --quiet --target .cache/underhell-port/renderer-test-python texture2ddecoder==1.0.6
PYTHONPATH="$PWD/.cache/underhell-port/renderer-test-python${PYTHONPATH:+:$PYTHONPATH}" python3 scripts/tests-underhell-renderer.py
# Required target libraries, headers and physics sources are submodules.
git submodule update --init --recursive
export ANDROID_NDK_HOME=$PWD/android-ndk-r10e/
export PATH="$PWD/clang+llvm-11.1.0-x86_64-linux-gnu-ubuntu-16.04/bin:$PATH"
python3 scripts/run-android-waf.py --config-log build/config.log ./waf configure -T release --build-games=underhell --prefix=srceng-mod-launcher/android --android=aarch64,host,21 --target=../aarch64 --enable-opus --togles --disable-warns
python3 scripts/run-android-waf.py ./waf install --target=client,server,shaderapidx9 --strip
python3 scripts/verify-underhell-renderer.py srceng-mod-launcher/android/lib/arm64-v8a/libshaderapidx9.so

if [ -e "srceng-mod-launcher/android/lib/arm64-v8a/README.md" ]; then
	rm srceng-mod-launcher/android/lib/arm64-v8a/README.md
fi
