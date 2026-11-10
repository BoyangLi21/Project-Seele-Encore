package com.projectseele.entity;

/** Identity policy only. Equipment custody and physical actions remain separate. */
public final class EvaEquipmentPolicyR45
{
    public static final int SWORD = 6;
    public static final int SHIELD = 7;
    public enum FieldInput { CANCEL_LAUNCH, NONE, EVADE, ROLL }

    public static boolean allowed(int weapon, int unit, boolean experimental)
    {
        if (weapon >= 0 && weapon <= 5) return true;
        if (experimental) return false;
        return weapon == SWORD && unit == 2 || weapon == SHIELD && unit == 0;
    }

    public static int normalized(int weapon, int unit, boolean experimental)
    {
        // Unknown IDs must never become N2 through an upper-bound clamp.
        if (weapon < 0) return 0;
        return allowed(weapon, unit, experimental) ? weapon : 1;
    }


    private EvaEquipmentPolicyR45() {}
}
