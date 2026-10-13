package com.projectseele.world;

import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;

/**
 * Applies narrowly scoped corrections to completed S19 owners.
 *
 * <p>This is a versioned migration path, not a repair loop. Every write is
 * checked against the owning manifest box, receives a durable receipt and is
 * never revisited after success.</p>
 */
public final class FacilityV2ArchitectureDirector
{
    private static final String COMMAND_SPINE =
            "command-spine-enclosure";
    private static final String COMMAND_SUITE =
            "command-suite-office-stairs";
    private static final String MAGI_DESCENT =
            "magi-secure-descent";
    private static final String DOGMA_DESCENT =
            "dogma-upper-descent";
    private static final String EVA_TRANSPORT_CLEARANCE =
            "eva-transport-clearance";

    private static final int COMMAND_SPINE_REVISION = 1;
    private static final int COMMAND_SUITE_REVISION = 1;
    private static final int MAGI_DESCENT_REVISION = 1;
    private static final int DOGMA_DESCENT_REVISION = 1;
    private static final int EVA_TRANSPORT_CLEARANCE_REVISION = 1;

    private FacilityV2ArchitectureDirector() {}

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
        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        if (!facility.commissioned())
        {
            return;
        }
        FacilityV2ArchitectureSavedData data =
                FacilityV2ArchitectureSavedData.get(level);
        applyCommandSpine(level, facility, data);
        applyCommandSuite(level, facility, data);
        applyMagiDescent(level, facility, data);
        applyDogmaDescent(level, facility, data);
        applyEvaTransportClearance(level, facility, data);
    }

    public static boolean ready(ServerLevel level)
    {
        FacilityV2ArchitectureSavedData data =
                FacilityV2ArchitectureSavedData.get(level);
        return !data.needs(COMMAND_SPINE, COMMAND_SPINE_REVISION)
                && !data.needs(COMMAND_SUITE, COMMAND_SUITE_REVISION)
                && !data.needs(MAGI_DESCENT, MAGI_DESCENT_REVISION)
                && !data.needs(DOGMA_DESCENT, DOGMA_DESCENT_REVISION)
                && !data.needs(EVA_TRANSPORT_CLEARANCE,
                EVA_TRANSPORT_CLEARANCE_REVISION);
    }

    private static void applyCommandSpine(
            ServerLevel level, FacilityV2SavedData facility,
            FacilityV2ArchitectureSavedData data)
    {
        if (!complete(facility, "CMD_LIFT_SPINE")
                || !data.needs(COMMAND_SPINE, COMMAND_SPINE_REVISION))
        {
            return;
        }
        FacilitySchemaV2.ResolvedManifest manifest = facility.manifest();
        FacilitySchemaV2.IntBox owner =
                manifest.requireZone("CMD_LIFT_SPINE").owner();
        CommandLiftSpineV2Plan plan =
                new CommandLiftSpineV2Plan(manifest);
        BlockPos centre = manifest.centre();
        int writes = 0;
        for (int minimumZ : new int[] {-3, 21})
        {
            for (int z = minimumZ; z <= minimumZ + 6; z++)
            {
                for (int y = -324; y <= -317; y++)
                {
                    BlockPos position = centre.offset(56, y, z);
                    BlockState target = plan.blockAt(position);
                    if (target == null)
                    {
                        throw new IllegalStateException(
                                "Command spine migration has no target at "
                                        + position);
                    }
                    writes += set(level, owner, position, target);
                }
            }
        }
        data.markApplied(COMMAND_SPINE, COMMAND_SPINE_REVISION);
        log(COMMAND_SPINE, COMMAND_SPINE_REVISION, writes);
    }

    private static void applyCommandSuite(
            ServerLevel level, FacilityV2SavedData facility,
            FacilityV2ArchitectureSavedData data)
    {
        if (!complete(facility, "COMMAND_SUITE")
                || !data.needs(COMMAND_SUITE, COMMAND_SUITE_REVISION))
        {
            return;
        }
        FacilitySchemaV2.ResolvedManifest manifest = facility.manifest();
        FacilitySchemaV2.IntBox owner =
                manifest.requireZone("COMMAND_SUITE").owner();
        BlockPos centre = manifest.centre();
        int writes = 0;
        for (int x = 98; x <= 104; x++)
        {
            for (int z = -3; z <= -2; z++)
            {
                writes += set(level, owner,
                        centre.offset(x, -325, z),
                        Blocks.AIR.defaultBlockState());
            }
        }
        data.markApplied(COMMAND_SUITE, COMMAND_SUITE_REVISION);
        log(COMMAND_SUITE, COMMAND_SUITE_REVISION, writes);
    }

    private static void applyMagiDescent(
            ServerLevel level, FacilityV2SavedData facility,
            FacilityV2ArchitectureSavedData data)
    {
        if (!complete(facility, "MAGI_CORE")
                || !data.needs(MAGI_DESCENT, MAGI_DESCENT_REVISION))
        {
            return;
        }
        FacilitySchemaV2.ResolvedManifest manifest = facility.manifest();
        FacilitySchemaV2.IntBox owner =
                manifest.requireZone("MAGI_CORE").owner();
        MagiCoreV2Plan plan = new MagiCoreV2Plan(manifest);
        BlockPos centre = manifest.centre();
        int writes = 0;

        // Remove the old landing and every old tread/support voxel. This
        // footprint does not overlap a MAGI core.
        for (int x = 20; x <= 36; x++)
        {
            for (int z = 17; z <= 32; z++)
            {
                BlockPos position = centre.offset(x, -370, z);
                BlockState target = plan.blockAt(position);
                writes += set(level, owner, position,
                        target == null
                                ? Blocks.AIR.defaultBlockState() : target);
            }
        }
        for (int step = 0; step < 26; step++)
        {
            int z = 23 - step;
            int treadY = -370 - step;
            for (int x = 24; x <= 32; x++)
            {
                for (int y = -399; y <= treadY; y++)
                {
                    BlockPos position = centre.offset(x, y, z);
                    BlockState target = plan.blockAt(position);
                    writes += set(level, owner, position,
                            target == null
                                    ? Blocks.AIR.defaultBlockState() : target);
                }
            }
        }

        // Install the new landing, straight descent and supported rails.
        for (int x = 20; x <= 36; x++)
        {
            for (int z = 17; z <= 32; z++)
            {
                writes += writePlan(level, owner, plan,
                        centre.offset(x, -371, z));
                writes += writePlan(level, owner, plan,
                        centre.offset(x, -370, z));
            }
        }
        for (int step = 0; step < 25; step++)
        {
            int z = 16 - step;
            int treadY = -372 - step;
            for (int x = 24; x <= 32; x++)
            {
                for (int y = -399; y <= treadY; y++)
                {
                    writes += writePlan(level, owner, plan,
                            centre.offset(x, y, z));
                }
            }
            writes += writePlan(level, owner, plan,
                    centre.offset(24, treadY + 1, z));
            writes += writePlan(level, owner, plan,
                    centre.offset(32, treadY + 1, z));
        }
        data.markApplied(MAGI_DESCENT, MAGI_DESCENT_REVISION);
        log(MAGI_DESCENT, MAGI_DESCENT_REVISION, writes);
    }

    private static void applyDogmaDescent(
            ServerLevel level, FacilityV2SavedData facility,
            FacilityV2ArchitectureSavedData data)
    {
        if (!complete(facility, "DOGMA_SPINE")
                || !data.needs(DOGMA_DESCENT, DOGMA_DESCENT_REVISION))
        {
            return;
        }
        FacilitySchemaV2.ResolvedManifest manifest = facility.manifest();
        FacilitySchemaV2.IntBox owner =
                manifest.requireZone("DOGMA_SPINE").owner();
        BlockPos centre = manifest.centre();
        int writes = 0;
        for (int x = 18; x <= 46; x++)
        {
            writes += set(level, owner,
                    centre.offset(x, -577, 212),
                    Blocks.AIR.defaultBlockState());
        }
        data.markApplied(DOGMA_DESCENT, DOGMA_DESCENT_REVISION);
        log(DOGMA_DESCENT, DOGMA_DESCENT_REVISION, writes);
    }

    /**
     * The reviewed two-times EVA collision box is sixty blocks tall. The
     * first S19 transport lease profiles retained the prototype's 40/48-block
     * upper clearance, so the head and shoulder pylons crossed every civil
     * boundary during rail transfer. Open only the newly added upper part of
     * each commissioned EVA lease plane; the route gate still owns the full
     * expanded aperture and keeps incomplete peers fail-closed.
     */
    private static void applyEvaTransportClearance(
            ServerLevel level, FacilityV2SavedData facility,
            FacilityV2ArchitectureSavedData data)
    {
        if(NervLegacyGenerationGuardR52.retired(level))return;
        if (!data.needs(EVA_TRANSPORT_CLEARANCE,
                EVA_TRANSPORT_CLEARANCE_REVISION))
        {
            return;
        }
        FacilitySchemaV2.ResolvedManifest manifest = facility.manifest();
        for (int variant = 0; variant < 3; variant++)
        {
            String unit = String.format("%02d", variant);
            if (!complete(facility, "UNIT" + unit + "_CAGE")
                    || !complete(facility, "UNIT" + unit + "_CARRIER")
                    || !complete(facility,
                    "UNIT" + unit + "_SWITCHYARD")
                    || !complete(facility, "UNIT" + unit + "_SILO"))
            {
                return;
            }
        }

        int writes = 0;
        BlockState air = Blocks.AIR.defaultBlockState();
        for (FacilitySchemaV2.PortSpec port : manifest.ports())
        {
            if (!port.clearProfile().startsWith("EVA2X_")
                    || port.facing().getAxis()
                    == net.minecraft.core.Direction.Axis.Y)
            {
                continue;
            }
            FacilitySchemaV2.IntBox owner =
                    manifest.requireZone(port.zoneId()).owner();
            FacilitySchemaV2.IntBox aperture = port.aperture();
            int minimumY = Math.max(-424, aperture.minY());
            for (int y = minimumY; y < aperture.maxY(); y++)
            {
                for (int z = aperture.minZ();
                     z < aperture.maxZ(); z++)
                {
                    for (int x = aperture.minX();
                         x < aperture.maxX(); x++)
                    {
                        BlockPos position = new BlockPos(x, y, z);
                        if (contains(owner, position))
                        {
                            writes += set(level, owner, position, air);
                        }
                    }
                }
            }
        }
        data.markApplied(EVA_TRANSPORT_CLEARANCE,
                EVA_TRANSPORT_CLEARANCE_REVISION);
        log(EVA_TRANSPORT_CLEARANCE,
                EVA_TRANSPORT_CLEARANCE_REVISION, writes);
    }

    private static int writePlan(
            ServerLevel level, FacilitySchemaV2.IntBox owner,
            FacilityZonePlan plan, BlockPos position)
    {
        BlockState target = plan.blockAt(position);
        if (target == null)
        {
            return 0;
        }
        return set(level, owner, position, target);
    }

    private static int set(
            ServerLevel level, FacilitySchemaV2.IntBox owner,
            BlockPos position, BlockState target)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return 0;
        if (!contains(owner, position))
        {
            throw new IllegalStateException(
                    "Architecture migration escaped owner at " + position);
        }
        if (level.getBlockState(position).equals(target))
        {
            return 0;
        }
        level.setBlock(position, target, Block.UPDATE_CLIENTS);
        PerformanceCounters.recordWorldBlockWrites(1);
        return 1;
    }

    private static boolean complete(
            FacilityV2SavedData facility, String zoneId)
    {
        return facility.requireZone(zoneId).state()
                == FacilityV2SavedData.ZoneState.COMPLETE;
    }

    private static boolean contains(
            FacilitySchemaV2.IntBox box, BlockPos position)
    {
        return position.getX() >= box.minX()
                && position.getX() < box.maxX()
                && position.getY() >= box.minY()
                && position.getY() < box.maxY()
                && position.getZ() >= box.minZ()
                && position.getZ() < box.maxZ();
    }

    private static void log(String id, int revision, int writes)
    {
        ProjectSeele.LOGGER.info(
                "Facility v2 architecture {} revision {} installed: writes={}",
                id, revision, writes);
    }
}
