package com.projectseele.client;

import net.minecraft.client.multiplayer.ClientLevel;

/** Eight contiguous service areas switch supplies over just under seven seconds. */
public final class CityLightWavesR65
{
    public static final int DISTRICTS = 8;
    private static final int INTERVAL = 18, FADE = 12;
    private static ClientLevel level;
    private static boolean wanted, restoring;
    private static int age;
    private static final float[] initial = new float[DISTRICTS], values = new float[DISTRICTS];
    private static volatile int darkAreas;

    static boolean contains(int x, int z)
    {
        return x >= -338 && x <= 318 && z >= -28 && z <= 588;
    }

    static int district(int x, int z)
    {
        return Math.max(0, Math.min(7, Math.floorDiv(x + 338 + ((z + 28) >> 1), 118)));
    }

    static int update(ClientLevel current, boolean blackout)
    {
        if (level != current)
        {
            level = current;
            java.util.Arrays.fill(values, 1F);
            java.util.Arrays.fill(initial, 1F);
            wanted = false;
            restoring = false;
            darkAreas = 0;
            age = INTERVAL * DISTRICTS;
        }
        if (current == null) return 0;
        if (blackout != wanted)
        {
            System.arraycopy(values, 0, initial, 0, DISTRICTS);
            restoring = wanted && !blackout;
            wanted = blackout;
            age = 0;
        }
        int mask = 0;
        for (int i = 0; i < DISTRICTS; i++)
        {
            float t = Math.min(1F, Math.max(0F, (age - INTERVAL * i) / (float) FADE));
            t = t * t * (3F - 2F * t);
            values[i] = initial[i] + ((wanted ? 0F : 1F) - initial[i]) * t;
            if (values[i] < .5F) mask |= 1 << i;
        }
        int changed = mask ^ darkAreas;
        darkAreas = mask;
        if (age++ >= (DISTRICTS - 1) * INTERVAL + FADE)
        {
            age = INTERVAL * DISTRICTS;
            restoring = false;
        }
        return changed;
    }

    static void joinDark(ClientLevel current)
    {
        update(current, true);
        java.util.Arrays.fill(initial, 0F);
        java.util.Arrays.fill(values, 0F);
        darkAreas = (1 << DISTRICTS) - 1;
        age = INTERVAL * DISTRICTS;
    }

    static boolean dark(int x, int z) { return (darkAreas & (1 << district(x, z))) != 0; }
    static boolean restoring(ClientLevel current) { return current != null && current == level && restoring; }
    static float[] lightLevels() { return values; }

    private CityLightWavesR65() {}
}
