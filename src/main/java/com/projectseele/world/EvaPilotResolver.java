package com.projectseele.world;

import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import org.jetbrains.annotations.Nullable;

/**
 * One ownership boundary for direct legacy riders and the persistent
 * EVA -> entry-plug -> pilot chain.
 */
public final class EvaPilotResolver
{
    private EvaPilotResolver() {}

    @Nullable
    public static EvaUnit01Entity controlTarget(Entity pilot)
    {
        Entity root = pilot.getRootVehicle();
        if (root instanceof EvaUnit01Entity eva)
        {
            return eva;
        }
        if (pilot.getVehicle() instanceof EvaUnit01Entity eva)
        {
            return eva;
        }
        if (pilot.getVehicle() instanceof EntryPlugCarrierEntity plug)
        {
            return plug.getLinkedEva();
        }
        return null;
    }

    /** Seat visibility follows physical insertion, not the capsule's assigned host. */
    public static boolean sealedInAirframe(Entity pilot)
    {
        if (pilot.getVehicle() instanceof EntryPlugCarrierEntity plug)
        {
            return plug.isLockedToEva();
        }
        return pilot.getVehicle() instanceof EvaUnit01Entity;
    }

    @Nullable
    public static LivingEntity pilot(EvaUnit01Entity eva)
    {
        return eva.getPilotEntity();
    }
}
