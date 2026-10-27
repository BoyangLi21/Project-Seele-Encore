package com.projectseele.client;

import com.projectseele.network.ClientboundLaunchFeedbackR54;
import java.util.HashMap;
import java.util.Map;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.world.phys.Vec3;

/** Short guide-scale exhaust and sparks from server-committed contact points. */
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
        for(var contact:packet.contacts())
        {
            var point=contact.point();if(camera.distanceToSqr(point)>192*192)continue;
            int clouds=packet.burst()?6:2;
            for(int i=0;i<clouds;i++)
            {
                var origin=point.add((random.nextDouble()-.5)*1.2,(random.nextDouble()-.5)*.8,(random.nextDouble()-.5)*1.2);
                Vec3 jet=contact.tangent().scale(-(.35+strength*.9));
                var particle=mc.particleEngine.createParticle(ParticleTypes.CLOUD,origin.x,origin.y,origin.z,jet.x,jet.y,jet.z);
                if(particle!=null){particle.scale(packet.burst()?10F:7F);particle.setLifetime(packet.burst()?18:12);}
            }
            int sparks=packet.burst()?8:2+(int)(strength*3);
            for(int i=0;i<sparks;i++)
            {
                var velocity=contact.tangent().scale(-(.6+strength*1.8)).add((random.nextDouble()-.5)*.4,(random.nextDouble()-.5)*.4,(random.nextDouble()-.5)*.4);
                var particle=mc.particleEngine.createParticle(ParticleTypes.ELECTRIC_SPARK,point.x,point.y,point.z,velocity.x,velocity.y,velocity.z);
                if(particle!=null){particle.scale(3F);particle.setLifetime(8);}
            }
        }
    }
    private NervLaunchFeedbackClientR54(){}
}
