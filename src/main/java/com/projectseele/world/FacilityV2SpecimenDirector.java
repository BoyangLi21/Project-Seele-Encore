package com.projectseele.world;

import java.util.List;

import com.projectseele.entity.LilithEntity;
import com.projectseele.registry.ModEntities;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** Installs persistent architectural specimens after their owner completes. */
public final class FacilityV2SpecimenDirector
{
    private static final String LILITH_TAG =
            "projectseele.facility_v2_lilith";

    private FacilityV2SpecimenDirector() {}

    public static void onZoneCompleted(ServerLevel level,
                                       FacilityV2SavedData data,
                                       String zoneId)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        if (!FacilityWorldPolicy.isCleanRebuild(level.getServer()))
        {
            return;
        }
        FacilityV2ElevatorDirector.onZoneCompleted(
                level, data.manifest(), zoneId);
        if (!"LILITH_CHAMBER".equals(zoneId))
        {
            return;
        }
        LilithChamberV2Plan plan =
                new LilithChamberV2Plan(data.manifest());
        BlockPos anchor = plan.specimenAnchor();
        level.getChunkAt(anchor);
        AABB bounds = AABB.ofSize(Vec3.atCenterOf(anchor),
                96.0D, 64.0D, 128.0D);
        List<LilithEntity> specimens = level.getEntitiesOfClass(
                LilithEntity.class, bounds,
                entity -> entity.getTags().contains(LILITH_TAG));
        LilithEntity specimen;
        boolean created = specimens.isEmpty();
        if (created)
        {
            specimen = ModEntities.LILITH.get().create(level);
            if (specimen == null)
            {
                return;
            }
        }
        else
        {
            specimen = specimens.get(0);
            for (int index = 1; index < specimens.size(); index++)
            {
                specimens.get(index).discard();
            }
        }
        specimen.moveTo(anchor.getX() + 0.5D, anchor.getY(),
                anchor.getZ() + 0.5D, 180.0F, 0.0F);
        specimen.setNoAi(true);
        specimen.setNoGravity(true);
        specimen.setInvulnerable(true);
        specimen.setPersistenceRequired();
        specimen.addTag(LILITH_TAG);
        specimen.setHealth(specimen.getMaxHealth());
        if (created)
        {
            level.addFreshEntity(specimen);
        }
    }
}
