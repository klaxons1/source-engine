# Underhell: experimental native Android DXVK-Sarek backend

**Uses actual DXVK-Sarek, not ordinary dxvk-native and not Wine DLLs.**
Android execution, rendering correctness, GPU compatibility, pause/resume and FPS
are **not proven by compilation or APK checks**. GLES remains the default, with
the existing ASTC checkbox and all 15 embedded touch controls.

## Architecture

- `libshaderapidx9.so`: existing GLES/TOGLES renderer, unchanged native ABI.
- `libshaderapidx9_sarek.so` + `bitmap_sarek`: separate real D3D9 COM ABI and
  D3DFORMAT conversions. Do not reuse TOGL enum ordinals or replace libtogl.
- `libdxvk_sarek_d3d9.so`: native ARM64 port of Sarek D3D9/DXSO/Vulkan core.
- `liblauncher_sarek.so` / `appframework_sarek`: retains the engine's SDL manager
  vtable including the eight GL compatibility slots, but creates no EGL context
  or OpenGL producer. Chooses `shaderapidx9_sarek` explicitly.
- Launcher-owned SDL2 + matching Java from the pinned `thirdparty` submodule.
  The patched Android lifecycle creates/restores EGL only for OpenGL windows.
- `UnderhellSarekActivity`: non-exported activity in separate `:sarek` process,
  same app UID. The existing Source Engine companion still supplies engine core
  libraries/resources; it does **not** execute our private GPU drivers. Isolated
  GPU-process shutdown resets native/SDL state without killing the main launcher.
- Main GLES launch still targets the external companion's existing SDLActivity.

The runner preloads its own SDL and the companion's tier0/vstdlib/steam_api/togl
before its launcher. It checks exact lowercase `underhell/gameinfo.txt`, uses
an explicit game-resource path, and installs both the embedded Underhell extras
VPK and the companion base extras VPK. SDL passes arguments as an array, preserving
quoted arguments rather than using the companion's fixed-buffer strtok path.
The native shaderapi uses the unique `DXVKSarekDirect3DCreate9` export: the
companion TOGL also exports `Direct3DCreate9`, so an unqualified symbol would risk
returning an incompatible TOGL object. The unique factory catches initialization
exceptions inside libc++ and returns NULL; it never unwinds into GNUSTL callers. Video-memory reporting queries the selected
adapter's device-local Vulkan heap budget/size, not Windows WMI or invented RAM.
ASTC is GLES-only; the stored checkbox setting survives a renderer change.

## Launcher / ZIP drivers

Open **Рендерер / Vulkan / GPU-драйверы ZIP…**:

1. Choose GLES (default) or experimental DXVK-Sarek/Vulkan (Android 8+, ARM64).
2. Save the resources root containing `hl2/` and `underhell/gameinfo.txt`.
   The GLES companion's preferences are private to that separate application;
   they cannot be read by this launcher.
3. Select system Vulkan, or install a trusted driver ZIP with the document picker.
   Custom drivers require **Android 9 / API 28+** and libadrenotools.
4. Fully exit the game before changing the driver/renderer. Reopening an existing
   Vulkan activity does not mutate the live namespace or device.

ZIPs must contain root `meta.json` with `name`, `minApi`, `libraryName`, plus the
named Android ARM64 `.so`. Other standard metadata fields are preserved/ignored.
Both `libvulkan_freedreno.so` and `vulkan.adreno.so` filename styles are accepted.
A Turnip package is not suitable for every Adreno, and is not a Mali driver.

Installation is transactional into unique directories in `getNoBackupFilesDir()`:
128 MiB compressed input, 256 MiB per file, 512 MiB total, 256 entries, 64 KiB
metadata. It rejects traversal, absolute/backslash/duplicate paths, file/directory
collisions, directory payloads, corrupt/truncated ZIPs and wrong-architecture or
non-shared ELF files. Extraction creates files, never archive symlinks. Failed
installations are removed; existing installations and selection remain untouched.
Directories are owner-only and files read-only. Old world-writable dataDir/VPK
sharing permissions are replaced with traversal-only directories/read-only VPKs.
**These checks do not establish that native driver code is trustworthy.** An
explicit warning precedes selection; native drivers execute with the app's rights.

### Real driver loading, not merely a ZIP catalogue

Before the first D3D9 device, Java/JNI supplies the owning APK's exact
`nativeLibraryDir`, a private temporary directory and selected immutable driver
path to Sarek. Its Vulkan loader calls `adrenotools_open_libvulkan` using
`ADRENOTOOLS_DRIVER_CUSTOM`, not a renamed ordinary dlopen of the selected `.so`.
`extractNativeLibs=true` is required for the namespace hook libraries.

Our small, source-published libadrenotools patch disables its internal system
fallback **when a custom driver was explicitly selected** and shares an atomic
hook-success flag across its namespaces. After Vulkan instance/device enumeration,
Sarek checks that the custom driver was actually opened by the hook. Failure
refuses that backend instead of claiming the ZIP worked while using system Vulkan.
The system Vulkan choice is separate. No clock/turbo/GPU-mapping override is used.
After a GPU failure, return to the launcher and explicitly choose GLES/system.
There is no promise to recover a crashed Vulkan device in-place.

## Android window and display contract

Before `Direct3DCreate9`, JNI registers real display dimensions and refresh rate
(from Android Display, expressed in milliHz, not an invented 60 Hz).
`DXVKSarekSetAndroidWindowProvider` makes D3D's stable HWND an SDL window token;
the callback resolves the **current** Java Surface to an acquired ANativeWindow.
Sizing releases temporary references. A successful Vulkan surface keeps its
window reference until `vkDestroySurfaceKHR`, including surface replacement.

The activity marks its provider unavailable before SDL's pause handshake; JNI
also checks `Surface.isValid()`. A Surface-less D3D9 present is deferred and marked
for recreation rather than falsely treating a normal app switch as device loss.
Owned SDL notifies an atomic surface epoch on `surfaceChanged`. The presenter
invalidates/recreates the Vulkan surface/swapchain on an epoch change instead of
reusing a stale Android window. D3D is windowed internally; SDL/Android owns actual
immersive fullscreen. This is implemented lifecycle plumbing, **not an assertion
that a particular phone/driver resumes correctly**.

Runtime HLSL source compilation is unsupported and returns an explicit warning
and NULL. The game must ship its precompiled DX9 shader caches. Native D3DX math
and the complete COM matrix stack are implemented; no BREAK-only math stubs.

## Build / checks

The existing Android workflow calls `scripts/build-android-aarch64.sh`. It builds
both renderer targets. It retains r10e/clang11/GNUSTL for Source's legacy engine
modules and uses NDK **23.1.7779620** with static libc++ for Sarek, owned SDL and
libadrenotools. The C/COM boundary does not exchange STL containers.

Modern runtime alone (does not link the engine or build an APK):

```sh
python3 -m pip install cmake==3.31.6 ninja==1.11.1.4 meson==1.8.0
python3 scripts/build-underhell-vulkan-runtime.py --ndk /path/to/ndk/23.1.7779620
```

Without `--ndk` / `ANDROID_SAREK_NDK_HOME`, the script fetches the pinned GitHub
NDK mirror below using sparse checkout. Build caches and binaries are ignored.
The script builds real Sarek, runs host WSI/UTF-8 sanitizers and production-math
numerical tests, builds libadrenotools + four hooks and SDL2/hidapi, audits required
exports and stages runtime hashes/licenses in `assets/underhell-vulkan.json`.

Native engine configuration adds `--sarek-sdk="$PWD/artifacts/dxvk-sarek-android-arm64"`
to the existing Android `--togles` configure, then builds/installs
`shaderapidx9_sarek,launcher_sarek` as well as the existing renderer/client/server.
The SDK option adds targets; it does not change the default GLES renderer.

Standalone Sarek SDK remains reproducible:

```sh
python3 scripts/build-dxvk-sarek-android.py --ndk /path/to/ndk/23.1.7779620
python3 scripts/build-dxvk-sarek-android.py --prepare-only # host WSI tests only
python3 scripts/test-underhell-sarek-math.py
python3 scripts/test-underhell-launch-contract.py        # includes ZIP/ELF tests
```

The final APK verifier checks the original Underhell client/server/GLES markers,
touch VPK and staging hashes, plus all ten Vulkan libraries, actual runtime hashes,
Sarek/launcher markers, provenance and the owned Java settings/SDL activity classes.
Modern runtime DSOs use 16 KiB LOAD alignment. **This does not establish whole-APK
16 KiB page-size support**: legacy engine/companion libraries must also support it.

Check levels must remain distinct:

1. Host sanitizer, math, ZIP/ELF and launch-policy tests (no GPU/Android execution).
2. Android native compile/link and final APK packaging/audits.
3. Real device: first image, precompiled shaders, touch controls, system/custom
   driver identity, background/resume/surface replacement, crash fallback, memory,
   heat and FPS. **No device result or FPS improvement is currently claimed.**

## Exact provenance / licensing

- Sarek core: `pythonlover02/dxvk-sarek` **0c0e8f6f62c7cb37dbf5d38413517efa00c08fef**.
- Native Win32/COM **headers only**: `fbraz3/dxvk`
  **870371520577d3781690f167ec33c45a0f17fd43**. This does not replace Sarek's core.
- DirectX headers: `Joshua-Ashton/mingw-directx-headers`
  **9df86f2341616ef1888ae59919feaa6d4fad693d**.
- glslang 11.13.0 host compiler: **77551c429f86c0e077f26552b7c1c0f12a9f235e**.
- `bylaws/libadrenotools`: **8fae8ce254dfc1344527e05301e43f37dea2df80**;
  `liblinkernsbypass`: **aa3975893d83ef1bc84c321ec60c65fbf1287887** (BSD-2-Clause).
- `thirdparty`/SDL source+Java: **c5b901ecef515ea068fa8b8a19ca5cd5353905cb** (SDL zlib).
- NDK mirror `khadas/android_common_common14-5.15_prebuilts_ndk-r23`:
  **6dcd51aede6a404a9917d9a159ed0c12fd9c8c08**.

Patches live in `scripts/experimental/`. The build retains Sarek/native zlib,
DirectX-header LGPL/MinGW notices, SDL, BSD and NDK runtime notices in APK assets
and the standalone SDK. Existing launcher/engine licensing remains applicable.
No Wine runtime or GPL Generals project patch was copied.
