package com.projectseele.world;

import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

/** A stationary original socket must not acquire a fictitious angle on reload. */
public final class RigidTransformPrecisionR52Test
{
    public static void main(String[] args)
    {
        int checks=0;
        for(int i=1;i<=720;i++)
        {
            var q=new Quaternionf().rotationXYZ(i*.019F,i*.027F,i*.043F);
            var a=RigidTransform.of(new Vec3(2000.25,-706,328.5),q);
            var b=new RigidTransform(a.translation(),a.qx(),a.qy(),a.qz(),a.qw());
            if(a.rotationErrorDegrees(a)>1e-5||a.rotationErrorDegrees(b)>1e-5)
                throw new AssertionError("False angle for unchanged original quaternion "+i);
            var opposite=new RigidTransform(a.translation(),-a.qx(),-a.qy(),-a.qz(),-a.qw());
            if(a.rotationErrorDegrees(opposite)>1e-5)throw new AssertionError("q/-q discontinuity");
            checks+=3;
        }
        for(double degrees:new double[]{.001,.01,.04,1,45,90,179.9,180})
        {
            double half=Math.toRadians(degrees)*.5;
            var a=RigidTransform.identity();var b=RigidTransform.of(Vec3.ZERO,new Quaternionf(0,(float)Math.sin(half),0,(float)Math.cos(half)));
            if(Math.abs(a.rotationErrorDegrees(b)-degrees)>2e-5)throw new AssertionError("Real angular displacement changed: "+degrees+" -> "+a.rotationErrorDegrees(b));
            checks++;
        }
        System.out.println("RigidTransformPrecisionR52Test PASS "+checks+" unchanged/sign/reload/real-rotation checks");
    }
}
