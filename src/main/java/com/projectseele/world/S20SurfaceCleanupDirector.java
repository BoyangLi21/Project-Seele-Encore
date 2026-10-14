package com.projectseele.world;

import java.util.ArrayList;
import java.util.List;

import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;

/**
 * Bounded one-time cleanup for superseded Tokyo-3 surface geometry in S20.
 *
 * <p>The first S20 world inherited the two northern rows and north outer ward
 * from the former city origin at z=80. Clearing a broad cuboid would destroy
 * natural terrain and the authoritative city, so this migration removes only
 * the exact deterministic tower/pylon footprints. It also resolves the two
 * known current-city lot conflicts before replaying local skyscraper assets.</p>
 */
public final class S20SurfaceCleanupDirector
{
    private static final BlockPos LEGACY_ORIGIN = new BlockPos(30, 80, 80);
    private static final BlockPos CURRENT_ORIGIN =
            IntegratedNervMapBuilder.TOKYO3_ORIGIN;
    private static final int[] LOT_CENTRES =
            {-160, -120, -80, -40, 0, 40, 80, 120, 160};
    private static final int[] OUTER_CENTRES =
            {-200, -160, -120, -80, -40, 0, 40, 80, 120, 160};
    private static final List<Job> JOBS = jobs();
    private static final BlockPos MARKER_BASE =
            new BlockPos(152, -448, 244);
    private static final int PHASE_INTERVAL_TICKS = 2;
    private static boolean completeLogged;

    private S20SurfaceCleanupDirector() {}

    public static void tick(MinecraftServer server)
    {
        if(NervLegacyGenerationGuardR52.retired(server))return;
        if (!FacilityWorldPolicy.isS20Rebuild(server)
                || server.getTickCount() % PHASE_INTERVAL_TICKS != 0)
        {
            return;
        }
        ServerLevel level = server.getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null)
        {
            return;
        }
        int phase = firstMissing(level);
        if (phase < 0)
        {
            if (!completeLogged)
            {
                completeLogged = true;
                ProjectSeele.LOGGER.info(
                        "S20 Tokyo-3 bounded cleanup complete: jobs={} "
                                + "legacyOrigin={} currentCityPreserved=true",
                        JOBS.size(), LEGACY_ORIGIN);
            }
            return;
        }

        Job job = JOBS.get(phase);
        level.getChunkAt(job.chunkAnchor());
        job.run(level);
        level.setBlock(marker(phase),
                Blocks.STRUCTURE_VOID.defaultBlockState(),
                Block.UPDATE_CLIENTS);
        ProjectSeele.LOGGER.info(
                "S20 surface cleanup {}/{}: {}",
                phase + 1, JOBS.size(), job.name());
    }

    public static boolean installed(ServerLevel level)
    {
        return firstMissing(level) < 0;
    }

    private static int firstMissing(ServerLevel level)
    {
        for (int phase = 0; phase < JOBS.size(); phase++)
        {
            if (!level.getBlockState(marker(phase))
                    .is(Blocks.STRUCTURE_VOID))
            {
                return phase;
            }
        }
        return -1;
    }

    private static BlockPos marker(int phase)
    {
        return MARKER_BASE.offset(phase, 0, 0);
    }

    private static List<Job> jobs()
    {
        List<Job> jobs = new ArrayList<>();
        jobs.add(new Job("remove lift-overlap tower (110,260)",
                CURRENT_ORIGIN.offset(80, 0, 40), level ->
        {
            ThirdTokyoSurfaceBuilder.removeArmouredTower(
                    level, CURRENT_ORIGIN, 80, 40, false);
            S20SurfaceTransitDirector.repairSurfacePavilion(level);
        }));
        jobs.add(new Job("remove small tower at (120,100,294)",
                CURRENT_ORIGIN.offset(80, 0, 80), level ->
        {
            ThirdTokyoSurfaceBuilder.removeArmouredTower(
                    level, CURRENT_ORIGIN, 80, 80, false);
            LocalMapAssetLoader.placeTokyo3Skyscrapers(level,
                    CURRENT_ORIGIN, 0);
        }));

        for (int z : new int[] {-160, -120, -80})
        {
            for (int x : LOT_CENTRES)
            {
                int gridX = x;
                int gridZ = z;
                jobs.add(new Job("remove legacy armoured lot "
                        + gridX + "," + gridZ,
                        LEGACY_ORIGIN.offset(gridX, 0, gridZ),
                        level -> ThirdTokyoSurfaceBuilder
                                .removeArmouredTower(level, LEGACY_ORIGIN,
                                        gridX, gridZ, true)));
            }
        }
        for (int x : OUTER_CENTRES)
        {
            int gridX = x;
            jobs.add(new Job("remove legacy north outer ward " + gridX,
                    LEGACY_ORIGIN.offset(gridX, 0, -200),
                    level -> ThirdTokyoSurfaceBuilder
                            .removeOuterWardTower(level, LEGACY_ORIGIN,
                                    gridX, -200, true)));
        }
        // The old west perimeter also contributed three freestanding towers
        // north of the new district boundary. They are separate from the
        // north row above, so enumerate them explicitly rather than clearing
        // an unsafe rectangular strip.
        for (int z : new int[] {-160, -120, -80})
        {
            int gridZ = z;
            jobs.add(new Job("remove legacy west outer ward " + gridZ,
                    LEGACY_ORIGIN.offset(-200, 0, gridZ),
                    level -> ThirdTokyoSurfaceBuilder
                            .removeOuterWardTower(level, LEGACY_ORIGIN,
                                    -200, gridZ, true)));
        }
        for (int x : new int[] {-180, 180})
        {
            int gridX = x;
            jobs.add(new Job("remove legacy north pylon " + gridX,
                    LEGACY_ORIGIN.offset(gridX, 0, -160),
                    level -> ThirdTokyoSurfaceBuilder.removePowerPylon(
                            level, LEGACY_ORIGIN, gridX, -160, true)));
        }
        return List.copyOf(jobs);
    }

    private record Job(String name, BlockPos chunkAnchor, Action action)
    {
        void run(ServerLevel level)
        {
            this.action.run(level);
        }
    }

    @FunctionalInterface
    private interface Action
    {
        void run(ServerLevel level);
    }
}
