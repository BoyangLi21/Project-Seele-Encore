package com.projectseele.event;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import com.projectseele.network.*;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.entity.living.LivingDamageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.network.PacketDistributor;

/** Real accepted damage supplies contact position and direction; shield strikes remain shield feedback. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class EvaHitFeedback
{
    private record Contact(LivingEntity target,Vec3 point,Vec3 direction) {}
    private static final ThreadLocal<Contact> CONTACT=new ThreadLocal<>();
    public static boolean hurt(LivingEntity target,DamageSource source,float amount,Vec3 point,Vec3 direction)
    {
        Contact old=CONTACT.get();CONTACT.set(new Contact(target,point,direction));
        float health=target.getHealth(),field=target instanceof Angel angel?angel.getAtField():target instanceof EvaUnit01Entity eva?eva.getAtFieldEnergy():0;
        try
        {
            boolean accepted=target instanceof GaghielEntity marine
                    ? marine.hurtAt(source,amount,point) : target.hurt(source,amount);
            float after=target instanceof Angel angel?angel.getAtField():target instanceof EvaUnit01Entity eva?eva.getAtFieldEnergy():0;
            if(target.getHealth()>=health&&after<field&&source.getEntity() instanceof LivingEntity attacker)
            {
                CombatFeelR31.acceptedHit(target,attacker,amount,direction,true,point);
                long tick=target.level().getGameTime();float height=(float)Math.max(0,Math.min(1,(point.y-target.getY())/target.getBbHeight()));
                EvaImpactResponse.add(target,tick,direction,.38F,height);
                SeeleNetwork.CHANNEL.send(PacketDistributor.TRACKING_ENTITY_AND_SELF.with(()->target),new ClientboundImpactResponsePacket(target.getId(),tick,direction,.38F,height));
            }
            return accepted;
        }
        finally{if(old==null)CONTACT.remove();else CONTACT.set(old);}
    }
    @SubscribeEvent public static void damaged(LivingDamageEvent event)
    {
        LivingEntity target=event.getEntity();if(!(target.level() instanceof ServerLevel level)||!(target instanceof EvaUnit01Entity||target instanceof Angel)||event.getAmount()<=0)return;
        var c=CONTACT.get();Vec3 origin=event.getSource().getSourcePosition();if(origin==null)origin=target.position().subtract(target.getLookAngle());
        Vec3 point=c!=null&&c.target==target?c.point:target.position().add(0,target.getBbHeight()*.58,0);
        Vec3 direction=c!=null&&c.target==target?c.direction:target.position().subtract(origin).normalize();
        float strength=(float)Math.min(1.2,.22+Math.sqrt(event.getAmount()/Math.max(1,target.getMaxHealth()))*2.0);
        float height=(float)Math.max(0,Math.min(1,(point.y-target.getY())/target.getBbHeight()));long tick=level.getGameTime();EvaImpactResponse.add(target,tick,direction,strength,height);
        CombatFeelR31.acceptedHit(target,event.getSource().getEntity() instanceof LivingEntity actor?actor:null,event.getAmount(),direction,false,point);
        if(event.getSource().getEntity() instanceof Angel||event.getSource().getEntity() instanceof EvaUnit01Entity eva&&eva.isMeleeWeapon())
            SeeleNetwork.CHANNEL.send(PacketDistributor.TRACKING_ENTITY_AND_SELF.with(()->target),new ClientboundCombatImpactR36(point,direction,strength,target instanceof EvaUnit01Entity));
        if(target instanceof EvaUnit01Entity eva)EvaImpactResponse.displace(eva,direction,strength);
        SeeleNetwork.CHANNEL.send(PacketDistributor.TRACKING_ENTITY_AND_SELF.with(()->target),new ClientboundImpactResponsePacket(target.getId(),tick,direction,strength,height));
        if(target instanceof EvaUnit01Entity)com.projectseele.world.GiantParticles.send(level,ParticleTypes.ELECTRIC_SPARK,point.x,point.y,point.z,40,2.3,2.3,2.3,.35);
        else com.projectseele.world.GiantParticles.send(level,new net.minecraft.core.particles.DustParticleOptions(new org.joml.Vector3f(.36F,.015F,.025F),3.8F),point.x,point.y,point.z,36,2.4,2.4,2.4,.22);
        com.projectseele.world.GiantParticles.send(level,ParticleTypes.POOF,point.x,point.y,point.z,12,1.2,1.2,1.2,.08);
    }
    private EvaHitFeedback() {}
}
