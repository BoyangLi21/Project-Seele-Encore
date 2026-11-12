package com.projectseele.entity;

import com.google.gson.JsonObject;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import java.util.UUID;

/** One grounded C action, using the root-authored source clock and trajectory. */
public final class EvaFieldActionsR45
{
    private static final WeakIdentityMap<EvaUnit01Entity,Runtime> RUNTIMES=new WeakIdentityMap<>();
    private record Pending(UUID pilot,int weapon,int directions,boolean sprinting,float yaw,long until,long wallUntil,
                           EvaUnit01Entity.RecoveryInputStampR51 stamp,long fieldSequence){}
    private static final class Runtime {long sequence,lastStep=Long.MIN_VALUE;int elapsed;Vec3 previous;Pending pending;}
    public static boolean active(EvaUnit01Entity e)
    {return !EvaWeaponHandlingR45.fieldActionR45(e).isEmpty();}
    public static String clip(EvaUnit01Entity e)
    {return EvaWeaponHandlingR45.fieldActionR45(e).getString("clip");}
    public static float progress(EvaUnit01Entity e,float partial)
    {
        if(!active(e))return 0;var s=EvaWeaponHandlingR45.fieldActionR45(e);
        float ticks=e.fieldActionProgressR45(partial)*s.getInt("duration");
        // Older live state omitted this marker and used an added entry delay.
        if(s.getInt("source_clock_r51")==1)return Mth.clamp(ticks/Math.max(1,s.getInt("source_ticks")),0,1);
        return Mth.clamp((ticks-s.getInt("entry_ticks"))/Math.max(1,s.getInt("source_ticks")),0,1);
    }
    public static float entryProgress(EvaUnit01Entity e,float partial)
    {
        var s=EvaWeaponHandlingR45.fieldActionR45(e);
        return Mth.clamp(e.fieldActionProgressR45(partial)*s.getInt("duration")/Math.max(1,s.getInt("entry_ticks")),0,1);
    }
    public static void clear(EvaUnit01Entity e)
    {
        if(!e.level().isClientSide&&CLIMB.equals(EvaWeaponHandlingR45.fieldActionR45(e).getString("clip")))e.setNoGravity(false);
        if(!e.level().isClientSide&&!EvaWeaponHandlingR45.fieldActionR45(e).isEmpty())
            EvaWeaponHandlingR45.fieldActionR45(e,new CompoundTag());
        var runtime=RUNTIMES.get(e);if(runtime!=null){runtime.previous=null;runtime.lastStep=Long.MIN_VALUE;runtime.pending=null;}
    }
    /** The ledge climb: Space at a ledge taller than a step. */
    public static final String CLIMB="climb_up";
    /**
     * Ledges Space takes the EVA onto (blocks above its feet): lower ones it
     * walks up; up to hip height it steps up, above that it climbs, up to
     * what its hands reach overhead.
     */
    private static final double CLIMB_LOW=20,CLIMB_HIGH=64;
    private static boolean stableOwner(EvaUnit01Entity e)
    {return stableOwner(e,false);}
    private static boolean stableOwner(EvaUnit01Entity e,boolean climbing)
    {
        return !e.isExperimentalUnit()&&e.isAlive()&&e.isPoweredOn()&&(climbing||e.onGround())
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
    /** The ticks of an evade or roll, counted from its start, in which a blow passes the body by. */
    private static final int SLIP_FROM_R63=1,SLIP_TO_R63=7;
    /** -Dprojectseele.evadeCancelR63=false plays an evade asked for during a strike as it used to, for comparison. */
    private static final boolean CANCEL_R63=!"false".equals(System.getProperty("projectseele.evadeCancelR63"));
    /**
     * True while an evade is slipping a blow: its first seven ticks, against a blow struck by another
     * body. A blast or a beam fills the place the body is leaving and is not slipped.
     */
    public static boolean slipsR63(EvaUnit01Entity e,net.minecraft.world.damagesource.DamageSource source)
    {
        if(e.level().isClientSide||!active(e))return false;
        var runtime=RUNTIMES.get(e);
        if(runtime==null||runtime.elapsed<SLIP_FROM_R63||runtime.elapsed>SLIP_TO_R63)return false;
        return source.getDirectEntity() instanceof net.minecraft.world.entity.LivingEntity attacker&&attacker!=e
                &&source.getDirectEntity()==source.getEntity()
                &&!source.is(net.minecraft.tags.DamageTypeTags.IS_EXPLOSION)&&!source.is(net.minecraft.tags.DamageTypeTags.IS_PROJECTILE)
                &&!source.is(net.minecraft.tags.DamageTypeTags.BYPASSES_INVULNERABILITY);
    }
    public static boolean request(EvaUnit01Entity e,ServerPlayer pilot,int directions,boolean sprinting)
    {
        if(e.level().isClientSide||pilot==null||e.getPilotEntity()!=pilot||!stableOwner(e)
                ||EvaCombatR31.active(e)||EvaWeaponHandlingR45.active(e)
                ||e.isPilotProne()||e.isPilotCrouching()||e.rifleStanceLevel(0)>.01F)return false;
        if(directions<0||directions>15||(directions&3)==3||(directions&12)==12)return false;
        if(!sprinting&&directions==0)return false;
        // A strike that has landed or missed has only its recovery left, and an evade asked for then
        // takes its place at once. It used to be held until the strike had played out, and was only
        // accepted in the strike's last eight ticks: up to four tenths of a second between the key
        // and the body moving, with an Angel's blow on its way.
        if(CANCEL_R63&&!active(e)&&!e.isPilotControlLocked()&&e.strikeSpentR63())
        {
            e.interruptCombatR31();
            return start(e,pilot,directions,sprinting,requestedYaw(e,directions,sprinting));
        }
        if(active(e)||e.hasLiveActionForRender(0)||e.hasLegacyStrikeForRender()||e.isPilotControlLocked())
        {
            var state=EvaWeaponHandlingR45.fieldActionR45(e);var runtime=RUNTIMES.get(e);
            if(active(e)&&runtime==null)return false;
            if(runtime==null)runtime=RUNTIMES.computeIfAbsent(e,k->new Runtime());
            boolean tail=active(e)?state.getInt("duration")-runtime.elapsed<=EvaUnit01Entity.RECOVERY_INPUT_BUFFER_TICKS_R51
                    :!e.isPilotControlLocked()&&e.recoveryInputTailR51();
            if(!tail)return false;
            runtime.pending=new Pending(pilot.getUUID(),e.getWeapon(),directions,sprinting,requestedYaw(e,directions,sprinting),
                    e.level().getGameTime()+EvaUnit01Entity.RECOVERY_INPUT_BUFFER_TICKS_R51,System.nanoTime()+400_000_000L,
                    e.recoveryInputStampR51(),active(e)?state.getLong("sequence"):0);
            return true;
        }
        return start(e,pilot,directions,sprinting,requestedYaw(e,directions,sprinting));
    }
    /**
     * Space against a ledge too tall to walk up: step up onto it or climb it,
     * by its height (EvaClimbChoreographyR57). The move's path, scaled to this
     * ledge, carries the body; the drawn pose climbs relative to it. Returns
     * false (an ordinary jump follows) when no ledge of climbable height with
     * room on top stands right ahead.
     */
    public static boolean requestClimb(EvaUnit01Entity e,ServerPlayer pilot)
    {
        if(e.level().isClientSide||pilot==null||e.getPilotEntity()!=pilot||!stableOwner(e)||active(e)
                ||EvaCombatR31.active(e)||EvaWeaponHandlingR45.active(e)||e.isPilotProne()||e.isPilotCrouching()
                ||e.rifleStanceLevel(0)>.01F||e.hasLiveActionForRender(0)||e.hasLegacyStrikeForRender()||e.isPilotControlLocked())return false;
        var authored=admittedClip(e,CLIMB);
        if(authored==null||!authored.has("r57_climb_path"))return false;
        double[] ledge=ledge(e);if(ledge==null)return false;
        EvaGameplayMotionR32.beginAction(e,EvaBodyPose.sample(e,0));
        e.interruptCombatR31();
        var runtime=RUNTIMES.computeIfAbsent(e,k->new Runtime());
        var state=new CompoundTag();state.putString("clip",CLIMB);
        state.putLong("sequence",++runtime.sequence);state.putLong("since",e.level().getGameTime());
        int sourceTicks=EvaClimbChoreographyR57.ticks(ledge[0]);
        state.putInt("source_clock_r51",1);state.putInt("source_ticks",sourceTicks);state.putInt("entry_ticks",6);state.putInt("duration",sourceTicks);
        state.putUUID("pilot",pilot.getUUID());state.putFloat("facing",e.getYRot());
        state.putDouble("x0",e.getX());state.putDouble("y0",e.getY());state.putDouble("z0",e.getZ());
        state.putDouble("rise",ledge[0]);state.putDouble("advance",ledge[1]);
        runtime.previous=Vec3.ZERO;runtime.lastStep=Long.MIN_VALUE;runtime.elapsed=0;
        e.setDeltaMovement(Vec3.ZERO);
        EvaWeaponHandlingR45.fieldActionR45(e,state);e.fieldActionPhaseR45(0);EvaActionFoleyR61.fieldStart(e,CLIMB);return true;
    }
    /** {rise, advance} in blocks onto the ledge right ahead, or null. */
    private static double[] ledge(EvaUnit01Entity e)
    {
        var level=e.level();var box=e.getBoundingBox();
        Vec3 forward=Vec3.directionFromRotation(0,e.getYRot()).multiply(1,0,1).normalize();
        // Something taller than a step stands within two blocks ahead.
        if(level.noCollision(e,box.move(forward.scale(2)).move(0,CLIMB_LOW+.5,0)))return null;
        double advance=Math.max(box.getXsize(),box.getZsize())*.5+4;
        for(double rise=CLIMB_LOW+1;rise<=CLIMB_HIGH;rise+=1)
        {
            // Room to rise in place, then room on top, standing on something.
            if(!level.noCollision(e,box.move(0,rise,0)))return null;
            var top=box.move(forward.scale(advance)).move(0,rise,0);
            if(level.noCollision(e,top)&&level.noCollision(e,box.move(forward.scale(advance*.5)).move(0,rise,0))
                    &&!level.noCollision(e,top.move(0,-1.5,0)))return new double[]{rise,advance};
        }
        return null;
    }
    private static float requestedYaw(EvaUnit01Entity e,int directions,boolean sprinting)
    {
        if(!sprinting||directions==0)return e.getYRot();
        double right=((directions&8)!=0?1:0)-((directions&4)!=0?1:0);
        double front=((directions&1)!=0?1:0)-((directions&2)!=0?1:0);
        Vec3 forward=e.getForward().multiply(1,0,1).normalize();
        Vec3 direction=new Vec3(forward.z,0,-forward.x).scale(right).add(forward.scale(front));
        return (float)Math.toDegrees(Math.atan2(-direction.x,direction.z));
    }
    private static boolean start(EvaUnit01Entity e,ServerPlayer pilot,int directions,boolean sprinting,float yaw)
    {
        String name=sprinting?"roll_forward":(directions&4)!=0?"evade_left":(directions&8)!=0?"evade_right"
                :(directions&2)!=0?"evade_back":"evade_forward";
        var authored=admittedClip(e,name);if(authored==null)return false;
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
        int entryTicks=2;
        state.putInt("source_clock_r51",1);state.putInt("source_ticks",sourceTicks);state.putInt("entry_ticks",entryTicks);state.putInt("duration",sourceTicks);
        state.putUUID("pilot",pilot.getUUID());state.putFloat("facing",yaw);
        runtime.previous=root(authored,0);runtime.lastStep=Long.MIN_VALUE;runtime.elapsed=0;
        e.setDeltaMovement(new Vec3(0,e.getDeltaMovement().y,0));
        EvaWeaponHandlingR45.fieldActionR45(e,state);e.fieldActionPhaseR45(0);EvaActionFoleyR61.fieldStart(e,name);return true;
    }
    private static boolean pendingValid(EvaUnit01Entity e,Runtime runtime)
    {
        var p=runtime.pending;var pilot=e.getPilotEntity();
        return p!=null&&pilot instanceof ServerPlayer&&pilot.getUUID().equals(p.pilot())&&e.getWeapon()==p.weapon()
                &&e.level().getGameTime()<=p.until()&&System.nanoTime()<=p.wallUntil()&&stableOwner(e)
                &&!e.isPilotProne()&&!e.isPilotCrouching()&&e.rifleStanceLevel(0)<=.01F
                &&!EvaWeaponHandlingR45.active(e)&&!EvaCombatR31.active(e)&&e.recoveryInputStampR51().equals(p.stamp())
                &&(!active(e)||EvaWeaponHandlingR45.fieldActionR45(e).getLong("sequence")==p.fieldSequence());
    }
    private static void consumePending(EvaUnit01Entity e,Runtime runtime)
    {
        if(runtime.pending==null)return;
        if(!pendingValid(e,runtime)){runtime.pending=null;return;}
        if(active(e)||e.hasLiveActionForRender(0)||e.hasLegacyStrikeForRender())return;
        if(e.isPilotControlLocked()){runtime.pending=null;return;}
        var pending=runtime.pending;runtime.pending=null;
        start(e,(ServerPlayer)e.getPilotEntity(),pending.directions(),pending.sprinting(),pending.yaw());
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
        if(e.level().isClientSide)return;
        var known=RUNTIMES.get(e);
        if(known!=null&&known.pending!=null&&!pendingValid(e,known))known.pending=null;
        if(!active(e)){if(known!=null)consumePending(e,known);return;}
        var state=EvaWeaponHandlingR45.fieldActionR45(e);var pilot=e.getPilotEntity();
        long now=e.level().getGameTime();
        boolean climbing=CLIMB.equals(state.getString("clip"));
        if(!stableOwner(e,climbing)||pilot==null||!state.hasUUID("pilot")||!state.getUUID("pilot").equals(pilot.getUUID())
                ||now<state.getLong("since")){clear(e);return;}
        var authored=admittedClip(e,state.getString("clip"));if(authored==null){clear(e);return;}
        var runtime=RUNTIMES.get(e);if(runtime==null){clear(e);return;}
        if(runtime.lastStep==now)return;runtime.lastStep=now;
        if(CombatFeelR31.hitPaused(e))return;
        e.setYRot(state.getFloat("facing"));e.yBodyRot=e.getYRot();e.yHeadRot=e.getYRot();
        float at=Mth.clamp(++runtime.elapsed/(float)state.getInt("duration"),0,1);
        e.fieldActionPhaseR45(at);
        EvaActionFoleyR61.fieldTick(e,state,runtime.elapsed,state.getInt("duration"));
        if(climbing)
        {
            // Along the climb path, scaled to this ledge; no gravity or
            // collision on the way, both checked before the climb began.
            float[] path=EvaClimbChoreographyR57.path(state.getDouble("rise"),progress(e,0));double up=path[0],on=path[1];
            Vec3 forward=Vec3.directionFromRotation(0,state.getFloat("facing")).multiply(1,0,1).normalize();
            e.setNoGravity(true);e.setDeltaMovement(Vec3.ZERO);e.fallDistance=0;
            e.setPos(state.getDouble("x0")+forward.x*on*state.getDouble("advance"),state.getDouble("y0")+up*state.getDouble("rise"),
                    state.getDouble("z0")+forward.z*on*state.getDouble("advance"));
            e.setOnGround(true);
        }
        else
        {
            Vec3 next=root(authored,progress(e,0)),delta=next.subtract(runtime.previous);runtime.previous=next;
            e.moveFieldRootR45(delta);
        }
        if(runtime.elapsed>=state.getInt("duration"))
        {
            if(climbing)e.setNoGravity(false);
            var pending=runtime.pending;
            EvaGameplayMotionR32.releaseToMovement(e);e.finishCapturedActionEndpointR45();clear(e);
            runtime.pending=pending;consumePending(e,runtime);
        }
    }
    private EvaFieldActionsR45() {}
}
