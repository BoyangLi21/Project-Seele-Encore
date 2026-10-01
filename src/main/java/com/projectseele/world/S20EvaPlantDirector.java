package com.projectseele.world;

import java.util.List;

import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;

/**
 * One-time staged construction of the compact S20 EVA plant.
 *
 * <p>S20 starts from the approved static GeoFront reference, but the old cage
 * voids were only a prototype. This director replaces only the three retained
 * mechanical lines, one bounded phase at a time. It never invokes any S19,
 * Facility-v2 or legacy whole-map writer.</p>
 */
public final class S20EvaPlantDirector
{
    private static final BlockPos ORIGIN =
            IntegratedNervMapBuilder.GEOFRONT_ORIGIN;
    private static final BlockPos MARKER_BASE =
            new BlockPos(116, -446, 181);
    private static final int PHASE_INTERVAL_TICKS = 10;
    // Phases 11-16 were coordinate-driven field repairs. They converted
    // player observation coordinates into broad edit boxes and damaged
    // neighbouring authored geometry. Map correction is now preview-only;
    // this automatic builder stops at the last pre-repair phase.
    private static final int PHASES = 11;
    private static boolean completeLogged;

    private S20EvaPlantDirector() {}

    public static void tick(MinecraftServer server)
    {
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
        if (!FacilityWorldPolicy.unmigratedS20CivilGenerationAllowed(level))
        {
            return;
        }
        int phase = firstMissingPhase(level);
        if (phase < 0)
        {
            if (!completeLogged)
            {
                completeLogged = true;
                ProjectSeele.LOGGER.info(
                        "S20 compact EVA plant ready: cages=3 "
                                + "gallery=1 carrierLines=3 oldWholeMapWriters=0");
            }
            return;
        }

        BlockPos load = switch (phase)
        {
            case 0, 1, 2 -> EvaHangarBuilder.hangarBed(ORIGIN, phase);
            case 3 -> ORIGIN.offset(0, 49, -136);
            case 4, 5, 6 ->
                    IntegratedNervMapBuilder.lowerLiftBed(phase - 4);
            case 7 -> ORIGIN.offset(0, EvaHangarBuilder.GALLERY_Y,
                    EvaHangarBuilder.GALLERY_Z);
            case 8, 10 ->
                    IntegratedNervMapBuilder.lowerLiftBed(1);
            case 9 -> IntegratedNervMapBuilder.lowerLiftBed(1).below(2);
            default -> throw new IllegalStateException(
                    "Unknown S20 EVA plant phase " + phase);
        };
        level.getChunkAt(load);
        switch (phase)
        {
            case 0, 1, 2 ->
                    EvaHangarBuilder.buildS20Cage(level, ORIGIN, phase);
            case 3 ->
                    EvaHangarBuilder.buildS20ObservationGallery(level, ORIGIN);
            case 4, 5, 6 ->
                    EvaHangarBuilder.buildS20TransportLine(
                            level, ORIGIN, phase - 4);
            case 7 ->
                    EvaHangarBuilder.repairS20BoardingRoutes(level, ORIGIN);
            case 8 ->
                    EvaHangarBuilder.buildS20LaunchControlSpine(level, ORIGIN);
            case 9 ->
                    EvaHangarBuilder.buildS20LaunchWellFoundations(level);
            case 10 ->
                    IntegratedNervMapBuilder
                            .restoreS20LowerLaunchShells(level);
            default -> throw new IllegalStateException(
                    "Unknown S20 EVA plant phase " + phase);
        }
        level.setBlock(marker(phase),
                Blocks.STRUCTURE_VOID.defaultBlockState(),
                Block.UPDATE_CLIENTS);
        ProjectSeele.LOGGER.info(
                "S20 compact EVA plant phase {}/{} installed: {}",
                phase + 1, PHASES, phaseName(phase));
    }

    public static boolean installed(ServerLevel level)
    {
        return firstMissingPhase(level) < 0;
    }

    private static int firstMissingPhase(ServerLevel level)
    {
        for (int phase = 0; phase < PHASES; phase++)
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
        return MARKER_BASE.offset(0, 0, phase);
    }

    private static String phaseName(int phase)
    {
        return List.of(
                "EVA-00 WET CAGE",
                "EVA-01 WET CAGE",
                "EVA-02 WET CAGE",
                "OBSERVATION AND BOARDING GALLERY",
                "EVA-00 CARRIER LINE",
                "EVA-01 CARRIER LINE",
                "EVA-02 CARRIER LINE",
                "BOARDING PRESSURE-DOOR REVISION",
                "THREE-WELL LAUNCH CONTROL SPINE",
                "THREE-WELL STRUCTURAL FOUNDATIONS",
                "THREE-WELL LOWER PRESSURE SHELLS").get(phase);
    }
}
