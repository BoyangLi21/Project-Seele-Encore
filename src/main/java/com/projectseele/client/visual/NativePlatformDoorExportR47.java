package com.projectseele.client.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;
import java.util.function.Consumer;

/** Passive measurement of actual stopped native trains. No boarding or simulation writes. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class NativePlatformDoorExportR47
{
    private static final String TARGET=System.getProperty("projectseele.exportPlatformDoorsR47","");
    private static final JsonArray STOPS=new JsonArray();
    private static final Set<String> SEEN=new HashSet<>();
    private static final Map<String,JsonObject> RESOURCES=new LinkedHashMap<>();
    private static final Set<String> REPORTED_ERRORS=new HashSet<>();
    private static int ticks;
    private static boolean diagnosticsChanged;
    private record Resource(Object cache,JsonObject details){}
    private static final class ResourceWaiting extends Exception
    {
        private final JsonObject details;
        private ResourceWaiting(JsonObject details){super(details.toString());this.details=details;}
    }
    private static Object call(Object value,String name)throws Exception{return value.getClass().getMethod(name).invoke(value);}
    private static double number(Object value,String name)throws Exception{return ((Number)call(value,name)).doubleValue();}
    private static double railProgress(Object vehicle,Object persistent)throws Exception
    {
        for(Object source:new Object[]{vehicle,persistent})
        {
            try{return number(source,"getRailProgress");}catch(NoSuchMethodException ignored){}
            for(Class<?> type=source.getClass();type!=null;type=type.getSuperclass())
            {
                try{var field=type.getDeclaredField("railProgress");field.setAccessible(true);return ((Number)field.get(source)).doubleValue();}
                catch(NoSuchFieldException ignored){}
            }
        }
        throw new IllegalStateException("Actual native rail progress unavailable");
    }
    private static JsonArray xyz(Object vector)throws Exception
    {var result=new JsonArray();for(String axis:new String[]{"x","y","z"}){double value=vector.getClass().getField(axis).getDouble(vector);if(!Double.isFinite(value))throw new IllegalStateException("Non-finite actual native vector axis "+axis);result.add(value);}return result;}
    private static Resource resource(Object car,int ordinal,int count)throws Exception
    {
        String id=(String)call(car,"getVehicleId");
        var detail=new JsonObject();detail.addProperty("vehicle_resource",id);detail.addProperty("ordinal",ordinal);detail.addProperty("car_count",count);detail.addProperty("cache_force",false);
        Class<?> mode=Class.forName("org.mtr.core.data.TransportMode");Object train=mode.getField("TRAIN").get(null);Object[] found={null};boolean[] callback={false};
        Class<?> loader=Class.forName("org.mtr.mod.client.CustomResourceLoader");
        // Inspect only this requested native id and current TRAIN cache count.
        // A resource-pack reload can temporarily empty/repopulate this cache.
        try
        {
            var field=loader.getDeclaredField("VEHICLES_CACHE");field.setAccessible(true);
            Object values=((Map<?,?>)field.get(null)).get(train);
            if(values instanceof Map<?,?> registered)
            {detail.addProperty("registered_train_resource_count",registered.size());detail.addProperty("registered_in_train_cache",registered.containsKey(id));}
        }
        catch(ReflectiveOperationException error){detail.addProperty("registry_cache_probe",error.getClass().getSimpleName());}
        Consumer<Object> accept=pair->{callback[0]=true;try{found[0]=call(pair,"left");}catch(Exception e){throw new IllegalStateException(e);}};
        loader.getMethod("getVehicleById",mode,String.class,Consumer.class).invoke(null,train,id,accept);
        detail.addProperty("callback_invoked",callback[0]);
        if(found[0]==null)
        {
            detail.addProperty("resource_state",detail.has("registered_train_resource_count")&&detail.get("registered_train_resource_count").getAsInt()==0?"TRAIN_RESOURCE_LIST_NOT_READY":"REQUESTED_ID_ABSENT_FROM_CURRENT_TRAIN_CACHE");
            throw new ResourceWaiting(detail);
        }
        detail.addProperty("resolved_vehicle_resource",(String)call(found[0],"getId"));
        // Same non-forced cache request as MTR's actual vehicle renderer.
        Object cache;
        try{cache=found[0].getClass().getMethod("getCachedVehicleResource",int.class,int.class,boolean.class).invoke(found[0],ordinal,count,false);}
        catch(Exception error){detail.addProperty("resource_state","REGISTERED_NATIVE_CACHE_LOAD_ERROR");detail.addProperty("native_error",String.valueOf(error.getCause()==null?error:error.getCause()));throw new ResourceWaiting(detail);}
        if(cache==null){detail.addProperty("resource_state","REGISTERED_NATIVE_MODEL_CACHE_PENDING");throw new ResourceWaiting(detail);}
        detail.addProperty("resource_state","READY");detail.addProperty("native_cache_class",cache.getClass().getName());
        return new Resource(cache,detail);
    }
    private static Object body(Object vehicle,Object car,int ordinal)throws Exception
    {
        Class<?> vector=Class.forName("org.mtr.core.tool.Vector"),frame=Class.forName("org.mtr.mod.render.PositionAndRotation"),list=Class.forName("org.mtr.libraries.it.unimi.dsi.fastutil.objects.ObjectArrayList");
        var positions=(List<?>)call(vehicle,"getVehicleCarsAndPositions");var frames=new ArrayList<Object>();
        for(Object bogies:(Iterable<?>)call(positions.get(ordinal),"right"))frames.add(frame.getConstructor(vector,vector,boolean.class).newInstance(call(bogies,"left"),call(bogies,"right"),true));
        return frame.getConstructor(list,Class.forName("org.mtr.core.data.VehicleCar"),boolean.class).newInstance(list.getConstructor(Collection.class).newInstance(frames),car,true);
    }
    private static JsonObject car(Object vehicle,Object car,int ordinal,int count)throws Exception
    {
        Resource resource=resource(car,ordinal,count);Object cache=resource.cache();
        Object frame=body(vehicle,car,ordinal),position=frame.getClass().getField("position").get(frame);
        double yaw=frame.getClass().getField("yaw").getDouble(frame),c=Math.cos(yaw),s=Math.sin(yaw);
        if(!Double.isFinite(yaw))throw new IllegalStateException("Non-finite actual native car yaw");
        var row=new JsonObject();row.addProperty("ordinal",ordinal);row.addProperty("vehicle_resource",(String)call(car,"getVehicleId"));row.addProperty("length",number(car,"getLength"));row.addProperty("yaw_radians",yaw);row.add("native_body_position",xyz(position));
        var doors=new JsonArray();
        for(Object box:(Iterable<?>)cache.getClass().getField("doorways").get(cache))
        {
            double x=(number(box,"getMinXMapped")+number(box,"getMaxXMapped"))/2,z=(number(box,"getMinZMapped")+number(box,"getMaxZMapped"))/2,inner=x-Math.signum(x)*.4,floorY=Double.NEGATIVE_INFINITY;
            for(Object floor:(Iterable<?>)cache.getClass().getField("floors").get(cache))
                if(inner>=number(floor,"getMinXMapped")-.05&&inner<=number(floor,"getMaxXMapped")+.05&&z>=number(floor,"getMinZMapped")-.05&&z<=number(floor,"getMaxZMapped")+.05)floorY=Math.max(floorY,number(floor,"getMaxYMapped"));
            if(!Double.isFinite(floorY)){resource.details().addProperty("resource_state","READY_NATIVE_DOORWAY_WITHOUT_MATCHING_FLOOR");resource.details().addProperty("door_local_x",x);resource.details().addProperty("door_local_z",z);throw new ResourceWaiting(resource.details());}
            var door=new JsonObject();var world=new JsonArray();world.add(position.getClass().getField("x").getDouble(position)+x*c+z*s);world.add(position.getClass().getField("y").getDouble(position)+floorY);world.add(position.getClass().getField("z").getDouble(position)+z*c-x*s);door.add("world",world);
            door.addProperty("local_x",x);door.addProperty("local_z",z);door.addProperty("local_width",number(box,"getMaxZMapped")-number(box,"getMinZMapped"));door.addProperty("outward_x",Math.signum(x)*c);door.addProperty("outward_z",-Math.signum(x)*s);doors.add(door);
        }
        if(doors.isEmpty()){resource.details().addProperty("resource_state","READY_NATIVE_CACHE_WITHOUT_DOORWAYS");throw new ResourceWaiting(resource.details());}
        row.add("doors",doors);row.add("native_resource_status",resource.details());return row;
    }
    private static void recordResource(long platform,long route,long vehicle,JsonObject detail,long time)
    {
        String key=vehicle+"/"+detail.get("ordinal").getAsInt()+"/"+detail.get("vehicle_resource").getAsString();
        JsonObject old=RESOURCES.get(key);String stage=detail.get("resource_state").getAsString();
        boolean changed=old==null||!stage.equals(old.get("resource_state").getAsString());
        detail.addProperty("platform_id",Long.toString(platform));detail.addProperty("route_id",Long.toString(route));detail.addProperty("vehicle_id",Long.toString(vehicle));detail.addProperty("last_client_game_time",time);
        detail.addProperty("attempt_count",old==null?1:old.get("attempt_count").getAsInt()+1);detail.addProperty("retry_on_next_actual_stop_sample",!"READY".equals(stage));RESOURCES.put(key,detail);diagnosticsChanged|=changed;
        if(changed&&!"READY".equals(stage))ProjectSeele.LOGGER.warn("R47 native door sample deferred: platform={} vehicle={} resource={} ordinal={} state={}; collector continues",platform,vehicle,detail.get("vehicle_resource").getAsString(),detail.get("ordinal").getAsInt(),stage);
    }
    private static void writeReports()throws Exception
    {
        Path path=Path.of(TARGET).toAbsolutePath();Files.createDirectories(path.getParent());
        var report=new JsonObject();report.addProperty("schema","projectseele.r47.actual-native-platform-doors.v1");report.addProperty("passive",true);report.addProperty("complete_all_platforms",false);report.add("stops",STOPS);write(path,report);
        var diagnostics=new JsonObject();diagnostics.addProperty("schema","projectseele.r47.actual-native-resource-status.v1");diagnostics.addProperty("collector_disabled",false);diagnostics.addProperty("cache_force",false);var rows=new JsonArray();RESOURCES.values().forEach(rows::add);diagnostics.add("observed_resources",rows);
        write(path.resolveSibling(path.getFileName()+".resources.json"),diagnostics);diagnosticsChanged=false;
    }
    private static void write(Path path,JsonObject report)throws Exception
    {
        Path temporary=path.resolveSibling(path.getFileName()+".tmp");
        Files.writeString(temporary,new GsonBuilder().setPrettyPrinting().create().toJson(report),java.nio.charset.StandardCharsets.UTF_8);
        try{Files.move(temporary,path,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}
        catch(AtomicMoveNotSupportedException ignored){Files.move(temporary,path,StandardCopyOption.REPLACE_EXISTING);}
    }
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(TARGET.isBlank()||event.phase!=TickEvent.Phase.END||++ticks%20!=0)return;
        var mc=net.minecraft.client.Minecraft.getInstance();if(mc.level==null||!"projectseele:geofront".equals(mc.level.dimension().location().toString()))return;
        try
        {
            Object data=Class.forName("org.mtr.mod.client.MinecraftClientData").getMethod("getInstance").invoke(null);boolean changed=false;
            for(Object vehicle:(Iterable<?>)data.getClass().getField("vehicles").get(data))
            {
                try
                {
                Object extra=vehicle.getClass().getField("vehicleExtraData").get(vehicle),persistent=vehicle.getClass().getField("persistentVehicleData").get(vehicle);
                long platform=((Number)call(extra,"getThisPlatformId")).longValue(),route=((Number)call(extra,"getThisRouteId")).longValue();
                if(platform==-1||number(vehicle,"getSpeed")>=.001||number(persistent,"getDoorValue")<=.8)continue;
                var cars=(List<?>)extra.getClass().getField("immutableVehicleCars").get(extra);if(cars.isEmpty()||!((String)call(cars.get(0),"getVehicleId")).startsWith("eidan_9000"))continue;
                long vehicleId=((Number)call(vehicle,"getId")).longValue();var rows=new JsonArray();boolean waiting=false;
                for(int i=0;i<cars.size();i++)
                {
                    try{JsonObject row=car(vehicle,cars.get(i),i,cars.size());recordResource(platform,route,vehicleId,row.getAsJsonObject("native_resource_status"),mc.level.getGameTime());rows.add(row);}
                    catch(ResourceWaiting pending){recordResource(platform,route,vehicleId,pending.details,mc.level.getGameTime());waiting=true;}
                }
                if(waiting)continue; // No partial car/stop rows or SEEN token until all actual cars are ready.
                long direction=Math.round(rows.get(0).getAsJsonObject().get("yaw_radians").getAsDouble()*1000);String key=platform+"/"+route+"/"+vehicleId+"/"+direction;if(SEEN.contains(key))continue;
                var stop=new JsonObject();stop.addProperty("platform_id",Long.toString(platform));stop.addProperty("route_id",Long.toString(route));stop.addProperty("vehicle_id",Long.toString(((Number)call(vehicle,"getId")).longValue()));stop.addProperty("speed",number(vehicle,"getSpeed"));stop.addProperty("door_value",number(persistent,"getDoorValue"));stop.addProperty("client_game_time",mc.level.getGameTime());stop.add("native_head",xyz(call(vehicle,"getHeadPosition")));
                stop.addProperty("rail_progress",railProgress(vehicle,persistent));stop.add("cars",rows);STOPS.add(stop);SEEN.add(key);changed=true;
                }
                catch(Exception error)
                {
                    String key=error.getClass().getName()+"/"+error.getMessage();
                    if(REPORTED_ERRORS.add(key))ProjectSeele.LOGGER.error("R47 native door sample error; other vehicles and later samples continue",error);
                }
            }
            if(changed||diagnosticsChanged||!RESOURCES.isEmpty()&&ticks%200==0)writeReports();
        }
        catch(Exception error){String key="collector/"+error.getClass().getName()+"/"+error.getMessage();if(REPORTED_ERRORS.add(key))ProjectSeele.LOGGER.error("R47 native door exporter retryable error; collector remains enabled",error);}
    }
}
