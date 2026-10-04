package com.projectseele.world;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import com.projectseele.visual.RegionalNativeTransitInspection;
import java.lang.reflect.Field;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.function.Consumer;
import net.minecraft.server.level.ServerLevel;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Opt-in raw server/client transport evidence, without simulation or pose writes. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class TransportLifecycleTraceR45
{
    private static final boolean ENABLED=Boolean.getBoolean("projectseele.r45TransportTrace");
    private static final Map<String,ArrayDeque<JsonObject>> RECENT=new HashMap<>();
    private static long sequence;
    public static boolean enabled(){return ENABLED;}
    public static Object call(Object object,String name)throws ReflectiveOperationException
    {return object.getClass().getMethod(name).invoke(object);}
    public static Object field(Object object,String name)throws ReflectiveOperationException
    {
        Class<?> type=object.getClass();
        while(type!=null)
        {
            try{Field f=type.getDeclaredField(name);f.setAccessible(true);return f.get(object);}
            catch(NoSuchFieldException ignored){type=type.getSuperclass();}
        }
        throw new NoSuchFieldException(object.getClass().getName()+"."+name);
    }
    public static JsonObject vehicle(Object vehicle)throws ReflectiveOperationException
    {
        JsonObject row=new JsonObject();Object extra=field(vehicle,"vehicleExtraData");
        row.addProperty("vehicle_id",((Number)call(vehicle,"getId")).longValue());
        row.addProperty("raw_speed",((Number)field(vehicle,"speed")).doubleValue());
        try{row.addProperty("presented_speed",((Number)call(vehicle,"getSpeed")).doubleValue());}
        catch(NoSuchMethodException ignored){} // Only the client VehicleExtension exposes this getter.
        row.addProperty("raw_rail_progress",((Number)field(vehicle,"railProgress")).doubleValue());
        row.addProperty("mode",String.valueOf(call(vehicle,"getTransportMode")));
        row.addProperty("on_route",(Boolean)call(vehicle,"getIsOnRoute"));
        row.addProperty("route_id",((Number)call(extra,"getThisRouteId")).longValue());
        row.addProperty("platform_id",((Number)call(extra,"getThisPlatformId")).longValue());
        row.addProperty("next_platform_id",((Number)call(extra,"getNextPlatformId")).longValue());
        row.addProperty("native_door_multiplier",((Number)call(extra,"getDoorMultiplier")).intValue());
        Object head=call(vehicle,"getHeadPosition");
        if(head!=null)
        {
            JsonArray p=new JsonArray();for(String axis:new String[]{"x","y","z"})p.add(((Number)field(head,axis)).doubleValue());row.add("raw_head",p);
        }
        return row;
    }
    public static synchronized void record(String side,String actor,JsonObject row)
    {
        if(!ENABLED)return;
        row.addProperty("side",side);row.addProperty("actor",actor);row.addProperty("sequence",++sequence);
        row.addProperty("wall_utc_millis",System.currentTimeMillis());row.addProperty("monotonic_nanos",System.nanoTime());
        var queue=RECENT.computeIfAbsent(side+"/"+actor,key->new ArrayDeque<>());
        queue.addLast(row.deepCopy());while(queue.size()>64)queue.removeFirst();
        ProjectSeele.LOGGER.info("TRANSPORT R45 STATE {}",row);
    }
    public static synchronized void dump(String reason)
    {
        if(!ENABLED)return;
        JsonObject result=new JsonObject();result.addProperty("reason",reason);
        for(var entry:RECENT.entrySet())
        {JsonArray rows=new JsonArray();entry.getValue().forEach(rows::add);result.add(entry.getKey(),rows);}
        ProjectSeele.LOGGER.info("TRANSPORT R45 LAST64 {}",result);
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||event.phase!=TickEvent.Phase.END)return;
        ServerLevel level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;
        JsonObject row=new JsonObject();row.addProperty("server_tick",event.getServer().getTickCount());
        row.addProperty("game_time",level.getGameTime());row.addProperty("dimension",level.dimension().location().toString());
        JsonArray players=new JsonArray();
        for(var player:level.players())
        {
            JsonObject p=new JsonObject();p.addProperty("uuid",player.getStringUUID());p.addProperty("position",player.position().toString());
            p.addProperty("velocity",player.getDeltaMovement().toString());p.addProperty("grounded",player.onGround());
            p.addProperty("vanilla_vehicle",player.getVehicle()==null?"":player.getVehicle().getStringUUID());players.add(p);
        }
        row.add("actual_players",players);JsonArray vehicles=new JsonArray();
        try
        {
            Object simulator=RegionalNativeTransitInspection.simulator();row.addProperty("simulator_present",simulator!=null);
            if(simulator!=null)for(Object siding:(Iterable<?>)field(simulator,"sidings"))
            {
                var snapshot=new ArrayList<Object>();for(Object value:(Iterable<?>)field(siding,"vehicles"))snapshot.add(value);
                for(Object value:snapshot)
                {
                    Object extra=field(value,"vehicleExtraData");JsonArray riders=new JsonArray();
                    Consumer<Object> collect=rider->
                    {
                        JsonObject r=new JsonObject();
                        try
                        {
                            r.addProperty("uuid",String.valueOf(field(rider,"uuid")));
                            r.addProperty("car",((Number)call(rider,"getRidingCar")).longValue());
                            for(String axis:new String[]{"X","Y","Z"})r.addProperty("relative_"+axis.toLowerCase(),((Number)call(rider,"get"+axis)).doubleValue());
                            r.addProperty("gangway",(Boolean)call(rider,"getIsOnGangway"));r.addProperty("door_override",(Boolean)call(rider,"getDoorOverride"));
                        }
                        catch(ReflectiveOperationException error){r.addProperty("read_error",error.toString());}
                        riders.add(r);
                    };
                    extra.getClass().getMethod("iterateRidingEntities",Consumer.class).invoke(extra,collect);
                    if(riders.isEmpty()&&!String.valueOf(call(value,"getTransportMode")).equals("AIRPLANE"))continue;
                    JsonObject v=vehicle(value);v.add("native_registered_riders",riders);vehicles.add(v);
                }
            }
        }
        catch(Exception error){row.addProperty("native_read_error",error.toString());}
        row.add("actual_native_vehicles",vehicles);record("server","world",row);
    }
    @SubscribeEvent public static void stop(net.minecraftforge.event.server.ServerStoppingEvent event)
    {if(ENABLED){dump("server_stopping");synchronized(TransportLifecycleTraceR45.class){RECENT.clear();}}}
    private TransportLifecycleTraceR45(){}
}
