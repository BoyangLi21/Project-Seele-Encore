import java.lang.instrument.Instrumentation;
import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** Opt-in R10 fixture options only. No transformations, entity or motion writes. */
public final class TinyQaRenderDistanceR52Agent {
    private static final Path WORLD=Path.of("D:/eva/artifacts/r51_nonmap_release/native_r51/game/saves/SEELE_FIRST_BATTLE_REVIEW_R10").toAbsolutePath().normalize();
    private static final Path CAPTURE=Path.of("C:/Users/liboy/.codex/worktrees/r51-nonmap/eva/artifacts/r52_native_handling_candidate9_retry1").toAbsolutePath().normalize();
    private static final ScheduledExecutorService RETRY=Executors.newSingleThreadScheduledExecutor(r->{var t=new Thread(r,"r52-qa-rd8-options-only");t.setDaemon(true);return t;});
    private static boolean attempted;private static long expectedPid,started;private static Path out;private static Object mc;private static volatile boolean done,queued;
    static void check(boolean value,String reason){if(!value)throw new IllegalStateException(reason);}
    static Method returns(Class<?> type,String result,int parameters)throws Exception {
        for(var m:type.getMethods())if(m.getReturnType().getName().equals(result)&&m.getParameterCount()==parameters)return m;
        throw new NoSuchMethodException(type.getName()+" -> "+result+"/"+parameters);
    }
    static Method named(Class<?> type,String[] names,Class<?>...args)throws Exception {
        for(String n:names)try{return type.getMethod(n,args);}catch(NoSuchMethodException ignored){}
        throw new NoSuchMethodException(type.getName()+" "+Arrays.toString(names));
    }
    static Field namedField(Class<?> type,String...names)throws Exception {
        for(String n:names)try{return type.getField(n);}catch(NoSuchFieldException ignored){}
        throw new NoSuchFieldException(type.getName()+" "+Arrays.toString(names));
    }
    static void guard(){
        check(ProcessHandle.current().pid()==expectedPid,"Wrong exact PID");
        check("ordinary-motion-r52".equals(System.getProperty("projectseele.regionalBuild")),"Wrong QA mode");
        check("true".equals(System.getProperty("projectseele.ordinaryHandlingOnlyR52")),"Not handling-only QA");
        check(!Boolean.getBoolean("projectseele.firstBattleThenOrdinaryR52")&&!Boolean.getBoolean("projectseele.firstBattleThenHandlingR52"),"Movie mode refused");
        check(WORLD.equals(Path.of(System.getProperty("projectseele.ordinaryMotionWorldR52","")).toAbsolutePath().normalize()),"Declared world mismatch");
        check(CAPTURE.resolve("ordinary").equals(Path.of(System.getProperty("projectseele.ordinaryMotionOutputR52","")).toAbsolutePath().normalize()),"Wrong exact capture");
    }
    public static void agentmain(String arguments,Instrumentation instrumentation)throws Exception {
        check(!attempted,"Already attempted; keep evidence");attempted=true;
        var values=new HashMap<String,String>();for(String arg:arguments.split("\\|")){int i=arg.indexOf('=');check(i>0&&values.put(arg.substring(0,i),arg.substring(i+1))==null,"Malformed argument");}
        check(values.keySet().equals(Set.of("pid","out")),"Unexpected arguments");expectedPid=Long.parseLong(values.get("pid"));out=Path.of(values.get("out")).toAbsolutePath().normalize();check(out.equals(CAPTURE.resolve("rd8_adjustment")),"Wrong exact receipt directory");guard();
        Files.createDirectories(out);check(!Files.exists(out.resolve("OPTIONS_APPLIED.json"))&&!Files.exists(out.resolve("FAILURE.json")),"Prior result exists");started=System.nanoTime();
        Class<?> mcClass=null;for(var c:instrumentation.getAllLoadedClasses())if(c.getName().equals("net.minecraft.client.Minecraft")){mcClass=c;break;}check(mcClass!=null,"Minecraft not loaded");
        mc=returns(mcClass,"net.minecraft.client.Minecraft",0).invoke(null);check(mc!=null,"Minecraft singleton unavailable");
        RETRY.scheduleAtFixedRate(TinyQaRenderDistanceR52Agent::queue,0,1,TimeUnit.SECONDS);
    }
    static void queue(){
        if(done||queued)return;if(System.nanoTime()-started>600_000_000_000L){failure(new IllegalStateException("Actual R10 integrated world not ready within 600s"));return;}
        try{queued=true;named(mc.getClass(),new String[]{"execute"},Runnable.class).invoke(mc,(Runnable)TinyQaRenderDistanceR52Agent::apply);}catch(Throwable e){queued=false;failure(e);}
    }
    static void apply(){
        try{
            guard();check(Thread.currentThread().getName().equals("Render thread"),"Not client main/render thread");
            ClassLoader loader=mc.getClass().getClassLoader();Class<?> renderSystem=Class.forName("com.mojang.blaze3d.systems.RenderSystem",false,loader);check((Boolean)renderSystem.getMethod("isOnRenderThread").invoke(null),"RenderSystem thread guard failed");
            Object server=returns(mc.getClass(),"net.minecraft.client.server.IntegratedServer",0).invoke(mc);if(server==null)return;
            Class<?> resource=Class.forName("net.minecraft.world.level.storage.LevelResource",false,loader);Object root=null;
            for(var f:resource.getFields())if(f.getType()==resource){Object value=f.get(null);for(var m:resource.getMethods())if(m.getParameterCount()==0&&m.getReturnType()==String.class&&".".equals(m.invoke(value)))root=value;}
            check(root!=null,"World root resource absent");Path observed=((Path)returns(server.getClass(),"java.nio.file.Path",1).invoke(server,root)).toAbsolutePath().normalize();check(observed.equals(WORLD),"Actual world mismatch: "+observed);
            Object options=namedField(mc.getClass(),"options","f_91066_").get(mc);
            Object distance=named(options.getClass(),new String[]{"renderDistance","m_231984_"}).invoke(options);Method get=named(distance.getClass(),new String[]{"get","m_231551_"});Method set=named(distance.getClass(),new String[]{"set","m_231514_"},Object.class);
            int before=((Number)get.invoke(distance)).intValue();Field pause=namedField(options.getClass(),"pauseOnLostFocus","f_92126_");boolean pauseBefore=pause.getBoolean(options);
            check(before==24||before==8,"Unexpected existing distance "+before);
            set.invoke(distance,Integer.valueOf(8));pause.setBoolean(options,false);int after=((Number)get.invoke(distance)).intValue();check(after==8&&!pause.getBoolean(options),"Options did not converge");
            done=true;String json="{\n  \"passed\":true,\n  \"pid\":"+expectedPid+",\n  \"actual_world\":\""+escape(observed.toString())+"\",\n  \"thread\":\""+escape(Thread.currentThread().getName())+"\",\n  \"render_thread_guard\":true,\n  \"before_render_distance\":"+before+",\n  \"after_render_distance\":"+after+",\n  \"before_pause_on_lost_focus\":"+pauseBefore+",\n  \"after_pause_on_lost_focus\":false,\n  \"production_jar_modified\":false,\n  \"entity_motion_clock_written\":false,\n  \"world_written\":false,\n  \"options_file_written_by_agent\":false,\n  \"original_options_restoration_owned_by_runner\":true\n}\n";
            Files.writeString(out.resolve("OPTIONS_APPLIED.json"),json,StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW);RETRY.shutdown();
        }catch(Throwable e){failure(e);}finally{queued=false;}
    }
    static String escape(String s){return s.replace("\\","\\\\").replace("\"","\\\"").replace("\r","\\r").replace("\n","\\n");}
    static void failure(Throwable e){done=true;RETRY.shutdown();try{Files.writeString(out.resolve("FAILURE.json"),"{\"passed\":false,\"pid\":"+expectedPid+",\"error\":\""+escape(e.toString())+"\",\"world_written\":false,\"production_jar_modified\":false}\n",StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW);}catch(Throwable ignored){}}
}
