package com.projectseele.entity;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.*;
import net.minecraft.util.Mth;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.*;
import org.joml.Vector3f;
import org.joml.Quaternionf;
import java.nio.file.*;
import java.util.*;

/** Calibrated motion poses, measured hand contacts, and physics-timed airborne phases. */
public final class EvaGameplayMotionR32
{
    private static final EntityDataAccessor<Long> AIR=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.LONG);
    private static final EntityDataAccessor<Long> LAND=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.LONG);
    private static final EntityDataAccessor<Long> TAKEOFF=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.LONG);
    private static final EntityDataAccessor<Float> FLOOR=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> VERTICAL=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> GUARD=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<CompoundTag> LAND_FROM=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.COMPOUND_TAG);
    private static final EntityDataAccessor<CompoundTag> ACTION_FROM=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.COMPOUND_TAG);
    private static final EntityDataAccessor<Boolean> LOW_TARGET=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Boolean> SERVER_MOVEMENT=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<CompoundTag> RELEASE_FROM=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.COMPOUND_TAG);
    private static final WeakIdentityMap<EvaUnit01Entity,State> STATES=new WeakIdentityMap<>();
    private static final Map<Integer,Optional<JsonObject>> PROFILES=new HashMap<>();
    private static final boolean REVIEW_POSE_CHOICES=Boolean.getBoolean("projectseele.r44SharedContactWitness")||com.projectseele.visual.BodyPoseLayersR40.ENABLED;
    private static final WeakIdentityMap<EvaUnit01Entity,JsonObject> POSE_CHOICES=new WeakIdentityMap<>();
    private static final class State {boolean air,guard;double y;float velocity;int scan;Vec3 previousContact;}
    public static boolean bootstrap(){return true;}
    public static void define(SynchedEntityData d){d.define(AIR,-1L);d.define(LAND,-1L);d.define(TAKEOFF,-1L);d.define(FLOOR,-1000000F);d.define(VERTICAL,0F);d.define(GUARD,0F);d.define(LAND_FROM,new CompoundTag());d.define(ACTION_FROM,new CompoundTag());d.define(LOW_TARGET,false);d.define(SERVER_MOVEMENT,false);d.define(RELEASE_FROM,new CompoundTag());}
    public static boolean serverMovement(EvaUnit01Entity e){return e.getEntityData().get(SERVER_MOVEMENT);}
    public static boolean movementMayComposeR45(EvaUnit01Entity e)
    {
        if(e instanceof EvaPrototypeEntity||e.isBerserk()||!ready(e)||e.isNervLogisticsLocked()||e.isVisuallyAirborneForRender()
                ||e.isFirstBattleActive()||EvaShutdownR30.disabled(e)||e.rifleStanceLevel(0)>.01F
                ||EvaCombatR31.action(e)!=EvaCombatR31.NONE)return false;
        return java.util.Set.of("jab","cross","hook","heavy","knife_forward","knife_reverse").contains(activeGroundClip(e,0));
    }
    private static int takeoffTicks(EvaUnit01Entity e)
    {
        var c=clip(e,"jump_start");
        return c.has("preparation_ticks")?Mth.clamp(c.get("preparation_ticks").getAsInt(),3,10):3;
    }
    public static boolean prepareJump(EvaUnit01Entity e)
    {
        if(!ready(e))return true;
        if(age(e,TAKEOFF,0)<0){beginAction(e);EvaCombatSupportR33.release(e);e.getEntityData().set(TAKEOFF,e.level().getGameTime());return false;}
        return age(e,TAKEOFF,0)>=takeoffTicks(e);
    }
    public static void beginAction(EvaUnit01Entity e)
    {
        if(!ready(e)||e.level().isClientSide)return;
        beginAction(e,EvaBodyPose.sample(e,0));
    }
    public static void beginAction(EvaUnit01Entity e,EvaBodyPose.Sample pose)
    {
        if(!ready(e)||e.level().isClientSide)return;
        var state=STATES.get(e);if(state!=null)state.previousContact=null;
        EvaCombatSupportR33.capture(e,pose);var origin=EvaShutdownR30.encode(pose);
        if(lowAttackReadyR44(e))origin.putInt("attack_stance_r44",e.isPilotProne()?3:e.isPilotCrouching()?1:0);
        e.getEntityData().set(ACTION_FROM,origin);
        e.getEntityData().set(RELEASE_FROM,new CompoundTag());
        var target=e.level().getEntitiesOfClass(net.minecraft.world.entity.LivingEntity.class,e.getBoundingBox().inflate(36),a->a instanceof Angel&&a.isAlive()
                &&a.position().subtract(e.position()).multiply(1,0,1).normalize().dot(e.getForward())>.35)
                .stream().min(java.util.Comparator.comparingDouble(e::distanceToSqr)).orElse(null);
        e.getEntityData().set(LOW_TARGET,phrases(e)&&lowContactTargetR49(target,36));
    }
    /** The actual grounded surface owns attack height even without a physics-profile rig. */
    public static boolean lowContactTargetR49(net.minecraft.world.entity.LivingEntity target,double height)
    {
        if(target==null)return false;
        if(com.projectseele.physics.ShamshelPosedContactsR48.supports(target))
            return com.projectseele.physics.ShamshelPosedContactsR48.bounds(target).getYsize()<height;
        return com.projectseele.physics.CombatBodyDynamics.active(target)&&target.getBoundingBox().getYsize()<height;
    }
    public static synchronized JsonObject profile(int variant)
    {
        return PROFILES.computeIfAbsent(variant,key->{
            Path file=CombatMotionResourcesR44.resolve("projectseele.gameplayReviewDirectory",
                    "eva_gameplay_r44_"+key+".json","eva_gameplay_r43_"+key+".json",
                    "eva_gameplay_r42_"+key+".json","eva_gameplay_r32_"+key+".json");
            if(!Files.isRegularFile(file))return Optional.empty();
            try
            {
                byte[] bytes=CombatMotionResourcesR44.read(file,"eva-gameplay-"+key);
                var data=JsonParser.parseString(new String(bytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
                if(data.get("schema").getAsInt()!=2||data.get("rig_key").getAsInt()!=key)throw new IllegalArgumentException("Gameplay rig contract");
                com.projectseele.ProjectSeele.LOGGER.info("EVA gameplay profile resolved: rig={} file={} sha256={}",key,file.toAbsolutePath().normalize(),
                        java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes)));
                return Optional.of(data);
            }
            catch(Exception error){throw new IllegalStateException("Gameplay motion rejected: "+file,error);}
        }).orElse(null);
    }
    public static synchronized void reload(){PROFILES.clear();}
    public static int variant(EvaUnit01Entity e){return e instanceof EvaPrototypeEntity un?3+un.getUNSerial():e.getUnitVariant();}
    public static float guardWeight(EvaUnit01Entity e){return e.getEntityData().get(GUARD);}
    public static boolean ready(EvaUnit01Entity e){return profile(variant(e))!=null;}
    private static boolean singleFlight(EvaUnit01Entity e)
    {var p=profile(variant(e));return p!=null&&p.has("airborne_revision")&&p.get("airborne_revision").getAsInt()>=42;}
    public static boolean sharedJump(EvaUnit01Entity e)
    {
        return !(e instanceof EvaPrototypeEntity)&&!e.isBerserk()
                &&singleFlight(e)&&EvaBodyPose.hasTerrainStances()
                &&(sharedWeapon(e)||e.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE);
    }
    public static boolean sharedJumpActive(EvaUnit01Entity e,float partial)
    {
        return sharedJump(e)&&(age(e,TAKEOFF,partial)>=0||airAge(e,partial)>=0
                ||landAge(e,partial)>=0&&landAge(e,partial)<18);
    }
    public static boolean sharedHands(EvaUnit01Entity e,float partial)
    {
        var p=profile(variant(e));return p!=null
                &&p.has("hand_pose_revision")&&p.get("hand_pose_revision").getAsInt()>=2&&sharedBody(e,partial);
    }
    public static boolean hasClip(EvaUnit01Entity e,String name)
    {var p=profile(variant(e));return p!=null&&p.getAsJsonObject("clips").has("r32_"+name);}
    public static boolean knifeReady(EvaUnit01Entity e)
    {return hasClip(e,"knife_forward")&&hasClip(e,"knife_reverse");}
    public static boolean lowAttackReadyR44(EvaUnit01Entity e)
    {
        var p=profile(variant(e));if(p==null||!p.has("low_attack_revision_r44")||p.get("low_attack_revision_r44").getAsInt()<1)return false;
        for(String stance:java.util.List.of("crouch","prone"))for(String name:java.util.List.of("jab","cross","hook","heavy","knife_forward","knife_reverse"))
            if(!p.getAsJsonObject("clips").has("r32_"+stance+"_"+name))return false;
        return true;
    }
    public static int actionStanceR44(EvaUnit01Entity e)
    {
        if(!lowAttackReadyR44(e))return 0;var origin=e.getEntityData().get(ACTION_FROM);
        return e.hasLiveActionForRender(0)&&origin.contains("attack_stance_r44")?origin.getInt("attack_stance_r44")
                :e.isPilotProne()?3:e.isPilotCrouching()?1:0;
    }
    public static boolean lowActionR44(EvaUnit01Entity e)
    {return lowAttackReadyR44(e)&&e.hasLiveActionForRender(0)&&actionStanceR44(e)>0;}
    public static boolean kickReady(EvaUnit01Entity e){return hasClip(e,"kick");}
    public static boolean sharedWeapon(EvaUnit01Entity e)
    {return EvaSwordActionsR45.active(e)||EvaFieldActionsR45.active(e)||e.getWeapon()==EvaUnit01Entity.WEAPON_SWORD_R45||e.getWeapon()==EvaUnit01Entity.WEAPON_SHIELD_R45||EvaWeaponHandlingR45.active(e)||e.getWeapon()==EvaUnit01Entity.WEAPON_FISTS||e.getWeapon()==EvaUnit01Entity.WEAPON_KNIFE&&(knifeReady(e)||EvaWeaponHandlingR45.available(e));}
    public static String activeGroundClip(EvaUnit01Entity e,float partial)
    {
        if(EvaFieldActionsR45.active(e))return EvaFieldActionsR45.clip(e);
        if(EvaSwordActionsR45.active(e))return EvaSwordActionsR45.clip(e);
        if(EvaBerserkMotionR34.striking(e))return EvaBerserkMotionR34.name(e);
        if(e.isHeavyMotionActive())return "heavy";
        if(e.getOrdinaryAttackStage()>=0)return ordinary(e.getOrdinaryAttackStage());
        if(e.isKickMotionActive(partial)&&kickReady(e))return "kick";
        int knife=e.getKnifeMotionType(partial);
        return knife>=0&&knifeReady(e)?knife==1?"knife_reverse":"knife_forward":"";
    }
    public static float activeGroundPhase(EvaUnit01Entity e,float partial)
    {
        if(EvaFieldActionsR45.active(e))return EvaFieldActionsR45.progress(e,partial);
        if(EvaSwordActionsR45.active(e))return EvaSwordActionsR45.progress(e,partial);
        if(EvaBerserkMotionR34.striking(e))return EvaBerserkMotionR34.phase(e,partial);
        if(e.isHeavyMotionActive())return e.heavyMotionProgress(partial);
        if(e.getOrdinaryAttackStage()>=0)return e.getOrdinaryAttackProgress(partial);
        if(e.isKickMotionActive(partial))return e.getKickAttackProgress(partial);
        int knife=e.getKnifeMotionType(partial);return knife>=0?e.getKnifeMotionProgress(knife,partial):0;
    }
    public static boolean directed(EvaUnit01Entity e){var p=profile(variant(e));return p!=null&&p.has("combat_foundation")&&p.get("combat_foundation").getAsInt()>=34;}
    public static boolean phrases(EvaUnit01Entity e){var p=profile(variant(e));return p!=null&&p.has("combat_foundation")&&p.get("combat_foundation").getAsInt()>=36;}
    public static boolean naturalRecovery(EvaUnit01Entity e)
    {var p=profile(variant(e));return p!=null&&p.has("natural_recovery")&&p.get("natural_recovery").getAsBoolean();}
    public static boolean planted(EvaUnit01Entity e,String side,float partial)
    {
        if(!directed(e)||!EvaCombatSupportR33.strike(e))return true;
        String name=activeGroundClip(e,partial);if(name.isEmpty())return true;
        float phase=activeGroundPhase(e,partial);
        var frames=clip(e,name).getAsJsonArray("frames");var f=frames.get(Math.min(frames.size()-1,Math.round(Mth.clamp(phase,0,1)*(frames.size()-1)))).getAsJsonObject();
        return f.getAsJsonArray("foot_contact").get(side.equals("l")?0:1).getAsBoolean();
    }
    private static String resolve(EvaUnit01Entity e,String name)
    {
        int stance=actionStanceR44(e);
        if(stance>0&&java.util.Set.of("jab","cross","hook","heavy","knife_forward","knife_reverse").contains(name))return (stance>=3?"prone_":"crouch_")+name;
        if(name.equals("jab")&&e.getOrdinaryAttackStage()==3&&hasClip(e,"jab_loop"))return "jab_loop";
        return phrases(e)&&e.getEntityData().get(LOW_TARGET)&&java.util.Set.of("jab","cross","hook","heavy").contains(name)?"low_"+name:name;
    }
    public static String resolvedGroundClipR44(EvaUnit01Entity e,float partial)
    {String name=activeGroundClip(e,partial);return name.isEmpty()?"":resolve(e,name);}
    /** Return only metadata written at the actual pose/blend call sites. */
    public static JsonObject actualPoseChoiceReviewR44(EvaUnit01Entity e,float partial)
    {
        var row=POSE_CHOICES.get(e);if(row==null||row.get("world_tick").getAsLong()!=e.level().getGameTime()
                ||Math.abs(row.get("partial").getAsFloat()-partial)>.0001F)return null;
        return row.deepCopy();
    }
    private static void reviewChoice(EvaUnit01Entity e,String key,String value)
    {if(REVIEW_POSE_CHOICES){var row=POSE_CHOICES.get(e);if(row!=null)row.addProperty(key,value);}}
    private static void reviewWeight(EvaUnit01Entity e,String key,float value)
    {if(REVIEW_POSE_CHOICES){var row=POSE_CHOICES.get(e);if(row!=null)row.addProperty(key,value);}}
    private static JsonObject clip(EvaUnit01Entity e,String name){return profile(variant(e)).getAsJsonObject("clips").getAsJsonObject("r32_"+resolve(e,name));}
    public static float contactPhase(EvaUnit01Entity e,String name){return clip(e,name).get("contact_phase").getAsFloat();}
    /** A recovered performance carries its own source clock. Older profiles
     * retain their existing combat timing until deliberately re-authored. */
    public static float authoredOrdinaryTicksR45(EvaUnit01Entity e,int stage)
    {
        if(!ready(e))return 0;
        var c=clip(e,ordinary(stage));
        if(!c.has("source_timing_r45")||!c.get("source_timing_r45").getAsBoolean())return 0;
        float seconds=c.get("source_duration_seconds").getAsFloat();
        if(!Float.isFinite(seconds)||seconds<.2F||seconds>2F)
            throw new IllegalStateException("Invalid recovered ordinary source duration");
        return seconds*20F;
    }
    public static boolean selectedThreeStageR45(EvaUnit01Entity e)
    {
        if(!ready(e)||actionStanceR44(e)>0)return false;
        for(String name:List.of("jab","cross","hook","jab_loop"))
        {
            if(!hasClip(e,name))return false;
            var c=clip(e,name);
            if(!c.has("source_timing_r45")||!c.get("source_timing_r45").getAsBoolean())return false;
        }
        return true;
    }
    public static int authoredHeavyTicksR45(EvaUnit01Entity e)
    {
        if(!ready(e))return 0;
        var c=clip(e,"heavy");
        if(!c.has("source_timing_r45")||!c.get("source_timing_r45").getAsBoolean())return 0;
        float seconds=c.get("source_duration_seconds").getAsFloat();
        if(!Float.isFinite(seconds)||seconds<.2F||seconds>4F)
            throw new IllegalStateException("Invalid authored heavy source duration");
        return Math.max(1,Math.round(seconds*20));
    }
    public static boolean inContactWindowR45(EvaUnit01Entity e,String name,float phase)
    {
        float contact=contactPhase(e,name);
        float lead=name.equals("heavy")?.29F:.21F,tail=name.equals("heavy")?.10F:.14F;
        return phase>=Math.max(0,contact-lead)&&phase<=Math.min(.98F,contact+tail);
    }
    public static float swingSoundPhaseR45(EvaUnit01Entity e,String name)
    {return Math.max(0,contactPhase(e,name)-(name.equals("heavy")?.15F:.19F));}
    public static float releasePhase(EvaUnit01Entity e)
    {
        var c=clip(e,ordinary(e.getOrdinaryAttackStage()));
        return c.has("release_phase")?Mth.clamp(c.get("release_phase").getAsFloat(),.65F,.98F):.76F;
    }
    public static EvaBodyPose.Sample committedContactPose(EvaUnit01Entity e)
    {
        if(!phrases(e)||e.getEntityData().get(LOW_TARGET)||e.getOrdinaryAttackStage()<0&&!e.isHeavyMotionActive()&&!EvaBerserkMotionR34.striking(e))return null;
        String name=EvaBerserkMotionR34.striking(e)?EvaBerserkMotionR34.name(e):e.isHeavyMotionActive()?"heavy":ordinary(e.getOrdinaryAttackStage());
        return EvaBodyPose.gameplayClip(e,resolve(e,name),contactPhase(e,name));
    }
    public static String side(EvaUnit01Entity e,String name){return clip(e,name).get("leading_side").getAsString();}
    public static String ordinary(int stage){return switch(stage){case 1->"cross";case 2->"hook";default->"jab";};}
    public static float phase(EvaUnit01Entity e,String name,float progress)
    {
        if(name.startsWith("sword_")||name.startsWith("evade_")||name.startsWith("roll_"))return progress;
        if(name.equals("kick")||name.startsWith("knife_"))return progress;
        if(directed(e)&&name.startsWith("berserk")||EvaCombatSupportR33.ready(e)&&java.util.Set.of("jab","cross","hook","heavy").contains(name))return progress;
        float contact=contactPhase(e,name),at=name.equals("heavy")?.50F:.45F;
        return progress<at?Mth.lerp(progress/at,0,contact):Mth.lerp((progress-at)/(1-at),contact,1);
    }
    public static Vec3 root(EvaUnit01Entity e,String name,float phase)
    {
        phase=phase(e,name,phase);
        var points=clip(e,name).getAsJsonArray("trajectory_m");float f=Mth.clamp(phase,0,1)*(points.size()-1);int a=(int)f,b=Math.min(a+1,points.size()-1);
        var x=points.get(a).getAsJsonArray();var y=points.get(b).getAsJsonArray();return new Vec3(Mth.lerp(f-a,x.get(0).getAsDouble(),y.get(0).getAsDouble()),0,Mth.lerp(f-a,x.get(2).getAsDouble(),y.get(2).getAsDouble()));
    }
    public static float airAge(EvaUnit01Entity e,float partial){return age(e,AIR,partial);}
    public static float landAge(EvaUnit01Entity e,float partial){return age(e,LAND,partial);}
    private static float age(EvaUnit01Entity e,EntityDataAccessor<Long> key,float partial){long since=e.getEntityData().get(key);return since<0?-1:(float)(e.level().getGameTime()-since+partial);}
    public static boolean descending(EvaUnit01Entity e){return e.getEntityData().get(VERTICAL)<-.03F;}
    public static float clearance(EvaUnit01Entity e,float partial){return (float)Math.max(0,Math.min(128,e.getPosition(partial).y-e.getEntityData().get(FLOOR)));}
    public static void tick(EvaUnit01Entity e)
    {
        if(e.level().isClientSide||!ready(e))return;
        var state=STATES.computeIfAbsent(e,key->{var s=new State();s.y=e.getY();return s;});
        String active=activeGroundClip(e,0);
        if(!active.isEmpty())state.previousContact=contact(e,active,0);
        else state.previousContact=null;
        float dy=(float)(e.getY()-state.y);state.y=e.getY();state.velocity=Mth.lerp(.5F,state.velocity,dy);e.getEntityData().set(VERTICAL,state.velocity);
        boolean blocked=e.isNervLogisticsLocked()||e.isFirstBattleActive()||EvaShutdownR30.disabled(e)||com.projectseele.physics.CombatBodyDynamics.active(e)||e instanceof EvaPrototypeEntity un&&un.isUNFlying();
        boolean air=!blocked&&!e.onGround()&&e.isVisuallyAirborneForRender();
        if(air)
        {
            double floor=-1000000;float offset=e.getBbWidth()*.3F;
            for(float[] p:new float[][]{{0,0},{offset,offset},{offset,-offset},{-offset,offset},{-offset,-offset}})
            {
                var from=e.position().add(p[0],1,p[1]);var hit=e.level().clip(new ClipContext(from,from.add(0,-129,0),ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,e));
                if(hit.getType()==HitResult.Type.BLOCK)floor=Math.max(floor,hit.getLocation().y);
            }
            e.getEntityData().set(FLOOR,(float)floor);
            if(!state.air){e.getEntityData().set(AIR,e.level().getGameTime());e.getEntityData().set(LAND,-1L);}
        }
        else if(state.air&&!blocked)
        {
            e.getEntityData().set(LAND_FROM,EvaShutdownR30.encode(EvaBodyPose.sample(e,0)));
            e.getEntityData().set(LAND,e.level().getGameTime());e.getEntityData().set(AIR,-1L);
        }
        if(blocked){e.getEntityData().set(AIR,-1L);e.getEntityData().set(LAND,-1L);}
        state.air=air;
        if(air||blocked||age(e,TAKEOFF,0)>takeoffTicks(e)+5)e.getEntityData().set(TAKEOFF,-1L);
        if(++state.scan%8==0||serverMovement(e)&&!state.guard&&!blocked)
        {
            boolean nearby=!blocked&&e.isPoweredOn()&&sharedWeapon(e)&&!e.isPilotProne()&&!e.isPilotCrouching()
                    &&!e.level().getEntitiesOfClass(net.minecraft.world.entity.LivingEntity.class,e.getBoundingBox().inflate(64,40,64),a->a instanceof Angel&&a.isAlive()).isEmpty();
            state.guard=nearby;
        }
        e.getEntityData().set(GUARD,Mth.approach(e.getEntityData().get(GUARD),state.guard?1:0,EvaCombatSupportR33.ready(e)?.045F:.14F));
        // Keep one movement owner throughout an engagement. Alternating local
        // vehicle prediction and server poses on every punch/recoil made their
        // different-time collision queries repeatedly correct each other.
        boolean hardBlock=e.isNervLogisticsLocked()||e.isFirstBattleActive()||EvaShutdownR30.disabled(e)
                ||e instanceof EvaPrototypeEntity un&&un.isUNFlying()||e.getPilotEntity()==null||!phrases(e);
        boolean owned=serverMovement(e);
        if(hardBlock)owned=false;
        else if(!com.projectseele.physics.CombatBodyDynamics.active(e)&&e.onGround())
            owned=state.guard||EvaBodyPose.runtimeLocomotionR44(e)&&sharedWeapon(e)
                    &&(e.rifleStanceLevel(0)<.01F||lowAttackReadyR44(e));
        e.getEntityData().set(SERVER_MOVEMENT,owned);
    }
    public static boolean owns(EvaUnit01Entity e,float partial)
    {
        if(!ready(e)||e.hasLegacyStrikeForRender()||e.isNervLogisticsLocked()||e.isFirstBattleActive()||EvaShutdownR30.disabled(e)||EvaCombatR31.action(e)>=EvaCombatR31.REACH&&EvaCombatR31.action(e)<=EvaCombatR31.THROW)return false;
        if(e instanceof EvaPrototypeEntity un&&un.isUNFlying())return false;
        if(EvaDorsalMechanism.bow(e)>.001F||EvaDorsalMechanism.open(e)>.001F)return false;
        if(EvaFieldActionsR45.active(e)||EvaSwordActionsR45.active(e))return true;
        if(EvaCombatSupportR33.ready(e)&&sharedWeapon(e)&&!e.hasLiveActionForRender(partial)&&e.rifleStanceLevel(partial)<1)return true;
        return age(e,TAKEOFF,partial)>=0||airAge(e,partial)>=0||landAge(e,partial)>=0&&landAge(e,partial)<18||e.getOrdinaryAttackStage()>=0||e.isHeavyMotionActive()
                ||e.isKickMotionActive(partial)&&kickReady(e)||e.getKnifeMotionType(partial)>=0&&knifeReady(e)
                ||sharedWeapon(e)&&!e.hasLiveActionForRender(partial)&&!e.isPilotProne()&&!e.isPilotCrouching()&&e.getEntityData().get(GUARD)>.01F;
    }
    public static boolean sharedBody(EvaUnit01Entity e,float partial)
    {
        if(EvaWeaponHandlingR45.active(e)||EvaWeaponHandlingR45.holding(e,partial))return true;
        if(owns(e,partial))return true;
        return ready(e)&&EvaBodyPose.hasTerrainStances()&&sharedWeapon(e)
                &&e.isPoweredOn()&&!e.isNervLogisticsLocked()&&!e.isFirstBattleActive()&&!EvaShutdownR30.disabled(e)
                &&e.getVisualPose()==0&&e.getActivationTicks()==0&&e.getMotionLabPhysicsPreview()==0
                &&!e.hasLiveActionForRender(partial)&&!e.hasLegacyStrikeForRender()&&EvaCombatR31.action(e)==EvaCombatR31.NONE
                &&!(e instanceof EvaPrototypeEntity un&&un.isUNFlying());
    }
    /** Read-only inputs at the actual renderer's ownership decision. */
    public static JsonObject ownerDiagnosticR44(EvaUnit01Entity e,float partial)
    {
        JsonObject row=new JsonObject();row.addProperty("variant",variant(e));row.addProperty("profile_ready",ready(e));
        row.addProperty("owns_action_or_locomotion",owns(e,partial));row.addProperty("shared_body",sharedBody(e,partial));row.addProperty("shared_hands",sharedHands(e,partial));
        row.addProperty("powered",e.isPoweredOn());row.addProperty("power_ticks",e.getPowerTicks());row.addProperty("umbilical",e.isUmbilicalConnected());
        row.addProperty("plug_inserted",e.isEntryPlugInserted());row.addProperty("pilot_entity",e.getPilotEntity()==null?-1:e.getPilotEntity().getId());
        row.addProperty("direct_passenger",e.getFirstPassenger()==null?-1:e.getFirstPassenger().getId());row.addProperty("passenger_count",e.getPassengers().size());
        row.addProperty("bay_repair",EvaBayRepairR33.active(e));row.addProperty("shutdown_mode",EvaShutdownR30.mode(e));row.addProperty("berserk_silent",EvaBerserkMotionR34.silent(e));
        row.addProperty("legacy_trigger_playing",e.hasLegacyStrikeForRender());row.addProperty("live_action",e.hasLiveActionForRender(partial));
        row.addProperty("visual_pose",e.getVisualPose());row.addProperty("activation",e.getActivationTicks());row.addProperty("physics_preview",e.getMotionLabPhysicsPreview());
        row.addProperty("locked",e.isNervLogisticsLocked());row.addProperty("first_battle",e.isFirstBattleActive());row.addProperty("weapon",e.getWeapon());row.addProperty("shared_weapon",sharedWeapon(e));
        row.addProperty("stance",e.rifleStanceLevel(partial));row.addProperty("prone_requested",e.isPilotProne());row.addProperty("crouch_requested",e.isPilotCrouching());
        row.addProperty("grapple_action",EvaCombatR31.action(e));row.addProperty("server_movement_owner",serverMovement(e));
        row.addProperty("pilot_locomotion_intent_r45",e.pilotLocomotionRequestedR45());
        row.addProperty("equipment_active_r45",EvaWeaponHandlingR45.active(e));
        if(EvaWeaponHandlingR45.active(e))
        {row.addProperty("equipment_phase_r45",EvaWeaponHandlingR45.phase(e,partial));row.addProperty("knife_draw_phase_r45",EvaWeaponHandlingR45.drawPhase(e,partial));}
        row.addProperty("dorsal_bow",EvaDorsalMechanism.bow(e));row.addProperty("dorsal_open",EvaDorsalMechanism.open(e));
        row.add("body_clip_resolution",EvaBodyPose.clipDiagnosticR44(e));return row;
    }
    public record AppliedPoseR44(EvaBodyPose.Sample pose,boolean capturedMovementSupport) {}
    public static EvaBodyPose.Sample apply(EvaUnit01Entity e,EvaBodyPose.Sample base,float partial)
    {return applyWithCapturedBaseR44(e,base,partial,false).pose();}
    public static AppliedPoseR44 applyWithCapturedBaseR44(EvaUnit01Entity e,EvaBodyPose.Sample base,float partial,boolean capturedBase)
    {
        boolean[] movementOwner={false};
        if(REVIEW_POSE_CHOICES)
        {
            JsonObject row=new JsonObject();row.addProperty("world_tick",e.level().getGameTime());row.addProperty("partial",partial);
            row.addProperty("scope","Actual gameplay pose choice/blend call sites before terrain/reaction/feet; absent fields denote an unrecorded branch.");
            POSE_CHOICES.put(e,row);
        }
        var pose=applyAction(e,base,partial,capturedBase,movementOwner);var tag=e.getEntityData().get(RELEASE_FROM);
        if(tag.isEmpty()||!owns(e,partial)||e.hasLiveActionForRender(partial)||airAge(e,partial)>=0||CombatReactionsR36.active(e)||EvaCombatR31.action(e)!=0)return new AppliedPoseR44(pose,movementOwner[0]);
        float age=e.level().getGameTime()-tag.getLong("release_at")+partial;
        if(age<0||age>=6)return new AppliedPoseR44(pose,movementOwner[0]);
        var from=EvaBodyPose.neutralForTransportR32(e);EvaShutdownR30.decode(tag,from);
        Vec3 origin=e.level().isClientSide?e.getPosition(partial):e.position();
        var shift=new Vector3f((float)(tag.getDouble("release_x")-origin.x),0,(float)(tag.getDouble("release_z")-origin.z))
                .rotateY(-(180-e.getYRot())*Mth.DEG_TO_RAD).div(com.projectseele.entity.EvaScale.RENDER_SCALE);
        from.positions.get("root").add(shift);from.dirty();float u=age/6;u=u*u*(3-2*u);
        reviewWeight(e,"release_to_current_pose_weight",u);reviewWeight(e,"release_age_ticks",age);
        return new AppliedPoseR44(EvaBodyPose.blend(from,pose,u),false);
    }
    public static void releaseToMovement(EvaUnit01Entity e)
    {
        if(e.level().isClientSide||!phrases(e))return;
        var tag=EvaShutdownR30.encode(EvaBodyPose.sample(e,0));tag.putLong("release_at",e.level().getGameTime());tag.putDouble("release_x",e.getX());tag.putDouble("release_z",e.getZ());
        e.getEntityData().set(RELEASE_FROM,tag);
        EvaCombatSupportR33.beginReleaseR44(e);
    }
    private static EvaBodyPose.Sample applyAction(EvaUnit01Entity e,EvaBodyPose.Sample base,float partial,boolean capturedBase,boolean[] movementOwner)
    {
        if(!owns(e,partial)){reviewChoice(e,"owner_branch","base");movementOwner[0]=capturedBase&&EvaCapturedLocomotionR44.SUPPORT_OWNERSHIP_CANDIDATE;return base;}
        if(EvaFieldActionsR45.active(e))
        {
            String name=EvaFieldActionsR45.clip(e);float phase=EvaFieldActionsR45.progress(e,partial),entry=EvaFieldActionsR45.entryProgress(e,partial);
            var pose=EvaBodyPose.gameplayClip(e,name,phase);
            if(entry<1&&!e.getEntityData().get(ACTION_FROM).isEmpty())
            {var from=EvaBodyPose.neutralForTransportR32(e);EvaShutdownR30.decode(e.getEntityData().get(ACTION_FROM),from);pose=EvaBodyPose.blend(from,pose,entry*entry*(3-2*entry));}
            reviewChoice(e,"owner_branch","field_full_body");reviewChoice(e,"effective_action_clip","r32_"+name);reviewWeight(e,"sample_phase",phase);
            return pose;
        }
        if(EvaSwordActionsR45.active(e))return actionPose(e,EvaSwordActionsR45.clip(e),EvaSwordActionsR45.progress(e,partial),base,partial);
        if(EvaBerserkMotionR34.silent(e))return EvaBerserkMotionR34.stillPose(e);
        if(EvaBerserkMotionR34.active(e))return actionPose(e,EvaBerserkMotionR34.name(e),EvaBerserkMotionR34.phase(e,partial),base,partial);
        if(e.isBerserk()&&profile(variant(e)).getAsJsonObject("clips").has("r32_berserk_run"))
        {
            float cycle=e.rifleGaitPhase(partial);cycle-=Mth.floor(cycle);
            var guard=EvaBodyPose.gameplayClip(e,"berserk_guard",(e.tickCount+partial)%100/100);
            var run=EvaBodyPose.gameplayClip(e,"berserk_run",cycle);
            if(hasClip(e,"berserk_walk"))run=EvaBodyPose.blend(EvaBodyPose.gameplayClip(e,"berserk_walk",cycle),run,e.rifleRunBlend(partial));
            return EvaBodyPose.blend(guard,run,e.rifleMoveBlend(partial));
        }
        float air=airAge(e,partial),land=landAge(e,partial);
        if(age(e,TAKEOFF,partial)>=0&&air<0)
        {
            float progress=Math.min(1,age(e,TAKEOFF,partial)/takeoffTicks(e)),contact=clip(e,"jump_start").get("takeoff_phase").getAsFloat();
            var from=EvaBodyPose.neutralForTransportR32(e);EvaShutdownR30.decode(e.getEntityData().get(ACTION_FROM),from);
            return EvaBodyPose.blend(from,EvaBodyPose.gameplayClip(e,"jump_start",progress*contact),progress);
        }
        if(air>=0)
        {
            float takeoff=clip(e,"jump_start").get("takeoff_phase").getAsFloat();
            boolean single=singleFlight(e);
            float flightPhase=descending(e)?.5F+.5F*EvaDorsalMechanism.smooth(1-clearance(e,partial)/28F)
                    :.5F*EvaDorsalMechanism.smooth(air/12F);
            var pose=single?EvaBodyPose.gameplayClip(e,"jump_flight",flightPhase)
                    :air<8?EvaBodyPose.gameplayClip(e,"jump_start",Mth.lerp(air/8,takeoff,1)):EvaBodyPose.gameplayClip(e,"jump_loop",(air-8)%40/40);
            if(single&&air<5)
            {
                var launch=EvaBodyPose.gameplayClip(e,"jump_start",takeoff);
                pose=EvaBodyPose.blend(launch,pose,EvaDorsalMechanism.smooth(air/5));
            }
            var arms=e.getWeapon()==EvaUnit01Entity.WEAPON_FISTS?EvaBodyPose.gameplayClip(e,"guard",(e.level().getGameTime()%120+partial)/120F):base;
            for(String n:pose.rig.keySet())if((!single||e.getWeapon()!=EvaUnit01Entity.WEAPON_FISTS)&&(n.startsWith("arm_")||n.startsWith("forearm_")||n.startsWith("wrist_")||n.startsWith("hand_")))
            {pose.rotations.get(n).slerp(arms.rotations.get(n),.9F);pose.positions.get(n).lerp(arms.positions.get(n),.9F);}pose.dirty();
            float prepare=descending(e)?1-Mth.clamp(clearance(e,partial)/25F,0,1):0;
            if(!single&&prepare>0){float contact=clip(e,"jump_land").get("ground_contact_phase").getAsFloat();pose=EvaBodyPose.blend(pose,EvaBodyPose.gameplayClip(e,"jump_land",contact*prepare),prepare);}
            int action=EvaCombatR31.action(e);
            if(action==EvaCombatR31.AIR_STRIKE||action==EvaCombatR31.AIR_SLAM)
            {
                boolean kick=action==EvaCombatR31.AIR_SLAM;String name=kick?"air_kick":"air_strike";
                float age=EvaCombatR31.age(e,partial),stroke=EvaCombatR31.strokeAge(e,partial),contact=contactPhase(e,name);
                float chamber=Math.max(0,contact-(kick?.14F:.07F));
                float phase=stroke<0?Mth.lerp(Math.min(1,age/4),0,chamber):stroke<5?Mth.lerp(stroke/5,chamber,contact):Mth.lerp(Math.min(1,(stroke-5)/12),contact,1);
                var attack=EvaBodyPose.gameplayClip(e,name,phase);
                // The pelvis drives the recorded downward stroke. Replacing its
                // transform with the idle jump left the fist above the head.
                // Both strokes follow through and return to the flight pose.
                // The old heavy branch froze its contact pose until landing.
                float weight=EvaDorsalMechanism.smooth(age/3)*(1-EvaDorsalMechanism.smooth((stroke-13)/4));
                pose=EvaBodyPose.blend(pose,attack,weight);
            }
            return pose;
        }
        if(land>=0&&land<18&&e.getOrdinaryAttackStage()<0&&!e.isHeavyMotionActive())
        {
            float contact=clip(e,"jump_land").get("ground_contact_phase").getAsFloat();var pose=EvaBodyPose.gameplayClip(e,"jump_land",Mth.lerp(Math.min(1,land/16),contact,1));
            if(land<3){var from=EvaBodyPose.neutralForTransportR32(e);EvaShutdownR30.decode(e.getEntityData().get(LAND_FROM),from);pose=EvaBodyPose.blend(from,pose,land/3);}
            if(land>10)pose=EvaBodyPose.blend(pose,groundLocomotion(e,base,partial,capturedBase,null),(land-10)/8);
            return pose;
        }
        if(e.getOrdinaryAttackStage()>=0){String name=ordinary(e.getOrdinaryAttackStage());return actionPose(e,name,e.getOrdinaryAttackProgress(partial),base,partial);}
        if(e.isHeavyMotionActive())return actionPose(e,"heavy",e.heavyMotionProgress(partial),base,partial);
        String active=activeGroundClip(e,partial);
        if(!active.isEmpty())return actionPose(e,active,activeGroundPhase(e,partial),base,partial);
        return groundLocomotion(e,base,partial,capturedBase,movementOwner);
    }
    private static EvaBodyPose.Sample groundLocomotion(EvaUnit01Entity e,EvaBodyPose.Sample base,float partial,boolean capturedBase,boolean[] movementOwner)
    {
        if(e.getWeapon()==EvaUnit01Entity.WEAPON_SHIELD_R45&&hasClip(e,"shield_idle"))
        {
            var guard=EvaBodyPose.gameplayClip(e,"shield_idle",(e.tickCount+partial)%100/100F);
            if(e.isPilotCrouching()&&hasClip(e,"shield_brace"))
                guard=EvaBodyPose.blend(guard,EvaBodyPose.gameplayClip(e,"shield_brace",.55F),e.rifleCrouchBlend(partial));
            for(String name:java.util.List.of("clavicle_l","arm_l","forearm_l","wrist_l","hand_l"))
                if(base.rig.containsKey(name))
                {base.rotations.put(name,new Quaternionf(guard.rotations.get(name)));base.positions.put(name,new Vector3f(guard.positions.get(name)));}
            base.dirty();if(movementOwner!=null)movementOwner[0]=capturedBase;return base;
        }
        if(e.getWeapon()==EvaUnit01Entity.WEAPON_SWORD_R45&&hasClip(e,"sword_guard"))
        {
            var guard=EvaBodyPose.gameplayClip(e,"sword_guard",(e.tickCount+partial)%80/80F);
            // Locomotion keeps its pelvis and supports. The sword carry affects
            // only the captured shoulder/arm chain, never a frozen lower body.
            for(String name:base.rig.keySet())if(name.startsWith("clavicle_")||name.startsWith("arm_")||name.startsWith("forearm_")||name.startsWith("wrist_")||name.startsWith("hand_"))
            {base.rotations.put(name,new Quaternionf(guard.rotations.get(name)));base.positions.put(name,new Vector3f(guard.positions.get(name)));}
            base.dirty();if(movementOwner!=null)movementOwner[0]=capturedBase;return base;
        }
        reviewChoice(e,"owner_branch","ground_locomotion");reviewChoice(e,"effective_guard_clip","r32_guard");
        // Field travel keeps the accepted locomotion's complete arm swing.
        // The combat advance clips previously replaced it with a cupped guard.
        if(e.pilotLocomotionRequestedR45()&&e.rifleStanceLevel(partial)<.01F)
        {
            if(movementOwner!=null)movementOwner[0]=capturedBase;
            reviewChoice(e,"owner_branch","natural_field_locomotion");return base;
        }
        reviewWeight(e,"guard_phase",(e.level().getGameTime()%120+partial)/120F);
        var guard=EvaBodyPose.gameplayClip(e,"guard",(e.level().getGameTime()%120+partial)/120F);
        float low=Mth.clamp(e.rifleStanceLevel(partial),0,1);low=low*low*(3-2*low);
        float guardBlend=e.getEntityData().get(GUARD)*(1-low);
        if(EvaCapturedLocomotionR44.SUPPORT_OWNERSHIP_CANDIDATE&&capturedBase)
        {
            var pose=EvaBodyPose.blend(base,guard,guardBlend);
            for(String n:base.rig.keySet())if(n.equals("root")||n.equals("torso_lower")||n.startsWith("leg_")||n.startsWith("shin_")||n.startsWith("ankle_")||n.startsWith("foot_"))
            {pose.rotations.put(n,new Quaternionf(base.rotations.get(n)));pose.positions.put(n,new Vector3f(base.positions.get(n)));}
            pose.dirty();if(movementOwner!=null)movementOwner[0]=true;
            reviewChoice(e,"lower_body_owner","captured_movement");reviewWeight(e,"base_to_guard_locomotion_weight",0F);
            reviewWeight(e,"captured_upper_guard_weight",guardBlend);return pose;
        }
        // Pose, stride and footfall timing use the same continuous blend.
        // The old run<.5 switch changed complete hand/leg poses in one frame.
        if(EvaCombatSupportR33.ready(e))
        {
            reviewWeight(e,"base_to_guard_locomotion_weight",EvaCombatSupportR33.gaitWeight(e,partial));
            reviewWeight(e,"guard_to_directional_locomotion_move",e.rifleMoveBlend(partial));
            return EvaBodyPose.blend(base,EvaCombatSupportR33.locomotion(e,guard,partial),EvaCombatSupportR33.gaitWeight(e,partial));
        }
        // Retain the measured locomotion in the legs while keeping the guard up.
        for(String n:base.rig.keySet())if(n.equals("root")||n.startsWith("leg_")||n.startsWith("shin_")||n.startsWith("ankle_")||n.startsWith("foot_"))
        {guard.rotations.get(n).slerp(base.rotations.get(n),e.rifleMoveBlend(partial));guard.positions.get(n).lerp(base.positions.get(n),e.rifleMoveBlend(partial));}
        guard.dirty();return EvaBodyPose.blend(base,guard,guardBlend);
    }
    private static EvaBodyPose.Sample actionPose(EvaUnit01Entity e,String name,float progress,EvaBodyPose.Sample base,float partial)
    {
        String resolved=resolve(e,name);float phase=phase(e,name,progress);
        reviewChoice(e,"owner_branch","action_pose");reviewChoice(e,"effective_action_clip","r32_"+resolved);reviewWeight(e,"sample_phase",phase);
        var pose=EvaBodyPose.gameplayClip(e,resolved,phase);
        if(progress<.18F&&!e.getEntityData().get(ACTION_FROM).isEmpty())
        {var from=EvaBodyPose.neutralForTransportR32(e);EvaShutdownR30.decode(e.getEntityData().get(ACTION_FROM),from);reviewWeight(e,"entry_to_action_weight",progress/.18F);pose=EvaBodyPose.blend(from,pose,progress/.18F);}
        if(progress>.86F&&!phrases(e)){var end=e.getEntityData().get(GUARD)>.5F?EvaBodyPose.gameplayClip(e,"guard",(e.level().getGameTime()%120+partial)/120F):base;pose=EvaBodyPose.blend(pose,end,(progress-.86F)/.14F);}
        if(!(e instanceof EvaPrototypeEntity)&&e.rifleStanceLevel(partial)<.01F
                &&e.rifleMoveBlend(partial)>.001F
                &&java.util.Set.of("jab","cross","hook","heavy","knife_forward","knife_reverse").contains(name))
        {
            // Movement owns the pelvis and legs. The captured strike owns the
            // chest/arms, rebased against that pelvis, rather than freezing the
            // full lower body while the authoritative entity keeps travelling.
            var chest=pose.matrix("torso_upper").getUnnormalizedRotation(new Quaternionf()).normalize();
            float mobility=Mth.clamp(e.rifleMoveBlend(partial),0,1);
            mobility=mobility*mobility*(3-2*mobility);
            Vector3f pelvis=new Vector3f(),basePelvis=new Vector3f();
            for(String side:List.of("l","r"))
            {
                String leg="leg_"+side;
                pelvis.add(pose.matrix(leg).transformPosition(new Vector3f(pose.rig.get(leg).pivot())));
                basePelvis.add(base.matrix(leg).transformPosition(new Vector3f(base.rig.get(leg).pivot())));
            }
            pelvis.mul(.5F).lerp(basePelvis.mul(.5F),mobility);
            for(String n:base.rig.keySet())if(n.equals("root")||n.equals("torso_lower")||n.startsWith("leg_")
                    ||n.startsWith("shin_")||n.startsWith("ankle_")||n.startsWith("foot_")||n.startsWith("toe_"))
            {pose.rotations.get(n).slerp(base.rotations.get(n),mobility);pose.positions.get(n).lerp(base.positions.get(n),mobility);}
            pose.dirty();var actualPelvis=new Vector3f();
            for(String side:List.of("l","r"))
            {String leg="leg_"+side;actualPelvis.add(pose.matrix(leg).transformPosition(new Vector3f(pose.rig.get(leg).pivot())));}
            pose.positions.get("root").add(pelvis.sub(actualPelvis.mul(.5F)));pose.dirty();
            String parent=pose.rig.get("torso_upper").parent();
            var parentRotation=pose.matrix(parent).getUnnormalizedRotation(new Quaternionf()).normalize();
            pose.rotations.put("torso_upper",parentRotation.invert().mul(chest));pose.dirty();
            reviewChoice(e,"lower_body_owner","r45_current_movement");
            reviewWeight(e,"lower_body_movement_weight",mobility);
        }
        return pose;
    }
    public static Vec3 hand(EvaUnit01Entity e,String side,float partial)
    {
        var body=EvaBodyPose.sample(e,partial);String name="hand_"+side;var point=new Vector3f(body.rig.get(name).pivot());String finger="finger_middle_"+side;
        if(body.rig.containsKey(finger))point.lerp(body.rig.get(finger).pivot(),.55F);
        var local=(EvaAnatomicalHandsR45.enabled(e)?EvaAnatomicalHandsR45.contact(e,body,side,partial):body.matrix(name).transformPosition(point))
                .mul(EvaScale.RENDER_SCALE).rotateY((180-EvaAirTransportR31.frameYaw(e,partial))*Mth.DEG_TO_RAD);
        return (e.level().isClientSide?e.getPosition(partial):e.position()).add(local.x,local.y,local.z);
    }
    public static Vec3 contact(EvaUnit01Entity e,String name,float partial)
    {
        var c=clip(e,name);
        if(!c.has("contact_bone"))return hand(e,side(e,name),partial);
        var pose=EvaBodyPose.sample(e,partial);String bone=c.get("contact_bone").getAsString();
        Vector3f point=new Vector3f(pose.rig.get(bone).pivot());
        if(c.has("contact_point_model"))
        {
            var a=c.getAsJsonArray("contact_point_model");point.set(-a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat()).div(16);
        }
        var local=pose.matrix(bone).transformPosition(point).mul(EvaScale.RENDER_SCALE).rotateY((180-EvaAirTransportR31.frameYaw(e,partial))*Mth.DEG_TO_RAD);
        return (e.level().isClientSide?e.getPosition(partial):e.position()).add(local.x,local.y,local.z);
    }
    public static Vec3 airContact(EvaUnit01Entity e,float partial)
    {
        if(EvaCombatR31.action(e)!=EvaCombatR31.AIR_SLAM)return hand(e,side(e,"air_strike"),partial);
        var body=EvaBodyPose.sample(e,partial);String name="foot_"+side(e,"air_kick");
        var point=new Vector3f(body.rig.get(name).pivot());
        var local=body.matrix(name).transformPosition(point).mul(EvaScale.RENDER_SCALE).rotateY((180-EvaAirTransportR31.frameYaw(e,partial))*Mth.DEG_TO_RAD);
        return (e.level().isClientSide?e.getPosition(partial):e.position()).add(local.x,local.y,local.z);
    }
    public static Vec3 previousContact(EvaUnit01Entity e,Vec3 fallback)
    {var s=STATES.get(e);return s==null||s.previousContact==null?fallback:s.previousContact;}
    private EvaGameplayMotionR32(){}
}
