package com.projectseele.world;

import com.google.gson.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Pure bound/triangle regressions; no native world or clearance acceptance. */
public final class CarrierRearGuideBudgetR53Test
{
    private static int checks;
    private static void check(boolean value,String why){checks++;if(!value)throw new AssertionError(why);}
    private static void rejects(double curvature,double sampling)
    {boolean rejected=false;try{CarrierRearGuideMotionR53.continuousBudget(curvature,sampling);}catch(IllegalArgumentException expected){rejected=true;}check(rejected,"Invalid or unbounded source accepted: "+curvature+" / "+sampling);}
    private static void analyticRampWindows()
    {
        var json=NervRouteCoreR52Test.rootFixtureForNativeBindingTest();var ramp=new JsonObject();
        ramp.addProperty("flat_before",1);ramp.addProperty("slope_run",8);ramp.addProperty("blend",1);
        for(var raw:json.getAsJsonArray("legs")){var row=raw.getAsJsonObject();if(Set.of("original1","reverse_original1").contains(row.get("id").getAsString()))row.add("ramp_profile",ramp.deepCopy());}
        var directory=NervRouteDirectoryR52.parse(json);
        var binding=new FootSupportFrameR52.Binding(new Vec3(-1,0,0),new Vec3(1,0,0),RigidTransform.identity());
        for(String id:List.of("original1","reverse_original1"))
        {
            var path=new DirectoryTrajectoryR52(directory,directory.leg(id),binding,0,1);
            var slices=CarrierRearGuideMotionR53.rearMotionSlices(path);check(slices.size()==5,"Original ramp must retain both blends and all three affine intervals");
            double previous=0;int affine=0;
            for(var slice:slices)
            {
                check(slice.fromFraction()==previous,"Analytic windows leave a source gap");previous=slice.toFraction();
                if(!CarrierRearGuideMotionR53.affineOriginalRamp(slice))continue;affine++;
                var budget=CarrierRearGuideMotionR53.continuousBudget(slice,new CarrierRearGuideR53.Hardware(List.of(),List.of(),"fixture"));
                check(budget.divisions()==1&&budget.error()>=slice.samplingErrorBound()+.00002,"Affine source dropped roundoff or retained global curved subdivisions");
                var from=slice.sample(0).evaRoot().translation();var to=slice.sample(1).evaRoot().translation();
                for(int k=0;k<=8;k++)check(slice.sample(k/8D).evaRoot().translation().distanceTo(from.lerp(to,k/8D))<=budget.error(),"Actual affine ramp sample escaped the whole-window chord");
            }
            check(previous==1&&affine==3,"Forward/reverse source coverage or analytic classification changed");
            var aroundBlend=new DirectoryTrajectoryR52(directory,directory.leg(id),binding,.09,.21);
            check(!CarrierRearGuideMotionR53.affineOriginalRamp(aroundBlend),"A window crossing a rounded grade was mistaken for a straight chord");
        }
    }
    private static void fixedSourceSnapshot()
    {
        var frame=RigidTransform.identity();
        var lower=new NervRigidMeshSweepR52(new double[]{0,0,0,1,0,0,0,0,1});
        var upper=new NervRigidMeshSweepR52(new double[]{0,.00004,0,1,.00004,0,0,.00004,1});
        var moving=new NervLegacyCarrierRideR52.Piece("rear/source",lower,new double[0],frame,"fixture");
        var clear=new CarrierRearGuideMotionR53.FixedPair(0,moving,moving,upper,frame,0,"upper");
        var expanded=new CarrierRearGuideMotionR53.FixedPair(1,moving,moving,upper,frame,.00006,"original source error");
        check(CarrierRearGuideMotionR53.evaluateFixedSourceR53(List.of(clear)).isEmpty(),"Frozen separated pair rejected");
        check(CarrierRearGuideMotionR53.evaluateFixedSourceR53(List.of(clear,expanded)).equals("original source error"),
            "Frozen source check dropped interval error or leaked PairQuery across intervals");
        var crossing=new NervRigidMeshSweepR52(new double[]{.2,-1,.2,.2,1,.2,.8,0,.2});
        var obstacle=new CarrierRearGuideMotionR53.FixedPair(2,moving,moving,crossing,frame,0,"actual steel");
        check(CarrierRearGuideMotionR53.evaluateFixedSourceR53(List.of(obstacle)).equals("actual steel"),"True fixed triangle collision lost");
        check(NervGeometryWorkR53.submit(()->true,()->CarrierRearGuideMotionR53.evaluateFixedSourceR53(List.of(clear,obstacle))).join()
            .equals("actual steel"),"Worker snapshot differs from synchronous exact pair check");
        check(NervGeometryWorkR53.submit(()->true,()->CarrierRearGuideMotionR53.evaluateFixedSourceR53(List.of(clear))).join()
            .isEmpty(),"Independent worker PairQuery contaminated a clear source snapshot");
    }
    public static void main(String[] args)
    {
        analyticRampWindows();
        fixedSourceSnapshot();
        double sampling=.00004;check(sampling+.00002>=.00005,"Legacy total-budget rejection fixture lost");
        var straight=CarrierRearGuideMotionR53.continuousBudget(0,sampling);
        check(straight.divisions()==1&&straight.chord()==0&&straight.error()>=sampling+.00002,"Irreducible source error was dropped or subdivided");
        var curved=CarrierRearGuideMotionR53.continuousBudget(1,sampling);
        var precise=CarrierRearGuideMotionR53.continuousBudget(1,0);
        check(curved.divisions()==precise.divisions()&&curved.error()>=precise.error()+sampling,"Source uncertainty reduced the chord budget or escaped the final expansion");
        for(double curvature:new double[]{0,.000001,.01,1,100,1000})for(double source:new double[]{0,.00004,.001,.1})
        {
            var budget=CarrierRearGuideMotionR53.continuousBudget(curvature,source);
            check(budget.divisions()>=1&&budget.divisions()<=4096&&budget.chord()<=.00003,"Finite chord subdivision limit was ignored");
            double exactDeviation=curvature/(8D*budget.divisions()*budget.divisions());
            check(budget.chord()>=exactDeviation&&budget.rounding()>=source+.00002&&budget.error()>=source+.00002+exactDeviation,"Parabola midpoint/source uncertainty escaped outward certificate");
        }
        for(double invalid:new double[]{-1,Double.NaN,Double.POSITIVE_INFINITY}){rejects(invalid,0);rejects(1,invalid);}
        rejects(Double.MAX_VALUE,0);rejects(0,Double.MAX_VALUE);rejects(5000,0);
        var lower=new NervRigidMeshSweepR52(new double[]{0,0,0,1,0,0,0,0,1});
        var upper=new NervRigidMeshSweepR52(new double[]{0,.00004,0,1,.00004,0,0,.00004,1});var frame=RigidTransform.identity();
        check(!lower.intersects(frame,frame,upper,frame,frame,.003,Vec3.ZERO),"Separated exact triangles unexpectedly intersect");
        check(lower.intersects(frame,frame,upper,frame,frame,.003,new Vec3(straight.error(),straight.error(),straight.error())),"Irreducible uncertainty failed to reject a nearby obstacle");
        System.out.println("PASS rear curve budget checks="+checks+"; source error retained; no World/native clearance acceptance");
    }
    private CarrierRearGuideBudgetR53Test(){}
}
