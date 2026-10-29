package com.projectseele.entity;

import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Installed cannon frame and target sector math only; no world/entity construction. */
public final class FixedCannonAimR54Test
{
    public static void main(String[] args)
    {
        var g=new YashimaCannonGeometryR52.Geometry(new Vec3(9.377162,10.523421,29.045622),
                new Quaternionf(-.3302944F,.70686644F,-.6172466F,-.10125217F).normalize(),8,
                new AABB(-1,0,-1,1,8,1),new Vec3(.010581753,6.80000013,.24999977),new Vec3(0,-1,0),
                new Vec3(-.080359111,.076456793,-.209464857),new Vec3(-.131789107,5.763069167,.61175522),new Vec3(.020904999,6.305188656,.509781539));
        var origin=new Vec3(-1242.5,174,-1400.5);var pivot=g.point(origin,new Quaternionf(),g.pivot());
        double maximumMiss=0;
        for(var centre:new Vec3[]{new Vec3(30.5,114,355.5),new Vec3(30.5,153.058,450.92),new Vec3(30.5,193.058,450.92)})
        {
            var axis=centre.subtract(pivot).normalize();double yaw=Math.atan2(axis.x,axis.z),pitch=Math.asin(axis.y);
            for(int x=-3;x<=3;x+=3)for(int y=-3;y<=3;y+=3)
            {
                var target=pivot.add(direction(yaw+Math.toRadians(x),pitch+Math.toRadians(y)).scale(2200));
                var q=YashimaCannonGeometryR52.aimWithinSectorR54(g,origin,target,centre);
                var toTarget=target.subtract(g.point(origin,q,g.muzzle()));var bore=g.boreWorld(q);
                double miss=toTarget.cross(bore).length();maximumMiss=Math.max(maximumMiss,miss);
                require(toTarget.dot(bore)>0&&miss<.02,"Playable target ray misses: "+miss);
            }
            for(var target:new Vec3[]{pivot.add(0,2000,0),pivot.add(0,-2000,0),pivot.subtract(axis.scale(2000)),pivot})
            {
                var q=YashimaCannonGeometryR52.aimWithinSectorR54(g,origin,target,centre);var bore=g.boreWorld(q);
                double delta=Math.atan2(Math.sin(Math.atan2(bore.x,bore.z)-yaw),Math.cos(Math.atan2(bore.x,bore.z)-yaw));
                require(Float.isFinite(q.lengthSquared())&&Math.abs(delta)<=Math.toRadians(12.001)
                        &&Math.abs(Math.asin(bore.y)-pitch)<=Math.toRadians(8.001),"Barrel escaped target sector");
            }
        }
        var grip=new EvaAnatomicalHandsR45.Grip(new Vector3f(1,2,3),new Vector3f(0,1,0),new Vector3f(1,0,0),new Quaternionf(),new Vector3f());
        for(int i=0;i<100;i++)
        {
            var current=new Quaternionf().rotationXYZ(i*.13F,i*.07F,i*.17F);
            var desired=new Vector3f((float)Math.sin(i),.3F,(float)Math.cos(i)).normalize();
            var fitted=FixedCannonPoseR52.palmOrientationR54(current,grip,desired);
            require(fitted.transform(new Vector3f(0,0,1)).dot(desired)>.99999F,"Measured palm normal not fitted");
        }
        System.out.println("PASS: target and deliberate misses remain aimable; up/down/rear cannot overturn; measured palm orientations fit. Max target-ray miss="+maximumMiss);
    }
    private static Vec3 direction(double yaw,double pitch)
    {return new Vec3(Math.sin(yaw)*Math.cos(pitch),Math.sin(pitch),Math.cos(yaw)*Math.cos(pitch));}
    private static void require(boolean valid,String message){if(!valid)throw new AssertionError(message);}
}
