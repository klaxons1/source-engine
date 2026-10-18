#!/bin/sh
set -eu

# Resolve all paths against this checkout, not the caller's current directory.
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
LAUNCHER="$ROOT/srceng-mod-launcher"
LAUNCHER_REV=2174bf02eb7f46b457538dccecf3cbc42b6057d5
SDK_REV=9c474caf7be38a887574291f611152fc24a7afe3

# Do not git-pull an unreviewed template after installing the native libraries.
git -C "$LAUNCHER" fetch --depth 1 origin "$LAUNCHER_REV"
git -C "$LAUNCHER" checkout --detach "$LAUNCHER_REV"
python3 "$ROOT/scripts/test-underhell-launch-contract.py"
python3 "$ROOT/scripts/test-underhell-fonts.py"
python3 "$ROOT/scripts/tests-underhell-touch.py"
python3 "$ROOT/scripts/build-underhell-touch-assets.py" --check --launcher "$LAUNCHER"
python3 "$ROOT/scripts/prepare-underhell-launcher.py" "$LAUNCHER"

# Use our own icon, not extras/icons/lc.png (Lost Coast).
for entry in drawable:48 drawable-hdpi:72 drawable-xhdpi:96 drawable-xxhdpi:144 drawable-xxxhdpi:192; do
    density=${entry%:*}
    size=${entry#*:}
    mkdir -p "$LAUNCHER/android/res/$density"
    convert -background none "$ROOT/assets/android/underhell.png" -resize "${size}x${size}" \
        "$LAUNCHER/android/res/$density/mod_icon.png"
done

cd "$LAUNCHER"
if [ ! -d android-sdk ]; then
    git clone --depth 1 --no-checkout https://github.com/ItzVladik/android-sdk android-sdk
fi
git -C android-sdk fetch --depth 1 origin "$SDK_REV"
git -C android-sdk checkout --detach "$SDK_REV"
export ANDROID_SDK_HOME="$PWD/android-sdk"
chmod +x waf
./waf configure -T release --javac-source-target=8
./waf build
python3 "$ROOT/scripts/verify-underhell-apk.py" build/android/mod-signed.apk \
    --sdk "$ANDROID_SDK_HOME" --staging android
# Keep the workflow's existing mod-signed.apk path, and offer a branded copy too.
cp build/android/mod-signed.apk build/android/underhell.apk
