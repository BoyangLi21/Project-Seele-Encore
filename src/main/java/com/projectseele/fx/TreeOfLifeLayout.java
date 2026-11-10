package com.projectseele.fx;

import net.minecraft.world.phys.Vec3;

/**
 * The Golden Dawn Tree of Life in the inverted orientation used by the
 * Third-Impact tableau. The server (which parks the nine Mass-Production Evas
 * on the outer Sephirot) and the client light effect share this layout so the
 * vessels, path letters and crucified Unit-01 occupy the same diagram.
 */
public final class TreeOfLifeLayout
{
    // Unit-01 now uses the approved 2x airframe. Keep the ritual bodies at
    // humanly readable spacing in world space, then frame the whole tableau
    // from farther away; compressing the old 62 x 134 field made the central
    // cruciform airframe physically intersect six Mass-Production Evas.
    public static final float COLUMN_X = 48.0F;
    public static final float ROW_Y = 40.0F;
    public static final int TIFERET = 5;

    /**
     * Local plane coordinates (x across, y up), index 0..9 = Keter..Malkuth.
     * Keter is deliberately lowest: EoE manifests an inverted Tree around
     * Unit-01, rather than the ordinary upright instructional diagram.
     */
    public static final float[][] NODES = {
            {0.0F, 0.0F},   // 1 Keter (inverted nadir)
            {-1.0F, 1.0F},  // 2 Chokmah
            {1.0F, 1.0F},   // 3 Binah
            {-1.0F, 2.2F},  // 4 Chesed
            {1.0F, 2.2F},   // 5 Gevurah
            {0.0F, 3.4F},   // 6 Tiferet (centre: Unit-01)
            {-1.0F, 4.6F},  // 7 Netzach
            {1.0F, 4.6F},   // 8 Hod
            {0.0F, 5.8F},   // 9 Yesod
            {0.0F, 6.8F}    // 10 Malkuth (inverted crown)
    };

    /** The canonical 22 paths (verified against the traditional diagram). */
    public static final int[][] PATHS = {
            {0,1},{0,2},{0,5},{1,2},{1,3},{1,5},{2,4},{2,5},
            {3,4},{3,5},{3,6},{4,5},{4,7},{5,6},{5,7},{5,8},
            {6,7},{6,8},{7,8},{6,9},{7,9},{8,9}
    };

    private TreeOfLifeLayout() {}

    public static float localX(int index)
    {
        return NODES[index][0] * COLUMN_X;
    }

    public static float localY(int index)
    {
        return NODES[index][1] * ROW_Y;
    }

    /** World position of a Sephira for a tree rooted at origin, facing yaw. */
    public static Vec3 worldNode(Vec3 origin, float yawRad, int index)
    {
        float x = localX(index);
        float y = localY(index);
        double sin = Math.sin(yawRad);
        double cos = Math.cos(yawRad);
        // The tree plane's local +X maps into the horizontal plane rotated by yaw.
        return new Vec3(origin.x + x * cos, origin.y + y, origin.z - x * sin);
    }

    /** Minecraft yaw which presents an EVA's front on the tree's front side. */
    public static float frontFacingYawDegrees(float yawRad)
    {
        return -(float) Math.toDegrees(yawRad);
    }

}
