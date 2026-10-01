package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.Vec3;

/** Fixed civil frame for the retained three-line plant, separate from capsule P/S frames. */
public final class HangarStructuralFrameR44
{
    public static final int CRANE_RUNNING_SURFACE_ABOVE_BED = 70;
    public static final int SHARED_ROOF_UNDERSIDE_ABOVE_BED = 88;
    public static final double RAIL_HALF_GAUGE = 4;
    public static final int RUNWAY_BEAM_BASE_ABOVE_BED = 67;
    public static final int RUNWAY_BEAM_HEIGHT = 3;
    public static final int OUTBOARD_HANGER_HALF_WIDTH = 8;
    public static final int[] HANGER_Z_OFFSETS = {-24, -6, 12};

    public static Vec3 trolleyOrigin(BlockPos bed, double worldZ)
    {
        return new Vec3(bed.getX() + .5,
                bed.getY() + CRANE_RUNNING_SURFACE_ABOVE_BED, worldZ);
    }

    public static int roofUndersideY(BlockPos bed)
    {
        return bed.getY() + SHARED_ROOF_UNDERSIDE_ABOVE_BED;
    }

    private HangarStructuralFrameR44() {}
}
