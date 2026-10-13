package com.projectseele.world;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Optional;

import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModBlocks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.LadderBlock;
import net.minecraft.world.level.block.state.BlockState;

/**
 * Builds Tokyo-3 and GeoFront as two vertically separated parts of one map.
 * The three EVA shafts are real continuous block volumes; no portal or
 * dimension boundary exists between their lower and upper stations.
 */
public final class IntegratedNervMapBuilder
{
    public static final int MAP_VERSION = 22;
    /**
     * The 640-block Skyweave sphere is buried below a normal Tokyo-3 surface.
     * The lower NERV floor stays south of the city centre so the three launch
     * terminals remain in the same physical X/Z columns as their surface beds.
     */
    public static final BlockPos GEOFRONT_ORIGIN = new BlockPos(30, -444, 296);
    public static final BlockPos TOKYO3_ORIGIN = new BlockPos(30, 80, 220);
    public static final BlockPos S22_TOKYO3_ORIGIN = new BlockPos(30, 68, 220);
    public static final int[] LIFT_X = {-42, 0, 42};
    /** 31x31 unobstructed core for the doubled EVA and its shoulder pylons. */
    public static final int SHAFT_CLEAR_RADIUS = 15;
    /** One mechanical rail layer plus one pressure wall around the clear core. */
    public static final int SHAFT_OUTER_RADIUS = 17;
    private static final int SHAFT_GUIDE_OFFSET = SHAFT_CLEAR_RADIUS + 1;
    public static final int SURFACE_HEADROOM = 82;

    private static final int LOWER_TERMINAL_Z = -76;
    private static final int LOWER_BED_ABOVE_ORIGIN = 1;
    private static final int SURFACE_BED_BELOW_ORIGIN = 1;
    private static final int LOWER_CARRIER_DOOR_HEIGHT = 68;
    private static final int LOWER_OBSERVATION_HEIGHT = 60;
    private static final int LOWER_INTERFACE_HEIGHT = 72;
    private static final int DORSAL_ACCESS_DECK_ABOVE_ORIGIN = 56;
    private static final int UPDATE_CLIENTS = Block.UPDATE_CLIENTS;
    private static final List<LiftLink> LIFT_LINKS = createLiftLinks(
            TOKYO3_ORIGIN, GEOFRONT_ORIGIN);
    private static final List<LiftLink> S22_LIFT_LINKS =
            createLiftLinks(S22_TOKYO3_ORIGIN,
                    GEOFRONT_ORIGIN.offset(0, -12, 0));
    private static final BlockPos RESCUE_MECHANICAL_MARKER_A =
            GEOFRONT_ORIGIN.offset(100, 2, -100);
    private static final BlockPos RESCUE_MECHANICAL_MARKER_B =
            GEOFRONT_ORIGIN.offset(101, 2, -100);

    private IntegratedNervMapBuilder() {}

    /**
     * Restores only the retained three-line EVA plant.  Unlike {@link #ensure}
     * this method never invokes old GeoFront, Tokyo-3, command-room, Dogma or
     * topology repair passes.
     */
    public static boolean restoreLegacyMechanicalOnly(ServerLevel level)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return false;
        FacilityWorldPolicy.requireLegacyGenerationAllowed(
                level.getServer(), "restoreLegacyMechanicalOnly");
        if (level.getBlockState(RESCUE_MECHANICAL_MARKER_A)
                .is(Blocks.BARRIER)
                && level.getBlockState(RESCUE_MECHANICAL_MARKER_B)
                .is(Blocks.STRUCTURE_VOID)
                && rescueMechanicalReady(level))
        {
            return false;
        }

        /*
         * A marker is only a receipt, not the plant itself.  Earlier rescue
         * builds returned here even after scenery reconciliation had removed
         * a cage control or a lift bed, permanently leaving a "complete"
         * marker in front of a broken sortie line.  The cheap mechanical audit
         * above now has to pass before the receipt can suppress reconstruction.
         */
        EvaHangarBuilder.buildMechanicalOnly(level, GEOFRONT_ORIGIN);
        for (LiftLink link : LIFT_LINKS)
        {
            if (!lowerLiftInterfaceValid(level, link))
            {
                rebuildLowerLiftInterface(level, link);
            }
            if (!shaftIsContinuous(level, link)
                    || !surfaceExitIsClear(level, link))
            {
                buildContinuousShaft(level, link);
                buildSurfaceHead(level, link);
            }
        }
        ensurePowerPylons(level);
        buildControlMarkers(level);
        set(level, RESCUE_MECHANICAL_MARKER_A,
                Blocks.BARRIER.defaultBlockState());
        set(level, RESCUE_MECHANICAL_MARKER_B,
                Blocks.STRUCTURE_VOID.defaultBlockState());
        ProjectSeele.LOGGER.info(
                "NERV rescue restored legacy mechanical-only authority: "
                        + "three wet cages, carriers and launch shafts");
        return true;
    }

    /**
     * Cheap read-only gameplay gate for the retained three-line plant.
     *
     * <p>The full legacy runtime audit also inspects retired command, MAGI,
     * city and landscape revisions.  Those are no longer the authority in the
     * fused rescue save and must never prevent a physically complete EVA line
     * from accepting a command-room release.</p>
     */
    public static boolean rescueMechanicalReady(ServerLevel level)
    {
        if (!level.getBlockState(RESCUE_MECHANICAL_MARKER_A)
                .is(Blocks.BARRIER)
                || !level.getBlockState(RESCUE_MECHANICAL_MARKER_B)
                .is(Blocks.STRUCTURE_VOID)
                || !EvaHangarBuilder.runtimeInfrastructurePresent(
                level, GEOFRONT_ORIGIN))
        {
            return false;
        }
        for (LiftLink link : LIFT_LINKS)
        {
            if (!level.getBlockState(link.lowerBed()).is(Blocks.LODESTONE)
                    || !level.getBlockState(link.surfaceBed())
                    .is(Blocks.LODESTONE))
            {
                return false;
            }
        }
        return true;
    }

    /** Builds the city first, GeoFront second, then cuts the shafts last. */
    public static IntegratedAudit build(ServerLevel level)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return inspect(level);
        FacilityWorldPolicy.requireLegacyGenerationAllowed(
                level.getServer(), "IntegratedNervMapBuilder.build");
        PerformanceCounters.recordBuilderCall();
        requireBuildHeight(level);
        boolean stagedEvaWorld = LocalMapAssetLoader.stagedEvaWorld(level);
        ProjectSeele.LOGGER.info(
                "Local EVA map detection: stagedWorld={} role=native-surface localSkyscraper={}",
                stagedEvaWorld,
                LocalMapAssetLoader.skyscraperAvailable());

        int storedRetractionDepth =
                Tokyo3RetractionDirector.depth(level, TOKYO3_ORIGIN);
        ThirdTokyoSurfaceBuilder.buildDistrict(level, TOKYO3_ORIGIN);
        for (int depth = 1; depth <= storedRetractionDepth; depth++)
        {
            ThirdTokyoSurfaceBuilder.applyRetractionDepth(level, TOKYO3_ORIGIN,
                    depth - 1, depth);
        }
        Tokyo3LandscapeBuilder.build(level, TOKYO3_ORIGIN);
        Tokyo3RetractionDirector.register(level, TOKYO3_ORIGIN);
        int skyscrapers = LocalMapAssetLoader.placeTokyo3Skyscrapers(
                level, TOKYO3_ORIGIN, storedRetractionDepth);
        if (stagedEvaWorld || skyscrapers > 0)
        {
            LocalMapAssetLoader.markImportedTokyo3(level, TOKYO3_ORIGIN);
        }
        ProjectSeele.LOGGER.info(
                "Tokyo-3 surface built at {} with {}/3 private skyscrapers; "
                        + "local world staged={} and native buried GeoFront topology active",
                TOKYO3_ORIGIN, skyscrapers, stagedEvaWorld);

        Tokyo3RecoveryConsole.build(level, TOKYO3_ORIGIN);

        GeoFrontBuilder.build(level, GEOFRONT_ORIGIN, false);
        GeoFrontLandscapeBuilder.build(level, GEOFRONT_ORIGIN);
        EvaHangarBuilder.build(level, GEOFRONT_ORIGIN);
        GeoFrontBuilder.repairCavernLighting(level, GEOFRONT_ORIGIN);
        for (LiftLink link : LIFT_LINKS)
        {
            buildContinuousShaft(level, link);
            buildSurfaceHead(level, link);
        }
        // Launch shafts deliberately cut the carrier portal last. Repaint the
        // bounded human route after that cut; its S-bypass stays outside the
        // audited 15x15 shaft shells.
        NervOperationsCentreBuilder.repairRuntimeAccess(
                level, GEOFRONT_ORIGIN);
        // Facility builders own rooms, but this pass owns every shared doorway.
        // It must be absolutely last or a later annex/shaft repair can turn a
        // valid corridor back into a wall in the same setup operation.
        NervFacilityTopologyBuilder.build(level, GEOFRONT_ORIGIN);
        // The topology wall touches the top rung and quarantine glazing at the
        // Terminal-Dogma threshold. Restore those room-owned cells after the
        // generic corridor pass, without rebuilding the deep cavern.
        TerminalDogmaBuilder.repairRuntimeAccess(level, GEOFRONT_ORIGIN);
        NervOperationsCentreBuilder.linkFacilities(level, GEOFRONT_ORIGIN);
        ensurePowerPylons(level);
        buildControlMarkers(level);
        return inspect(level);
    }

    /** Rebuilds only when the complete physical-map audit fails. */
    public static IntegratedAudit ensure(ServerLevel level)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return inspect(level);
        FacilityWorldPolicy.requireLegacyGenerationAllowed(
                level.getServer(), "IntegratedNervMapBuilder.ensure");
        ensureLowerBayWindows(level);
        ensurePowerPylons(level);

        if (isInstalled(level))
        {
            int storedRetractionDepth =
                    Tokyo3RetractionDirector.depth(level, TOKYO3_ORIGIN);
            ThirdTokyoSurfaceBuilder.ensureDistrictRevision(
                    level, TOKYO3_ORIGIN, storedRetractionDepth);
            GeoFrontBuilder.ensurePyramidRevision(level, GEOFRONT_ORIGIN);
            GeoFrontLandscapeBuilder.ensure(level, GEOFRONT_ORIGIN);
            TerminalDogmaBuilder.ensureRevision(level, GEOFRONT_ORIGIN);
            EvaHangarBuilder.ensure(level, GEOFRONT_ORIGIN);
            repairLowerLiftInterfaces(level);
            repairInterruptedShafts(level);
            repairInterruptedCityRestoration(level);
            repairMissingStreetLevelDistrict(level);
            ThirdTokyoSurfaceBuilder.repairSubstationCores(level, TOKYO3_ORIGIN);
            ThirdTokyoSurfaceBuilder.ensureLaunchControlQuarter(
                    level, TOKYO3_ORIGIN);
            repairMissingTokyo3Landscape(level);
            // Text displays and button labels can enter the entity manager a
            // few ticks after their chunks. Repair those bounded runtime
            // layers before judging the immutable 640-block map, otherwise
            // every login needlessly rewrites Tokyo-3 and the complete sphere.
            NervOperationsCentreBuilder.repairRuntimeAccess(
                    level, GEOFRONT_ORIGIN);
            MagiDeepLabBuilder.repairRuntimeLabels(level, GEOFRONT_ORIGIN);
            TerminalDogmaBuilder.repairRuntimeSpecimen(
                    level, GEOFRONT_ORIGIN);
            // The district repair owns the street grid, so the recovery room
            // and its two pressure corridors have to be repainted afterwards.
            Tokyo3RecoveryConsole.ensure(level, TOKYO3_ORIGIN);
            NervFacilityTopologyBuilder.ensure(level, GEOFRONT_ORIGIN);
            TerminalDogmaBuilder.repairRuntimeAccess(
                    level, GEOFRONT_ORIGIN);
            NervOperationsCentreBuilder.linkFacilities(
                    level, GEOFRONT_ORIGIN);
            Tokyo3RetractionDirector.register(level, TOKYO3_ORIGIN);
        }
        IntegratedAudit audit = inspect(level);
        if (audit.valid())
        {
            ProjectSeele.LOGGER.info(
                    "Integrated NERV map reused without full rebuild");
            return audit;
        }
        ProjectSeele.LOGGER.warn(
                "Integrated NERV map incremental audit failed; rebuilding: {}",
                audit.summary());
        return build(level);
    }

    /**
     * Repairs and checks only the structures which can inhibit a live sortie.
     * The explicit setup/audit commands retain the complete map inspection;
     * command-room buttons must not synchronously load every remote city,
     * forest and cavern landmark before they can release an EVA.
     */
    public static RuntimeAudit prepareRuntime(ServerLevel level)
    {
        FacilityWorldPolicy.requireLegacyGenerationAllowed(
                level.getServer(), "IntegratedNervMapBuilder.prepareRuntime");
        PerformanceCounters.recordRepairCall();
        long startedAt = System.nanoTime();
        boolean installed = isInstalled(level);
        if (!installed)
        {
            return new RuntimeAudit(false, false, false, false,
                    false, false, 0, 0, 0, 0, false, false, 0,
                    elapsedMilliseconds(startedAt));
        }

        boolean lowerBayWindows = lowerBayWindowsPresent(level);
        /*
         * A launch/recovery button is a safety gate, not a world generator.
         * The former implementation synchronously ran every city, pyramid,
         * Dogma, hangar and corridor revision before inspecting the three
         * shafts. That took 5-13 seconds on an installed save and let unrelated
         * builders overwrite one another immediately before a sortie. Explicit
         * setup/repair commands still own mutations; live controls are strictly
         * read-only.
         */
        EvaHangarBuilder.HangarAudit hangars =
                EvaHangarBuilder.inspect(level, GEOFRONT_ORIGIN);
        NervOperationsCentreBuilder.OperationsAudit operations =
                NervOperationsCentreBuilder.inspect(level, GEOFRONT_ORIGIN);
        Tokyo3RecoveryConsole.RecoveryConsoleAudit recoveryConsole =
                Tokyo3RecoveryConsole.inspect(level, TOKYO3_ORIGIN);
        MagiDeepLabBuilder.MagiAudit magi =
                MagiDeepLabBuilder.inspect(level, GEOFRONT_ORIGIN);
        boolean magiStructure = magi.physicalAccess() && magi.shaft()
                && magi.roomShell() && magi.pribnowBox()
                && magi.cores() == 3 && magi.controls() == 3;

        int lowerBeds = 0;
        int surfaceBeds = 0;
        int continuousShafts = 0;
        int clearExits = 0;
        for (LiftLink link : LIFT_LINKS)
        {
            if (level.getBlockState(link.lowerBed()).is(Blocks.LODESTONE))
            {
                lowerBeds++;
            }
            if (level.getBlockState(link.surfaceBed()).is(Blocks.LODESTONE))
            {
                surfaceBeds++;
            }
            if (shaftIsContinuous(level, link))
            {
                continuousShafts++;
            }
            if (surfaceExitIsClear(level, link))
            {
                clearExits++;
            }
        }
        boolean controlMarkers = controlMarkersPresent(level);
        boolean operationsPhysical = operations.runtimePhysicalValid();
        boolean valid = controlMarkers && lowerBayWindows
                && hangars.valid() && recoveryConsole.valid()
                && powerPylonsPresent(level)
                && lowerBeds == LIFT_LINKS.size()
                && surfaceBeds == LIFT_LINKS.size()
                && continuousShafts == LIFT_LINKS.size()
                && clearExits == LIFT_LINKS.size()
                && operationsPhysical && magiStructure;
        RuntimeAudit audit = new RuntimeAudit(valid, true, controlMarkers,
                lowerBayWindows, hangars.valid(), recoveryConsole.valid(),
                lowerBeds, surfaceBeds, continuousShafts, clearExits,
                operationsPhysical, magiStructure, magi.labels(),
                elapsedMilliseconds(startedAt));
        ProjectSeele.LOGGER.info("Integrated NERV runtime gate: {}",
                audit.summary());
        if (!valid)
        {
            ProjectSeele.LOGGER.warn(
                    "Integrated NERV runtime detail: hangars={} operations={} magi={}",
                    hangars.summary(), operations.summary(), magi.summary());
            ProjectSeele.LOGGER.warn(
                    "Run /seele geofront audit for detailed shaft diagnostics; "
                            + "live sortie controls never rebuild the map.");
        }
        return audit;
    }

    /**
     * Audits immutable map topology while an EVA is physically deployed.
     * The wet cage is intentionally non-parked at this point: its bridge is
     * retracted, LCL drained, plug absent and carrier parked at the silo.
     * Final recovery still uses IntegratedAudit.valid() and therefore proves
     * that every hangar fixture was restored.
     */
    public static boolean continuousMapValidDuringSortie(
            ServerLevel level, IntegratedAudit audit)
    {
        GeoFrontBuilder.GeoFrontAudit geo = audit.geoFront();
        GeoFrontLandscapeBuilder.LandscapeAudit geoLandscape =
                audit.geoFrontLandscape();
        ThirdTokyoSurfaceBuilder.DistrictAudit city = audit.tokyo3();
        Tokyo3LandscapeBuilder.LandscapeAudit cityLandscape =
                audit.tokyo3Landscape();
        // A deployed EVA intentionally removes its wet-cage carrier, bridge
        // and LCL and opens the street-level safety deck. Validate the
        // immutable world and continuous route here; exact decorative tower,
        // forest and closed-deck counts are restored/audited after recovery.
        //
        // Do not fold the operations annex, MAGI pedestrian access or
        // Terminal Dogma fit-out into this gate. Those facilities have their
        // own audits and can be repaired independently; none is part of the
        // 31x31 moving envelope. Treating an unfinished corridor or display as
        // a failed sortie hid a physically successful 522-block launch.
        return geo.floor() && geo.skySphere() && geo.lake()
                && geo.naturalLake() && geo.pyramid()
                && geo.legacyInnerPyramidGone() && geo.realSky()
                && geo.cavernLighting() && geo.lifts() == LIFT_LINKS.size()
                && geo.bridge() && geo.observation()
                && geo.vanillaLavaSamples() == 0
                && geoLandscape.shore() && geoLandscape.docks() == 2
                && geoLandscape.pumpHouse() && geoLandscape.lclIntake()
                && geoLandscape.serviceRoad() && geoLandscape.maintenance()
                && geoLandscape.bunkers() == 2
                && geoLandscape.lclLakeSamples() == 4
                && geoLandscape.protectedSites()
                && city.roads() == 8 && city.substations() == 2
                && city.pylons() == 6
                && city.sortieLane() && city.observationDeck()
                && city.foundation()
                && cityLandscape.retainingWall()
                && cityLandscape.underDeck() && cityLandscape.deepGrid()
                && cityLandscape.ridgePoints() == 4
                && cityLandscape.highway() && cityLandscape.westPortal()
                && cityLandscape.eastPortal() && cityLandscape.railway()
                && cityLandscape.station() && cityLandscape.shaftHeadroom()
                && cityLandscape.rescueCentre()
                && audit.deeplyBuried()
                && audit.controlMarkers()
                && powerPylonsPresent(level)
                && audit.recoveryConsole()
                && audit.lowerBeds() == LIFT_LINKS.size()
                && audit.surfaceBeds() == LIFT_LINKS.size()
                && audit.continuousShafts() == LIFT_LINKS.size()
                && audit.clearExits() == LIFT_LINKS.size();
    }

    public static IntegratedAudit inspect(ServerLevel level)
    {
        GeoFrontBuilder.GeoFrontAudit geoFront =
                GeoFrontBuilder.inspect(level, GEOFRONT_ORIGIN);
        int storedRetractionDepth =
                Tokyo3RetractionDirector.depth(level, TOKYO3_ORIGIN);
        ThirdTokyoSurfaceBuilder.DistrictAudit tokyo3 =
                ThirdTokyoSurfaceBuilder.inspect(level, TOKYO3_ORIGIN,
                        storedRetractionDepth);
        Tokyo3LandscapeBuilder.LandscapeAudit tokyo3Landscape =
                Tokyo3LandscapeBuilder.inspect(level, TOKYO3_ORIGIN);
        GeoFrontLandscapeBuilder.LandscapeAudit geoFrontLandscape =
                GeoFrontLandscapeBuilder.inspect(level, GEOFRONT_ORIGIN);
        int lowerBeds = 0;
        int surfaceBeds = 0;
        int continuousShafts = 0;
        int clearExits = 0;
        for (LiftLink link : LIFT_LINKS)
        {
            if (level.getBlockState(link.lowerBed()).is(Blocks.LODESTONE))
            {
                lowerBeds++;
            }
            if (level.getBlockState(link.surfaceBed()).is(Blocks.LODESTONE))
            {
                surfaceBeds++;
            }
            if (shaftIsContinuous(level, link))
            {
                continuousShafts++;
            }
            if (surfaceExitIsClear(level, link))
            {
                clearExits++;
            }
        }
        boolean controlMarkers = controlMarkersPresent(level);
        boolean powerPylons = powerPylonsPresent(level);
        EvaHangarBuilder.HangarAudit hangars =
                EvaHangarBuilder.inspect(level, GEOFRONT_ORIGIN);
        Tokyo3RecoveryConsole.RecoveryConsoleAudit recoveryConsole =
                Tokyo3RecoveryConsole.inspect(level, TOKYO3_ORIGIN);
        int sphereTop = GEOFRONT_ORIGIN.getY()
                + GeoFrontBuilder.CAVERN_TOP_Y;
        int rockCover = TOKYO3_ORIGIN.getY() - sphereTop;
        int sphereBottom = GEOFRONT_ORIGIN.getY()
                + GeoFrontBuilder.CAVERN_BOTTOM_Y;
        int bedrockClearance = sphereBottom - level.getMinBuildHeight();
        boolean deeplyBuried = rockCover >= 80 && bedrockClearance >= 16;
        boolean valid = geoFront.valid() && geoFrontLandscape.valid()
                && tokyo3.valid() && tokyo3Landscape.valid() && controlMarkers
                && powerPylons
                && hangars.valid() && recoveryConsole.valid()
                && deeplyBuried
                && lowerBeds == LIFT_LINKS.size()
                && surfaceBeds == LIFT_LINKS.size()
                && continuousShafts == LIFT_LINKS.size()
                && clearExits == LIFT_LINKS.size();
        return new IntegratedAudit(valid, geoFront, geoFrontLandscape, tokyo3,
                tokyo3Landscape, deeplyBuried, rockCover, bedrockClearance,
                controlMarkers, hangars.valid(), recoveryConsole.valid(),
                lowerBeds, surfaceBeds, continuousShafts, clearExits);
    }

    /**
     * Cheap persistent readiness check for navigation commands. It loads only
     * the two marker chunks and cannot trigger a map rebuild.
     */
    public static boolean isInstalled(ServerLevel level)
    {
        level.getChunkAt(lowerControlMarker());
        level.getChunkAt(legacyLowerControlMarker());
        level.getChunkAt(surfaceControlMarker());
        if (controlMarkersPresent(level))
        {
            return true;
        }
        if (legacyControlMarkersPresent(level))
        {
            buildControlMarkers(level);
            ProjectSeele.LOGGER.info(
                    "Migrated NERV installation receipt away from the EVA-01 carrier rail");
            return true;
        }
        if (surfaceControlMarkerPresent(level) && liftMarkersPresent(level))
        {
            // Old saves can already have lost the lower receipt because it sat
            // directly on EVA-01's carrier rail. The surviving surface receipt
            // plus all six lift endpoints is a sufficiently strict legacy
            // fingerprint to repair receipts without rebuilding the map.
            buildControlMarkers(level);
            ProjectSeele.LOGGER.info(
                    "Repaired missing NERV lower installation receipt from lift endpoints");
            return true;
        }
        if (lowerControlMarkerPresent(level, lowerControlMarker())
                && lowerLiftMarkersPresent(level))
        {
            // The retractable city owns the surface blocks above all three
            // shafts. An interrupted restoration can legitimately erase the
            // upper receipt and surface beds while the buried installation is
            // still intact. The protected lower receipt plus all three lower
            // carrier beds is a strict enough fingerprint to enter the
            // bounded runtime repair, which recreates the upper endpoints.
            ProjectSeele.LOGGER.warn(
                    "Recovering NERV surface receipts from intact lower installation markers");
            return true;
        }
        return false;
    }

    public static BlockPos geoFrontOrigin()
    {
        return GEOFRONT_ORIGIN;
    }

    public static BlockPos geoFrontOrigin(ServerLevel level)
    {
        return S24CoordinateTransform.apply(level.getServer(),
                GEOFRONT_ORIGIN);
    }

    public static BlockPos tokyo3Origin()
    {
        return TOKYO3_ORIGIN;
    }

    /** Runtime surface frame; R28 remains at Y=80 while S22 follows Y=68 terrain. */
    public static BlockPos tokyo3Origin(ServerLevel level)
    {
        return S24CoordinateTransform.apply(level.getServer(), TOKYO3_ORIGIN);
    }

    public static List<LiftLink> liftLinks()
    {
        return LIFT_LINKS;
    }

    public static List<LiftLink> liftLinks(ServerLevel level)
    {
        if (!FacilityWorldPolicy.isS22Coastal(level.getServer()))
        {
            if (RegionalFacilityLayout.migrated(level.getServer()))
                return createLiftLinks(TOKYO3_ORIGIN.offset(0,0,-256), RegionalFacilityLayout.launchOrigin(level));
            return LIFT_LINKS;
        }
        return createLiftLinks(tokyo3Origin(level), geoFrontOrigin(level));
    }

    public static LiftLink lift(int index)
    {
        if (index < 0 || index >= LIFT_LINKS.size())
        {
            throw new IllegalArgumentException("EVA lift index must be 0, 1 or 2");
        }
        return LIFT_LINKS.get(index);
    }

    public static LiftLink lift(ServerLevel level, int index)
    {
        List<LiftLink> links = liftLinks(level);
        if (index < 0 || index >= links.size())
        {
            throw new IllegalArgumentException("EVA lift index must be 0, 1 or 2");
        }
        return links.get(index);
    }

    /** Unit variants 00/01/02 use lift indices 0/1/2 respectively. */
    public static LiftLink liftForUnitVariant(int unitVariant)
    {
        return lift(unitVariant);
    }

    /** Resolves a real station only while its lodestone marker is present. */
    public static Optional<LiftLink> readLiftMarker(ServerLevel level, BlockPos marker)
    {
        if (!level.getBlockState(marker).is(Blocks.LODESTONE))
        {
            return Optional.empty();
        }
        return liftLinks(level).stream().filter(link -> link.lowerBed().equals(marker)
                || link.surfaceBed().equals(marker)).findFirst();
    }

    public static Optional<LiftLink> findLift(BlockPos stationBed)
    {
        return LIFT_LINKS.stream()
                .filter(link -> link.lowerBed().equals(stationBed)
                        || link.surfaceBed().equals(stationBed))
                .findFirst();
    }

    public static boolean isLowerStation(BlockPos stationBed)
    {
        return LIFT_LINKS.stream().anyMatch(link -> link.lowerBed().equals(stationBed));
    }

    public static boolean isSurfaceStation(BlockPos stationBed)
    {
        return LIFT_LINKS.stream().anyMatch(link -> link.surfaceBed().equals(stationBed));
    }

    public static int ascentDistance()
    {
        return lift(0).ascentBlocks();
    }

    public static BlockPos lowerLiftBed(int index)
    {
        return lift(index).lowerBed();
    }

    public static BlockPos lowerLiftBed(BlockPos geoFrontOrigin, int index)
    {
        if (index < 0 || index >= LIFT_X.length)
        {
            throw new IllegalArgumentException(
                    "EVA lift index must be 0, 1 or 2");
        }
        return geoFrontOrigin.offset(LIFT_X[index],
                LOWER_BED_ABOVE_ORIGIN, LOWER_TERMINAL_Z);
    }

    public static BlockPos lowerLiftBed(ServerLevel level, int index)
    {
        return lift(level, index).lowerBed();
    }

    public static BlockPos surfaceLiftBed(int index)
    {
        return lift(index).surfaceBed();
    }

    public static BlockPos surfaceLiftBed(ServerLevel level, int index)
    {
        return lift(level, index).surfaceBed();
    }

    public static boolean isSurfaceStation(ServerLevel level, BlockPos stationBed)
    {
        return liftLinks(level).stream()
                .anyMatch(link -> link.surfaceBed().equals(stationBed));
    }

    public static BlockPos lowerControlMarker()
    {
        // Keep the persistent installation receipt away from Unit-01's moving
        // hangar carrier. The former x=0/z=-104 position lay directly in the
        // central rail bed and was overwritten every time the carrier passed.
        return GEOFRONT_ORIGIN.offset(96, 1, -104);
    }

    private static BlockPos legacyLowerControlMarker()
    {
        return GEOFRONT_ORIGIN.offset(0, 1, -104);
    }

    public static BlockPos surfaceControlMarker()
    {
        return TOKYO3_ORIGIN.offset(0, -2, 16);
    }

    /** Hard exclusion used by every Tokyo-3 terrain and building write path. */
    public static boolean isCityMovementProtected(BlockPos position)
    {
        for (LiftLink link : LIFT_LINKS)
        {
            if (position.getY() >= link.lowerBed().getY()
                    && position.getY() <= link.surfaceBed().getY() + SURFACE_HEADROOM
                    && Math.abs(position.getX() - link.x()) <= SHAFT_OUTER_RADIUS
                    && Math.abs(position.getZ() - link.z()) <= SHAFT_OUTER_RADIUS)
            {
                return true;
            }
        }
        for (BlockPos marker : new BlockPos[] {lowerControlMarker(),
                legacyLowerControlMarker(), surfaceControlMarker()})
        {
            if (position.equals(marker) || position.equals(marker.east())
                    || position.equals(marker.west()))
            {
                return true;
            }
        }
        return false;
    }
    private static List<LiftLink> createLiftLinks(BlockPos surfaceOrigin,
                                                   BlockPos geoFrontOrigin)
    {
        List<LiftLink> links = new ArrayList<>(LIFT_X.length);
        for (int index = 0; index < LIFT_X.length; index++)
        {
            int relativeX = LIFT_X[index];
            int worldX = surfaceOrigin.getX() + relativeX;
            int worldZ = surfaceOrigin.getZ();
            BlockPos lowerBed = geoFrontOrigin.offset(relativeX,
                    LOWER_BED_ABOVE_ORIGIN, LOWER_TERMINAL_Z);
            BlockPos surfaceBed = surfaceOrigin.offset(relativeX,
                    -SURFACE_BED_BELOW_ORIGIN, 0);
            if (lowerBed.getX() != surfaceBed.getX()
                    || lowerBed.getZ() != surfaceBed.getZ()
                    || lowerBed.getX() != worldX
                    || lowerBed.getZ() != worldZ)
            {
                throw new IllegalStateException(
                        "GeoFront and Tokyo-3 lift stations must share one physical X/Z column");
            }
            links.add(new LiftLink(index, worldX, worldZ,
                    lowerBed, surfaceBed));
        }
        return List.copyOf(links);
    }

    private static void buildContinuousShaft(ServerLevel level, LiftLink link)
    {
        BlockState accent = accent(link.index());
        int bottomY = link.lowerBed().getY() + 1;
        int topY = link.surfaceBed().getY();
        for (int y = bottomY; y <= topY; y++)
        {
            int relativeY = y - bottomY;
            for (int x = -SHAFT_OUTER_RADIUS; x <= SHAFT_OUTER_RADIUS; x++)
            {
                for (int z = -SHAFT_OUTER_RADIUS; z <= SHAFT_OUTER_RADIUS; z++)
                {
                    BlockPos position = new BlockPos(
                            link.x() + x, y, link.z() + z);
                    int edge = Math.max(Math.abs(x), Math.abs(z));
                    if (edge <= SHAFT_CLEAR_RADIUS)
                    {
                        clear(level, position);
                    }
                    else if (edge == SHAFT_OUTER_RADIUS)
                    {
                        boolean lowerCarrierDoor =
                                relativeY <= LOWER_CARRIER_DOOR_HEIGHT
                                && z == -SHAFT_OUTER_RADIUS
                                && Math.abs(x) <= SHAFT_CLEAR_RADIUS;
                        boolean lowerObservationWindow =
                                relativeY <= LOWER_OBSERVATION_HEIGHT
                                && z == SHAFT_OUTER_RADIUS
                                && Math.abs(x) <= SHAFT_CLEAR_RADIUS;
                        if (lowerCarrierDoor)
                        {
                            clear(level, position);
                        }
                        else
                        {
                            set(level, position, lowerObservationWindow
                                    ? Blocks.GRAY_STAINED_GLASS.defaultBlockState()
                                    : shaftWall(relativeY, x, z, accent));
                        }
                    }
                    else
                    {
                        clear(level, position);
                    }
                }
            }

            // Guide rails and the inspection ladder live in the one-block
            // mechanical layer between the 31x31 clear core and outer shell.
            // Putting them at +/-SHAFT_CLEAR_RADIUS made the shaft repair
            // immediately fail its own all-air clearance audit.
            for (int x : new int[] {-SHAFT_GUIDE_OFFSET,
                    SHAFT_GUIDE_OFFSET})
            {
                for (int z : new int[] {-SHAFT_GUIDE_OFFSET,
                        SHAFT_GUIDE_OFFSET})
                {
                    set(level, new BlockPos(
                                    link.x() + x, y, link.z() + z),
                            Blocks.POLISHED_BASALT.defaultBlockState());
                }
            }
            set(level, new BlockPos(link.x(), y,
                            link.z() + SHAFT_GUIDE_OFFSET),
                    Blocks.LADDER.defaultBlockState()
                            .setValue(LadderBlock.FACING, Direction.NORTH));
        }

        // Preserve the GeoFront dorsal access opening cut by the lower gantry.
        int accessDeckY = GEOFRONT_ORIGIN.getY()
                + DORSAL_ACCESS_DECK_ABOVE_ORIGIN;
        for (int x = -2; x <= 2; x++)
        {
            for (int y = accessDeckY + 1; y <= accessDeckY + 3; y++)
            {
                clear(level, new BlockPos(link.x() + x, y,
                        link.z() - SHAFT_OUTER_RADIUS));
            }
        }

        // A single physical carrier marker closes the upper station at Y=363.
        set(level, link.surfaceBed(), Blocks.LODESTONE.defaultBlockState());
        for (int y = TOKYO3_ORIGIN.getY();
             y <= TOKYO3_ORIGIN.getY() + SURFACE_HEADROOM; y++)
        {
            for (int x = -SHAFT_CLEAR_RADIUS; x <= SHAFT_CLEAR_RADIUS; x++)
            {
                for (int z = -SHAFT_CLEAR_RADIUS; z <= SHAFT_CLEAR_RADIUS; z++)
                {
                    clear(level, new BlockPos(
                            link.x() + x, y, link.z() + z));
                }
            }
        }
    }

    /**
     * Repairs the bounded hand-off between each wet cage carrier tunnel and
     * its launch shaft. Prototype maps could lose the lodestone carrier bed or
     * retain a tunnel roof across the shaft core, while rebuilding all 524
     * vertical blocks would cause a large synchronous stall.
     */
    private static void repairLowerLiftInterfaces(ServerLevel level)
    {
        int repaired = 0;
        for (LiftLink link : LIFT_LINKS)
        {
            if (lowerLiftInterfaceValid(level, link))
            {
                continue;
            }
            rebuildLowerLiftInterface(level, link);
            repaired++;
        }
        if (repaired > 0)
        {
            ProjectSeele.LOGGER.info(
                    "Repaired {}/{} lower EVA carrier/launch-shaft interfaces",
                    repaired, LIFT_LINKS.size());
        }
    }

    /** Repairs only the three interrupted physical shafts on an installed map. */
    private static void repairInterruptedShafts(ServerLevel level)
    {
        int repaired = 0;
        for (LiftLink link : LIFT_LINKS)
        {
            if (shaftIsContinuous(level, link)
                    && surfaceExitIsClear(level, link))
            {
                continue;
            }
            buildContinuousShaft(level, link);
            buildSurfaceHead(level, link);
            repaired++;
        }
        if (repaired > 0)
        {
            ProjectSeele.LOGGER.info(
                    "Repaired {}/{} interrupted EVA launch shafts without rebuilding the map",
                    repaired, LIFT_LINKS.size());
        }
    }

    private static boolean lowerLiftInterfaceValid(ServerLevel level,
                                                   LiftLink link)
    {
        if (!level.getBlockState(link.lowerBed()).is(Blocks.LODESTONE))
        {
            return false;
        }
        int bottomY = link.lowerBed().getY() + 1;
        for (int y = bottomY; y <= bottomY + LOWER_INTERFACE_HEIGHT; y++)
        {
            if (!shaftLayerIsClear(level, link, y))
            {
                return false;
            }
        }
        return true;
    }

    private static void rebuildLowerLiftInterface(ServerLevel level,
                                                  LiftLink link)
    {
        set(level, link.lowerBed(), Blocks.LODESTONE.defaultBlockState());
        BlockState accent = accent(link.index());
        int bottomY = link.lowerBed().getY() + 1;
        for (int y = bottomY; y <= bottomY + LOWER_INTERFACE_HEIGHT; y++)
        {
            int relativeY = y - bottomY;
            for (int x = -SHAFT_OUTER_RADIUS; x <= SHAFT_OUTER_RADIUS; x++)
            {
                for (int z = -SHAFT_OUTER_RADIUS; z <= SHAFT_OUTER_RADIUS; z++)
                {
                    BlockPos position = new BlockPos(
                            link.x() + x, y, link.z() + z);
                    int edge = Math.max(Math.abs(x), Math.abs(z));
                    if (edge <= SHAFT_CLEAR_RADIUS)
                    {
                        clear(level, position);
                    }
                    else if (edge == SHAFT_OUTER_RADIUS)
                    {
                        boolean carrierDoor =
                                relativeY <= LOWER_CARRIER_DOOR_HEIGHT
                                && z == -SHAFT_OUTER_RADIUS
                                && Math.abs(x) <= SHAFT_CLEAR_RADIUS;
                        boolean observationWindow =
                                relativeY <= LOWER_OBSERVATION_HEIGHT
                                && z == SHAFT_OUTER_RADIUS
                                && Math.abs(x) <= SHAFT_CLEAR_RADIUS;
                        if (carrierDoor)
                        {
                            clear(level, position);
                        }
                        else
                        {
                            set(level, position, observationWindow
                                    ? Blocks.GRAY_STAINED_GLASS.defaultBlockState()
                                    : shaftWall(relativeY, x, z, accent));
                        }
                    }
                    else
                    {
                        clear(level, position);
                    }
                }
            }

            for (int x : new int[] {-SHAFT_GUIDE_OFFSET,
                    SHAFT_GUIDE_OFFSET})
            {
                for (int z : new int[] {-SHAFT_GUIDE_OFFSET,
                        SHAFT_GUIDE_OFFSET})
                {
                    set(level, new BlockPos(
                                    link.x() + x, y, link.z() + z),
                            Blocks.POLISHED_BASALT.defaultBlockState());
                }
            }
            set(level, new BlockPos(link.x(), y,
                            link.z() + SHAFT_GUIDE_OFFSET),
                    Blocks.LADDER.defaultBlockState()
                            .setValue(LadderBlock.FACING, Direction.NORTH));
        }
    }
    private static BlockState shaftWall(int relativeY, int x, int z,
                                        BlockState accent)
    {
        if (relativeY % 32 == 0)
        {
            return accent;
        }
        if (relativeY % 8 == 0 && (x == 0 || z == 0))
        {
            return Blocks.SEA_LANTERN.defaultBlockState();
        }
        if (Math.abs(x) == SHAFT_OUTER_RADIUS
                && Math.abs(z) == SHAFT_OUTER_RADIUS)
        {
            return Blocks.IRON_BLOCK.defaultBlockState();
        }
        return com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
    }

    private static void buildSurfaceHead(ServerLevel level, LiftLink link)
    {
        BlockState accent = accent(link.index());
        int groundY = TOKYO3_ORIGIN.getY();
        // Earlier prototypes surrounded every sortie with four pylons and an
        // overhead frame. Tokyo-3 should release an EVA directly onto an open
        // battle street, so rebuilds actively clear that obsolete enclosure.
        int apronRadius = SHAFT_OUTER_RADIUS + 2;
        for (int x = -apronRadius; x <= apronRadius; x++)
        {
            for (int z = -apronRadius; z <= apronRadius; z++)
            {
                for (int y = 1; y <= 20; y++)
                {
                    clear(level, new BlockPos(
                            link.x() + x, groundY + y, link.z() + z));
                }
            }
        }
        for (int x = -apronRadius; x <= apronRadius; x++)
        {
            for (int z = -apronRadius; z <= apronRadius; z++)
            {
                int edge = Math.max(Math.abs(x), Math.abs(z));
                BlockPos position = new BlockPos(
                        link.x() + x, groundY, link.z() + z);
                if (edge <= SHAFT_CLEAR_RADIUS)
                {
                    clear(level, position);
                }
                else if (edge < SHAFT_OUTER_RADIUS)
                {
                    set(level, position, Math.floorMod(x + z, 4) < 2
                            ? accent : Blocks.BLACK_CONCRETE.defaultBlockState());
                }
                else if (edge == SHAFT_OUTER_RADIUS)
                {
                    set(level, position, Blocks.IRON_BLOCK.defaultBlockState());
                }
                else
                {
                    set(level, position, Blocks.SMOOTH_STONE.defaultBlockState());
                }
            }
        }
    }

    public static BlockPos lowerPowerPylon(int index)
    {
        return lift(index).lowerBed().offset(SHAFT_GUIDE_OFFSET, 1, 0);
    }

    public static BlockPos surfacePowerPylon(int index)
    {
        return lift(index).surfaceBed().offset(SHAFT_OUTER_RADIUS + 2, 2, 0);
    }

    private static BlockPos surfacePowerPylon(ServerLevel level,int index)
    {
        if(java.nio.file.Files.isRegularFile(level.getServer().getWorldPath(
                net.minecraft.world.level.storage.LevelResource.ROOT).resolve("r28_surface_power.json")))
            return new BlockPos(new int[]{-12,30,72}[index],81,3);
        return surfacePowerPylon(index);
    }

    /**
     * S20-only repair for the lower pressure walls removed with the pyramid
     * interior. The north carrier aperture remains open by design; the other
     * three walls, guide layer and observation side are reconstructed from
     * the canonical launch-shaft contract.
     */
    public static void restoreS20LowerLaunchShells(ServerLevel level)
    {
        if(NervLegacyGenerationGuardR52.retired(level))return;
        if (!FacilityWorldPolicy.isS20Rebuild(level.getServer()))
        {
            throw new IllegalStateException(
                    "S20 launch-shell repair rejected outside S20");
        }
        for (LiftLink link : LIFT_LINKS)
        {
            rebuildLowerLiftInterface(level, link);
            BlockState accent = accent(link.index());
            int y = link.lowerBed().getY();
            for (int x = -SHAFT_OUTER_RADIUS;
                 x <= SHAFT_OUTER_RADIUS; x++)
            {
                for (int z = -SHAFT_OUTER_RADIUS;
                     z <= SHAFT_OUTER_RADIUS; z++)
                {
                    if (Math.max(Math.abs(x), Math.abs(z))
                            != SHAFT_OUTER_RADIUS)
                    {
                        continue;
                    }
                    boolean carrierAperture = z == -SHAFT_OUTER_RADIUS
                            && Math.abs(x) <= SHAFT_CLEAR_RADIUS;
                    BlockPos position = new BlockPos(
                            link.x() + x, y, link.z() + z);
                    if (carrierAperture)
                    {
                        clear(level, position);
                    }
                    else
                    {
                        set(level, position,
                                (x == 0 || z == 0) ? accent
                                        : com.projectseele.world.NervMaterials.structuralBlock()
                                                .defaultBlockState());
                    }
                }
            }
        }
        ProjectSeele.LOGGER.info(
                "S20 lower launch pressure shells restored: "
                        + "wells=3 lowerLayers=74 carrierApertures=preserved");
    }

    /**
     * Final bounded safety pass after a room or pedestrian-route repair.
     * Public command-room code may call this, but it cannot rebuild the city or
     * the complete 522-block columns.
     */
    public static void repairLowerSortieInterfaces(ServerLevel level)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        FacilityWorldPolicy.requireLegacyGenerationAllowed(
                level.getServer(),
                "IntegratedNervMapBuilder.repairLowerSortieInterfaces");
        repairLowerLiftInterfaces(level);
    }

    /** Repairs only the requested EVA's lower carrier/shaft hand-off. */
    public static boolean ensureLowerSortieInterface(ServerLevel level, int index)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return false;
        FacilityWorldPolicy.requireLegacyGenerationAllowed(
                level.getServer(),
                "IntegratedNervMapBuilder.ensureLowerSortieInterface");
        LiftLink link = lift(index);
        if (FacilityV2RescueDirector.isTargetWorld(level.getServer()))
        {
            return rescueMechanicalReady(level)
                    && lowerLiftInterfaceValid(level, link);
        }
        if (!lowerLiftInterfaceValid(level, link))
        {
            rebuildLowerLiftInterface(level, link);
            ProjectSeele.LOGGER.info(
                    "Repaired EVA-{} lower sortie interface before command release",
                    String.format(Locale.ROOT, "%02d", index));
        }
        return lowerLiftInterfaceValid(level, link);
    }

    private static void ensurePowerPylons(ServerLevel level)
    {
        for (int index = 0; index < LIFT_LINKS.size(); index++)
        {
            BlockPos legacy = lift(index).lowerBed().offset(
                    SHAFT_CLEAR_RADIUS, 1, 0);
            if (!legacy.equals(lowerPowerPylon(index))
                    && level.getBlockState(legacy)
                    .is(ModBlocks.UMBILICAL_PYLON.get()))
            {
                level.removeBlock(legacy, false);
            }
            set(level, lowerPowerPylon(index),
                    ModBlocks.UMBILICAL_PYLON.get().defaultBlockState());
            set(level, surfacePowerPylon(level,index),
                    ModBlocks.UMBILICAL_PYLON.get().defaultBlockState());
        }
    }

    private static boolean powerPylonsPresent(ServerLevel level)
    {
        for (int index = 0; index < LIFT_LINKS.size(); index++)
        {
            if (!level.getBlockState(lowerPowerPylon(index))
                    .is(ModBlocks.UMBILICAL_PYLON.get())
                    || !level.getBlockState(surfacePowerPylon(level,index))
                    .is(ModBlocks.UMBILICAL_PYLON.get()))
            {
                return false;
            }
        }
        return true;
    }

    private static void buildControlMarkers(ServerLevel level)
    {
        BlockPos lower = lowerControlMarker();
        set(level, lower, Blocks.CHISELED_DEEPSLATE.defaultBlockState());
        set(level, lower.east(), Blocks.ORANGE_CONCRETE.defaultBlockState());
        set(level, lower.west(), Blocks.BLACK_CONCRETE.defaultBlockState());
        BlockPos surface = surfaceControlMarker();
        set(level, surface, Blocks.CHISELED_QUARTZ_BLOCK.defaultBlockState());
        set(level, surface.east(), Blocks.ORANGE_CONCRETE.defaultBlockState());
        set(level, surface.west(), Blocks.BLACK_CONCRETE.defaultBlockState());
    }

    private static boolean controlMarkersPresent(ServerLevel level)
    {
        return lowerControlMarkerPresent(level, lowerControlMarker())
                && surfaceControlMarkerPresent(level);
    }

    private static boolean legacyControlMarkersPresent(ServerLevel level)
    {
        return lowerControlMarkerPresent(level, legacyLowerControlMarker())
                && surfaceControlMarkerPresent(level);
    }

    private static boolean lowerControlMarkerPresent(ServerLevel level,
                                                     BlockPos lower)
    {
        return level.getBlockState(lower).is(Blocks.CHISELED_DEEPSLATE)
                && level.getBlockState(lower.east()).is(Blocks.ORANGE_CONCRETE)
                && level.getBlockState(lower.west()).is(Blocks.BLACK_CONCRETE);
    }

    private static boolean surfaceControlMarkerPresent(ServerLevel level)
    {
        BlockPos surface = surfaceControlMarker();
        return level.getBlockState(surface).is(Blocks.CHISELED_QUARTZ_BLOCK)
                && level.getBlockState(surface.east()).is(Blocks.ORANGE_CONCRETE)
                && level.getBlockState(surface.west()).is(Blocks.BLACK_CONCRETE);
    }

    private static boolean liftMarkersPresent(ServerLevel level)
    {
        for (LiftLink link : LIFT_LINKS)
        {
            level.getChunkAt(link.lowerBed());
            level.getChunkAt(link.surfaceBed());
            if (!level.getBlockState(link.lowerBed()).is(Blocks.LODESTONE)
                    || !level.getBlockState(link.surfaceBed()).is(Blocks.LODESTONE))
            {
                return false;
            }
        }
        return true;
    }

    private static boolean lowerLiftMarkersPresent(ServerLevel level)
    {
        for (LiftLink link : LIFT_LINKS)
        {
            level.getChunkAt(link.lowerBed());
            if (!level.getBlockState(link.lowerBed()).is(Blocks.LODESTONE))
            {
                return false;
            }
        }
        return true;
    }

    private static boolean shaftIsContinuous(ServerLevel level, LiftLink link)
    {
        int bottom = link.lowerBed().getY() + 2;
        int top = link.surfaceBed().getY() - 2;
        for (int y = bottom; y <= top; y++)
        {
            if (!shaftLayerIsClear(level, link, y))
            {
                return false;
            }
        }
        return true;
    }

    private static String shaftFailure(ServerLevel level, LiftLink link)
    {
        int bottom = link.lowerBed().getY() + 2;
        int top = link.surfaceBed().getY() - 2;
        for (int y = bottom; y <= top; y++)
        {
            for (int x = -SHAFT_CLEAR_RADIUS; x <= SHAFT_CLEAR_RADIUS; x++)
            {
                for (int z = -SHAFT_CLEAR_RADIUS; z <= SHAFT_CLEAR_RADIUS; z++)
                {
                    BlockPos position = new BlockPos(
                            link.x() + x, y, link.z() + z);
                    BlockState state = level.getBlockState(position);
                    if (!state.isAir())
                    {
                        return "core obstruction at " + position.toShortString()
                                + " block=" + state.getBlock();
                    }
                }
            }
            if (!shaftLayerIsClear(level, link, y))
            {
                return "pressure-wall contract failed at y=" + y;
            }
        }
        return null;
    }

    private static boolean shaftLayerIsClear(ServerLevel level,
                                             LiftLink link, int y)
    {
        for (int x = -SHAFT_CLEAR_RADIUS; x <= SHAFT_CLEAR_RADIUS; x++)
        {
            for (int z = -SHAFT_CLEAR_RADIUS; z <= SHAFT_CLEAR_RADIUS; z++)
            {
                if (!level.getBlockState(new BlockPos(
                        link.x() + x, y, link.z() + z)).isAir())
                {
                    return false;
                }
            }
        }
        boolean southWall = isShaftWall(level.getBlockState(
                        new BlockPos(link.x(), y,
                                link.z() - SHAFT_OUTER_RADIUS)));
        int accessDeckY = GEOFRONT_ORIGIN.getY()
                + DORSAL_ACCESS_DECK_ABOVE_ORIGIN;
        boolean auditedGantryDoor = y >= accessDeckY + 1
                && y <= accessDeckY + 3
                && level.getBlockState(new BlockPos(
                        link.x(), y, link.z() - SHAFT_OUTER_RADIUS)).isAir();
        int carrierPortalBottom = link.lowerBed().getY() + 1;
        int carrierPortalTop = carrierPortalBottom
                + LOWER_CARRIER_DOOR_HEIGHT;
        boolean auditedCarrierDoor = y >= carrierPortalBottom
                && y <= carrierPortalTop
                && level.getBlockState(new BlockPos(
                        link.x(), y, link.z() - SHAFT_OUTER_RADIUS)).isAir();
        return isShaftWall(level.getBlockState(
                        new BlockPos(link.x() - SHAFT_OUTER_RADIUS,
                                y, link.z())))
                && isShaftWall(level.getBlockState(
                        new BlockPos(link.x() + SHAFT_OUTER_RADIUS,
                                y, link.z())))
                && isShaftWall(level.getBlockState(
                        new BlockPos(link.x(), y,
                                link.z() + SHAFT_OUTER_RADIUS)))
                && (southWall || auditedGantryDoor || auditedCarrierDoor);
    }
    private static boolean surfaceExitIsClear(ServerLevel level, LiftLink link)
    {
        for (int y = TOKYO3_ORIGIN.getY();
             y <= TOKYO3_ORIGIN.getY() + SURFACE_HEADROOM; y++)
        {
            for (int x = -SHAFT_CLEAR_RADIUS; x <= SHAFT_CLEAR_RADIUS; x++)
            {
                for (int z = -SHAFT_CLEAR_RADIUS; z <= SHAFT_CLEAR_RADIUS; z++)
                {
                    if (!level.getBlockState(new BlockPos(
                            link.x() + x, y, link.z() + z)).isAir())
                    {
                        return false;
                    }
                }
            }
        }
        return true;
    }

    private static boolean isShaftWall(BlockState state)
    {
        return state.is(com.projectseele.world.NervMaterials.STRUCTURAL_SHELL)
                || state.is(Blocks.IRON_BLOCK)
                || state.is(Blocks.SEA_LANTERN)
                || state.is(Blocks.GRAY_STAINED_GLASS)
                || state.is(Blocks.ORANGE_CONCRETE)
                || state.is(Blocks.PURPLE_CONCRETE)
                || state.is(Blocks.RED_CONCRETE);
    }

    private static boolean lowerBayWindowsPresent(ServerLevel level)
    {
        for (LiftLink link : LIFT_LINKS)
        {
            int wallZ = link.z() + SHAFT_OUTER_RADIUS;
            int bottom = link.lowerBed().getY() + 2;
            int accessDeckY = GEOFRONT_ORIGIN.getY()
                    + DORSAL_ACCESS_DECK_ABOVE_ORIGIN;
            for (int y : new int[] {bottom, (bottom + accessDeckY) / 2,
                    accessDeckY - 1})
            {
                for (int x : new int[] {-SHAFT_CLEAR_RADIUS,
                        SHAFT_CLEAR_RADIUS})
                {
                    if (!level.getBlockState(new BlockPos(
                            link.x() + x, y, wallZ))
                            .is(Blocks.GRAY_STAINED_GLASS))
                    {
                        return false;
                    }
                }
            }
        }
        return true;
    }

    private static void repairMissingStreetLevelDistrict(ServerLevel level)
    {
        Tokyo3RetractionDirector.Status city = Tokyo3RetractionDirector.status(
                level, TOKYO3_ORIGIN);
        if (city.depth() != 0 || city.targetDepth() != 0)
        {
            return;
        }
        ThirdTokyoSurfaceBuilder.DistrictAudit audit =
                ThirdTokyoSurfaceBuilder.inspect(level, TOKYO3_ORIGIN, 0);
        if (audit.valid())
        {
            return;
        }
        ProjectSeele.LOGGER.warn(
                "Tokyo-3 street-level structures are incomplete despite depth=0; rebuilding once: {}",
                audit.summary());
        ThirdTokyoSurfaceBuilder.buildDistrict(level, TOKYO3_ORIGIN);
        // District reconstruction replaces whole street lots. Repaint the
        // connected highway, railway, station and protected recovery zones in
        // the same repair transaction instead of leaving a visually complete
        // skyline on top of an invalid landscape.
        Tokyo3LandscapeBuilder.build(level, TOKYO3_ORIGIN);
        LocalMapAssetLoader.placeTokyo3Skyscrapers(level, TOKYO3_ORIGIN, 0);
        Tokyo3RecoveryConsole.ensure(level, TOKYO3_ORIGIN);
    }
    private static void repairMissingTokyo3Landscape(ServerLevel level)
    {
        Tokyo3RetractionDirector.Status city = Tokyo3RetractionDirector.status(
                level, TOKYO3_ORIGIN);
        if (city.depth() != 0 || city.targetDepth() != 0)
        {
            return;
        }
        Tokyo3LandscapeBuilder.LandscapeAudit audit =
                Tokyo3LandscapeBuilder.inspect(level, TOKYO3_ORIGIN);
        if (audit.valid())
        {
            return;
        }
        ProjectSeele.LOGGER.warn(
                "Tokyo-3 connected landscape is incomplete; rebuilding bounded surface infrastructure: {}",
                audit.summary());
        Tokyo3LandscapeBuilder.build(level, TOKYO3_ORIGIN);
        LocalMapAssetLoader.placeTokyo3Skyscrapers(level, TOKYO3_ORIGIN, 0);
        Tokyo3RecoveryConsole.ensure(level, TOKYO3_ORIGIN);
    }

    private static void repairInterruptedCityRestoration(ServerLevel level)
    {
        Tokyo3RetractionDirector.Status city = Tokyo3RetractionDirector.status(
                level, TOKYO3_ORIGIN);
        if (city.depth() > 0 && city.targetDepth() == 0)
        {
            ProjectSeele.LOGGER.warn(
                    "Interrupted Tokyo-3 restoration detected at depth={}; resuming bounded physical repair",
                    city.depth());
            Tokyo3RetractionDirector.forceDepth(level, TOKYO3_ORIGIN, false);
        }
    }
    private static long elapsedMilliseconds(long startedAt)
    {
        return (System.nanoTime() - startedAt) / 1_000_000L;
    }

    /** Backfills the lower-bay glazing without rebuilding the imported map. */
    private static void ensureLowerBayWindows(ServerLevel level)
    {
        for (LiftLink link : LIFT_LINKS)
        {
            int wallZ = link.z() + SHAFT_OUTER_RADIUS;
            int bottom = link.lowerBed().getY() + 2;
            int top = bottom + LOWER_OBSERVATION_HEIGHT;
            for (int y = bottom; y <= top; y++)
            {
                for (int x = -SHAFT_CLEAR_RADIUS;
                     x <= SHAFT_CLEAR_RADIUS; x++)
                {
                    // The dorsal access door is on the south carrier wall.
                    // This north face is the sealed observation glazing; an
                    // older repair mirrored the doorway here and made every
                    // shaft fail its pressure-wall contract at Y=-387.
                    set(level, new BlockPos(link.x() + x, y, wallZ),
                            Blocks.GRAY_STAINED_GLASS.defaultBlockState());
                }
            }
        }
    }

    private static BlockState accent(int index)
    {
        return switch (index)
        {
            case 0 -> Blocks.ORANGE_CONCRETE.defaultBlockState();
            case 2 -> Blocks.RED_CONCRETE.defaultBlockState();
            default -> Blocks.PURPLE_CONCRETE.defaultBlockState();
        };
    }

    private static void requireBuildHeight(ServerLevel level)
    {
        int requiredMin = GEOFRONT_ORIGIN.getY()
                + TerminalDogmaBuilder.FACILITY_Y_OFFSET
                + TerminalDogmaBuilder.MIN_RELATIVE_Y;
        int requiredMax = TOKYO3_ORIGIN.getY()
                + Math.max(SURFACE_HEADROOM, 44);
        if (requiredMin < level.getMinBuildHeight()
                || requiredMax >= level.getMaxBuildHeight())
        {
            throw new IllegalStateException(String.format(Locale.ROOT,
                    "Integrated NERV map requires Y=%d..%d but dimension provides %d..%d",
                    requiredMin, requiredMax, level.getMinBuildHeight(),
                    level.getMaxBuildHeight() - 1));
        }
    }

    private static void clear(ServerLevel level, BlockPos position)
    {
        if (!level.getBlockState(position).isAir())
        {
            set(level, position, Blocks.AIR.defaultBlockState());
        }
    }

    private static void set(ServerLevel level, BlockPos position, BlockState state)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        if (!level.getBlockState(position).equals(state))
        {
            level.setBlock(position, state, UPDATE_CLIENTS);
            PerformanceCounters.recordWorldBlockWrites(1);
        }
    }

    public record LiftLink(int index, int x, int z, BlockPos lowerBed,
                           BlockPos surfaceBed)
    {
        public int ascentBlocks()
        {
            return this.surfaceBed.getY() - this.lowerBed.getY();
        }

        public BlockPos surfaceExit()
        {
            return this.surfaceBed.above();
        }
    }

    public record RuntimeAudit(boolean valid, boolean installed,
                               boolean controlMarkers,
                               boolean lowerBayWindows, boolean hangars,
                               boolean recoveryConsole, int lowerBeds,
                               int surfaceBeds, int continuousShafts,
                               int clearExits, boolean operations,
                               boolean magi, int magiLabels,
                               long elapsedMilliseconds)
    {
        /**
         * Safety-critical gate for moving a doubled EVA. Cosmetic displays,
         * MAGI maintenance access and support-annex pedestrian links remain
         * visible in {@link #valid()} but cannot strand an otherwise safe
         * airframe in its cage.
         */
        public boolean launchReady()
        {
            return this.installed && this.controlMarkers
                    && this.lowerBayWindows && this.hangars
                    && this.recoveryConsole
                    && this.lowerBeds == LIFT_LINKS.size()
                    && this.surfaceBeds == LIFT_LINKS.size()
                    && this.continuousShafts == LIFT_LINKS.size()
                    && this.clearExits == LIFT_LINKS.size();
        }

        public String summary()
        {
            return String.format(Locale.ROOT,
                    "valid=%s launchReady=%s installed=%s controlMarkers=%s windows=%s "
                            + "hangars=%s recoveryConsole=%s "
                            + "lowerBeds=%d/3 surfaceBeds=%d/3 "
                            + "continuousShafts=%d/3 clearExits=%d/3 "
                            + "operations=%s magi=%s magiLabels=%d/3 "
                            + "elapsed=%dms",
                    this.valid, this.launchReady(), this.installed,
                    this.controlMarkers,
                    this.lowerBayWindows, this.hangars,
                    this.recoveryConsole, this.lowerBeds, this.surfaceBeds,
                    this.continuousShafts, this.clearExits, this.operations,
                    this.magi, this.magiLabels, this.elapsedMilliseconds);
        }
    }

    public record IntegratedAudit(boolean valid,
                                  GeoFrontBuilder.GeoFrontAudit geoFront,
                                  GeoFrontLandscapeBuilder.LandscapeAudit geoFrontLandscape,
                                   ThirdTokyoSurfaceBuilder.DistrictAudit tokyo3,
                                   Tokyo3LandscapeBuilder.LandscapeAudit tokyo3Landscape,
                                   boolean deeplyBuried, int rockCover,
                                   int bedrockClearance,
                                   boolean controlMarkers, boolean hangars,
                                  boolean recoveryConsole, int lowerBeds,
                                  int surfaceBeds, int continuousShafts,
                                  int clearExits)
    {
        public String summary()
        {
            return String.format(Locale.ROOT,
                    "valid=%s mapVersion=%d deeplyBuried=%s rockCover=%d "
                            + "bedrockClearance=%d controlMarkers=%s "
                            + "hangars=%s recoveryConsole=%s lowerBeds=%d/3 "
                            + "surfaceBeds=%d/3 continuousShafts=%d/3 clearExits=%d/3 "
                            + "geoFront={%s} geoFrontLandscape={%s} tokyo3={%s} "
                            + "tokyo3Landscape={%s}",
                    this.valid, MAP_VERSION, this.deeplyBuried, this.rockCover,
                    this.bedrockClearance, this.controlMarkers, this.hangars,
                    this.recoveryConsole, this.lowerBeds, this.surfaceBeds,
                    this.continuousShafts, this.clearExits,
                    this.geoFront.summary(), this.geoFrontLandscape.summary(),
                    this.tokyo3.summary(), this.tokyo3Landscape.summary());
        }
    }
}
