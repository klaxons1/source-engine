	private Intent prepareIntent( Intent i ) throws java.io.IOException
	{
		String argv = UnderhellLaunchContract.buildArguments( cmdArgs.getText().toString() );
		String nativePath = getApplicationInfo().nativeLibraryDir;
		UnderhellLaunchContract.requireLibraries( nativePath );

		// The companion SDLActivity is singleTask and does not handle onNewIntent.
		// Never just bring an old Lost Coast/HL2 engine session back to the front.
		i.addFlags( Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK );
		saveSettings( mPref.edit() );
		i.putExtra( "argv", argv );
		i.putExtra( "gamedir", MOD_NAME );
		i.putExtra( "gamelibdir", nativePath );
		i.putExtra( "vpk", getFilesDir().getPath() + "/" + ExtractAssets.VPK_NAME );
		Log.i( "UnderhellLaunch", "gamedir=" + MOD_NAME + " gamelibdir=" + nativePath + " argv=" + argv );
		return i;
	}

	public void startSource( View view )
	{
		try
		{
			Intent intent = new Intent();
			intent.setComponent( new ComponentName( "com.valvesoftware.source", "org.libsdl.app.SDLActivity" ) );
			intent = prepareIntent( intent );
			ExtractAssets.extractAssets( this );
			startActivity( intent );
		}
		catch( Exception e )
		{
			Log.e( "UnderhellLaunch", "Underhell launch refused", e );
			new AlertDialog.Builder( this ).setTitle( "underhell" )
				.setMessage( "Cannot start the Underhell port:\n" + e.toString()
					+ "\n\nThe Source Engine companion must be installed. If an old game is still running, force-stop Source Engine and retry. No stock-library fallback was requested." )
				.setPositiveButton( android.R.string.ok, ( DialogInterface.OnClickListener ) null ).show();
		}
	}

