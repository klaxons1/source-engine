// Included only by touch.cpp in the Underhell client.
#include "underhell/uh_touch_assets.h"

static IVTFTexture *UH_EmbeddedTouchTexture( const char *name )
{
	for ( int i = 0; i < ARRAYSIZE( g_UHTouchAssets ); ++i )
	{
		const UHTouchAsset &asset = g_UHTouchAssets[i];
		char path[128];
		Q_snprintf( path, sizeof( path ), "vgui/touch/underhell/%s", asset.name );
		if ( Q_strcmp( name, path ) ) continue;
		IVTFTexture *texture = CreateVTFTexture();
		if ( !texture->Init( 64, 64, 1, IMAGE_FORMAT_RGBA8888, 0x230c, 1, 1 ) )
		{
			DestroyVTFTexture( texture );
			return NULL;
		}
		unsigned char *pixels = texture->ImageData( 0, 0, 0 );
		int cursor = 0;
		for ( int r = 0; r < asset.count; ++r )
		{
			int count = asset.runs[r] >> 8, color = asset.runs[r] & 255;
			if ( color >= ARRAYSIZE( g_UHTouchPalette ) || cursor + count > 4096 ) break;
			for ( int n = 0; n < count; ++n, ++cursor )
				memcpy( pixels + cursor * 4, g_UHTouchPalette[color], 4 );
		}
		if ( cursor == 4096 ) return texture;
		DestroyVTFTexture( texture );
		return NULL;
	}
	return NULL;
}

static void UH_TouchVisibilityChanged( IConVar *, const char *, float )
{
	gTouch.UpdateUnderhellVisibility();
}
static ConVar uh_touch_buttons( "uh_touch_buttons", "1", FCVAR_ARCHIVE,
	"Show the Underhell action buttons (positions are editable in the touch editor)", UH_TouchVisibilityChanged );

// Stored in the touch profile as well as the engine config. Migrate AFTER startup
// configs have run, so an old touch_enable/touch_draw=0 cannot hide the new HUD.
static ConVar uh_touch_layout_version( "uh_touch_layout_version", "0", FCVAR_ARCHIVE,
	"Installed Underhell touch layout revision" );

void CTouchControls::ActivateUnderhellButtons()
{
	bool firstInstall = uh_touch_layout_version.GetInt() < 1;
	if ( firstInstall )
	{
		touch_enable.SetValue( 1 );
		touch_draw.SetValue( 1 );
		uh_touch_buttons.SetValue( 1 );
	}
	AddUnderhellButtons();
	if ( firstInstall )
	{
		for ( int i = 0; i < ARRAYSIZE( g_UHTouchAssets ); ++i )
		{
			char name[32];
			Q_snprintf( name, sizeof( name ), "uh_%s", g_UHTouchAssets[i].name );
			ShowButton( name );
		}
		uh_touch_layout_version.SetValue( 1 );
		WriteConfig();
	}
}

void CTouchControls::AddUnderhellButtons( bool reset )
{
	for ( int i = 0; i < ARRAYSIZE( g_UHTouchAssets ); ++i )
	{
		const UHTouchAsset &asset = g_UHTouchAssets[i];
		char name[32], texture[128];
		Q_snprintf( name, sizeof( name ), "uh_%s", asset.name );
		if ( reset ) RemoveButton( name );
		// Do not reset a player's existing positions, bindings, colors or hidden flags.
		if ( FindButton( name ) ) continue;
		Q_snprintf( texture, sizeof( texture ), "vgui/touch/underhell/%s", asset.name );
		AddButton( name, texture, asset.command, asset.x, asset.y, asset.x + .06f, asset.y + .10f,
			rgba_t( 255, 255, 255, 220 ), round_aspect, 1.f, uh_touch_buttons.GetBool() ? 0 : TOUCH_FL_HIDE );
	}
	if ( !uh_touch_buttons.GetBool() )
		for ( int i = 0; i < ARRAYSIZE( g_UHTouchAssets ); ++i )
		{
			char name[32];
			Q_snprintf( name, sizeof( name ), "uh_%s", g_UHTouchAssets[i].name );
			HideButton( name );
		}
}

void CTouchControls::UpdateUnderhellVisibility()
{
	if ( !initialized ) return;
	AddUnderhellButtons( false );
	for ( int i = 0; i < ARRAYSIZE( g_UHTouchAssets ); ++i )
	{
		char name[32];
		Q_snprintf( name, sizeof( name ), "uh_%s", g_UHTouchAssets[i].name );
		if ( uh_touch_buttons.GetBool() ) ShowButton( name ); else HideButton( name );
	}
	// Visibility changes do not rebuild/upload the atlas; Paint handles new textures once.
}

void CTouchControls::ResetUnderhellButtons()
{
	if ( !initialized ) return;
	AddUnderhellButtons( true );
	WriteConfig();
}

CON_COMMAND( uh_touch_reset, "Reset only Underhell action buttons; keep movement and other custom controls" )
{
	gTouch.ResetUnderhellButtons();
}

// Optional quality tradeoff, not an unmeasured claim that TOGL ES itself is fixed.
// Snapshot the actual settings and restore only values still owned by this profile.
struct UHFastSetting { const char *name, *fast; char previous[64]; bool applied; };
static UHFastSetting g_UHFastSettings[] =
{
	{ "r_flashlightdepthtexture", "0", "", false },
	{ "r_shadowrendertotexture", "0", "", false },
	{ "r_waterforceexpensive", "0", "", false },
	{ "r_waterforcereflectentities", "0", "", false },
	{ "mat_motion_blur_enabled", "0", "", false },
};
static bool g_UHFastActive = false;
static void UH_AndroidFastChanged( IConVar *variable, const char *, float )
{
	bool enable = ((ConVar *)variable)->GetBool();
	if ( enable == g_UHFastActive ) return;
	g_UHFastActive = enable;
	for ( int i = 0; i < ARRAYSIZE( g_UHFastSettings ); ++i )
	{
		UHFastSetting &setting = g_UHFastSettings[i];
		ConVarRef value( setting.name, true );
		if ( !value.IsValid() ) continue;
		if ( enable )
		{
			Q_strncpy( setting.previous, value.GetString(), sizeof( setting.previous ) );
			setting.applied = true;
			value.SetValue( setting.fast );
		}
		else if ( setting.applied )
		{
			if ( !Q_strcmp( value.GetString(), setting.fast ) ) value.SetValue( setting.previous );
			setting.applied = false;
		}
	}
	Msg( "[Underhell] Android reduced graphics load: %s (flashlight shadows, water reflections, motion blur)\n", enable ? "ON" : "OFF/restored" );
}
// Deliberately not archived: original settings must be captured in this session.
static ConVar uh_android_fast( "uh_android_fast", "0", 0,
	"Optional reduced render load: 1=on, 0=restore this session's prior settings", UH_AndroidFastChanged );
CON_COMMAND( uh_android_fast_toggle, "Toggle optional reduced graphics load; keep night vision, flashlight beam and gameplay" )
{
	uh_android_fast.SetValue( !uh_android_fast.GetBool() );
}
