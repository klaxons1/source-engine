#include "uh_astc.h"
#include <cassert>
#include <cstdio>
#include <vector>
#include <cstring>
#include <climits>
using GLenum = unsigned;
using GLbitfield = unsigned;
using GLuint64 = unsigned long long;
enum { GL_ALREADY_SIGNALED=0x911A, GL_TIMEOUT_EXPIRED=0x911B,
       GL_CONDITION_SATISFIED=0x911C, GL_WAIT_FAILED=0x911D,
       GL_SYNC_FLUSH_COMMANDS_BIT=1 };
#include "uh_glsync.h"
#include "query_test.inc"
#include "upload_test.inc"
void TestSync() {
    assert(UHGLFenceSignaled(GL_ALREADY_SIGNALED));
    assert(UHGLFenceSignaled(GL_CONDITION_SATISFIED));
    assert(!UHGLFenceSignaled(GL_TIMEOUT_EXPIRED));
    for (unsigned ready : {GL_ALREADY_SIGNALED, GL_CONDITION_SATISFIED}) {
        int calls = 0;
        assert(UHGLWaitForFence([&](unsigned flags, unsigned long long timeout) {
            assert(!flags && !timeout); ++calls; return ready;
        })); assert(calls == 1);
    }
    int calls = 0;
    assert(UHGLWaitForFence([&](unsigned flags, unsigned long long timeout) -> unsigned {
        ++calls;
        if (calls == 1) { assert(!flags && !timeout); return GL_TIMEOUT_EXPIRED; }
        assert(timeout == 1000000);
        assert(flags == (calls == 2 ? GL_SYNC_FLUSH_COMMANDS_BIT : 0));
        return calls == 4 ? GL_CONDITION_SATISFIED : GL_TIMEOUT_EXPIRED;
    })); assert(calls == 4);
    calls = 0;
    assert(!UHGLWaitForFence([&](unsigned, unsigned long long) -> unsigned {
        ++calls; return GL_WAIT_FAILED;
    })); assert(calls == 1);
    calls = 0;
    assert(!UHGLWaitForFence([&](unsigned, unsigned long long) -> unsigned {
        return ++calls == 1 ? GL_TIMEOUT_EXPIRED : GL_WAIT_FAILED;
    })); assert(calls == 2);
}
int main(int argc, char **argv) {
    assert(argc == 4);
    TestSync(); TestQueries(); TestUploads(strcmp(argv[3], "off") != 0);
    assert(!UHASTCSize(0, 4) && !UHASTCSize(UINT_MAX, UINT_MAX));
    assert(!UHBCSize(UH_BC3, UINT_MAX, 4));
    assert(UHASTCSize(1, 1) == 16 && UHASTCSize(5, 7) == 64);
    unsigned char in[16] = {}, out[64] = {};
    assert(!UHASTCTranscode(UH_BC1_RGB, false, 4, 4, in, 7, out, 16));
    assert(!UHASTCTranscode(UH_BC1_RGB, false, 4, 4, in, 8, out, 15));
    assert(!UHBCDecodeImage(UH_BC3, 2, 2, in, 15, out, 16, 4));
    assert(!UHBCDecodeImage(UH_BC3, 2, 2, in, 16, out, 15, 4));
    FILE *input = fopen(argv[1], "rb"), *output = fopen(argv[2], "wb");
    assert(input && output);
    unsigned header[4];
    while (fread(header, sizeof(header), 1, input)) {
        UHBCFormat format = UHBCFormat(header[0] & 255);
        bool srgb = header[0] & 256;
        unsigned w = header[1], h = header[2], size = header[3];
        std::vector<unsigned char> source(size+1), astc(UHASTCSize(w,h)), rgba(w*h*4);
        assert(fread(source.data()+1, size, 1, input) == 1); // deliberately unaligned
        size_t direct = 0;
        assert(UHASTCTranscode(format, srgb, w, h, source.data()+1, size, astc.data(), astc.size(), &direct));
        assert(UHBCDecodeImage(format, w, h, source.data()+1, size, rgba.data(), rgba.size(), 4));
        unsigned result[] = {unsigned(astc.size()), unsigned(direct)};
        assert(fwrite(result, sizeof(result), 1, output) == 1);
        assert(fwrite(astc.data(), astc.size(), 1, output) == 1);
        assert(fwrite(rgba.data(), rgba.size(), 1, output) == 1);
    }
    assert(!ferror(input)); fclose(input); fclose(output);
    UHASTCShutdown();
    puts("Native renderer: bounds, unaligned input, fence waits, GetData and upload routing PASS");
}
