package com.projectseele.entity;

import com.google.gson.JsonObject;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;

/** One grounded C action, using the root-authored source clock and trajectory. */
public final class EvaFieldActionsR45
{
    private static final WeakIdentityMap<EvaUnit01Entity,Runtime> RUNTIMES=new WeakIdentityMap<>();
    private static final class Runtime {long sequence,lastStep=Long.MIN_VALUE;int elapsed;Vec3 previous;}
    public static boolean active(EvaUnit01Entity e)
    {return !EvaWeaponHandlingR45.fieldActionR45(e).isEmpty();}
    public static String clip(EvaUnit01Entity e)
    {return EvaWeaponHandlingR45.fieldActionR45(e).getString("clip");}
    public static float progress(EvaUnit01Entity e,float partial)
    {
        if(!active(e))return 0;var s=EvaWeaponHandlingR45.fieldActionR45(e);
        float ticks=e.fieldActionProgressR45(partial)*s.getInt("duration");
        return Mth.clamp((ticks-s.getInt("entry_ticks"))/Math.max(1,s.getInt("source_ticks")),0,1);
    }
    public static float entryProgress(EvaUnit01Entity e,float partial)
    {
        var s=EvaWeaponHandlingR45.fieldActionR45(e);
        return Mth.clamp(e.fieldActionProgressR45(partial)*s.getInt("duration")/Math.max(1,s.getInt("entry_ticks")),0,1);
    }
    public static void clear(EvaUnit01Entity e)
    {
        if(!e.level().isClientSide&&!EvaWeaponHandlingR45.fieldActionR45(e).isEmpty())
            EvaWeaponHandlingR45.fieldActionR45(e,new CompoundTag());
        var runtime=RUNTIMES.get(e);if(runtime!=null){runtime.previous=null;runtime.lastStep=Long.MIN_VALUE;}
    }
    private static boolean stableOwner(EvaUnit01Entity e)
    {
        return !e.isExperimentalUnit()&&e.isAlive()&&e.isPoweredOn()&&e.onGround()
                &&!e.isNervLogisticsLocked()&&!e.isLaunchSequenceActive()&&!e.isFirstBattleActive()
                &&!e.isBerserk()&&!EvaShutdownR30.disabled(e)&&!EvaBayRepairR33.active(e)
                &&!EvaAirTransportR31.active(e)&&!com.projectseele.physics.CombatBodyDynamics.active(e)
                &&!CombatFeelR31.restrained(e)&&e.getActivationTicks()==0
                &&(e.getWeapon()==EvaUnit01Entity.WEAPON_FISTS||e.getWeapon()==EvaUnit01Entity.WEAPON_KNIFE);
    }
    private static JsonObject admittedClip(EvaUnit01Entity e,String name)
    {
        var profile=EvaGameplayMotionR32.profile(e.getUnitVariant());String key="r32_"+name;
        if(profile==null||!profile.has("clips")||!profile.getAsJsonObject("clips").has(key)
                ||!EvaBodyPose.combatCaptureReadyR31(e,key))return null;
        var c=profile.getAsJsonObject("clips").getAsJsonObject(key);
        if(!c.has("source_duration_seconds")||!c.has("trajectory_m")||!c.has("frames")
                ||c.getAsJsonArray("frames").size()<2||c.getAsJsonArray("trajectory_m").size()<2)return null;
        double seconds=c.get("source_duration_seconds").getAsDouble();
        if(!Double.isFinite(seconds)||seconds<=0||seconds*20>Integer.MAX_VALUE)return null;
        for(var p:c.getAsJsonArray("trajectory_m"))
        {
            var point=p.getAsJsonArray();if(point.size()!=3)return null;
            for(int i=0;i<3;i++)if(!Double.isFinite(point.get(i).getAsDouble()))return null;
        }
        return c;
    }
    public static boolean request(EvaUnit01Entity e,ServerPlayer pilot,int directions,boolean sprinting)
    {
        if(e.level().isClientSide||pilot==null||e.getPilotEntity()!=pilot||!stableOwner(e)
                ||e.isPilotControlLocked()||active(e)||EvaCombatR31.active(e)
                ||e.hasLiveActionForRender(0)||e.hasLegacyStrikeForRender()
                ||e.isPilotProne()||e.isPilotCrouching()||e.rifleStanceLevel(0)>.01F)return false;
        if(directions<0||directions>15||(directions&3)==3||(directions&12)==12)return false;
        if(!sprinting&&directions==0)return false;
        String name=sprinting?"roll_forward":(directions&4)!=0?"evade_left":(directions&8)!=0?"evade_right"
                :(directions&2)!=0?"evade_back":"evade_forward";
        var authored=admittedClip(e,name);if(authored==null)return false;
        float yaw=e.getYRot();
        if(sprinting&&directions!=0)
        {
            double right=((directions&8)!=0?1:0)-((directions&4)!=0?1:0);
            double front=((directions&1)!=0?1:0)-((directions&2)!=0?1:0);
            Vec3 forward=e.getForward().multiply(1,0,1).normalize();
            Vec3 direction=new Vec3(forward.z,0,-forward.x).scale(right).add(forward.scale(front));
            yaw=(float)Math.toDegrees(Math.atan2(-direction.x,direction.z));
        }
        // Preserve the world-facing entry pose while the new action adopts its
        // requested travel direction. The source starts crouched, not standing.
        var origin=EvaBodyPose.sample(e,0);
        var turn=new org.joml.Quaternionf().rotationY((yaw-e.getYRot())*Mth.DEG_TO_RAD);
        var pivot=origin.rig.get("root").pivot();
        origin.rotations.put("root",new org.joml.Quaternionf(turn).mul(origin.rotations.get("root")));
        origin.positions.put("root",turn.transform(new org.joml.Vector3f(origin.positions.get("root")).add(pivot)).sub(pivot));origin.dirty();
        EvaGameplayMotionR32.beginAction(e,origin);
        e.interruptCombatR31();
        var runtime=RUNTIMES.computeIfAbsent(e,k->new Runtime());
        var state=new CompoundTag();state.putString("clip",name);
        state.putLong("sequence",++runtime.sequence);state.putLong("since",e.level().getGameTime());
        int sourceTicks=Math.max(1,(int)Math.round(authored.get("source_duration_seconds").getAsDouble()*20));
        int entryTicks=sprinting?6:3;
        state.putInt("source_ticks",sourceTicks);state.putInt("entry_ticks",entryTicks);state.putInt("duration",sourceTicks+entryTicks);
        state.putUUID("pilot",pilot.getUUID());state.putFloat("facing",yaw);
        runtime.previous=root(authored,0);runtime.lastStep=Long.MIN_VALUE;runtime.elapsed=0;
        e.setDeltaMovement(new Vec3(0,e.getDeltaMovement().y,0));
        EvaWeaponHandlingR45.fieldActionR45(e,state);e.fieldActionPhaseR45(0);return true;
    }
    private static Vec3 root(JsonObject clip,float phase)
    {
        var points=clip.getAsJsonArray("trajectory_m");float at=Mth.clamp(phase,0,1)*(points.size()-1);
        int a=(int)at,b=Math.min(a+1,points.size()-1);var x=points.get(a).getAsJsonArray();var y=points.get(b).getAsJsonArray();
        return new Vec3(Mth.lerp(at-a,x.get(0).getAsDouble(),y.get(0).getAsDouble()),0,
                Mth.lerp(at-a,x.get(2).getAsDouble(),y.get(2).getAsDouble()));
    }
    public static void tick(EvaUnit01Entity e)
    {
        if(e.level().isClientSide||!active(e))return;
        var state=EvaWeaponHandlingR45.fieldActionR45(e);var pilot=e.getPilotEntity();
        long now=e.level().getGameTime();
        if(!stableOwner(e)||pilot==null||!state.hasUUID("pilot")||!state.getUUID("pilot").equals(pilot.getUUID())
                ||now<state.getLong("since")){clear(e);return;}
        var authored=admittedClip(e,state.getString("clip"));if(authored==null){clear(e);return;}
        var runtime=RUNTIMES.get(e);if(runtime==null){clear(e);return;}
        if(runtime.lastStep==now)return;runtime.lastStep=now;
        if(CombatFeelR31.hitPaused(e))return;
        e.setYRot(state.getFloat("facing"));e.yBodyRot=e.getYRot();e.yHeadRot=e.getYRot();
        float at=Mth.clamp(++runtime.elapsed/(float)state.getInt("duration"),0,1);
        e.fieldActionPhaseR45(at);
        Vec3 next=root(authored,progress(e,0)),delta=next.subtract(runtime.previous);runtime.previous=next;
        e.moveFieldRootR45(delta);
        if(runtime.elapsed>=state.getInt("duration"))
        {EvaGameplayMotionR32.releaseToMovement(e);e.finishCapturedActionEndpointR45();clear(e);}
    }
    private EvaFieldActionsR45() {}
}
