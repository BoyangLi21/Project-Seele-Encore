package com.projectseele.world;

import java.util.UUID;
import net.minecraft.nbt.CompoundTag;

/** Persisted phase authority for the same original task, independent of command timing. */
public final class NervLaunchPhasesR53
{
    public static final String KEY="MotionPhasesR53";
    public enum Stage { PRELAUNCH,ASCENT,DESCENT,RETURN_TRANSFER }
    public record Run(Stage stage,double stop,NervRouteDirectoryR52.SpeedProfile speed)
    {
        public boolean launch(){return stage==Stage.ASCENT;}
        public boolean bankStop(){return stage==Stage.PRELAUNCH||stage==Stage.DESCENT;}
    }
    public static Run current(CompoundTag data,UUID task,NervRouteDirectoryR52 directory,NervRouteDirectoryR52.Route route,double at)
    {
        if(!route.phased())throw new IllegalArgumentException("Explicit phased route required");
        var tag=data.getCompound(KEY);double ready=directory.readyDistanceR53(route),total=directory.routeLength(route);
        if(tag.isEmpty())
        {
            if(at!=0&&!data.getBoolean("ContinuousCheckedStartR52"))throw new IllegalStateException("Moved task lost its explicit motion phase receipt");
            if(data.getCompound("ContinuousClockR52").getDouble("SpeedMps")!=0)throw new IllegalStateException("New phase authority cannot replace a moving clock");
            tag=new CompoundTag();tag.putInt("Version",1);tag.putUUID("Task",task);tag.putString("Directory",directory.fingerprint());tag.putString("Route",route.id());
            Stage initial=route.recovery()?(at>ready?Stage.RETURN_TRANSFER:Stage.DESCENT):Stage.PRELAUNCH;
            tag.putString("Stage",initial.name());tag.putBoolean("NormalTransferR54",true);data.put(KEY,tag);
        }
        if(tag.getInt("Version")!=1||!tag.hasUUID("Task")||!tag.getUUID("Task").equals(task)||!tag.getString("Directory").equals(directory.fingerprint())||!tag.getString("Route").equals(route.id()))throw new IllegalStateException("Original task/phase/directory authority changed");
        Stage stage=Stage.valueOf(tag.getString("Stage"));boolean bank=stage==Stage.PRELAUNCH||stage==Stage.DESCENT;
        if(route.recovery()!=(stage==Stage.DESCENT||stage==Stage.RETURN_TRANSFER)||at<0||at>total||bank&&at>ready+1e-6||!bank&&at<ready-1e-6)throw new IllegalStateException("Actual distance is outside its persisted motion phase");
        boolean transfer=stage==Stage.PRELAUNCH||stage==Stage.RETURN_TRANSFER;
        var speed=transfer?route.motionProfile().prelaunch():route.motionProfile().launch();
        // Restore the established transfer speed for new and saved jobs.
        if(transfer)speed=new NervRouteDirectoryR52.SpeedProfile(speed.cruiseMps()*4,speed.accelerationMps2()*16,speed.decelerationMps2()*16);
        return new Run(stage,bank?ready:total,speed);
    }
    /** A complete native distance clock is necessary; a request flag cannot skip the stop. */
    public static Run crossStoppedBank(CompoundTag data,UUID task,NervRouteDirectoryR52 directory,NervRouteDirectoryR52.Route route,double at)
    {
        var run=current(data,task,directory,route,at);var speed=run.speed();double total=directory.routeLength(route);
        if(!run.bankStop()||at!=run.stop()||data.contains("ContinuousBrakeR52"))throw new IllegalStateException("Explicit unbraked stopped bank boundary required");
        verifyStoppedBank(data,task,directory,route,at);
        data.getCompound(KEY).putString("Stage",route.recovery()?Stage.RETURN_TRANSFER.name():Stage.ASCENT.name());
        var next=current(data,task,directory,route,at);var target=next.speed();
        NervMechanicalTravelR52.rememberContinuous(data,route.id(),directory.fingerprint(),total,new NervMechanicalTravelR52.ContinuousClock(new NervMechanicalTravelR52.ContinuousProfile(at,total,target.cruiseMps(),target.accelerationMps2(),target.decelerationMps2()),0));
        data.remove("ContinuousAutoLaunchR52");data.remove("ReleaseWhenReady");return next;
    }
    public static void verifyStoppedBank(CompoundTag data,UUID task,NervRouteDirectoryR52 directory,NervRouteDirectoryR52.Route route,double at)
    {
        var run=current(data,task,directory,route,at);if(!run.bankStop()||at!=run.stop()||data.contains("ContinuousBrakeR52"))throw new IllegalStateException("Actual unbraked bank stop required");
        if(data.getCompound("ContinuousClockR52").isEmpty())
        {
            var prior=data.getCompound("PreviousBankStopR53");var source=directory.route(prior.getString("SourceRoute"));
            if(!route.recovery()||!data.hasUUID("HeadReturnFromTaskR53")||!prior.hasUUID("SourceTask")||!prior.getUUID("SourceTask").equals(data.getUUID("HeadReturnFromTaskR53"))||!prior.getString("SourceRoute").equals(data.getString("HeadReturnFromRouteR53"))||!prior.hasUUID("TargetTask")||!prior.getUUID("TargetTask").equals(task)||!prior.getString("TargetRoute").equals(route.id())||!prior.getString("Directory").equals(directory.fingerprint())||source==null||!source.readyNode().equals(route.readyNode())||Math.abs(prior.getDouble("TargetDistance")-at)>1e-6)throw new IllegalStateException("A cancelled original bank stop cannot be inferred from an empty clock");
            var stored=prior.getCompound("Clock");var old=new CompoundTag();old.put("ContinuousClockR52",stored.copy());old.put(KEY,prior.getCompound("SourcePhase").copy());var sourceRun=current(old,prior.getUUID("SourceTask"),directory,source,stored.getDouble("DistanceMetres"));var sourceSpeed=sourceRun.speed();var before=NervMechanicalTravelR52.continuousClock(old,source.id(),directory.fingerprint(),stored.getDouble("DistanceMetres"),directory.routeLength(source),stored.getDouble("ToMetres"),sourceSpeed.cruiseMps(),sourceSpeed.accelerationMps2(),sourceSpeed.decelerationMps2());
            if(before.speed()!=0||Math.abs(before.distance()-directory.readyDistanceR53(source))>1e-6)throw new IllegalStateException("Original cancelled clock was not stopped at this same bank");return;
        }
        var speed=run.speed();var clock=NervMechanicalTravelR52.continuousClock(data,route.id(),directory.fingerprint(),at,directory.routeLength(route),run.stop(),speed.cruiseMps(),speed.accelerationMps2(),speed.decelerationMps2());if(!clock.complete()||clock.speed()!=0)throw new IllegalStateException("Bank phase transition requires completed real zero-speed clock");
    }
    public static boolean firstLaunchCommit(CompoundTag data,Run run,double before,double after,double ready)
    {
        if(!run.launch()||after<=before)return false;var tag=data.getCompound(KEY);boolean first=!tag.getBoolean("LaunchCommitted")&&before<=ready+.01&&after>=ready;
        tag.putBoolean("LaunchCommitted",true);return first;
    }
    private NervLaunchPhasesR53(){}
}
