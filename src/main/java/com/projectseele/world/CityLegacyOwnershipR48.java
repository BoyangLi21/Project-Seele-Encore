package com.projectseele.world;

import com.projectseele.ProjectSeele;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;

/** A declared rigid-city owner inhibits legacy writes even while the Create backend is disabled. */
public final class CityLegacyOwnershipR48
{
    private static final Map<ServerLevel, Set<String>> REPORTED = new WeakHashMap<>();
    private CityLegacyOwnershipR48() {}

    public static boolean inhibits(ServerLevel level, BlockPos origin, String producer)
    {
        if (!CityRigidTopologyR45.owns(level, origin)) return false;
        String key = origin.asLong() + "/" + producer;
        if (REPORTED.computeIfAbsent(level, ignored -> new HashSet<>()).add(key))
            ProjectSeele.LOGGER.info("Declared rigid city owner inhibits legacy producer: dimension={} origin={} producer={}; original cargo and fixed interfaces retained",
                    level.dimension().location(), origin.toShortString(), producer);
        return true;
    }
}
