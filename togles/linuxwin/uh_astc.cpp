// BC endpoint/weight translation adapted from klaxons1/ASTransCoder,
// ab4b21320b3158f9f9c32123f36060302c62369c (MIT, ../ASTransCoder-LICENSE).
// Unlike the prototype, reverse EVERY weight bit, not just the pixel order.
// Never substitute color weights for independent BC3 alpha weights.
#include "uh_astc.h"
#include "astcenc.h"
#include <string.h>
#include <limits.h>
#include <pthread.h>

namespace {
pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
astcenc_context *contexts[2] = { 0, 0 };
struct Lock {
    Lock() { pthread_mutex_lock(&mutex); }
    ~Lock() { pthread_mutex_unlock(&mutex); }
};
unsigned Read16(const uint8_t *p) { return p[0] | (unsigned(p[1]) << 8); }
void PutBits(uint8_t *p, unsigned value, unsigned offset, unsigned count) {
    for (unsigned i = 0; i < count; ++i)
        p[(offset + i) / 8] |= ((value >> i) & 1) << ((offset + i) % 8);
}
void Expand565(unsigned c, unsigned *rgb) {
    // Rounded expansion, matching the existing DXT decompressor.
    rgb[0] = ((c >> 11) * 255 + 15) / 31;
    rgb[1] = (((c >> 5) & 63) * 255 + 31) / 63;
    rgb[2] = ((c & 31) * 255 + 15) / 31;
}
bool Direct(const uint8_t *source, UHBCFormat format, uint8_t *out) {
    const uint8_t *color = source;
    unsigned alpha = 255;
    if (format == UH_BC2) return false;
    if (format == UH_BC3) {
        // Equal endpoints alone do NOT imply constant alpha: codes 6/7 in
        // the six-alpha mode still mean transparent/opaque, respectively.
        uint64_t indices = 0;
        for (unsigned i = 0; i < 6; ++i) indices |= uint64_t(source[2+i]) << (8*i);
        unsigned values[8] = {source[0], source[1], 0, 0, 0, 0, 0, 255};
        for (unsigned i = 2; i < 8; ++i) {
            if (values[0] > values[1]) values[i] = ((8-i)*values[0] + (i-1)*values[1])/7;
            else if (i < 6) values[i] = ((6-i)*values[0] + (i-1)*values[1])/5;
        }
        alpha = values[indices & 7];
        for (unsigned i = 1; i < 16; ++i)
            if (values[(indices >> (3*i)) & 7] != alpha) return false;
        color += 8;
    }
    unsigned a[3], b[3];
    unsigned c0 = Read16(color), c1 = Read16(color + 2);
    unsigned codes = unsigned(color[4]) | (unsigned(color[5]) << 8)
        | (unsigned(color[6]) << 16) | (unsigned(color[7]) << 24);
    // The one-plane, four-weight mode cannot represent the BC1 three-color
    // midpoint AND its transparent/black entry. Use a real encoder instead.
    if (format != UH_BC3 && c0 <= c1) return false;
    Expand565(c0, a); Expand565(c1, b);
    bool swap = a[0]+a[1]+a[2] > b[0]+b[1]+b[2];
    memset(out, 0, 16);
    PutBits(out, 66, 0, 11); // 4x4, one plane, QUANT_4 weights
    PutBits(out, format == UH_BC3 ? 12 : 8, 13, 4); // RGBA/RGB direct endpoints
    for (unsigned channel = 0; channel < 3; ++channel) {
        PutBits(out, swap ? b[channel] : a[channel], 17+channel*16, 8);
        PutBits(out, swap ? a[channel] : b[channel], 25+channel*16, 8);
    }
    if (format == UH_BC3) {
        PutBits(out, alpha, 65, 8); PutBits(out, alpha, 73, 8);
    }
    static const unsigned weights[4] = {0, 3, 1, 2};
    for (unsigned pixel = 0; pixel < 16; ++pixel) {
        unsigned weight = weights[(codes >> (2*pixel)) & 3];
        if (swap) weight = 3-weight;
        // ASTC's weight bitstream runs backwards, INCLUDING bits inside a code.
        for (unsigned bit = 0; bit < 2; ++bit)
            PutBits(out, (weight >> bit) & 1, 127-pixel*2-bit, 1);
    }
    return true;
}
astcenc_context *Context(bool srgb) {
    unsigned index = srgb ? 1 : 0;
    if (!contexts[index]) {
        astcenc_config config;
        if (astcenc_config_init(srgb ? ASTCENC_PRF_LDR_SRGB : ASTCENC_PRF_LDR,
                4, 4, 1, ASTCENC_PRE_FASTEST, 0, &config) != ASTCENC_SUCCESS) return 0;
        if (astcenc_context_alloc(&config, 1, &contexts[index]) != ASTCENC_SUCCESS) return 0;
    }
    return contexts[index];
}
bool Encode(const uint8_t *block, UHBCFormat format, bool srgb, uint8_t *out) {
    uint32_t rgba[16];
    UHBCDecodeBlock(format, block, rgba);
    astcenc_context *ctx = Context(srgb);
    if (!ctx) return false;
    void *planes[] = {rgba};
    astcenc_image image = {4, 4, 1, ASTCENC_TYPE_U8, planes};
    const astcenc_swizzle swizzle = {ASTCENC_SWZ_R, ASTCENC_SWZ_G, ASTCENC_SWZ_B, ASTCENC_SWZ_A};
    astcenc_error result = astcenc_compress_image(ctx, &image, &swizzle, out, 16, 0);
    astcenc_compress_reset(ctx);
    return result == ASTCENC_SUCCESS;
}
}
size_t UHASTCSize(unsigned width, unsigned height) {
    if (!width || !height || width > UINT_MAX-3 || height > UINT_MAX-3) return 0;
    size_t x = (width+3)/4, y = (height+3)/4;
    if (x > SIZE_MAX / 16 / y) return 0;
    return x*y*16;
}
bool UHASTCTranscode(UHBCFormat format, bool srgb, unsigned width, unsigned height,
    const void *source, size_t sourceSize, void *output, size_t outputSize, size_t *directBlocks) {
    if (directBlocks) *directBlocks = 0;
    size_t bytes = UHASTCSize(width, height);
    if (format < UH_BC1_RGB || format > UH_BC3 || !bytes || !source || !output || outputSize < bytes)
        return false;
    unsigned stride = format == UH_BC1_RGB || format == UH_BC1_RGBA ? 8 : 16;
    size_t count = bytes/16;
    if (sourceSize != count*stride) return false;
    Lock lock; // GL uploads are serialized; also safe for native worker tests.
    const uint8_t *in = static_cast<const uint8_t *>(source);
    uint8_t *out = static_cast<uint8_t *>(output);
    for (size_t i = 0; i < count; ++i) {
        if (Direct(in+i*stride, format, out+i*16)) {
            if (directBlocks) ++*directBlocks;
        } else if (!Encode(in+i*stride, format, srgb, out+i*16)) return false;
    }
    return true;
}
void UHASTCShutdown() {
    Lock lock;
    for (unsigned i = 0; i < 2; ++i) {
        astcenc_context_free(contexts[i]); contexts[i] = 0;
    }
}
