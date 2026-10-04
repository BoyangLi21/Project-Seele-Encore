package com.projectseele.entity;

/** The head keeps its anatomical socket in every stance. */
public final class EvaCervicalKinematicsR25
{
    public static float modelOffset(EvaUnit01Entity eva,float partial)
    {
        // The old prone rebase moved the hinge five world blocks in both Y
        // and Z while the neck skin retained its original bind. Counter-
        // rotating the head then stretched that skin instead of articulating
        // the neck. Clearance must come from the authored joint rotations.
        return 0;
    }
    private EvaCervicalKinematicsR25() {}
}
