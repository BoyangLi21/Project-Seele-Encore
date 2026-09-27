package com.projectseele.entity;

import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import org.joml.Vector3f;
import java.util.*;

/** Telescopic dolly pads use the same measured surface points for drawing and handoff. */
public final class UNReceivingCradleR40
{
    public record Fit(float yaw,Vec3 offset,double score) {}
    public static Fit fit(EvaUnit01Entity eva,float yaw)
    {
        var pose=EvaAirTransportR31.active(eva)?EvaAirTransportR31.origin(eva):EvaBodyPose.sample(eva,0);
        return fit(eva,yaw,com.projectseele.world.VerticalCarrierSweepR40.localVertices(eva,pose));
    }
    private static Fit fit(EvaUnit01Entity eva,float yaw,List<Vec3> points)
    {
        if(!(eva instanceof EvaPrototypeEntity un)||!(eva.level() instanceof net.minecraft.server.level.ServerLevel level))return new Fit(yaw,Vec3.ZERO,0);
        var home=com.projectseele.world.UNRecoveryR22.home(un.getUNSerial());var min=com.projectseele.world.UNHangarDimensionsR31.minimum(level,un.getUNSerial());var max=com.projectseele.world.UNHangarDimensionsR31.maximum(level,un.getUNSerial());
        double c=Math.cos((180-yaw)*Mth.DEG_TO_RAD),s=Math.sin((180-yaw)*Mth.DEG_TO_RAD);
        double x0=Double.POSITIVE_INFINITY,x1=Double.NEGATIVE_INFINITY,z0=x0,z1=x1;
        for(var p:points){double x=c*p.x+s*p.z,z=-s*p.x+c*p.z;x0=Math.min(x0,x);x1=Math.max(x1,x);z0=Math.min(z0,z);z1=Math.max(z1,z);}
        double lowX=min.getX()-home.x+.65-x0,highX=max.getX()+1-home.x-.65-x1;
        double lowZ=min.getZ()-home.z+.65-z0,highZ=max.getZ()+1-home.z-.65-z1;
        if(lowX>highX||lowZ>highZ)return null;
        var offset=new Vec3(Mth.clamp(0,lowX,highX),0,Mth.clamp(0,lowZ,highZ));
        return new Fit(yaw,offset,offset.lengthSqr()+.003*Math.abs(Mth.wrapDegrees(yaw))+.015*(x1-x0)*(x1-x0));
    }
    /** Keep the long axis of a fallen load along the ground transfer lane. */
    public static float groundHeading(EvaUnit01Entity eva)
    {
        var pose=EvaAirTransportR31.active(eva)?EvaAirTransportR31.origin(eva):EvaBodyPose.sample(eva,0);
        var up=pose.matrix("torso_lower").transformDirection(new Vector3f(0,1,0)).normalize();
        if(!EvaShutdownR30.disabled(eva)&&Math.abs(up.y)>.65)return 0;
        var points=com.projectseele.world.VerticalCarrierSweepR40.localVertices(eva,pose);double best=Double.POSITIVE_INFINITY;float angle=Float.NaN;
        for(int yaw=-180;yaw<180;yaw++)
        {
            var fit=fit(eva,yaw,points);if(fit!=null&&fit.score()<best){best=fit.score();angle=yaw;}
        }
        return angle;
    }
    public static List<Vec3> pads(EvaUnit01Entity eva)
    {
        var pose=EvaAirTransportR31.active(eva)?EvaAirTransportR31.origin(eva):EvaBodyPose.sample(eva,0);
        var points=EvaBodyPose.carrierBearingPointsR40(eva,pose);
        if(points.isEmpty())return List.of();
        var hulls=EvaBodyPose.posedCarrierHulls(eva,pose);
        double low=hulls.stream().mapToDouble(b->b.minY).min().orElse(0);
        double lift=Math.max(0,.035-low);var result=new ArrayList<Vec3>();
        for(var p:points)
        {
            if(p.y>low+8)continue;
            var at=new Vec3(-p.x,p.y+lift-.02,-p.z);
            if(result.stream().noneMatch(other->other.distanceToSqr(at)<9))result.add(at);
        }
        return result;
    }
    public static Vec3 contact(EvaUnit01Entity eva,UNTransportEntity cart)
    {
        if(cart==null||!cart.groundCart()||cart.cargoEntityId()!=eva.getId()||cart.targetDeployment()<.99F)return null;
        var actual=EvaBodyPose.carrierBearingPointsR40(eva,EvaBodyPose.sample(eva,0));
        for(var p:actual)
        {
            var v=new Vector3f((float)p.x,(float)p.y,(float)p.z).rotateY((180-eva.getYRot())*Mth.DEG_TO_RAD);
            Vec3 world=eva.position().add(v.x,v.y,v.z);
            for(var pad:pads(eva))
            {
                var q=new Vector3f((float)pad.x,(float)pad.y,(float)pad.z).rotateY(-cart.getYRot()*Mth.DEG_TO_RAD);
                Vec3 top=cart.position().add(q.x,q.y,q.z);
                if(Math.abs(world.y-top.y)<.12&&world.subtract(top).horizontalDistanceSqr()<4)return top;
            }
        }
        return null;
    }
    private UNReceivingCradleR40() {}
}
