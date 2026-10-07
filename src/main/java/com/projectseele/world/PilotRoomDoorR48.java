package com.projectseele.world;

import com.projectseele.ProjectSeele;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Finite original pilot-room doors precede nearby seat hit boxes. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class PilotRoomDoorR48
{
    @SubscribeEvent(priority=EventPriority.HIGHEST)
    public static void use(PlayerInteractEvent.RightClickBlock event)
    {
        if(event.getHand()!=InteractionHand.MAIN_HAND
                ||!(event.getEntity() instanceof ServerPlayer player)
                ||!(event.getLevel() instanceof ServerLevel level))return;
        if(FacilityDoorControlsR49.pilotDoorUse(level,event.getPos(),player)
                ||PilotRestroomsR47.manualDoorR48(level,event.getPos(),player))
        {
            event.setCanceled(true);
            event.setCancellationResult(InteractionResult.CONSUME);
        }
    }
    private PilotRoomDoorR48() { }
}
