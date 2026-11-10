package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.Vec3;

/** Fixed civil frame for the retained three-line plant, separate from capsule P/S frames. */
public final class HangarStructuralFrameR44
{
    public static final int CRANE_RUNNING_SURFACE_ABOVE_BED = 70;

    public static Vec3 trolleyOrigin(BlockPos bed, double worldZ)
    {
        return new Vec3(bed.getX() + .5,
                bed.getY() + CRANE_RUNNING_SURFACE_ABOVE_BED, worldZ);
    }


    private HangarStructuralFrameR44() {}
}
