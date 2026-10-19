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
    private static native int[] nativeGetSurfaceSize();
    @Override protected void pauseNativeThread() {
        // Follow SDL's actual lifecycle: multi-window Android uses onStop/onStart,
        // not onPause/onResume. Close the WSI gate before SDL's pause handshake.
        if (!mBrokenLibraries) nativeSetResumed(false);
        super.pauseNativeThread();
    }
    @Override protected void resumeNativeThread() {
        // Open the gate BEFORE SDL can start the native thread, including from
        // onStart on Android 7+. Surface validity is still checked separately.
        if (!mBrokenLibraries) nativeSetResumed(true);
        super.resumeNativeThread();
    }
    @Override protected String[] getLibraries() { return new String[] { "SDL2", "launcher_sarek" }; }
    @Override protected String getMainFunction() { return "LauncherMainAndroid"; }
    @Override protected String[] getArguments() {
        int[] surface = nativeGetSurfaceSize();
        int height = getIntent().getIntExtra("render_height", 720);
        String[] result = UnderhellLaunchContract.buildNativeArgumentArray(
            getIntent().getStringExtra("argv"), surface[0], surface[1], height, getIntent().getBooleanExtra("dx6", false));
        android.util.Log.i("UnderhellVulkan", "Surface=" + surface[0] + "x" + surface[1]
            + "; target height=" + height + "; argv=" + Arrays.toString(result));
        return result;
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
            if (getIntent().getBooleanExtra("dx6", false))
                for (String module : new String[] {"shaderapidx9_sarek_dx6", "materialsystem_sarek_dx6", "stdshader_dx6_sarek"})
                    if (!new File(own, "lib" + module + ".so").isFile())
                        throw new IOException("Incomplete DX6 APK: " + module);
            String core = getPackageManager().getApplicationInfo("com.valvesoftware.source", 0).nativeLibraryDir;
            UnderhellGpuDrivers.Driver driver = UnderhellGpuDrivers.selected(this, getIntent().getStringExtra("driver_id"));
            if (driver != null && Build.VERSION.SDK_INT < 28) throw new IOException("Custom drivers need Android 9+");
            File temp = new File(getNoBackupFilesDir(), "vulkan-tmp");
            UnderhellDriverArchive.privateDirectory(temp);
            File ownVpk = copyAsset(this, "extras_dir.vpk", "underhell-extras.vpk");
            Context companion = createPackageContext("com.valvesoftware.source", 0);
            File baseVpk = copyAsset(companion, "extras_dir.vpk", "engine-extras.vpk");
            // Font lookup in the companion core is APP_DATA_PATH/files/<name>.
            // The VPK has touch/shader assets, not these physical font files.
            for (String font : new String[] { "dejavusans.ttf", "dejavusans-bold.ttf",
                    "dejavusans-oblique.ttf", "dejavusans-boldoblique.ttf", "LiberationMono-Regular.ttf" })
                copyAsset(this, "fonts/" + font, font);
            // SONAME preloading lets the companion core use OUR lifecycle-safe SDL.
            System.load(own + "/libhidapi.so");
            System.load(own + "/libSDL2.so");
            for (String lib : new String[] { "tier0", "vstdlib", "steam_api", "togl" })
                System.load(core + "/lib" + lib + ".so");
            System.load(own + "/libdxvk_sarek_d3d9.so");
            System.load(own + "/liblauncher_sarek.so");
            LinkedHashMap<String, String> env = new LinkedHashMap<String, String>();
            env.put("APP_DATA_PATH", getApplicationInfo().dataDir);
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
        // Always refresh assets on a full GPU-process launch, including bundled fonts.
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
