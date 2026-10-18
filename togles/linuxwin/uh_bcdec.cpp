#include "uh_bcdec.h"
#include "decompress.h"
#include <string.h>
#include <limits.h>
size_t UHBCSize(UHBCFormat format, unsigned width, unsigned height) {
    if (format < UH_BC1_RGB || format > UH_BC3 || !width || !height
        || width > UINT_MAX-3 || height > UINT_MAX-3) return 0;
    size_t x = (width+3)/4, y = (height+3)/4;
    unsigned stride = format == UH_BC1_RGB || format == UH_BC1_RGBA ? 8 : 16;
    if (x > SIZE_MAX / stride / y) return 0;
    return x*y*stride;
}
void UHBCDecodeBlock(UHBCFormat format, const uint8_t *source, uint32_t rgba[16]) {
    int simple = 0, complex = 0;
    if (format == UH_BC2) DecompressBlockDXT3(0, 0, 4, source, 0, &simple, &complex, rgba);
    else if (format == UH_BC3) DecompressBlockDXT5(0, 0, 4, source, 0, &simple, &complex, rgba);
    else {
        DecompressBlockDXT1(0, 0, 4, source, 1, &simple, &complex, rgba);
        if (format == UH_BC1_RGB)
            for (unsigned i = 0; i < 16; ++i) rgba[i] |= 0xff000000u;
    }
}
bool UHBCDecodeImage(UHBCFormat format, unsigned width, unsigned height,
    const void *source, size_t sourceSize, void *pixels, size_t pixelSize, unsigned channels) {
    size_t size = UHBCSize(format, width, height);
    if (!size || sourceSize != size || !source || !pixels || (channels != 3 && channels != 4)
        || size_t(width) > SIZE_MAX / channels / height || pixelSize < size_t(width)*height*channels)
        return false;
    unsigned stride = format == UH_BC1_RGB || format == UH_BC1_RGBA ? 8 : 16;
    const uint8_t *in = static_cast<const uint8_t *>(source);
    uint8_t *out = static_cast<uint8_t *>(pixels);
    for (unsigned y = 0; y < height; y += 4) {
        for (unsigned x = 0; x < width; x += 4, in += stride) {
            uint32_t block[16];
            UHBCDecodeBlock(format, in, block);
            for (unsigned j = 0; j < 4 && y+j < height; ++j)
                for (unsigned i = 0; i < 4 && x+i < width; ++i)
                    memcpy(out+(size_t(y+j)*width+x+i)*channels,
                        reinterpret_cast<const uint8_t *>(block+j*4+i), channels);
        }
    }
    return true;
}
