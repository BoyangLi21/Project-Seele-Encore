import java.lang.instrument.Instrumentation;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

/** O(1) AFTER_LEVEL counters only; no resident mesh/state enumeration or render mutation. */
public final class CurrentRigidRenderSummaryAgentR60
{
    private static ClassLoader loader;
    private static Class<?> type(String name)throws Exception{return Class.forName(name,false,loader);}
    private static Field privateField(Class<?> owner,String name)throws Exception{Field f=owner.getDeclaredField(name);f.setAccessible(true);return f;}
    private static Object invoke(Object owner,String[] names,Class<?>[] signature,Object...args)throws Exception
    {for(String name:names)try{return owner.getClass().getMethod(name,signature).invoke(owner,args);}catch(NoSuchMethodException absent){}throw new NoSuchMethodException(Arrays.toString(names));}
    private static final class Session
    {
        final Path output;final Object bus,gson,after;final Method json;final Field draws,uploads,parts,vertices;final int maximum;final long deadline;
        final AtomicBoolean ended=new AtomicBoolean();Consumer<Object> listener;int frames;long previous=-1,previousUploads,previousIdentity,previousTime,totalDraws,totalUploads,firstIdentity,lastIdentity;
        Session(Path output,Object bus,Object gson,Object after,int maximum,int seconds,Class<?> gpu)throws Exception
        {this.output=output;this.bus=bus;this.gson=gson;this.after=after;this.maximum=maximum;deadline=System.nanoTime()+seconds*1_000_000_000L;json=gson.getClass().getMethod("toJson",Object.class);draws=privateField(gpu,"draws");uploads=privateField(gpu,"uploads");parts=privateField(gpu,"PARTS");vertices=privateField(gpu,"uploadedVertices");}
        synchronized void write(Map<String,Object> row)throws Exception{Files.writeString(output,json.invoke(gson,row)+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);}
        void finish(String reason)
        {if(!ended.compareAndSet(false,true))return;try{bus.getClass().getMethod("unregister",Object.class).invoke(bus,listener);}catch(Throwable ignored){}try{write(Map.of("state","LIGHT_READ_ONLY_PROFILE_FINISHED","reason",reason,"actual_frames",frames,"measured_intervals",Math.max(0,frames-1),"draws_in_intervals",totalDraws,"uploads_in_intervals",totalUploads,"first_resident_identity_count",firstIdentity,"last_resident_identity_count",lastIdentity,"world_gl_pose_or_render_modified",false));}catch(Throwable ignored){}}
        void event(Object event)
        {
            if(ended.get())return;
            try
            {
                if(event.getClass().getMethod("getStage").invoke(event)!=after)return;if(System.nanoTime()>=deadline){finish("bounded_deadline");return;}
                long begin=System.nanoTime(),d=draws.getLong(null),u=uploads.getLong(null);int identities=((Map<?,?>)parts.get(null)).size();long now=System.nanoTime();
                var row=new LinkedHashMap<String,Object>();row.put("state","LIGHT_AFTER_LEVEL_READ_ONLY_FRAME");row.put("frame",++frames);row.put("utc_ms",System.currentTimeMillis());row.put("thread",Thread.currentThread().getName());row.put("draw_calls_total",d);row.put("uploads_total",u);row.put("uploaded_vertices_total",vertices.getLong(null));row.put("resident_identity_count",identities);row.put("delta_draws",previous<0?null:d-previous);row.put("delta_uploads",previous<0?null:u-previousUploads);row.put("delta_identity_count",previous<0?null:identities-previousIdentity);row.put("after_level_interval_ms",previous<0?null:(now-previousTime)/1e6);row.put("read_only_cost_ms",(now-begin)/1e6);row.put("enumerated_resident_parts_or_states",false);row.put("world_gl_pose_or_render_modified",false);
                if(previous>=0){totalDraws+=d-previous;totalUploads+=u-previousUploads;}else firstIdentity=identities;lastIdentity=identities;previous=d;previousUploads=u;previousIdentity=identities;previousTime=now;write(row);if(frames>=maximum)finish("bounded_frame_count");
            }
            catch(Throwable failure){while(failure instanceof InvocationTargetException&&failure.getCause()!=null)failure=failure.getCause();try{write(Map.of("state","LIGHT_READ_ONLY_PROFILE_ERROR","error",failure.toString()));}catch(Throwable ignored){}finish("inspection_error");}
        }
    }
    public static void agentmain(String argument,Instrumentation instrumentation)throws Exception
    {
        String[] a=argument.split("\\|",-1);if(a.length!=3)throw new IllegalArgumentException("fresh_external_jsonl|20..60frames|1..30seconds required");Path output=Path.of(a[0]).toAbsolutePath().normalize();int frames=Integer.parseInt(a[1]),seconds=Integer.parseInt(a[2]);if(frames<20||frames>60||seconds<1||seconds>30||Files.exists(output))throw new IllegalArgumentException("Fresh bounded summary required");
        for(Path p=output;p!=null;p=p.getParent())if(Files.exists(p.resolve("level.dat"))||Files.exists(p.resolve("session.lock")))throw new IllegalArgumentException("Output inside World");
        for(Class<?> c:instrumentation.getAllLoadedClasses())if(c.getName().equals("com.projectseele.ProjectSeele")){loader=c.getClassLoader();break;}if(loader==null)throw new IllegalStateException("Actual existing Project SEELE required");
        Object server=type("net.minecraftforge.server.ServerLifecycleHooks").getMethod("getCurrentServer").invoke(null);Class<?> resource=type("net.minecraft.world.level.storage.LevelResource");Object root;try{root=resource.getField("ROOT").get(null);}catch(NoSuchFieldException missing){root=resource.getField("f_78182_").get(null);}Path actual=((Path)invoke(server,new String[]{"getWorldPath","m_129843_"},new Class<?>[]{resource},root)).toRealPath(),expected=Path.of("D:/eva/artifacts/map_complete_20261013/WORLD").toRealPath();if(!Files.isSameFile(actual,expected))throw new IllegalStateException("Actual World differs");
        Files.createDirectories(output.getParent());if(output.getParent().toRealPath().startsWith(expected))throw new IllegalArgumentException("Resolved output inside World");
        Object bus=type("net.minecraftforge.common.MinecraftForge").getField("EVENT_BUS").get(null);Class<?> event=type("net.minecraftforge.client.event.RenderLevelStageEvent"),priority=type("net.minecraftforge.eventbus.api.EventPriority");Object after=type("net.minecraftforge.client.event.RenderLevelStageEvent$Stage").getField("AFTER_LEVEL").get(null),gson=type("com.google.gson.Gson").getConstructor().newInstance();var s=new Session(output,bus,gson,after,frames,seconds,type("com.projectseele.client.render.RigidMachineryGpuR44"));s.listener=s::event;bus.getClass().getMethod("addListener",priority,boolean.class,Class.class,Consumer.class).invoke(bus,priority.getField("NORMAL").get(null),false,event,s.listener);
        s.write(Map.of("state","LIGHT_READ_ONLY_RENDER_REGISTERED","pid",ProcessHandle.current().pid(),"actual_world",actual.toString(),"maximum_frames",frames,"maximum_seconds",seconds,"world_gl_pose_or_render_modified",false));Thread timer=new Thread(()->{try{Thread.sleep(seconds*1000L);}catch(InterruptedException ignored){}s.finish("bounded_deadline");},"SEELE-light-readonly-render-summary-deadline");timer.setDaemon(true);timer.start();
    }
}
