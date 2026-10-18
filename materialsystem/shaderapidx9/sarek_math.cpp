// Minimal native D3DX math required by Source's precompiled-shader backend.
// Row-vector Direct3D conventions, including depth in [0,1], NOT OpenGL [-1,1].
#include "sarek_native.h"
#include "tier1/utlvector.h"
#include <cmath>
#include <cstring>

D3DXMATRIX* WINAPI D3DXMatrixMultiply(D3DXMATRIX* out, const D3DXMATRIX* a, const D3DXMATRIX* b) {
    D3DXMATRIX result;
    for (int r=0;r<4;r++) for(int c=0;c<4;c++) {
        result.m[r][c]=0;
        for(int k=0;k<4;k++) result.m[r][c]+=a->m[r][k]*b->m[k][c];
    }
    *out=result; return out;
}
D3DXMATRIX* WINAPI D3DXMatrixTranspose(D3DXMATRIX* out, const D3DXMATRIX* a) {
    D3DXMATRIX result;
    for(int r=0;r<4;r++) for(int c=0;c<4;c++) result.m[r][c]=a->m[c][r];
    *out=result; return out;
}
D3DXMATRIX* WINAPI D3DXMatrixInverse(D3DXMATRIX* out, FLOAT* determinant, const D3DXMATRIX* a) {
    double m[4][8], det=1;
    for(int r=0;r<4;r++) for(int c=0;c<8;c++) m[r][c]=c<4 ? a->m[r][c] : double(c-4==r);
    for(int c=0;c<4;c++) {
        int pivot=c;
        for(int r=c+1;r<4;r++) if(std::fabs(m[r][c])>std::fabs(m[pivot][c])) pivot=r;
        if(m[pivot][c]==0 || !std::isfinite(m[pivot][c])) { if(determinant)*determinant=0; return NULL; }
        if(pivot!=c) { for(int k=0;k<8;k++){ double v=m[c][k];m[c][k]=m[pivot][k];m[pivot][k]=v; } det=-det; }
        double d=m[c][c];det*=d;
        for(int k=0;k<8;k++) m[c][k]/=d;
        for(int r=0;r<4;r++) if(r!=c) { double v=m[r][c];for(int k=0;k<8;k++)m[r][k]-=v*m[c][k]; }
    }
    D3DXMATRIX result;
    for(int r=0;r<4;r++)for(int c=0;c<4;c++)result.m[r][c]=float(m[r][c+4]);
    if(determinant)*determinant=float(det);*out=result;return out;
}
D3DXMATRIX* WINAPI D3DXMatrixTranslation(D3DXMATRIX* out,FLOAT x,FLOAT y,FLOAT z) {
    D3DXMatrixIdentity(out);out->_41=x;out->_42=y;out->_43=z;return out;
}
D3DXMATRIX* WINAPI D3DXMatrixScaling(D3DXMATRIX* out,FLOAT x,FLOAT y,FLOAT z) {
    D3DXMatrixIdentity(out);out->_11=x;out->_22=y;out->_33=z;return out;
}
D3DXMATRIX* WINAPI D3DXMatrixRotationAxis(D3DXMATRIX* out,const D3DXVECTOR3* axis,FLOAT angle) {
    float len=std::sqrt(axis->x*axis->x+axis->y*axis->y+axis->z*axis->z);
    if(!len) return D3DXMatrixIdentity(out);
    float x=axis->x/len,y=axis->y/len,z=axis->z/len,c=std::cos(angle),s=std::sin(angle),d=1-c;
    D3DXMatrixIdentity(out);
    out->_11=c+x*x*d;out->_12=x*y*d+z*s;out->_13=x*z*d-y*s;
    out->_21=x*y*d-z*s;out->_22=c+y*y*d;out->_23=y*z*d+x*s;
    out->_31=x*z*d+y*s;out->_32=y*z*d-x*s;out->_33=c+z*z*d;return out;
}
D3DXMATRIX* WINAPI D3DXMatrixOrthoOffCenterRH(D3DXMATRIX* out,FLOAT l,FLOAT r,FLOAT b,FLOAT t,FLOAT zn,FLOAT zf) {
    std::memset(out,0,sizeof(*out));out->_11=2/(r-l);out->_22=2/(t-b);out->_33=1/(zn-zf);
    out->_41=-(r+l)/(r-l);out->_42=-(t+b)/(t-b);out->_43=zn/(zn-zf);out->_44=1;return out;
}
D3DXMATRIX* WINAPI D3DXMatrixPerspectiveOffCenterRH(D3DXMATRIX* out,FLOAT l,FLOAT r,FLOAT b,FLOAT t,FLOAT zn,FLOAT zf) {
    std::memset(out,0,sizeof(*out));out->_11=2*zn/(r-l);out->_22=2*zn/(t-b);
    out->_31=(r+l)/(r-l);out->_32=(t+b)/(t-b);out->_33=zf/(zn-zf);out->_34=-1;out->_43=zn*zf/(zn-zf);return out;
}
D3DXMATRIX* WINAPI D3DXMatrixPerspectiveRH(D3DXMATRIX* out,FLOAT w,FLOAT h,FLOAT zn,FLOAT zf) {
    return D3DXMatrixPerspectiveOffCenterRH(out,-w/2,w/2,-h/2,h/2,zn,zf);
}
D3DXVECTOR4* WINAPI D3DXVec4Transform(D3DXVECTOR4* out,const D3DXVECTOR4* v,const D3DXMATRIX* m) {
    D3DXVECTOR4 result;
    const float* in=&v->x;float* o=&result.x;
    for(int c=0;c<4;c++){o[c]=0;for(int k=0;k<4;k++)o[c]+=in[k]*m->m[k][c];}
    *out=result;return out;
}
D3DXVECTOR3* WINAPI D3DXVec3TransformCoord(D3DXVECTOR3* out,const D3DXVECTOR3* v,const D3DXMATRIX* m) {
    D3DXVECTOR4 in(v->x,v->y,v->z,1),value;D3DXVec4Transform(&value,&in,m);
    *out=D3DXVECTOR3(value.x/value.w,value.y/value.w,value.z/value.w);return out;
}
D3DXVECTOR4* WINAPI D3DXVec4Normalize(D3DXVECTOR4* out,const D3DXVECTOR4* v) {
    float len=std::sqrt(v->x*v->x+v->y*v->y+v->z*v->z+v->w*v->w);
    *out=len ? D3DXVECTOR4(v->x/len,v->y/len,v->z/len,v->w/len) : D3DXVECTOR4(0,0,0,0);return out;
}
D3DXPLANE* WINAPI D3DXPlaneNormalize(D3DXPLANE* out,const D3DXPLANE* p) {
    float len=std::sqrt(p->a*p->a+p->b*p->b+p->c*p->c);
    *out=len ? D3DXPLANE(p->a/len,p->b/len,p->c/len,p->d/len) : D3DXPLANE(0,0,0,0);return out;
}
D3DXPLANE* WINAPI D3DXPlaneTransform(D3DXPLANE* out,const D3DXPLANE* p,const D3DXMATRIX* m) {
    D3DXVECTOR4 in(p->a,p->b,p->c,p->d),value;D3DXVec4Transform(&value,&in,m);
    *out=D3DXPLANE(value.x,value.y,value.z,value.w);return out;
}
class SarekMatrixStack final : public ID3DXMatrixStack {
    ULONG refs=1;
    CUtlVector<D3DXMATRIX> stack;
    HRESULT transform(const D3DXMATRIX& value,bool local) {return local?MultMatrixLocal(&value):MultMatrix(&value);}
    HRESULT rotate(const D3DXVECTOR3* axis,FLOAT a,bool local) {D3DXMATRIX m;D3DXMatrixRotationAxis(&m,axis,a);return transform(m,local);}
    HRESULT ypr(FLOAT y,FLOAT p,FLOAT r,bool local) {
        D3DXMATRIX a,b,c,tmp,m;D3DXVECTOR3 x(1,0,0),yy(0,1,0),z(0,0,1);
        D3DXMatrixRotationAxis(&a,&z,r);D3DXMatrixRotationAxis(&b,&x,p);D3DXMatrixRotationAxis(&c,&yy,y);
        D3DXMatrixMultiply(&tmp,&a,&b);D3DXMatrixMultiply(&m,&tmp,&c);return transform(m,local);
    }
public:
    SarekMatrixStack(){stack.AddToTail();LoadIdentity();}
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID id,void** out) override {
        if(!out)return E_POINTER;*out=NULL;
        if(id!=IID_IUnknown && id!=IID_ID3DXMatrixStack)return E_NOINTERFACE;
        *out=static_cast<ID3DXMatrixStack*>(this);AddRef();return S_OK;
    }
    ULONG STDMETHODCALLTYPE AddRef() override {return __sync_add_and_fetch(&refs,1);}
    ULONG STDMETHODCALLTYPE Release() override {ULONG n=__sync_sub_and_fetch(&refs,1);if(!n)delete this;return n;}
    HRESULT STDMETHODCALLTYPE Pop() override {if(stack.Count()==1)return D3DERR_INVALIDCALL;stack.Remove(stack.Count()-1);return S_OK;}
    HRESULT STDMETHODCALLTYPE Push() override {D3DXMATRIX m=*GetTop();stack.AddToTail(m);return S_OK;}
    HRESULT STDMETHODCALLTYPE LoadIdentity() override {D3DXMatrixIdentity(GetTop());return S_OK;}
    HRESULT STDMETHODCALLTYPE LoadMatrix(const D3DXMATRIX* m) override {if(!m)return E_POINTER;*GetTop()=*m;return S_OK;}
    HRESULT STDMETHODCALLTYPE MultMatrix(const D3DXMATRIX* m) override {if(!m)return E_POINTER;D3DXMatrixMultiply(GetTop(),GetTop(),m);return S_OK;}
    HRESULT STDMETHODCALLTYPE MultMatrixLocal(const D3DXMATRIX* m) override {if(!m)return E_POINTER;D3DXMatrixMultiply(GetTop(),m,GetTop());return S_OK;}
    HRESULT STDMETHODCALLTYPE RotateAxis(const D3DXVECTOR3* v,FLOAT a) override {return v?rotate(v,a,false):E_POINTER;}
    HRESULT STDMETHODCALLTYPE RotateAxisLocal(const D3DXVECTOR3* v,FLOAT a) override {return v?rotate(v,a,true):E_POINTER;}
    HRESULT STDMETHODCALLTYPE RotateYawPitchRoll(FLOAT y,FLOAT p,FLOAT r) override {return ypr(y,p,r,false);}
    HRESULT STDMETHODCALLTYPE RotateYawPitchRollLocal(FLOAT y,FLOAT p,FLOAT r) override {return ypr(y,p,r,true);}
    HRESULT STDMETHODCALLTYPE Scale(FLOAT x,FLOAT y,FLOAT z) override {D3DXMATRIX m;D3DXMatrixScaling(&m,x,y,z);return transform(m,false);}
    HRESULT STDMETHODCALLTYPE ScaleLocal(FLOAT x,FLOAT y,FLOAT z) override {D3DXMATRIX m;D3DXMatrixScaling(&m,x,y,z);return transform(m,true);}
    HRESULT STDMETHODCALLTYPE Translate(FLOAT x,FLOAT y,FLOAT z) override {D3DXMATRIX m;D3DXMatrixTranslation(&m,x,y,z);return transform(m,false);}
    HRESULT STDMETHODCALLTYPE TranslateLocal(FLOAT x,FLOAT y,FLOAT z) override {D3DXMATRIX m;D3DXMatrixTranslation(&m,x,y,z);return transform(m,true);}
    D3DXMATRIX* STDMETHODCALLTYPE GetTop() override {return &stack[stack.Count()-1];}
};
HRESULT WINAPI D3DXCreateMatrixStack(DWORD,LPD3DXMATRIXSTACK* out) {
    if(!out)return E_POINTER;*out=new SarekMatrixStack;return S_OK;
}

extern "C" __attribute__((used, visibility("default"))) const char UnderhellSarekShaderAPI[] = "UNDERHELL_SAREK_SHADERAPI_V1";
