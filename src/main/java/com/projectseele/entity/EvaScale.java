package com.projectseele.entity;

/**
 * One authoritative world-scale contract for the three playable Evangelions.
 *
 * <p>The reviewed Tiger meshes were originally shipped at a 2.5 render scale
 * and a 30-block standing height. Infrastructure and interaction sockets must
 * use the same multiplier as the renderer; otherwise a larger-looking EVA
 * keeps the old collision box, muzzle, cockpit and launch shaft.
 */
public final class EvaScale
{
    public static final float LEGACY_RENDER_SCALE = 2.5F;
    /** User-approved final world scale: twice the original reviewed rig. */
    public static final float WORLD_MULTIPLIER = 2.0F;
    public static final float RENDER_SCALE =
            LEGACY_RENDER_SCALE * WORLD_MULTIPLIER;

    public static final float NORMAL_WIDTH = 8.5F * WORLD_MULTIPLIER;
    public static final float NORMAL_HEIGHT = 30.0F * WORLD_MULTIPLIER;
    public static final float CROUCH_HEIGHT = 24.0F * WORLD_MULTIPLIER;
    public static final float PRONE_WIDTH = 24.0F * WORLD_MULTIPLIER;
    public static final float PRONE_HEIGHT = 8.5F * WORLD_MULTIPLIER;

    /**
     * Reviewed upper-back external-power receptacle.  The previous flexible
     * lead ended at legacy lumbar height, which reads as a cable plugged into
     * the pelvis after the airframe was enlarged to its final two-times scale.
     * These two points are now the armour face and the tail of one compact
     * rigid plug; the cable terminates at the plug instead of continuing down
     * the body.
     */
    public static final double UMBILICAL_MOUNT_HEIGHT =
            47.20D;
    public static final double UMBILICAL_SOCKET_HEIGHT =
            47.20D;

    /**
     * Entry plugs do not scale one-for-one with an EVA. The airframe doubled
     * from the reviewed prototype, while the TV-style pressure capsule stays
     * a slim roughly ten-block spinal insert instead of becoming one quarter
     * of the machine's full height.
     */
    public static final float ENTRY_PLUG_RENDER_SCALE = 3.2F;
    public static final float ENTRY_PLUG_WIDTH =
            2.0F;
    public static final float ENTRY_PLUG_LENGTH =
            10.0F;
    public static final float ENTRY_PLUG_INTERACTION_RANGE =
            14.0F;
    public static final float CARRIER_WIDTH = 29.0F;

    private EvaScale() {}

    public static double fromLegacy(double blocks)
    {
        return blocks * WORLD_MULTIPLIER;
    }

    public static float fromLegacy(float blocks)
    {
        return blocks * WORLD_MULTIPLIER;
    }
}
