package com.projectseele.entity;

import com.projectseele.util.QuaternionChannelsR45;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import java.util.Random;

/** Frozen body snapshots must preserve axes around all supported knee/hip orientations. */
public final class PoseSnapshotCodecR45Test
{
    private static Vector3f legacy(Quaternionf q)
    {
        return new Vector3f((float)Math.atan2(2*(q.w*q.x+q.y*q.z),1-2*(q.x*q.x+q.y*q.y)),
                (float)Math.asin(Math.max(-1,Math.min(1,2*(q.w*q.y-q.z*q.x)))),
                (float)Math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)));
    }
    public static void main(String[] args)
    {
        var random=new Random(45);double oldMaximum=0,newMaximum=0;
        var rig=java.util.Map.of("root",new EvaBodyPose.Bone("root",null,new Vector3f(),new Quaternionf()));
        for(int i=0;i<2400;i++)
        {
            float x=(random.nextFloat()*2-1)*(float)Math.PI,z=(random.nextFloat()*2-1)*(float)Math.PI;
            float y=i<1200?(i%2==0?1:-1)*(float)(Math.PI/2+(i%3-1)*1e-6):(random.nextFloat()*2-1)*(float)Math.PI;
            var q=new Quaternionf().rotationZYX(z,y,x);var old=legacy(q);
            var snapshot=new EvaBodyPose.Sample(rig);snapshot.rotations.put("root",new Quaternionf(q));
            snapshot.positions.put("root",new Vector3f(x,y,z));
            var restored=new EvaBodyPose.Sample(rig);EvaPoseSnapshotR50.decode(EvaPoseSnapshotR50.encode(snapshot),restored);
            if(restored.positions.get("root").distance(snapshot.positions.get("root"))>1e-6F)
                throw new AssertionError("Snapshot root translation changed");
            var bad=new Quaternionf().rotationZYX(old.z,old.y,old.x);var good=restored.rotations.get("root");
            for(var axis:new Vector3f[]{new Vector3f(1,0,0),new Vector3f(0,1,0),new Vector3f(0,0,1)})
            {
                oldMaximum=Math.max(oldMaximum,q.transform(new Vector3f(axis)).distance(bad.transform(new Vector3f(axis))));
                newMaximum=Math.max(newMaximum,q.transform(new Vector3f(axis)).distance(good.transform(new Vector3f(axis))));
            }
        }
        if(oldMaximum<.1)throw new AssertionError("Legacy negative control did not reproduce pose corruption");
        if(newMaximum>2e-4)throw new AssertionError("Snapshot axes changed: "+newMaximum);
        System.out.println("Pose snapshot common codec: legacy maximum axis error="+oldMaximum+"; shared codec="+newMaximum+"; 2400 orientations PASS");
    }
}
