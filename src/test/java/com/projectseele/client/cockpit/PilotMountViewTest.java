package com.projectseele.client.cockpit;

import com.projectseele.world.EntryPlugKinematics;
import com.projectseele.world.RigidTransform;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

public final class PilotMountViewTest {
    public static void main(String[] args) {
        for (int step = 0; step <= 72; step++) {
            float angle = (float) Math.toRadians(step * 5);
            var transform = RigidTransform.of(new Vec3(1,2,3), new Quaternionf().rotateY(angle).rotateZ(angle / 2));
            var seat = PilotMountView.angles(transform, 0, 0, 0, -53, 42, 168);
            Vec3 expected = transform.transformVector(EntryPlugKinematics.PILOT_VIEW_FORWARD_P);
            if (expected.distanceToSqr(Vec3.directionFromRotation(seat.pitch(),seat.yaw())) > 1e-6)
                throw new AssertionError("Stationary pilot did not rotate with the plug at step " + step);
            Vec3 seatUp = transform.transformVector(EntryPlugKinematics.PILOT_EYE_P.subtract(EntryPlugKinematics.PILOT_SEAT_P).normalize());
            double az = Math.toRadians(seat.yaw()), bank = Math.toRadians(seat.roll());
            Vec3 left = new Vec3(Math.cos(az), 0, Math.sin(az));
            Vec3 cameraUp = expected.cross(left).scale(Math.cos(bank)).subtract(left.scale(Math.sin(bank)));
            if (cameraUp.distanceToSqr(seatUp) > 1e-6) throw new AssertionError("Capsule horizon lost its roll");
            var optics = PilotMountView.angles(transform, 0, 0, 1, -53, 80, 168);
            if (Math.abs(Mth.wrapDegrees(optics.yaw() - 233)) > .001
                    || Math.abs(optics.pitch() - 60) > .001 || Math.abs(optics.roll()) > .001)
                throw new AssertionError("Handoff must end at the fixed EVA's clamped view");
        }
        if (PilotMountView.yaw(-179,179) != 181 || PilotMountView.pitch(-89) != -55)
            throw new AssertionError("Fixed view wrap or vertical limit");
    }
}
