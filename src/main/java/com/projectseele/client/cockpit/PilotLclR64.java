package com.projectseele.client.cockpit;

import com.projectseele.config.SeeleConfig;
import com.projectseele.entity.EntryPlugCarrierEntity;
import net.minecraft.util.Mth;

/**
 * R64: the LCL in the plug, as the pilot sees it.
 * <p>
 * The plug fills from the floor while the cabin sequence says so (the capsule's own LCL stage outside the Unit, the
 * first part of the Unit's activation when it is boarded directly); the surface climbs past the knees and the yokes,
 * closes over the eye, and the view is in the liquid. Then the liquid is charged and clears: over a few seconds the
 * colour falls to a trace and the bubbles thin out to one now and then. Leaving the seat, or the capsule being
 * drawn or thrown out, lets it run out from the top down.
 * <p>
 * Nothing here is sent or saved: it is drawn from what the server already tells every client.
 */
public final class PilotLclR64
{
    /** The plug's floor and roof against the pilot's eye (blocks). */
    public static final float FLOOR = -1.10F, ROOF = .78F;
    /** Seconds: the quickest the plug fills, how long it takes to run out, how long the liquid takes to clear. */
    private static final float FILL_LEAST = 1.6F, DRAIN = 1.4F, CLEAR = 3.2F;
    /** How strongly the liquid colours the view while it is fresh, and once it has cleared. */
    private static final float FRESH = .58F, SETTLED = .075F;
    /** How far cleared the liquid still counts while it runs out (0 fresh, 1 settled). */
    private static final float DRAINING = .45F;

    private static float fill, cleared, sinceFull;
    private static boolean seated, known;

    private PilotLclR64() {}

    public static boolean on()
    {
        return PilotCockpitR64.ON && SeeleConfig.COCKPIT_LCL.get();
    }

    /**
     * One frame.
     *
     * @param plug     the capsule the player sits in, or null
     * @param driving  the player pilots a Unit (in its seat, or in a capsule locked into it)
     * @param progress the cabin sequence, 0..1 (the one the insertion overlay shows), or -1 where none runs
     */
    public static void frame(EntryPlugCarrierEntity plug, boolean driving, float progress, float seconds)
    {
        if (!on()) { fill = 0; cleared = 0; seated = false; known = false; return; }
        float dt = Mth.clamp(seconds, 0, .1F);
        boolean inSeat = plug != null || driving;
        float wanted;
        if (!inSeat) wanted = 0;
        else if (progress >= 0) wanted = Mth.clamp((progress - .06F) / .37F, 0, 1);
        else if (driving) wanted = 1;
        else
        {
            // In the capsule with no sequence running: dry while it waits open, sealed or recovered; full in between.
            int cabin = plug.getCabinStage();
            wanted = cabin == EntryPlugCarrierEntity.CABIN_SYNCHRONIZING || cabin == EntryPlugCarrierEntity.CABIN_ONLINE ? 1 : 0;
            // Thrown clear or being drawn out with the pilot aboard: the capsule lets its LCL go.
            int stage = plug.getInsertionStage();
            if (stage == EntryPlugCarrierEntity.STAGE_FIELD_EJECTING || stage == EntryPlugCarrierEntity.STAGE_FIELD_LANDED
                    || stage == EntryPlugCarrierEntity.STAGE_EJECTING) wanted = 0;
        }
        // Found already in the seat with nothing running (a world joined in the Unit, a test boarding): no show.
        if (!known || inSeat && !seated && (progress < 0 || progress > .5F) && wanted >= 1 && fill <= 0)
        {
            fill = wanted; cleared = wanted >= 1 ? 1 : 0; sinceFull = CLEAR;
        }
        known = true; seated = inSeat;
        float before = fill;
        if (wanted > fill) fill = Math.min(wanted, fill + dt / FILL_LEAST);
        else if (wanted < fill) fill = Math.max(wanted, fill - dt / DRAIN);
        // Coming in, the liquid is fresh. Running out, it is seen again as the liquid it is: the charge that
        // cleared it goes with the connection, and a trace of colour falling past the eye would not read as anything.
        if (fill > before && before < 1) cleared = 0;
        if (fill < before && cleared > DRAINING) cleared = Math.max(DRAINING, cleared - dt / .3F);
        if (fill >= 1)
        {
            sinceFull += dt;
            cleared = Math.min(1, cleared + dt / CLEAR);
        }
        else sinceFull = 0;
    }

    /** How full the plug is, 0..1. */
    public static float fill() { return fill; }

    /** The surface against the eye (blocks). */
    public static float level()
    {
        // The floor to the chin goes evenly; the last of it, over the face, a little quicker, as a held breath does.
        float eased = fill < .6F ? fill : .6F + (fill - .6F) * (1 + (fill - .6F) * .9F) / 1.36F;
        return Mth.lerp(Mth.clamp(eased, 0, 1), FLOOR, ROOF);
    }

    /** How much the liquid shows: on its surface and in the view under it. */
    public static float strength()
    {
        if (fill <= 0) return 0;
        float scale = (float) (double) SeeleConfig.COCKPIT_LCL_TINT.get();
        float ease = cleared * cleared * (3 - 2 * cleared);
        return Mth.lerp(ease, FRESH, SETTLED * scale);
    }

    /** How much of the view is in the liquid: 0 with the surface under the eye, 1 with it over. */
    public static float under()
    {
        return Mth.clamp((level() + .05F) / .12F, 0, 1);
    }

    /** Bubbles, 0..1 of the most: a rush while it fills, then fewer, then one now and then. */
    public static float bubbles()
    {
        if (fill <= 0) return 0;
        if (fill < 1) return .55F + .45F * fill;
        return Mth.lerp(Mth.clamp(sinceFull / (CLEAR * 1.3F), 0, 1), 1F, .07F);
    }

    /** True while the plug is filling or running out (the display says so). */
    public static boolean moving() { return fill > 0 && fill < 1; }
    public static boolean clearing() { return fill >= 1 && cleared < 1; }
}
