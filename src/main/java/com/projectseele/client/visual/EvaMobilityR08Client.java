package com.projectseele.client.visual;

import com.projectseele.ProjectSeele;
import com.projectseele.visual.EvaMobilityR08Review;
import net.minecraft.client.Minecraft;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class EvaMobilityR08Client
{
    private static int ending;
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if("r08-details".equals(System.getProperty("projectseele.regionalBuild",""))
                && event.phase==TickEvent.Phase.END
                && com.projectseele.visual.RegionalR08DetailReview.finished)
        {
            if(++ending>60)Minecraft.getInstance().stop();
            return;
        }
        if(("collision-audit".equals(System.getProperty("projectseele.regionalBuild",""))||"r19-collision".equals(System.getProperty("projectseele.regionalBuild",""))||"r40-collision".equals(System.getProperty("projectseele.regionalBuild","")))
                && event.phase==TickEvent.Phase.END
                && com.projectseele.visual.RegionalSpatialAuditDriver.done)
        {
            if(++ending>60)Minecraft.getInstance().stop();
            return;
        }
        if(("r08-installations".equals(System.getProperty("projectseele.regionalBuild",""))||"r08-heli-recover".equals(System.getProperty("projectseele.regionalBuild","")))
                && event.phase==TickEvent.Phase.END
                && com.projectseele.visual.RegionalR08InstallationReview.finished)
        {
            if(++ending>60)Minecraft.getInstance().stop();
            return;
        }
        if(!EvaMobilityR08Review.ENABLED||event.phase!=TickEvent.Phase.END)return;
        var mc=Minecraft.getInstance();mc.options.pauseOnLostFocus=false;
        mc.options.keyUp.setDown(EvaMobilityR08Review.forward>0);mc.options.keyJump.setDown(EvaMobilityR08Review.jump);
        if(mc.player!=null&&mc.player.isPassenger()){mc.player.setYRot(0);mc.player.setXRot(0);}
        EvaMobilityR08Review.clientTracked=mc.level!=null&&mc.level.getEntity(EvaMobilityR08Review.unitId)!=null;
        EvaMobilityR08Review.clientMounted=mc.player!=null&&mc.player.getVehicle()!=null&&mc.player.getVehicle().getId()==EvaMobilityR08Review.unitId;
        if(mc.player!=null)EvaMobilityR08Review.clientStatus="vehicle="+mc.player.getVehicle()+", local="+mc.player.getRootVehicle().isControlledByLocalInstance()+", camera="+(mc.getCameraEntity()==mc.player)+", input="+mc.player.zza+", screen="+mc.screen;
        if(EvaMobilityR08Review.finished&&++ending>40)mc.stop();
    }
}
