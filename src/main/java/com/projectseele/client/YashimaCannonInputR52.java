package com.projectseele.client;

import com.projectseele.network.*;
import com.projectseele.world.*;
import net.minecraft.client.Minecraft;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.InputEvent;
import net.minecraftforge.eventbus.api.*;
import net.minecraftforge.fml.common.Mod;

/** Only the synchronized original fixed actor intercepts pilot use before ordinary melee/rack input. */
@Mod.EventBusSubscriber(modid="projectseele",value=Dist.CLIENT)
public final class YashimaCannonInputR52
{
    private static int lastTick=-1;
    @SubscribeEvent(priority=EventPriority.HIGHEST) public static void use(InputEvent.InteractionKeyMappingTriggered event)
    {
        if(!event.isUseItem())return;var mc=Minecraft.getInstance();var player=mc.player;if(player==null||mc.screen!=null)return;
        var eva=EvaPilotResolver.controlTarget(player);if(eva==null||!eva.hasFixedCannonR52()||eva.getPilotEntity()!=player)return;
        var gun=eva.fixedCannonBodyR52();if(gun==null||!gun.readyR52()||!gun.loadedR52())return;
        if(eva.fixedCannonOperatingR52()&&!player.isShiftKeyDown())return;
        var eye=player.getEyePosition();if(!eva.fixedCannonOperatingR52()&&YashimaCannonMeshR52.rayHitR52(gun,eye,eye.add(player.getLookAngle().scale(128)))==null)return;
        event.setCanceled(true);event.setSwingHand(false);
        if(lastTick!=player.tickCount){lastTick=player.tickCount;SeeleNetwork.CHANNEL.sendToServer(new ServerboundEvaControlPacket(ServerboundEvaControlPacket.ACTION_FIXED_CANNON_R52,gun.getId()));}
    }
    private YashimaCannonInputR52(){}
}
