package com.projectseele.world;

/** Sector order changes only when a new city journey starts; old saved motion retains its clock. */
public final class CityRegionalMotionR54
{
    public static final String PROFILE = "regional_cross_trapezoid_r54";

    public static int delay(int x, int z)
    {
        if (Math.abs(x) <= 60 || Math.abs(z) <= 60) return 0;
        return 40 + (z < 0 ? (x < 0 ? 0 : 1) : (x >= 0 ? 2 : 3)) * 20;
    }

    private CityRegionalMotionR54() { }
}
