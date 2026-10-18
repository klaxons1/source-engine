// Runtime identity for the native Underhell modules, not just APK branding.
#include "cbase.h"
#include "igamesystem.h"
#include "tier0/icommandline.h"
#include <stdlib.h>
#include "tier0/memdbgon.h"

#ifndef GIT_COMMIT_HASH
#define GIT_COMMIT_HASH "unknown-host-check"
#endif

namespace
{
void ReportUnderhellPort()
{
#ifdef CLIENT_DLL
	const char *identity = "UNDERHELL_PORT_CLIENT_V1";
	const char *gameDirectory = engine->GetGameDirectory();
#else
	const char *identity = "UNDERHELL_PORT_SERVER_V1";
	char gameDirectory[MAX_PATH];
	engine->GetGameDir( gameDirectory, sizeof( gameDirectory ) );
#endif
	const char *modLibraryPath = getenv( "APP_MOD_LIB" );
	Msg( "[Underhell] %s revision=%s game=%s APP_MOD_LIB=%s argv=%s\n",
		identity, GIT_COMMIT_HASH, gameDirectory,
		modLibraryPath ? modLibraryPath : "<unset>", CommandLine()->GetCmdLine() );
}

class CUnderhellPortStatus : public CAutoGameSystem
{
public:
	CUnderhellPortStatus() : CAutoGameSystem( "UnderhellPortStatus" ) {}
	virtual void LevelInitPostEntity() { ReportUnderhellPort(); }
};
CUnderhellPortStatus g_UnderhellPortStatus;
}

#ifdef CLIENT_DLL
CON_COMMAND( uh_client_port_status, "Show the loaded Underhell client identity and game directory" )
#else
CON_COMMAND( uh_server_port_status, "Show the loaded Underhell server identity and game directory" )
#endif
{
	ReportUnderhellPort();
}
