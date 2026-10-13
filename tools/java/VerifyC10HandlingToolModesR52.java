import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import java.lang.instrument.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;
import org.objectweb.asm.tree.analysis.*;

/** Standalone Unit1 handling mode: no movie handoff or first-battle transform. */
public final class VerifyC10HandlingToolModesR52 {
    static byte[] member(Path jar,String name)throws Exception {
        try(var z=new ZipFile(jar.toFile())){return z.getInputStream(z.getEntry(name+".class")).readAllBytes();}
    }
    public static void main(String[] args)throws Exception {
        if(args.length!=3)throw new IllegalArgumentException("Expected immutable JAR, client JAR, output directory");
        var p=new Properties();p.setProperty("projectseele.regionalBuild","ordinary-motion-r52");p.setProperty("projectseele.ordinaryHandlingOnlyR52","true");p.setProperty("projectseele.ordinaryHandlingC10R52","true");p.setProperty("projectseele.firstBattleThenOrdinaryR52","false");p.setProperty("projectseele.firstBattleThenHandlingR52","false");C10HandlingR52Attach.verifyTarget(p);
        System.getProperties().putAll(p);
        var constructor=Class.forName("C10HandlingR52Agent$1").getDeclaredConstructor();constructor.setAccessible(true);var transformer=(ClassFileTransformer)constructor.newInstance();
        Path out=Path.of(args[2]);Files.createDirectories(out);int methods=0;
        for(String name:List.of("net/minecraft/client/Minecraft","net/minecraft/client/renderer/GameRenderer","com/projectseele/client/render/EvaPoseGraph")){
            byte[] input=member(Path.of(name.startsWith("net/")?args[1]:args[0]),name);byte[] result=transformer.transform(null,VerifyC10HandlingToolModesR52.class.getClassLoader(),name,null,null,input);if(result==null)throw new AssertionError("Missing transform "+name);
            var node=new ClassNode();new ClassReader(result).accept(node,0);int callbacks=0;
            for(var m:node.methods){for(var i:m.instructions)if(i instanceof MethodInsnNode call&&call.owner.equals("java/util/function/Consumer")&&call.name.equals("accept"))callbacks++;if((m.access&(Opcodes.ACC_ABSTRACT|Opcodes.ACC_NATIVE))==0){new Analyzer<BasicValue>(new BasicVerifier()).analyze(node.name,m);methods++;}}
            if(callbacks<1)throw new AssertionError("No actual handling callback "+name);Files.write(out.resolve(name.substring(name.lastIndexOf('/')+1)+"_verified.class"),result);
        }
        String movie="com/projectseele/client/visual/FirstBattleR10Client";if(transformer.transform(null,VerifyC10HandlingToolModesR52.class.getClassLoader(),movie,null,null,member(Path.of(args[0]),movie))!=null)throw new AssertionError("Standalone handling touched movie");
        System.out.println("PASS standalone Unit1 handling attach mode; 3 transformed classes; "+methods+" method stacks; no first-battle transform.");
    }
}
