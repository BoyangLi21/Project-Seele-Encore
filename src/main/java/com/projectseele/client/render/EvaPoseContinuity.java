package com.projectseele.client.render;

import java.util.HashMap;
import java.util.Map;

import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.util.WeakIdentityMap;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;

/**
 * Removes pose pops at every state change, whichever pose owner draws the
 * body.  A change of owner or of the pilot's pose key (walk -> strike,
 * stand -> prone, weapon swap, ...) captures the difference between the
 * last drawn pose and the new pose, fingers included, as an offset that
 * decays to zero, so the new motion keeps its own velocity instead of
 * cross-fading against a frozen frame.  Strike entries blend briefly to keep
 * their snap; stance and weapon changes take longer.  A body bone that jumps
 * far beyond its previous frame's motion without a key change is caught the
 * same way.
 */
final class EvaPoseContinuity
{
    private static final long OWNER_NANOS = 220_000_000L;
    private static final long POP_NANOS = 120_000_000L;
    private static final float POP_DEGREES = 25.0F;
    private static final long STALE_NANOS = 300_000_000L;
    /** Development diagnostic: log pose pops and tick-held bones (-Dprojectseele.poseDiag=true). */
    private static final boolean DIAG = Boolean.getBoolean("projectseele.poseDiag");
    private static final java.util.Set<String> DIAG_BONES = java.util.Set.of("root", "torso_lower", "torso_upper", "neck", "head",
            "clavicle_l", "arm_l", "forearm_l", "hand_l", "clavicle_r", "arm_r", "forearm_r", "hand_r",
            "leg_l", "shin_l", "foot_l", "leg_r", "shin_r", "foot_r");
    private static final WeakIdentityMap<EvaUnit01Entity, State> STATES = new WeakIdentityMap<>();

    private static final class State
    {
        final Map<String, float[]> last = new HashMap<>();
        final Map<String, Float> step = new HashMap<>();
        final Map<String, Float> drawnStep = new HashMap<>();
        String key = "";
        long blendNanos;
        String trigger = "";
        String rawOwner = "";
        long diagWindow, diagUploads, diagDraws;
        long traceFrame;
        java.util.List<Object[]> trace = new java.util.ArrayList<>(), prevTrace = new java.util.ArrayList<>();
        int diagLines;
        final Map<String, int[]> diagCounts = new HashMap<>();
        Map<String, float[]> offsets;
        long blendStart;
        long lastNanos;
        String owner;
    }

    private EvaPoseContinuity() {}

    static void settle(EvaUnit01Entity entity, BakedGeoModel model, String owner)
    {
        settle(entity, model, owner, owner, 0.0F);
    }

    static void settle(EvaUnit01Entity entity, BakedGeoModel model, String owner, String rawOwner, float partialTick)
    {
        long now = com.projectseele.client.AircraftRenderClockR21.frameNanos();
        trace(entity, model, "settle.in");
        String key = owner + "|" + entity.poseTransitionKey(partialTick);
        State state = STATES.get(entity);
        if (state == null)
        {
            state = new State();
            STATES.put(entity, state);
        }
        // A shader pack draws the body again for its shadow map within the same
        // frame: that pass reuses this frame's blend and must not re-trigger.
        boolean repeat = now == state.lastNanos;
        if (!repeat && now - state.lastNanos < STALE_NANOS && !state.last.isEmpty())
        {
            long blend = !key.equals(state.key) ? transitionNanos(state.key, key)
                    : state.offsets == null && popped(model, state) ? POP_NANOS : 0L;
            if (blend > 0)
            {
                Map<String, float[]> offsets = new HashMap<>();
                State s = state;
                forEach(model, bone ->
                {
                    float[] prev = s.last.get(bone.getName());
                    if (prev == null)
                    {
                        return;
                    }
                    Quaternionf cur = rotation(bone);
                    Quaternionf before = new Quaternionf().rotationZYX(prev[2], prev[1], prev[0]);
                    Quaternionf delta = new Quaternionf(cur).conjugate().mul(before).normalize();
                    offsets.put(bone.getName(), new float[] {delta.x, delta.y, delta.z, delta.w,
                            prev[3] - bone.getPosX(), prev[4] - bone.getPosY(), prev[5] - bone.getPosZ()});
                });
                state.offsets = offsets;
                state.blendStart = now;
                state.blendNanos = blend;
                state.trigger = !key.equals(state.key) ? state.key + "->" + key : "pop";
            }
        }
        Map<String, float[]> raw = null;
        if (state.offsets != null && !repeat)
        {
            Map<String, float[]> captured = new HashMap<>();
            forEach(model, bone -> captured.put(bone.getName(), new float[] {bone.getRotX(), bone.getRotY(), bone.getRotZ(),
                    bone.getPosX(), bone.getPosY(), bone.getPosZ()}));
            raw = captured;
        }
        if (state.offsets != null)
        {
            float t = (now - state.blendStart) / (float) state.blendNanos;
            if (t >= 1)
            {
                state.offsets = null;
            }
            else
            {
                float w = 1 - t * t * (3 - 2 * t);
                Map<String, float[]> offsets = state.offsets;
                Quaternionf identity = new Quaternionf();
                forEach(model, bone ->
                {
                    float[] o = offsets.get(bone.getName());
                    if (o == null)
                    {
                        return;
                    }
                    Quaternionf delta = new Quaternionf(o[0], o[1], o[2], o[3]);
                    Quaternionf q = rotation(bone).mul(new Quaternionf(identity).slerp(delta, w));
                    // JOML 1.10.5 getEulerAnglesZYX does not invert rotationZYX (up to 75
                    // degrees off); the project's channel conversion does.
                    Vector3f euler = QuaternionChannels.euler(q);
                    bone.setRotX(euler.x);
                    bone.setRotY(euler.y);
                    bone.setRotZ(euler.z);
                    bone.setPosX(bone.getPosX() + o[4] * w);
                    bone.setPosY(bone.getPosY() + o[5] * w);
                    bone.setPosZ(bone.getPosZ() + o[6] * w);
                });
            }
        }
        // Pops were only caught with no blend running, so a target that jumped
        // mid-blend (a combo strike taking over the previous one) reached the
        // screen in one frame. Restart the blend from the last drawn pose.
        if (raw != null && state.offsets != null && now != state.blendStart && popped(model, state))
        {
            Map<String, float[]> offsets = new HashMap<>();
            for (var entry : raw.entrySet())
            {
                float[] prev = state.last.get(entry.getKey()), r = entry.getValue();
                if (prev == null)
                {
                    continue;
                }
                Quaternionf before = new Quaternionf().rotationZYX(prev[2], prev[1], prev[0]);
                Quaternionf delta = new Quaternionf().rotationZYX(r[2], r[1], r[0]).conjugate().mul(before).normalize();
                offsets.put(entry.getKey(), new float[] {delta.x, delta.y, delta.z, delta.w, prev[3] - r[3], prev[4] - r[4], prev[5] - r[5]});
            }
            long remaining = state.blendStart + state.blendNanos - now;
            state.offsets = offsets;
            state.blendStart = now;
            state.blendNanos = Math.max(POP_NANOS, remaining);
            state.trigger = state.trigger + "+pop";
            State s = state;
            forEach(model, bone ->
            {
                float[] prev = s.last.get(bone.getName());
                if (prev == null || !offsets.containsKey(bone.getName()))
                {
                    return;
                }
                bone.setRotX(prev[0]);
                bone.setRotY(prev[1]);
                bone.setRotZ(prev[2]);
                bone.setPosX(prev[3]);
                bone.setPosY(prev[4]);
                bone.setPosZ(prev[5]);
            });
        }
        if (DIAG && !state.last.isEmpty())
        {
            if (repeat)
            {
                passMismatch(entity, model, state, rawOwner, partialTick);
            }
            else if (now - state.lastNanos < 100_000_000L)
            {
                diagnose(entity, model, state, rawOwner, partialTick, now);
            }
        }
        if (repeat)
        {
            return;
        }
        State s = state;
        for (String name : DIAG_BONES)
        {
            float[] prev = s.last.get(name);
            GeoBone bone = model.getBone(name).orElse(null);
            if (prev != null && bone != null)
            {
                s.drawnStep.put(name, degrees(rotation(bone), prev));
            }
        }
        forEach(model, bone -> s.last.put(bone.getName(), new float[] {bone.getRotX(), bone.getRotY(), bone.getRotZ(),
                bone.getPosX(), bone.getPosY(), bone.getPosZ()}));
        state.key = key;
        state.owner = owner;
        state.rawOwner = rawOwner;
        state.lastNanos = now;
    }

    /**
     * A pop: a body bone turns far more in one frame than its previous frame
     * predicts.  A held bone: it stays exactly still for a frame between two
     * moving frames (sampled per tick instead of per frame).  Pops are logged
     * as they happen; counts per owner every ten seconds.
     */
    private static void diagnose(EvaUnit01Entity entity, BakedGeoModel model, State state, String rawOwner,
                                 float partialTick, long now)
    {
        if (now - state.diagWindow > 10_000_000_000L)
        {
            if (!state.diagCounts.isEmpty())
            {
                StringBuilder b = new StringBuilder();
                state.diagCounts.forEach((k, v) -> b.append(' ').append(k).append("=frames:").append(v[0])
                        .append("/pops:").append(v[1]).append("/held:").append(v[2]));
                com.projectseele.ProjectSeele.LOGGER.info("POSE DIAG summary eva={}{} skinUploads={} skinDraws={}", entity.getUnitVariant(), b,
                        RigidCapsuleGpu.posedUploads - state.diagUploads, RigidCapsuleGpu.posedDrawCalls - state.diagDraws);
                state.diagUploads = RigidCapsuleGpu.posedUploads;
                state.diagDraws = RigidCapsuleGpu.posedDrawCalls;
                state.diagCounts.clear();
            }
            state.diagWindow = now;
            state.diagLines = 0;
        }
        int[] counts = state.diagCounts.computeIfAbsent(rawOwner, k -> new int[3]);
        counts[0]++;
        String context = null;
        float worst = 0;
        String worstBone = null;
        float worstPrev = 0;
        boolean held = false;
        String heldBone = null;
        for (String name : DIAG_BONES)
        {
            GeoBone bone = model.getBone(name).orElse(null);
            float[] prev = state.last.get(name);
            if (bone == null || prev == null)
            {
                continue;
            }
            Quaternionf before = new Quaternionf().rotationZYX(prev[2], prev[1], prev[0]);
            float deg = (float) Math.toDegrees(rotation(bone).difference(before, new Quaternionf()).angle());
            if (deg > 180) deg = 360 - deg;
            Float last = state.step.put(name, deg);
            float expected = last == null ? 0 : last;
            if (deg > Math.max(9.0F, expected * 2.5F + 4.0F) && deg - expected > worst)
            {
                worst = deg - expected;
                worstBone = name;
                worstPrev = expected;
            }
            if (deg < 0.01F && expected > 0.6F)
            {
                held = true;
                heldBone = name;
            }
        }
        if (held)
        {
            counts[2]++;
            if (state.diagLines++ < 40)
            {
                com.projectseele.ProjectSeele.LOGGER.info("POSE HELD eva={} bone={} key={} dtMs={}", entity.getUnitVariant(), heldBone,
                        entity.poseTransitionKey(partialTick), String.format("%.1f", (now - state.lastNanos) / 1e6));
            }
        }
        if (worstBone != null)
        {
            counts[1]++;
            if (state.diagLines++ < 40)
            {
                context = "weapon=" + entity.getWeapon() + " crouch=" + entity.isPilotCrouching() + " prone=" + entity.isPilotProne()
                        + " stance=" + String.format("%.2f", entity.rifleStanceLevel(partialTick))
                        + " attack=" + entity.getOrdinaryAttackStage() + " heavy=" + entity.isHeavyMotionActive()
                        + " live=" + entity.hasLiveActionForRender(partialTick) + " key=" + entity.poseTransitionKey(partialTick);
                com.projectseele.ProjectSeele.LOGGER.info("POSE POP eva={} owner={} prevOwner={} bone={} jump={} prevStep={} {} stages:{}",
                        entity.getUnitVariant(), rawOwner, state.rawOwner, worstBone, String.format("%.1f", worst + worstPrev),
                        String.format("%.1f", worstPrev), context, traceDelta(state, worstBone)
                        + (state.offsets == null ? " blend=none" : " blend=" + state.trigger + "@" + String.format("%.2f",
                        (now - state.blendStart) / (float) state.blendNanos)));
            }
        }
    }

    /** Development: record the arm-end bones after one pose graph stage. */
    static void traceBegin(EvaUnit01Entity entity, BakedGeoModel model)
    {
        if (!DIAG)
        {
            return;
        }
        State state = STATES.get(entity);
        if (state == null)
        {
            state = new State();
            STATES.put(entity, state);
        }
        long now = com.projectseele.client.AircraftRenderClockR21.frameNanos();
        if (now != state.traceFrame)
        {
            state.prevTrace = state.trace;
            state.traceFrame = now;
        }
        state.trace = new java.util.ArrayList<>();
        trace(entity, model, "begin");
    }

    /** Development: per traced bone, the pose graph stages that turned it this frame. */
    static String writers(EvaUnit01Entity entity)
    {
        State state = DIAG ? STATES.get(entity) : null;
        if (state == null)
        {
            return "";
        }
        StringBuilder b = new StringBuilder();
        for (int column = 1; column <= TRACE_BONES.length; column++)
        {
            b.append(TRACE_BONES[column - 1]).append(':');
            float[] before = null;
            for (Object[] row : state.trace)
            {
                float[] now = (float[]) row[column];
                if (before != null && now != null
                        && degrees(new Quaternionf().rotationZYX(now[2], now[1], now[0]), before) > .5F)
                {
                    b.append(row[0]).append(',');
                }
                if (now != null)
                {
                    before = now;
                }
            }
            b.append(';');
        }
        return b.toString();
    }

    static void trace(EvaUnit01Entity entity, BakedGeoModel model, String stage)
    {
        if (!DIAG)
        {
            return;
        }
        State state = STATES.get(entity);
        if (state == null)
        {
            return;
        }
        Object[] row = new Object[TRACE_BONES.length + 1];
        row[0] = stage;
        for (int i = 0; i < TRACE_BONES.length; i++)
        {
            GeoBone bone = model.getBone(TRACE_BONES[i]).orElse(null);
            row[i + 1] = bone == null ? null : new float[] {bone.getRotX(), bone.getRotY(), bone.getRotZ()};
        }
        state.trace.add(row);
    }

    private static final String[] TRACE_BONES = {"hand_l", "hand_r", "forearm_l", "forearm_r", "arm_l", "arm_r", "cannon", "torso_upper"};

    /** Per stage, how far the popped bone moved since the same stage last frame. */
    private static String traceDelta(State state, String boneName)
    {
        int column = java.util.Arrays.asList(TRACE_BONES).indexOf(boneName) + 1;
        if (column <= 0)
        {
            return "";
        }
        StringBuilder b = new StringBuilder();
        for (Object[] row : state.trace)
        {
            Object[] before = null;
            for (Object[] candidate : state.prevTrace)
            {
                if (candidate[0].equals(row[0]))
                {
                    before = candidate;
                }
            }
            if (before == null || row[column] == null || before[column] == null)
            {
                b.append(' ').append(row[0]).append("=new");
                continue;
            }
            float[] now = (float[]) row[column];
            b.append(' ').append(row[0]).append('=').append(String.format("%.1f",
                    degrees(new Quaternionf().rotationZYX(now[2], now[1], now[0]), (float[]) before[column])));
        }
        return b.toString();
    }

    /** Development: a second render pass of one frame posing a body bone differently from the first. */
    private static void passMismatch(EvaUnit01Entity entity, BakedGeoModel model, State state, String rawOwner, float partialTick)
    {
        for (String name : DIAG_BONES)
        {
            float[] prev = state.last.get(name);
            GeoBone bone = model.getBone(name).orElse(null);
            if (prev == null || bone == null)
            {
                continue;
            }
            float deg = degrees(rotation(bone), prev);
            if (deg > 2.0F && state.diagLines++ < 40)
            {
                com.projectseele.ProjectSeele.LOGGER.info("POSE PASS MISMATCH eva={} owner={} bone={} deg={} key={}",
                        entity.getUnitVariant(), rawOwner, name, String.format("%.1f", deg), entity.poseTransitionKey(partialTick));
            }
        }
    }

    /** Blend length for a change of pose key "owner|weapon:pose[:...]". */
    private static long transitionNanos(String from, String to)
    {
        String[] a = from.split("\\|", 2), b = to.split("\\|", 2);
        if (a.length < 2 || b.length < 2 || !a[0].equals(b[0]))
        {
            return OWNER_NANOS;
        }
        String oldPose = a[1], newPose = b[1];
        if (oldPose.equals("firstbattle") || newPose.equals("firstbattle"))
        {
            return 300_000_000L;
        }
        String oldWeapon = oldPose.split(":", 2)[0], newWeapon = newPose.split(":", 2)[0];
        if (!oldWeapon.equals(newWeapon))
        {
            return 250_000_000L;
        }
        if (strike(newPose))
        {
            return 90_000_000L;
        }
        if (strike(oldPose))
        {
            return 160_000_000L;
        }
        if (newPose.contains("prone") != oldPose.contains("prone") || newPose.contains("crouch") != oldPose.contains("crouch")
                || newPose.contains("airborne") != oldPose.contains("airborne"))
        {
            return 200_000_000L;
        }
        return 150_000_000L;
    }

    private static boolean strike(String pose)
    {
        return pose.contains(":ordinary") || pose.contains(":kick") || pose.contains(":knife") || pose.contains(":smash")
                || pose.contains(":melee");
    }

    /** A body bone turned far more since the last drawn frame than that frame's own motion predicts. */
    private static boolean popped(BakedGeoModel model, State state)
    {
        for (String name : DIAG_BONES)
        {
            float[] prev = state.last.get(name);
            GeoBone bone = model.getBone(name).orElse(null);
            if (prev == null || bone == null)
            {
                continue;
            }
            float deg = degrees(rotation(bone), prev);
            float expected = state.drawnStep.getOrDefault(name, 0.0F);
            if (deg > POP_DEGREES && deg > expected * 3.0F + 8.0F)
            {
                return true;
            }
        }
        return false;
    }

    private static float degrees(Quaternionf current, float[] prev)
    {
        Quaternionf before = new Quaternionf().rotationZYX(prev[2], prev[1], prev[0]);
        float deg = (float) Math.toDegrees(current.difference(before, new Quaternionf()).angle());
        return deg > 180 ? 360 - deg : deg;
    }

    private static Quaternionf rotation(GeoBone bone)
    {
        return new Quaternionf().rotationZYX(bone.getRotZ(), bone.getRotY(), bone.getRotX());
    }

    private static void forEach(BakedGeoModel model, java.util.function.Consumer<GeoBone> action)
    {
        for (GeoBone bone : model.topLevelBones())
        {
            walk(bone, action);
        }
    }

    private static void walk(GeoBone bone, java.util.function.Consumer<GeoBone> action)
    {
        action.accept(bone);
        for (GeoBone child : bone.getChildBones())
        {
            walk(child, action);
        }
    }
}
