package com.projectseele.physics;

import com.projectseele.entity.EvaBodyPose;
import java.util.LinkedHashMap;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** A nearly straight, laterally bowed leg must bend forward, not roll sideways. */
public final class KneeSupportR40Test
{
    private static Vector3f point(EvaBodyPose.Sample pose, String bone)
    {
        return pose.matrix(bone).transformPosition(new Vector3f(pose.rig.get(bone).pivot()));
    }

    private static void check(boolean condition, String reason)
    {
        if (!condition) throw new AssertionError(reason);
    }

    public static void main(String[] args)
    {
        float largestReachError = 0;
        float largestHipSwing = 0;
        for (String side : new String[] {"l", "r"})
        for (float yaw : new float[] {0, .8F, -2.2F})
        for (int step = 0; step <= 160; step++)
        {
            float sign = side.equals("l") ? 1 : -1;
            var rig = new LinkedHashMap<String, EvaBodyPose.Bone>();
            rig.put("root", new EvaBodyPose.Bone("root", null, new Vector3f(), new Quaternionf()));
            rig.put("leg_" + side, new EvaBodyPose.Bone("leg_" + side, "root", new Vector3f(0, 10, 0), new Quaternionf()));
            rig.put("shin_" + side, new EvaBodyPose.Bone("shin_" + side, "leg_" + side, new Vector3f(.03F * sign, 4, 0), new Quaternionf()));
            rig.put("foot_" + side, new EvaBodyPose.Bone("foot_" + side, "shin_" + side, new Vector3f(.06F * sign, 0, 0), new Quaternionf()));
            var joint = new Vector3f(.03F * sign, 5, 0);
            rig.put("r30_knee_socket_" + side, new EvaBodyPose.Bone("r30_knee_socket_" + side, "leg_" + side, joint, new Quaternionf()));
            var pose = new EvaBodyPose.Sample(rig);
            var heading = new Quaternionf().rotationY(yaw);
            pose.rotations.put("root", heading);
            var target = heading.transform(new Vector3f(.06F * sign, step / 40F, 0));
            AnatomicalLimbConstraints.reachFoot(pose, null, side, target, heading);
            float error = point(pose, "foot_" + side).distance(target);
            largestReachError = Math.max(largestReachError, error);
            check(error < .003F, "Foot missed reachable support: " + error);
            var hipAxis = pose.matrix("leg_" + side).transformDirection(new Vector3f(1, 0, 0));
            float swing = hipAxis.angle(heading.transform(new Vector3f(1, 0, 0)));
            largestHipSwing = Math.max(largestHipSwing, swing);
            check(swing < .025F, "Sagittal compression introduced lateral hip roll: " + swing);
            var kneeFromUpper = pose.matrix("leg_" + side).transformPosition(new Vector3f(joint));
            var kneeFromLower = pose.matrix("shin_" + side).transformPosition(new Vector3f(joint));
            check(kneeFromUpper.distance(kneeFromLower) < .00001F, "Knee disconnected at the measured hinge");
            var footRotation = pose.matrix("foot_" + side).getUnnormalizedRotation(new Quaternionf()).normalize();
            check(Math.abs(heading.dot(footRotation)) > .99999F, "Support changed foot orientation");
            if (step > 12)
            {
                var localKnee = new Quaternionf(heading).invert().transform(kneeFromUpper);
                check(localKnee.z < -.2F, "Knee failed to bend forward");
            }
        }
        System.out.println("966 mirrored/yawed leg compressions PASS; max support error="
                + largestReachError + ", max lateral hip swing=" + largestHipSwing);
    }

    private KneeSupportR40Test() {}
}
