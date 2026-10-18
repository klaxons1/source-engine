#!/usr/bin/env python3
"""Compile the real launcher flags and pinned SDL Android default-selection block.

This is a host regression test, not a real Android Surface/Vulkan execution test.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    launcher = (ROOT / 'appframework/sdlmgr.cpp').read_text()
    sdl = ROOT / 'thirdparty/SDL-src'
    video = (sdl / 'src/video/SDL_video.c').read_text()
    start = launcher.index('int flags = SDL_WINDOW_HIDDEN;', launcher.index('bool CSDLMgr::CreateHiddenGameWindow'))
    flags = launcher[start:launcher.index('m_Window = SDL_CreateWindow', start)]
    graphics = re.search(r'Uint32 graphics_flags = flags & [^;]+;', video).group()
    start = video.index('    /* Some platforms have certain graphics backends enabled by default */')
    defaults = video[start:video.index('    if (flags & SDL_WINDOW_OPENGL)', start)]
    android_window = (sdl / 'src/video/android/SDL_androidwindow.c').read_text()
    assert 'if ((window->flags & SDL_WINDOW_OPENGL) != 0)' in android_window
    assert 'data->egl_surface = SDL_EGL_CreateSurface' in android_window
    activity = (ROOT / 'assets/android/java/me/nillerusr/UnderhellSarekActivity.java').read_text()
    base = (sdl / 'android-project/app/src/main/java/org/libsdl/app/SDLActivity.java').read_text()
    for method, value in (('resumeNativeThread', 'true'), ('pauseNativeThread', 'false')):
        body = activity.split('void ' + method + '()', 1)[1].split('\n    }', 1)[0]
        assert body.index('nativeSetResumed(' + value + ')') < body.index('super.' + method + '()')
        assert 'protected void ' + method + '()' in base
    assert 'if (mHasMultiWindow) {\n            resumeNativeThread();' in base
    assert 'protected void onResume()' not in activity
    template = '''#include <SDL_video.h>
#define __ANDROID__ 1
#define DX_TO_GL_ABSTRACTION 1
NATIVE_DEFINE
static bool SDL_IsVideoContextExternal() { return false; }
int main() {
  struct { bool is_dummy; } device{false};
  auto* _this = &device;
  LAUNCHER_FLAGS
  GRAPHICS_FLAGS
  SDL_DEFAULTS
#ifdef UNDERHELL_VULKAN_LAUNCHER
  return (flags & SDL_WINDOW_VULKAN) && !(flags & SDL_WINDOW_OPENGL) ? 0 : 42;
#else
  return (flags & SDL_WINDOW_OPENGL) && !(flags & SDL_WINDOW_VULKAN) ? 0 : 42;
#endif
}
'''
    with tempfile.TemporaryDirectory(prefix='underhell-sdl-flags-') as tmp:
        for name, native, broken, expected in (('sarek', True, False, 0), ('gles', False, False, 0),
                                               ('old-sarek-negative-control', True, True, 42)):
            source = template.replace('NATIVE_DEFINE', '#define UNDERHELL_VULKAN_LAUNCHER 1' if native else '')
            source = source.replace('LAUNCHER_FLAGS', flags.replace('flags |= SDL_WINDOW_VULKAN;', '') if broken else flags)
            source = source.replace('GRAPHICS_FLAGS', graphics).replace('SDL_DEFAULTS', defaults)
            cpp = Path(tmp) / (name + '.cpp')
            exe = Path(tmp) / name
            cpp.write_text(source)
            subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++11', '-Wall', '-Wextra',
                            '-I' + str(sdl / 'include'), str(cpp), '-o', str(exe)], check=True)
            result = subprocess.run([str(exe)])
            if result.returncode != expected:
                raise RuntimeError(f'{name}: got {result.returncode}, expected {expected}')
            print(f'PASS: {name} (compiled launcher + actual pinned SDL Android defaults)')
    print('PASS: SDL resume/pause gate ordering, including Android multi-window onStart')


if __name__ == '__main__':
    main()
