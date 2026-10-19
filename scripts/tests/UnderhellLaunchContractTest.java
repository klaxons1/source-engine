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
        int[] size = UnderhellLaunchContract.nativeRenderSize(null,2309,1080,720);
        if(size[0]!=1539 || size[1]!=720)throw new AssertionError("wrong aspect/default");
        size=UnderhellLaunchContract.nativeRenderSize(null,2309,1080,0);
        if(size[0]!=2309 || size[1]!=1080)throw new AssertionError("native size lost");
        size=UnderhellLaunchContract.nativeRenderSize("-w 1280",1920,1080,720);
        if(size[0]!=1280 || size[1]!=720)throw new AssertionError("single-width aspect");
        size=UnderhellLaunchContract.nativeRenderSize("-height 480",1920,1080,720);
        if(size[0]!=853 || size[1]!=480)throw new AssertionError("single-height aspect");
        size=UnderhellLaunchContract.nativeRenderSize("-width 800 -height 600",2309,1080,0);
        if(size[0]!=800 || size[1]!=600)throw new AssertionError("explicit dimensions changed");
        size=UnderhellLaunchContract.nativeRenderSize(null,1280,600,1080);
        if(size[0]!=1280 || size[1]!=600)throw new AssertionError("unexpected upscaling");
        String nativeArgs=String.join(" ",UnderhellLaunchContract.buildNativeArgumentArray("+echo \"keep quoted value\" -w 1280",1920,1080,720));
        if(!nativeArgs.contains("keep quoted value") || !nativeArgs.contains("-w 1280 -h 720"))throw new AssertionError(nativeArgs);
        for(String invalid:new String[]{"-w", "-w 0", "-h -1", "-width 999999999999", "-height nope", "-w 800 -w -console", "-h 720 -height"}) {
            bad=false;try{UnderhellLaunchContract.nativeRenderSize(invalid,2309,1080,720);}catch(IllegalArgumentException e){bad=true;}
            if(!bad)throw new AssertionError("invalid dimension accepted: "+invalid);
        }
        // The companion/GLES launch path remains independent of native defaults.
        if(String.join(" ",UnderhellLaunchContract.buildArgumentArray("-console")).contains("-w "))throw new AssertionError();
        String legacy=String.join(" ",UnderhellLaunchContract.buildNativeArgumentArray(
            "-dxlevel 95 -maxdxlevel 95 +mat_dxlevel 95 -uh_dx6=1 +echo \"keep quoted value\"",2309,1080,720,true));
        if(!legacy.endsWith("-uh_dx6 -dxlevel 60 -maxdxlevel 60") || legacy.contains("95") || !legacy.contains("keep quoted value"))throw new AssertionError(legacy);
        String normal=String.join(" ",UnderhellLaunchContract.buildNativeArgumentArray("-uh_dx6 -uh_dx6=1",2309,1080,720,false));
        if(normal.contains("uh_dx6") || normal.contains("-dxlevel 60"))throw new AssertionError(normal);
        if(UnderhellLaunchContract.buildArguments("-uh_dx6 -uh_dx6=1 -console").contains("uh_dx6"))throw new AssertionError("GLES leaked legacy selection");
        File root=Files.createTempDirectory("underhell-java").toFile();
        File c=new File(root,"libclient.so"),s=new File(root,"libserver.so"),r=new File(root,"libshaderapidx9.so");
        try {
            bad=false;try{UnderhellLaunchContract.requireLibraries(root.toString());}catch(IOException e){bad=true;}if(!bad)throw new AssertionError();
            Files.write(c.toPath(),elf(UnderhellLaunchContract.CLIENT_MARKER,183));
            Files.write(s.toPath(),elf(UnderhellLaunchContract.SERVER_MARKER,183));
            bad=false;try{UnderhellLaunchContract.requireLibraries(root.toString());}catch(IOException e){bad=true;}if(!bad)throw new AssertionError("missing renderer accepted");
            Files.write(r.toPath(),elf("stock renderer",183));
            bad=false;try{UnderhellLaunchContract.requireLibraries(root.toString());}catch(IOException e){bad=true;}if(!bad)throw new AssertionError("stock renderer accepted");
            Files.write(r.toPath(),elf(UnderhellLaunchContract.RENDERER_MARKER,40));
            bad=false;try{UnderhellLaunchContract.requireLibraries(root.toString());}catch(IOException e){bad=true;}if(!bad)throw new AssertionError("wrong renderer ABI accepted");
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
