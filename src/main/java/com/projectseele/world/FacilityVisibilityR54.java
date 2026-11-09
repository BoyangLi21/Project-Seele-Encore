package com.projectseele.world;

import com.projectseele.entity.Angel;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.MassProductionEvaEntity;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.entity.NervHangarDoorEntity;
import com.projectseele.entity.NervSiloDoorEntity;
import net.minecraft.world.entity.Entity;

/** Wet-bay solids and their moving machinery share one bounded visibility range. */
public final class FacilityVisibilityR54
{
    public static final int DISTANCE = 384;
    public static final int DISTANCE_SQUARED = DISTANCE * DISTANCE;
    public static final int GIANT_DISTANCE = 1536;

    /** Sixty-block bodies stand far above the terrain LODs, so they outlive the chunk view. */
    public static boolean giant(Entity entity)
    {
        return entity instanceof EvaUnit01Entity || entity instanceof Angel || entity instanceof MassProductionEvaEntity;
    }

    public static int trackingDistance(Entity entity, int entityRange, int viewRange)
    {
        int vanillaRange = Math.min(entityRange, viewRange);
        if (giant(entity)) return Math.max(vanillaRange, GIANT_DISTANCE);
        // DH carries the wet-bay liquid blocks beyond the vanilla view range,
        // but cannot carry its entity doors, crane or EVA. Retain those originals.
        return entity instanceof EntryPlugCarrierEntity
                || entity instanceof NervCarrierPlatformEntity
                || entity instanceof NervHangarDoorEntity
                || entity instanceof NervSiloDoorEntity
                ? Math.max(vanillaRange, DISTANCE) : vanillaRange;
    }

    private FacilityVisibilityR54() { }
}
