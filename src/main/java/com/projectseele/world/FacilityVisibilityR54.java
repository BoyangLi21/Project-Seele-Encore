package com.projectseele.world;

import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.entity.NervHangarDoorEntity;
import com.projectseele.entity.NervSiloDoorEntity;
import net.minecraft.world.entity.Entity;

/** Wet-bay solids and their moving machinery share one bounded visibility range. */
public final class FacilityVisibilityR54
{
    public static final int DISTANCE = 384;
    public static final int DISTANCE_SQUARED = DISTANCE * DISTANCE;

    public static int trackingDistance(Entity entity, int entityRange, int viewRange)
    {
        int vanillaRange = Math.min(entityRange, viewRange);
        // DH carries the wet-bay liquid blocks beyond the vanilla view range,
        // but cannot carry its entity doors, crane or EVA. Retain those originals.
        return entity instanceof EvaUnit01Entity
                || entity instanceof EntryPlugCarrierEntity
                || entity instanceof NervCarrierPlatformEntity
                || entity instanceof NervHangarDoorEntity
                || entity instanceof NervSiloDoorEntity
                ? Math.max(vanillaRange, DISTANCE) : vanillaRange;
    }

    private FacilityVisibilityR54() { }
}
