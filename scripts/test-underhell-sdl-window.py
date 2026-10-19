#!/usr/bin/env python3
"""Compile the real launcher flags and pinned SDL Android default-selection block.

This is a host regression test, not a real Android Surface/Vulkan execution test.
"""
from pathlib import Path
import os
import importlib.util
import shutil
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def staged_activity(base):
    spec = importlib.util.spec_from_file_location('launcher_prepare', ROOT / 'scripts/prepare-underhell-launcher.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.prepare_sdl_activity(base)


def test_ready_getter(staged):
    java = os.environ.get('JAVA', shutil.which('java'))
    jar = os.environ.get('JAVA_COMPILER_JAR')
    javac = os.environ.get('JAVAC', shutil.which('javac'))
    if not java or (not jar and not javac):
        print('SKIP: executable Java Surface-ready getter test (Java compiler required)')
        return
    def method(name):
        start = staged.index('    public static Surface ' + name + '()')
        return staged[start:staged.index('\n    }', start) + len('\n    }')]
    ready_field = re.search(r'public volatile boolean mIsSurfaceReady;', staged).group()
    source = """class Surface {}
class SDLSurface {
  READY_FIELD
  Surface current = new Surface();
  public Surface getNativeSurface() { return current; }
}
public class SDLActivity {
  static SDLSurface mSurface;
  ORIGINAL_GETTER
  READY_GETTER
  static void check(boolean ok) { if (!ok) throw new AssertionError(); }
  public static void main(String[] args) throws Exception {
    check(getNativeSurface() == null && getNativeSurfaceIfReady() == null);
    mSurface = new SDLSurface();
    check(getNativeSurface() == mSurface.current); // surfaceCreated handshake
    check(getNativeSurfaceIfReady() == null); // not yet surfaceChanged
    mSurface.mIsSurfaceReady = true;
    check(getNativeSurfaceIfReady() == mSurface.current);
    mSurface.mIsSurfaceReady = false; // destroyed; holder can still return an object
    check(getNativeSurfaceIfReady() == null);
    Surface old = mSurface.current; mSurface.current = new Surface();
    check(getNativeSurfaceIfReady() == null);
    mSurface.mIsSurfaceReady = true;
    check(getNativeSurfaceIfReady() == mSurface.current && getNativeSurfaceIfReady() != old);
    check(java.lang.reflect.Modifier.isVolatile(SDLSurface.class.getField("mIsSurfaceReady").getModifiers()));
  }
}
""".replace('READY_FIELD', ready_field).replace('ORIGINAL_GETTER', method('getNativeSurface')).replace('READY_GETTER', method('getNativeSurfaceIfReady'))
    with tempfile.TemporaryDirectory(prefix='underhell-java-surface-') as tmp:
        path = Path(tmp) / 'SDLActivity.java'
        path.write_text(source)
        compiler = [java, '-jar', jar] if jar else [javac]
        cp = ['-classpath', os.environ['JAVA_TEST_CLASSPATH']] if os.environ.get('JAVA_TEST_CLASSPATH') else []
        subprocess.run(compiler + cp + ['-source', '8', '-target', '8', '-d', tmp, str(path)], check=True)
        subprocess.run([java, '-cp', tmp, 'SDLActivity'], check=True)
    print('PASS: actual staged Java Surface getters (mock Surface/holder, including destroy/recreate)')


def test_surface_destroy(sdl):
    # Execute the actual patched JNI body against a host SDL/EGL/window mock.
    with tempfile.TemporaryDirectory(prefix='underhell-surface-destroy-') as tmp:
        tmp = Path(tmp)
        for name in ('src/core/android/SDL_android.c', 'src/video/android/SDL_androidevents.c'):
            out = tmp / name
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(sdl / name, out)
        subprocess.run(['git', 'apply', str(ROOT / 'scripts/experimental/sdl-underhell-vulkan.patch')], cwd=tmp, check=True)
        patched = (tmp / 'src/core/android/SDL_android.c').read_text()
        start = patched.index('{', patched.index('JNIEXPORT void JNICALL SDL_JAVA_INTERFACE(onNativeSurfaceDestroyed)(JNIEnv *env, jclass jcls)\n{'))
        body = patched[start:patched.index('\n}', start) + 2]
        prefix = r"""#include <SDL_video.h>
#include <cassert>
struct SDL_Window { Uint32 flags; void* driverdata; };
struct SDL_WindowData { int backup_done, egl_surface; void* native_window; };
struct SDL_VideoDevice {};
static SDL_VideoDevice device;
static SDL_Window* Android_Window;
static int Android_ActivityMutex, locks, delays, errors, destroyed, released, notified;
#define EGL_NO_SURFACE 0
static void SDL_LockMutex(int) { assert(locks++ == 0); }
static void SDL_UnlockMutex(int) { assert(--locks == 0); }
extern "C" int SDL_SetError(const char*, ...) { ++errors; return -1; }
static void SDL_Delay(unsigned) { ++delays; }
static SDL_VideoDevice* SDL_GetVideoDevice() { return &device; }
static void SDL_EGL_DestroySurface(SDL_VideoDevice*, int) { ++destroyed; }
static void ANativeWindow_release(void*) { ++released; }
static void callback() { assert(locks == 1); ++notified; }
static void (*underhell_surface_callback)() = callback;
static void destroySurface()
"""
        suffix = r"""
int main() {
  SDL_WindowData data{0, EGL_NO_SURFACE, &data};
  SDL_Window window{SDL_WINDOW_VULKAN, &data}; Android_Window = &window;
  destroySurface();
  // Regression control: old Vulkan path waits 490ms for nonexistent EGL backup.
  if (delays || errors) return 42;
  assert(!locks && !destroyed && released == 1 && notified == 1 && !data.native_window);
  delays = errors = destroyed = released = notified = 0;
  window.flags = SDL_WINDOW_OPENGL; data = {0, 123, &data};
  destroySurface();
  assert(delays == 49 && errors == 1 && destroyed == 1 && released == 1 && notified == 1);
  delays = errors = destroyed = released = notified = 0;
  data = {1, 123, &data}; destroySurface();
  assert(!delays && !errors && destroyed == 1 && released == 1 && notified == 1 && !locks);
}
"""
        for name, code, expected in (
            ('surface-destroy', body, 0),
            ('old-surface-destroy-negative-control', body.replace(
                '(Android_Window->flags & SDL_WINDOW_OPENGL) && !data->backup_done', '!data->backup_done'), 42)):
            cpp, exe = tmp / (name + '.cpp'), tmp / name
            cpp.write_text(prefix + code + suffix)
            subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++11', '-Wall', '-Wextra',
                            '-I' + str(sdl / 'include'), str(cpp), '-o', str(exe)], check=True)
            assert subprocess.run([str(exe)]).returncode == expected
            print('PASS:', name, '(actual SDL JNI body, mock EGL/window)')


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
    staged = staged_activity(base)
    assert 'public volatile boolean mIsSurfaceReady;' in staged
    assert 'getNativeSurfaceIfReady()' in staged
    assert 'return SDLActivity.mSurface.getNativeSurface();' in staged # original SDL handshake retained
    destroy = staged.split('public void surfaceDestroyed(', 1)[1].split('public void surfaceChanged(', 1)[0]
    assert destroy.index('mIsSurfaceReady = false;') < destroy.index('SDLActivity.handleNativeState();')
    bridge = (ROOT / 'launcher/android/sarek_bridge.cpp').read_text()
    assert 'GetStaticMethodID(clazz, "getNativeSurfaceIfReady",' in bridge
    test_ready_getter(staged)
    test_surface_destroy(sdl)
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
