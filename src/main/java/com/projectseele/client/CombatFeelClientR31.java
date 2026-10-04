package com.projectseele.client;

import com.projectseele.entity.*;
import com.projectseele.network.ClientboundCombatFeelR31;
import com.projectseele.world.EvaPilotResolver;
import net.minecraft.client.Minecraft;
import net.minecraft.world.entity.LivingEntity;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ViewportEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

@Mod.EventBusSubscriber(modid="projectseele",value=Dist.CLIENT)
public final class CombatFeelClientR31
{
    public static void receive(ClientboundCombatFeelR31 p)
    {
        var mc=Minecraft.getInstance();if(mc.level!=null&&mc.level.getEntity(p.entity()) instanceof LivingEntity actor)
        {CombatFeelR31.receive(actor,p.beat(),p.phase());if(p.beat().kind()==CombatFeelR31.THROWN)actor.setDeltaMovement(p.beat().direction());}
    }
    @SubscribeEvent public static void camera(ViewportEvent.ComputeCameraAngles e)
    {
        var mc=Minecraft.getInstance();if(mc.player==null||mc.getCameraEntity()!=mc.player)return;
        var eva=EvaPilotResolver.controlTarget(mc.player);
        if(eva==null||eva.isNervLogisticsLocked()||eva.isFirstBattleActive()||EvaCommandFeedClient.isOpticalRenderPass())return;
        var b=CombatFeelR31.beat(eva);float pulse=0;
        if(b!=null)
        {
            float t=CombatFeelR31.age(eva,(float)e.getPartialTick());
            pulse=(float)(Math.exp(-t/3.5)*Math.sin(t*1.15))*b.strength();
        }
        float pitch=pulse*(b!=null&&b.kind()==CombatFeelR31.CONTACT?.65F:1.4F);
        float roll=pulse*(b!=null&&b.kind()==CombatFeelR31.CONTACT?.22F:.6F);
        if(mc.options.getCameraType().isFirstPerson())
        {
            var impact=EvaImpactResponse.sample(eva,(float)e.getPartialTick());
            float physical=(impact.roll()+impact.pitch()*.22F)*7;
            // Both packets originate from the same accepted hit. One camera
            // owner takes the stronger response instead of adding it twice.
            if(Math.abs(physical)>Math.abs(roll))roll=physical;
            roll=net.minecraft.util.Mth.clamp(roll,-2.5F,2.5F);
            pitch=net.minecraft.util.Mth.clamp(pitch,-1.8F,1.8F);
            // Roll preserves the firing ray. A post-camera pitch kick does
            // not, so sighted optics never receive that second aim offset.
            if(ClientForgeEvents.isRifleSightActive(eva)||ClientForgeEvents.isCannonScopeActive(eva))pitch=0;
        }
        float scale=com.projectseele.config.SeeleConfig.FX_INTENSITY.get().floatValue();
        e.setPitch(e.getPitch()+pitch*scale);e.setRoll(e.getRoll()+roll*scale);
    }
    private CombatFeelClientR31() {}
}
