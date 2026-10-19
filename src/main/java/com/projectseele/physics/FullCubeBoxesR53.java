package com.projectseele.physics;

import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/** Preserve native box enumeration without decomposing the canonical cube. */
public final class FullCubeBoxesR53
{
    public static void visit(VoxelShape shape, Shapes.DoubleLineConsumer consumer)
    {
        if(shape == Shapes.block()) consumer.consume(0, 0, 0, 1, 1, 1);
        else shape.forAllBoxes(consumer);
    }

    private FullCubeBoxesR53() {}
}
