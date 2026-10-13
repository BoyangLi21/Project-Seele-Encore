package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.nbt.*;
import net.minecraft.world.phys.Vec3;
import com.projectseele.world.NervMechanicalTravelR52.*;
import static com.projectseele.world.NervMechanicalTravelR52.*;

/** Real Root curve inputs and compressed clock round trips; no native/world acceptance. */
public final class NervContinuousTravelR52Test {
    private static int checks;
    private static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    private static void reject(Runnable fn,String why){boolean failed=false;try{fn.run();}catch(RuntimeException expected){failed=true;}check(failed,why);}
    private static CompoundTag cold(CompoundTag data)throws Exception{var bytes=new ByteArrayOutputStream();NbtIo.writeCompressed(data,bytes);return NbtIo.readCompressed(new ByteArrayInputStream(bytes.toByteArray()));}
    public static void main(String[] args)throws Exception {
        for(double metres:new double[]{.5,5,270,1200,6000}) {
            var profile=new ContinuousProfile(0,metres,180,120,120);double previous=0;
            for(long ticks=0;ticks<Math.ceil(profile.durationSeconds()*20)+2;ticks++) {
                var clock=new ContinuousClock(profile,ticks);double d=clock.distance();check(d>=previous&&d<=metres,"Distance reversed or overran true endpoint");check(clock.speed()>=0&&clock.speed()<=180,"Invalid continuous velocity");previous=d;
                var data=new CompoundTag();rememberContinuous(data,"whole/route","a".repeat(64),metres,clock);var restored=continuousClock(cold(data),"whole/route","a".repeat(64),d,metres,metres,180,120,120);check(restored.equals(clock),"Compressed reload changed distance/speed clock");
                double half=profile.distanceAt(ticks+.5);check(half>=d&&half<=profile.distanceAt(ticks+1),"Partial tick left its accepted actual curve window");
            }
            check(previous==metres&&profile.speedAt(Math.ceil(profile.durationSeconds()*20))==0,"Run did not stop exactly at final endpoint");
        }
        var first=new ContinuousClock(new ContinuousProfile(0,400,180,120,120),30);var queued=new CompoundTag();rememberContinuous(queued,"queue","b".repeat(64),2000,first);extendContinuousR52(queued,"queue","b".repeat(64),2000);var extended=continuousClock(queued,"queue","b".repeat(64),first.distance(),2000,2000,180,120,120);check(extended.distance()==first.distance()&&extended.speed()==first.speed(),"Queued launch reset accepted distance or velocity");check(extended.profile().speedAt(.01)>=first.speed(),"Queued launch inserted a leg-stop");
        var moving=new ContinuousClock(new ContinuousProfile(0,2000,180,120,120),45);var braking=new CompoundTag();rememberContinuous(braking,"brake","c".repeat(64),2000,moving);brakeContinuousR52(braking,"brake","c".repeat(64),2000,"CANCEL");var b0=continuousClock(braking,"brake","c".repeat(64),moving.distance(),2000,braking.getCompound("ContinuousClockR52").getDouble("ToMetres"),180,120,120);check(b0.speed()==moving.speed()&&b0.distance()==moving.distance(),"Cancel stopped instantaneously or changed current point");check(Math.abs(b0.profile().toMetres()-moving.distance()-brakingDistanceR52(moving.speed(),120))<1e-6,"Cancel used no actual stopping distance");double priorSpeed=b0.speed();for(long t=1;t<=Math.ceil(b0.profile().durationSeconds()*20);t++){var decel=new ContinuousClock(b0.profile(),t);check(decel.speed()<=priorSpeed&&priorSpeed-decel.speed()<=6+1e-8,"Actual braking force or monotonic speed changed");priorSpeed=decel.speed();rememberContinuous(braking,"brake","c".repeat(64),2000,decel);var restored=continuousClock(cold(braking),"brake","c".repeat(64),decel.distance(),2000,decel.profile().toMetres(),180,120,120);check(restored.equals(decel),"Braking speed/distance lost on cold NBT reload");}check(priorSpeed==0,"Cancelled original did not decelerate to rest");
        var stopped=new ContinuousClock(new ContinuousProfile(0,400,180,120,120),500);var manual=new CompoundTag();rememberContinuous(manual,"queue","b".repeat(64),2000,stopped);extendContinuousR52(manual,"queue","b".repeat(64),2000);check(continuousClock(manual,"queue","b".repeat(64),400,2000,2000,180,120,120).speed()==0,"Explicit READY launch did not start at rest");
        reject(()->continuousClock(new CompoundTag(),"moved","b".repeat(64),80,2000,2000,180,120,120),"Missing moved clock was silently rebased");
        var forged=queued.copy();forged.getCompound("ContinuousClockR52").putDouble("DistanceMetres",-1);reject(()->continuousClock(forged,"queue","b".repeat(64),first.distance(),2000,2000,180,120,120),"Forged persisted scalar distance accepted");reject(()->continuousClock(queued,"foreign","b".repeat(64),first.distance(),2000,2000,180,120,120),"Foreign route reused the actual clock");
        check(NervRouteRuntimeStateR52.allowed(NervRouteRuntimeStateR52.Phase.PREPARING,NervRouteRuntimeStateR52.Phase.DEPARTING),"PREP+LAUNCH requires no unnecessary READY stop");
        byte[] input=Files.readAllBytes(Path.of(args[0]));String sha=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(input));var fixture=JsonParser.parseString(new String(input,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();check(fixture.get("status").getAsString().equals("design"),"Expected actual uninstalled Root design");fixture.addProperty("status","installed");fixture.addProperty("installation_receipt_sha256","0".repeat(64));var directory=NervRouteDirectoryR52.parse(fixture);
        var binding=new FootSupportFrameR52.Binding(new Vec3(-3,0,0),new Vec3(3,0,0),RigidTransform.identity());int crossings=0;
        for(var route:directory.routes().values()) {
            check(route.continuousUpright(),"Actual selected route lacks explicit profile");
            if(!route.recovery()){var reverse=directory.route(directory.ports().get(route.port()).reverseRoutes().get(route.variant()));for(int i=0;i<route.legs().size();i++)for(double fraction:new double[]{0,.27,.5,.93,1}){var fwd=directory.sample(directory.leg(route.legs().get(i)),fraction,binding).evaRoot();var back=directory.sample(directory.leg(reverse.legs().get(reverse.legs().size()-1-i)),1-fraction,binding).evaRoot();check(fwd.translation().distanceTo(back.translation())<.001&&fwd.rotationErrorDegrees(back)<.0001,"Cancelled saved point cannot mirror to exact reverse source");}}double length=directory.routeLength(route);var profile=new ContinuousProfile(0,length,route.cruiseMps(),route.accelerationMps2(),route.decelerationMps2());
            for(int i=1;i<route.legs().size();i++) {
                double edge=directory.routeDistance(route,i,0);double a=Math.max(0,edge-.05),b=Math.min(length,edge+.05);var paths=directory.routeSlices(route,a,b,binding);check(paths.size()==2,"Same tick boundary omitted one real subcurve");var portable=DirectoryTrajectoryR52.decodePortableR52(DirectoryTrajectoryR52.encodePortableR52(paths));check(Math.abs(portable.lengthMetres()-(b-a))<1e-6,"Cross-leg portable distance changed");check(portable.sample(0).translation().distanceTo(paths.get(0).sample(0).evaRoot().translation())<1e-5,"Window first live point differs");check(portable.sample(portable.lengthMetres()).translation().distanceTo(paths.get(1).sample(1).evaRoot().translation())<1e-5,"Window final committed point differs");double near=edge-a;check(portable.sample(near-1e-6).translation().distanceTo(portable.sample(near+1e-6).translation())<1e-4,"Cross-leg client curve jumps");crossings++;
            }
            for(long t=0;t<Math.ceil(profile.durationSeconds()*20);t++) {
                double a=profile.distanceAt(t),b=profile.distanceAt(t+1);var paths=directory.routeSlices(route,a,b,binding);var portable=DirectoryTrajectoryR52.decodePortableR52(DirectoryTrajectoryR52.encodePortableR52(paths));check(Math.abs(portable.lengthMetres()-(b-a))<1e-6,"Accepted route window length disagrees with one speed clock");
                for(double partial:new double[]{0,.5,1}) {double at=profile.distanceAt(t+partial);var pos=directory.locateDistance(route,at);var expected=directory.sample(directory.leg(route.legs().get(pos.legIndex())),pos.fraction(),binding).evaRoot();var decoded=portable.sample(Math.max(0,Math.min(portable.lengthMetres(),at-a)));check(decoded.translation().distanceTo(expected.translation())<.0001&&decoded.rotationErrorDegrees(expected)<.0001,"Client shared actual curve/distance differs from server");}
            }
        }
        System.out.println("R52 continuous actual-clock/codec PASS checks="+checks+" crossings="+crossings+" directory_design_sha="+sha+"; no native/world acceptance");
    }
}
