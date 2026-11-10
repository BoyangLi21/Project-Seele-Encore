package com.projectseele.world;

import net.minecraft.server.MinecraftServer;

/**
 * Tombstone for the failed SEELE_FULL_REBUILD rescue pipeline.
 *
 * <p>The old class name is intentionally retained because several legacy
 * systems still query it when deciding how to treat that archived save.
 * It is never a clean-world builder: its tick is a permanent no-op and the
 * archive itself is read-only evidence.</p>
 */
public final class FacilityV2RescueDirector
{

    private FacilityV2RescueDirector() {}

    public static void tick(MinecraftServer server)
    {
        // REJECT_FAIL_CLOSED: the failed rescue save is never repaired.
    }

    public static boolean isTargetWorld(MinecraftServer server)
    {
        return FacilityWorldPolicy.isReadOnlyBrokenArchive(server);
    }

}
