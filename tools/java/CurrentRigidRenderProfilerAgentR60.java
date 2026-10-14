import java.lang.instrument.Instrumentation;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

/** Bounded AFTER_LEVEL reads of existing GPU counters/identities. No rendering, GL, pose or World mutation. */
public final class CurrentRigidRenderProfilerAgentR60
{
    private static ClassLoader loader;
    private static final Map<String,Class<?>> loadedTypes=new HashMap<>();
    private static final Map<String,Field> fields=new HashMap<>();
    private static Class<?> type(String name)throws Exception{return Class.forName(name,false,loader);}
    private static Object field(Object owner,String name)throws Exception
    {
        Class<?> initial=owner instanceof Class<?> c?c:owner.getClass();String key=initial.getName()+"/"+name;Field f=fields.get(key);
        if(f==null){for(Class<?> c=initial;c!=null;c=c.getSuperclass())try{f=c.getDeclaredField(name);f.setAccessible(true);break;}catch(NoSuchFieldException absent){}if(f==null)throw new NoSuchFieldException(key);fields.put(key,f);}
        return f.get(owner instanceof Class<?>?null:owner);
    }
    private static Object invoke(Object owner,String[] names,Class<?>[] signature,Object...args)throws Exception
    {for(String name:names)try{return owner.getClass().getMethod(name,signature).invoke(owner,args);}catch(NoSuchMethodException absent){}throw new NoSuchMethodException(Arrays.toString(names));}
    private static Object staticField(Class<?> owner,String...names)throws Exception
    {for(String name:names)try{return owner.getField(name).get(null);}catch(NoSuchFieldException absent){}throw new NoSuchFieldException(Arrays.toString(names));}
    private static String shortKey(Object value){String s=String.valueOf(value);return s.length()>220?s.substring(0,220):s;}
    private static void references(Object value,String path,int depth,Set<Object> identities,IdentityHashMap<Object,List<String>> owners)throws Exception
    {
        if(value==null||depth>4)return;
        if(identities.contains(value)){var row=owners.computeIfAbsent(value,k->new ArrayList<>());if(row.size()<4)row.add(path);return;}
        if(value instanceof Map<?,?> map){for(var e:map.entrySet())references(e.getValue(),path+"/"+shortKey(e.getKey()),depth+1,identities,owners);return;}
        if(value instanceof Iterable<?> list){int n=0;for(Object item:list){if(n>=20000)break;references(item,path+"["+(n++)+"]",depth+1,identities,owners);}return;}
        if(value.getClass().getName().startsWith("com.projectseele.client.render."))for(String name:List.of("parts","cells","mesh"))try{references(field(value,name),path+"."+name,depth+1,identities,owners);}catch(NoSuchFieldException absent){}
    }
    private static IdentityHashMap<Object,List<String>> owners(Set<Object> identities)throws Exception
    {
        var result=new IdentityHashMap<Object,List<String>>();Map<String,List<String>> maps=Map.of(
                "TvFacilityMeshes",List.of("PARTS","DECLARED_HATCH_PARTS","DECLARED_STACK_PARTS"),"TripoMachineryR48",List.of("CACHE"),
                "NervLowerFrameRendererR52",List.of("STATIC"),"NervServiceFootDriveRendererR52",List.of("PARTS"),
                "NervOriginalCarrierRendererR52",List.of("GUIDES"),"NervLegacyCarrierRideRendererR52",List.of("CACHE"),
                "NervFootGuideStationRendererR52",List.of("PARTS"),"NervUprightGuideRendererR52",List.of("loaded"));
        for(var e:maps.entrySet()){Class<?> c=loadedTypes.get("com.projectseele.client.render."+e.getKey());if(c==null)continue;for(String name:e.getValue())try{references(field(c,name),e.getKey()+"."+name,0,identities,result);}catch(NoSuchFieldException absent){}}
        return result;
    }
    private static long metric(Object json,String key)throws Exception
    {Object value=json.getClass().getMethod("get",String.class).invoke(json,key);return ((Number)value.getClass().getMethod("getAsLong").invoke(value)).longValue();}
    private static final class Session
    {
        final Path output;final Object bus,gson;final Method json,snapshot;final Class<?> gpu;final Object after;final int maximum;final long deadline;
        final AtomicBoolean ended=new AtomicBoolean();Consumer<Object> listener;int frames;long priorDraw=-1,priorUpload,priorNano,beginNano;
        long measuredDraws,measuredUploads,intervals;Map<String,Object> last=Map.of();
        Session(Path output,Object bus,Object gson,Method json,Class<?> gpu,Object after,int maximum,int seconds)throws Exception
        {this.output=output;this.bus=bus;this.gson=gson;this.json=json;this.gpu=gpu;this.after=after;this.maximum=maximum;deadline=System.nanoTime()+seconds*1_000_000_000L;snapshot=gpu.getMethod("snapshot");}
        synchronized void write(Map<String,Object> row)throws Exception{Files.writeString(output,json.invoke(gson,row)+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);}
        void finish(String reason)
        {
            if(!ended.compareAndSet(false,true))return;
            try{bus.getClass().getMethod("unregister",Object.class).invoke(bus,listener);}catch(Throwable ignored){}
            var summary=new LinkedHashMap<String,Object>();summary.put("state","READ_ONLY_RENDER_PROFILE_FINISHED");summary.put("reason",reason);summary.put("actual_after_level_frames",frames);summary.put("measured_intervals",intervals);summary.put("draws_in_measured_intervals",measuredDraws);summary.put("uploads_in_measured_intervals",measuredUploads);summary.put("last_render_thread_snapshot",last);summary.put("world_gl_pose_or_render_modified",false);summary.put("scope","Actual AFTER_LEVEL counter deltas and current resident identity/state references; cached_batches are not per-frame draws. Listener unregistered after completion.");
            try{write(summary);}catch(Throwable ignored){}
        }
        void event(Object event)
        {
            if(ended.get())return;
            try
            {
                if(event.getClass().getMethod("getStage").invoke(event)!=after)return;
                if(System.nanoTime()>=deadline){finish("bounded_deadline");return;}
                long started=System.nanoTime();Object data=snapshot.invoke(null);long draws=metric(data,"draw_calls"),uploads=metric(data,"uploads");
                @SuppressWarnings("unchecked")Map<Object,Map<Object,Object>> parts=(Map<Object,Map<Object,Object>>)field(gpu,"PARTS");
                var groups=new TreeMap<String,Integer>();var byPipeline=new TreeMap<String,Integer>();var identities=Collections.newSetFromMap(new IdentityHashMap<Object,Boolean>());identities.addAll(parts.keySet());
                var attributed=owners(identities);var ownerCounts=new TreeMap<String,Integer>();var largest=new ArrayList<Map<String,Object>>();int batches=0;
                for(var entry:parts.entrySet())
                {
                    Object identity=entry.getKey();List<String> paths=attributed.get(identity);String owner=paths==null?"UNATTRIBUTED_RUNTIME_IDENTITY":paths.get(0).split("[./]",2)[0];ownerCounts.merge(owner,1,Integer::sum);
                    int variants=entry.getValue().size();batches+=variants;float[] vertices=(float[])field(identity,"vertices");float[] bounds=(float[])field(identity,"bounds");
                    var top=new LinkedHashMap<String,Object>();top.put("identity",identity.getClass().getName()+"@"+Integer.toHexString(System.identityHashCode(identity)));top.put("encoded_vertices",vertices.length/11);top.put("state_variants",variants);top.put("bounds",bounds.clone());top.put("texture",String.valueOf(field(identity,"texture")));top.put("owner_cache_paths",paths==null?List.of():List.copyOf(paths));largest.add(top);
                    for(Object key:entry.getValue().keySet())
                    {
                        Object pipeline=field(key,"pipeline");String pipelineName=pipeline.getClass().getName()+"@"+Integer.toHexString(System.identityHashCode(pipeline));byPipeline.merge(pipelineName,1,Integer::sum);
                        String group="pipeline="+pipelineName+" external="+field(key,"external")+" mirror="+field(key,"mirror")+" triangles="+field(key,"triangles")+" light="+field(key,"light")+" entity="+field(key,"entity")+" blockEntity="+field(key,"blockEntity")+" item="+field(key,"item");groups.merge(group,1,Integer::sum);
                    }
                }
                largest.sort((a,b)->Integer.compare((Integer)b.get("encoded_vertices"),(Integer)a.get("encoded_vertices")));if(largest.size()>10)largest=new ArrayList<>(largest.subList(0,10));
                long now=System.nanoTime();var row=new LinkedHashMap<String,Object>();row.put("state","AFTER_LEVEL_READ_ONLY_FRAME");row.put("frame",++frames);row.put("utc_ms",System.currentTimeMillis());row.put("thread",Thread.currentThread().getName());row.put("draw_calls_total",draws);row.put("uploads_total",uploads);row.put("delta_draws",priorDraw<0?null:draws-priorDraw);row.put("delta_uploads",priorDraw<0?null:uploads-priorUpload);row.put("after_level_interval_ms",priorDraw<0?null:(now-priorNano)/1e6);row.put("snapshot_cached_batches",metric(data,"cached_batches"));row.put("resident_identity_count",parts.size());row.put("resident_state_count",batches);row.put("state_groups",groups);row.put("pipeline_groups",byPipeline);row.put("identity_owner_cache_groups",ownerCounts);row.put("top10_resident_identity_vertices",largest);row.put("read_only_profiler_cost_ms",(now-started)/1e6);row.put("world_gl_pose_or_render_modified",false);
                if(priorDraw>=0){measuredDraws+=draws-priorDraw;measuredUploads+=uploads-priorUpload;intervals++;}else beginNano=now;
                priorDraw=draws;priorUpload=uploads;priorNano=now;last=Collections.unmodifiableMap(row);write(row);if(frames>=maximum)finish("bounded_frame_count");
            }
            catch(Throwable failure){while(failure instanceof InvocationTargetException&&failure.getCause()!=null)failure=failure.getCause();try{write(Map.of("state","READ_ONLY_PROFILE_ERROR","error",failure.toString()));}catch(Throwable ignored){}finish("inspection_error");}
        }
    }
    public static void agentmain(String argument,Instrumentation instrumentation)throws Exception
    {
        String[] a=argument.split("\\|",-1);if(a.length!=3)throw new IllegalArgumentException("fresh_external_jsonl|20..60frames|1..30seconds required");Path output=Path.of(a[0]).toAbsolutePath().normalize();int frames=Integer.parseInt(a[1]),seconds=Integer.parseInt(a[2]);
        if(frames<20||frames>60||seconds<1||seconds>30||Files.exists(output))throw new IllegalArgumentException("Fresh bounded profiler required");
        for(Path p=output;p!=null;p=p.getParent())if(Files.exists(p.resolve("level.dat"))||Files.exists(p.resolve("session.lock")))throw new IllegalArgumentException("Output inside World");
        for(Class<?> c:instrumentation.getAllLoadedClasses()){loadedTypes.put(c.getName(),c);if(c.getName().equals("com.projectseele.ProjectSeele"))loader=c.getClassLoader();}if(loader==null)throw new IllegalStateException("Existing Project SEELE client required");
        Object server=type("net.minecraftforge.server.ServerLifecycleHooks").getMethod("getCurrentServer").invoke(null);Class<?> resource=type("net.minecraft.world.level.storage.LevelResource");
        Path actual=((Path)invoke(server,new String[]{"getWorldPath","m_129843_"},new Class<?>[]{resource},staticField(resource,"ROOT","f_78182_"))).toRealPath();Path expected=Path.of("D:/eva/artifacts/map_complete_20261013/WORLD").toRealPath();if(!Files.isSameFile(actual,expected))throw new IllegalStateException("Actual World mismatch");
        Files.createDirectories(output.getParent());if(output.getParent().toRealPath().startsWith(expected))throw new IllegalArgumentException("Resolved output inside World");
        Object bus=type("net.minecraftforge.common.MinecraftForge").getField("EVENT_BUS").get(null);Class<?> event=type("net.minecraftforge.client.event.RenderLevelStageEvent"),priority=type("net.minecraftforge.eventbus.api.EventPriority");Object after=type("net.minecraftforge.client.event.RenderLevelStageEvent$Stage").getField("AFTER_LEVEL").get(null);
        Object gson=type("com.google.gson.Gson").getConstructor().newInstance();Method json=gson.getClass().getMethod("toJson",Object.class);var session=new Session(output,bus,gson,json,type("com.projectseele.client.render.RigidMachineryGpuR44"),after,frames,seconds);session.listener=session::event;
        bus.getClass().getMethod("addListener",priority,boolean.class,Class.class,Consumer.class).invoke(bus,priority.getField("NORMAL").get(null),false,event,session.listener);
        session.write(Map.of("state","READ_ONLY_RENDER_LISTENER_REGISTERED","pid",ProcessHandle.current().pid(),"actual_world",actual.toString(),"maximum_frames",frames,"maximum_seconds",seconds,"world_gl_pose_or_render_modified",false));
        Thread timer=new Thread(()->{try{Thread.sleep(seconds*1000L);}catch(InterruptedException ignored){}session.finish("bounded_deadline");},"SEELE-readonly-render-profiler-deadline");timer.setDaemon(true);timer.start();
    }
}
