#ifndef UH_BCDEC_H
#define UH_BCDEC_H
#include <stddef.h>
#include <stdint.h>
enum UHBCFormat { UH_BC1_RGB, UH_BC1_RGBA, UH_BC2, UH_BC3 };
size_t UHBCSize(UHBCFormat format, unsigned width, unsigned height);
void UHBCDecodeBlock(UHBCFormat format, const uint8_t *source, uint32_t rgba[16]);
// Clipped block writes: works for NPOT textures and the 1x1/2x2 mip tail.
bool UHBCDecodeImage(UHBCFormat format, unsigned width, unsigned height,
    const void *source, size_t sourceSize, void *pixels, size_t pixelSize, unsigned channels);
#endif
