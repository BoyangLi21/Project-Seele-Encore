package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.network.SeeleNetwork;
import com.projectseele.network.ServerboundSynchLabExitR47;
import net.minecraft.client.Minecraft;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Laboratory V/Shift request the same owned safe exit before ordinary EVA/vanilla dismount consumers. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class SynchLabInputR47
{
    @SubscribeEvent(priority=EventPriority.HIGHEST)
    public static void tick(TickEvent.ClientTickEvent event)
    {
        var minecraft=Minecraft.getInstance();var player=minecraft.player;
        if(player==null||!(player.getVehicle() instanceof EntryPlugCarrierEntity cap)||cap.laboratorySlotR47()<0)return;
        if(event.phase==TickEvent.Phase.START)
        {
            if(minecraft.screen==null&&minecraft.options.keyShift.isDown())
                SeeleNetwork.CHANNEL.sendToServer(new ServerboundSynchLabExitR47());
            minecraft.options.keyShift.setDown(false);player.setShiftKeyDown(false);return;
        }
        if(minecraft.screen!=null)return;
        while(Keybinds.EXIT_EVA.consumeClick())SeeleNetwork.CHANNEL.sendToServer(new ServerboundSynchLabExitR47());
    }
    private SynchLabInputR47(){}
}
