import java.lang.instrument.Instrumentation;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** Record actual loaded runtime on the server thread; never alter a task or actor. */
public final class CurrentGameplayReadOnlyAgentV2R53
{
    private static ClassLoader loader;
    private static Class<?> type(String name) throws Exception { return Class.forName(name,true,loader); }
    private static Object invoke(Object object,String[] names,Class<?>[] signature,Object... args) throws Exception
    {
        for(String name:names)try{return object.getClass().getMethod(name,signature).invoke(object,args);}
        catch(NoSuchMethodException absent){}
        throw new NoSuchMethodException(Arrays.toString(names));
    }
    private static Object call(Object object,String name) throws Exception {return invoke(object,new String[]{name},new Class<?>[0]);}
    private static Object stat(String name,String method,Class<?>[] signature,Object... args) throws Exception
    {Method target=type(name).getDeclaredMethod(method,signature);target.setAccessible(true);return target.invoke(null,args);}
    private static Map<String,Object> record(Object object,String... fields) throws Exception
    {
        var result=new LinkedHashMap<String,Object>();
        for(String field:fields){Object value=call(object,field);result.put(field,value==null?null:value.toString());}
        return result;
    }
    private static Object entity(Object level,Object id) throws Exception
    {
        if(!(id instanceof UUID))return null;
        Object actor=invoke(level,new String[]{"getEntity","m_8791_"},new Class<?>[]{UUID.class},id);
        if(actor==null)return Map.of("uuid",id.toString(),"loaded",false);
        var result=new LinkedHashMap<String,Object>();result.put("uuid",id.toString());result.put("loaded",true);
        result.put("type",actor.getClass().getName());
        result.put("position",invoke(actor,new String[]{"position","m_20182_"},new Class<?>[0]).toString());
        result.put("velocity",invoke(actor,new String[]{"getDeltaMovement","m_20184_"},new Class<?>[0]).toString());
        result.put("yaw",invoke(actor,new String[]{"getYRot","m_146908_"},new Class<?>[0]));
        result.put("pitch",invoke(actor,new String[]{"getXRot","m_146909_"},new Class<?>[0]));
        result.put("on_ground",invoke(actor,new String[]{"onGround","m_20096_"},new Class<?>[0]));
        result.put("persistent_data",call(actor,"getPersistentData").toString());
        Object vehicle=invoke(actor,new String[]{"getVehicle","m_20202_"},new Class<?>[0]);
        result.put("vehicle_uuid",vehicle==null?null:invoke(vehicle,new String[]{"getUUID","m_20148_"},new Class<?>[0]).toString());
        var passengers=new ArrayList<String>();for(Object p:(List<?>)invoke(actor,new String[]{"getPassengers","m_20197_"},new Class<?>[0]))passengers.add(invoke(p,new String[]{"getUUID","m_20148_"},new Class<?>[0]).toString());result.put("passenger_uuids",passengers);
        return result;
    }
    private static Map<String,Object> snapshot(Object server) throws Exception
    {
        Object level=null;
        for(Object candidate:(Iterable<?>)invoke(server,new String[]{"getAllLevels","m_129785_"},new Class<?>[0]))
            if(invoke(candidate,new String[]{"dimension","m_46472_"},new Class<?>[0]).toString().contains("projectseele:geofront"))level=candidate;
        if(level==null)throw new IllegalStateException("Actual GeoFront not loaded");
        Class<?> levelType=type("net.minecraft.server.level.ServerLevel");
        var report=new LinkedHashMap<String,Object>();report.put("utc_ms",System.currentTimeMillis());
        report.put("game_time",invoke(level,new String[]{"getGameTime","m_46467_"},new Class<?>[0]));
        report.put("world_written_by_observer",false);
        Field live=type("com.projectseele.world.NervRouteRuntimeR52").getDeclaredField("LIVE");live.setAccessible(true);
        Object controller=((Map<?,?>)live.get(null)).get(level);
        var originals=new ArrayList<Map<String,Object>>();report.put("original_bay_actors",originals);
        if(controller!=null)
        {
            Field ownerField=controller.getClass().getDeclaredField("owner");ownerField.setAccessible(true);Object owner=ownerField.get(controller);
            Field unitsField=owner.getClass().getDeclaredField("units");unitsField.setAccessible(true);
            for(var item:((Map<?,?>)unitsField.get(owner)).entrySet())
            {
                var row=new LinkedHashMap<String,Object>();row.put("variant",item.getKey());
                for(String part:List.of("eva","plug","npc"))row.put(part,entity(level,call(item.getValue(),part)));
                originals.add(row);
            }
        }
        report.put("route_ready",stat("com.projectseele.world.NervRouteRuntimeR52","ready",new Class<?>[]{levelType},level));
        Object saved=stat("com.projectseele.world.NervRouteRuntimeR52","state",new Class<?>[]{levelType,boolean.class},level,false);
        var ground=new ArrayList<Map<String,Object>>();report.put("ground_jobs",ground);
        if(saved!=null)
        {
            report.put("route_fault",call(saved,"fault"));
            for(Object job:(Collection<?>)call(saved,"jobs"))
            {
                var row=record(job,"phase","waiting");Object snap=call(job,"snapshot");
                row.put("snapshot",record(snap,"task","route","leg","fraction","stage","waiting","kind","directoryFingerprint"));
                Object original=call(snap,"original");row.put("original",record(original,"eva","plug","pilot","owner","variant","mission"));
                row.put("owner_data",call(job,"ownerData").toString());
                for(String part:List.of("eva","plug","pilot"))row.put(part,entity(level,call(original,part)));
                ground.add(row);
            }
        }
        boolean airReady=(boolean)stat("com.projectseele.world.NervAirTransportRuntimeR52","ready",new Class<?>[]{levelType},level);
        report.put("air_ready",airReady);if(!airReady)return report;
        report.put("air_status",stat("com.projectseele.world.NervAirTransportRuntimeR52","status",new Class<?>[]{levelType},level));
        Object air=stat("com.projectseele.world.NervAirTransportRuntimeR52","state",new Class<?>[]{levelType},level);
        report.put("air_fault",call(air,"fault"));var flights=new ArrayList<Map<String,Object>>();report.put("air_jobs",flights);
        for(Object job:(Collection<?>)call(air,"jobs"))
        {
            var row=record(job,"task","aircraft","itinerary","receiver","leg","age","phase","heldPhase","carrying","payloadTransferred","waiting");
            Object original=call(job,"original");row.put("original",record(original,"eva","plug","pilot","owner","variant"));
            row.put("aircraft_actual",entity(level,call(job,"aircraft")));row.put("eva",entity(level,call(original,"eva")));
            row.put("owner_data",call(job,"ownerData").toString());flights.add(row);
        }
        return report;
    }
    public static void agentmain(String argument,Instrumentation instrumentation) throws Exception
    {
        String[] args=argument.split("\\|",-1);if(args.length!=2)throw new IllegalArgumentException("output|seconds required");
        Path output=Path.of(args[0]).toAbsolutePath().normalize();int seconds=Integer.parseInt(args[1]);
        if(seconds<1||seconds>7200||Files.exists(output))throw new IllegalArgumentException("Fresh bounded observer required");
        for(Path at=output;at!=null;at=at.getParent())if(Files.exists(at.resolve("level.dat"))||Files.exists(at.resolve("session.lock")))
            throw new IllegalArgumentException("Observer output cannot be inside a native World");
        for(Class<?> c:instrumentation.getAllLoadedClasses())if(c.getName().equals("com.projectseele.ProjectSeele")){loader=c.getClassLoader();break;}
        if(loader==null)throw new IllegalStateException("Actual mod not loaded");
        Object server=stat("net.minecraftforge.server.ServerLifecycleHooks","getCurrentServer",new Class<?>[0]);
        if(server==null)throw new IllegalStateException("Actual existing server required");
        Files.createDirectories(output.getParent());
        Object gson=type("com.google.gson.Gson").getConstructor().newInstance();Method json=gson.getClass().getMethod("toJson",Object.class);
        Thread recorder=new Thread(()->
        {
            long deadline=System.nanoTime()+seconds*1_000_000_000L;
            while(System.nanoTime()<deadline&&!Files.exists(output.resolveSibling(output.getFileName()+".stop")))
            {
                var done=new CompletableFuture<Void>();
                Runnable capture=()->
                {
                    try{Map<String,Object> report;
                        try{report=snapshot(server);}catch(Throwable error){while(error instanceof InvocationTargetException&&error.getCause()!=null)error=error.getCause();report=Map.of("error",error.toString(),"utc_ms",System.currentTimeMillis());}
                        Files.writeString(output,json.invoke(gson,report)+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);
                        done.complete(null);
                    }catch(Throwable error){done.completeExceptionally(error);}
                };
                try{invoke(server,new String[]{"execute","m_18707_"},new Class<?>[]{Runnable.class},capture);done.get(30,TimeUnit.SECONDS);Thread.sleep(1000);}
                catch(Throwable error){break;}
            }
        },"SEELE-current-readonly-observer");recorder.setDaemon(true);recorder.start();
    }
}
