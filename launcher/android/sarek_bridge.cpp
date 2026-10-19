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
#include "sarek_surface_state.h"

static jclass hostClass;
static jmethodID getSurface;
static jmethodID surfaceIsValid;
static jmethodID surfaceGeneration;
static SDL_SpinLock surfaceStateLock;
static SarekSurfaceState surfaceState;
static std::atomic<bool> activityResumed{false};

enum WindowReadState { WINDOW_READY, ACTIVITY_PAUSED, HOST_NOT_READY, NO_JNI,
    SURFACE_NOT_READY, INVALID_SURFACE, JNI_ERROR, NO_NATIVE_WINDOW };
static std::atomic<int> lastWindowReadState{-1};
static ANativeWindow* windowReadResult(WindowReadState state, ANativeWindow* window = NULL, int generation = 0) {
    if (lastWindowReadState.exchange(state) != state) {
        static const char* reasons[] = {"ready", "activity paused", "host not configured", "no JNI environment",
            "SDL Surface not ready", "Surface.isValid=false", "JNI exception", "ANativeWindow_fromSurface returned NULL"};
        __android_log_print(ANDROID_LOG_INFO, "UnderhellVulkan", "Native window: %s (generation=%d, %dx%d)",
            reasons[state], generation, window ? ANativeWindow_getWidth(window) : 0,
            window ? ANativeWindow_getHeight(window) : 0);
    }
    return window;
}

// SDL can call this with Android_ActivityMutex held. Only use Java Surface /
// ANativeWindow APIs here, never SDL_GetWindowWMInfo or SDL window operations.
static ANativeWindow* readWindow(void* hwnd, int* generation) {
    if (!activityResumed.load()) return windowReadResult(ACTIVITY_PAUSED);
    if (!hwnd || !hostClass || !getSurface || !surfaceIsValid || !surfaceGeneration) return windowReadResult(HOST_NOT_READY);
    JNIEnv* env = static_cast<JNIEnv*>(SDL_AndroidGetJNIEnv());
    if (!env) return windowReadResult(NO_JNI);
    jobject surface = env->CallStaticObjectMethod(hostClass, getSurface);
    if (env->ExceptionCheck()) { env->ExceptionClear(); return windowReadResult(JNI_ERROR); }
    if (!surface) return windowReadResult(SURFACE_NOT_READY);
    bool valid = env->CallBooleanMethod(surface, surfaceIsValid);
    if (valid && !env->ExceptionCheck() && generation) *generation = env->CallIntMethod(surface, surfaceGeneration);
    ANativeWindow* window = valid && !env->ExceptionCheck() ? ANativeWindow_fromSurface(env, surface) : NULL;
    env->DeleteLocalRef(surface);
    if (env->ExceptionCheck()) {
        env->ExceptionClear();
        if (window) ANativeWindow_release(window);
        return windowReadResult(JNI_ERROR);
    }
    return windowReadResult(window ? WINDOW_READY : valid ? NO_NATIVE_WINDOW : INVALID_SURFACE,
        window, generation ? *generation : 0); // acquired; released by Sarek WSI
}

static bool observeWindow(ANativeWindow* window, int generation, bool initializeOnly) {
    int width = window ? ANativeWindow_getWidth(window) : 0;
    int height = window ? ANativeWindow_getHeight(window) : 0;
    SDL_AtomicLock(&surfaceStateLock);
    bool changed = surfaceState.observe(reinterpret_cast<uintptr_t>(window), generation, width, height, initializeOnly);
    SDL_AtomicUnlock(&surfaceStateLock);
    return changed;
}

static ANativeWindow* currentWindow(void* hwnd) {
    int generation = 0;
    ANativeWindow* window = readWindow(hwnd, &generation);
    if (window) observeWindow(window, generation, true); // seed before first vkCreateSwapchain
    return window;
}

static void surfaceChanged() {
    int generation = 0;
    ANativeWindow* window = readWindow(&activityResumed, &generation);
    bool changed = observeWindow(window, generation, false);
    if (window) ANativeWindow_release(window);
    if (changed) DXVKSarekNotifyAndroidSurface();
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
    getSurface = env->GetStaticMethodID(clazz, "getNativeSurfaceIfReady", "()Landroid/view/Surface;");
    jclass surfaceClass = env->FindClass("android/view/Surface");
    surfaceIsValid = surfaceClass ? env->GetMethodID(surfaceClass, "isValid", "()Z") : NULL;
    surfaceGeneration = surfaceClass ? env->GetMethodID(surfaceClass, "getGenerationId", "()I") : NULL;
    if (surfaceClass) env->DeleteLocalRef(surfaceClass);
    if (!hostClass || !getSurface || !surfaceIsValid || !surfaceGeneration || env->ExceptionCheck()) return;
    DXVKSarekSetAndroidWindowProvider(currentWindow);
    typedef void (*RegisterSurfaceCallback)(void (*)(void));
    void* sdl = dlopen("libSDL2.so", RTLD_NOW | RTLD_NOLOAD);
    auto registerCallback = sdl ? reinterpret_cast<RegisterSurfaceCallback>(dlsym(sdl, "SDL_UnderhellSetSurfaceCallback")) : NULL;
    if (!registerCallback) { fail("Owned Vulkan SDL lifecycle is missing; refusing EGL fallback"); return; }
    registerCallback(surfaceChanged);
    __android_log_print(ANDROID_LOG_INFO, "UnderhellVulkan", "Sarek native host (ready-surface-v2): %dx%d %.3f Hz", width, height, refreshMilliHz / 1000.0);
}

extern "C" __attribute__((used, visibility("default"))) const char UnderhellSarekLauncher[] = "UNDERHELL_SAREK_LAUNCHER_V1";

extern "C" __attribute__((visibility("default"))) JNIEXPORT void JNICALL
Java_me_nillerusr_UnderhellSarekActivity_nativeSetResumed(JNIEnv*, jclass, jboolean resumed) {
    bool active = resumed == JNI_TRUE;
    if (activityResumed.exchange(active) != active) {
        DXVKSarekNotifyAndroidSurface();
        __android_log_print(ANDROID_LOG_INFO, "UnderhellVulkan", "Activity resumed=%s", active ? "true" : "false");
    }
}

extern "C" __attribute__((visibility("default"))) JNIEXPORT jintArray JNICALL
Java_me_nillerusr_UnderhellSarekActivity_nativeGetSurfaceSize(JNIEnv* env, jclass) {
    // Called by SDL's native thread only after Java's Surface-ready handshake.
    ANativeWindow* window = currentWindow(&activityResumed);
    jint size[2] = {window ? ANativeWindow_getWidth(window) : 0,
                    window ? ANativeWindow_getHeight(window) : 0};
    if (window) ANativeWindow_release(window);
    if (size[0] <= 0 || size[1] <= 0) {
        jclass exception = env->FindClass("java/lang/IllegalStateException");
        if (exception) env->ThrowNew(exception, "Sarek: Android Surface is not ready for render-size selection");
        return NULL;
    }
    jintArray result = env->NewIntArray(2);
    if (result) env->SetIntArrayRegion(result, 0, 2, size);
    return result;
}
