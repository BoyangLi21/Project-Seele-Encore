package com.projectseele.client.visual;

import com.projectseele.ProjectSeele;
import com.projectseele.visual.AccessR44Review;
import net.minecraft.client.Minecraft;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class AccessR44Client
{
    private static int end;
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(!AccessR44Review.ENABLED||event.phase!=TickEvent.Phase.END)return;var mc=Minecraft.getInstance();
        mc.options.pauseOnLostFocus=false;if(mc.player==null)return;if(mc.screen!=null)mc.setScreen(null);
        mc.options.keyUp.setDown(AccessR44Review.walk);mc.player.input.up=AccessR44Review.walk;mc.player.input.forwardImpulse=AccessR44Review.walk?1:0;
        mc.player.zza=AccessR44Review.walk?1:0;mc.player.setYRot(180);mc.player.setXRot(0);
        if(AccessR44Review.done&&++end>35){mc.options.keyUp.setDown(false);mc.stop();}
    }
    private AccessR44Client() {}
}
