package com.projectseele.world;

import com.google.gson.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

/** Small pure geometry regressions; no actor, registry or World is created. */
public final class NervCentrelineCurveR52Test
{
    private static int checks;
    private static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    private static void rejects(Runnable work,String why){boolean failed=false;try{work.run();}catch(IllegalArgumentException expected){failed=true;}check(failed,why);}
    private static JsonObject named(JsonArray array,String id){for(var v:array){var o=v.getAsJsonObject();if(o.get("id").getAsString().equals(id))return o;}throw new AssertionError(id);}
    private static JsonArray xyz(double... values){var result=new JsonArray();for(double v:values)result.add(v);return result;}
    private static NervCentrelineCurveR52 curve(Vec3... points){return new NervCentrelineCurveR52(List.of(new NervCentrelineCurveR52.Segment(points.length==2?NervCentrelineCurveR52.Type.LINE:NervCentrelineCurveR52.Type.QUINTIC_BEZIER,List.of(points))));}
    private static JsonObject profile(String ready){var p=new JsonObject();p.addProperty("type","continuous_upright");p.addProperty("cruise_mps",30);p.addProperty("acceleration_mps2",8);p.addProperty("deceleration_mps2",10);p.addProperty("ready_node",ready);return p;}
    private static JsonObject fixture()
    {
        var root=NervRouteCoreR52Test.rootFixtureForNativeBindingTest();
        var ramp=new JsonObject();ramp.addProperty("flat_before",1);ramp.addProperty("slope_run",8);ramp.addProperty("blend",1);
        named(root.getAsJsonArray("legs"),"original1").add("ramp_profile",ramp.deepCopy());named(root.getAsJsonArray("legs"),"reverse_original1").add("ramp_profile",ramp.deepCopy());
        var bridge=curve(new Vec3(10,1,10),new Vec3(10,1,12),new Vec3(10,1,14),new Vec3(10,-3,20),new Vec3(10,-1,20),new Vec3(10,1,20));
        named(root.getAsJsonArray("legs"),"bridge12_1").add("centre_curve",bridge.toJson());named(root.getAsJsonArray("legs"),"reverse_bridge12_1").add("centre_curve",bridge.reversed().toJson());
        named(root.getAsJsonArray("routes"),"depart_b2l1").add("motion_profile",profile("dock1_1"));named(root.getAsJsonArray("routes"),"return_b2l1").add("motion_profile",profile("dock1_1"));return root;
    }
    public static void main(String[] args)
    {
        var line=curve(new Vec3(0,0,0),new Vec3(3,4,0));check(Math.abs(line.length()-5)<=line.lengthErrorBound(),"Line length escaped certified bracket");check(line.point(.4).distanceTo(new Vec3(1.2,1.6,0))<=line.pointErrorBound(),"Actual line arc sample changed");check(line.pointErrorBound()>0,"Numeric sampling was incorrectly labelled exact");
        var uneven=curve(Vec3.ZERO,new Vec3(.1,0,0),new Vec3(.6,0,0),new Vec3(1.2,0,0),new Vec3(2.4,0,0),new Vec3(5,0,0));
        for(int i=0;i<=20;i++)check(Math.abs(uneven.point(i/20D).x-5*i/20D)<=uneven.pointErrorBound(),"Quintic used raw polynomial parameter as arc length");
        rejects(()->curve(Vec3.ZERO,Vec3.ZERO,new Vec3(1,0,0),new Vec3(2,0,0),new Vec3(3,0,0),new Vec3(4,0,0)),"Zero endpoint derivative accepted");
        rejects(()->curve(Vec3.ZERO,new Vec3(1,0,0),new Vec3(1,0,0),new Vec3(-1,0,0),new Vec3(-1,0,0),Vec3.ZERO),"Interior zero derivative accepted");
        rejects(()->new NervCentrelineCurveR52(List.of(new NervCentrelineCurveR52.Segment(NervCentrelineCurveR52.Type.LINE,List.of(Vec3.ZERO,new Vec3(1,0,0))),new NervCentrelineCurveR52.Segment(NervCentrelineCurveR52.Type.LINE,List.of(new Vec3(1,0,0),new Vec3(1,1,0))))),"Disconnected tangent accepted");
        var document=fixture();var directory=NervRouteDirectoryR52.parse(document);var route=directory.route("depart_b2l1");var bridge=directory.leg("bridge12_1").centreCurve();var back=bridge.reversed();
        check(route.continuousUpright()&&route.cruiseMps()==30&&route.readyNode().equals("dock1_1"),"Explicit continuous speed/profile lost");
        check(NervCentrelineCurveR52.parse(bridge.toJson()).point(.37).distanceTo(bridge.point(.37))==0,"Portable client controls changed actual sampler");
        for(int i=0;i<=12;i++)check(bridge.point(i/12D).distanceTo(back.point(1-i/12D))<=bridge.pointErrorBound()+back.pointErrorBound(),"Reverse arc geometry differs");
        var binding=new FootSupportFrameR52.Binding(new Vec3(-1,-2,.5),new Vec3(1,-2,.5),RigidTransform.identity());
        var path=new DirectoryTrajectoryR52(directory,directory.leg("bridge12_1"),binding,.07,.94);check(path.pureTranslation()&&path.angularTravel()==0,"Continuous curve rotated the EVA");check(path.samplingErrorBound()>0&&path.translationSecondDerivativeBound()>0,"Inverse mapping or curve curvature omitted from sweep proof");
        double radius=100;int divisions=path.divisions(radius,.002);double error=path.error(radius,divisions);check(error<=.002,"Curve subdivisions exceed positive query budget");
        for(int i=0;i<divisions;i++){var a=path.sample(i/(double)divisions);var b=path.sample((i+1D)/divisions);for(int k=0;k<=3;k++){double f=k/3D;var value=path.sample((i+f)/divisions);check(value.evaRoot().translation().distanceTo(a.evaRoot().translation().lerp(b.evaRoot().translation(),f))<=error,"Actual curve escaped certified chord+inverse error");check(value.evaRoot().rotationErrorDegrees(RigidTransform.identity())==0,"Prepared rotation changed");check(value.leftContact().distanceTo(value.evaRoot().transformPoint(binding.leftFoot()))<1e-12,"Actual original left contact moved relative to EVA");}}
        rejects(()->path.divisions(radius,path.roundoffBound(radius)/2),"Error budget below inverse numeric floor accepted");
        var original=directory.leg("original1");var old=NervRouteDirectoryR52.parse(NervRouteCoreR52Test.rootFixtureForNativeBindingTest());
        for(int i=0;i<=20;i++){double f=i/20D;var expected=new Vec3(10,original.rampProfile().heightFraction(10,f),10D*(float)f);check(directory.centrePoint(original,f).distanceTo(expected)<1e-12,"Original ramp position formula changed");double distance=directory.legDistance(original,f);check(Math.abs(directory.legFractionAtDistance(original,distance)-f)<1e-12,"Original ramp distance/parameter roundtrip failed");}
        check(directory.legLength(original)>=old.legLength(old.leg("original1"))-1e-6,"Original grade arc lost length");
        double join=directory.legLength(original);var located=directory.locateDistance(route,join);check(located.legIndex()==1&&located.fraction()==0,"Exact route join did not preserve outgoing segment progress");
        var slices=directory.routeSlices(route,join-.25,join+.25,binding);check(slices.size()==2&&slices.get(0).sample(1).evaRoot().translation().distanceTo(slices.get(1).sample(0).evaRoot().translation())<1e-12,"Cross-leg sweep intervals are disconnected");
        check(directory.routeSpans(route,join,join).size()==1,"Actual zero-distance hold lost its geometry sample");
        var portable=DirectoryTrajectoryR52.decodePortableR52(DirectoryTrajectoryR52.encodePortableR52(slices));check(Math.abs(portable.lengthMetres()-.5)<1e-12,"Portable window lost shared distance");
        for(int i=0;i<=20;i++){double m=.5*i/20D;var pos=directory.locateDistance(route,join-.25+m);var actual=directory.sample(directory.leg(route.legs().get(pos.legIndex())),pos.fraction(),binding).evaRoot();var decoded=portable.sample(m);check(decoded.translation().distanceTo(actual.translation())<1e-9&&decoded.rotationErrorDegrees(actual)==0,"Portable controls/ramp changed accepted rigid sample");}
        check(portable.tangent(0).distanceTo(directory.tangent(original,slices.get(0).fromFraction()))<1e-12,"Portable original ramp tangent changed");
        var reverse=directory.route("return_b2l1");double reverseJoin=directory.legLength(directory.leg(reverse.legs().get(0)));var reverseWindow=DirectoryTrajectoryR52.decodePortableR52(DirectoryTrajectoryR52.encodePortableR52(directory.routeSlices(reverse,reverseJoin,reverseJoin+.25,binding)));check(reverseWindow.tangent(0).distanceTo(directory.tangent(directory.leg("bridge12_1"),1))<1e-12,"Recovery head flipped instead of retaining canonical forward tangent");
        var mixed=new NervCentrelineCurveR52(List.of(new NervCentrelineCurveR52.Segment(NervCentrelineCurveR52.Type.LINE,List.of(Vec3.ZERO,new Vec3(0,0,10))),new NervCentrelineCurveR52.Segment(NervCentrelineCurveR52.Type.QUINTIC_BEZIER,List.of(new Vec3(0,0,10),new Vec3(0,0,11),new Vec3(0,0,12),new Vec3(4,0,14),new Vec3(5,0,14),new Vec3(6,0,14)))));
        check(mixed.curvatureBound(0,.1)<mixed.curvatureBound()*.01,"Distant small corner polluted the straight interval curvature bound");
        var changedOrientation=document.deepCopy();named(changedOrientation.getAsJsonArray("nodes"),"exit_b2l1").getAsJsonObject("foot_frame").add("quaternion_xyzw",xyz(0,Math.sqrt(.5),0,Math.sqrt(.5)));rejects(()->NervRouteDirectoryR52.parse(changedOrientation),"Continuous route changed prepared orientation");
        var bad=document.deepCopy();named(bad.getAsJsonArray("routes"),"depart_b2l1").getAsJsonObject("motion_profile").addProperty("cruise_mps",0);var invalidSpeed=bad;rejects(()->NervRouteDirectoryR52.parse(invalidSpeed),"Zero cruise speed accepted");
        var noProfile=document.deepCopy();named(noProfile.getAsJsonArray("routes"),"depart_b2l1").addProperty("motion_profile","continuous_upright");rejects(()->NervRouteDirectoryR52.parse(noProfile),"Missing explicit profile object accepted");
        if(args.length>0) {
            try {var root=JsonParser.parseString(java.nio.file.Files.readString(java.nio.file.Path.of(args[0]))).getAsJsonObject();var actual=NervRouteDirectoryR52.parse(root);double longest=0,maxInverse=0,maxCurvature=0;var ids=new HashSet<String>();for(var r:actual.routes().values()){check(r.continuousUpright(),"Actual Root route is not continuous");longest=Math.max(longest,actual.routeLength(r));for(String id:r.legs()){if(!ids.add(id))continue;var l=actual.leg(id);if(l.centreCurve()!=null){maxInverse=Math.max(maxInverse,l.centreCurve().pointErrorBound());maxCurvature=Math.max(maxCurvature,l.centreCurve().curvatureBound());}for(double f:new double[]{0,.17,.5,.83,1}){var point=actual.centrePoint(l,f);check(Double.isFinite(point.lengthSqr()),"Actual Root curve point is not finite");double metres=actual.legDistance(l,f);check(Math.abs(actual.legFractionAtDistance(l,metres)-f)<1e-10,"Actual Root distance conversion failed");}}}System.out.println("ACTUAL_ROOT_DESIGN_PARSER_PASS routes="+actual.routes().size()+" legs="+ids.size()+" longest_m="+longest+" inverse_bound_m="+maxInverse+" curvature_bound="+maxCurvature+" installed="+actual.installed()+"; not clearance/native acceptance");}
            catch(java.io.IOException failure){throw new RuntimeException(failure);}
        }
        System.out.println("PASS continuous centre curves: "+checks+" geometry/source checks; no World/game/native acceptance; subdivisions="+divisions+" bound="+error+" inverse="+bridge.pointErrorBound());
    }
    private NervCentrelineCurveR52Test(){}
}
