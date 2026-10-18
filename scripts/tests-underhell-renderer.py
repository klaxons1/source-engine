#!/usr/bin/env python3
"""Compile production renderer paths under ASan/UBSan; validate ASTC independently.
Dependency: texture2ddecoder==1.0.6 (test-only, not shipped in the APK).
"""
from pathlib import Path
import os
import random
import struct
import subprocess
import tempfile
import texture2ddecoder as oracle

ROOT = Path(__file__).resolve().parent.parent
QUERY_STUB = r'''
using DWORD=unsigned; using uint=unsigned; using HRESULT=int;
#define GL_BATCH_PERF_CALL_TIMER
#define Assert assert
const int S_FALSE=1, S_OK=0, D3DERR_NOTAVAILABLE=-1, D3D_DEVICE_VALID_MARKER=42;
const int D3DQUERYTYPE_OCCLUSION=1, D3DQUERYTYPE_EVENT=2, D3DGETDATA_FLUSH=1;
unsigned ThreadGetCurrentId(){return 123;}
struct Device {int m_nValidMarker=42;};
struct Context {unsigned m_nCurOwnerThreadId=123;};
struct Query {
 bool ready=false; int completed=0;
 bool IsStarted(){return true;} bool IsStopped(){return true;} bool IsDone(){return ready;}
 void Complete(uint *p){assert(ready);++completed;if(p)*p=77;}
};
struct FakeGL;
struct QueryGL {int flushed=0;void glFlush(){++flushed;}} queryGL;
#define gGL (&queryGL)
#define GLMDebugPrintf(...) ((void)0)
struct IDirect3DQuery9 {
 Device device; Context context; Query query;
 Device *m_device=&device; Context *m_ctx=&context; Query *m_query=&query;
 unsigned m_nIssueStartThreadID=123,m_nIssueEndThreadID=123;
 int m_nIssueStartDrawCallIndex=0,m_nIssueEndDrawCallIndex=1;
 int m_nIssueStartFrameIndex=0,m_nIssueEndFrameIndex=0;
 int m_nIssueStartQueryCreationCounter=0,m_nIssueEndQueryCreationCounter=0;
 int m_type=D3DQUERYTYPE_OCCLUSION;
 HRESULT GetData(void*,DWORD,DWORD);
};
'''
QUERY_TEST = r'''
#undef gGL
void TestQueries() {
 for(int type : {D3DQUERYTYPE_OCCLUSION,D3DQUERYTYPE_EVENT})
  for(unsigned flags : {0u,1u}) for(bool ready : {false,true}) {
   IDirect3DQuery9 q;q.m_type=type;q.query.ready=ready;queryGL.flushed=0;
   unsigned result=99;
   assert(q.GetData(&result,4,flags)==(ready?S_OK:S_FALSE));
   assert(queryGL.flushed==int(flags));assert(q.query.completed==int(ready));
   assert(result==(ready?(type==D3DQUERYTYPE_EVENT?1u:77u):0u));
  }
 IDirect3DQuery9 q;q.query.ready=true;assert(q.GetData(nullptr,0,1)==S_OK);
 q.m_nIssueEndQueryCreationCounter=1;assert(q.GetData(nullptr,0,1)==D3DERR_NOTAVAILABLE);
}
'''
UPLOAD_STUB = r'''
#include <cstdlib>
#include <stdexcept>
using GLint=int;using GLsizei=int;using GLvoid=void;using GLboolean=unsigned char;
enum {GL_NUM_COMPRESSED_TEXTURE_FORMATS=0x86A2,GL_COMPRESSED_TEXTURE_FORMATS=0x86A3,
 GL_COMPRESSED_RGB_S3TC_DXT1_EXT=0x83F0,GL_COMPRESSED_RGBA_S3TC_DXT1_EXT=0x83F1,
 GL_COMPRESSED_RGBA_S3TC_DXT3_EXT=0x83F2,GL_COMPRESSED_RGBA_S3TC_DXT5_EXT=0x83F3,
 GL_COMPRESSED_SRGB_S3TC_DXT1_EXT=0x8C4C,GL_COMPRESSED_SRGB_ALPHA_S3TC_DXT1_EXT=0x8C4D,
 GL_COMPRESSED_SRGB_ALPHA_S3TC_DXT3_EXT=0x8C4E,GL_COMPRESSED_SRGB_ALPHA_S3TC_DXT5_EXT=0x8C4F,
 GL_SRGB8_ALPHA8=0x8C43,GL_RGBA8=0x8058,GL_RGBA=0x1908,GL_UNSIGNED_BYTE=0x1401};
#define UNDERHELL_ASTC 1
#define Msg(...) ((void)0)
#define Error(...) throw std::runtime_error("upload failed")
struct FakeCommand {bool enabled=true;int FindParm(const char*){return enabled?1:0;}} command;
FakeCommand *CommandLine(){return &command;}
struct UploadGL {
 unsigned format=0;int compressed=0,plain=0;bool nullData=false;
 void glGetIntegerv(unsigned name,int *p){
  if(name==GL_NUM_COMPRESSED_TEXTURE_FORMATS)*p=3;
  else {p[0]=0x83F0;p[1]=0x83F3;p[2]=0x93B0;}
 }
 void glCompressedTexImage2D(unsigned,int,unsigned fmt,int w,int h,int,int bytes,const void *p){
  format=fmt;++compressed;nullData=!p;
  assert(bytes==int(fmt==0x93B0?UHASTCSize(w,h):UHBCSize(fmt==0x83F0?UH_BC1_RGB:UH_BC3,w,h)));
 }
 void glTexImage2D(unsigned,int,unsigned fmt,int,int,int,unsigned,unsigned,const void *p){
  format=fmt;++plain;nullData=!p;
 }
} uploadGL;
#define gGL (&uploadGL)
'''
UPLOAD_TEST = r'''
#undef gGL
void TestUploads(bool enabled) {
 command.enabled=enabled;
 unsigned char bc[64]={};bc[8]=255;bc[9]=255;
 CompressedTexImage2D(0,0,0x83F0,4,4,0,8,bc);assert(uploadGL.format==0x83F0);
 CompressedTexImage2D(0,0,0x83F3,4,4,0,16,bc);assert(uploadGL.format==0x83F3);
 CompressedTexImage2D(0,0,0x83F2,4,4,0,16,bc);assert(uploadGL.format==(enabled?0x93B0:GL_RGBA8));
 CompressedTexImage2D(0,0,0x8C4E,2,2,0,16,bc);assert(uploadGL.format==GL_SRGB8_ALPHA8);
 CompressedTexImage2D(0,0,0x83F2,1,1,0,16,nullptr);assert(uploadGL.nullData);
 assert(uploadGL.format==(enabled?0x93B0:GL_RGBA8));
 // A late three-color mip must stay ASTC, not invalidate an earlier direct mip.
 bc[0]=255;bc[1]=255;bc[2]=0;bc[3]=0;
 CompressedTexImage2D(0,0,0x83F1,4,4,0,8,bc);unsigned first=uploadGL.format;
 bc[0]=0;bc[1]=0;bc[2]=255;bc[3]=255;bc[4]=0xff;
 CompressedTexImage2D(0,1,0x83F1,2,2,0,8,bc);assert(uploadGL.format==first);
 CompressedTexImage2D(0,0,0x83F2,5,7,0,64,bc);assert(uploadGL.format==first);
 // Dynamic / autogen callers opt out, even when the checkbox is on.
 UHCompressedTexImage2D(0,0,0x83F2,4,4,0,16,bc,false);assert(uploadGL.format==GL_RGBA8);
 bool failed=false;try{CompressedTexImage2D(0,0,0x83F2,2,2,0,15,bc);}catch(...){failed=true;}assert(failed);
}
'''


DYNAMIC_STUB = r'''
const unsigned GL_PIXEL_UNPACK_BUFFER=0x88EC, kGLMTexDynamic=0x80;
struct GLMTexLayoutSlice {int m_storageSize=16,m_storageOffset=8;};
struct DynFormat {int m_chunkSize=4;};
struct DynLayout {struct {unsigned m_texFlags=kGLMTexDynamic;} m_key;
 DynFormat format;DynFormat *m_format=&format;GLMTexLayoutSlice m_slices[2];};
struct DynDesc {int m_sliceIndex=1;};
struct DynGL {int bound=7;unsigned char *mapped=nullptr;bool unmapped=false;
 void glUnmapBuffer(unsigned){assert(bound==7);unmapped=true;memset(mapped,0xdd,24);}
 void glBindBuffer(unsigned,unsigned value){bound=value;}
} dynGL;
#define gGL (&dynGL)
struct DynTex {
 DynLayout layout;DynLayout *m_layout=&layout;unsigned char *m_mapped=nullptr;bool wrote=false;
 unsigned char expected[16];
 void WriteTexels(DynDesc *,bool){assert(dynGL.unmapped && dynGL.bound==0);
  assert(!memcmp(m_mapped,expected,16));wrote=true;}
 void UnlockFixture(){DynDesc d;DynDesc *desc=&d;bool fullyDirty=true;
'''
DYNAMIC_TEST = r'''
 }};
#undef gGL
void TestDynamic(){
 unsigned char source[24];for(unsigned i=0;i<24;++i)source[i]=i;
 DynTex tex;memcpy(tex.expected,source+8,16);tex.m_mapped=source;dynGL.mapped=source;
 tex.UnlockFixture();assert(tex.wrote && !tex.m_mapped && dynGL.bound==0);
}
'''


def bgra_to_rgba(data):
    out = bytearray(data)
    out[0::4], out[2::4] = data[2::4], data[0::4]
    return bytes(out)


def bc_reference(kind, width, height, data):
    # Independent spec implementation. texture2ddecoder 1.0.6 incorrectly uses
    # BC1 three-color interpolation in BC3 when c0 <= c1; do not copy that bug.
    result = bytearray(width*height*4)
    stride = 8 if kind < 2 else 16
    offset = 0
    for y in range(0,height,4):
        for x in range(0,width,4):
            block = data[offset:offset+stride]; offset += stride
            color = block if kind < 2 else block[8:]
            c0,c1,codes = struct.unpack('<HHI',color)
            def expand(c): return [(c>>11)*255//31, ((c>>5)&63)*255//63, (c&31)*255//31]
            a,b = expand(c0),expand(c1)
            palette = [a,b]
            if kind >= 2 or c0 > c1:
                palette += [[(2*u+v)//3 for u,v in zip(a,b)],[(u+2*v)//3 for u,v in zip(a,b)]]
            else: palette += [[(u+v)//2 for u,v in zip(a,b)],[0,0,0]]
            alpha = [255]*16
            if kind==2:
                bits=int.from_bytes(block[:8],'little');alpha=[((bits>>(4*i))&15)*17 for i in range(16)]
            elif kind==3:
                a0,a1=block[:2]; values=[a0,a1]
                values += [((8-i)*a0+(i-1)*a1)//7 for i in range(2,8)] if a0>a1 else [((6-i)*a0+(i-1)*a1)//5 for i in range(2,6)]+[0,255]
                bits=int.from_bytes(block[2:8],'little');alpha=[values[(bits>>(3*i))&7] for i in range(16)]
            for j in range(4):
                for i in range(4):
                    if x+i>=width or y+j>=height: continue
                    n=j*4+i;code=(codes>>(2*n))&3
                    aa=0 if kind==1 and c0<=c1 and code==3 else alpha[n]
                    start=((y+j)*width+x+i)*4;result[start:start+4]=bytes(palette[code]+[aa])
    return result


def run():
    rng = random.Random(7319)
    cases = []
    # Both endpoint orders in RGB-sum space, every index, random colors.
    direct = b"".join(struct.pack('<HHI', *sorted((rng.randrange(65536), rng.randrange(65536)), reverse=True), rng.getrandbits(32)) for _ in range(4096))
    cases.append((0, False, 256, 256, direct, 'direct'))
    # Alpha varies independently of constant RGB; both BC3 alpha modes.
    for a, b in ((255, 0), (0, 255), (64, 64)):
        indices = sum((i % 8) << (i*3) for i in range(16))
        block = bytes((a,b)) + indices.to_bytes(6,'little') + struct.pack('<HHI',0xf800,0xf800,0)
        cases.append((3,False,4,4,block,'alpha'))
    # Constant alpha, including nonopaque values, uses direct RGBA endpoints.
    for alpha in (0, 17, 128, 255):
        block = bytes((alpha,alpha))+bytes(6)+struct.pack('<HHI',0x001f,0xf800,0xe4e4e4e4)
        cases.append((3,False,4,4,block,'direct-alpha'))
    for kind in range(4):
        for srgb in (False, True):
            for w,h in ((1,1),(2,2),(3,5),(5,7),(8,8),(17,9)):
                size = ((w+3)//4)*((h+3)//4)*(8 if kind < 2 else 16)
                cases.append((kind,srgb,w,h,rng.randbytes(size),'random'))
    # A one-bit alpha mask, and the equal-endpoint mode.
    for color1 in (0xffff, 0):
        cases.append((1,False,4,4,struct.pack('<HHI',0,color1,0xe4e4e4e4),'mask'))
    with tempfile.TemporaryDirectory(prefix='underhell-renderer-') as name:
        tmp = Path(name)
        query = (ROOT/'togles/linuxwin/dxabstract.cpp').read_text()
        a = query.index('HRESULT IDirect3DQuery9::GetData(')
        b = query.index('\n// -----', a)
        (tmp/'query_test.inc').write_text(QUERY_STUB+query[a:b]+QUERY_TEST)
        tex = (ROOT/'togles/linuxwin/cglmtex.cpp').read_text()
        helpers = tex[tex.index('GLboolean isDXTc('):tex.index('// Check the actual format,')]
        policy = tex[tex.index('struct UHCompressedFormats'):tex.index('// TexSubImage should work')]
        (tmp/'upload_test.inc').write_text(UPLOAD_STUB+helpers+policy+UPLOAD_TEST)
        a=tex.index('if( m_layout->m_key.m_texFlags & kGLMTexDynamic && m_mapped )')
        b=tex.index('\n\t\t\t\telse\n',a)
        (tmp/'dynamic_test.inc').write_text(DYNAMIC_STUB+tex[a:b]+DYNAMIC_TEST)
        flags = ['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer']
        subprocess.run(['gcc','-std=c99',*flags,'-c',str(ROOT/'togles/linuxwin/decompress.c'),'-o',str(tmp/'dec.o')],check=True)
        vendor = ROOT/'togles/thirdparty/astcenc'
        sources = [ROOT/'scripts/tests/underhell_astc_native.cpp', ROOT/'togles/linuxwin/uh_astc.cpp',ROOT/'togles/linuxwin/uh_bcdec.cpp',*sorted(vendor.glob('astcenc_*.cpp'))]
        subprocess.run(['g++','-std=c++14','-pthread',*flags,'-I'+str(vendor),'-I'+str(ROOT/'togles/linuxwin'),'-I'+str(tmp),*map(str,sources),str(tmp/'dec.o'),'-o',str(tmp/'native')],check=True)
        input = tmp/'input'
        with input.open('wb') as stream:
            for kind,srgb,w,h,data,_ in cases:
                stream.write(struct.pack('<4I',kind+(256 if srgb else 0),w,h,len(data))+data)
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1')
        subprocess.run([str(tmp/'native'),str(input),str(tmp/'output'),'on'],check=True,env=env)
        (tmp/'empty').write_bytes(b'')
        subprocess.run([str(tmp/'native'),str(tmp/'empty'),str(tmp/'off'),'off'],check=True,env=env)
        result = (tmp/'output').read_bytes(); pos=0; max_error=0; direct_count=0
        for kind,srgb,w,h,data,label in cases:
            length, count = struct.unpack_from('<II',result,pos); pos+=8
            astc=result[pos:pos+length];pos+=length
            native=result[pos:pos+w*h*4];pos+=w*h*4
            decoded=bgra_to_rgba(oracle.decode_astc(astc,w,h,4,4))
            assert len(decoded)==w*h*4
            reference=bc_reference(kind,w,h,data)
            assert max(abs(a-b) for a,b in zip(native,reference))<=1,(kind,w,h,label,'BC decoder')
            if label.startswith('direct'):
                assert count==length//16
                error=max(abs(a-b) for a,b in zip(decoded,native));max_error=max(max_error,error)
                assert error<=4,('direct',error)
                assert decoded[3::4]==native[3::4], 'constant alpha changed'
            elif label=='alpha':
                assert count==0
                error=max(abs(a-b) for a,b in zip(decoded[3::4],native[3::4]))
                assert error<=24,('independent alpha',error)
            elif label=='mask':
                assert max(abs(a-b) for a,b in zip(decoded[3::4],native[3::4]))<=8
            # Random fallback blocks are lossy; reject error blocks and opaque
            # replacement of real alpha, not with a misleading lossless claim.
            if any(native[i] != 255 for i in range(3,len(native),4)):
                assert any(decoded[i] != 255 for i in range(3,len(decoded),4))
            direct_count+=count
        assert pos==len(result)
        print(f'Independent ASTC oracle: {len(cases)} images, {direct_count} direct blocks, max direct channel error {max_error}: PASS')

if __name__=='__main__':
    run()
