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

## Underhell touch controls and TOGL ES load

The Underhell client installs 14 action buttons plus an optional graphics-profile
button after loading the existing touch profile. **Install/update the launcher
APK and start a map: no separate ZIP, copying materials, console exec or launcher
arguments are needed.** On the first map after the update a versioned migration
enables `touch_enable`, `touch_draw` and `uh_touch_buttons`, shows the new actions,
and saves the profile with a backup. Subsequent maps respect deliberate hiding
or disabling. Late startup profiles that remove all buttons have missing actions
restored at map start. Existing positions, commands and colors are preserved;
only missing `uh_*` buttons are added. The
normal joystick, look, attack and jump buttons remain. `uh_touch_buttons 0/1`
hides/shows the extras; `uh_touch_reset` resets only the Underhell controls.
A command-button press consumes that finger rather than also dragging the
fullscreen joystick/look zone; another finger can still move or aim.

`scripts/build-underhell-touch-assets.py` reproducibly generates 15 original
64x64 VTF 7.2 RGBA8888 icons and matching VMTs, a manual installation CFG and a
compact palette/RLE native fallback with byte-identical pixels. No Pillow or
external texture converter is required. The APK build checks generated files,
runs the production C++ policy tests, packs the VTF/VMTs into an inline VPK v1,
and updates the extraction checksum. The final APK gate also verifies that
`assets/extras_dir.vpk` is present and identical to the staged file. No gameinfo
or copyrighted game content is packaged. The fallback makes automatic native
buttons independent of whether a particular companion mounts the extras VPK.

All new icons share the existing touch atlas/draw batch. Atlas rebuilds happen
before drawing and not on each button or visibility toggle. Rebuilds release
old texture IDs, convert BGRA correctly, check rectangle packing, and grow the
atlas before copying rather than using unchecked failed placements. Initial
texture pointers are zeroed; an empty atlas does not issue an invalid draw.

`uh_android_fast 1` (the lightning button) is **optional and off by default**.
It lowers GPU load by disabling flashlight-depth and render-to-texture shadows,
forced expensive/entity water reflections and motion blur. It does not change
VSync, force unsafe threading, remove synchronization, or turn off night vision
or the flashlight beam. `uh_android_fast 0` restores the captured values in the
current session, unless the player has manually changed a setting since enabling
it. Missing companion CVars are skipped. Turn it off before saving/exit if you
want the original archived graphics settings retained. This is a quality tradeoff,
not proof of a TOGL ES renderer speedup; actual profiling needs phone/GPU/FPS data.
The companion renderer itself is not replaced by a client/server-only mod APK.

For the **already-installed APK**, merge the loose `assets/underhell/materials`
and `assets/underhell/cfg` files into the resource directory, then run
`exec underhell_touch.cfg` (or add `+exec underhell_touch.cfg` to launcher arguments).
This adds 14 existing gameplay commands, without requiring a new native build;
use `touch_writeconfig` to save the layout. The optional manual
`underhell_android_fast.cfg` uses existing renderer CVars but is **not** an
in-session reversible toggle: back up `config.cfg` first. See
`assets/underhell/README-touch-ru.txt`. The manual pack does not add new native
commands, touch input fixes or automatic installation to an old APK.

## If Lost Coast starts or Underhell features are missing

The former sender relied only on `gamedir` / `gamelibdir` Intent extras. The
reviewed companion (`nillerusr/srceng-android`, `7fb280dadf9c0199d1fa287844a02292ee9d281a`)
uses a `singleTask` SDLActivity with no `onNewIntent` handler: a repeated launch
can merely resume the previous game without rerunning `ValveActivity2.initNatives`.
This is a concrete restart hazard, **not** proof of what happened on an unseen
phone or in a different installed companion fork.

The updated mod sender:

- starts a fresh companion task with `NEW_TASK | CLEAR_TASK` instead of resuming
  the previous SDLActivity; **save any running game before starting Underhell**;
- always sends nonempty `-game underhell -defaultgamedir underhell` argv, removes
  old game-selection switches from the mod's saved arguments, and keeps other
  quoted arguments intact;
- requests native library extraction and refuses to launch if readable ARM ELF
  `libclient.so` / `libserver.so` with this port's identity markers are missing;
- logs the requested game, arguments and native path under `UnderhellLaunch`,
  and displays launch exceptions instead of silently ignoring them.

A final APK gate checks the *compiled* package and all application labels using
SDK aapt/aapt2, verifies ARM64 client/server identity markers in the packaged ELF
files, and compares their SHA-256 hashes with the installed native build outputs.
The actual Java policy is compiled and executed in the APK build before branding.

For a phone-side check, first save/exit and **force-stop Source Engine** in
Android settings, install this updated APK and open the **underhell** icon (not
the generic Source Engine or old Lost Coast icon). In the engine console run:

```text
uh_client_port_status
uh_server_port_status
```

The server command is available after starting a local map. These commands print
`UNDERHELL_PORT_CLIENT_V1` / `UNDERHELL_PORT_SERVER_V1`, the source revision, actual
game directory and `APP_MOD_LIB`. Both commands must exist in the new port. An
unknown command indicates that the corresponding port module is not loaded;
changing resource files alone cannot add native gameplay features to a stock DLL.
The same identities are logged when a map initializes.

If the problem persists, supply the companion app/version, the complete contents
of `underhell/gameinfo.txt`, and the launch log. With adb, useful Java-side logs
are `adb logcat -s UnderhellLaunch SRCAPK`; also attach the engine's `engine.log`
or the console output of the two status commands. `SRCAPK` should show the
received Underhell arguments and the native engine log should show the mod
library path. If the directory is correct but Lost Coast content still appears,
check the actual installed gameinfo SearchPaths and map/autoexec settings. The
repository's example gameinfo is not automatically written onto the phone.

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
