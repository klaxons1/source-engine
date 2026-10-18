# Underhell: Android launcher and gameplay port

## What this checkout builds

- Display name: **underhell** (lowercase, in every locale).
- Application ID: `com.valvesoftware.source.underhell`.
- Game-directory intent extra: `gamedir=underhell` (not `lostcoast`, not `Underhell`).
- Native client/server variant: `--build-games=underhell`, with the local Episodic
  baseline and the imported Underhell translation units on **both** sides.
- Icon: local `assets/android/underhell.png`, not the Lost Coast icon.
- APK: `srceng-mod-launcher/build/android/underhell.apk`. The original
  `mod-signed.apk` is also retained for the existing CI workflow, which still
  uploads it under its legacy `mod-apk` / `mod-release.apk` artifact names.

This is a **mod launcher**, not a replacement for the companion Source Engine
Android application. It starts `com.valvesoftware.source/org.libsdl.app.SDLActivity`
and supplies its own game directory and native library directory, as the template
already did. The APK does not contain Underhell's copyrighted models/maps/sounds
or the base Half-Life 2 content.

## Content layout: case matters

Put your legally obtained content in the data root configured in the companion
Source Engine app:

```text
<engine-content-root>/
    underhell/
        gameinfo.txt
        maps/
        materials/
        models/
        resource/
        scripts/
        sound/
        ...
    hl2/
    ep2/
    episodic/
    platform/
```

The outer directory **must be `underhell`**. Android treats `Underhell` and
`underhell` as different names. Do not lowercase all asset files indiscriminately:
references inside BSP/MDL/VMT files may rely on their authored case. The C++
include paths added by this port have been corrected against the actual Linux
checkout, e.g. `Sprite.h`, `BasePropDoor.h`, `npc_BaseZombie.h`, and
`materialsystem/itexture.h`.

`assets/underhell/gameinfo.txt` is an adapted example from the upstream commits.
Install it as `underhell/gameinfo.txt` if your existing gameinfo mounts Lost Coast
or the wrong content. Back up the old file first. Underhell is mounted first,
then HL2, then Episode Two/One fallback content. HL2 must precede the Episodes for
cinematic assets such as `models/blackout.mdl`. There is no `lostcoast` search path.
The build deliberately does not overwrite files in your phone's data directory.

Run a **read-only** case audit against unpacked resources:

```sh
python3 scripts/check-underhell-content.py /path/to/data/underhell \
    --base /path/to/data/hl2 --base /path/to/data/ep2 \
    --base /path/to/data/episodic
```

This checks the exact root/gameinfo spelling, case collisions, and literal C++
asset references that can be found among loose files. It does **not** parse VPKs,
BSPs, MDLs, dynamic asset names or material graphs. Unresolved loose references
are listed as unverified, not silently certified correct. Actual Underhell
resources were not supplied with this task, so their case and completeness
cannot be certified from this repository alone.

## Build

The existing CI prepares the launcher checkout, NDK r10e, Clang 11.1.0, JDK,
ImageMagick and signing tools. Native build entry point:

```sh
sh scripts/build-android-aarch64.sh
sh scripts/build-apk.sh
```

The native script initializes `lib`, `thirdparty`, and `ivp` recursively before
configuring Waf. The APK script pins the external template and SDK, configures
branding without the upstream Lost Coast/extras script, and stops on errors.
Waf failures stream normally and expose their diagnostic tail as CI annotations
(including `config.log` on configure failure) so compiler errors remain
inspectable through the GitHub API.
It does not `git pull` arbitrary launcher changes after native libraries have
been installed. Template revisions:

- `ItzVladik/srceng-mod-launcher`: `2174bf02eb7f46b457538dccecf3cbc42b6057d5`
- `ItzVladik/android-sdk`: `9c474caf7be38a887574291f611152fc24a7afe3`

`prepare-underhell-launcher.py` is idempotent, checks the manifest/Java intent
contract and application label, and rejects stale/mixed `lostcoast` packaging
rather than creating a wrongly branded APK. It does not touch installed native
libraries. Android package identity differs from the former Lost Coast package;
its launcher preferences are separate.

## Imported implementation and adaptations

Seven upstream commits, from `d563c5d` through `1111766`, were ported from:

https://github.com/klaxons1/source-sdk-2013-ce/tree/arena/01a01580-source-sdk-2013-ce

Exact commit IDs, source mappings and adaptation notes are recorded in
`upstream-port.json`. This is a source-level port, **not** a blind cherry-pick of
the SDK repository's Windows projects or SDK headers over the Android engine.
The gameinfo changes are adapted separately. The blood-material files added and
then deleted upstream remain deleted; the final material-precache fix is kept.
The engine's existing Bink ABI and its player-animation/platform changes are
preserved. A `max()` call on a network variable is adapted to use its integer
value explicitly. Windows-style HUD `swprintf` calls use the bounded portable
`V_swprintf_safe` helper for Android/Bionic. Touch input now updates the same free-aim cursor as desktop
mouse input; already-scaled angular deltas are not multiplied by desktop mouse
sensitivity again.

Preserved upstream audit documents are under `upstream/`. They describe both
implemented systems and unresolved/speculative behavior; their historical build
claims apply to the upstream environment, **not** this Android build. In
particular, this port does not establish 1:1 parity for AI, dismemberment, bullet
time, vehicles, all inventory items, or shader effects merely by importing them.

### Shader Editor limitation

Upstream contains an **optional bridge**, not the Shader Editor implementation.
The original Windows `shadereditor_2013.dll`/`shadereditor_2007.dll` cannot run on
Android. On Android the bridge now asks the engine's native library loader for
`shadereditor_2013` (a native `libshadereditor_2013.so` with compatible
`ShaderEditor005` ABI in the app's native library directory), rather than trying
to load a Windows DLL from external storage. No such ARM64 module is provided by
the seven imported commits. Without it, the optional bridge stays inactive and
its dependent night-vision/gas-mask postprocessing is **not implemented on
Android**. This limitation is explicit, not hidden behind a claimed successful
port. Porting the shader runtime is separate work.

## Verification

Offline regression checks:

```sh
python3 scripts/tests-underhell.py
sh -n scripts/build-apk.sh scripts/build-android-aarch64.sh
```

Host C++ syntax checks (requires submodules and GCC; these are **not** Android
compilation or linking):

```sh
python3 scripts/check-underhell-cpp.py
# Exercise Android preprocessor branches using the host compiler (still NOT an NDK build):
python3 scripts/check-underhell-cpp.py --android-branches
# Optional: check every client/server translation unit, including unchanged code.
python3 scripts/check-underhell-cpp.py --all
```

A release still requires a successful Android client/server + APK build, APK
inspection, installation with the companion engine app, and in-game checks using
the real content: starting a Chapter 1 map, save/load, inventory/use/drop,
weapons/ironsights, flashlight, mirrors/cameras, AI and transitions. No claim of
successful Android runtime testing is made by these host checks.
