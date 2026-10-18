# Arm ASTC encoder (library only)

Upstream: https://github.com/ARM-software/astc-encoder
Version: **4.8.0**, commit `0d6c9047c5ad19640e2d60fdb8f11a16675e7938`.
License: Apache-2.0, included as `LICENSE.txt`; original source headers retained.

These are the library translation units (only two leading-whitespace cleanups) listed by upstream
`Source/cmake_core.cmake`, plus its library headers. No CLI, image loaders,
Python, or external encoder executable is included in the APK.

Compiled as a private PIC static library inside Android `libshaderapidx9.so`.
Used only for blocks that cannot use the direct ASTransCoder endpoint/weight
translation: BC1 three-color/transparency, BC2, and independent BC3 alpha.
A single 4x4 RGBA stack buffer is used, not a full decompressed image. Encoder
contexts are cached separately for linear/sRGB and freed on renderer disconnect.
