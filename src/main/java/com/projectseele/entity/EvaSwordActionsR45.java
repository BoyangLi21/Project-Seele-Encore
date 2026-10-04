package com.projectseele.entity;

import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import com.projectseele.combat.EvaContactHitsR45;
import com.projectseele.physics.CombatDamageTargetsR44;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;

/** Independent Unit-02 sword actions; the root-owned API supplies the actual blade geometry. */
public final class EvaSwordActionsR45
{
    private static final WeakIdentityMap<EvaUnit01Entity,Runtime> STATES=new WeakIdentityMap<>();
    private static final class Runtime
    {
        final EvaContactHitsR45 hits=new EvaContactHitsR45();
        int sequence,elapsed,nextStage,queued=-1,traceRows;boolean soundPlayed,swingPlayed;long lastStep=Long.MIN_VALUE,inputAt;
        EvaAnatomicalHandsR45.SwordBladeR45 previous;Vec3 root;
    }
    public static boolean active(EvaUnit01Entity e){return !EvaWeaponHandlingR45.swordActionR45(e).isEmpty();}
    public static String clip(EvaUnit01Entity e){return EvaWeaponHandlingR45.swordActionR45(e).getString("clip");}
    public static float progress(EvaUnit01Entity e,float partial){return active(e)?e.swordActionProgressR45(partial):0;}
    public static boolean dispatchReadyR45(EvaUnit01Entity e)
    {
        if(e.isExperimentalUnit()||e.getUnitVariant()!=2)return false;
        var rig=EvaBodyPose.neutralForTransportR32(e).rig;
        if(!rig.containsKey("lance")||!rig.containsKey("hand_r"))return false;
        for(String name:java.util.List.of("sword_a","sword_b","sword_c","sword_heavy"))if(authored(e,name)==null)return false;
        return true;
    }
    private static JsonObject authored(EvaUnit01Entity e,String name)
    {
        var profile=EvaGameplayMotionR32.profile(e.getUnitVariant());String key="r32_"+name;
        if(profile==null||!profile.has("clips")||!profile.getAsJsonObject("clips").has(key)
                ||!EvaBodyPose.combatCaptureReadyR31(e,key))return null;
        var c=profile.getAsJsonObject("clips").getAsJsonObject(key);
        if(!c.has("source_duration_seconds")||!c.has("trajectory_m")||!c.has("contact_phase"))return null;
        double seconds=c.get("source_duration_seconds").getAsDouble(),contact=c.get("contact_phase").getAsDouble();
        if(!Double.isFinite(seconds)||seconds<=0||seconds*20>Integer.MAX_VALUE
                ||!Double.isFinite(contact)||contact<0||contact>1||c.getAsJsonArray("trajectory_m").size()<2)return null;
        for(var value:c.getAsJsonArray("trajectory_m"))
        {var point=value.getAsJsonArray();if(point.size()!=3)return null;for(int i=0;i<3;i++)if(!Double.isFinite(point.get(i).getAsDouble()))return null;}
        return c;
    }
    private static boolean owner(EvaUnit01Entity e,LivingEntity pilot)
    {
        return pilot!=null&&e.getPilotEntity()==pilot&&e.isAlive()&&!e.isExperimentalUnit()&&e.getUnitVariant()==2
                &&e.getWeapon()==EvaUnit01Entity.WEAPON_SWORD_R45&&e.isPoweredOn()&&e.onGround()
                &&!e.isNervLogisticsLocked()&&!e.isLaunchSequenceActive()&&!e.isFirstBattleActive()&&!e.isBerserk()
                &&!EvaShutdownR30.disabled(e)&&!EvaBayRepairR33.active(e)&&!EvaAirTransportR31.active(e)
                &&!com.projectseele.physics.CombatBodyDynamics.active(e)&&!CombatFeelR31.restrained(e)
                &&e.getActivationTicks()==0&&!e.isPilotProne()&&!e.isPilotCrouching()&&e.rifleStanceLevel(0)<.01F;
    }
    public static boolean request(EvaUnit01Entity e,LivingEntity pilot,boolean heavy)
    {
        if(e.level().isClientSide||!owner(e,pilot)||!EvaEquipmentResourcesR45.ready(e,6))return false;
        var runtime=STATES.computeIfAbsent(e,k->new Runtime());
        if(active(e))
        {if(heavy||runtime.queued!=1)runtime.queued=heavy?1:0;runtime.inputAt=e.level().getGameTime();return true;}
        if(e.isPilotControlLocked()||e.hasLiveActionForRender(0)||EvaCombatR31.active(e)||e.hasLegacyStrikeForRender())return false;
        if(heavy&&!e.swordHeavyAvailableR45())return false;
        String name=heavy?"sword_heavy":new String[]{"sword_a","sword_b","sword_c"}[runtime.nextStage];
        var authored=authored(e,name);if(authored==null)return false;
        e.interruptCombatR31();EvaGameplayMotionR32.beginAction(e);
        var state=new CompoundTag();int sequence=runtime.sequence=(runtime.sequence+1)&Integer.MAX_VALUE;
        state.putString("clip",name);state.putInt("sequence",sequence);state.putLong("since",e.level().getGameTime());
        state.putUUID("pilot",pilot.getUUID());state.putBoolean("heavy",heavy);
        state.putInt("duration",e.swordSourceTicksR45(authored.get("source_duration_seconds").getAsDouble()));
        runtime.elapsed=0;runtime.lastStep=Long.MIN_VALUE;runtime.previous=null;runtime.queued=-1;
        runtime.soundPlayed=false;runtime.swingPlayed=false;runtime.root=sourceRoot(authored,0);runtime.hits.begin(sequence,state.getLong("since"));
        if(!heavy)runtime.nextStage=(runtime.nextStage+1)%3;else {runtime.nextStage=0;e.swordBeginHeavyCooldownR45();}
        EvaWeaponHandlingR45.swordActionR45(e,state);e.swordActionPhaseR45(0);return true;
    }
    public static boolean cancelByPilotR45(EvaUnit01Entity e,LivingEntity pilot)
    {if(!active(e)||!owner(e,pilot))return false;clear(e);return true;}
    public static void clear(EvaUnit01Entity e)
    {
        if(!e.level().isClientSide&&!EvaWeaponHandlingR45.swordActionR45(e).isEmpty())
            EvaWeaponHandlingR45.swordActionR45(e,new CompoundTag());
        var runtime=STATES.get(e);if(runtime!=null){runtime.hits.end();runtime.previous=null;runtime.root=null;runtime.queued=-1;runtime.nextStage=0;}
    }
    private static Vec3 sourceRoot(JsonObject clip,float phase)
    {
        var points=clip.getAsJsonArray("trajectory_m");float at=phase*(points.size()-1);int a=(int)at,b=Math.min(a+1,points.size()-1);
        var x=points.get(a).getAsJsonArray();var y=points.get(b).getAsJsonArray();
        return new Vec3(net.minecraft.util.Mth.lerp(at-a,x.get(0).getAsDouble(),y.get(0).getAsDouble()),0,
                net.minecraft.util.Mth.lerp(at-a,x.get(2).getAsDouble(),y.get(2).getAsDouble()));
    }
    private static boolean valid(EvaAnatomicalHandsR45.SwordBladeR45 frame)
    {
        if(frame==null||frame.base()==null||frame.tip()==null||!Double.isFinite(frame.radius())||frame.radius()<=0)return false;
        for(Vec3 p:java.util.List.of(frame.base(),frame.tip()))if(!Double.isFinite(p.x)||!Double.isFinite(p.y)||!Double.isFinite(p.z))return false;
        return frame.base().distanceToSqr(frame.tip())>0;
    }
    public static void tick(EvaUnit01Entity e)
    {
        if(e.level().isClientSide||!active(e))return;
        var state=EvaWeaponHandlingR45.swordActionR45(e);var pilot=e.getPilotEntity();var runtime=STATES.get(e);
        if(runtime==null||!owner(e,pilot)||!state.hasUUID("pilot")||!state.getUUID("pilot").equals(pilot.getUUID())){clear(e);return;}
        long now=e.level().getGameTime();if(runtime.lastStep==now)return;runtime.lastStep=now;
        if(CombatFeelR31.hitPaused(e))return;
        var authored=authored(e,state.getString("clip"));if(authored==null){clear(e);return;}
        float at=Math.min(1,++runtime.elapsed/(float)state.getInt("duration"));e.swordActionPhaseR45(at);
        if(!runtime.swingPlayed&&at>=EvaGameplayMotionR32.swingSoundPhaseR45(e,state.getString("clip")))
        {runtime.swingPlayed=true;EvaMovementSounds.swing(e,state.getBoolean("heavy")?2.8F:2.1F);}
        Vec3 next=sourceRoot(authored,at);e.moveCombatRootR34(next.subtract(runtime.root));runtime.root=next;
        var blade=EvaAnatomicalHandsR45.swordBladeWorldR45(e,0);
        if(valid(blade))
        {
            var previous=runtime.previous==null?blade:runtime.previous;
            if(EvaGameplayMotionR32.inContactWindowR45(e,state.getString("clip"),at))contact(e,pilot,runtime,state,previous,blade);
            runtime.previous=blade;
        }
        else runtime.previous=null;
        if(runtime.elapsed>=state.getInt("duration"))
        {
            int queued=runtime.queued,nextStage=runtime.nextStage;boolean fresh=now-runtime.inputAt<=e.swordInputBufferTicksR45();
            EvaGameplayMotionR32.releaseToMovement(e);e.finishCapturedActionEndpointR45();clear(e);
            if(queued>=0&&fresh){runtime.nextStage=nextStage;request(e,pilot,queued==1);}
        }
    }
    private static boolean clearRay(EvaUnit01Entity e,Vec3 from,Vec3 to)
    {return e.level().clip(new ClipContext(from,to,ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,e)).getType()==HitResult.Type.MISS;}
    private static float field(net.minecraft.world.entity.Entity target)
    {
        if(target instanceof EvaUnit01Entity eva)return eva.getAtFieldEnergy();
        if(target instanceof Angel angel)return angel.getAtField();return Float.NaN;
    }
    private static void contact(EvaUnit01Entity e,LivingEntity pilot,Runtime runtime,CompoundTag state,
            EvaAnatomicalHandsR45.SwordBladeR45 before,EvaAnatomicalHandsR45.SwordBladeR45 after)
    {
        Vec3[] points={before.base(),before.tip(),after.tip(),after.base()};double radius=Math.max(before.radius(),after.radius());
        double x=Double.POSITIVE_INFINITY,y=x,z=x,mx=Double.NEGATIVE_INFINITY,my=mx,mz=mx;
        for(Vec3 p:points){x=Math.min(x,p.x);y=Math.min(y,p.y);z=Math.min(z,p.z);mx=Math.max(mx,p.x);my=Math.max(my,p.y);mz=Math.max(mz,p.z);}
        var area=new AABB(x,y,z,mx,my,mz).inflate(radius);float damage=e.swordDamageR45(state.getBoolean("heavy"));
        for(var target:CombatDamageTargetsR44.candidates(e.level(),area,e,pilot))
        {
            var point=CombatDamageTargetsR44.clipBladeSweepR45(target,points[0],points[1],points[2],points[3],radius);if(point.isEmpty())continue;
            Vec3 p=point.get();
            if(!clearRay(e,before.base(),p)||!clearRay(e,after.base(),p)
                    ||!clearRay(e,e.position().add(0,Math.max(2,before.base().y-e.getY()),0),before.base())
                    ||!clearRay(e,e.position().add(0,Math.max(2,after.base().y-e.getY()),0),after.base()))continue;
            int sequence=state.getInt("sequence");var admission=runtime.hits.admit(sequence,target.getUUID());
            if(!admission.allowsDamage())continue;
            boolean accepted=false,absorbed=false;float beforeField=field(target);long started=runtime.hits.startedAt();
            int invulnerableBefore=target.invulnerableTime;float healthBefore=target instanceof LivingEntity living?living.getHealth():Float.NaN;
            Vec3 direction=target.position().subtract(e.position()).multiply(1,0,1).normalize();
            try
            {
                // Only an admitted real blade/body/LOS contact reaches this cooldown-tagged source.
                var source=com.projectseele.registry.ModDamageTypesR45.ordinaryContact(e);
                accepted=CombatDamageTargetsR44.hurt(target,source,damage,p,direction,CombatDamageTargetsR44.Weapon.CONTACT);
            }
            finally
            {
                try{absorbed=EvaContactHitsR45.settledContactR46(false,beforeField,field(target));}
                finally{runtime.hits.finishAttempt(sequence,started,target.getUUID(),accepted||absorbed);}
            }
            if(Boolean.getBoolean("projectseele.r45ContactTrace")&&runtime.traceRows++<4096)
                ProjectSeele.LOGGER.info("R45 SWORD CONTACT eva={} pilot={} clip={} sequence={} target={} damage={} accepted={} field_consumed={} blade_before={} blade_after={} contact={} invulnerable_before={} invulnerable_after={} health_before={} health_after={} field_before={} field_after={}",
                        e.getUUID(),pilot.getUUID(),state.getString("clip"),sequence,target.getUUID(),damage,accepted,absorbed,before,after,p,
                        invulnerableBefore,target.invulnerableTime,healthBefore,target instanceof LivingEntity living?living.getHealth():Float.NaN,beforeField,field(target));
            if((accepted||absorbed)&&!runtime.soundPlayed){runtime.soundPlayed=true;e.swordContactSoundR45(p);}
            if(accepted&&target instanceof LivingEntity living)
                living.knockback(state.getBoolean("heavy")?2:1.1,e.getX()-target.getX(),e.getZ()-target.getZ());
        }
    }
    private EvaSwordActionsR45() {}
}
