#pragma once
#include "tier0/platform.h"
#include "tier0/basetypes.h"
// Source's POSIX HMODULE is uintptr-sized; native headers use a pointer handle.
#define HMODULE SarekNativeModule
#include <d3d9.h>
#undef HMODULE
#define __D3DX9_H__
#include <d3dx9math.h>
#undef __D3DX9_H__
typedef HWND VD3DHWND;
typedef HANDLE VD3DHANDLE;
#define GLMPRINTF(args)
#define GLMPRINTSTR(args)
#define GLMPRINTTEXT(args)
struct ID3DXBuffer : IUnknown {
    virtual void* GetBufferPointer() = 0;
    virtual DWORD GetBufferSize() = 0;
};
typedef ID3DXBuffer* LPD3DXBUFFER;
inline DWORD D3DXGetShaderVersion(const DWORD* code) { return code ? code[0] : 0; }

#undef ZeroMemory
#include <SDL.h>
inline BOOL GetClientRect(HWND w, RECT* r) {
    if (!w || !r) return FALSE;
    int x, y; SDL_GetWindowSize(static_cast<SDL_Window*>(w), &x, &y);
    *r = {0, 0, x, y}; return TRUE;
}
