package com.projectseele.client.cockpit;

import com.projectseele.world.EntryPlugKinematics;
import com.projectseele.world.RigidTransform;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

public final class PilotMountViewTest {
    public static void main(String[] args) {
        for (int heading = -180; heading < 180; heading += 15) {
            var dock = EntryPlugKinematics.dockTransform(new Vec3(30, -1015, 311), heading);
            for (float yaw : new float[]{-65, 0, 65}) for (float pitch : new float[]{-55, 0, 60}) {
                var view = PilotMountView.angles(dock, yaw, pitch, 0, heading);
                if (Math.abs(Mth.wrapDegrees(view.yaw() - heading - yaw)) > .001
                        || Math.abs(view.pitch() - pitch) > .001 || Math.abs(view.roll()) > .001)
                    throw new AssertionError("Docked sight or horizon off at " + heading + "/" + yaw + "/" + pitch);
            }
        }
        // Drive a full socket turn. Both the direction and the horizon must follow the physical cabin.
        Vec3 forward = EntryPlugKinematics.CABIN_VIEW_FORWARD_P;
        Vec3 up = new Vec3(0, -forward.z, forward.y);
        for (int step = 0; step <= 72; step++) {
            float turn = (float) Math.toRadians(step * 5);
            var frame = RigidTransform.of(new Vec3(1, 2, 3), new Quaternionf().rotateY(1.1F).rotateX(-1.05F).rotateZ(turn));
            var view = PilotMountView.angles(frame, 0, 0, 0, 168);
            Vec3 direction = Vec3.directionFromRotation(view.pitch(), view.yaw());
            if (frame.transformVector(forward).distanceToSqr(direction) > 1e-6)
                throw new AssertionError("Cabin front lost at socket turn " + step);
            double yaw = Math.toRadians(view.yaw()), roll = Math.toRadians(view.roll());
            Vec3 left = new Vec3(Math.cos(yaw), 0, Math.sin(yaw));
            Vec3 cameraUp = direction.cross(left).scale(Math.cos(roll)).subtract(left.scale(Math.sin(roll)));
            if (cameraUp.distanceToSqr(frame.transformVector(up)) > 1e-6)
                throw new AssertionError("Cabin horizon lost at socket turn " + step);
            var optics = PilotMountView.angles(frame, 32, -17, 1, 168);
            if (Math.abs(Mth.wrapDegrees(optics.yaw() - 200)) > .001
                    || Math.abs(optics.pitch() + 17) > .001 || Math.abs(optics.roll()) > .001)
                throw new AssertionError("EVA optics lost the pilot's look relative to the cabin front");
        }
        if (PilotMountView.yaw(-179, 179) != 181 || PilotMountView.pitch(-89) != -55)
            throw new AssertionError("Fixed view wrap or vertical limit");
    }
}
