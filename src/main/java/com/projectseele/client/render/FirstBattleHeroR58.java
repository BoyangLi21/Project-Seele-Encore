package com.projectseele.client.render;

import com.projectseele.entity.EvaScale;
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
 * Unit-01 in the first-battle finale. The authored clip keeps the body's path
 * and timing, but its limb angles bent elbows and knees backwards and rolled
 * the wrists and ankles; every frame the arms and legs are re-solved to the
 * clip's own hand and foot positions with elbows out and down, knees forward,
 * wrists straight and feet flat when they are near the ground. The ground
 * and pound is replaced: both fists locked together, raised over the head
 * with the back arched, and driven down into Sachiel's core six times.
 */
final class FirstBattleHeroR58
{
    /** Clip seconds of each blow; the third, fifth and sixth carry the clip's damage events. */
    static final float[] BLOWS = {12.75F, 13.35F, 14.15F, 14.75F, 15.35F, 16.05F};
    static final float POUND_IN = 12.05F, POUND_OUT = 16.75F;
    private static final float WIND = .4F, STRIKE = .11F, HOLD = .1F;

    private FirstBattleHeroR58() {}

    static final float GROUNDED_IN = 5.6F, GROUNDED_OUT = 12.2F;
    private static float standingRootY, standingAnkle = 3;

    /** Unit-01's forearms (left, right), published for Sachiel's claws (one frame behind at most). */
    private static final Vec3[] forearms = new Vec3[2];
    private static float forearmsAt = -1;

    static Vec3[] forearms(float time)
    {
        return forearms[0] != null && forearms[1] != null && Math.abs(time - forearmsAt) < .25F ? forearms.clone() : null;
    }

    /** Where the fists land: the chest of the pinned Sachiel, in front of the kneeling unit. */
    static Vec3 core(FirstBattleSignals.Spec spec, float time)
    {
        return FirstBattleClip.poundCore(spec, time);
    }

    /** {@code root}: the renderer's own model-to-world matrix for this frame. */
    static void apply(Entity eva, BakedGeoModel model, FirstBattleSignals.Spec spec, float time, float partial, Matrix4f root)
    {
        Vector3f at = root.getTranslation(new Vector3f());
        Vec3 origin = new Vec3(at.x, at.y, at.z);
        float yaw = FirstBattleClip.yaw(spec, true, time);
        Vec3 front = Vec3.directionFromRotation(0, yaw).multiply(1, 0, 1).normalize();
        double ground = spec.origin().y;

        // From the grab to the pin the clip's body leaps up and over Sachiel
        // and flings a leg back: hold the body at standing height and keep
        // both feet on the ground through it.
        GeoBone rootBone = model.getBone("root").orElse(null);
        float grounded = Math.min(smooth((time - GROUNDED_IN) / .4F), smooth((GROUNDED_OUT - time) / .5F));
        if (rootBone != null)
        {
            if (time < 1) standingRootY = rootBone.getPosY();
            else if (grounded > 0 && rootBone.getPosY() > standingRootY)
                rootBone.setPosY(Mth.lerp(grounded, rootBone.getPosY(), standingRootY));
        }
        GeoBone torso = model.getBone("torso_upper").orElse(null);
        GeoBone armL = model.getBone("arm_l").orElse(null), armR = model.getBone("arm_r").orElse(null);
        if (torso == null || armL == null || armR == null) return;
        Vector3f shoulderL = EvaRigTransforms.point(armL, EvaRigTransforms.pivot(armL), root);
        Vector3f shoulderR = EvaRigTransforms.point(armR, EvaRigTransforms.pivot(armR), root);
        Vector3f lateral = new Vector3f(shoulderL).sub(shoulderR);
        lateral.y = 0;
        if (lateral.lengthSquared() < 1e-4F) lateral.set((float) -front.z, 0, (float) front.x);
        lateral.normalize();

        float pound = poundWeight(time);
        Vector3f[] hands = new Vector3f[2];
        for (int s = 0; s < 2; s++)
        {
            GeoBone hand = model.getBone("hand_" + (s == 0 ? "l" : "r")).orElse(null);
            hands[s] = hand == null ? null : EvaRigTransforms.point(hand, EvaRigTransforms.pivot(hand), root);
        }
        // The grab: both hands on Sachiel's shoulders, the trunk driving into
        // it, then twisting to hurl it down.
        Vec3[] held = FirstBattleAngelR58.shoulders(time);
        float grab = Math.min(smooth((time - FirstBattleAngelR58.GRAB_IN) / .5F), smooth((FirstBattleAngelR58.GRAB_END - time) / .4F));
        if (held != null && grab > 0)
        {
            float twist = smooth((time - FirstBattleAngelR58.YANK) / (FirstBattleAngelR58.GRAB_OUT - FirstBattleAngelR58.YANK)) * grab;
            var drive = new Quaternionf().fromAxisAngleRad(lateral.x, lateral.y, lateral.z, .22F * grab)
                    .premul(new Quaternionf().rotationY(-.55F * twist));
            var current = EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(torso)));
            EvaRigTransforms.rotate(torso, EvaRigTransforms.rotation(EvaRigTransforms.parent(torso, root)).invert().mul(drive.mul(current)));
            shoulderL = EvaRigTransforms.point(armL, EvaRigTransforms.pivot(armL), root);
            shoulderR = EvaRigTransforms.point(armR, EvaRigTransforms.pivot(armR), root);
            Vector3f[] own = {shoulderL, shoulderR};
            Vector3f middle = toF(held[0]).add(toF(held[1])).mul(.5F);
            for (int s = 0; s < 2; s++)
                if (hands[s] != null)
                {
                    // Each hand takes the shoulder across from it, a little in toward the neck.
                    Vector3f a = toF(held[0]), b = toF(held[1]);
                    Vector3f mine = a.distanceSquared(own[s]) < b.distanceSquared(own[s]) ? a : b;
                    Vector3f grip = new Vector3f(mine).lerp(middle, .25F).add(0, -2, 0);
                    hands[s] = new Vector3f(hands[s]).lerp(grip, grab);
                }
        }
        if (pound > 0)
        {
            // The trunk arches back for the wind-up and is thrown down with the blow.
            float lean = trunk(time) * pound;
            var turn = new Quaternionf().fromAxisAngleRad(lateral.x, lateral.y, lateral.z, lean);
            var current = EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(torso)));
            EvaRigTransforms.rotate(torso, EvaRigTransforms.rotation(EvaRigTransforms.parent(torso, root)).invert().mul(turn.mul(current)));
            shoulderL = EvaRigTransforms.point(armL, EvaRigTransforms.pivot(armL), root);
            shoulderR = EvaRigTransforms.point(armR, EvaRigTransforms.pivot(armR), root);
            Vector3f fists = fists(spec, time, shoulderL, shoulderR, front);
            for (int s = 0; s < 2; s++)
                if (hands[s] != null)
                {
                    Vector3f locked = new Vector3f(fists).fma(s == 0 ? 1.3F : -1.3F, lateral);
                    hands[s] = new Vector3f(hands[s]).lerp(locked, pound);
                }
        }

        for (int s = 0; s < 2; s++)
        {
            String side = s == 0 ? "l" : "r";
            GeoBone upper = model.getBone("arm_" + side).orElse(null), lower = model.getBone("forearm_" + side).orElse(null);
            GeoBone wrist = model.getBone("wrist_" + side).orElse(null), hand = model.getBone("hand_" + side).orElse(null);
            if (upper == null || lower == null || wrist == null || hand == null || hands[s] == null) continue;
            Vector3f out = new Vector3f(lateral).mul(s == 0 ? 1 : -1);
            Vector3f pole = new Vector3f(out).mul(.8F).add(0, -1, 0).fma(-.3F, toF(front));
            EvaRigTransforms.solveArm(upper, lower, wrist, hand, side, hands[s],
                    EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(hand))), pole, root);
            straighten(wrist, hand, lower, root);
            Vector3f elbow = EvaRigTransforms.point(lower, EvaRigTransforms.pivot(lower), root);
            Vector3f palm = EvaRigTransforms.point(hand, EvaRigTransforms.pivot(hand), root);
            Vector3f mid = elbow.lerp(palm, .55F);
            forearms[s] = new Vec3(mid.x, mid.y, mid.z);
        }
        forearmsAt = time;

        for (int s = 0; s < 2; s++)
        {
            String side = s == 0 ? "l" : "r";
            GeoBone upper = model.getBone("leg_" + side).orElse(null), lower = model.getBone("shin_" + side).orElse(null);
            GeoBone ankle = model.getBone("ankle_" + side).orElse(null), foot = model.getBone("foot_" + side).orElse(null);
            if (upper == null || lower == null || ankle == null || foot == null) continue;
            Vector3f target = EvaRigTransforms.point(foot, EvaRigTransforms.pivot(foot), root);
            Quaternionf rotation = EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(foot)));
            // A foot within reach of the ground stands on it, flat and level with the heading.
            if (time < 1) standingAnkle = (float) Math.max(.5, target.y - ground);
            else if (grounded > 0 && target.y - ground > standingAnkle)
                target.y = (float) Mth.lerp(grounded, target.y, ground + standingAnkle);
            float above = (float) (target.y - ground);
            float plant = 1 - Mth.clamp((above - 1.5F) / 4F, 0, 1);
            if (plant > 0)
            {
                target.y = (float) Math.max(target.y, ground + 1.1F);
                // A foot well behind the hip stands on its toes, heel raised, as in a lunge.
                Vector3f hip = EvaRigTransforms.point(upper, EvaRigTransforms.pivot(upper), root);
                float behind = -new Vector3f(target).sub(hip).dot(toF(front));
                float lift = (float) Math.toRadians(40) * Mth.clamp((behind - 4) / 14F, 0, 1);
                Vector3f toes = toF(front).mul(Mth.cos(lift)).add(0, -Mth.sin(lift), 0);
                Quaternionf flat = new Quaternionf().rotationTo(toF(front), toes).mul(EvaRigTransforms.rotation(root));
                rotation = new Quaternionf(rotation).slerp(flat, plant);
            }
            Vector3f pole = toF(front).fma(s == 0 ? .15F : -.15F, lateral).add(0, .1F, 0);
            EvaRigTransforms.solveLeg(upper, lower, ankle, foot, target, rotation, pole, root);
            limitAnkle(lower, foot, root);
        }
        if (JOINT_LOG && (int) (time * 20) != lastLogged)
        {
            lastLogged = (int) (time * 20);
            StringBuilder row = new StringBuilder(String.format(java.util.Locale.ROOT, "R58 FINALE JOINTS t=%.2f", time));
            for (String side : new String[] {"l", "r"})
            {
                // Knee ahead of the hip-ankle line (+ = forward), elbow off the shoulder-wrist line (out, down).
                var hip = at(model, "leg_" + side, root); var knee = at(model, "shin_" + side, root); var ankle = at(model, "foot_" + side, root);
                var sh = at(model, "arm_" + side, root); var el = at(model, "forearm_" + side, root); var wr = at(model, "hand_" + side, root);
                Vector3f k = new Vector3f(knee).sub(new Vector3f(hip).lerp(ankle, .5F));
                Vector3f e = new Vector3f(el).sub(new Vector3f(sh).lerp(wr, .5F));
                Vector3f out = new Vector3f(lateral).mul(side.equals("l") ? 1 : -1);
                row.append(String.format(java.util.Locale.ROOT, " knee_%s=%.1f elbowOut_%s=%.1f elbowDown_%s=%.1f ankle_%s=%.0f footY_%s=%.1f",
                        side, k.dot(toF(front)), side, e.dot(out), side, -e.y, side, ankleBend(model, side, root), side, ankle.y - ground));
            }
            com.projectseele.ProjectSeele.LOGGER.info(row.toString());
        }
    }

    /** Largest turn of the foot away from square to the shin; the rigid ankle armour parts beyond it. */
    private static final float ANKLE_LIMIT = (float) Math.toRadians(35);

    private static void limitAnkle(GeoBone shin, GeoBone foot, Matrix4f root)
    {
        Quaternionf shinWorld = EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(shin)));
        Quaternionf footWorld = EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(foot)));
        Quaternionf delta = new Quaternionf(shinWorld).invert().mul(footWorld).normalize();
        float angle = 2 * (float) Math.acos(Math.min(1, Math.abs(delta.w)));
        if (angle <= ANKLE_LIMIT) return;
        Quaternionf limited = new Quaternionf().slerp(delta, ANKLE_LIMIT / angle);
        Quaternionf wanted = new Quaternionf(shinWorld).mul(limited);
        EvaRigTransforms.rotate(foot, EvaRigTransforms.rotation(EvaRigTransforms.parent(foot, root)).invert().mul(wanted));
    }

    static float ankleBend(BakedGeoModel model, String side, Matrix4f root)
    {
        GeoBone shin = model.getBone("shin_" + side).orElse(null), foot = model.getBone("foot_" + side).orElse(null);
        if (shin == null || foot == null) return 0;
        Quaternionf a = EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(shin)));
        Quaternionf b = EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(foot)));
        Quaternionf d = a.invert().mul(b).normalize();
        return (float) Math.toDegrees(2 * Math.acos(Math.min(1, Math.abs(d.w))));
    }

    private static final boolean JOINT_LOG = Boolean.getBoolean("projectseele.finaleJointLogR58");
    private static int lastLogged = -1;

    private static Vector3f at(BakedGeoModel model, String bone, Matrix4f root)
    {
        GeoBone b = model.getBone(bone).orElse(null);
        return b == null ? new Vector3f() : EvaRigTransforms.point(b, EvaRigTransforms.pivot(b), root);
    }

    /** 0 outside the ground and pound, eased in and out of the clip's own pose. */
    static float poundWeight(float time)
    {
        float in = Mth.clamp((time - POUND_IN) / .35F, 0, 1), out = Mth.clamp((POUND_OUT - time) / .45F, 0, 1);
        return smooth(Math.min(in, out));
    }

    /** Phase of the blow sequence: -1 wound up, 0 between, +1 driven down. */
    private static float phase(float time)
    {
        for (float blow : BLOWS)
        {
            if (time < blow - WIND - STRIKE) return 0;
            if (time < blow - STRIKE) return -smooth((time - (blow - WIND - STRIKE)) / WIND);
            if (time < blow) { float s = (time - (blow - STRIKE)) / STRIKE; return -1 + 2 * s * s; }
            if (time < blow + HOLD) return 1;
            if (time < blow + HOLD + .1F) return 1 - .45F * smooth((time - blow - HOLD) / .1F);
        }
        return .55F;
    }

    private static float trunk(float time)
    {
        float p = phase(time);
        return p < 0 ? .5F * p : .62F * p;
    }

    private static Vector3f fists(FirstBattleSignals.Spec spec, float time, Vector3f shoulderL, Vector3f shoulderR, Vec3 front)
    {
        Vector3f shoulders = new Vector3f(shoulderL).add(shoulderR).mul(.5F);
        Vector3f high = new Vector3f(shoulders).add(0, 19, 0).fma(-4, toF(front));
        Vector3f low = toF(core(spec, time));
        Vector3f rest = new Vector3f(low).add(0, 7, 0);
        float p = phase(time);
        if (p < 0) return new Vector3f(rest).lerp(high, -p);
        if (p < 1) return new Vector3f(high).lerp(low, p);
        return low;
    }

    /** Wrist in line with the forearm: the hand takes the forearm's own rotation. */
    private static void straighten(GeoBone wrist, GeoBone hand, GeoBone lower, Matrix4f root)
    {
        wrist.setRotX(0); wrist.setRotY(0); wrist.setRotZ(0);
        hand.setRotX(0); hand.setRotY(0); hand.setRotZ(0);
    }

    private static float smooth(float t)
    {
        t = Mth.clamp(t, 0, 1);
        return t * t * (3 - 2 * t);
    }

    private static Vector3f toF(Vec3 v) { return new Vector3f((float) v.x, (float) v.y, (float) v.z); }
}
