package com.projectseele.client.render;

import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;

import com.projectseele.entity.EvaUnit01Entity;
import org.joml.Quaternionf;
import org.joml.Vector3f;
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
        double time = (entity.tickCount + (double)partialTick) / 20.0D;
        String key = entity.poseTransitionKey(partialTick);
        State state = STATES.computeIfAbsent(entity, ignored -> new State());
        double dt = time - state.time;
        if (dt < 0.0D || dt > 0.5D)
        {
            state = new State();
            STATES.put(entity, state);
        }
        boolean changed = !key.equals(state.key);
        if (changed)
        {
            boolean leavingAction=state.liveAction&&!entity.hasLiveActionForRender(partialTick);
            state.liveAction=entity.hasLiveActionForRender(partialTick);
            state.key = key;
            state.start = time;
            state.duration = entity.isPilotCrouching() || entity.isPilotProne()
                    || state.lowStance ? 0.28D
                    : entity.isHeavyMotionActive() ? 0.18D
                    : entity.hasLiveActionForRender(partialTick) ? 0.10D : 0.20D;
            if(sharedExit&&!leavingAction)state.duration=0;
            state.lowStance = entity.isPilotCrouching() || entity.isPilotProne();
            for (Track track : state.bones.values())
            {
                track.begin();
            }
        }
        double age = time - state.start;
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
            var pose=com.projectseele.entity.EvaBodyPose.neutralForTransportR32(entity);
            for(String name:pose.rig.keySet())
                model.getBone(name).ifPresent(b->pose.rotations.put(name,new Quaternionf().rotationZYX(b.getRotZ(),b.getRotY(),b.getRotX())));
            // The offset of a bent hinge is nonlinear in its rotation.
            // Lerp'ing old and new offsets separated the knee/elbow sockets
            // even when both endpoint poses were individually assembled.
            com.projectseele.entity.EvaBodyPose.preserveJointCentres(pose);
            for(String side:new String[]{"l","r"})for(String family:new String[]{"shin_","forearm_"})
            {
                String name=family+side;var offset=pose.positions.get(name);
                if(offset!=null)model.getBone(name).ifPresent(b->{b.setPosX(-offset.x*16);b.setPosY(offset.y*16);b.setPosZ(offset.z*16);});
            }
        }
        state.time = time;
        state.pendingDt = dt;
        state.frameOpen = true;
        state.evaluatedThisFrame = true;
        return new EvaMotionEngineV2.BoneWrites(Set.copyOf(rotations),
                Set.copyOf(positions), OWNER);
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
    }

    public static void recordFinal(EvaUnit01Entity entity,BakedGeoModel model)
    {
        State state=STATES.get(entity);if(state==null)return;
        if(!state.frameOpen)return;
        state.frameOpen=false;
        if(!state.evaluatedThisFrame){STATES.remove(entity);return;}
        state.evaluatedThisFrame=false;
        state.bones.forEach((name,track)->model.getBone(name).ifPresent(bone->{
            Pose pose=Pose.read(bone);
            if(!state.finalInitialized){track.last=pose;track.source=pose;}
            else if(state.pendingDt>1e-6)track.update(pose,state.pendingDt);
            else{track.last=pose;track.linearVelocity.zero();track.angularVelocity.zero();}
        }));
        state.pendingDt=0;
        state.finalInitialized=true;
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
            Quaternionf q = this.rotation;
            bone.setRotX((float)Math.atan2(2.0D * (q.w * q.x + q.y * q.z),
                    1.0D - 2.0D * (q.x * q.x + q.y * q.y)));
            bone.setRotY((float)Math.asin(Math.max(-1.0D, Math.min(1.0D,
                    2.0D * (q.w * q.y - q.z * q.x)))));
            bone.setRotZ((float)Math.atan2(2.0D * (q.w * q.z + q.x * q.y),
                    1.0D - 2.0D * (q.y * q.y + q.z * q.z)));
            bone.setPosX(this.position.x);
            bone.setPosY(this.position.y);
            bone.setPosZ(this.position.z);
            bone.setScaleX(this.scale.x);
            bone.setScaleY(this.scale.y);
            bone.setScaleZ(this.scale.z);
        }
    }
}
