package com.projectseele.client.render;

import com.projectseele.entity.FirstBattleClip;
import com.projectseele.entity.FirstBattleSignals;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;

/**
 * Sachiel in the first-battle finale, solved every frame against Unit-01's
 * body instead of replaying limb angles authored for another mesh. The clip
 * still owns where the body is and when things happen; each phase below
 * blends in from whatever pose precedes it.
 *
 * <ul>
 * <li>Stand-off (0-6.1 s): upright and hunched, claws raised at Unit-01.</li>
 * <li>Grab (5.6-9.5 s): the arm Unit-01 seizes goes into its hand and is
 * hauled straight; the free arm claws at its shoulder; the trunk leans back
 * against the pull until the yank throws it forward.</li>
 * <li>Pinned (11.6-17.7 s): on its back with its core under Unit-01's fists,
 * arms and knees jerking up at every blow.</li>
 * <li>Embrace (17.0-18.7 s): it springs onto Unit-01's chest, arms round the
 * shoulders, legs round the waist, and squeezes, shaking, until the cross.</li>
 * </ul>
 */
final class FirstBattleAngelR58
{
    private static final String[] NAMES = {"root", "torso_lower", "torso_upper", "neck", "head",
            "arm_l", "forearm_l", "hand_l", "leg_l", "shin_l", "foot_l",
            "arm_r", "forearm_r", "hand_r", "leg_r", "shin_r", "foot_r"};
    /** Ankle pivot height of the standing mesh, blocks. */
    private static final float ANKLE = 3.5F;
    private static final int ROOT = 0, TORSO_UPPER = 2, HEAD = 4, ARM_L = 5, ARM_R = 11;

    static final float STAND_END = 6.1F;
    static final float GRAB_IN = 5.6F, GRAB_FULL = 6.1F, YANK = 8.4F, GRAB_OUT = 9.1F, GRAB_END = 9.5F;
    static final float PIN_IN = 9.5F, PIN_FULL = 10.9F, PIN_END = 17.7F;
    static final float RISE = 17.0F, HOLD = 17.7F, END = 18.7F;

    private FirstBattleAngelR58() {}

    /** Sachiel's shoulders during the grab, published for Unit-01's hands (one frame behind at most). */
    private static Vec3[] shoulders;
    private static float shouldersAt = -1;

    static Vec3[] shoulders(float time) { return shoulders != null && Math.abs(time - shouldersAt) < .25F ? shoulders : null; }

    private static Vec3 vec(Vector3f v) { return new Vec3(v.x, v.y, v.z); }

    /** Sachiel's waist, neck and head this frame, for the review checks. */
    private static Vec3[] body;
    private static float bodyAt = -1;

    static Vec3[] body(float time) { return body != null && Math.abs(time - bodyAt) < .25F ? body : null; }

    /** Sachiel's waist as the grapple began. */
    private static Vec3 grabAnchor;

    /** Sachiel's waist when Unit-01 let go: the throw starts there. */
    private static Vec3 released;
    private static float releasedAt = -1;

    private record Frame(GeoBone[] bones, Matrix4f root, Vec3 origin, float yaw, double ground) {}

    /** {@code root}: the renderer's own model-to-world matrix for this frame. */
    static void apply(Entity angel, BakedGeoModel model, FirstBattleSignals.Spec spec, float time, float partial, Matrix4f root)
    {
        GeoBone[] bones = new GeoBone[NAMES.length];
        for (int i = 0; i < NAMES.length; i++)
        {
            bones[i] = model.getBone(NAMES[i]).orElse(null);
            if (bones[i] == null) return;
        }
        Vector3f at = root.getTranslation(new Vector3f());
        Vec3 origin = new Vec3(at.x, at.y, at.z);
        float yaw = FirstBattleClip.yaw(spec, false, time);
        Frame f = new Frame(bones, root, origin, yaw, spec.origin().y);
        if (time < 1) grabAnchor = null;
        if (time <= STAND_END) blend(f, ramp(time, 0, .4F, STAND_END - .01F, STAND_END), () -> standoff(f, spec, time));
        if (time >= GRAB_IN && time <= GRAB_END) blend(f, ramp(time, GRAB_IN, GRAB_FULL, GRAB_OUT, GRAB_END), () -> grab(f, spec, time));
        if (time >= PIN_IN && time <= PIN_END) blend(f, ramp(time, PIN_IN, PIN_IN + .15F, PIN_END - .01F, PIN_END), () -> pinned(f, spec, time));
        if (time >= RISE && time <= END) blend(f, ramp(time, RISE, HOLD, END, END + 1), () -> embrace(f, spec, time));
        body = new Vec3[] {vec(point(f, TORSO_UPPER)), vec(point(f, TORSO_UPPER + 1)), vec(point(f, HEAD))};
        bodyAt = time;
    }

    // ------------------------------------------------------------------ phases

    private static void standoff(Frame f, FirstBattleSignals.Spec spec, float time)
    {
        Vec3 eva = FirstBattleClip.point(spec, true, "root_blocks", time);
        Vec3 toward = horizontal(eva.subtract(f.origin), f.yaw);
        float breath = .04F * Mth.sin(time * 2.1F);
        lean(f, toward, .16F + breath);
        f.bones[HEAD].setRotX(.15F);
        Vec3 side = new Vec3(-toward.z, 0, toward.x);
        for (int arm : new int[] {ARM_L, ARM_R})
        {
            double sign = sideOf(f, arm, side);
            Vector3f shoulder = point(f, arm);
            // Claws held before the chest toward Unit-01, swaying with the breath.
            Vec3 hand = new Vec3(shoulder.x, shoulder.y, shoulder.z).add(toward.scale(2.5)).add(side.scale(sign * -2))
                    .add(0, -13 + 1.5 * Mth.sin(time * 1.7F + (float) sign), 0);
            limb(f, arm, hand, side.scale(sign).add(0, -.5, 0).add(toward.scale(-.5)), 0);
        }
        legs(f, toward, side, null);
    }

    private static void grab(Frame f, FirstBattleSignals.Spec spec, float time)
    {
        Vec3 eva = FirstBattleClip.point(spec, true, "root_blocks", time);
        Vec3 toward = horizontal(eva.subtract(f.origin), f.yaw);
        Vec3 side = new Vec3(-toward.z, 0, toward.x);
        float yank = smooth((time - YANK) / (GRAB_OUT - YANK));
        // Seized by the shoulders and driven back: the trunk arches away,
        // then is wrenched toward Unit-01 as it twists into the throw.
        lean(f, toward, -.18F + .5F * yank);
        if (time < GRAB_IN + .06F || grabAnchor == null) grabAnchor = vec(point(f, TORSO_UPPER));
        float drive = smooth((time - GRAB_IN) / (YANK - GRAB_IN));
        place(f, TORSO_UPPER, grabAnchor.subtract(toward.scale(4 * drive - 6 * yank)));
        shoulders = new Vec3[] {vec(point(f, ARM_L)), vec(point(f, ARM_R))};
        shouldersAt = time;
        released = vec(point(f, TORSO_UPPER));
        releasedAt = time;
        Vec3[] grips = FirstBattleHeroR58.forearms(time);
        for (int arm : new int[] {ARM_L, ARM_R})
        {
            double sign = sideOf(f, arm, side);
            Vec3 s = vec(point(f, arm));
            Vec3 hold = null;
            if (grips != null)
                hold = grips[0].distanceToSqr(s) < grips[1].distanceToSqr(s) ? grips[0] : grips[1];
            // Claws clamped on the forearm that holds this shoulder; without it, guarding.
            Vec3 target = hold != null ? hold : s.add(toward.scale(8)).add(0, -12, 0).add(side.scale(sign * 3));
            limb(f, arm, target, side.scale(sign).add(0, -.5, 0).add(toward.scale(-.3)), .5F);
        }
        legs(f, toward, side, null);
    }

    private static void pinned(Frame f, FirstBattleSignals.Spec spec, float time)
    {
        Vec3 front = Vec3.directionFromRotation(0, FirstBattleClip.yaw(spec, true, time)).multiply(1, 0, 1).normalize();
        Vec3 core = FirstBattleHeroR58.core(spec, time);
        float jerk = jerk(time);
        for (int i = 1; i < f.bones.length; i++) zero(f.bones[i]);
        // On its back: the body's long axis runs away from Unit-01, its chest to
        // the sky. Before that it is thrown there: a short arc from where
        // Unit-01 let go, turning from upright onto its back as it falls.
        float flight = Mth.clamp((time - PIN_IN) / (PIN_FULL - PIN_IN), 0, 1);
        boolean thrown = flight < 1 && released != null && Math.abs(releasedAt - PIN_IN) < 1.5F;
        Quaternionf supine = new Quaternionf().rotationTo(new Vector3f(0, 1, 0), toF(front));
        Quaternionf turn = thrown ? new Quaternionf().slerp(supine, smooth(flight)) : supine;
        Quaternionf world = turn.mul(EvaRigTransforms.rotation(f.root));
        EvaRigTransforms.rotate(f.bones[ROOT], EvaRigTransforms.rotation(f.root).invert().mul(world));
        f.bones[HEAD].setRotX(-.25F - .35F * jerk);
        // The core, a little above the waist on the chest's face, lies under the fists.
        Vec3 waist = core.subtract(front.scale(5.4)).add(0, -5.1 - 1.2 * jerk, 0);
        if (thrown)
        {
            float u = smooth(flight);
            waist = released.lerp(waist, u).add(0, 9 * 4 * flight * (1 - flight), 0);
        }
        place(f, TORSO_UPPER, waist);
        Vec3 side = new Vec3(-front.z, 0, front.x);
        for (int arm : new int[] {ARM_L, ARM_R})
        {
            double sign = sideOf(f, arm, side);
            Vector3f s = point(f, arm);
            Vec3 hand = new Vec3(s.x, f.ground + 2 + 11 * jerk, s.z).add(side.scale(sign * 13)).add(front.scale(-4 + 3 * jerk));
            limb(f, arm, hand, side.scale(sign).add(0, .5, 0), .5F);
        }
        for (int s = 0; s < 2; s++)
        {
            int leg = s == 0 ? ARM_L + 3 : ARM_R + 3;
            Vector3f hip = point(f, leg);
            double sign = sideOf(f, leg, side);
            Vec3 foot = new Vec3(hip.x, f.ground + ANKLE + 4 * jerk, hip.z).add(front.scale(-16)).add(side.scale(sign * 6));
            limb(f, leg, foot, new Vec3(0, 1, 0).add(side.scale(sign * .4)), -.3F);
        }
    }

    private static void embrace(Frame f, FirstBattleSignals.Spec spec, float time)
    {
        Vec3 socket = FirstBattleClip.point(spec, true, "socket_blocks", time);
        Vec3 front = Vec3.directionFromRotation(0, FirstBattleClip.yaw(spec, true, time)).multiply(1, 0, 1).normalize();
        Vec3 side = new Vec3(-front.z, 0, front.x);
        Vec3 evaRoot = FirstBattleClip.point(spec, true, "root_blocks", time);
        float hold = Mth.clamp((time - HOLD) / (END - HOLD), 0, 1);
        float squeeze = hold * hold;
        float shake = hold * .35F * Mth.sin(time * 44F) + hold * .2F * Mth.sin(time * 71F);
        lean(f, front.scale(-1), .28F + .1F * squeeze);
        f.bones[TORSO_UPPER].setRotX(.12F);
        f.bones[HEAD].setRotX(.35F);
        place(f, TORSO_UPPER, socket.add(front.scale(12.5 - 1.5 * squeeze)).add(0, -21 + shake, 0).add(side.scale(shake * .6)));
        for (int arm : new int[] {ARM_L, ARM_R})
        {
            double sign = sideOf(f, arm, side);
            limb(f, arm, socket.add(side.scale(sign * (8.5 - 2.5 * squeeze))).add(0, -7.5, 0).add(front.scale(-2.5 - squeeze)),
                    side.scale(sign).add(0, .45, 0).add(front.scale(.3)), .5F);
            int leg = arm + 3;
            limb(f, leg, evaRoot.add(side.scale(sign * (8.5 - 2 * squeeze))).add(0, 17, 0).add(front.scale(-2.5)),
                    side.scale(sign).add(0, .7, 0).add(front.scale(.6)), -.6F);
        }
    }

    // ------------------------------------------------------------------ helpers

    /** Strength of the recoil from the nearest of Unit-01's blows. */
    private static float jerk(float time)
    {
        float strongest = 0;
        for (float blow : FirstBattleHeroR58.BLOWS)
        {
            float since = time - blow;
            if (since >= 0 && since < .6F) strongest = Math.max(strongest, (float) Math.exp(-since / .12F));
        }
        return strongest;
    }

    /** Trunk upright, its top tipped by {@code amount} toward {@code toward}; spine bones straightened. */
    private static void lean(Frame f, Vec3 toward, float amount)
    {
        for (int i = 1; i < f.bones.length; i++) zero(f.bones[i]);
        Vector3f up = new Vector3f(0, 1, 0).fma(amount, toF(toward)).normalize();
        Quaternionf world = new Quaternionf().rotationTo(new Vector3f(0, 1, 0), up).mul(EvaRigTransforms.rotation(f.root));
        EvaRigTransforms.rotate(f.bones[ROOT], EvaRigTransforms.rotation(f.root).invert().mul(world));
    }

    /** Moves the whole body (root bone) so that a bone's pivot lands on a world point. */
    private static void place(Frame f, int bone, Vec3 target)
    {
        Vector3f now = point(f, bone);
        Vector3f move = toF(target).sub(now);
        Vector3f local = EvaRigTransforms.rotation(f.root).invert().transform(move).div(f.root.getScale(new Vector3f()).y);
        GeoBone r = f.bones[ROOT];
        r.setPosX(r.getPosX() - local.x * 16); r.setPosY(r.getPosY() + local.y * 16); r.setPosZ(r.getPosZ() + local.z * 16);
    }

    /** Two-bone chain from {@code first} (arm or leg) to a world target; end bone curled by {@code curl}. */
    private static void limb(Frame f, int first, Vec3 target, Vec3 pole, float curl)
    {
        EvaRigTransforms.solveGenericArm(f.bones[first], f.bones[first + 1], f.bones[first + 2], toF(target),
                EvaRigTransforms.rotation(f.root), toF(pole), f.root);
        GeoBone end = f.bones[first + 2];
        end.setRotX(curl); end.setRotY(0); end.setRotZ(0);
    }

    /** Standing legs: knees forward, feet flat on the ground under the hips. */
    private static void legs(Frame f, Vec3 toward, Vec3 side, Vec3 unused)
    {
        for (int leg : new int[] {ARM_L + 3, ARM_R + 3})
        {
            Vector3f hip = point(f, leg);
            double sign = sideOf(f, leg, side);
            Vec3 foot = new Vec3(hip.x, f.ground + ANKLE, hip.z).add(side.scale(sign * 2.5));
            limb(f, leg, foot, toward.add(side.scale(sign * .2)).add(0, .1, 0), 0);
        }
    }

    private static double sideOf(Frame f, int bone, Vec3 side)
    {
        Vector3f p = point(f, bone);
        double s = Math.signum(new Vec3(p.x, p.y, p.z).subtract(f.origin).dot(side));
        return s == 0 ? (bone == ARM_L || bone == ARM_L + 3 ? 1 : -1) : s;
    }

    private static Vector3f point(Frame f, int bone)
    {
        return EvaRigTransforms.point(f.bones[bone], EvaRigTransforms.pivot(f.bones[bone]), f.root);
    }

    /** Solves a phase, then mixes it with the incoming pose by weight. */
    private static void blend(Frame f, float weight, Runnable phase)
    {
        if (weight <= 0) return;
        float[][] before = new float[f.bones.length][];
        for (int i = 0; i < f.bones.length; i++) before[i] = read(f.bones[i]);
        phase.run();
        if (weight >= 1) return;
        for (int i = 0; i < f.bones.length; i++)
        {
            float[] a = before[i], b = read(f.bones[i]);
            var q = new Quaternionf().rotationZYX(a[2], a[1], a[0]).slerp(new Quaternionf().rotationZYX(b[2], b[1], b[0]), weight);
            EvaRigTransforms.rotate(f.bones[i], q);
            f.bones[i].setPosX(Mth.lerp(weight, a[3], b[3]));
            f.bones[i].setPosY(Mth.lerp(weight, a[4], b[4]));
            f.bones[i].setPosZ(Mth.lerp(weight, a[5], b[5]));
        }
    }

    /** 0 before {@code a}, eased to 1 by {@code b}, held, eased back to 0 from {@code c} to {@code d}. */
    private static float ramp(float t, float a, float b, float c, float d)
    {
        return Math.min(smooth((t - a) / Math.max(1e-3F, b - a)), smooth((d - t) / Math.max(1e-3F, d - c)));
    }

    private static Vec3 horizontal(Vec3 v, float yaw)
    {
        Vec3 h = v.multiply(1, 0, 1);
        return h.lengthSqr() < 1e-4 ? Vec3.directionFromRotation(0, yaw + 180) : h.normalize();
    }

    private static float[] read(GeoBone b)
    {
        return new float[] {b.getRotX(), b.getRotY(), b.getRotZ(), b.getPosX(), b.getPosY(), b.getPosZ()};
    }

    private static void zero(GeoBone b)
    {
        b.setRotX(0); b.setRotY(0); b.setRotZ(0); b.setPosX(0); b.setPosY(0); b.setPosZ(0);
    }

    private static float smooth(float t)
    {
        t = Mth.clamp(t, 0, 1);
        return t * t * (3 - 2 * t);
    }

    private static Vector3f toF(Vec3 v) { return new Vector3f((float) v.x, (float) v.y, (float) v.z); }
}
