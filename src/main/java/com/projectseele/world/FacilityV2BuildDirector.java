package com.projectseele.world;

import java.util.Map;

import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;

/**
 * Budgeted, restart-safe executor for FacilitySchema v2 zone plans.
 *
 * <p>Only explicit administrator actions may place a zone in
 * {@code GENERATING}. The ordinary server tick merely advances that already
 * authorized plan and never calls an old builder or attempts local repair.</p>
 */
public final class FacilityV2BuildDirector
{
    public static final int MAX_CHANGED_BLOCKS_PER_TICK = 32768;
    public static final long MAX_NANOS_PER_TICK = 20_000_000L;

    private FacilityV2BuildDirector() {}

    public static void start(ServerLevel level, FacilityZonePlan plan)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        if(NervLegacyGenerationGuardR52.evaZone(level,plan.zoneId()))return;
        FacilityWorldPolicy.requireCleanRebuild(
                level.getServer(), "FacilityV2BuildDirector.start");
        FacilityV2SavedData data = FacilityV2SavedData.get(level);
        FacilitySchemaV2.ZoneSpec expected =
                data.manifest().requireZone(plan.zoneId());
        if (!expected.owner().equals(plan.owner()))
        {
            throw new IllegalArgumentException(
                    plan.zoneId() + " plan owner differs from manifest");
        }
        data.beginZone(plan.zoneId(), plan.stage(), plan.buildPlanHash());
        ProjectSeele.LOGGER.info(
                "FacilitySchema v2 queued {} stage={} blocks={} plan={}",
                plan.zoneId(), plan.stage(), plan.owner().volume(),
                plan.buildPlanHash());
    }

    public static void tick(MinecraftServer server)
    {
        if (NervLegacyGenerationGuardR52.retired(server)) return;
        if (!FacilityWorldPolicy.isCleanRebuild(server))
        {
            return;
        }
        ServerLevel level = server.getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null)
        {
            return;
        }
        FacilityV2SavedData data = FacilityV2SavedData.get(level);
        if (!data.commissioned())
        {
            return;
        }
        data.activeZone().ifPresent(active ->
                advance(level, data, active));
    }

    private static void advance(ServerLevel level, FacilityV2SavedData data,
                                Map.Entry<String,
                                        FacilityV2SavedData.ZoneRecord> active)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        String zoneId = active.getKey();
        if(NervLegacyGenerationGuardR52.evaZone(level,zoneId))return;
        FacilityV2SavedData.ZoneRecord record = active.getValue();
        try
        {
            FacilityZonePlan plan = FacilityV2Plans.resolve(
                    data.manifest(), zoneId);
            if (!record.stage().equals(plan.stage())
                    || !record.generatorVersion().equals(
                    FacilitySchemaV2.GENERATOR_VERSION)
                    || !record.buildPlanHash().equals(plan.buildPlanHash()))
            {
                data.failZone(zoneId,
                        "persisted generation receipt does not match plan");
                return;
            }

            long cursor = record.cursor();
            long visited = record.visited();
            long changed = record.changed();
            long volume = plan.owner().volume();
            int changedThisTick = 0;
            long start = System.nanoTime();
            while (cursor < volume
                    && changedThisTick < MAX_CHANGED_BLOCKS_PER_TICK
                    && System.nanoTime() - start < MAX_NANOS_PER_TICK)
            {
                BlockPos position = plan.owner().positionAt(cursor);
                BlockState target = plan.blockAt(position);
                cursor++;
                visited++;
                if (target == null
                        || level.getBlockState(position).equals(target))
                {
                    continue;
                }
                level.setBlock(position, target, Block.UPDATE_CLIENTS);
                changedThisTick++;
                changed++;
            }

            data.updateZoneProgress(zoneId, cursor, visited, changed);
            if (cursor >= volume)
            {
                data.completeZone(zoneId);
                FacilityV2RouteGateDirector.refresh(level, data);
                FacilityV2SpecimenDirector.onZoneCompleted(
                        level, data, zoneId);
                ProjectSeele.LOGGER.info(
                        "FacilitySchema v2 completed {} visited={} changed={}",
                        zoneId, visited, changed);
            }
        }
        catch (RuntimeException exception)
        {
            data.failZone(zoneId, exception.getClass().getSimpleName()
                    + ": " + exception.getMessage());
            ProjectSeele.LOGGER.error(
                    "FacilitySchema v2 generation failed for " + zoneId,
                    exception);
        }
    }
}
