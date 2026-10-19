#pragma once
#include <cstdint>

// Metadata only; the caller holds a lock and owns its acquired ANativeWindow.
// SDL surfaceChanged can be caused by the swapchain's own buffer setup. Do not
// invalidate a still-identical Surface on every one of those notifications.
struct SarekSurfaceState {
    bool initialized = false;
    uintptr_t window = 0;
    int generation = 0, width = 0, height = 0;

    bool observe(uintptr_t nextWindow, int nextGeneration, int nextWidth, int nextHeight,
                 bool initializeOnly = false) {
        if (initialized && window && initializeOnly) return false;
        bool changed = !initialized || window != nextWindow || generation != nextGeneration
            || width != nextWidth || height != nextHeight;
        initialized = true;
        window = nextWindow; generation = nextGeneration;
        width = nextWidth; height = nextHeight;
        return changed;
    }
};
