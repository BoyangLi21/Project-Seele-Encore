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
 * Removes pose pops when the full-body owner changes between frames
 * (animator <-> legacy stack).  The difference between the last drawn pose
 * and the new owner's first pose is applied as an offset that decays to zero,
 * so the new motion keeps its own velocity instead of cross-fading against a
 * frozen frame.
 */
final class EvaPoseContinuity
{
    private static final long BLEND_NANOS = 220_000_000L;
    private static final long STALE_NANOS = 300_000_000L;
    private static final WeakIdentityMap<EvaUnit01Entity, State> STATES = new WeakIdentityMap<>();

    private static final class State
    {
        final Map<String, float[]> last = new HashMap<>();
        Map<String, float[]> offsets;
        long blendStart;
        long lastNanos;
        String owner;
    }

    private EvaPoseContinuity() {}

    static void settle(EvaUnit01Entity entity, BakedGeoModel model, String owner)
    {
        long now = System.nanoTime();
        State state = STATES.get(entity);
        if (state == null)
        {
            state = new State();
            STATES.put(entity, state);
        }
        else if (!owner.equals(state.owner) && now - state.lastNanos < STALE_NANOS && !state.last.isEmpty())
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
        }
        if (state.offsets != null)
        {
            float t = (now - state.blendStart) / (float) BLEND_NANOS;
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
                    Vector3f euler = q.getEulerAnglesZYX(new Vector3f());
                    bone.setRotX(euler.x);
                    bone.setRotY(euler.y);
                    bone.setRotZ(euler.z);
                    bone.setPosX(bone.getPosX() + o[4] * w);
                    bone.setPosY(bone.getPosY() + o[5] * w);
                    bone.setPosZ(bone.getPosZ() + o[6] * w);
                });
            }
        }
        State s = state;
        forEach(model, bone -> s.last.put(bone.getName(), new float[] {bone.getRotX(), bone.getRotY(), bone.getRotZ(),
                bone.getPosX(), bone.getPosY(), bone.getPosZ()}));
        state.owner = owner;
        state.lastNanos = now;
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
