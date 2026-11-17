package com.projectseele.client.cockpit;

/**
 * R64: the arithmetic of the positron cannon's sight, kept apart from the game so that it can be checked by itself
 * (CannonSightMathR64Test).
 * <p>
 * The sight shows three things that are each true: where the barrel points (the point its bore's ray reaches, put on
 * the picture where that point is seen from the pilot's eye), how far the charge has come (a ring that closes on the
 * barrel's mark), and where the target's core is and whether the bore's ray passes through it. The shot is on when
 * all three have come together: the barrel has stopped moving, the charge is full, the ray is through the core.
 */
public final class CannonSightMathR64
{
    /** The barrel counts as settled within this angle of where it is being sent (degrees). */
    public static final double SETTLED = .30;
    /** The visor opens the picture to this share of the plain field of view, and the full charge to this. */
    public static final float FIELD_DOWN = .35F, FIELD_CHARGED = .16F;

    private CannonSightMathR64() {}

    /**
     * Where a direction from the eye falls on the picture: x to the right and y downwards, both in half picture
     * heights from its middle. Null behind the eye.
     *
     * @param field the picture's vertical field of view, in degrees
     */
    public static double[] onPicture(double dx, double dy, double dz, double[] forward, double[] up, double[] right, double field)
    {
        double ahead = dx * forward[0] + dy * forward[1] + dz * forward[2];
        if (ahead <= 1e-6) return null;
        double scale = 1 / Math.tan(Math.toRadians(field) / 2);
        double x = (dx * right[0] + dy * right[1] + dz * right[2]) / ahead * scale;
        double y = -(dx * up[0] + dy * up[1] + dz * up[2]) / ahead * scale;
        return new double[]{x, y};
    }

    /** The angle between two directions, in degrees. */
    public static double apart(double ax, double ay, double az, double bx, double by, double bz)
    {
        double a = Math.sqrt(ax * ax + ay * ay + az * az), b = Math.sqrt(bx * bx + by * by + bz * bz);
        if (a < 1e-9 || b < 1e-9) return 180;
        double cos = (ax * bx + ay * by + az * bz) / (a * b);
        return Math.toDegrees(Math.acos(Math.max(-1, Math.min(1, cos))));
    }

    /** How far a ray passes from a point: the ray from (ox, oy, oz) along the unit direction (dx, dy, dz). */
    public static double missBy(double ox, double oy, double oz, double dx, double dy, double dz, double px, double py, double pz)
    {
        double rx = px - ox, ry = py - oy, rz = pz - oz;
        double along = Math.max(0, rx * dx + ry * dy + rz * dz);
        double cx = rx - dx * along, cy = ry - dy * along, cz = rz - dz * along;
        return Math.sqrt(cx * cx + cy * cy + cz * cz);
    }

    /** The field of view's share with the visor so far down (0..1) and the charge so far up (0..1). */
    public static float field(float down, float charge)
    {
        float lowered = FIELD_DOWN + (FIELD_CHARGED - FIELD_DOWN) * clamp(charge);
        return 1 + (lowered - 1) * smooth(clamp(down));
    }

    /**
     * The shot is on. With no core in play (a target dummy, a building) the third condition is that the bore's ray
     * reaches something at all.
     *
     * @param barrelOff how far the barrel still is from where it is being sent, in degrees
     */
    public static boolean on(double barrelOff, float charge, boolean coreInPlay, boolean coreOpen, boolean rayThroughCore, boolean rayReaches)
    {
        return barrelOff <= SETTLED && charge >= 1 && (coreInPlay ? coreOpen && rayThroughCore : rayReaches);
    }

    /** How near the three are to coming together, 0..1: the least of the three, for the tone that quickens. */
    public static float closing(double barrelOff, float charge, boolean coreInPlay, double coreMiss, double coreRadius, boolean rayReaches)
    {
        float barrel = clamp((float) (1 - (barrelOff - SETTLED) / 6));
        float core = coreInPlay ? clamp((float) (1 - (coreMiss - coreRadius) / (coreRadius * 4))) : rayReaches ? 1 : 0;
        return Math.min(barrel, Math.min(clamp(charge), core));
    }

    private static float clamp(float value) { return Math.max(0, Math.min(1, value)); }

    private static float smooth(float value) { return value * value * (3 - 2 * value); }
}
