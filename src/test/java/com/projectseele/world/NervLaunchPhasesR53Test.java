package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.nbt.CompoundTag;

/** Explicit parser/clock/save-load contracts only; no world or mechanical admission. */
public final class NervLaunchPhasesR53Test
{
    private static int checks;
    private static void check(boolean value,String why){checks++;if(!value)throw new AssertionError(why);}
    private static void rejected(Runnable operation,String why){try{operation.run();}catch(IllegalArgumentException|IllegalStateException expected){checks++;return;}throw new AssertionError(why);}
    private static JsonObject object(String file)throws Exception{return JsonParser.parseString(Files.readString(Path.of(file))).getAsJsonObject();}
    public static void main(String[] args)throws Exception
    {
        var fixture=object(args[0]);var directory=NervRouteDirectoryR52.parse(fixture);directory.validateCompactLaunchContractR52();
        check(directory.routes().size()==18,"All original routes required");
        for(var route:directory.routes().values())
        {
            var data=new CompoundTag();var task=UUID.randomUUID();var run=NervLaunchPhasesR53.current(data,task,directory,route,0);double total=directory.routeLength(route),bank=directory.readyDistanceR53(route);
            data.putBoolean("ContinuousAutoLaunchR52",true);check(run.stop()==bank,"Queued launch skipped bank stop");check(run.speed().cruiseMps()==(route.recovery()?180:4),"Wrong first phase speed");
            var speed=run.speed();var clock=new NervMechanicalTravelR52.ContinuousClock(new NervMechanicalTravelR52.ContinuousProfile(0,run.stop(),speed.cruiseMps(),speed.accelerationMps2(),speed.decelerationMps2()),0);
            while(!clock.complete()){clock=clock.next();check(clock.distance()<=bank&&clock.speed()<=speed.cruiseMps()+1e-9,"Phase overshot its stopped bank / cruise limit");}
            NervMechanicalTravelR52.rememberContinuous(data,route.id(),directory.fingerprint(),total,clock);
            check(clock.speed()==0,"Bank failed to stop");var reload=data.copy();check(NervLaunchPhasesR53.current(reload,task,directory,route,bank).equals(run),"Cold resume changed original phase");
            var second=NervLaunchPhasesR53.crossStoppedBank(reload,task,directory,route,bank);check(second.stop()==total&&second.speed().cruiseMps()==(route.recovery()?4:180),"Second phase profile mismatch");
            var next=NervMechanicalTravelR52.continuousClock(reload,route.id(),directory.fingerprint(),bank,total,total,second.speed().cruiseMps(),second.speed().accelerationMps2(),second.speed().decelerationMps2());check(next.speed()==0,"Bank switch carried speed across heading discontinuity");
            check(NervLaunchPhasesR53.firstLaunchCommit(reload,second,bank,next.next().distance(),bank)==!route.recovery(),"First-launch-only feedback mismatch");
            check(!NervLaunchPhasesR53.firstLaunchCommit(reload.copy(),second,bank,next.next().distance(),bank),"Reload repeated electrical burst");
            check(!NervLaunchPhasesR53.firstLaunchCommit(data.copy(),second,bank+1,bank+2,bank),"Mid-route resumed task fabricated delayed burst");
            var bad=data.copy();bad.getCompound("ContinuousClockR52").putDouble("SpeedMps",1);rejected(()->NervLaunchPhasesR53.crossStoppedBank(bad,task,directory,route,bank),"Nonzero saved speed passed stop");
            rejected(()->NervLaunchPhasesR53.current(data,UUID.randomUUID(),directory,route,bank),"Different task stole phase");
            rejected(()->NervLaunchPhasesR53.current(new CompoundTag(),task,directory,route,bank+1),"Missing moved phase silently inferred");
            if(!route.recovery())
            {
                var back=directory.routes().values().stream().filter(r->r.reverseOf().equals(route.id())).findFirst().orElseThrow();var backTask=UUID.randomUUID();double backBank=directory.readyDistanceR53(back);var resume=new CompoundTag();resume.putBoolean("ContinuousCheckedStartR52",true);resume.putUUID("HeadReturnFromTaskR53",task);resume.putString("HeadReturnFromRouteR53",route.id());var evidence=new CompoundTag();evidence.putUUID("SourceTask",task);evidence.putUUID("TargetTask",backTask);evidence.putString("Directory",directory.fingerprint());evidence.putString("SourceRoute",route.id());evidence.putString("TargetRoute",back.id());evidence.putDouble("TargetDistance",backBank);evidence.put("Clock",data.getCompound("ContinuousClockR52").copy());evidence.put("SourcePhase",data.getCompound(NervLaunchPhasesR53.KEY).copy());resume.put("PreviousBankStopR53",evidence);NervLaunchPhasesR53.verifyStoppedBank(resume,backTask,directory,back,backBank);
                var damaged=resume.copy();damaged.getCompound("PreviousBankStopR53").getCompound("Clock").putDouble("CruiseMps",999);rejected(()->NervLaunchPhasesR53.verifyStoppedBank(damaged,backTask,directory,back,backBank),"Cancelled clock changed source speed authority");
                var continued=NervLaunchPhasesR53.crossStoppedBank(resume,backTask,directory,back,backBank);check(continued.stage()==NervLaunchPhasesR53.Stage.RETURN_TRANSFER&&continued.speed().cruiseMps()==4,"Retained actual bank stop did not resume slow original return");
            }
        }
        var missing=fixture.deepCopy();missing.getAsJsonArray("routes").get(0).getAsJsonObject().getAsJsonObject("motion_profile").remove("phase_version");rejected(()->NervRouteDirectoryR52.parse(missing),"Missing explicit phase accepted");
        var flat=fixture.deepCopy();var leg=flat.getAsJsonArray("legs").asList().stream().map(JsonElement::getAsJsonObject).filter(v->v.get("from").getAsString().equals("unit0/bank2")&&v.has("centre_curve")).findFirst().orElseThrow();var controls=leg.getAsJsonObject("centre_curve").getAsJsonArray("segments").get(0).getAsJsonObject().getAsJsonArray("controls");controls.get(1).getAsJsonArray().set(1,controls.get(0).getAsJsonArray().get(1));rejected(()->NervRouteDirectoryR52.parse(flat),"Launch horizontal or zero derivative accepted");
        var wrong=fixture.deepCopy();wrong.getAsJsonArray("routes").get(0).getAsJsonObject().getAsJsonObject("motion_profile").addProperty("ready_node","unit0/bay");rejected(()->NervRouteDirectoryR52.parse(wrong),"BAY masqueraded as ready bank");
        var bankTask=UUID.randomUUID();var head=NervBankHeadTransferR53.begin(bankTask,directory.fingerprint(),"unit0/departure/1",new net.minecraft.world.phys.Vec3(0,0,-1),new net.minecraft.world.phys.Vec3(0,1,0));
        for(int point=1;point<120;point++){var state=head.copy();for(int i=0;i<point;i++)state=NervBankHeadTransferR53.advance(state,1,i);var pose=NervBankHeadTransferR53.pose(state,point);check(NervBankHeadTransferR53.pose(state.copy(),point).equals(pose),"Cold head preparation changed actual pose");for(int i=point;i>0;i--)state=NervBankHeadTransferR53.advance(state,-1,point+i);check(state.getInt("Clock")==0&&state.getBoolean("AbortedToStart")&&!NervBankHeadTransferR53.unfinished(state)&&state.getUUID("Task").equals(bankTask),"Cancelled local motion lost original task or stop");check(NervBankHeadTransferR53.pose(state,0).slide()==0,"Cancelled local fork did not return exactly");}
        rejected(()->NervBankHeadTransferR53.advance(head,-1,0),"Negative local clock accepted");
        rejected(()->NervBankHeadTransferR53.sample(new net.minecraft.world.phys.Vec3(Double.NaN,0,0),new net.minecraft.world.phys.Vec3(0,1,0),0),"Nonfinite persisted axis accepted");
        System.out.println("R53 phased launch PASS checks="+checks+"; 18 parser-only routes, persisted zero-speed bank boundary, slow prelaunch/return, launch-only single feedback; no world/game/geometry acceptance");
    }
}
