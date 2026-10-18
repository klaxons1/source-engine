package me.nillerusr;

import android.content.Context;
import android.os.Build;
import org.json.JSONObject;
import java.io.*;
import java.util.*;

/** Driver directories belong to THIS APK's UID; never pass them to the companion. */
public final class UnderhellGpuDrivers {
    public static final String SYSTEM = "";
    public static final class Driver {
        public final String id, name, library;
        public final File directory;
        Driver(String id, String name, String library, File directory) {
            this.id = id; this.name = name; this.library = library; this.directory = directory;
        }
        @Override public String toString() { return name; }
    }
    private UnderhellGpuDrivers() {}
    public static File root(Context context) throws IOException {
        // Older launcher versions made dataDir world-writable for VPK sharing.
        // Restore traversal-only access BEFORE installing any native code.
        File data = new File(context.getApplicationInfo().dataDir).getCanonicalFile();
        File files = context.getFilesDir();
        File noBackup = context.getNoBackupFilesDir();
        // An older world's-writable directory must not leave predictable VPK
        // staging paths writable, or allow a planted symlink to redirect storage.
        if (!files.getCanonicalFile().equals(new File(data, "files"))
                || !noBackup.getCanonicalFile().equals(new File(data, "no_backup")))
            throw new IOException("Unexpected/symlinked private application storage");
        for (File directory : new File[] { data, files }) {
            if (!directory.setWritable(false, false) || !directory.setWritable(true, true))
                throw new IOException("Cannot protect the application's data directories");
        }
        File root = new File(noBackup, "gpu-drivers");
        UnderhellDriverArchive.privateDirectory(noBackup);
        if (!root.getCanonicalFile().equals(new File(noBackup.getCanonicalFile(), "gpu-drivers")))
            throw new IOException("Symlinked GPU driver storage refused");
        UnderhellDriverArchive.privateDirectory(root);
        return root;
    }
    public static Driver read(File dir) throws Exception {
        String id = dir.getName();
        File meta = new File(dir, "meta.json");
        if (!meta.isFile() || meta.length() > 65536) throw new IOException("ZIP needs root meta.json (max 64 KiB)");
        ByteArrayOutputStream data = new ByteArrayOutputStream();
        try (InputStream in = new FileInputStream(meta)) {
            byte[] buffer = new byte[4096]; int n;
            while ((n = in.read(buffer)) != -1) {
                if (data.size() + n > 65536) throw new IOException("Oversized meta.json");
                data.write(buffer, 0, n);
            }
        }
        JSONObject json = new JSONObject(new String(data.toByteArray(), "UTF-8"));
        String library = json.getString("libraryName");
        if (!library.equals(UnderhellDriverArchive.safeName(library, false)) || library.contains("/")
                || !library.matches("[A-Za-z0-9_][A-Za-z0-9_.+-]*\\.so"))
            throw new IOException("meta.json libraryName must be a root *.so filename");
        int minApi = json.getInt("minApi");
        if (minApi < 1 || minApi > Build.VERSION.SDK_INT)
            throw new IOException("Driver requires Android API " + minApi + ", device API " + Build.VERSION.SDK_INT);
        String name = json.getString("name");
        if (name.trim().isEmpty() || name.length() > 160) throw new IOException("Invalid driver name");
        for (int i = 0; i < name.length(); ++i)
            if (Character.isISOControl(name.charAt(i))) throw new IOException("Invalid driver name");
        UnderhellDriverArchive.checkElf(new File(dir, library));
        return new Driver(id, name, library, dir);
    }
    public static Driver selected(Context context, String id) throws Exception {
        File storage = root(context); // restore private permissions even for system Vulkan
        if (id == null || id.isEmpty()) return null;
        if (!id.matches("[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}"))
            throw new IOException("Invalid installed driver identifier");
        return read(new File(storage, id));
    }
    public static List<Driver> installed(Context context) throws Exception {
        List<Driver> result = new ArrayList<Driver>();
        result.add(new Driver(SYSTEM, "Системный Vulkan", "", null));
        File[] files = root(context).listFiles();
        if (files != null) for (File dir : files) {
            if (!dir.isDirectory() || dir.getName().startsWith(".")) continue;
            try { result.add(selected(context, dir.getName())); }
            catch (Exception e) { android.util.Log.w("UnderhellVulkan", "Invalid installed driver: " + dir.getName(), e); }
        }
        return result;
    }
}
