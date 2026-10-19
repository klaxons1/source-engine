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


## Experimental ASTC renderer checkbox

The launcher now has **ASTC-текстуры (экспериментально, нужен перезапуск)**,
default **off**, saved in its `underhell_astc` preference. Close the engine
completely before changing it; the existing clear-task launch contract is retained.
The checkbox owns `-uh_astc`: stale copies in saved/free-form arguments are removed.
There are no manual texture archives to install; the 15 embedded touch controls
and their first-map activation are unchanged.

This APK includes a **private `libshaderapidx9.so`**, not just a new `libtogl.so`:
the companion already links/loads its own TOGL before loading the mod. The shader
module is explicitly found through `APP_MOD_LIB`; it embeds this checkout's TOGLES,
uses `-Bsymbolic` for both data/functions, initializes its own GL entrypoint table
against the companion's already-current SDL context, and uses the existing
`ILauncherMgr` window/presentation interface. No companion APK replacement or
ELF search-path override is required. The launcher refuses missing/wrong renderer
identity/ABI; the build verifies ELF local binding and absence of a `libtogl.so`
dependency. This isolation still requires testing with the actual companion/device.
The updated renderer is loaded even with the checkbox off; off disables the ASTC
codec, not the renderer's query/decompression fixes.

### Format selection and correctness

- Query the driver's actual compressed-format list once, per process. Prefer
  **native support for the exact DXT + linear/sRGB format**: it avoids transcoding
  entirely. Previously the DXT1 extension bit incorrectly gated DXT3/5 too.
- If that exact native format is unavailable and the checkbox is on, use ASTC
  4x4 **only if the matching linear/sRGB ASTC enum is supported**. Otherwise use
  the ordinary RGBA upload. Do not assume all Android GPUs support ASTC.
  Dynamic/render-target/autogenerated-mip textures opt out of ASTC; compressed
  dynamic CPU fallback copies the mapped slice before unmapping and unbinding
  its unpack PBO, instead of dereferencing an unmapped pointer.
- Adapted the MIT endpoint/weight algorithm from
  `klaxons1/ASTransCoder@ab4b21320b3158f9f9c32123f36060302c62369c`.
  Independent decoding exposed reversed *bits within each two-bit weight* in the
  prototype (swapped intermediate colors). The native port fixes this.
- Four-color BC1 and constant-alpha BC3 use direct block translation, without
  full-image RGBA intermediates. BC1 three-color/transparency, BC2/DXT3, and BC3
  independent alpha use the vendored Arm ASTC encoder **per 4x4 block**, with a
  64-byte stack RGBA tile. Unlike the prototype, alpha is encoded independently,
  not assigned the RGB weights. All blocks/mips of that format remain ASTC;
  never mix an ASTC mip with a one-mip RGBA fallback.
- ASTC is lossy. Direct-path tests observed maximum channel difference **3/255**;
  generic fallback blocks can have greater error and additional loading cost.
  Texture appearance, especially alpha-test edges, still needs device inspection.
  No FPS or loading-time improvement is claimed without measurements.
- RGBA fallback now clips NPOT/tiny mip writes and removes the unsafe
  compressed-size == raw-size heuristic (a BC3 2x2 mip is also 16 bytes). DXT3
  always uses four-color interpolation; compressed reads are unaligned-safe.

### Unjustified waits removed

`D3DGETDATA_FLUSH` now submits queued GL work and may return `S_FALSE`, as required
for asynchronous D3D9 queries; it no longer unconditionally blocks on event or
occlusion completion. Necessary explicit fence completion is retained, but uses
1 ms driver waits instead of a zero-timeout CPU spin. Both `GL_ALREADY_SIGNALED`
and `GL_CONDITION_SATISFIED` count as success; `GL_WAIT_FAILED` is not completion.

### Validation and phone checklist

```sh
python3 -m pip install --target .cache/renderer-tests texture2ddecoder==1.0.6
PYTHONPATH=.cache/renderer-tests python3 scripts/tests-underhell-renderer.py
python3 scripts/tests-underhell.py
```

The native tests execute production codec, query and GL-upload selection code
with ASan/UBSan, NPOT/mip/unaligned/size cases, independent ASTC decoding, and
checkbox-on/off routing. CI also compiles ARM64 shaderapi, checks its ELF, compiles
Java launch tests, and verifies all three actual packaged libraries plus touch VPK.
These checks are **not** an Android GPU/runtime test.

On a phone, test the same map with the checkbox off/on after fully closing the
engine. Check alpha-test foliage, translucent UI, flashlight, water/mirrors,
map transitions and all embedded buttons. Capture the startup log:
`UNDERHELL_RENDERER_ASTC_V1` proves the private renderer connected;
`Underhell ASTC: requested=..., LDR=..., sRGB=...` reports request/capability.
If exact native DXT support exists, it deliberately bypasses ASTC even when on.
Keep the previous working APK for rollback if companion ABI/context behavior
on the device differs; do not equate a successful build with a verified launch.


## Experimental native DXVK-Sarek / ZIP GPU drivers

The ARM64 build now adds a separately selected native **DXVK-Sarek** backend and
an owned same-UID GPU process; GLES remains the default and retains ASTC/controls.
The launcher settings install/select trusted ARM64 driver ZIPs in private storage;
Sarek loads the selected driver through **libadrenotools**, with explicit errors
rather than a hidden system-driver fallback. System Vulkan is a separate choice.
See [architecture, build pins, security and device-test caveats](DXVK_SAREK_ANDROID.md).
Compilation/packaging checks do not prove rendering, pause/resume or FPS on a phone.
