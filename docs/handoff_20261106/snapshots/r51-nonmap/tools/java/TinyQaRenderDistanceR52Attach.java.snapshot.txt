import com.sun.tools.attach.VirtualMachine;
import java.nio.file.*;

/** Root invokes this exact-PID options-only attach; no agent controls gameplay. */
public final class TinyQaRenderDistanceR52Attach {
    public static void main(String[] a)throws Exception {
        if(a.length!=3)throw new IllegalArgumentException("Expected exact PID, agent JAR, receipt output");
        String pid=a[0];Long.parseLong(pid);Path jar=Path.of(a[1]).toAbsolutePath().normalize(),out=Path.of(a[2]).toAbsolutePath().normalize();if(!Files.isRegularFile(jar))throw new IllegalArgumentException("Agent JAR absent");
        var vm=VirtualMachine.attach(pid);try{
            var p=vm.getSystemProperties();if(!"ordinary-motion-r52".equals(p.getProperty("projectseele.regionalBuild"))||!"true".equals(p.getProperty("projectseele.ordinaryHandlingOnlyR52"))||Boolean.parseBoolean(p.getProperty("projectseele.firstBattleThenOrdinaryR52"))||Boolean.parseBoolean(p.getProperty("projectseele.firstBattleThenHandlingR52")))throw new IllegalStateException("Wrong explicit standalone handling QA JVM");
            Path world=Path.of(p.getProperty("projectseele.ordinaryMotionWorldR52","")).toAbsolutePath().normalize();if(!world.equals(Path.of("D:/eva/artifacts/r51_nonmap_release/native_r51/game/saves/SEELE_FIRST_BATTLE_REVIEW_R10").toAbsolutePath().normalize()))throw new IllegalStateException("Declared QA world mismatch");
            vm.loadAgent(jar.toString(),"pid="+pid+"|out="+out);System.out.println("Options-only agent queued for exact PID "+pid+"; actual world/main-thread guard must publish OPTIONS_APPLIED.json.");
        }finally{vm.detach();}
    }
}
