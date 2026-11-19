package com.projectseele.client.render;

import java.util.List;
import java.util.function.BiFunction;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.Vec3;

public final class EvaFootfallWallsTest
{
    private static final AABB SIDE = new AABB(101, -60, -165, 124, 20, -128);
    private static final AABB FRONT = new AABB(48, -60, -132, 192, 20, -100);
    private static final Vec3 BODY = new Vec3(92.5, -44.93, -140.5);
    private static final double TOE = 5.51, HEEL = 5.28, WIDTH = 4.74;

    private static BiFunction<Vec3, Vec3, BlockHitResult> blocks(AABB... boxes)
    {
        return (from, to) -> {
            BlockHitResult hit = AABB.clip(List.of(boxes), from, to, BlockPos.ZERO);
            return hit == null ? BlockHitResult.miss(to, Direction.UP, BlockPos.ZERO) : hit;
        };
    }

    private static void close(double actual, double expected)
    {
        if (Math.abs(actual - expected) > 1e-6) throw new AssertionError(actual + " != " + expected);
    }

    public static void main(String[] args)
    {
        // The fixed tour's L-shaped wall: the ankle alone is inside the playable space on both axes.
        Vec3 landing = new Vec3(97.9, BODY.y, -135.4);
        Vec3 clear = EvaFootfallWalls.constrain(BODY, landing, 0, TOE, HEEL, WIDTH, blocks(SIDE, FRONT));
        close(clear.x + WIDTH, 100);
        close(clear.z + TOE, -133);
        // With only the side wall, the stride along it is untouched.
        Vec3 side = EvaFootfallWalls.constrain(BODY, landing, 0, TOE, HEEL, WIDTH, blocks(SIDE));
        close(side.x, clear.x);
        close(side.z, landing.z);
        // Captured at tour tick 386 in wall-stop-closed-after, when the drawn left toe was past x=101.
        Vec3 planted = new Vec3(97.27127059557901, BODY.y, -141.0012964236607);
        double yaw = -8.998919486999512;
        Vec3 corrected = EvaFootfallWalls.constrain(BODY, planted, yaw, TOE, HEEL, WIDTH, blocks(SIDE, FRONT));
        double leftExtent = -Math.sin(Math.toRadians(yaw)) * TOE + Math.cos(Math.toRadians(yaw)) * WIDTH;
        close(corrected.x + leftExtent, 100);
        close(corrected.z, planted.z);
        // A turned foot needs the projection of both its length and width. This short step is under the hip.
        Vec3 shortStep = new Vec3(96.5, BODY.y, BODY.z);
        Vec3 turned = EvaFootfallWalls.constrain(BODY, shortStep, -45, TOE, HEEL, WIDTH, blocks(SIDE));
        close(turned.x + (TOE + WIDTH) / Math.sqrt(2), 100);
        // The other wall normals use the heel and the opposite edge.
        Vec3 opposite = EvaFootfallWalls.constrain(Vec3.ZERO, new Vec3(-7, 0, -8), 0, TOE, HEEL, WIDTH,
                blocks(new AABB(-40,-10,-40,-10,10,40),new AABB(-40,-10,-40,40,10,-10)));
        close(opposite.x - WIDTH, -9);
        close(opposite.z - HEEL, -9);
        // A low step is below the knee rays. Its supporting height belongs to the terrain solver.
        Vec3 step = EvaFootfallWalls.constrain(BODY, landing, 0, TOE, HEEL, WIDTH,
                blocks(new AABB(88,-60,-144,110,-55,-125)));
        if (!step.equals(landing)) throw new AssertionError("step changed horizontal landing");
        // Ascending rays may miss and descending rays may see a tread from above.
        Vec3 tread = EvaFootfallWalls.constrain(new Vec3(0, 10, 0), new Vec3(4, 4, 0), 30, TOE, HEEL, WIDTH,
                blocks(new AABB(-40, -20, -40, 40, 6, 40)));
        close(tread.x, 4);
        close(tread.z, 0);
    }
}
