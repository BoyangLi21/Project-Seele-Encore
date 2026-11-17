package com.projectseele.entity;

import net.minecraft.network.syncher.*;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.Vec3;
import org.joml.Vector3f;
import java.util.*;

/** A slowly fitted prone support plane, shared by the skin, gun and optical socket. */
public final class EvaTerrainSupport
{
    private static final EntityDataAccessor<Vector3f> PLANE=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.VECTOR3);
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,View> VIEWS=new com.projectseele.util.WeakIdentityMap<>();
    private static final class View{final EvaPoseSignalClock[] clocks={new EvaPoseSignalClock(),new EvaPoseSignalClock(),new EvaPoseSignalClock()};Vector3f last;}
    public static boolean bootstrap(){return true;}
    public static void define(SynchedEntityData data){data.define(PLANE,new Vector3f());}
    public static void tick(EvaUnit01Entity eva)
    {
        if(eva.level().isClientSide)return;Vector3f desired=new Vector3f();float weight=EvaDorsalMechanism.smooth((eva.rifleStanceLevel(1)-2.35F)/.65F);
        if(weight>0&&eva.onGround()&&!eva.isFirstBattleActive()&&!eva.isNervLogisticsLocked())
        {
            double yaw=Math.toRadians(eva.getYRot());Vec3 front=new Vec3(-Math.sin(yaw),0,Math.cos(yaw)),right=new Vec3(-Math.cos(yaw),0,-Math.sin(yaw));
            double f=height(eva,front.scale(21)),b=height(eva,front.scale(-21)),r=height(eva,right.scale(9)),l=height(eva,right.scale(-9));
            desired.set((float)Math.atan2(f-b,42),(float)Math.atan2(r-l,18),(float)((f+b+r+l)*.25-eva.getY()));
            desired.x=Math.max(-.10F,Math.min(.10F,desired.x));desired.y=Math.max(-.10F,Math.min(.10F,desired.y));desired.z=Math.max(-1.2F,Math.min(1.2F,desired.z));desired.mul(weight);
        }
        Vector3f old=eva.getEntityData().get(PLANE),next=new Vector3f(old).lerp(desired,.18F);
        if(next.distanceSquared(desired)<1e-7)next.set(desired);if(next.distanceSquared(old)>1e-10)eva.getEntityData().set(PLANE,next);
    }
    private static double height(EvaUnit01Entity eva,Vec3 offset)
    {
        double[] samples=new double[3];int i=0;
        for(double x:new double[]{-1.2,0,1.2})
        {
            Vec3 p=eva.position().add(offset).add(x,0,0);var hit=eva.level().clip(new ClipContext(p.add(0,3.1,0),p.add(0,-4.1,0),ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,eva));
            samples[i++]=hit.getType()==net.minecraft.world.phys.HitResult.Type.MISS?eva.getY():hit.getLocation().y;
        }
        Arrays.sort(samples);return samples[1];
    }
    public static Vector3f sample(EvaUnit01Entity eva)
    {
        Vector3f value=eva.getEntityData().get(PLANE);if(!eva.level().isClientSide)return new Vector3f(value);
        View v=VIEWS.computeIfAbsent(eva,e->new View());if(v.last==null||!v.last.equals(value))
        {for(int i=0;i<3;i++)v.clocks[i].accept(value.get(i),false,false);v.last=new Vector3f(value);}
        long time=FirstBattleSignals.clientFrameTime();return new Vector3f(v.clocks[0].sample(time),v.clocks[1].sample(time),v.clocks[2].sample(time));
    }
    public static void apply(EvaUnit01Entity eva,EvaBodyPose.Sample body)
    {
        Vector3f p=sample(eva);body.rotations.get("root").rotateX(p.x).rotateZ(p.y);body.positions.get("root").y+=p.z/5;body.dirty();
    }
    private EvaTerrainSupport() {}
}
