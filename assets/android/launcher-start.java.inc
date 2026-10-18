	private Intent prepareIntent( Intent i ) throws java.io.IOException
	{
		String argv = UnderhellLaunchContract.buildArguments( cmdArgs.getText().toString(), underhellAstc.isChecked() );
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
			if (mPref.getString("underhell_renderer", "gles").equals("sarek")) {
                // The GLES companion has its own storage grant; it does not grant
                // this UID access to the resources for the owned native runner.
                if (android.os.Build.VERSION.SDK_INT >= 23 && checkSelfPermission(android.Manifest.permission.WRITE_EXTERNAL_STORAGE)
                        != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                    requestPermissions(new String[] { android.Manifest.permission.READ_EXTERNAL_STORAGE,
                        android.Manifest.permission.WRITE_EXTERNAL_STORAGE }, 17322);
                    android.widget.Toast.makeText(this, "Разрешите доступ к ресурсам и нажмите запуск ещё раз.", android.widget.Toast.LENGTH_LONG).show();
                    return;
                }
                UnderhellLaunchContract.requireLibraries(getApplicationInfo().nativeLibraryDir);
                for (String module : new String[] { "shaderapidx9_sarek", "launcher_sarek", "dxvk_sarek_d3d9", "SDL2", "hidapi", "adrenotools", "hook_impl", "main_hook", "file_redirect_hook", "gsl_alloc_hook" })
                    if (!new java.io.File(getApplicationInfo().nativeLibraryDir, "lib" + module + ".so").isFile())
                        throw new java.io.IOException("Incomplete Sarek APK: missing " + module);
                saveSettings(mPref.edit());
                Intent nativeIntent = new Intent(this, UnderhellSarekActivity.class);
                nativeIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                nativeIntent.putExtra("argv", UnderhellLaunchContract.buildArguments(cmdArgs.getText().toString(), false));
                nativeIntent.putExtra("gamepath", mPref.getString("underhell_gamepath", "/storage/emulated/0/srceng"));
                nativeIntent.putExtra("driver_id", mPref.getString("underhell_driver", ""));
                nativeIntent.putExtra("render_height", mPref.getInt("underhell_render_height", 720));
                startActivity(nativeIntent);
                return;
            }
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

