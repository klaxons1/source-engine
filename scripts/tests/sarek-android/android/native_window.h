#pragma once
// Host-only NDK mock. Never added to the Android library's include path.
#include <stdint.h>
struct ANativeWindow { int32_t width, height; };
extern "C" int32_t ANativeWindow_getWidth(ANativeWindow*);
extern "C" int32_t ANativeWindow_getHeight(ANativeWindow*);
extern "C" void ANativeWindow_release(ANativeWindow*);
