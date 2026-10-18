package me.nillerusr;

import org.libsdl.app.SDLActivity;
import android.content.*;
import android.content.pm.ApplicationInfo;
import android.graphics.Point;
import android.os.*;
import android.widget.Toast;
import java.io.*;
import java.util.*;

/** Own UID + isolated GPU process. The external GLES companion path is unchanged. */
public final class UnderhellSarekActivity extends SDLActivity {
    private static native void configureNative(String[] keys, String[] values, int width, int height, int refreshMilliHz);
    private static native void nativeSetResumed(boolean resumed);
    @Override protected void onPause() {
        // Stop WSI access before SDL waits for the render thread's pause acknowledgement.
        if (!mBrokenLibraries) nativeSetResumed(false);
        super.onPause();
    }
    @Override protected void onResume() {
        // SDL may start its native thread in super.onResume(). Surface validity is
        // checked separately; a missing/replaced Surface is never presented to.
        if (!mBrokenLibraries) nativeSetResumed(true);
        super.onResume();
    }
    @Override protected String[] getLibraries() { return new String[] { "SDL2", "launcher_sarek" }; }
    @Override protected String getMainFunction() { return "LauncherMainAndroid"; }
    @Override protected String[] getArguments() {
        return UnderhellLaunchContract.buildArgumentArray(getIntent().getStringExtra("argv"));
    }
    @Override public void loadLibraries() {
        try {
            if (Build.VERSION.SDK_INT < 26 || !Arrays.asList(Build.SUPPORTED_ABIS).contains("arm64-v8a"))
                throw new IOException("Native Sarek requires Android 8+ and ARM64");
            String path = getIntent().getStringExtra("gamepath");
            if (path == null || !new File(path, "underhell/gameinfo.txt").isFile())
                throw new IOException("Missing exact lowercase underhell/gameinfo.txt in the configured game path");
            String own = getApplicationInfo().nativeLibraryDir;
            UnderhellLaunchContract.requireLibraries(own); // preserve client/server/GLES provenance checks
            String core = getPackageManager().getApplicationInfo("com.valvesoftware.source", 0).nativeLibraryDir;
            UnderhellGpuDrivers.Driver driver = UnderhellGpuDrivers.selected(this, getIntent().getStringExtra("driver_id"));
            if (driver != null && Build.VERSION.SDK_INT < 28) throw new IOException("Custom drivers need Android 9+");
            File temp = new File(getNoBackupFilesDir(), "vulkan-tmp");
            UnderhellDriverArchive.privateDirectory(temp);
            File ownVpk = copyAsset(this, "extras_dir.vpk", "underhell-extras.vpk");
            Context companion = createPackageContext("com.valvesoftware.source", 0);
            File baseVpk = copyAsset(companion, "extras_dir.vpk", "engine-extras.vpk");
            // SONAME preloading lets the companion core use OUR lifecycle-safe SDL.
            System.load(own + "/libhidapi.so");
            System.load(own + "/libSDL2.so");
            for (String lib : new String[] { "tier0", "vstdlib", "steam_api", "togl" })
                System.load(core + "/lib" + lib + ".so");
            System.load(own + "/libdxvk_sarek_d3d9.so");
            System.load(own + "/liblauncher_sarek.so");
            LinkedHashMap<String, String> env = new LinkedHashMap<String, String>();
            env.put("APP_DATA_PATH", getFilesDir().getAbsolutePath());
            env.put("APP_LIB_PATH", core); env.put("APP_MOD_LIB", own);
            env.put("VALVE_GAME_PATH", new File(path).getCanonicalPath());
            env.put("EXTRAS_VPK_PATH", ownVpk.getAbsolutePath() + "," + baseVpk.getAbsolutePath());
            env.put("LANG", Locale.getDefault().toString());
            env.put("UH_VK_HOOK_DIR", own); env.put("UH_VK_TMP_DIR", temp.getAbsolutePath() + "/");
            env.put("UH_VK_DRIVER_DIR", driver == null ? "" : driver.directory.getCanonicalPath() + "/");
            env.put("UH_VK_DRIVER_NAME", driver == null ? "" : driver.library);
            Point size = new Point(); getWindowManager().getDefaultDisplay().getRealSize(size);
            float refresh = getWindowManager().getDefaultDisplay().getRefreshRate();
            if (!Float.isFinite(refresh) || refresh <= 0) throw new IOException("Android returned invalid display refresh rate");
            configureNative(env.keySet().toArray(new String[env.size()]), env.values().toArray(new String[env.size()]),
                Math.max(size.x, size.y), Math.min(size.x, size.y), Math.round(refresh * 1000));
            android.util.Log.i("UnderhellVulkan", "Selected: " + (driver == null ? "system Vulkan" : driver.name)
                + "; backend=DXVK-Sarek 0c0e8f6f (device validation pending)");
        } catch (Exception e) { throw new IllegalStateException("Sarek launch refused; select GLES in the launcher. " + e, e); }
    }
    private File copyAsset(Context source, String asset, String destination) throws IOException {
        File file = new File(getFilesDir(), destination);
        File stage = new File(getFilesDir(), destination + ".tmp");
        // Always refresh on a full GPU-process launch; never keep stale touch icons/base fonts after an update.
        try (InputStream in = source.getAssets().open(asset); FileOutputStream out = new FileOutputStream(stage)) {
            byte[] buffer = new byte[32768]; int n;
            while ((n = in.read(buffer)) != -1) out.write(buffer, 0, n);
            out.getFD().sync();
        }
        if (!stage.renameTo(file)) throw new IOException("Cannot install engine VPK asset");
        return file;
    }
    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        // Never reconfigure a live Vulkan namespace/device or reuse another mod's argv.
        Toast.makeText(this, "Сначала выйдите из игры. Новые настройки GPU применятся при полном запуске.", Toast.LENGTH_LONG).show();
    }
    @Override protected void onDestroy() {
        boolean exiting = isFinishing();
        if (exiting) {
            // A broken GPU must not keep the launcher's separate process or the next SDL session hostage.
            new Thread(() -> {
                try { Thread.sleep(3000); } catch (InterruptedException ignored) {}
                android.os.Process.killProcess(android.os.Process.myPid());
            }, "SarekExitWatchdog").start();
        }
        super.onDestroy();
        if (exiting) android.os.Process.killProcess(android.os.Process.myPid());
    }
}
