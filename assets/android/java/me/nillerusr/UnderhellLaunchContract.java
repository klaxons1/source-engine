package me.nillerusr;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Android-independent launch policy, shared with executable regression tests. */
public final class UnderhellLaunchContract {
    public static final String GAME = "underhell";
    public static final String CLIENT_MARKER = "UNDERHELL_PORT_CLIENT_V1";
    public static final String SERVER_MARKER = "UNDERHELL_PORT_SERVER_V1";

    public static final String RENDERER_MARKER = "UNDERHELL_RENDERER_ASTC_V1";

    private UnderhellLaunchContract() {}

    private static final class Token {
        final String raw;
        final String value;
        Token(String raw, String value) { this.raw = raw; this.value = value; }
    }

    // Keep quoted values intact, using Source's whole-token double-quote syntax.
    private static List<Token> tokens(String input) {
        List<Token> result = new ArrayList<Token>();
        int i = 0;
        while (i < input.length()) {
            while (i < input.length() && Character.isWhitespace(input.charAt(i))) ++i;
            if (i == input.length()) break;
            int start = i;
            if (input.charAt(i) == '"') {
                int valueStart = ++i;
                while (i < input.length() && input.charAt(i) != '"') ++i;
                if (i == input.length()) throw new IllegalArgumentException("Unclosed command-line quote");
                result.add(new Token(input.substring(start, i + 1), input.substring(valueStart, i)));
                ++i;
            } else {
                while (i < input.length() && !Character.isWhitespace(input.charAt(i))) ++i;
                String raw = input.substring(start, i);
                result.add(new Token(raw, raw));
            }
        }
        return result;
    }

    public static String buildArguments(String input) {
        return buildArguments(input, false);
    }

    public static String buildArguments(String input, boolean astc) {
        List<Token> args = tokens(input == null ? "" : input);
        // Always non-empty: the companion must not fall back to its saved Lost Coast argv.
        StringBuilder out = new StringBuilder("-game underhell -defaultgamedir underhell");
        for (int i = 0; i < args.size(); ++i) {
            String value = args.get(i).value.toLowerCase(Locale.ROOT);
            if (value.equals("-game") || value.equals("-defaultgamedir")) {
                if (i + 1 < args.size()) {
                    String next = args.get(i + 1).value;
                    if (!next.startsWith("-") && !next.startsWith("+")) ++i;
                }
                continue;
            }
            // This switch belongs to the checkbox, never to a stale saved argv.
            if (value.equals("-uh_astc") || value.startsWith("-uh_astc=")) continue;
            if (value.startsWith("-game=") || value.startsWith("-defaultgamedir=")) continue;
            out.append(' ').append(args.get(i).raw);
        }
        if (astc) out.append(" -uh_astc");
        return out.toString();
    }

    public static void requireLibraries(String directory) throws IOException {
        if (directory == null || directory.length() == 0)
            throw new IOException("Android did not provide a native library directory");
        File root = new File(directory);
        int client = checkLibrary(new File(root, "libclient.so"), CLIENT_MARKER);
        int server = checkLibrary(new File(root, "libserver.so"), SERVER_MARKER);
        int renderer = checkLibrary(new File(root, "libshaderapidx9.so"), RENDERER_MARKER);
        if (renderer != client) throw new IOException("Underhell renderer ABI mismatch");
        if (client != server) throw new IOException("Underhell client/server ABI mismatch");
    }

    private static int checkLibrary(File library, String marker) throws IOException {
        if (!library.isFile() || !library.canRead())
            throw new IOException("Missing readable Underhell library: " + library);
        try (FileInputStream stream = new FileInputStream(library)) {
            byte[] header = new byte[64];
            int used = 0;
            while (used < header.length) {
                int count = stream.read(header, used, header.length - used);
                if (count < 0) throw new IOException("Truncated ELF library: " + library);
                used += count;
            }
            int machine = (header[18] & 255) | ((header[19] & 255) << 8);
            int elfClass = header[4] & 255;
            if (header[0] != 127 || header[1] != 'E' || header[2] != 'L' || header[3] != 'F'
                    || header[5] != 1 || !((machine == 183 && elfClass == 2) || (machine == 40 && elfClass == 1)))
                throw new IOException("Not an Android ARM/ARM64 ELF library: " + library);
            byte[] buffer = new byte[16384];
            String carry = "";
            int count;
            while ((count = stream.read(buffer)) != -1) {
                String window = carry + new String(buffer, 0, count, "ISO-8859-1");
                if (window.contains(marker)) return machine;
                carry = window.substring(Math.max(0, window.length() - marker.length() + 1));
            }
            throw new IOException("Library is not this Underhell port (missing " + marker + "): " + library);
        }
    }
}
