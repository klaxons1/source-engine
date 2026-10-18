// Native host bridge; this file is linked ONLY into launcher_sarek.
#include <jni.h>
#include <SDL.h>
#include <SDL_system.h>
#include <android/native_window_jni.h>
#include <android/log.h>
#include <cstdlib>
#include <dlfcn.h>
#include <cstdint>
#include <atomic>
#include "android-host.h"

static jclass hostClass;
static jmethodID getSurface;
static jmethodID surfaceIsValid;
static std::atomic<bool> activityResumed{false};

static ANativeWindow* currentWindow(void* hwnd) {
    if (!activityResumed.load() || !hwnd || !hostClass || !getSurface || !surfaceIsValid) return NULL;
    JNIEnv* env = static_cast<JNIEnv*>(SDL_AndroidGetJNIEnv());
    if (!env) return NULL;
    jobject surface = env->CallStaticObjectMethod(hostClass, getSurface);
    if (env->ExceptionCheck()) { env->ExceptionClear(); return NULL; }
    bool valid = surface && env->CallBooleanMethod(surface, surfaceIsValid);
    ANativeWindow* window = valid && !env->ExceptionCheck() ? ANativeWindow_fromSurface(env, surface) : NULL;
    if (surface) env->DeleteLocalRef(surface);
    if (env->ExceptionCheck()) {
        env->ExceptionClear();
        if (window) ANativeWindow_release(window);
        return NULL;
    }
    return window; // acquired; Sarek WSI releases after using it
}


extern "C" __attribute__((visibility("default"))) JNIEXPORT void JNICALL
Java_me_nillerusr_UnderhellSarekActivity_configureNative(JNIEnv* env, jclass clazz,
    jobjectArray keys, jobjectArray values, jint width, jint height, jint refreshMilliHz) {
    auto fail = [&](const char* message) {
        jclass exception = env->FindClass("java/lang/IllegalStateException");
        if (exception) env->ThrowNew(exception, message);
    };
    if (!keys || !values || env->GetArrayLength(keys) != env->GetArrayLength(values)
            || env->GetArrayLength(keys) > 32) { fail("Invalid native host environment"); return; }
    for (jsize i = 0; i < env->GetArrayLength(keys); ++i) {
        jstring key = static_cast<jstring>(env->GetObjectArrayElement(keys, i));
        jstring value = static_cast<jstring>(env->GetObjectArrayElement(values, i));
        if (!key || !value) { fail("Missing native host environment"); return; }
        const char* k = env->GetStringUTFChars(key, NULL);
        const char* v = env->GetStringUTFChars(value, NULL);
        int status = k && v ? setenv(k, v, 1) : -1;
        if (k) env->ReleaseStringUTFChars(key, k);
        if (v) env->ReleaseStringUTFChars(value, v);
        env->DeleteLocalRef(key); env->DeleteLocalRef(value);
        if (status) { fail("Cannot set native host environment"); return; }
    }
    if (width <= 0 || height <= 0 || refreshMilliHz <= 0 ||
            !DXVKSarekSetAndroidDisplay(width, height, refreshMilliHz, 1000)) {
        fail("Invalid actual Android display metadata"); return;
    }
    hostClass = static_cast<jclass>(env->NewGlobalRef(clazz));
    getSurface = env->GetStaticMethodID(clazz, "getNativeSurface", "()Landroid/view/Surface;");
    jclass surfaceClass = env->FindClass("android/view/Surface");
    surfaceIsValid = surfaceClass ? env->GetMethodID(surfaceClass, "isValid", "()Z") : NULL;
    if (surfaceClass) env->DeleteLocalRef(surfaceClass);
    if (!hostClass || !getSurface || !surfaceIsValid || env->ExceptionCheck()) return;
    DXVKSarekSetAndroidWindowProvider(currentWindow);
    typedef void (*RegisterSurfaceCallback)(void (*)(void));
    void* sdl = dlopen("libSDL2.so", RTLD_NOW | RTLD_NOLOAD);
    auto registerCallback = sdl ? reinterpret_cast<RegisterSurfaceCallback>(dlsym(sdl, "SDL_UnderhellSetSurfaceCallback")) : NULL;
    if (!registerCallback) { fail("Owned Vulkan SDL lifecycle is missing; refusing EGL fallback"); return; }
    registerCallback(DXVKSarekNotifyAndroidSurface);
    __android_log_print(ANDROID_LOG_INFO, "UnderhellVulkan", "Sarek native host: %dx%d %.3f Hz", width, height, refreshMilliHz / 1000.0);
}

extern "C" __attribute__((used, visibility("default"))) const char UnderhellSarekLauncher[] = "UNDERHELL_SAREK_LAUNCHER_V1";

extern "C" __attribute__((visibility("default"))) JNIEXPORT void JNICALL
Java_me_nillerusr_UnderhellSarekActivity_nativeSetResumed(JNIEnv*, jclass, jboolean resumed) {
    activityResumed.store(resumed);
    DXVKSarekNotifyAndroidSurface();
}
