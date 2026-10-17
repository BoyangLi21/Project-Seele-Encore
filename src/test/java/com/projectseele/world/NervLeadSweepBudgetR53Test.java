package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.Vec3;

public final class NervLeadSweepBudgetR53Test {
    public static void main(String[] args)throws Exception {
        var bay=new RigidTransform(new Vec3(72.5,-1062,328.5),0,1,0,0);
        var spec=new NervServiceFootDriveR52.Spec(0,bay,bay,1.62,-1130);
        var shift=NervLegacyCarrierRideR52.class.getDeclaredMethod("leadShift",NervLegacyCarrierRideR52.LeadSampleR52.class,int.class);shift.setAccessible(true);
        var random=new Random(5322);int checks=0,oldTotal=0,newTotal=0;
        for(int trial=0;trial<400;trial++) {
            float a=trial<200?.895F+trial*.0005F:random.nextFloat();
            float b=Math.max(0,Math.min(1,a+(trial%2==0?.01F:-.01F)));
            var from=new NervLegacyCarrierRideR52.LeadSampleR52(spec,1,a,1);
            var to=new NervLegacyCarrierRideR52.LeadSampleR52(spec,1,b,1);
            int divisions=NervLegacyCarrierRideR52.leadSweepDivisionsR52(from,to);
            double certificate=NervLegacyCarrierRideR52.leadSweepErrorR52(from,to,divisions);
            oldTotal+=Math.max(a,b)<=.90?1:Math.max(16,(int)Math.ceil(Math.abs(b-a)*Math.sqrt(700000/(8*.001))));newTotal+=divisions;
            for(int n=0;n<divisions;n++) {
                double lo=n/(double)divisions,hi=(n+1D)/divisions;
                var left=(RigidTransform)shift.invoke(null,NervLegacyCarrierRideR52.interpolateLeadR52(from,to,lo),1);
                var right=(RigidTransform)shift.invoke(null,NervLegacyCarrierRideR52.interpolateLeadR52(from,to,hi),1);
                for(int sample=1;sample<16;sample++) {
                    double t=sample/16D;
                    var actual=(RigidTransform)shift.invoke(null,NervLegacyCarrierRideR52.interpolateLeadR52(from,to,lo+(hi-lo)*t),1);
                    double deviation=actual.translation().distanceTo(left.translation().lerp(right.translation(),t));
                    if(deviation>certificate)throw new AssertionError("Actual nested quintic leaves its curvature certificate: "+a+" -> "+b+" deviation="+deviation+" allowed="+certificate);
                    checks++;
                }
            }
        }
        if(newTotal>=oldTotal)throw new AssertionError("Measured lead sweep did not reduce subdivisions");
        // Every rendered telescopic source must be fixed-rotation and a
        // coordinate-wise affine fraction of the same certified shift.
        var from=new NervLegacyCarrierRideR52.LeadSampleR52(spec,1,.94F,1);
        var to=new NervLegacyCarrierRideR52.LeadSampleR52(spec,1,.95F,1);
        var A=NervLegacyCarrierRideR52.actualLeadPartsR52(from);var B=NervLegacyCarrierRideR52.actualLeadPartsR52(to);
        double bound=NervLegacyCarrierRideR52.leadSweepErrorR52(from,to,1);
        for(double t:new double[]{.125,.25,.375,.5,.625,.75,.875}) {
            var actual=NervLegacyCarrierRideR52.actualLeadPartsR52(NervLegacyCarrierRideR52.interpolateLeadR52(from,to,t));
            for(int i=0;i<A.size();i++) {
                var p=A.get(i);var q=B.get(i);var s=actual.get(i);
                if(p.mesh()!=q.mesh()||p.mesh()!=s.mesh()||!p.name().equals(s.name()))throw new AssertionError("Lead topology changed inside an interval");
                if(s.frame().translation().distanceTo(p.frame().translation().lerp(q.frame().translation(),t))>bound||s.frame().rotationErrorDegrees(p.frame())>1e-5)throw new AssertionError("Rendered member not covered: "+p.name());
                checks++;
            }
        }
        System.out.println("Lead curvature: "+checks+" actual-source checks; subdivisions "+oldTotal+" -> "+newTotal);
    }
}
