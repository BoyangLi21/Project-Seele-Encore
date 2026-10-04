package com.projectseele.world;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import com.supermartijn642.movingelevators.blocks.ControllerBlockEntity;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Reads the actual native group/menu/cage for every managed lift; no calls or writes. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class ElevatorInterfaceTraceR45
{
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!Boolean.getBoolean("projectseele.r45DeviceControlTrace")||event.phase!=TickEvent.Phase.END)return;
        var level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;
        for(var spec:NervLiftPassengerSync.managedLifts(level))
        {
            var position=S20MovingElevatorsAdapter.controllerPosition(spec,spec.lower());
            JsonObject row=new JsonObject();row.addProperty("lift",spec.id());row.addProperty("server_tick",event.getServer().getTickCount());
            row.addProperty("dimension",level.dimension().location().toString());row.addProperty("controller",position.toShortString());
            if(!level.hasChunkAt(position)||!(level.getBlockEntity(position) instanceof ControllerBlockEntity controller))
            {if(event.getServer().getTickCount()%20==0){row.addProperty("status","ACTUAL_CONTROLLER_UNLOADED_OR_ABSENT");ProjectSeele.LOGGER.info("LIFT R45 CONTROL {}",row);}continue;}
            var group=controller.getGroup();
            if(group==null){row.addProperty("status","NATIVE_GROUP_UNAVAILABLE");ProjectSeele.LOGGER.info("LIFT R45 CONTROL {}",row);continue;}
            if(!group.isMoving()&&event.getServer().getTickCount()%20!=0)continue;
            row.addProperty("moving",group.isMoving());row.addProperty("native_current_y",group.getCurrentY());row.addProperty("native_previous_y",group.getLastY());
            row.addProperty("native_target_speed",group.getTargetSpeed());row.addProperty("captured_cage_present",group.getCage()!=null);
            JsonArray floors=new JsonArray();for(int i=0;i<group.getFloorCount();i++)floors.add(group.getFloorYLevel(i));row.add("native_menu_floor_y",floors);
            JsonArray declared=new JsonArray();spec.stops().forEach(stop->declared.add(stop.walkY()));row.add("declared_floor_y",declared);
            if(group.getCage()!=null)
            {
                row.addProperty("native_cage_bounds",group.getCage().bounds.move(group.getCageAnchorPos(group.getCurrentY())).toString());
                row.addProperty("native_collision_members",group.getCage().collisionBoxes.size());
            }
            ProjectSeele.LOGGER.info("LIFT R45 CONTROL {}",row);
        }
    }
    private ElevatorInterfaceTraceR45(){}
}
