#pragma once
#include <stdint.h>
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
// Call before Direct3DCreate9, using the real physical display metadata.
// Example: refreshNumerator=60000, refreshDenominator=1001, NOT integer-rounded Hz.
// Returns false for invalid input. No guessed default mode is provided.
bool DXVKSarekSetAndroidDisplay(uint32_t width, uint32_t height,
    uint32_t refreshNumerator, uint32_t refreshDenominator);
// Unique native factory: do not bind the companion TOGL's same-named D3D9 export.
struct IDirect3D9;
struct IDirect3D9* DXVKSarekDirect3DCreate9(uint32_t sdkVersion);
// Matching native IDirect3D9* ONLY, returned by the unique factory above.
// Reports device-local Vulkan heap budget, or advertised size without budget support.
uint64_t DXVKSarekGetAdapterMemoryBytes(void* d3d9, uint32_t ordinal);
// Optional stable HWND bridge. Callback returns a freshly ACQUIRED ANativeWindow*
// (or NULL while absent). Queries release immediately; a Vulkan surface keeps
// its acquired reference until vkDestroySurfaceKHR.
struct ANativeWindow;
void DXVKSarekSetAndroidWindowProvider(struct ANativeWindow* (*provider)(void* hwnd));
void DXVKSarekNotifyAndroidSurface(void); // notify replacement/resume; recreate old VkSurface
#ifdef __cplusplus
}
#endif
// Without a provider, HWND must be an ANativeWindow*. With a provider it is a
// stable host token (e.g. SDL_Window*), resolved to the CURRENT Surface each time.
// The host owns the window, its lifetime, input and Android pause/resume/reset.
// This header does not make Source's custom TOGLES D3D9 ABI compatible with Sarek.
