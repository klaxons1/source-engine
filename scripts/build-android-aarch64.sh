#!/bin/sh
set -e
# Required target libraries, headers and physics sources are submodules.
git submodule update --init --recursive
export ANDROID_NDK_HOME=$PWD/android-ndk-r10e/
export PATH="$PWD/clang+llvm-11.1.0-x86_64-linux-gnu-ubuntu-16.04/bin:$PATH"
python3 scripts/run-android-waf.py --config-log build/config.log ./waf configure -T release --build-games=underhell --prefix=srceng-mod-launcher/android --android=aarch64,host,21 --target=../aarch64 --enable-opus --togles --disable-warns
python3 scripts/run-android-waf.py ./waf install --target=client,server --strip

if [ -e "srceng-mod-launcher/android/lib/arm64-v8a/README.md" ]; then
	rm srceng-mod-launcher/android/lib/arm64-v8a/README.md
fi
