package com.projectseele.client.visual;

import com.projectseele.ProjectSeele;
import com.projectseele.visual.CoordinationR44Review;
import net.minecraft.client.Minecraft;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class CoordinationR44Client
{
    private static int ended;
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(!CoordinationR44Review.ENABLED||event.phase!=TickEvent.Phase.END)return;var mc=Minecraft.getInstance();mc.options.pauseOnLostFocus=false;
        if(mc.player!=null&&mc.screen!=null)mc.setScreen(null);
        if(CoordinationR44Review.done&&++ended>35)mc.stop();
    }
    private CoordinationR44Client() {}
}
