// Underhell ASTransCoder integration. See ../ASTransCoder-LICENSE and
// ../thirdparty/astcenc/LICENSE.txt. The API has no GL/engine dependencies.
#ifndef UH_ASTC_H
#define UH_ASTC_H
#include <stddef.h>
#include <stdint.h>
#include "uh_bcdec.h"

size_t UHASTCSize(unsigned width, unsigned height);
// Input/output must have exactly the required block capacity. Common BC1 and
// constant-alpha BC3 blocks are translated without an intermediate RGBA image.
// Other blocks use Arm's encoder with only a 4x4 RGBA stack buffer.
bool UHASTCTranscode(UHBCFormat format, bool srgb, unsigned width, unsigned height,
    const void *source, size_t sourceSize, void *output, size_t outputSize,
    size_t *directBlocks = 0);
void UHASTCShutdown();
#endif
