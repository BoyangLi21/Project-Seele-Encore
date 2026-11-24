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
        // R65 (feedback 2, item 15): climbing in, the look goes on from where the pilot looked; no turn by itself.
        int boarded = 0;
        for (int step = 0; step < 72; step++) {
            float angle = (float) Math.toRadians(step * 5);
            var transform = RigidTransform.of(new Vec3(4, -9, 2), new Quaternionf().rotateY(angle).rotateX(angle / 3));
            for (float yaw = -60; yaw <= 60; yaw += 20) for (float pitch = -50; pitch <= 55; pitch += 15) {
                var view = PilotMountView.angles(transform, yaw, pitch, 0, 0, 0, 0);
                float[] look = PilotMountView.local(transform, view.yaw(), view.pitch());
                // Within a tenth of a degree (Minecraft's table sine, worse near the vertical); the fault was tens of degrees.
                if (Math.abs(look[0] - yaw) > .1 || Math.abs(look[1] - pitch) > .1)
                    throw new AssertionError("Seat look " + yaw + "/" + pitch + " came back as " + look[0] + "/" + look[1] + " at step " + step);
                var again = PilotMountView.angles(transform, look[0], look[1], 0, 0, 0, 0);
                // Minecraft's sine is a table: angles come back to about 0.006 degrees.
                if (Vec3.directionFromRotation(again.pitch(), again.yaw()).distanceToSqr(Vec3.directionFromRotation(view.pitch(), view.yaw())) > 1e-6)
                    throw new AssertionError("The first picture in the seat turned from where the pilot looked");
                boarded++;
            }
            // Looking past the seat's range, the look is the nearest the seat allows, never straight ahead.
            Vec3 forward = transform.transformVector(EntryPlugKinematics.PILOT_VIEW_FORWARD_P);
            var behind = PilotMountView.angles(transform, 120, 0, 0, 0, 0, 0);
            float[] edge = PilotMountView.local(transform, behind.yaw(), behind.pitch());
            if (Math.abs(edge[0] - 65) > .01) throw new AssertionError("A look past the seat's range was not held at its edge: " + edge[0]);
            if (forward.lengthSqr() < .5) throw new AssertionError("Seat frame lost");
        }
        System.out.println("PilotMountViewTest: " + boarded + " boarding looks kept");
    }
}
