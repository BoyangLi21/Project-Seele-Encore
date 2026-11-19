package com.projectseele.client.render;

import java.util.function.BiFunction;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;

/** Constrains the footprint against vertical block faces on the way to a landing. */
final class EvaFootfallWalls
{
    static Vec3 constrain(Vec3 body, Vec3 foot, double yaw, double toe, double heel, double halfWidth,
                          BiFunction<Vec3, Vec3, BlockHitResult> trace)
    {
        double radians = Math.toRadians(yaw);
        double forwardX = -Math.sin(radians), forwardZ = Math.cos(radians);
        double leftX = forwardZ, leftZ = -forwardX;
        // Ground settling may adjust a chosen landing by up to one more block along the sole.
        double margin = 1;
        double minX = Math.min(forwardX * toe, -forwardX * heel) - Math.abs(leftX) * halfWidth - margin;
        double maxX = Math.max(forwardX * toe, -forwardX * heel) + Math.abs(leftX) * halfWidth + margin;
        double minZ = Math.min(forwardZ * toe, -forwardZ * heel) - Math.abs(leftZ) * halfWidth - margin;
        double maxZ = Math.max(forwardZ * toe, -forwardZ * heel) + Math.abs(leftZ) * halfWidth + margin;
        double x = foot.x, z = foot.z;
        // A centre ray catches a narrow obstruction; the corners catch the other face of a stop
        // where the ankle can clear both walls while the outside edge of a turned foot crosses one.
        for (int probe = 0; probe < 5; probe++)
        {
            double dx = probe == 0 ? 0 : (probe <= 2 ? minX : maxX);
            double dz = probe == 0 ? 0 : (probe % 2 == 1 ? minZ : maxZ);
            BlockHitResult hit = trace.apply(body, foot.add(dx, 0, dz));
            if (hit.getType() != HitResult.Type.BLOCK) continue;
            switch (hit.getDirection())
            {
                case WEST -> x = Math.min(x, hit.getLocation().x - maxX);
                case EAST -> x = Math.max(x, hit.getLocation().x - minX);
                case NORTH -> z = Math.min(z, hit.getLocation().z - maxZ);
                case SOUTH -> z = Math.max(z, hit.getLocation().z - minZ);
                default -> { /* Slopes and the tops of steps are handled by the sole's ground probes. */ }
            }
        }
        return x == foot.x && z == foot.z ? foot : new Vec3(x, foot.y, z);
    }

    private EvaFootfallWalls() {}
}
