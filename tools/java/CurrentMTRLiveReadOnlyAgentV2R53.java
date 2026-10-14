import java.lang.instrument.Instrumentation;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** Reads the already loaded simulator and real forty-train journeys. No deployment. */
public final class CurrentMTRLiveReadOnlyAgentV2R53
{
    private static ClassLoader loader;
    private static Class<?> type(String n)throws Exception{return Class.forName(n,true,loader);}
    private static Object call(Object o,String n)throws Exception{return o.getClass().getMethod(n).invoke(o);}
    private static Object field(Object o,String n)throws Exception
    {for(Class<?> c=o.getClass();c!=null;c=c.getSuperclass())try{Field f=c.getDeclaredField(n);f.setAccessible(true);return f.get(o);}catch(NoSuchFieldException absent){}throw new NoSuchFieldException(n);}
    private static Object staticField(Class<?> owner,String...names)throws Exception
    {for(String n:names)try{return owner.getField(n).get(null);}catch(NoSuchFieldException absent){}throw new NoSuchFieldException(Arrays.toString(names));}
    private static Object invoke(Object o,String[] names,Class<?>[] sig,Object...args)throws Exception
    {for(String n:names)try{return o.getClass().getMethod(n,sig).invoke(o,args);}catch(NoSuchMethodException absent){}throw new NoSuchMethodException(Arrays.toString(names));}
    private static Map<String,Object> snapshot(Object server)throws Exception
    {
        var out=new LinkedHashMap<String,Object>();out.put("utc_ms",System.currentTimeMillis());out.put("world_or_simulator_written_by_observer",false);
        Class<?> resource=type("net.minecraft.world.level.storage.LevelResource");
        out.put("actual_server_world",invoke(server,new String[]{"getWorldPath","m_129843_"},new Class<?>[]{resource},staticField(resource,"ROOT","f_78182_")).toString());
        Object sim=type("com.projectseele.visual.RegionalNativeTransitInspection").getMethod("simulator").invoke(null);
        if(sim==null)throw new IllegalStateException("Actual loaded GeoFront MTR simulator absent");
        out.put("simulator_dimension",field(sim,"dimension"));var vehicles=new ArrayList<Map<String,Object>>();var ids=new HashSet<String>();
        for(Object siding:(Iterable<?>)field(sim,"sidings"))for(Object v:(Iterable<?>)field(siding,"vehicles"))
        {
            var row=new LinkedHashMap<String,Object>();String id=call(v,"getId").toString();ids.add(id);row.put("vehicle_id",id);row.put("siding_id",call(siding,"getId").toString());row.put("siding_hex_id",call(siding,"getHexId"));
            double progress=((Number)field(v,"railProgress")).doubleValue(),speed=((Number)call(v,"getSpeed")).doubleValue();row.put("rail_progress_metres",progress);row.put("speed_metres_per_ms",speed);row.put("speed_kph",speed*3600);
            row.put("on_route",call(v,"getIsOnRoute"));row.put("reversed",call(v,"getReversed"));Object head=call(v,"getHeadPosition");
            row.put("head_position",head==null?null:Map.of("x",field(head,"x"),"y",field(head,"y"),"z",field(head,"z")));
            Object extra=field(v,"vehicleExtraData");row.put("this_platform_id",call(extra,"getThisPlatformId").toString());row.put("this_route_id",call(extra,"getThisRouteId").toString());row.put("stop_index",call(extra,"getStopIndex"));
            row.put("next_stopping_ato",field(v,"nextStoppingIndexAto"));row.put("next_stopping_manual",field(v,"nextStoppingIndexManual"));
            var path=new ArrayList<Object>();for(Object p:(Iterable<?>)field(extra,"immutablePath"))path.add(p);
            int current=-1;for(int i=0;i<path.size();i++)if(progress>=((Number)call(path.get(i),"getStartDistance")).doubleValue()&&progress<((Number)call(path.get(i),"getEndDistance")).doubleValue()){current=i;break;}
            row.put("native_current_path_index",current);
            if(current>=0)
            {
                Object p=path.get(current);var segment=new LinkedHashMap<String,Object>();
                Object start=field(p,"startPosition"),end=field(p,"endPosition");
                segment.put("start",List.of(call(start,"getX"),call(start,"getY"),call(start,"getZ")));segment.put("end",List.of(call(end,"getX"),call(end,"getY"),call(end,"getZ")));segment.put("start_distance",call(p,"getStartDistance"));segment.put("end_distance",call(p,"getEndDistance"));
                segment.put("cached_raw_limit_kph",field(p,"speedLimit"));segment.put("native_effective_limit_kph",call(p,"getSpeedLimitKilometersPerHour"));segment.put("zero_limit_clamped_to_one",((Number)field(p,"speedLimit")).longValue()<=0);
                segment.put("signal_colors",call(p,"getSignalColors").toString());row.put("actual_current_segment",segment);
            }
            vehicles.add(row);
        }
        out.put("vehicles",vehicles);out.put("vehicle_count",vehicles.size());out.put("observed_vehicle_ids",ids);return out;
    }
    public static void agentmain(String argument,Instrumentation instrumentation)throws Exception
    {
        String[] a=argument.split("\\|",-1);if(a.length!=2)throw new IllegalArgumentException("output|seconds required");Path output=Path.of(a[0]).toAbsolutePath().normalize();int seconds=Integer.parseInt(a[1]);
        if(seconds<1||seconds>1800||Files.exists(output))throw new IllegalArgumentException("Fresh bounded read-only output required");
        for(Path p=output;p!=null;p=p.getParent())if(Files.exists(p.resolve("level.dat"))||Files.exists(p.resolve("session.lock")))throw new IllegalArgumentException("Observer output inside World");
        for(Class<?> c:instrumentation.getAllLoadedClasses())if(c.getName().equals("com.projectseele.ProjectSeele")){loader=c.getClassLoader();break;}if(loader==null)throw new IllegalStateException("Actual mod not loaded");
        Object server=type("net.minecraftforge.server.ServerLifecycleHooks").getMethod("getCurrentServer").invoke(null);if(server==null)throw new IllegalStateException("Actual existing server required");
        Object gson=type("com.google.gson.Gson").getConstructor().newInstance();Method json=gson.getClass().getMethod("toJson",Object.class);Files.createDirectories(output.getParent());
        Thread observer=new Thread(()->
        {
            long deadline=System.nanoTime()+seconds*1000000000L;
            while(System.nanoTime()<deadline&&!Files.exists(output.resolveSibling(output.getFileName()+".stop")))
            {
                var done=new CompletableFuture<Void>();Runnable capture=()->
                {
                    try
                    {
                        Map<String,Object> record;
                        try{record=snapshot(server);}catch(Throwable failure){while(failure instanceof InvocationTargetException&&failure.getCause()!=null)failure=failure.getCause();record=Map.of("error",failure.toString(),"utc_ms",System.currentTimeMillis());}
                        Files.writeString(output,json.invoke(gson,record)+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);done.complete(null);
                    }catch(Throwable failure){done.completeExceptionally(failure);}
                };
                try{invoke(server,new String[]{"execute","m_18707_"},new Class<?>[]{Runnable.class},capture);done.get(30,TimeUnit.SECONDS);Thread.sleep(1000);}catch(Throwable failure){break;}
            }
        },"SEELE-current-MTR-readonly-V2");observer.setDaemon(true);observer.start();
    }
}
