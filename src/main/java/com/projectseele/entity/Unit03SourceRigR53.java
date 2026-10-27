package com.projectseele.entity;

/** Production UN01 uses its source proportions and the retargeted rig4 library. */
public final class Unit03SourceRigR53
{
    public static final String MARKER = "unit03_source_production_r53";

    public static boolean loaded()
    {
        return EvaBodyPose.hasRigBoneR53(4, MARKER);
    }

    public static boolean uses(EvaUnit01Entity eva)
    {
        return eva instanceof EvaPrototypeEntity un && un.getUNSerial() == 1 && loaded();
    }

    public static String displayName(int serial)
    {
        return serial == 1 && loaded() ? "EVA-03" : "EVA-UN-0" + serial;
    }

    public static boolean sharesGroundActions(EvaUnit01Entity eva)
    {
        if (!(eva instanceof EvaPrototypeEntity un)) return true;
        // UN00 has its own measured rig3. Experimental identity must not
        // disable the shared jump, walking strike and locomotion blend.
        return un.getUNSerial() == 0 && EvaBodyPose.rigKey(eva) == 3 || uses(eva);
    }

    private Unit03SourceRigR53() {}
}
