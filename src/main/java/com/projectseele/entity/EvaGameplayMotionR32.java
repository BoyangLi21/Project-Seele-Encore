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
    private static final class State {boolean air,guard;double y;float velocity;int scan;Vec3 previousContact;}
    public static boolean bootstrap(){return true;}
    public static void define(SynchedEntityData d){d.define(AIR,-1L);d.define(LAND,-1L);d.define(TAKEOFF,-1L);d.define(FLOOR,-1000000F);d.define(VERTICAL,0F);d.define(GUARD,0F);d.define(LAND_FROM,new CompoundTag());d.define(ACTION_FROM,new CompoundTag());d.define(LOW_TARGET,false);d.define(SERVER_MOVEMENT,false);d.define(RELEASE_FROM,new CompoundTag());}
    public static boolean serverMovement(EvaUnit01Entity e){return e.getEntityData().get(SERVER_MOVEMENT);}
    public static boolean prepareJump(EvaUnit01Entity e)
    {
        if(!ready(e))return true;
        if(age(e,TAKEOFF,0)<0){beginAction(e);EvaCombatSupportR33.release(e);e.getEntityData().set(TAKEOFF,e.level().getGameTime());return false;}
        return age(e,TAKEOFF,0)>=3;
    }
    public static void beginAction(EvaUnit01Entity e)
    {
        if(!ready(e)||e.level().isClientSide)return;
        beginAction(e,EvaBodyPose.sample(e,0));
    }
    public static void beginAction(EvaUnit01Entity e,EvaBodyPose.Sample pose)
    {
        if(!ready(e)||e.level().isClientSide)return;
        EvaCombatSupportR33.capture(e,pose);e.getEntityData().set(ACTION_FROM,EvaShutdownR30.encode(pose));
        e.getEntityData().set(RELEASE_FROM,new CompoundTag());
        var target=e.level().getEntitiesOfClass(net.minecraft.world.entity.LivingEntity.class,e.getBoundingBox().inflate(36),a->a instanceof Angel&&a.isAlive()
                &&a.position().subtract(e.position()).multiply(1,0,1).normalize().dot(e.getForward())>.35)
                .stream().min(java.util.Comparator.comparingDouble(e::distanceToSqr)).orElse(null);
        e.getEntityData().set(LOW_TARGET,phrases(e)&&target!=null&&com.projectseele.physics.CombatBodyDynamics.active(target)&&target.getBoundingBox().getYsize()<36);
    }
    public static synchronized JsonObject profile(int variant)
    {
        return PROFILES.computeIfAbsent(variant,key->{
            Path file=Path.of("projectseele-local-maps/eva_gameplay_r42_"+key+".json");
            String review=System.getProperty("projectseele.gameplayReviewDirectory", "");
            if(!review.isEmpty()&&"r31-combat".equals(System.getProperty("projectseele.regionalBuild", "")))
                file=Path.of(review).resolve("eva_gameplay_r42_"+key+".json");
            else if(!Files.isRegularFile(file))file=Path.of("projectseele-local-maps/eva_gameplay_r32_"+key+".json");
            if(!Files.isRegularFile(file))return Optional.empty();
            try{var data=JsonParser.parseString(Files.readString(file)).getAsJsonObject();if(data.get("schema").getAsInt()!=2||data.get("rig_key").getAsInt()!=key)throw new IllegalArgumentException("Gameplay rig contract");return Optional.of(data);}
            catch(Exception error){throw new IllegalStateException("Gameplay motion rejected: "+file,error);}
        }).orElse(null);
    }
    public static int variant(EvaUnit01Entity e){return e instanceof EvaPrototypeEntity un?3+un.getUNSerial():e.getUnitVariant();}
    public static float guardWeight(EvaUnit01Entity e){return e.getEntityData().get(GUARD);}
    public static boolean ready(EvaUnit01Entity e){return profile(variant(e))!=null;}
    private static boolean singleFlight(EvaUnit01Entity e)
    {var p=profile(variant(e));return p!=null&&p.has("airborne_revision")&&p.get("airborne_revision").getAsInt()>=42;}
    public static boolean sharedHands(EvaUnit01Entity e,float partial)
    {
        var p=profile(variant(e));return e.getWeapon()==EvaUnit01Entity.WEAPON_FISTS&&p!=null
                &&p.has("hand_pose_revision")&&p.get("hand_pose_revision").getAsInt()>=2&&sharedBody(e,partial);
    }
    public static boolean directed(EvaUnit01Entity e){var p=profile(variant(e));return p!=null&&p.has("combat_foundation")&&p.get("combat_foundation").getAsInt()>=34;}
    public static boolean phrases(EvaUnit01Entity e){var p=profile(variant(e));return p!=null&&p.has("combat_foundation")&&p.get("combat_foundation").getAsInt()>=36;}
    public static boolean naturalRecovery(EvaUnit01Entity e)
    {var p=profile(variant(e));return p!=null&&p.has("natural_recovery")&&p.get("natural_recovery").getAsBoolean();}
    public static boolean planted(EvaUnit01Entity e,String side,float partial)
    {
        if(!directed(e)||!EvaCombatSupportR33.strike(e))return true;
        String name=EvaBerserkMotionR34.striking(e)?EvaBerserkMotionR34.name(e):e.isHeavyMotionActive()?"heavy":ordinary(e.getOrdinaryAttackStage());
        float phase=EvaBerserkMotionR34.striking(e)?EvaBerserkMotionR34.phase(e,partial):e.isHeavyMotionActive()?e.heavyMotionProgress(partial):e.getOrdinaryAttackProgress(partial);
        var frames=clip(e,name).getAsJsonArray("frames");var f=frames.get(Math.min(frames.size()-1,Math.round(Mth.clamp(phase,0,1)*(frames.size()-1)))).getAsJsonObject();
        return f.getAsJsonArray("foot_contact").get(side.equals("l")?0:1).getAsBoolean();
    }
    private static String resolve(EvaUnit01Entity e,String name)
    {return phrases(e)&&e.getEntityData().get(LOW_TARGET)&&java.util.Set.of("jab","cross","hook","heavy").contains(name)?"low_"+name:name;}
    private static JsonObject clip(EvaUnit01Entity e,String name){return profile(variant(e)).getAsJsonObject("clips").getAsJsonObject("r32_"+resolve(e,name));}
    public static float contactPhase(EvaUnit01Entity e,String name){return clip(e,name).get("contact_phase").getAsFloat();}
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
        if(e.getOrdinaryAttackStage()>=0||e.isHeavyMotionActive())
        {String name=e.isHeavyMotionActive()?"heavy":ordinary(e.getOrdinaryAttackStage());state.previousContact=hand(e,side(e,name),0);}
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
        if(air||blocked||age(e,TAKEOFF,0)>8)e.getEntityData().set(TAKEOFF,-1L);
        if(++state.scan%8==0||serverMovement(e)&&!state.guard&&!blocked)
        {
            boolean nearby=!blocked&&e.isPoweredOn()&&e.getWeapon()==EvaUnit01Entity.WEAPON_FISTS&&!e.isPilotProne()&&!e.isPilotCrouching()
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
        else if(!com.projectseele.physics.CombatBodyDynamics.active(e)&&e.onGround())owned=state.guard;
        e.getEntityData().set(SERVER_MOVEMENT,owned);
    }
    public static boolean owns(EvaUnit01Entity e,float partial)
    {
        if(!ready(e)||e.isNervLogisticsLocked()||e.isFirstBattleActive()||EvaShutdownR30.disabled(e)||EvaCombatR31.action(e)>=EvaCombatR31.REACH&&EvaCombatR31.action(e)<=EvaCombatR31.THROW)return false;
        if(e instanceof EvaPrototypeEntity un&&un.isUNFlying())return false;
        if(EvaDorsalMechanism.bow(e)>.001F||EvaDorsalMechanism.open(e)>.001F)return false;
        if(EvaCombatSupportR33.ready(e)&&e.getWeapon()==EvaUnit01Entity.WEAPON_FISTS&&!e.hasLiveActionForRender(partial)&&e.rifleStanceLevel(partial)<1)return true;
        return age(e,TAKEOFF,partial)>=0||airAge(e,partial)>=0||landAge(e,partial)>=0&&landAge(e,partial)<18||e.getOrdinaryAttackStage()>=0||e.isHeavyMotionActive()
                ||e.getWeapon()==EvaUnit01Entity.WEAPON_FISTS&&!e.hasLiveActionForRender(partial)&&!e.isPilotProne()&&!e.isPilotCrouching()&&e.getEntityData().get(GUARD)>.01F;
    }
    public static boolean sharedBody(EvaUnit01Entity e,float partial)
    {
        if(owns(e,partial))return true;
        return ready(e)&&EvaBodyPose.hasTerrainStances()&&e.getWeapon()==EvaUnit01Entity.WEAPON_FISTS
                &&e.isPoweredOn()&&!e.isNervLogisticsLocked()&&!e.isFirstBattleActive()&&!EvaShutdownR30.disabled(e)
                &&e.getVisualPose()==0&&e.getActivationTicks()==0&&e.getMotionLabPhysicsPreview()==0
                &&!e.hasLiveActionForRender(partial)&&EvaCombatR31.action(e)==EvaCombatR31.NONE
                &&!(e instanceof EvaPrototypeEntity un&&un.isUNFlying());
    }
    public static EvaBodyPose.Sample apply(EvaUnit01Entity e,EvaBodyPose.Sample base,float partial)
    {
        var pose=applyAction(e,base,partial);var tag=e.getEntityData().get(RELEASE_FROM);
        if(tag.isEmpty()||!owns(e,partial)||e.getOrdinaryAttackStage()>=0||e.isHeavyMotionActive()||airAge(e,partial)>=0||CombatReactionsR36.active(e)||EvaCombatR31.action(e)!=0)return pose;
        float age=e.level().getGameTime()-tag.getLong("release_at")+partial;
        if(age<0||age>=6)return pose;
        var from=EvaBodyPose.neutralForTransportR32(e);EvaShutdownR30.decode(tag,from);
        Vec3 origin=e.level().isClientSide?e.getPosition(partial):e.position();
        var shift=new Vector3f((float)(tag.getDouble("release_x")-origin.x),0,(float)(tag.getDouble("release_z")-origin.z))
                .rotateY(-(180-e.getYRot())*Mth.DEG_TO_RAD).div(com.projectseele.entity.EvaScale.RENDER_SCALE);
        from.positions.get("root").add(shift);from.dirty();float u=age/6;u=u*u*(3-2*u);
        return EvaBodyPose.blend(from,pose,u);
    }
    public static void releaseToMovement(EvaUnit01Entity e)
    {
        if(e.level().isClientSide||!phrases(e))return;
        var tag=EvaShutdownR30.encode(EvaBodyPose.sample(e,0));tag.putLong("release_at",e.level().getGameTime());tag.putDouble("release_x",e.getX());tag.putDouble("release_z",e.getZ());
        e.getEntityData().set(RELEASE_FROM,tag);
    }
    private static EvaBodyPose.Sample applyAction(EvaUnit01Entity e,EvaBodyPose.Sample base,float partial)
    {
        if(!owns(e,partial))return base;
        if(EvaBerserkMotionR34.silent(e))return EvaBerserkMotionR34.stillPose(e);
        if(EvaBerserkMotionR34.active(e))return actionPose(e,EvaBerserkMotionR34.name(e),EvaBerserkMotionR34.phase(e,partial),base,partial);
        if(e.isBerserk()&&profile(variant(e)).getAsJsonObject("clips").has("r32_berserk_run"))
        {
            float cycle=e.rifleGaitPhase(partial);cycle-=Mth.floor(cycle);
            var guard=EvaBodyPose.gameplayClip(e,"berserk_guard",(e.tickCount+partial)%100/100);
            return EvaBodyPose.blend(guard,EvaBodyPose.gameplayClip(e,"berserk_run",cycle),e.rifleMoveBlend(partial));
        }
        float air=airAge(e,partial),land=landAge(e,partial);
        if(age(e,TAKEOFF,partial)>=0&&air<0)
        {
            float progress=Math.min(1,age(e,TAKEOFF,partial)/3),contact=clip(e,"jump_start").get("takeoff_phase").getAsFloat();
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
                float phase=stroke<0?Mth.lerp(Math.min(1,age/4),0,chamber):stroke<5?Mth.lerp(stroke/5,chamber,contact):kick?contact:Mth.lerp(Math.min(1,(stroke-5)/12),contact,1);
                var attack=EvaBodyPose.gameplayClip(e,name,phase);
                // The pelvis drives the recorded downward stroke. Replacing its
                // transform with the idle jump left the fist above the head.
                float weight=Math.min(1,age/3)*(kick?1:1-Mth.clamp((stroke-13)/4,0,1));
                pose=EvaBodyPose.blend(pose,attack,weight);
            }
            return pose;
        }
        if(land>=0&&land<18&&e.getOrdinaryAttackStage()<0&&!e.isHeavyMotionActive())
        {
            float contact=clip(e,"jump_land").get("ground_contact_phase").getAsFloat();var pose=EvaBodyPose.gameplayClip(e,"jump_land",Mth.lerp(Math.min(1,land/16),contact,1));
            if(land<3){var from=EvaBodyPose.neutralForTransportR32(e);EvaShutdownR30.decode(e.getEntityData().get(LAND_FROM),from);pose=EvaBodyPose.blend(from,pose,land/3);}
            if(land>10)pose=EvaBodyPose.blend(pose,groundLocomotion(e,base,partial),(land-10)/8);
            return pose;
        }
        if(e.getOrdinaryAttackStage()>=0){String name=ordinary(e.getOrdinaryAttackStage());return actionPose(e,name,e.getOrdinaryAttackProgress(partial),base,partial);}
        if(e.isHeavyMotionActive())return actionPose(e,"heavy",e.heavyMotionProgress(partial),base,partial);
        return groundLocomotion(e,base,partial);
    }
    private static EvaBodyPose.Sample groundLocomotion(EvaUnit01Entity e,EvaBodyPose.Sample base,float partial)
    {
        var guard=EvaBodyPose.gameplayClip(e,"guard",(e.level().getGameTime()%120+partial)/120F);
        float low=Mth.clamp(e.rifleStanceLevel(partial),0,1);low=low*low*(3-2*low);
        float guardBlend=e.getEntityData().get(GUARD)*(1-low);
        if(EvaCombatSupportR33.ready(e)&&e.rifleRunBlend(partial)<.5F)return EvaBodyPose.blend(base,EvaCombatSupportR33.locomotion(e,guard,partial),guardBlend);
        // Retain the measured locomotion in the legs while keeping the guard up.
        if(e.rifleMoveBlend(partial)>.1F)for(String n:base.rig.keySet())if(n.equals("root")||n.startsWith("leg_")||n.startsWith("shin_")||n.startsWith("ankle_")||n.startsWith("foot_"))
        {guard.rotations.put(n,base.rotations.get(n));guard.positions.put(n,base.positions.get(n));}
        guard.dirty();return EvaBodyPose.blend(base,guard,guardBlend);
    }
    private static EvaBodyPose.Sample actionPose(EvaUnit01Entity e,String name,float progress,EvaBodyPose.Sample base,float partial)
    {
        var pose=EvaBodyPose.gameplayClip(e,resolve(e,name),phase(e,name,progress));
        if(progress<.18F&&!e.getEntityData().get(ACTION_FROM).isEmpty())
        {var from=EvaBodyPose.neutralForTransportR32(e);EvaShutdownR30.decode(e.getEntityData().get(ACTION_FROM),from);return EvaBodyPose.blend(from,pose,progress/.18F);}
        if(progress>.86F&&!phrases(e)){var end=e.getEntityData().get(GUARD)>.5F?EvaBodyPose.gameplayClip(e,"guard",(e.level().getGameTime()%120+partial)/120F):base;pose=EvaBodyPose.blend(pose,end,(progress-.86F)/.14F);}
        return pose;
    }
    public static Vec3 hand(EvaUnit01Entity e,String side,float partial)
    {
        var body=EvaBodyPose.sample(e,partial);String name="hand_"+side;var point=new Vector3f(body.rig.get(name).pivot());String finger="finger_middle_"+side;
        if(body.rig.containsKey(finger))point.lerp(body.rig.get(finger).pivot(),.55F);
        var local=body.matrix(name).transformPosition(point).mul(EvaScale.RENDER_SCALE).rotateY((180-EvaAirTransportR31.frameYaw(e,partial))*Mth.DEG_TO_RAD);
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
