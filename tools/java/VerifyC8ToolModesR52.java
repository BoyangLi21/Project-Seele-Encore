import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import java.lang.instrument.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;
import org.objectweb.asm.tree.analysis.*;

/** Offline mode guards and transformed stacks; never attach or load game classes. */
public final class VerifyC8ToolModesR52 {
    static Properties mode(String mode, boolean first, boolean handling, boolean combined) {
        var p=new Properties();p.setProperty("projectseele.regionalBuild",mode);
        p.setProperty("projectseele.firstBattleThenOrdinaryR52",Boolean.toString(first));
        p.setProperty("projectseele.ordinaryHandlingOnlyR52",Boolean.toString(handling));
        p.setProperty("projectseele.firstBattleThenHandlingR52",Boolean.toString(combined));return p;
    }
    static void rejected(Properties p) {
        try {OrdinaryMotionR52Attach.verifyTarget(p);}catch(IllegalStateException expected){return;}
        throw new AssertionError("Unsafe mode accepted: "+p);
    }
    static byte[] member(Path jar,String name)throws Exception {
        try(var z=new ZipFile(jar.toFile())){return z.getInputStream(z.getEntry(name+".class")).readAllBytes();}
    }
    static int[] counts(byte[] bytes) {
        var node=new ClassNode();new ClassReader(bytes).accept(node,0);int stops=0,callbacks=0;
        for(var method:node.methods)for(var instruction:method.instructions)if(instruction instanceof MethodInsnNode call){
            if(call.owner.equals("net/minecraft/client/Minecraft")&&Set.of("m_91395_","stop").contains(call.name))stops++;
            if(call.owner.equals("java/util/function/Consumer")&&call.name.equals("accept"))callbacks++;
        }return new int[]{stops,callbacks};
    }
    public static void main(String[] args)throws Exception {
        if(args.length!=3)throw new IllegalArgumentException("Expected immutable production JAR, native client JAR, output directory");
        OrdinaryMotionR52Attach.verifyTarget(mode("ordinary-motion-r52",false,false,false));
        OrdinaryMotionR52Attach.verifyTarget(mode("ordinary-motion-r52",false,true,false));
        OrdinaryMotionR52Attach.verifyTarget(mode("r10-firstbattle",true,false,false));
        OrdinaryMotionR52Attach.verifyTarget(mode("r10-firstbattle",true,true,true));
        rejected(mode("other",true,true,true));rejected(mode("r10-firstbattle",false,false,false));
        rejected(mode("r10-firstbattle",true,true,false));rejected(mode("r10-firstbattle",true,false,true));
        rejected(mode("r10-firstbattle",false,true,true));rejected(mode("ordinary-motion-r52",true,true,true));
        System.setProperty("projectseele.regionalBuild","r10-firstbattle");
        System.setProperty("projectseele.firstBattleThenOrdinaryR52","true");
        System.setProperty("projectseele.ordinaryHandlingOnlyR52","true");
        System.setProperty("projectseele.firstBattleThenHandlingR52","true");
        var constructor=Class.forName("OrdinaryMotionR52Agent$1").getDeclaredConstructor();constructor.setAccessible(true);
        var transformer=(ClassFileTransformer)constructor.newInstance();Path out=Path.of(args[2]);Files.createDirectories(out);
        int methods=0;
        for(String name:List.of("net/minecraft/client/Minecraft","net/minecraft/client/renderer/GameRenderer","com/projectseele/client/render/EvaPoseGraph","com/projectseele/client/visual/FirstBattleR10Client")) {
            byte[] input=member(Path.of(name.startsWith("net/")?args[1]:args[0]),name);
            byte[] result=transformer.transform(null,VerifyC8ToolModesR52.class.getClassLoader(),name,null,null,input);
            if(result==null)throw new AssertionError("Missing transform: "+name);
            int[] before=counts(input),after=counts(result);
            if(after[1]<=before[1])throw new AssertionError("No callback: "+name);
            if(name.endsWith("FirstBattleR10Client")&&(before[0]!=2||after[0]!=0||after[1]-before[1]!=2))throw new AssertionError("Bad exit handoff");
            var node=new ClassNode();new ClassReader(result).accept(node,0);
            for(var method:node.methods)if((method.access&(Opcodes.ACC_ABSTRACT|Opcodes.ACC_NATIVE))==0){new Analyzer<BasicValue>(new BasicVerifier()).analyze(node.name,method);methods++;}
            Files.write(out.resolve(name.substring(name.lastIndexOf('/')+1)+"_verified.class"),result);
        }
        System.out.println("PASS: 4 allowed / 6 rejected attach modes; 4 transformed classes; "+methods+" method stacks; exact 2-stop movie handoff.");
    }
}
