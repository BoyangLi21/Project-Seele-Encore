package com.projectseele.client;

import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import com.projectseele.world.TransportLifecycleTraceR45;
import net.minecraft.client.Minecraft;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.lang.reflect.Field;

/** Observes raw player/vehicle epochs; never queries meshes or advances MTR smoothing. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class TransportClientTraceR45
{
    private static Vec3 previous;
    private static long previousNano;
    private static long lastDump;
    @SubscribeEvent public static void render(TickEvent.RenderTickEvent event)
    {
        if(!TransportLifecycleTraceR45.enabled()||event.phase!=TickEvent.Phase.END)return;
        var mc=Minecraft.getInstance();if(mc.level==null||mc.player==null)return;
        JsonObject row=new JsonObject();long now=System.nanoTime();Vec3 point=mc.player.position();
        row.addProperty("client_game_time",mc.level.getGameTime());row.addProperty("dimension",mc.level.dimension().location().toString());
        row.addProperty("player_position",point.toString());row.addProperty("velocity",mc.player.getDeltaMovement().toString());
        row.addProperty("grounded",mc.player.onGround());row.addProperty("paused",mc.isPaused());
        row.addProperty("native_simulation_seconds",AircraftRenderClockR21.simulationSeconds);row.addProperty("native_frame",AircraftRenderClockR21.frame);
        row.addProperty("frame_wall_seconds",previousNano==0?0:(now-previousNano)/1e9);row.addProperty("duplicate_mtr_passes",AircraftRenderClockR21.duplicateMtrPasses);
        row.addProperty("vanilla_vehicle",mc.player.getVehicle()==null?"":mc.player.getVehicle().getStringUUID());
        try
        {
            Class<?> riding=Class.forName("org.mtr.mod.client.VehicleRidingMovement");Field f=riding.getDeclaredField("ridingVehicleId");f.setAccessible(true);long id=f.getLong(null);
            row.addProperty("native_riding_vehicle",id);
            Object data=Class.forName("org.mtr.mod.client.MinecraftClientData").getMethod("getInstance").invoke(null);
            for(Object v:(Iterable<?>)data.getClass().getField("vehicles").get(data))
            {
                if(((Number)TransportLifecycleTraceR45.call(v,"getId")).longValue()!=id)continue;
                row.add("actual_vehicle",TransportLifecycleTraceR45.vehicle(v));
                Object persistent=TransportLifecycleTraceR45.field(v,"persistentVehicleData");
                row.addProperty("presented_progress",((Number)TransportLifecycleTraceR45.field(persistent,"smoothedRailProgress")).doubleValue());
                row.addProperty("correction_remaining",((Number)TransportLifecycleTraceR45.field(persistent,"railProgressSmoothingAdjustment")).doubleValue());
                row.addProperty("native_door_value",((Number)TransportLifecycleTraceR45.call(persistent,"getDoorValue")).doubleValue());
                Object relative=riding.getMethod("getRidingVehicleCarNumberAndOffset",long.class).invoke(null,id);row.addProperty("native_relative_rider",String.valueOf(relative));
                break;
            }
        }
        catch(Exception error){row.addProperty("native_read_error",error.toString());}
        double movement=previous==null?0:point.distanceTo(previous);row.addProperty("position_step",movement);
        TransportLifecycleTraceR45.record("client",mc.player.getStringUUID(),row);
        if(movement>15&&now-lastDump>1_000_000_000L){lastDump=now;TransportLifecycleTraceR45.dump("observed_client_position_step_over_15m; movement is not asserted invalid");}
        previous=point;previousNano=now;
    }
    private TransportClientTraceR45(){}
}
