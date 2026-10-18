// Host contract test: no GPU or Android runtime is exercised here.
#include "wsi/wsi_platform.h"
#include "wsi/wsi_window.h"
#include "util/util_string.h"
#include <cassert>
#include <memory>
#include <cstring>
#include <iostream>
#include "../../../launcher/android/sarek_surface_state.h"
extern "C" bool DXVKSarekSetAndroidDisplay(uint32_t, uint32_t, uint32_t, uint32_t);
extern "C" int32_t ANativeWindow_getWidth(ANativeWindow* w) { return w->width; }
extern "C" int32_t ANativeWindow_getHeight(ANativeWindow* w) { return w->height; }
static int releases;
extern "C" void ANativeWindow_release(ANativeWindow*) { ++releases; }
extern "C" void DXVKSarekSetAndroidWindowProvider(ANativeWindow* (*)(void*));
extern "C" void DXVKSarekNotifyAndroidSurface();
static ANativeWindow window{1920, 1080}, replacement{2400, 1080};
static ANativeWindow* expectedWindow = &window;
static ANativeWindow* providerWindow;
static int token;
static ANativeWindow* provide(void* hwnd) { assert(hwnd == &token); return providerWindow; }
static VkResult surfaceResult = VK_SUCCESS;
static int surfaceCalls;
static VKAPI_ATTR VkResult VKAPI_CALL createSurface(VkInstance, const VkAndroidSurfaceCreateInfoKHR* info,
    const VkAllocationCallbacks* alloc, VkSurfaceKHR* surface) {
  assert(info->sType == VK_STRUCTURE_TYPE_ANDROID_SURFACE_CREATE_INFO_KHR);
  assert(info->window == expectedWindow && !info->pNext && !info->flags && !alloc);
  ++surfaceCalls;
  if (surfaceResult == VK_SUCCESS) *surface = reinterpret_cast<VkSurfaceKHR>(uintptr_t(42));
  return surfaceResult;
}
static VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL getProc(VkInstance, const char* name) {
  assert(!strcmp(name, "vkCreateAndroidSurfaceKHR"));
  return reinterpret_cast<PFN_vkVoidFunction>(createSurface);
}
static VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL missingProc(VkInstance, const char*) { return nullptr; }
int main() {
  using namespace dxvk::wsi;
  assert(!androidPresentFailed(VK_SUCCESS));
  assert(!androidPresentFailed(VK_SUBOPTIMAL_KHR));
  assert(androidPresentFailed(VK_ERROR_OUT_OF_DATE_KHR));
  assert(androidPresentFailed(VK_ERROR_SURFACE_LOST_KHR));
  assert(androidPresentFailed(VK_ERROR_DEVICE_LOST));
  SarekSurfaceState state;
  assert(state.observe(123, 1, 2309, 1080, true));
  for (int i = 0; i < 1000; ++i) assert(!state.observe(123, 1, 2309, 1080));
  assert(state.observe(123, 2, 2309, 1080)); // same pointer/extent, new Java generation
  assert(!state.observe(456, 3, 2309, 1080, true)); // queries cannot swallow a change
  assert(state.observe(456, 3, 2309, 1080));
  assert(state.observe(456, 3, 1080, 2309));
  assert(state.observe(0, 0, 0, 0));
  assert(!state.observe(0, 0, 0, 0));
  assert(state.observe(456, 4, 2309, 1080, true)); // seed after pause, before compositor callbacks
  assert(!state.observe(456, 4, 2309, 1080));

  WsiDriver* raw = nullptr;
  assert(AndroidWSI.createDriver(&raw));
  std::unique_ptr<WsiDriver> driver(raw);
  assert(!driver->getDefaultMonitor());
  assert(!DXVKSarekSetAndroidDisplay(0, 1080, 60, 1));
  assert(!DXVKSarekSetAndroidDisplay(1920, 1080, 60, 0));
  assert(!DXVKSarekSetAndroidDisplay(UINT32_MAX, 1080, 60, 1));
  assert(DXVKSarekSetAndroidDisplay(1920, 1080, 60000, 1001));
  auto monitor = driver->getDefaultMonitor();
  assert(monitor && driver->enumMonitors(0) == monitor && !driver->enumMonitors(1));
  WsiMode mode{};
  assert(driver->getCurrentDisplayMode(monitor, &mode));
  assert(mode.width == 1920 && mode.height == 1080 && mode.bitsPerPixel == 32);
  assert(mode.refreshRate.numerator == 60000 && mode.refreshRate.denominator == 1001);
  assert(!driver->getDisplayMode(monitor, 1, &mode));
  assert(!driver->getCurrentDisplayMode(nullptr, &mode));
  RECT rect{};
  assert(driver->getDesktopCoordinates(monitor, &rect) && rect.right == 1920 && rect.bottom == 1080);
  WCHAR name[32]{};
  assert(driver->getDisplayName(monitor, name) && dxvk::str::fromws(name) == "Android");
  uint32_t width = 99, height = 99;
  driver->getWindowSize(nullptr, &width, &height);
  assert(!width && !height);
  driver->getWindowSize(&window, &width, &height);
  assert(width == 1920 && height == 1080 && driver->isWindow(&window));
  assert(!driver->isWindow(nullptr) && driver->isMinimized(nullptr));
  WsiMode changed = mode; changed.width = 1280;
  assert(!driver->setWindowMode(monitor, &window, nullptr, changed));
  assert(driver->setWindowMode(monitor, &window, nullptr, mode));
  changed = mode; changed.refreshRate = {75, 1};
  assert(!driver->setWindowMode(monitor, &window, nullptr, changed));
  changed = mode; changed.bitsPerPixel = 16;
  assert(!driver->setWindowMode(monitor, &window, nullptr, changed));
  auto extensions = driver->getInstanceExtensions();
  assert(extensions.size() == 1 && !strcmp(extensions[0], VK_KHR_ANDROID_SURFACE_EXTENSION_NAME));
  VkSurfaceKHR surface = VK_NULL_HANDLE;
  assert(driver->createSurface(&window, getProc, VK_NULL_HANDLE, nullptr) == VK_ERROR_INITIALIZATION_FAILED);
  assert(driver->createSurface(nullptr, getProc, VK_NULL_HANDLE, &surface) == VK_ERROR_INITIALIZATION_FAILED);
  assert(driver->createSurface(&window, missingProc, VK_NULL_HANDLE, &surface) == VK_ERROR_EXTENSION_NOT_PRESENT);
  assert(driver->createSurface(&window, getProc, VK_NULL_HANDLE, &surface) == VK_SUCCESS);
  assert(surface == reinterpret_cast<VkSurfaceKHR>(uintptr_t(42)) && surfaceCalls == 1);
  surfaceResult = VK_ERROR_SURFACE_LOST_KHR;
  assert(driver->createSurface(&window, getProc, VK_NULL_HANDLE, &surface) == VK_ERROR_SURFACE_LOST_KHR);
  assert(surface == VK_NULL_HANDLE && surfaceCalls == 2);
  assert(!releases); // legacy host-owned window is not released by WSI
  DXVKSarekSetAndroidWindowProvider(provide);
  providerWindow = &window;
  driver->getWindowSize(&token, &width, &height);
  assert(width == 1920 && releases == 1);
  surfaceResult = VK_SUCCESS;
  assert(driver->createSurface(&token, getProc, VK_NULL_HANDLE, &surface) == VK_SUCCESS);
  assert(releases == 1); // held until VkSurface destruction, not just vkCreateSurface
  androidReleaseSurface(surface);
  assert(releases == 2);
  auto epoch = androidSurfaceEpoch(); DXVKSarekNotifyAndroidSurface();
  assert(androidSurfaceEpoch() == epoch + 1);
  providerWindow = expectedWindow = &replacement;
  driver->getWindowSize(&token, &width, &height);
  assert(width == 2400 && height == 1080 && releases == 3);
  assert(driver->createSurface(&token, getProc, VK_NULL_HANDLE, &surface) == VK_SUCCESS);
  androidReleaseSurface(surface); assert(releases == 4);
  providerWindow = nullptr;
  assert(driver->createSurface(&token, getProc, VK_NULL_HANDLE, &surface) == VK_ERROR_SURFACE_LOST_KHR);
  assert(surface == VK_NULL_HANDLE && releases == 4);
  driver->getWindowSize(&token, &width, &height); assert(!width && !height);
  DXVKSarekSetAndroidWindowProvider(nullptr);
  assert(dxvk::str::fromws(dxvk::str::tows(u8"Underhell — Привет").c_str()) == u8"Underhell — Привет");
  WCHAR shortName[3]; dxvk::str::tows("abcdef", shortName);
  assert(shortName[0] == L'a' && shortName[1] == L'b' && shortName[2] == 0);
  std::cout << "PASS: Android WSI host contract and UTF-8 (mock surface, not GPU)\n";
}
