#include "sarek_native.h"
#include <cassert>
#include <cmath>
#include <random>
#include <iostream>
static void near(float x,float y,float eps=0.0001f){assert(std::fabs(x-y)<eps);}
static void identity(const D3DXMATRIX& m){for(int r=0;r<4;r++)for(int c=0;c<4;c++)near(m.m[r][c],r==c?1:0,0.002f);}
int main(){
 D3DXMATRIX a,b,c,inverse;
 D3DXMatrixTranslation(&a,2,3,4);D3DXMatrixScaling(&b,2,3,4);
 D3DXMatrixMultiply(&c,&a,&b);near(c._41,4);near(c._42,9);near(c._43,16);
 D3DXMatrixMultiply(&a,&a,&b);for(int i=0;i<16;i++)near((&a._11)[i],(&c._11)[i]);
 D3DXMatrixTranspose(&a,&a);near(a._14,4);near(a._24,9);near(a._34,16);
 D3DXMatrixTranspose(&a,&a);
 float determinant;assert(D3DXMatrixInverse(&inverse,&determinant,&a));near(determinant,24);
 D3DXMatrixMultiply(&c,&a,&inverse);identity(c);
 std::mt19937 rng(1234);std::uniform_real_distribution<float> value(-2,2);
 for(int i=0;i<1000;i++){
  for(int r=0;r<4;r++)for(int col=0;col<4;col++)a.m[r][col]=value(rng)+(r==col?8:0);
  assert(D3DXMatrixInverse(&inverse,nullptr,&a));D3DXMatrixMultiply(&c,&a,&inverse);identity(c);
  D3DXMATRIX original=a;D3DXMatrixInverse(&a,nullptr,&a);D3DXMatrixMultiply(&c,&original,&a);identity(c);
 }
 D3DXMatrixScaling(&a,0,1,1);D3DXMatrixIdentity(&inverse);
 assert(!D3DXMatrixInverse(&inverse,&determinant,&a));near(determinant,0);identity(inverse);
 D3DXVECTOR3 out,point(0,0,-1),farPoint(0,0,-100);
 D3DXMatrixPerspectiveRH(&a,2,2,1,100);D3DXVec3TransformCoord(&out,&point,&a);near(out.z,0);
 D3DXVec3TransformCoord(&out,&farPoint,&a);near(out.z,1);
 D3DXMatrixOrthoOffCenterRH(&a,-2,2,-3,3,1,100);
 point=D3DXVECTOR3(-2,-3,-1);D3DXVec3TransformCoord(&out,&point,&a);near(out.x,-1);near(out.y,-1);near(out.z,0);
 farPoint=D3DXVECTOR3(2,3,-100);D3DXVec3TransformCoord(&out,&farPoint,&a);near(out.x,1);near(out.y,1);near(out.z,1);
 D3DXVECTOR3 axis(0,0,2);D3DXMatrixRotationAxis(&a,&axis,3.14159265358979323846f/2);
 point=D3DXVECTOR3(1,0,0);D3DXVec3TransformCoord(&out,&point,&a);near(out.x,0);near(out.y,1);
 D3DXVECTOR4 v(0,0,0,0);D3DXVec4Normalize(&v,&v);near(v.x,0);near(v.w,0);
 v=D3DXVECTOR4(0,3,4,0);D3DXVec4Normalize(&v,&v);near(v.y,0.6f);near(v.z,0.8f);
 D3DXPLANE p(0,3,4,10);D3DXPlaneNormalize(&p,&p);near(p.b,.6f);near(p.c,.8f);near(p.d,2);
 ID3DXMatrixStack* stack=nullptr;assert(D3DXCreateMatrixStack(0,&stack)==S_OK);identity(*stack->GetTop());
 assert(stack->Pop()==D3DERR_INVALIDCALL);assert(stack->Push()==S_OK);
 stack->Translate(1,2,3);stack->Scale(2,2,2);near(stack->GetTop()->_41,2);near(stack->GetTop()->_42,4);
 stack->Pop();identity(*stack->GetTop());stack->Translate(1,2,3);stack->ScaleLocal(2,2,2);near(stack->GetTop()->_41,1);
 void* queried=nullptr;assert(stack->QueryInterface(IID_IUnknown,&queried)==S_OK);assert(queried==stack);
 assert(stack->Release()==1);assert(stack->Release()==0);
 assert(D3DXCreateMatrixStack(0,nullptr)==E_POINTER);
 std::cout<<"PASS: native D3DX math, 1000 inverses, aliasing, RH 0..1 depth, COM matrix stack (host allocator adapter)\n";
}
