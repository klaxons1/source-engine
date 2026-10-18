import me.nillerusr.UnderhellDriverArchive;
import me.nillerusr.UnderhellLaunchContract;
import java.io.*;
import java.nio.file.*;
import java.nio.file.attribute.*;
import java.util.*;
import java.util.zip.*;

public final class UnderhellDriverArchiveTest {
    static int checks;
    static void check(boolean value) { ++checks; if (!value) throw new AssertionError("check " + checks); }
    static byte[] elf() {
        byte[] b = new byte[128]; b[0]=127; b[1]='E'; b[2]='L'; b[3]='F';
        b[4]=2; b[5]=1; b[6]=1; b[16]=3; b[18]=(byte)183; return b;
    }
    static byte[] zip(String[] names, byte[][] contents) throws Exception {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        try (ZipOutputStream out = new ZipOutputStream(buffer)) {
            for (int i=0; i<names.length; ++i) {
                out.putNextEntry(new ZipEntry(names[i])); out.write(contents[i]); out.closeEntry();
            }
        }
        return buffer.toByteArray();
    }
    static File install(byte[] data, File root) throws Exception {
        return UnderhellDriverArchive.install(new ByteArrayInputStream(data), root, dir -> {
            if (!new File(dir,"meta.json").isFile()) throw new IOException("missing metadata");
            UnderhellDriverArchive.checkElf(new File(dir,"libvulkan_test.so"));
        });
    }
    static void rejected(byte[] zip, File root) throws Exception {
        int count = root.list().length;
        boolean refused = false;
        try { install(zip,root); } catch(Exception expected) { refused = true; }
        check(refused); check(root.list().length == count);
        check(!new File(root.getParentFile(),"escape.so").exists());
    }
    public static void main(String[] args) throws Exception {
        File root = Files.createTempDirectory("underhell-driver-test-").toFile();
        try {
            byte[] good = zip(new String[]{"meta.json","libvulkan_test.so"}, new byte[][]{"{}".getBytes("UTF-8"), elf()});
            File a=install(good,root), b=install(good,root);
            check(!a.equals(b)); check(a.isDirectory()); check(!a.getName().startsWith("."));
            check(new File(a,"libvulkan_test.so").length()==128);
            Set<PosixFilePermission> permissions = Files.getPosixFilePermissions(a.toPath());
            check(!permissions.contains(PosixFilePermission.OTHERS_READ));
            check(!permissions.contains(PosixFilePermission.GROUP_EXECUTE));
            check(!Files.getPosixFilePermissions(new File(a,"libvulkan_test.so").toPath()).contains(PosixFilePermission.OWNER_WRITE));
            for(String name: new String[]{"../escape.so","/escape.so","a/../../escape.so","a\\escape.so","C:/escape.so","a//x","a/./x","a/../x","\n.so",""}) {
                if(name.isEmpty()) {
                    boolean bad=false;try{UnderhellDriverArchive.safeName(name,false);}catch(IOException e){bad=true;}check(bad); continue;
                }
                rejected(zip(new String[]{name},new byte[][]{elf()}),root);
            }
            rejected(new byte[]{1,2,3},root);
            rejected(zip(new String[]{"meta.json"},new byte[][]{"{}".getBytes("UTF-8")}),root);
            byte[] arm32=elf();arm32[4]=1;arm32[18]=40;
            rejected(zip(new String[]{"libvulkan_test.so","meta.json"},new byte[][]{arm32,new byte[0]}),root);
            byte[] executable=elf();executable[16]=2;
            rejected(zip(new String[]{"libvulkan_test.so","meta.json"},new byte[][]{executable,new byte[0]}),root);
            rejected(zip(new String[]{"libvulkan_test.so"},new byte[][]{new byte[6]}),root);
            rejected(zip(new String[]{"meta.json","libvulkan_test.so"},new byte[][]{new byte[65537],elf()}),root);
            rejected(zip(new String[]{"payload/"},new byte[][]{new byte[]{42}}),root);
            rejected(zip(new String[]{"a","a/x"},new byte[][]{new byte[]{0},elf()}),root);
            String[] many=new String[257];byte[][] content=new byte[257][];
            for(int i=0;i<many.length;i++){many[i]="f"+i;content[i]=new byte[0];}
            rejected(zip(many,content),root);
            // ZIP64-independent duplicate alias: file and directory share the same canonical entry name.
            rejected(zip(new String[]{"alias","alias/"},new byte[][]{new byte[0],new byte[0]}),root);
            File[] before=root.listFiles();
            boolean stopped=false;
            try{UnderhellDriverArchive.install(new ByteArrayInputStream(good),root,dir->{throw new IOException("metadata rejects");});}
            catch(IOException expected){stopped=true;}
            check(stopped);check(root.listFiles().length==before.length);
            String[] launch=UnderhellLaunchContract.buildArgumentArray("-game lostcoast +map \"a map\" -uh_astc");
            check(Arrays.asList(launch).contains("a map"));check(!Arrays.asList(launch).contains("lostcoast"));
            check(!Arrays.asList(launch).contains("-uh_astc"));check(Arrays.asList(launch).contains("underhell"));
            StringBuilder overflow=new StringBuilder();for(int i=0;i<600;i++)overflow.append("x ");
            stopped=false;try{UnderhellLaunchContract.buildArgumentArray(overflow.toString());}catch(IllegalArgumentException e){stopped=true;}check(stopped);
            System.out.println("PASS: " + checks + " ZIP/ELF/transaction/permission/native-argv checks (no driver execution)");
        } finally { UnderhellDriverArchive.remove(root); }
    }
}
