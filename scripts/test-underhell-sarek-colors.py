#!/usr/bin/env python3
"""Compile production texture maps, vertex declarations and byte writers.

Uses real native D3D9 headers and an independent D3D9 byte-order oracle.
This checks the CPU/COM contract, not Vulkan rendering on a GPU.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def block(source, signature, semicolon=False):
    start = source.index(signature)
    begin = source.index('{', start)
    depth = 1
    end = begin + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + (';' if semicolon else '')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, default=ROOT / 'artifacts/dxvk-sarek-android-arm64')
    args = parser.parse_args()
    image = (ROOT / 'bitmap/imageformat.cpp').read_text()
    mesh = (ROOT / 'public/materialsystem/imesh.h').read_text()
    color_guard = mesh[mesh.index('#if defined( DX_TO_GL_ABSTRACTION )'):mesh.index('// forward declarations')]
    # Keep just the actual preprocessor guard, not the following separator.
    color_guard = color_guard[:color_guard.index('#endif') + len('#endif')]
    declarations = block((ROOT / 'materialsystem/shaderapidx9/vertexdecl.cpp').read_text(),
                         'static D3DDECLTYPE VertexElementToDeclType(')
    enums = '\n'.join(block((ROOT / path).read_text(), signature, True) for path, signature in (
        ('public/bitmap/imageformat.h', 'enum ImageFormat'),
        ('public/materialsystem/imaterial.h', 'enum VertexElement_t'),
        ('public/materialsystem/imaterialsystemhardwareconfig.h', 'enum VertexCompressionType_t')))
    functions = '\n'.join(block(image, signature) for signature in (
        'ImageFormat D3DFormatToImageFormat(', 'D3DFORMAT ImageFormatToD3DFormat('))
    writers = '\n'.join(block(mesh, signature) for signature in (
        'inline void CVertexBuilder::Color4ub(', 'inline void CVertexBuilder::Specular4ub(',
        'inline void CVertexBuilder::BoneMatrix('))
    prefix = r'''
#include <d3d9.h>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cassert>
#define Assert(x) assert(x)
#define BONE_MATRIX_INDEX_INVALID 255
#define COMPRESSED_NORMALS_TYPE 2
#define COMPRESSED_NORMALS_SEPARATETANGENTS_SHORT2 1
static bool IsX360() { return false; }
static void Detect_VertexElement_t_Changes(VertexElement_t) {}
static int sg_IndexSwap[4] = {2,1,0,3};
class CVertexBuilder {
public:
 alignas(4) unsigned char color[4]{}, specular[4]{}, bones[4]{};
 unsigned char *m_pColor=color, *m_pCurrColor=color, *m_pSpecular=specular, *m_pBoneMatrixIndex=bones;
 int m_nCurrentVertex=0, m_VertexSize_Specular=4, m_VertexSize_BoneMatrixIndex=4;
 void Color4ub(unsigned char,unsigned char,unsigned char,unsigned char);
 void Specular4ub(unsigned char,unsigned char,unsigned char,unsigned char);
 void BoneMatrix(int,int);
};
'''
    # D3D9 normalized byte formats: UBYTE4N/RGBA vs D3DCOLOR/BGRA.
    test = r'''
using Color = std::array<unsigned char,4>;
static Color decode(const unsigned char* bytes, bool bgra) {
 return {bytes[bgra?2:0],bytes[1],bytes[bgra?0:2],bytes[3]};
}
int main() {
#ifdef UNDERHELL_SAREK
 assert(ImageFormatToD3DFormat(IMAGE_FORMAT_RGBA8888)==D3DFMT_A8B8G8R8);
 assert(D3DFormatToImageFormat(D3DFMT_A8B8G8R8)==IMAGE_FORMAT_RGBA8888);
 assert(ImageFormatToD3DFormat(IMAGE_FORMAT_BGRA8888)==D3DFMT_A8R8G8B8);
 assert(D3DFormatToImageFormat(D3DFMT_A8R8G8B8)==IMAGE_FORMAT_BGRA8888);
 assert(VertexElementToDeclType(VERTEX_ELEMENT_COLOR,VERTEX_COMPRESSION_NONE)==D3DDECLTYPE_UBYTE4N);
 assert(VertexElementToDeclType(VERTEX_ELEMENT_SPECULAR,VERTEX_COMPRESSION_NONE)==D3DDECLTYPE_UBYTE4N);
 assert(VertexElementToDeclType(VERTEX_ELEMENT_BONEINDEX,VERTEX_COMPRESSION_NONE)==D3DDECLTYPE_UBYTE4N);
 const Color colors[] = {{255,0,0,255},{0,255,0,255},{0,0,255,255},{0,128,255,255},
                         {255,128,0,255},{255,255,255,255},{0,0,0,0},{17,89,221,123}};
 for (const auto& c : colors) {
   Color rgba=c, bgra={c[2],c[1],c[0],c[3]};
   assert(decode(rgba.data(),ImageFormatToD3DFormat(IMAGE_FORMAT_RGBA8888)==D3DFMT_A8R8G8B8)==c);
   assert(decode(bgra.data(),ImageFormatToD3DFormat(IMAGE_FORMAT_BGRA8888)==D3DFMT_A8R8G8B8)==c);
   CVertexBuilder vertex;
   vertex.Color4ub(c[0],c[1],c[2],c[3]); vertex.Specular4ub(c[0],c[1],c[2],c[3]);
   assert(decode(vertex.color,false)==c && decode(vertex.specular,false)==c);
   // Unchanged GLES-built companion writers supply RGBA too.
   assert(decode(rgba.data(),VertexElementToDeclType(VERTEX_ELEMENT_COLOR,VERTEX_COMPRESSION_NONE)==D3DDECLTYPE_D3DCOLOR)==c);
 }
 CVertexBuilder vertex; vertex.BoneMatrix(0,3); vertex.BoneMatrix(1,17); vertex.BoneMatrix(2,42);
 // Existing DX9 shader D3DCOLORtoUBYTE4 applies .zyxw after normalized fetch.
 auto fetched=decode(vertex.bones,false);
 assert(fetched[2]==3 && fetched[1]==17 && fetched[0]==42);
 puts("PASS: native RGBA/BGRA texture maps, RGBA vertex/specular ABI, packed bone indices, alpha");
#else
 assert(ImageFormatToD3DFormat(IMAGE_FORMAT_RGBA8888)==D3DFMT_A8R8G8B8);
 assert(D3DFormatToImageFormat(D3DFMT_A8R8G8B8)==IMAGE_FORMAT_RGBA8888);
 assert(VertexElementToDeclType(VERTEX_ELEMENT_COLOR,VERTEX_COMPRESSION_NONE)==D3DDECLTYPE_D3DCOLOR);
 CVertexBuilder vertex; vertex.Color4ub(17,89,221,123);
 assert((decode(vertex.color,false)==Color{17,89,221,123}));
 puts("PASS: legacy GLES format and vertex contracts unchanged");
#endif
}
'''
    with tempfile.TemporaryDirectory(prefix='sarek-colors-') as tmp:
        cpp = Path(tmp) / 'colors.cpp'
        # VertexElement_t must exist before the no-op compile-time guard adapter.
        cpp.write_text('#include <d3d9.h>\n' + enums + prefix + color_guard + '\n' +
                       functions + '\n' + declarations + '\n' + writers + '\n' + test)
        for name, defines in (('native', ['UNDERHELL_SAREK=1']),
                              ('gles', ['DX_TO_GL_ABSTRACTION=1', 'TOGLES=1'])):
            exe = Path(tmp) / name
            subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++14',
                '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                *['-D'+d for d in defines],
                *['-I'+str(args.sdk / 'include' / d) for d in ('windows','directx')],
                str(cpp), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
