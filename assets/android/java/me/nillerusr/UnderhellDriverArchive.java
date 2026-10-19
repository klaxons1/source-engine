package me.nillerusr;

import java.io.*;
import java.util.*;
import java.util.zip.*;

/** Bounded, transactional ZIP extraction. Never executes code from the document provider. */
public final class UnderhellDriverArchive {
    public static final long MAX_ARCHIVE = 128L * 1024 * 1024;
    public static final long MAX_TOTAL = 512L * 1024 * 1024;
    public static final long MAX_FILE = 256L * 1024 * 1024;
    public static final int MAX_ENTRIES = 256;
    public interface Validator { void validate(File directory) throws Exception; }
    private UnderhellDriverArchive() {}

    private static final class LimitedInput extends FilterInputStream {
        private long count;
        LimitedInput(InputStream in) { super(in); }
        private void add(int n) throws IOException {
            if (n > 0 && (count += n) > MAX_ARCHIVE) throw new IOException("ZIP exceeds 128 MiB");
        }
        @Override public int read() throws IOException { int n = in.read(); add(n < 0 ? 0 : 1); return n; }
        @Override public int read(byte[] b, int off, int len) throws IOException {
            int n = in.read(b, off, len); add(n); return n;
        }
        @Override public long skip(long n) throws IOException {
            byte[] b = new byte[8192]; long done = 0;
            while (done < n) { int k = read(b, 0, (int)Math.min(b.length, n - done)); if (k < 0) break; done += k; }
            return done;
        }
    }

    public static void privateDirectory(File dir) throws IOException {
        if (!dir.isDirectory() && !dir.mkdirs()) throw new IOException("Cannot create private directory");
        if (!dir.setReadable(false, false) || !dir.setWritable(false, false)
                || !dir.setExecutable(false, false) || !dir.setReadable(true, true)
                || !dir.setWritable(true, true) || !dir.setExecutable(true, true))
            throw new IOException("Cannot restrict directory permissions");
    }

    public static String safeName(String name, boolean directory) throws IOException {
        if (name == null || name.length() == 0 || name.length() > 240 || name.startsWith("/")
                || name.indexOf('\\') >= 0 || name.indexOf(':') >= 0 || name.indexOf('\0') >= 0)
            throw new IOException("Unsafe ZIP path");
        String clean = directory && name.endsWith("/") ? name.substring(0, name.length() - 1) : name;
        for (String part : clean.split("/", -1)) {
            if (part.isEmpty() || part.equals(".") || part.equals("..") || part.length() > 128)
                throw new IOException("Unsafe ZIP path");
            for (int i = 0; i < part.length(); ++i)
                if (Character.isISOControl(part.charAt(i))) throw new IOException("Control character in ZIP path");
        }
        return clean;
    }

    public static void checkElf(File file) throws IOException {
        byte[] h = new byte[64];
        try (DataInputStream in = new DataInputStream(new FileInputStream(file))) { in.readFully(h); }
        if (h[0] != 127 || h[1] != 'E' || h[2] != 'L' || h[3] != 'F'
                || h[4] != 2 || h[5] != 1 || h[6] != 1 || h[16] != 3 || h[17] != 0
                || (h[18] & 255) != 183 || h[19] != 0)
            throw new IOException("Driver must be an ELF64 little-endian AArch64 shared library: " + file.getName());
    }

    public static File install(InputStream input, File root, Validator validator) throws Exception {
        privateDirectory(root);
        File stage = new File(root, ".install-" + UUID.randomUUID());
        privateDirectory(stage);
        boolean published = false;
        try {
            Set<String> seen = new HashSet<String>();
            long total = 0; int count = 0;
            byte[] buffer = new byte[32768];
            try (ZipInputStream zip = new ZipInputStream(new LimitedInput(input))) {
                ZipEntry entry;
                while ((entry = zip.getNextEntry()) != null) {
                    if (++count > MAX_ENTRIES) throw new IOException("Too many ZIP entries");
                    String name = safeName(entry.getName(), entry.isDirectory());
                    if (!seen.add(name)) throw new IOException("Duplicate ZIP entry: " + name);
                    File file = new File(stage, name);
                    if (!file.getCanonicalPath().startsWith(stage.getCanonicalPath() + File.separator))
                        throw new IOException("ZIP path escapes installation");
                    if (entry.isDirectory()) {
                        if (zip.read() != -1) throw new IOException("Directory entry contains data");
                        privateDirectory(file); zip.closeEntry(); continue;
                    }
                    if (entry.getSize() > MAX_FILE) throw new IOException("Oversized ZIP entry");
                    privateDirectory(file.getParentFile());
                    long size = 0;
                    try (FileOutputStream out = new FileOutputStream(file)) {
                        int n;
                        while ((n = zip.read(buffer)) != -1) {
                            size += n; total += n;
                            if (size > MAX_FILE || total > MAX_TOTAL || (name.equals("meta.json") && size > 65536))
                                throw new IOException("ZIP expansion limit exceeded");
                            out.write(buffer, 0, n);
                        }
                        out.getFD().sync();
                    }
                    if (name.contains(".so")) checkElf(file);
                    if (!file.setReadable(false, false) || !file.setWritable(false, false)
                            || !file.setExecutable(false, false) || !file.setReadable(true, true))
                        throw new IOException("Cannot protect driver file");
                    zip.closeEntry(); // verifies the ZIP CRC too
                }
            }
            if (count == 0) throw new IOException("Empty or invalid ZIP");
            validator.validate(stage);
            File installed = new File(root, UUID.randomUUID().toString());
            if (!stage.renameTo(installed)) throw new IOException("Cannot publish driver installation");
            published = true;
            return installed;
        } finally { if (!published) remove(stage); }
    }

    public static void remove(File file) {
        // Used only with our freshly created staging directory, never a ZIP-supplied path.
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) for (File child : children) remove(child);
        }
        file.delete();
    }
}
