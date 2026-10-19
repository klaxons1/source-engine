// Executable tests of the production touch-policy/RLE code with engine services stubbed.
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <map>
#include <string>
#include <vector>
#define ARRAYSIZE(x) (int)(sizeof(x)/sizeof((x)[0]))
#define Q_snprintf std::snprintf
#define Q_strcmp std::strcmp
static void Q_strncpy(char *out, const char *in, size_t size) { std::snprintf(out,size,"%s",in); }
static void Msg(const char *fmt, ...) { va_list a; va_start(a,fmt); std::vprintf(fmt,a); va_end(a); }
#define FCVAR_ARCHIVE 128
#define TOUCH_FL_HIDE 1
#define CON_COMMAND(name, help) void name()
#define IMAGE_FORMAT_RGBA8888 0
#define round_aspect 2
struct IConVar { virtual ~IConVar() {} };
static std::map<std::string,std::string> settings;
struct ConVar : IConVar {
    std::string name;
    void (*callback)(IConVar*,const char*,float);
    ConVar(const char *n,const char *v,int,const char *,void (*cb)(IConVar*,const char*,float)=NULL) : name(n), callback(cb) {settings[n]=v;}
    int GetInt() const { return std::atoi(settings.at(name).c_str()); }
    bool GetBool() const { return settings[name] != "0"; }
    void SetValue(bool v) {settings[name]=v?"1":"0";if(callback)callback(this,"",0);}
};
struct ConVarRef {
    std::string name;
    ConVarRef(const char *n,bool) : name(n) {}
    bool IsValid() const {return settings.count(name)!=0;}
    const char *GetString() const {return settings[name].c_str();}
    void SetValue(const char *s) {settings[name]=s;}
};
struct rgba_t { unsigned char r,g,b,a; rgba_t(int R,int G,int B,int A):r(R),g(G),b(B),a(A){} };
struct IVTFTexture {
    std::vector<unsigned char> data;
    bool Init(int w,int h,int,int,int,int,int){data.resize(w*h*4);return true;}
    unsigned char *ImageData(int,int,int){return data.data();}
};
static IVTFTexture *CreateVTFTexture(){return new IVTFTexture;}
static void DestroyVTFTexture(IVTFTexture *t){delete t;}
struct CTouchButton {float x1,y1,x2,y2;int flags;std::string command;};
struct CTouchControls {
    bool initialized=true;
    int atlases=0,writes=0;
    std::map<std::string,CTouchButton> buttons;
    void AddUnderhellButtons(bool reset=false);
    void ActivateUnderhellButtons();
    void ResetUnderhellButtons();
    void UpdateUnderhellVisibility();
    CTouchButton *FindButton(const char *name){return buttons.count(name)?&buttons[name]:NULL;}
    void RemoveButton(const char *name){buttons.erase(name);}
    void AddButton(const char *n,const char *,const char *c,float x,float y,float xx,float yy,rgba_t,int,float,int flags){buttons[n]={x,y,xx,yy,flags,c};}
    void HideButton(const char *name){if(FindButton(name))buttons[name].flags|=TOUCH_FL_HIDE;}
    void ShowButton(const char *name){if(FindButton(name))buttons[name].flags&=~TOUCH_FL_HIDE;}
    void CreateAtlasTexture(){++atlases;}
    void WriteConfig(){++writes;}
};
static CTouchControls gTouch;
static ConVar touch_enable("touch_enable","0",0,"");
static ConVar touch_draw("touch_draw","0",0,"");
#include "underhell/uh_touch_controls.inl"

int main(int argc,char **argv) {
    assert(argc==2);
    assert(UH_EmbeddedTouchTexture("vgui/touch/missing")==NULL);
    for(int i=0;i<ARRAYSIZE(g_UHTouchAssets);++i){
        const UHTouchAsset &a=g_UHTouchAssets[i];
        std::string name=std::string("vgui/touch/underhell/")+a.name;
        IVTFTexture *t=UH_EmbeddedTouchTexture(name.c_str()); assert(t);
        std::ifstream f((std::string(argv[1])+"/assets/underhell/materials/"+name+".vtf").c_str(),std::ios::binary);
        std::vector<unsigned char> file((std::istreambuf_iterator<char>(f)),std::istreambuf_iterator<char>());
        assert(file.size()==80+64*64*4);
        assert(std::vector<unsigned char>(file.begin()+80,file.end())==t->data);
        DestroyVTFTexture(t);
    }
    gTouch.AddUnderhellButtons(); assert(gTouch.buttons.size()==15);
    gTouch.buttons["uh_inventory"].x1=.8f;
    gTouch.buttons["uh_inventory"].flags=TOUCH_FL_HIDE;
    gTouch.AddUnderhellButtons(); assert(gTouch.buttons.size()==15);
    assert(gTouch.buttons["uh_inventory"].x1==.8f && gTouch.buttons["uh_inventory"].flags==TOUCH_FL_HIDE);
    gTouch.buttons["custom_move"]={0,0,1,1,0,"_move"};
    uh_touch_buttons.SetValue(false);
    for(auto &b:gTouch.buttons)if(b.first!="custom_move")assert(b.second.flags&TOUCH_FL_HIDE);
    uh_touch_buttons.SetValue(true);
    for(auto &b:gTouch.buttons)if(b.first!="custom_move")assert(!(b.second.flags&TOUCH_FL_HIDE));
    uh_touch_reset();assert(gTouch.buttons.size()==16 && gTouch.buttons.count("custom_move"));
    assert(gTouch.buttons["uh_inventory"].x1==.15f);
    // First map: migrate an old disabled profile, keep custom movement/placement.
    gTouch.buttons["uh_inventory"].x1=.8f;
    touch_enable.SetValue(false); touch_draw.SetValue(false); uh_touch_buttons.SetValue(false);
    int before=gTouch.writes;
    gTouch.ActivateUnderhellButtons();
    assert(touch_enable.GetBool() && touch_draw.GetBool() && uh_touch_buttons.GetBool());
    assert(uh_touch_layout_version.GetInt()==1 && gTouch.writes==before+1);
    assert(gTouch.buttons["uh_inventory"].x1==.8f && gTouch.buttons.count("custom_move"));
    for(auto &b:gTouch.buttons)if(b.first!="custom_move")assert(!(b.second.flags&TOUCH_FL_HIDE));
    // Later maps respect a deliberate disable and never rewrite/reset the profile.
    uh_touch_buttons.SetValue(false); touch_enable.SetValue(false); touch_draw.SetValue(false);
    gTouch.ActivateUnderhellButtons();
    assert(!uh_touch_buttons.GetBool() && !touch_enable.GetBool() && !touch_draw.GetBool());
    assert(gTouch.writes==before+1);
    // Late legacy touch_removeall still gets missing actions restored at map start.
    gTouch.buttons.clear(); uh_touch_buttons.SetValue(true);
    gTouch.ActivateUnderhellButtons(); assert(gTouch.buttons.size()==15);
    settings["r_flashlightdepthtexture"]="1";
    settings["r_waterforceexpensive"]="1";
    settings["mat_motion_blur_enabled"]="1";
    uh_android_fast_toggle();assert(settings["r_flashlightdepthtexture"]=="0");
    // Manual changes made after activating the profile must not be overwritten.
    settings["r_waterforceexpensive"]="2";
    uh_android_fast_toggle();assert(settings["r_flashlightdepthtexture"]=="1");
    assert(settings["r_waterforceexpensive"]=="2" && settings["mat_motion_blur_enabled"]=="1");
    assert(!settings.count("r_shadowrendertotexture")); // Missing engine CVars safely skipped.
    std::puts("Underhell touch native policy, 15 embedded/VTF matches, layout and graphics restore: PASS");
}
