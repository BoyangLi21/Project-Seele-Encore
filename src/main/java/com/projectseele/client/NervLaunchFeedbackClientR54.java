package com.projectseele.client;

import com.projectseele.network.ClientboundLaunchFeedbackR54;
import java.util.HashMap;
import java.util.Map;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.world.phys.Vec3;

/** Broad pressure plumes and sparks from server-committed guide contacts. */
public final class NervLaunchFeedbackClientR54
{
    private static final Map<ClientLevel,Map<Integer,Long>> LAST=new java.util.WeakHashMap<>();
    public static void receive(ClientboundLaunchFeedbackR54 packet)
    {
        var mc=Minecraft.getInstance();
        if(mc.level==null||!mc.level.dimension().location().equals(packet.dimension()))return;
        var last=LAST.computeIfAbsent(mc.level,ignored->new HashMap<>());
        if(packet.tick()<=last.getOrDefault(packet.entity(),Long.MIN_VALUE))return;
        last.put(packet.entity(),packet.tick());
        if(com.projectseele.config.SeeleConfig.FX_INTENSITY.get()<=0)return;
        var camera=mc.gameRenderer.getMainCamera().getPosition();var random=mc.level.random;
        double strength=Math.min(1,packet.speed()/100D);
        Vec3 centre=Vec3.ZERO;
        for(var contact:packet.contacts())centre=centre.add(contact.point());
        if(!packet.contacts().isEmpty())centre=centre.scale(1D/packet.contacts().size());
        for(var contact:packet.contacts())
        {
            var point=contact.point();if(camera.distanceToSqr(point)>192*192)continue;
            Vec3 tangent=contact.tangent();
            Vec3 outward=point.subtract(centre);outward=outward.subtract(tangent.scale(outward.dot(tangent)));
            if(outward.lengthSqr()<1e-6)outward=tangent.cross(Math.abs(tangent.y)>.9?new Vec3(0,0,1):new Vec3(0,1,0));
            outward=outward.normalize();
            // The measured facets are pressed against steel. Release the
            // visible plume beyond that contact instead of inside the bearing.
            Vec3 nozzle=point.add(outward.scale(3.5)).add(tangent.scale(-1.5));
            int clouds=packet.burst()?28:8;
            for(int i=0;i<clouds;i++)
            {
                var origin=nozzle.add((random.nextDouble()-.5)*2.8,(random.nextDouble()-.5)*1.8,(random.nextDouble()-.5)*2.8);
                Vec3 jet=outward.scale(.7+random.nextDouble()*.6).add(tangent.scale(-(.7+strength*1.2)));
                var particle=mc.particleEngine.createParticle(ParticleTypes.CLOUD,origin.x,origin.y,origin.z,jet.x,jet.y,jet.z);
                // createParticle already enqueues the instance in ParticleEngine.
                if(particle!=null){particle.scale(packet.burst()?60F:42F);particle.setColor(.94F,.97F,1F);particle.setLifetime(packet.burst()?55:38);}
            }
            int sparks=packet.burst()?32:6+(int)(strength*8);
            for(int i=0;i<sparks;i++)
            {
                var velocity=outward.scale(.35).add(tangent.scale(-(.8+strength*2.2))).add((random.nextDouble()-.5)*.7,(random.nextDouble()-.5)*.7,(random.nextDouble()-.5)*.7);
                var particle=mc.particleEngine.createParticle(ParticleTypes.ELECTRIC_SPARK,nozzle.x,nozzle.y,nozzle.z,velocity.x,velocity.y,velocity.z);
                if(particle!=null){particle.scale(5F);particle.setLifetime(12);}
            }
        }
    }
    private NervLaunchFeedbackClientR54(){}
}
