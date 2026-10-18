import java.io.*;
import java.nio.file.*;
import me.nillerusr.UnderhellLaunchContract;
public class UnderhellLaunchContractTest {
    static void eq(String a, String b) { if (!a.equals(b)) throw new AssertionError(a+" != "+b); }
    static byte[] elf(String marker, int machine) throws Exception {
        byte[] a=new byte[16480]; a[0]=127;a[1]='E';a[2]='L';a[3]='F';a[4]=(byte)(machine==183?2:1);a[5]=1;
        a[18]=(byte)machine;a[19]=(byte)(machine>>8);
        // Deliberately cross a streaming read boundary after the ELF header.
        byte[] m=marker.getBytes("ISO-8859-1");System.arraycopy(m,0,a,16440,m.length);return a;
    }
    public static void main(String[] argv) throws Exception {
        String base="-game underhell -defaultgamedir underhell";
        eq(UnderhellLaunchContract.buildArguments(null),base);
        eq(UnderhellLaunchContract.buildArguments(""),base);
        eq(UnderhellLaunchContract.buildArguments("-game lostcoast -console"),base+" -console");
        eq(UnderhellLaunchContract.buildArguments("-GAME \"Lost Coast\" -defaultgamedir hl2 +map uh_chapter1"),base+" +map uh_chapter1");
        eq(UnderhellLaunchContract.buildArguments("-game -console -game=lostcoast"),base+" -console");
        eq(UnderhellLaunchContract.buildArguments("+echo \"keep -game lostcoast here\""),base+" +echo \"keep -game lostcoast here\"");
        boolean bad=false;try {UnderhellLaunchContract.buildArguments("\"unclosed");}catch(IllegalArgumentException e){bad=true;}if(!bad)throw new AssertionError();
        eq(UnderhellLaunchContract.buildArguments("-console",true),base+" -console -uh_astc");
        eq(UnderhellLaunchContract.buildArguments("-uh_astc -UH_ASTC=1 -console",false),base+" -console");
        eq(UnderhellLaunchContract.buildArguments("-uh_astc -uh_astc=0",true),base+" -uh_astc");
        File root=Files.createTempDirectory("underhell-java").toFile();
        File c=new File(root,"libclient.so"),s=new File(root,"libserver.so"),r=new File(root,"libshaderapidx9.so");
        try {
            bad=false;try{UnderhellLaunchContract.requireLibraries(root.toString());}catch(IOException e){bad=true;}if(!bad)throw new AssertionError();
            Files.write(c.toPath(),elf(UnderhellLaunchContract.CLIENT_MARKER,183));
            Files.write(s.toPath(),elf(UnderhellLaunchContract.SERVER_MARKER,183));
            Files.write(r.toPath(),elf(UnderhellLaunchContract.RENDERER_MARKER,183));
            UnderhellLaunchContract.requireLibraries(root.toString());
            Files.write(s.toPath(),elf("stock module",183));
            bad=false;try{UnderhellLaunchContract.requireLibraries(root.toString());}catch(IOException e){bad=true;}if(!bad)throw new AssertionError();
            Files.write(s.toPath(),elf(UnderhellLaunchContract.SERVER_MARKER,40));
            bad=false;try{UnderhellLaunchContract.requireLibraries(root.toString());}catch(IOException e){bad=true;}if(!bad)throw new AssertionError();
        } finally {c.delete();s.delete();r.delete();root.delete();}
        System.out.println("Launch contract Java tests passed");
    }
}
