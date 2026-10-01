package com.projectseele.client.visual;

import com.projectseele.ProjectSeele;
import com.projectseele.visual.RuntimeProfileR44Review;
import net.minecraft.client.Minecraft;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class RuntimeProfileR44Client
{
    private static int ended;
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {if(!RuntimeProfileR44Review.ENABLED||event.phase!=TickEvent.Phase.END)return;var mc=Minecraft.getInstance();mc.options.pauseOnLostFocus=false;if(mc.player!=null&&mc.screen!=null)mc.setScreen(null);if(RuntimeProfileR44Review.done&&++ended>40)mc.stop();}
    private RuntimeProfileR44Client() {}
}
