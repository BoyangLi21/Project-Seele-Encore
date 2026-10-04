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

    public static FieldInput contextualC(boolean experimental, boolean mechanical,
            boolean launchSequence, boolean legacyRequest, boolean fieldControllable,
            boolean anotherAction, boolean hasDirection, boolean sprinting)
    {
        if (experimental || mechanical || launchSequence || legacyRequest)
            return FieldInput.CANCEL_LAUNCH;
        if (!fieldControllable || anotherAction) return FieldInput.NONE;
        if (sprinting) return FieldInput.ROLL;
        return hasDirection ? FieldInput.EVADE : FieldInput.NONE;
    }

    private EvaEquipmentPolicyR45() {}
}
