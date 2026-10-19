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

### Android Surface regression (Adreno 640 / Turnip)

A device report reached `D3D9DeviceEx::ResetSwapChain`, then failed with
`Failed to create surface`. The native launcher previously omitted both SDL
OpenGL and Vulkan window flags. In our pinned SDL, `SDL_CreateWindow` **implicitly
adds `SDL_WINDOW_OPENGL` on Android when no graphics flag is set**. The Android
backend then creates an EGLSurface, which its own source explicitly documents
as incompatible with `vkCreateAndroidSurfaceKHR`. Skipping our explicit GL-context
setup was therefore insufficient. The Sarek launcher now requests
`SDL_WINDOW_VULKAN` explicitly and rejects a resulting OpenGL window; GLES flags
remain unchanged.

The WSI availability gate also follows SDL's `resumeNativeThread` /
`pauseNativeThread` hooks. On multi-window Android SDL can start the native thread
in `onStart`, before `onResume`; gating only in Activity `onResume` leaves an
initialization race. Surface validity and retained native-window ownership are
still checked independently.

`python3 scripts/test-underhell-sdl-window.py` compiles our actual flag-selection
block together with the pinned SDL Android default-selection block for Sarek,
GLES, and a negative control reproducing the old missing-Vulkan-flag bug. It also
checks ordering of the lifecycle hooks. These are host regression checks, not a
GPU/device test. Surface failures now include the Vulkan result and distinguish
native-surface creation from queue presentation-support failures. The native
engine error names DXVK-Sarek / Vulkan rather than the platform-wide OpenGL label.
The user's Adreno 640 still needs a launch test with the corrected APK; fixing
these integration defects does not prove subsequent game rendering.

### Source / native D3D9 color byte-order boundary

The Adreno 640 report after the Surface fix reaches a real swapchain. Red/blue
exchange is consistent with two independently reproducible integration defects:

* The shared bitmap mapping treated `IMAGE_FORMAT_RGBA8888` as native D3D9
  `A8R8G8B8` (BGRA bytes). For `bitmap_sarek` only, RGBA now maps to `A8B8G8R8`,
  with the corresponding reverse mapping; BGRA still maps to `A8R8G8B8`.
* The unchanged GLES-built companion/client use `OPENGL_SWAP_COLORS` vertex
  writers (RGBA). Native shaderapi declarations must therefore fetch color and
  specular as `UBYTE4N`, not BGRA `D3DCOLOR`. Native shaderapi's own inline writers
  now use the same byte layout. Packed bone indices share that writer convention;
  normalized RGBA fetch preserves the existing DX9 shader's `D3DCOLORtoUBYTE4`
  `.zyxw` operation rather than introducing an extra R/B exchange.

`test-underhell-sarek-colors.py` compiles the production format-mapping functions,
vertex-declaration selector, and byte writers against the native D3D9 headers.
ASan/UBSan checks cover primary colors, blue/orange, white, transparent/nontrivial
alpha, companion-style RGBA input and bone indices; a separate GLES profile
checks that the legacy format/vertex contracts are unchanged. The pre-fix code
fails the RGBA mapping check. No swapchain-wide swizzle or forced surface format
is applied: presenting an A8R8G8B8 backbuffer to an R8G8B8A8 swapchain is valid
when the blit performs the normal format conversion.

This color fix is not a claim to fix the other device reports: the posted log
still requests a 640x480 D3D backbuffer and presents to a 2309x1080 Android
surface, and repeatedly recreates the swapchain. Font availability, render-mode
selection, input scaling and the recreation trigger require separate validation.


### Owned-runner fonts, resolution, touch and present stability

The user confirmed the preceding color APK fixes colors on the Adreno 640.
This next revision leaves those mappings, GLES/ASTC and the 15 controls intact:

* `assets/android/fonts/` contains unmodified, SHA256-pinned DejaVu Sans regular,
  bold, oblique, bold-oblique and Sans Mono from matplotlib commit
  `4aeb773422464799998d900198b35cb80e94b3e1`, with the complete redistribution
  license. The Mono file uses the legacy `LiberationMono-Regular.ttf` filename
  expected by the companion's Courier fallback; it is **not** a Liberation font.
  The owned Activity copies fonts to its own `files/` and sets `APP_DATA_PATH`
  to **dataDir**, because linuxfont appends `/files/`. Neither the extras VPK nor
  another UID's private font installation is sufficient. Latin and Cyrillic are
  covered; this does not bundle the optional CJK/Thai fallback fonts.
* Sarek defaults to 720 pixels high, with width from the **actual ready Surface**
  queried on SDL's native thread. For the reported 2309x1080 Surface that is
  1539x720, not 640x480. Launcher GPU settings offer 1080p and Surface-native
  alternatives. Height is capped to the actual Surface when using a preset.
  Explicit `-w`/`-width` and `-h`/`-height` take precedence; a missing dimension
  follows Surface aspect. Canonical dimensions are appended to owned argv only;
  the companion GLES argument/configuration path is unchanged.
* In the **staged, owned** SDL Java, all move/down/up/cancel touch normalization
  uses `v.getWidth()/getHeight()`, not surface-buffer `mWidth/mHeight`.
  MotionEvent positions are View-local. The pristine thirdparty checkout and
  companion SDL are untouched. This corrects one scale-mismatch path; reported
  difficult tapping still requires actual device verification, not an assumption
  that every missed tap was caused by that path.
* Android Sarek accepts `VK_SUBOPTIMAL_KHR` as a successful present in D3D9's
  `SynchronizePresent`, consistent with its Presenter. Previously it invoked
  `RecreateSwapChain`/`waitForIdle` for every such frame. OUT_OF_DATE, Surface loss,
  device loss and epoch recovery remain errors/recreation paths. We do not force
  `currentTransform` without the required rotation/blit work.
* SDL Surface notifications compare native-window identity, Java Surface
  generation and dimensions before advancing the epoch. Repeated identical
  callbacks from buffer setup do not self-trigger recreation. Provider queries
  only seed an empty state; they cannot consume a real replacement notification.
  Resume/pause still invalidate on an actual state transition. The metadata lock
  never encloses JNI/SDL window calls or Vulkan work; no SDL window mutex is
  re-entered from its callback.

Checks: launcher Java policy (aspect, presets, explicit/invalid dimensions),
5 real TTF/cmap/Latin+Cyrillic/hash/license audits, staging/idempotence and APK
missing/corrupt-font negatives, actual WSI ASan/UBSan host tests including 1000
identical notifications, replacement/generation/resize/pause, and Vulkan status
policy. These are not GPU or phone input tests. The APK audit requires the pinned
font assets as well as the native runtime provenance.

### Opt-in Source DX6 graphics (Sarek, not D7VK)

The user confirmed fonts/resolution/input now work, then selected **Source DX6
through Sarek**, rather than an actual old-D3D API/D7VK port. D7VK translates
D3D3/5/6/7 clients into D3D9; Source's `dxlevel 60` still uses its D3D9 shaderapi.
No D7VK/Wine DLL is bundled or claimed here.

The GPU settings include **DX6-графика через Sarek (экспериментально)**, off by
default, disabled when GLES is selected. It applies on a fresh GPU-process start.
The checkbox passes an explicit intent boolean, removes stale private switches
and conflicting DX-level overrides, and supplies `-dxlevel 60 -maxdxlevel 60`.

This is not just a command-line preset: three separately named libraries are
built and checked in the APK:

* `materialsystem_sarek_dx6`: a Source-ABI material system with its minimum
  compiled as 60 and its mat_dxlevel ConVar fixed at 60, rather than the
  companion's POSIX minimum 90 / GL ConVar clamp 90..92. It loads the
  private DX6 dictionary explicitly and cannot let companion DX8/9/mod shader
  DLLs overwrite it. Includes the original fixed-function Wireframe fallback.
* `shaderapidx9_sarek_dx6`: the real native Sarek shaderapi with a minimum and
  maximum level of 60. Its material-system/shader-device interfaces retain the
  companion GL-layout startup-preload vtable slot (implemented as a no-op, not GL
  shader preloading). Normal Sarek keeps its existing target/caps behavior.
* `stdshader_dx6_sarek`: all **32 shader source units** listed in the original
  `stdshader_dx6.vpc`, including lightmapped/vertex-lit/unlit, eyes/teeth, water,
  sprites, depth/shadows and old screen-space paths. Legacy files that use the
  `BEGIN_VS_SHADER` spelling derive directly from `CBaseShader` in this build:
  their fixed-function helpers are already there; no modern VS/PS binaries or
  `BaseVSShader.cpp` are needed. Unused old DirectX utility includes are excluded.

The owned launcher chooses both the material system and shaderapi explicitly.
Unchecking the option selects the **original companion material system and
ordinary Sarek shaderapi**, not the legacy modules with a higher console value.
The regular POSIX minimum remains 90, Windows 80, and GLES/ASTC are unchanged.
Fonts, resolution, ZIP drivers and all touch controls remain shared/preserved.

Expect simpler materials and unavailable modern shader/HDR/postprocessing
features. Software vertex lighting/skinning and multipass fixed-function
rendering can be **slower**, so this is not an FPS guarantee. Visual correctness
and Underhell-specific effects need device validation.

`test-underhell-dx6.py` compiles all 32 actual shader translation units and the
actual minimum-level preprocessor policy for legacy, normal POSIX and Windows.
Launcher Java tests exercise checkbox-on/off, quote preservation and conflicting
DX-level sanitization. APK checks reject missing, wrong-ABI or wrong-identity
legacy modules and compare them with the staged outputs. These are build/CPU
checks, not a claim of Android GPU validation.

### Surface-not-ready diagnostics (including Pixel 6 / Mali-G78)

A reported Pixel 6 log reaches Vulkan device creation, then repeatedly fails
initial Android WSI Surface creation. The old combined `native window /
vkCreateAndroidSurfaceKHR failed` message did **not** identify whether the Java
provider returned NULL or Vulkan rejected an acquired window. Missing optional
GPU features in that log do not establish the cause of this Surface failure.

The owned SDL Java copy now publishes a volatile Surface-ready flag, closes it
before the destroy/pause handshake, and exposes a separate ready-only getter for
Sarek. SDL's original getter remains ungated for `surfaceCreated`, which runs
before readiness. Vulkan destruction skips the EGL-only backup wait and notifies
the host of Surface loss. GLES keeps its EGL backup/wait behavior.

WSI Surface creation waits at most two seconds for an unavailable provider,
re-querying every 10 ms on the render thread only. Provider queries and UI/SDL
callbacks never wait or call SDL window APIs. Actual Vulkan creation errors are
returned immediately, **not** retried or reported as successful presentation.
A failed Presenter constructor also releases its Surface/window lease after
swapchain setup fails, so later device attempts do not inherit that lease.

New DXVK log messages distinguish:

* `native window unavailable (provider returned NULL); ... was NOT called`:
  readiness/lifecycle or JNI bridge issue, not a Vulkan creation failure;
* `vkCreateAndroidSurfaceKHR rejected an acquired native window (...)`:
  Vulkan really was called; the actual result and window extent are included;
* `Failed to create swap chain, VkResult=...`: Surface creation passed, but the
  subsequent swapchain stage failed.

Android logcat tag `UnderhellVulkan` additionally reports activity transitions
and changes in window availability (paused, SDL not ready, invalid Surface, JNI
error, ready generation/extent), without emitting a message for every frame.
Host tests execute the patched SDL destroy body and staged Java getters against
mocks, including old-code negative controls, plus WSI recovery/timeout/driver
failure and reference-ownership tests under ASan/UBSan. These changes address
lifecycle defects; **the Pixel 6 black screen is not device-verified as fixed**.
On Mali select the system Vulkan driver, not an Adreno Turnip ZIP. Test ordinary
Sarek first with the optional DX6 graphics checkbox off.
