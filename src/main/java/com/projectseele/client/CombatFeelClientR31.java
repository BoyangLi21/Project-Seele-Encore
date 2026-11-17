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
    /**
     * R63: a blow of the piloted unit that lands pushes the pilot's view in by this fraction of its field for a
     * moment, a heavier one (held two ticks) by the second. A blow that meets nothing never moves the view.
     */
    public static final float HIT_PUSH_R63=.012F,HIT_PUSH_HEAVY_R63=.022F;
    public static void receive(ClientboundCombatFeelR31 p)
    {
        var mc=Minecraft.getInstance();if(mc.level!=null&&mc.level.getEntity(p.entity()) instanceof LivingEntity actor)
        {
            CombatFeelR31.receive(actor,p.beat(),p.phase());if(p.beat().kind()==CombatFeelR31.THROWN)actor.setDeltaMovement(p.beat().direction());
            if(p.beat().kind()==CombatFeelR31.CONTACT&&mc.player!=null&&mc.getCameraEntity()==mc.player&&actor==EvaPilotResolver.controlTarget(mc.player))
            {
                if(CameraKickR58.TOLD)com.projectseele.ProjectSeele.LOGGER.info("R63HITPUSH the piloted unit's blow landed, held {} ticks",p.beat().stopTicks());
                CameraKickR58.kick(0,0,-(p.push()>0?p.push():p.beat().stopTicks()<=1?HIT_PUSH_R63:HIT_PUSH_HEAVY_R63),3);
            }
        }
    }
    @SubscribeEvent public static void camera(ViewportEvent.ComputeCameraAngles e)
    {
        var mc=Minecraft.getInstance();if(mc.player==null||mc.getCameraEntity()!=mc.player)return;
        var eva=EvaPilotResolver.controlTarget(mc.player);
        if(eva==null||eva.isNervLogisticsLocked()||eva.isFirstBattleActive()||EvaCommandFeedClient.isOpticalRenderPass())return;
        var b=CombatFeelR31.beat(eva);float pulse=0,held=0;
        if(b!=null)
        {
            float t=CombatFeelR31.age(eva,(float)e.getPartialTick());
            // A heavier blow holds both bodies longer and swings the view further: by a quarter more for
            // each tick held past the first. Landing the kick on an Angel used to move it a third of a degree.
            float weight=b.stopTicks()<=1?1F:Math.min(2.2F,.75F+.25F*b.stopTicks());
            pulse=(float)(Math.exp(-t/3.5)*Math.sin(t*1.15))*b.strength()*weight;
            // While the bodies are held on the blow the view rattles, dying away as they let go.
            if(t<b.stopTicks())held=(float)Math.sin(t*6.5)*(1-t/b.stopTicks())*b.strength()*.55F;
        }
        float pitch=pulse*(b!=null&&b.kind()==CombatFeelR31.CONTACT?.65F:1.4F)+held*(b!=null&&b.kind()==CombatFeelR31.CONTACT?.8F:1F);
        float roll=pulse*(b!=null&&b.kind()==CombatFeelR31.CONTACT?.22F:.6F)+held*.45F;
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
            // R64: the plug's picture swings and rattles by a share of what the head does.
            float share=com.projectseele.client.cockpit.PilotViewSteadyR64.blowShake();pitch*=share;roll*=share;
        }
        float scale=com.projectseele.config.SeeleConfig.FX_INTENSITY.get().floatValue();
        e.setPitch(e.getPitch()+pitch*scale);e.setRoll(e.getRoll()+roll*scale);
    }
    private CombatFeelClientR31() {}
}
