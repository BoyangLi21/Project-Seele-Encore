package com.projectseele.client.render;

import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;

import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.EvaBodyPose;
import com.projectseele.entity.EvaGameplayMotionR32;
import com.projectseele.entity.FirstBattleSignals;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import org.joml.Matrix4f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;

/** Finite, render-clock transitions of the fully composed pose, including sockets. */
public final class EvaPoseTransition
{
    public static final String OWNER = "POSE_GRAPH_TRANSITION";
    private static final Map<EvaUnit01Entity, State> STATES = new WeakHashMap<>();
    private static final Map<BakedGeoModel, Map<String, RawPose>> GECKO_POSES = new WeakHashMap<>();

    private EvaPoseTransition() {}
    public static void resetEntityR30(EvaUnit01Entity entity){STATES.remove(entity);}
    static boolean retainNormalWeaponHistoryR52(EvaUnit01Entity entity)
    {
        State state=STATES.get(entity);
        return retainNormalWeaponHistoryR52(state!=null&&state.finalInitialized,
                state==null?-1:state.weapon,entity.getWeapon(),
                EvaGameplayMotionR32.sharedBody(entity,0),entity.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE);
    }
    static boolean retainNormalWeaponHistoryR52(boolean finalHistory,int before,int after,boolean sharedTarget,boolean rifleTarget)
    {return finalHistory&&before>=0&&before!=after&&(sharedTarget||rifleTarget);}
    /** Only the new ordinary guard receives a finite release; an incoming
     * attack retains its original phase and existing bounded entry segment. */
    static double sharedExitDurationR52(boolean leavingAction,boolean weaponChanged,boolean action)
    {return weaponChanged&&!action?.20D:leavingAction?.12D:0D;}
    static boolean continuesWeaponExitR52(boolean exiting,double age,double duration,
                                          boolean sameWeapon,boolean incomingAction)
    {return exiting&&age>=0&&age<duration&&sameWeapon&&!incomingAction;}
    private static void rebaseClockR52(State state,double time,boolean shared)
    {
        if(state.clockInitialized&&state.sharedClock!=shared)
        {
            // Preserve age and last-presented channels when the rifle path
            // uses entity tick time instead of the shared presentation clock.
            state.start+=time-state.time;state.time=time;state.pendingDt=0;
        }
        state.sharedClock=shared;state.clockInitialized=true;
    }
    /** A complete pose owner can bypass apply; that frame must not reuse its old pending delta. */
    public static void beginFrameR45(EvaUnit01Entity entity)
    {State state=STATES.get(entity);if(state!=null){state.frameOpen=true;state.evaluatedThisFrame=false;}}

    public static void clear()
    {
        STATES.clear();
        GECKO_POSES.clear();
    }

    // Baked models are shared between entities. Post-Gecko writes must never
    // become another entity's input, or the next frame's weapon reset target.
    public static void restoreGecko(BakedGeoModel model)
    {
        Map<String, RawPose> saved = GECKO_POSES.remove(model);
        if (saved != null)
        {
            saved.forEach((name, pose) -> model.getBone(name).ifPresent(pose::write));
        }
    }

    public static void rememberGecko(BakedGeoModel model)
    {
        Map<String, RawPose> saved = new HashMap<>();
        for(GeoBone bone:model.topLevelBones())rememberGeckoBoneR45(bone,saved);
        GECKO_POSES.put(model, saved);
    }

    private static void rememberGeckoBoneR45(GeoBone bone,Map<String,RawPose> saved)
    {
        saved.put(bone.getName(),RawPose.read(bone));
        for(GeoBone child:bone.getChildBones())rememberGeckoBoneR45(child,saved);
    }

    public static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity entity,
                                                    BakedGeoModel model,
                                                    float partialTick)
    {return apply(entity,model,partialTick,false);}
    public static EvaMotionEngineV2.BoneWrites applySharedExitR45(EvaUnit01Entity entity,BakedGeoModel model,float partialTick)
    {return apply(entity,model,partialTick,true);}
    private static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity entity,BakedGeoModel model,float partialTick,boolean sharedExit)
    {
        if (entity.getMotionLabPhysicsPreview() != 0 || entity.getVisualPose() != 0
                || !entity.isPoweredOn() || entity.isCrucified()
                || entity.isNervLogisticsLocked() || entity.isBerserk()
                || entity.getActivationTicks() > 0)
        {
            STATES.remove(entity);
            return EvaMotionEngineV2.BoneWrites.empty();
        }
        double time = sharedExit?FirstBattleSignals.clientFrameTime()/1_000_000_000D
                :(entity.tickCount + (double)partialTick) / 20.0D;
        String clip=EvaGameplayMotionR32.activeGroundClip(entity,partialTick);
        float actionPhase=clip.isEmpty()?0:EvaGameplayMotionR32.activeGroundPhase(entity,partialTick);
        String key = entity.poseTransitionKey(partialTick)+":"+EvaGameplayMotionR32.resolvedGroundClipR44(entity,partialTick);
        State state = STATES.computeIfAbsent(entity, ignored -> new State());
        state=prepareTransitionR52(state,time,sharedExit,key,clip,actionPhase,
                entity.hasLiveActionForRender(partialTick),com.projectseele.entity.EvaWeaponHandlingR45.active(entity),
                entity.getWeapon(),entity.isPilotCrouching()||entity.isPilotProne(),entity.isHeavyMotionActive(),
                sharedExit&&!clip.isEmpty()&&entity.hasLiveActionForRender(partialTick)
                        ?EvaGameplayMotionR32.actionEntryEndR51(entity,clip):0);
        STATES.put(entity,state);
        double age = time - state.start;
        if(sharedExit&&state.entryCorrection)
        {
            double fraction=Math.max(0,Math.min(1,(actionPhase-state.entryStart)/(state.entryEnd-state.entryStart)));
            age=Math.max(age,state.duration*fraction);
        }
        boolean blending = age < state.duration;
        Set<String> rotations = new LinkedHashSet<>();
        Set<String> positions = new LinkedHashSet<>();
        for (String name : EvaPoseGraph.contract().boneOrder())
        {
            GeoBone bone = model.getBone(name).orElse(null);
            if (bone == null)
            {
                continue;
            }
            Pose target = Pose.read(bone);
            Track track = state.bones.get(name);
            if (track == null)
            {
                state.bones.put(name, new Track(target));
                continue;
            }
            if(state.deferWeaponGuardFinal)
            {
                // Rifle contact and hand writers still run after this call.
                // Blend their composed result at recordFinal, rather than a
                // preliminary pose which those writers immediately replace.
                if(!EvaBodyPose.locomotionBoneR51(name)&&!name.contains("_axis_")
                        &&!Set.of("knife","lance","shield").contains(name))
                {rotations.add(name);positions.add(name);}
                continue;
            }
            // A small last-presented residual ends in the source entry segment,
            // before its contact phase. No attack clock is resampled or held;
            // pelvis, feet and their authoritative support remain untouched.
            if(sharedExit&&(!blending||EvaBodyPose.locomotionBoneR51(name)
                    ||name.equals("knife")||name.equals("lance")||name.equals("shield")||name.contains("_axis_")))continue;
            Pose result = blending ? track.sample(target, age, state.duration) : target;
            result.write(bone);
            if (blending)
            {
                rotations.add(name);
                positions.add(name);
            }
        }
        if(sharedExit&&blending)
        {
            var pose=EvaBodyPose.neutralForTransportR32(entity);
            for(String name:pose.rig.keySet())
                model.getBone(name).ifPresent(b->{
                    pose.rotations.put(name,new Quaternionf().rotationZYX(b.getRotZ(),b.getRotY(),b.getRotX()));
                    pose.positions.put(name,new Vector3f(-b.getPosX(),b.getPosY(),b.getPosZ()).div(16));
                });
            EvaBodyPose.preserveJointCentres(pose);
            for(String side:new String[]{"l","r"})for(String family:new String[]{"forearm_"})
            {
                String name=family+side;var offset=pose.positions.get(name);
                if(offset!=null)model.getBone(name).ifPresent(b->{b.setPosX(-offset.x*16);b.setPosY(offset.y*16);b.setPosZ(offset.z*16);});
            }
            String attachment=entity.getWeapon()==EvaUnit01Entity.WEAPON_KNIFE?"knife"
                    :entity.getWeapon()==EvaUnit01Entity.WEAPON_SWORD_R45?"lance"
                    :entity.getWeapon()==EvaUnit01Entity.WEAPON_SHIELD_R45?"shield":"";
            if(attachment.equals("knife"))com.projectseele.entity.EvaAnatomicalHandsR45.attachKnife(entity,pose);
            else if(attachment.equals("lance"))com.projectseele.entity.EvaAnatomicalHandsR45.attachSwordR45(entity,pose);
            else if(attachment.equals("shield"))com.projectseele.entity.EvaShieldRigR47.attach(entity,pose);
            if(!attachment.isEmpty())
            {
                var q=pose.rotations.get(attachment);var p=pose.positions.get(attachment);
                if(q!=null&&p!=null)model.getBone(attachment).ifPresent(b->{
                    EvaRigTransforms.rotate(b,q);b.setPosX(-p.x*16);b.setPosY(p.y*16);b.setPosZ(p.z*16);
                    rotations.add(attachment);positions.add(attachment);
                });
            }
        }
        return new EvaMotionEngineV2.BoneWrites(Set.copyOf(rotations),
                Set.copyOf(positions), OWNER);
    }

    /** Resolved source inputs share the same real State path in native render
     * and the recorded branch replay; no second transition implementation. */
    private static State prepareTransitionR52(State state,double time,boolean sharedExit,String key,String clip,
            float actionPhase,boolean liveAction,boolean handling,int weapon,boolean lowStance,boolean heavy,float entryEnd)
    {
        rebaseClockR52(state,time,sharedExit);
        double dt = time - state.time;
        if (dt < 0.0D || dt > 0.5D)
        {
            state = new State();
            rebaseClockR52(state,time,sharedExit);
        }
        boolean changed = !key.equals(state.key)||(sharedExit&&!clip.isEmpty()
                &&state.liveAction&&actionPhase+.15F<state.actionPhase);
        if(changed&&continuesWeaponExitR52(state.weaponGuardExit,time-state.start,
                state.duration,state.weapon==weapon,liveAction))
        {
            // A walk/idle key change during handoff updates the current target,
            // without cancelling or restarting its finite upper-body release.
            state.key=key;changed=false;
        }
        if (changed)
        {
            boolean leavingAction=state.liveAction&&!liveAction;
            boolean weaponChanged=state.weapon>=0&&state.weapon!=weapon&&!handling;
            state.liveAction=liveAction;
            state.key = key;
            state.start = time;
            state.duration = lowStance || state.lowStance ? 0.28D
                    : heavy ? 0.18D : liveAction ? 0.10D : 0.20D;
            state.entryCorrection=false;
            state.weaponGuardExit=weaponChanged&&!state.liveAction;
            if(sharedExit)
            {
                state.duration=sharedExitDurationR52(leavingAction,weaponChanged,state.liveAction);
                if(!clip.isEmpty()&&liveAction)
                {
                    state.entryStart=actionPhase;state.entryEnd=entryEnd;
                    state.entryCorrection=state.entryEnd>state.entryStart;
                    state.duration=state.entryCorrection?.06D:0;
                }
            }
            state.lowStance = lowStance;
            for (Track track : state.bones.values())
            {
                track.begin();
            }
        }
        double age = time - state.start;
        if(age>=state.duration)state.weaponGuardExit=false;
        state.deferWeaponGuardFinal=state.weaponGuardExit&&!sharedExit&&weapon==EvaUnit01Entity.WEAPON_RIFLE;
        state.time = time;
        state.weapon=weapon;
        state.actionPhase=actionPhase;
        if(dt>1e-6)state.pendingDt = dt;
        state.frameOpen = true;
        state.evaluatedThisFrame = true;
        return state;
    }

    private static final class State
    {
        private final Map<String, Track> bones = new HashMap<>();
        private String key = "";
        private double time;
        private double start;
        private double duration;
        private boolean lowStance;
        private boolean liveAction;
        private double pendingDt;
        private boolean finalInitialized;
        private boolean evaluatedThisFrame;
        private boolean frameOpen;
        private long recordedFrame=Long.MIN_VALUE;
        private float actionPhase,entryStart,entryEnd;
        private boolean entryCorrection;
        private boolean weaponGuardExit;
        private int weapon=-1;
        private boolean clockInitialized,sharedClock,deferWeaponGuardFinal;
    }

    public static void recordFinal(EvaUnit01Entity entity,BakedGeoModel model)
    {
        State state=STATES.get(entity);if(state==null)return;
        if(!state.frameOpen)return;
        state.frameOpen=false;
        if(!state.evaluatedThisFrame){STATES.remove(entity);return;}
        state.evaluatedThisFrame=false;
        long frame=FirstBattleSignals.clientFrameTime();
        if(state.recordedFrame==frame)return;
        state.recordedFrame=frame;
        if(state.deferWeaponGuardFinal&&state.weaponGuardExit)applyFinalWeaponGuardR52(state,model);
        state.bones.forEach((name,track)->model.getBone(name).ifPresent(bone->{
            Pose pose=Pose.read(bone);
            if(!state.finalInitialized){track.last=pose;track.source=pose;}
            else if(state.pendingDt>1e-6)track.update(pose,state.pendingDt);
            else track.last=pose;
        }));
        state.pendingDt=0;
        state.finalInitialized=true;
    }
    private static void applyFinalWeaponGuardR52(State state,BakedGeoModel model)
    {
        double age=Math.max(0,state.time-state.start);if(age>=state.duration)return;
        GeoBone hand=model.getBone("hand_r").orElse(null),gun=model.getBone("cannon").orElse(null);
        Matrix4f handToGun=hand==null||gun==null?null:EvaRigTransforms.model(hand).invert().mul(EvaRigTransforms.model(gun));
        for(var entry:state.bones.entrySet())
        {
            String name=entry.getKey();if(EvaBodyPose.locomotionBoneR51(name)||name.contains("_axis_")
                    ||Set.of("knife","lance","shield","cannon").contains(name))continue;
            model.getBone(name).ifPresent(bone->entry.getValue().sample(Pose.read(bone),age,state.duration).write(bone));
        }
        for(String side:new String[]{"l","r"})model.getBone("forearm_"+side)
                .ifPresent(bone->EvaRigTransforms.hinge(bone,EvaRigTransforms.elbow(bone,side)));
        // The new rifle remains rigidly fitted to the final moving right hand.
        // Its own source dimensions, scale and eventual ready pose are retained.
        if(handToGun!=null)writeModelR52(gun,EvaRigTransforms.model(hand).mul(handToGun));
    }
    private static void writeModelR52(GeoBone bone,Matrix4f desired)
    {
        Matrix4f local=bone.getParent()==null?new Matrix4f(desired):EvaRigTransforms.model(bone.getParent()).invert().mul(desired);
        Vector3f pivot=EvaRigTransforms.pivot(bone);
        Vector3f offset=local.getTranslation(new Vector3f()).sub(pivot).add(local.transformDirection(new Vector3f(pivot)));
        new Pose(local.getUnnormalizedRotation(new Quaternionf()).normalize(),
                new Vector3f(-offset.x*16,offset.y*16,offset.z*16),local.getScale(new Vector3f())).write(bone);
    }

    private static final class Track
    {
        private Pose last;
        private Pose source;
        private final Vector3f linearVelocity = new Vector3f();
        private final Vector3f angularVelocity = new Vector3f();
        private final Vector3f sourceLinear = new Vector3f();
        private final Vector3f sourceAngular = new Vector3f();

        private Track(Pose initial)
        {
            this.last = initial;
            this.source = initial;
        }

        private void begin()
        {
            this.source = this.last;
            this.sourceLinear.set(this.linearVelocity);
            this.sourceAngular.set(this.angularVelocity);
        }

        private Pose sample(Pose target, double age, double duration)
        {
            float s = (float)Math.max(0.0D, Math.min(1.0D, age / duration));
            float weight = s * s * s * (10.0F + s * (-15.0F + 6.0F * s));
            float prediction = (float)age * (1.0F - s) * (1.0F - s);
            Vector3f rotationStep = new Vector3f(this.sourceAngular).mul(prediction);
            Quaternionf predicted = exponential(rotationStep).mul(this.source.rotation);
            return new Pose(predicted.slerp(target.rotation, weight).normalize(),
                    new Vector3f(this.source.position).fma(prediction, this.sourceLinear)
                            .lerp(target.position, weight),
                    new Vector3f(this.source.scale).lerp(target.scale, weight));
        }

        private void update(Pose result, double dt)
        {
            this.linearVelocity.set(result.position).sub(this.last.position).div((float)dt);
            this.angularVelocity.set(logarithm(new Quaternionf(result.rotation)
                    .mul(new Quaternionf(this.last.rotation).conjugate()))).div((float)dt);
            limit(this.linearVelocity, 320.0F);
            limit(this.angularVelocity, 12.0F);
            this.last = result;
        }
    }

    private static void limit(Vector3f vector, float maximum)
    {
        if (vector.lengthSquared() > maximum * maximum)
        {
            vector.normalize(maximum);
        }
    }

    private static Vector3f logarithm(Quaternionf q)
    {
        q.normalize();
        if (q.w < 0.0F) q.set(-q.x, -q.y, -q.z, -q.w);
        float length = (float)Math.sqrt(q.x * q.x + q.y * q.y + q.z * q.z);
        float factor = length < 1.0E-6F ? 2.0F
                : 2.0F * (float)Math.atan2(length, q.w) / length;
        return new Vector3f(q.x, q.y, q.z).mul(factor);
    }

    private static Quaternionf exponential(Vector3f vector)
    {
        float angle = vector.length();
        return angle < 1.0E-6F ? new Quaternionf()
                : new Quaternionf().rotationAxis(angle,
                        vector.x / angle, vector.y / angle, vector.z / angle);
    }

    private record RawPose(float x, float y, float z, float px, float py, float pz,
                           float sx, float sy, float sz)
    {
        private static RawPose read(GeoBone bone)
        {
            return new RawPose(bone.getRotX(), bone.getRotY(), bone.getRotZ(),
                    bone.getPosX(), bone.getPosY(), bone.getPosZ(),
                    bone.getScaleX(), bone.getScaleY(), bone.getScaleZ());
        }

        private void write(GeoBone bone)
        {
            bone.setRotX(this.x); bone.setRotY(this.y); bone.setRotZ(this.z);
            bone.setPosX(this.px); bone.setPosY(this.py); bone.setPosZ(this.pz);
            bone.setScaleX(this.sx); bone.setScaleY(this.sy); bone.setScaleZ(this.sz);
        }
    }

    private record Pose(Quaternionf rotation, Vector3f position, Vector3f scale)
    {
        private static Pose read(GeoBone bone)
        {
            return new Pose(new Quaternionf().rotationZYX(bone.getRotZ(),
                    bone.getRotY(), bone.getRotX()),
                    new Vector3f(bone.getPosX(), bone.getPosY(), bone.getPosZ()),
                    new Vector3f(bone.getScaleX(), bone.getScaleY(), bone.getScaleZ()));
        }

        private void write(GeoBone bone)
        {
            // Rz Ry Rx, matching RenderUtils and Blender's authored XYZ.
            Vector3f channels = QuaternionChannels.euler(this.rotation);
            bone.setRotX(channels.x);
            bone.setRotY(channels.y);
            bone.setRotZ(channels.z);
            bone.setPosX(this.position.x);
            bone.setPosY(this.position.y);
            bone.setPosZ(this.position.z);
            bone.setScaleX(this.scale.x);
            bone.setScaleY(this.scale.y);
            bone.setScaleZ(this.scale.z);
        }
    }
}
