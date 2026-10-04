package com.projectseele.client;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaImpactResponse;
import com.projectseele.network.ClientboundImpactResponsePacket;
import com.projectseele.world.EvaPilotResolver;
import net.minecraft.client.Minecraft;
import net.minecraft.world.entity.LivingEntity;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.common.Mod;
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class EvaImpactClient
{
    public static void receive(ClientboundImpactResponsePacket p)
    {
        var mc=Minecraft.getInstance();var level=mc.level;
        if(level!=null&&level.getEntity(p.entity()) instanceof LivingEntity actor)
        {
            EvaImpactResponse.add(actor,p.tick(),p.direction(),p.strength(),p.height());
            if(actor instanceof com.projectseele.entity.EvaUnit01Entity eva&&mc.player!=null&&EvaPilotResolver.controlTarget(mc.player)==eva)
                EvaImpactResponse.displace(eva,p.direction(),p.strength());
        }
    }
    private EvaImpactClient() {}
}
