package com.projectseele.world;

import java.util.Random;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

/** Repeated bay actuator checks retain exact geometry, without world memoization. */
public final class NervPrepareSourceReuseR54Test
{
    private static int checks;
    private static void check(boolean condition,String reason){checks++;if(!condition)throw new AssertionError(reason);}
    public static void main(String[] args)throws Exception
    {
        var mesh=new NervRigidMeshSweepR52(new double[]{-3,-2,-1,4,1,2,0,5,3});var random=new Random(54);
        for(int i=0;i<200;i++)
        {
            var a=RigidTransform.of(new Vec3(30,-1062+i,328),new Quaternionf().rotationY(random.nextFloat()));
            var b=RigidTransform.of(a.translation().add(0,.2,0),new Quaternionf().rotationYXZ(random.nextFloat(),.01F,0));
            double error=NervRigidMeshSweepR52.error(NervRigidMeshSweepR52.radius(mesh.bounds()),NervRigidMeshSweepR52.angular(a,b),1);
            var expected=NervRigidMeshSweepR52.transformed(mesh.bounds(),a).minmax(NervRigidMeshSweepR52.transformed(mesh.bounds(),b)).inflate(error,NervRigidMeshSweepR52.yawOnly(a,b)?0:error,error);
            var actual=mesh.envelope(a,b);
            check(actual.equals(expected),"cached envelope must equal original affine/rotation bound");
            check(actual==mesh.envelope(a,b),"same exact source interval reuses its immutable envelope");
        }
        var bay=new RigidTransform(new Vec3(72.5,-1062,328.5),0,1,0,0);
        var spec=new NervServiceFootDriveR52.Spec(0,bay,bay,1.62,-1130);
        var first=NervLegacyCarrierRideR52.actualLeadPartsR52(new NervLegacyCarrierRideR52.LeadSampleR52(spec,0,0,1));
        var later=NervLegacyCarrierRideR52.actualLeadPartsR52(new NervLegacyCarrierRideR52.LeadSampleR52(spec,0,0,999));
        check(first==later,"unchanged original lead pose ignores observation timestamp");
        var moved=NervLegacyCarrierRideR52.actualLeadPartsR52(new NervLegacyCarrierRideR52.LeadSampleR52(spec,1,.94F,1000));
        check(first!=moved&&first.size()==moved.size(),"new actual actuator pose retains topology but rebuilds frames");
        check(java.util.stream.IntStream.range(0,first.size()).anyMatch(i->!first.get(i).frame().equals(moved.get(i).frame())),"changed stroke cannot reuse old transforms");
        check(first==NervLegacyCarrierRideR52.actualLeadPartsR52(new NervLegacyCarrierRideR52.LeadSampleR52(spec,0,0,1001)),"original source pose remains reusable after another sample");
        System.out.println("PASS prepare immutable geometry reuse: "+checks+", original lead members="+first.size());
    }
}
