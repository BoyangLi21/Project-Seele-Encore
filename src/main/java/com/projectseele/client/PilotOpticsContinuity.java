package com.projectseele.client;

import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import java.util.UUID;

/** Removes camera-source discontinuities without adding lag to input yaw or normal translation. */
public final class PilotOpticsContinuity
{
    private static UUID actor;
    private static double time;
    private static int branch;
    private static Vec3 previous=Vec3.ZERO,correction=Vec3.ZERO;

    public static Vec3 apply(EvaUnit01Entity eva,float partial,Vec3 eye)
    {
        // The optical broadcast uses a separate render pass and must never advance the pilot filter.
        if(EvaCommandFeedClient.isOpticalRenderPass())return eye;
        double now=(double)eva.level().getGameTime()+partial;
        Vec3 origin=new Vec3(Mth.lerp(partial,eva.xo,eva.getX()),Mth.lerp(partial,eva.yo,eva.getY()),Mth.lerp(partial,eva.zo,eva.getZ()));
        Vec3 local=eye.subtract(origin);
        boolean continuousBody=!eva.isExperimentalUnit()
                &&com.projectseele.entity.EvaGameplayMotionR32.sharedBody(eva,partial)
                &&com.projectseele.entity.EvaGameplayMotionR32.sharedWeapon(eva);
        int next=(continuousBody?0:(eva.isVisuallyAirborneForRender()?1:0)|(eva.hasLiveActionForRender(partial)?2:0))|(eva.getWeapon()<<2);
        if(!eva.getUUID().equals(actor)||now<time||now-time>10)
        {actor=eva.getUUID();time=now;branch=next;previous=local;correction=Vec3.ZERO;return eye;}
        double dt=Math.max(0,now-time)/20;
        if(next!=branch)
        {
            correction=previous.subtract(local);
            if(correction.lengthSqr()>144)correction=correction.normalize().scale(12);
            branch=next;
        }
        else correction=correction.scale(Math.pow(.5,dt/.075));
        // Aimed rifle optics are an exact firing ray. Never soften that ray.
        if(ClientForgeEvents.isRifleSightActive(eva)||ClientForgeEvents.isCannonScopeActive(eva))correction=Vec3.ZERO;
        time=now;previous=local.add(correction);return origin.add(previous);
    }
    public static void clear(){actor=null;correction=Vec3.ZERO;}
    private PilotOpticsContinuity() {}
}
