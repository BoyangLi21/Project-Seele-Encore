import java.lang.instrument.Instrumentation;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.function.Consumer;

/** Repair the tool camera head interpolation and replay all inputs in the same live QA JVM. */
public final class OrdinaryMotionR52CameraRepairAgent {
    public static void agentmain(String arg,Instrumentation instrumentation)throws Exception {
        if(!"ordinary-motion-r52".equals(System.getProperty("projectseele.regionalBuild")))throw new IllegalStateException("Wrong fixture JVM");
        Class<?> agent=null;for(var c:instrumentation.getAllLoadedClasses())if(c.getName().equals("OrdinaryMotionR52Agent"))agent=c;
        if(agent==null)throw new IllegalStateException("Original QA agent missing");
        final Class<?> previous=agent;
        var cameraField=agent.getDeclaredField("camera");cameraField.setAccessible(true);
        @SuppressWarnings("unchecked") var tick=(Consumer<Object[]>)System.getProperties().get("seele.ordinary.motion.r52.tick");
        System.getProperties().put("seele.ordinary.motion.r52.tick",(Consumer<Object[]>)values->{
            tick.accept(values);try{
                Object camera=cameraField.get(null);if(camera==null)return;
                float yaw=0;for(String name:new String[]{"getYRot","m_146908_"})try{yaw=((Number)camera.getClass().getMethod(name).invoke(camera)).floatValue();break;}catch(NoSuchMethodException ignored){}
                for(String name:new String[]{"setYHeadRot","m_5616_"})try{camera.getClass().getMethod(name,float.class).invoke(camera,yaw);break;}catch(NoSuchMethodException ignored){}
                for(String name:new String[]{"yHeadRotO","f_20886_"})try{camera.getClass().getField(name).setFloat(camera,yaw);break;}catch(NoSuchFieldException ignored){}
            }catch(Exception error){throw new RuntimeException(error);}
        });
        var sf=agent.getDeclaredField("server");sf.setAccessible(true);Object server=sf.get(null);
        var setup=agent.getDeclaredMethod("setup");setup.setAccessible(true);
        Path out=Path.of(System.getProperty("projectseele.ordinaryMotionOutputR52"));
        Files.writeString(out.resolve("RUNTIME_CAMERA_REPAIR.txt"),"Original detached armor stand camera requires head yaw and yHeadRotO, as the existing EvaConnectedActionReview does. First attempted input sequence had zero captured body/frames and is retained in inputs.jsonl. Replaying all three segments with corrected camera in the same JVM/flat fixture; no production class replacement or JAR change.\n");
        Runnable operation=()->{try{setup.invoke(null);}catch(Exception error){throw new RuntimeException(error);}};
        for(String name:new String[]{"execute","m_18701_"})try{server.getClass().getMethod(name,Runnable.class).invoke(server,operation);return;}catch(NoSuchMethodException ignored){}
        throw new NoSuchMethodException("Native server execute");
    }
}
