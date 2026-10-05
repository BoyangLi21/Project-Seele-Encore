package com.projectseele.world;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.registry.ModBlocks;
import com.projectseele.registry.ModFluids;
import com.projectseele.visual.GeoFrontCommands;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.Mth;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.level.block.DirectionalBlock;
import net.minecraft.world.level.block.LadderBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.StairBlock;
import net.minecraft.world.level.block.state.properties.AttachFace;
import net.minecraft.world.phys.Vec3;

/** Three independent wet cages and their physical carrier routes. */
public final class EvaHangarBuilder
{
    public static final int HANGAR_CENTRE_Z = -136;
    public static final int HANGAR_BED_ABOVE_ORIGIN = 1;
    public static final int LCL_SHOULDER_LAYERS = 44;
    public static final int GALLERY_Y = 49;
    public static final int GALLERY_Z = -164;
    public static final int OBSERVATION_FLOOR_Y = GALLERY_Y + 9;
    public static final int BRIDGE_SEGMENTS = 9;
    /** Shared half-width of every static and moving EVA carrier. */
    public static final int CARRIER_HALF_EXTENT = 14;

    private static final int HALF_WIDTH = 20;
    private static final int HALF_DEPTH = 27;
    private static final int CHAMBER_HEIGHT = 80;
    private static final int GATE_Z = HANGAR_CENTRE_Z + HALF_DEPTH;
    private static final int CORRIDOR_HALF_WIDTH = 17;
    private static final int CARRIER_HALF = CARRIER_HALF_EXTENT;
    private static final int CATWALK_FLOOR_ABOVE_BED = 48;
    // The EVA is parked at yaw 180, so it faces -Z and looks straight into the
    // observation gallery. Its back, and therefore the entry-plug socket, the
    // rear gate and the transport tunnel, are all on +Z.
    // Three clear front circulation rows plus one supported inner guard row.
    // At the measured retained beds this is Z=-267..-264, instead of a
    // four-metre shelf extending to -261 in front of the TV mechanical beam.
    private static final int FRONT_CROSS_Z_FROM_BED = -27;
    private static final int FRONT_CROSS_DEPTH = 4;
    private static final int REAR_GANTRY_Z_FROM_BED = 25;
    private static final int REAR_BOARDING_Z_FROM_BED = 16;
    // The dorsal boarding deck sits on the SAME level as the shoulder catwalk
    // and the observation gallery, so the pilot walks one flat floor to the
    // plug with no ladder, and the plug hangs at gallery eye level instead of
    // near the cage ceiling where it read as floating in the cavern sky.
    private static final int REAR_GANTRY_ABOVE_BED = CATWALK_FLOOR_ABOVE_BED;
    /** Half-width of the clear lane the 17-wide airframe needs to leave. */
    private static final int EXIT_LANE_HALF_WIDTH = 16;
    private static final int SIDE_CATWALK_X = 19;
    private static final int BOARDING_CONNECTOR_HALF_WIDTH = 2;
    private static final int GALLERY_SIDE_MARGIN = 4;
    private static final int CONTROL_ROOM_HALF_WIDTH = 10;
    private static final int OBSERVATION_CEILING_Y = GALLERY_Y + 18;
    private static final int UPDATE_CLIENTS = Block.UPDATE_CLIENTS;
    /** Cells the plug crane currently occupies per cage, so it moves cheaply. */
    private static final Map<Integer, Set<BlockPos>> CRANE_CELLS =
            new HashMap<>();

    private EvaHangarBuilder() {}

    /** Clears process-local moving-crane ownership between server sessions. */
    public static void resetRuntime()
    {
        CRANE_CELLS.clear();
    }

    public static HangarAudit ensure(ServerLevel level, BlockPos origin)
    {
        if (!FacilityWorldPolicy.legacyGenerationAllowed(level.getServer()))
        {
            return inspect(level, origin);
        }
        ensureHangarPowerPylons(level, origin);
        HangarAudit audit = inspect(level, origin);
        if (audit.valid())
        {
            return audit;
        }
        /*
         * SEELE_FULL_REBUILD deliberately fuses an imported command module
         * with newly-authored civil routes.  The old build() method also calls
         * linkHangars(), which owns a broad legacy volume and can silently
         * repaint that fusion whenever one cage marker is missing.  Repair
         * only the three mechanical lots in the rescue save.
         */
        build(level, origin);
        audit = inspect(level, origin);
        ProjectSeele.LOGGER.info("NERV EVA hangars upgraded: {}", audit.summary());
        if (!audit.valid())
        {
            String gallery = galleryCrossWalkFailure(level, origin);
            ProjectSeele.LOGGER.warn("NERV boarding-route diagnostic: {} | gallery: {}",
                    boardingRouteDiagnostics(level, origin),
                    gallery == null ? "ok" : gallery);
        }
        return audit;
    }

    public static HangarAudit build(ServerLevel level, BlockPos origin)
    {
        FacilityWorldPolicy.requireLegacyGenerationAllowed(
                level.getServer(), "EvaHangarBuilder");
        HangarAudit audit = buildMechanicalOnly(level, origin);
        NervOperationsCentreBuilder.linkHangars(level, origin);
        return audit;
    }

    /**
     * Authors only the three wet cages, observation gallery and carrier
     * tunnels.  Facility-v2 rescue worlds use this entry point so restoring a
     * mechanical line can never repaint the imported command module.
     */
    public static HangarAudit buildMechanicalOnly(ServerLevel level,
                                                   BlockPos origin)
    {
        FacilityWorldPolicy.requireLegacyGenerationAllowed(
                level.getServer(), "EvaHangarBuilder.buildMechanicalOnly");
        PerformanceCounters.recordBuilderCall();
        for (int variant = 0; variant < 3; variant++)
        {
            buildChamber(level, origin, variant);
            buildTransportTunnel(level, origin, variant);
        }
        buildObservationGallery(level, origin);
        return inspect(level, origin);
    }

    /**
     * Rebuilds one compact S20 wet cage around the retained mechanical
     * anchors. This is deliberately narrower than {@link #buildMechanicalOnly}:
     * the S20 director owns staging and calls one bounded cage at a time.
     *
     * <p>The cage is a sealed fluid vessel, not a clearance box. Its front
     * wall is a lit observation face, the shoulder walks are supported by the
     * pressure shell, and the rear gate is the only opening into the carrier
     * line. Dynamic bridge, crane and LCL operations continue to use the same
     * physical coordinates as the live logistics state machine.</p>
     */
    public static void buildS20Cage(ServerLevel level, BlockPos origin,
                                    int variant)
    {
        requireVariant(variant);
        if (!FacilityWorldPolicy.unmigratedS20CivilGenerationAllowed(level))
        {
            return;
        }
        PerformanceCounters.recordBuilderCall();
        buildChamber(level, origin, variant);

        BlockPos bed = hangarBed(origin, variant);
        BlockState accent = accent(variant);
        BlockState frame =
                Blocks.POLISHED_BLACKSTONE_BRICKS.defaultBlockState();
        BlockState glass =
                Blocks.LIGHT_GRAY_STAINED_GLASS.defaultBlockState();

        /*
         * The inherited compact cage had a nearly black tinted observation
         * face. At GeoFront light levels it read as an open void even though a
         * wall was present. Keep the pressure boundary but make the EVA and
         * the real LCL legible from both operator decks.
         */
        for (int x = -(HALF_WIDTH - 2); x <= HALF_WIDTH - 2; x++)
        {
            for (int y = 38; y <= 65; y++)
            {
                BlockPos position = bed.offset(x, y, -HALF_DEPTH);
                boolean mullion = Math.floorMod(x, 6) == 0
                        || y == 38 || y == 65;
                boolean lamp = mullion
                        && (Math.floorMod(x, 12) == 0
                        || Math.floorMod(y - 38, 9) == 0);
                set(level, position, lamp
                        ? Blocks.SEA_LANTERN.defaultBlockState()
                        : mullion ? (Math.floorMod(x, 12) == 6
                                ? accent : frame) : glass);
            }
        }

        // Full-height illuminated structural ribs make the vessel's boundary
        // readable from the cavern instead of looking like floating catwalks.
        for (int z = -HALF_DEPTH; z <= HALF_DEPTH; z += 6)
        {
            for (int y = 1; y < CHAMBER_HEIGHT; y++)
            {
                boolean lamp = y == 12 || y == 28 || y == 44 || y == 60;
                for (int side : new int[] {-HALF_WIDTH, HALF_WIDTH})
                {
                    set(level, bed.offset(side, y, z),
                            lamp ? Blocks.SEA_LANTERN.defaultBlockState()
                                    : frame);
                }
            }
        }
        for (int x = -HALF_WIDTH; x <= HALF_WIDTH; x += 5)
        {
            set(level, bed.offset(x, CHAMBER_HEIGHT, 0),
                    Blocks.SEA_LANTERN.defaultBlockState());
        }
        for (int z = -18; z <= 18; z += 9)
        {
            for (int x = -15; x <= 15; x += 10)
            {
                set(level, bed.offset(x, CHAMBER_HEIGHT, z),
                        Blocks.SEA_LANTERN.defaultBlockState());
            }
        }

        // Reassert the only authorised mechanical exit after the shell pass.
        setGate(level, origin, variant, false);
        set(level, bed, Blocks.LODESTONE.defaultBlockState());
    }

    /**
     * Builds the shared two-level personnel frontage and its three controls.
     * The retained source-map route reaches this bounded room at its east end;
     * no speculative kilometre-long gallery is generated.
     */
    public static void buildS20ObservationGallery(
            ServerLevel level, BlockPos origin)
    {
        if (!FacilityWorldPolicy.unmigratedS20CivilGenerationAllowed(level))
        {
            return;
        }
        if (relocatedObservationInstalled(level, origin))
        {
            return;
        }
        PerformanceCounters.recordBuilderCall();
        buildObservationGallery(level, origin);

        int minX = IntegratedNervMapBuilder.LIFT_X[0] - HALF_WIDTH
                - GALLERY_SIDE_MARGIN;
        int maxX = IntegratedNervMapBuilder.LIFT_X[2] + HALF_WIDTH
                + GALLERY_SIDE_MARGIN;
        int minZ = GALLERY_Z - 7;
        int maxZ = GALLERY_Z + 8;

        // Replace the opaque southern frontage with a continuous pressure
        // window. Both lower boarding level and upper control booths now read
        // as rooms overlooking the three airframes.
        for (int x = minX + 1; x < maxX; x++)
        {
            for (int y = GALLERY_Y + 1; y < OBSERVATION_CEILING_Y; y++)
            {
                BlockPos position = origin.offset(x, y, maxZ);
                boolean mullion = Math.floorMod(x, 7) == 0
                        || y == OBSERVATION_FLOOR_Y;
                set(level, position, mullion
                        ? Blocks.POLISHED_BLACKSTONE_BRICKS.defaultBlockState()
                        : Blocks.LIGHT_GRAY_STAINED_GLASS.defaultBlockState());
            }
        }

        // A supported orthogonal east vestibule meets the physical cage lift
        // at (108, -394, 192). This is short enough to be a real room-to-room
        // connection, not an owner-box corridor.
        int walkY = origin.getY() + GALLERY_Y;
        int eastX = maxX;
        int liftX = 108;
        int turnZ = origin.getZ() + GALLERY_Z - 3;
        int liftZ = 192;
        buildS20PersonnelLeg(level,
                eastX, liftX, walkY, turnZ, true);
        buildS20PersonnelLeg(level,
                turnZ, liftZ - 7, walkY, liftX, false);
    }

    /**
     * Rebuilds the short straight carrier passage from one sealed cage to its
     * existing launch column. The launch shaft itself remains the retained
     * continuous source-map structure.
     */
    public static void buildS20TransportLine(ServerLevel level,
                                             BlockPos origin, int variant)
    {
        requireVariant(variant);
        if (!FacilityWorldPolicy.unmigratedS20CivilGenerationAllowed(level))
        {
            return;
        }
        PerformanceCounters.recordBuilderCall();
        buildTransportTunnel(level, origin, variant);
        BlockPos bed = hangarBed(origin, variant);
        BlockPos lower = IntegratedNervMapBuilder.lowerLiftBed(level, variant);
        set(level, bed, Blocks.LODESTONE.defaultBlockState());
        set(level, lower, Blocks.LODESTONE.defaultBlockState());

        /*
         * Give the lower interface a visible collar and service deck. The
         * doubled EVA keeps a clear 31x31 core; all personnel blocks stay on
         * the outside of that swept volume.
         */
        int deckY = bed.getY() + CATWALK_FLOOR_ABOVE_BED;
        int outer = IntegratedNervMapBuilder.SHAFT_OUTER_RADIUS;
        int clear = IntegratedNervMapBuilder.SHAFT_CLEAR_RADIUS;
        BlockState accent = accent(variant);
        for (int x = -outer; x <= outer; x++)
        {
            for (int z = -outer; z <= outer; z++)
            {
                int edge = Math.max(Math.abs(x), Math.abs(z));
                BlockPos deck = lower.offset(x, deckY - lower.getY(), z);
                if (edge == outer)
                {
                    set(level, deck, Math.floorMod(x + z, 6) == 0
                            ? Blocks.SEA_LANTERN.defaultBlockState()
                            : Blocks.POLISHED_BLACKSTONE_BRICKS
                                    .defaultBlockState());
                    set(level, deck.above(),
                            Blocks.IRON_BARS.defaultBlockState());
                }
                else if (edge > clear)
                {
                    set(level, deck, accent);
                }
            }
        }
    }

    /**
     * Builds the S20 launch-control gallery as one continuous personnel
     * space behind all three lower launch wells.
     *
     * <p>The retained source map contains the vertical launch columns, but
     * the old floor around them was an exposed maintenance apron. This
     * revision gives that machinery a deliberate NERV interior: three sealed
     * observation windows, a shared control spine, a supported pressure shell
     * and an orthogonal route back to the compact-cage personnel lift. The
     * gallery stays one block outside every shaft wall and never enters an
     * EVA, carrier or entry-plug swept volume.</p>
     */
    public static void buildS20LaunchControlSpine(ServerLevel level,
                                                   BlockPos origin)
    {
        if (!FacilityWorldPolicy.unmigratedS20CivilGenerationAllowed(level))
        {
            return;
        }
        PerformanceCounters.recordBuilderCall();
        int floorY = origin.getY() + GALLERY_Y;
        int shaftOuter = IntegratedNervMapBuilder.SHAFT_OUTER_RADIUS;
        BlockPos westWell = IntegratedNervMapBuilder.lowerLiftBed(level, 0);
        BlockPos eastWell = IntegratedNervMapBuilder.lowerLiftBed(level, 2);
        int northZ = westWell.getZ() + shaftOuter + 1;
        int southZ = northZ + 6;
        int westX = westWell.getX() - shaftOuter - 7;
        int eastX = eastWell.getX() + shaftOuter + 7;

        BlockState floor =
                Blocks.POLISHED_DEEPSLATE.defaultBlockState();
        BlockState support =
                com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
        BlockState wall =
                Blocks.POLISHED_BLACKSTONE_BRICKS.defaultBlockState();
        BlockState window =
                Blocks.LIGHT_GRAY_STAINED_GLASS.defaultBlockState();
        BlockState ceiling =
                Blocks.DEEPSLATE_TILES.defaultBlockState();

        for (int x = westX; x <= eastX; x++)
        {
            boolean frame = Math.floorMod(x - westX, 7) == 0;
            boolean facesWell = false;
            int nearestVariant = 0;
            int nearestDistance = Integer.MAX_VALUE;
            for (int variant = 0; variant < 3; variant++)
            {
                int distance = Math.abs(x
                        - IntegratedNervMapBuilder.lowerLiftBed(level, variant).getX());
                if (distance < nearestDistance)
                {
                    nearestDistance = distance;
                    nearestVariant = variant;
                }
                if (distance <= shaftOuter)
                {
                    facesWell = true;
                }
            }
            BlockState accent = accent(nearestVariant);

            for (int z = northZ; z <= southZ; z++)
            {
                BlockPos deck = new BlockPos(x, floorY, z);
                set(level, deck, Math.floorMod(x + z, 11) == 0
                        ? Blocks.SEA_LANTERN.defaultBlockState() : floor);
                set(level, deck.below(), support);
                for (int y = 1; y <= 4; y++)
                {
                    BlockPos position = deck.above(y);
                    boolean boundary = z == northZ || z == southZ
                            || x == westX || x == eastX;
                    if (!boundary)
                    {
                        clear(level, position);
                    }
                    else if (z == northZ && facesWell && !frame
                            && y >= 1 && y <= 3)
                    {
                        set(level, position, window);
                    }
                    else if (y == 2 && (z == southZ
                            || x == westX || x == eastX))
                    {
                        set(level, position, accent);
                    }
                    else
                    {
                        set(level, position, wall);
                    }
                }
                set(level, deck.above(5),
                        z > northZ && z < southZ
                                && Math.floorMod(x - westX, 8) == 4
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : ceiling);
            }
        }

        /*
         * The cage lift's upper door faces north at z=185. Route around the
         * east side of the lift, then return west into the gallery. This
         * preserves the lift's physical door direction and avoids cutting
         * through Unit-02's cage or launch shaft.
         */
        int liftHandoffX = 108;
        int liftHandoffZ = 185;
        int bypassX = eastX + 22;
        int galleryJoinZ = (northZ + southZ) / 2;
        buildS20EnclosedHall(level, liftHandoffX, bypassX,
                floorY, liftHandoffZ, true);
        buildS20EnclosedHall(level, liftHandoffZ, galleryJoinZ,
                floorY, bypassX, false);
        buildS20EnclosedHall(level, eastX, bypassX,
                floorY, galleryJoinZ, true);
        openS20HallIntersection(level, bypassX, liftHandoffZ, floorY);
        openS20HallIntersection(level, bypassX, galleryJoinZ, floorY);

        ProjectSeele.LOGGER.info(
                "S20 three-well launch control spine built: "
                        + "gallery=x[{},{}] y={} z[{},{}] "
                        + "sealedWindows=3 route=orthogonal "
                        + "mechanicalSweptVolumeWrites=0",
                westX, eastX, floorY, northZ, southZ);
    }

    /**
     * Restores the two-layer structural raft below all three launch wells.
     * The pyramid-clear migration removed these lower caps while leaving the
     * vertical shells intact, which made every shaft appear to end in air.
     * This method writes strictly below each carrier bed and therefore never
     * enters the EVA swept volume or horizontal transport rail.
     */
    public static void buildS20LaunchWellFoundations(ServerLevel level)
    {
        if (!FacilityWorldPolicy.unmigratedS20CivilGenerationAllowed(level))
        {
            return;
        }
        int radius = IntegratedNervMapBuilder.SHAFT_OUTER_RADIUS;
        for (int variant = 0; variant < 3; variant++)
        {
            BlockPos bed = IntegratedNervMapBuilder.lowerLiftBed(level, variant);
            for (int y = -2; y <= -1; y++)
            {
                for (int x = -radius; x <= radius; x++)
                {
                    for (int z = -radius; z <= radius; z++)
                    {
                        boolean beam = y == -2
                                || Math.floorMod(x, 8) == 0
                                || Math.floorMod(z, 8) == 0;
                        set(level, bed.offset(x, y, z), beam
                                ? com.projectseele.world.NervMaterials.structuralBlock()
                                        .defaultBlockState()
                                : Blocks.POLISHED_DEEPSLATE
                                        .defaultBlockState());
                    }
                }
            }
        }
        ProjectSeele.LOGGER.info(
                "S20 three-well foundation raft restored: "
                        + "layers=2 radius={} sweptVolumeWrites=0", radius);
    }

    /**
     * Seven-wide enclosed personnel hall with a continuous structural
     * under-slab. The arguments are axis coordinates, matching
     * {@link #buildS20PersonnelLeg}; no diagonal interpolation is permitted.
     */
    private static void buildS20EnclosedHall(
            ServerLevel level, int from, int to, int floorY,
            int fixed, boolean alongX)
    {
        int start = Math.min(from, to);
        int end = Math.max(from, to);
        for (int axis = start; axis <= end; axis++)
        {
            for (int lateral = -3; lateral <= 3; lateral++)
            {
                BlockPos deck = alongX
                        ? new BlockPos(axis, floorY, fixed + lateral)
                        : new BlockPos(fixed + lateral, floorY, axis);
                set(level, deck, Math.abs(lateral) == 3
                        ? Blocks.POLISHED_BLACKSTONE_BRICKS
                                .defaultBlockState()
                        : Math.floorMod(axis + lateral, 10) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.POLISHED_DEEPSLATE
                                        .defaultBlockState());
                set(level, deck.below(),
                        com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
                for (int y = 1; y <= 4; y++)
                {
                    if (Math.abs(lateral) < 3)
                    {
                        clear(level, deck.above(y));
                    }
                    else
                    {
                        set(level, deck.above(y),
                                y == 2 || y == 3
                                        ? Blocks.GRAY_STAINED_GLASS
                                                .defaultBlockState()
                                        : Blocks.DEEPSLATE_TILES
                                                .defaultBlockState());
                    }
                }
                set(level, deck.above(5),
                        Math.abs(lateral) < 3
                                && Math.floorMod(axis, 7) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.DEEPSLATE_TILES
                                        .defaultBlockState());
            }
        }
    }

    /** Removes the mutually-overlapping side walls at an orthogonal hall turn. */
    private static void openS20HallIntersection(
            ServerLevel level, int centreX, int centreZ, int floorY)
    {
        for (int x = centreX - 2; x <= centreX + 2; x++)
        {
            for (int z = centreZ - 2; z <= centreZ + 2; z++)
            {
                BlockPos floor = new BlockPos(x, floorY, z);
                set(level, floor, Math.floorMod(x + z, 9) == 0
                        ? Blocks.SEA_LANTERN.defaultBlockState()
                        : Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                set(level, floor.below(),
                        com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
                for (int y = 1; y <= 4; y++)
                {
                    clear(level, floor.above(y));
                }
                set(level, floor.above(5),
                        x == centreX && z == centreZ
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.DEEPSLATE_TILES.defaultBlockState());
            }
        }
    }

    /**
     * One bounded S20 revision for saves whose plant receipt predates the
     * widened boarding doors. It touches only the shared concourse, six door
     * apertures and three authored boarding connectors.
     */
    public static void repairS20BoardingRoutes(ServerLevel level,
                                                BlockPos origin)
    {
        PerformanceCounters.recordBuilderCall();
        clearGalleryConcourse(level, origin);
        for (int variant = 0; variant < 3; variant++)
        {
            buildBoardingConnector(level, origin, variant, accent(variant));
        }
        openShoulderCatwalkDoors(level, origin, GALLERY_Z + 8);
    }

    private static void buildS20PersonnelLeg(
            ServerLevel level, int from, int to, int floorY,
            int fixed, boolean alongX)
    {
        int start = Math.min(from, to);
        int end = Math.max(from, to);
        for (int axis = start; axis <= end; axis++)
        {
            for (int lateral = -2; lateral <= 2; lateral++)
            {
                BlockPos floor = alongX
                        ? new BlockPos(axis, floorY, fixed + lateral)
                        : new BlockPos(fixed + lateral, floorY, axis);
                set(level, floor, Math.floorMod(axis + lateral, 8) == 0
                        ? Blocks.SEA_LANTERN.defaultBlockState()
                        : Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                for (int head = 1; head <= 4; head++)
                {
                    clear(level, floor.above(head));
                }
                if (Math.abs(lateral) == 2)
                {
                    set(level, floor.above(),
                            Blocks.IRON_BARS.defaultBlockState());
                }
            }
        }
    }

    public static HangarAudit inspect(ServerLevel level, BlockPos origin)
    {
        int beds = 0;
        int shells = 0;
        int controls = 0;
        int galleries = 0;
        int observationRooms = 0;
        int plugRigs = 0;
        int walkableRoutes = 0;
        int wideTransportTunnels = 0;
        for (int variant = 0; variant < 3; variant++)
        {
            BlockPos bed = hangarBed(origin, variant);
            if (level.getBlockState(bed).is(Blocks.LODESTONE))
            {
                beds++;
            }
            if (level.getBlockState(bed.offset(-HALF_WIDTH, CHAMBER_HEIGHT, 0))
                    .is(Blocks.SEA_LANTERN)
                    && level.getBlockState(bed.offset(HALF_WIDTH, CHAMBER_HEIGHT, 0))
                    .is(Blocks.SEA_LANTERN))
            {
                shells++;
            }
            for (boolean prepare : new boolean[] {true, false})
            {
                if (level.getBlockState(controlPosition(origin, variant, prepare))
                        .is(Blocks.STONE_BUTTON))
                {
                    controls++;
                }
            }
            if (level.getBlockState(cancelControlPosition(origin, variant))
                    .is(Blocks.STONE_BUTTON))
            {
                controls++;
            }
            if (level.getBlockState(origin.offset(
                    IntegratedNervMapBuilder.LIFT_X[variant],
                    OBSERVATION_CEILING_Y, GALLERY_Z)).is(Blocks.BEACON))
            {
                galleries++;
            }
            if (level.getBlockState(origin.offset(
                    IntegratedNervMapBuilder.LIFT_X[variant],
                    OBSERVATION_FLOOR_Y + 3, GALLERY_Z + 8))
                    .is(Blocks.GRAY_STAINED_GLASS))
            {
                observationRooms++;
            }
            if (level.getBlockState(bed.offset(0, CHAMBER_HEIGHT - 1,
                    REAR_BOARDING_Z_FROM_BED)).is(Blocks.BEACON))
            {
                plugRigs++;
            }
            if (isBoardingRouteWalkable(level, origin, variant))
            {
                walkableRoutes++;
            }
            if (level.getBlockState(bed.offset(CORRIDOR_HALF_WIDTH, 68,
                    HALF_DEPTH + 4)).is(com.projectseele.world.NervMaterials.STRUCTURAL_SHELL))
            {
                wideTransportTunnels++;
            }
        }
        boolean galleryLinked = galleryCrossWalkFailure(level, origin) == null;
        boolean valid = beds == 3 && shells == 3 && controls == 9
                && galleries == 3 && observationRooms == 3
                && plugRigs == 3 && walkableRoutes == 3
                && wideTransportTunnels == 3 && galleryLinked;
        return new HangarAudit(valid, beds, shells, controls, galleries,
                observationRooms, plugRigs, walkableRoutes,
                wideTransportTunnels, galleryLinked);
    }

    /**
     * Cheap immutable gate for the live logistics tick. Carrier beds and the
     * boarding route are intentionally absent while an EVA is in transit, so
     * the complete static hangar audit must not pause its own state machine.
     */
    public static boolean runtimeInfrastructurePresent(ServerLevel level,
                                                       BlockPos origin)
    {
        /*
         * Runtime authority is deliberately narrower than the visual cage.
         * The user has hand-corrected walls, lamps, galleries and the old
         * local control panels several times; none of those decorative cells
         * is a mechanical prerequisite for an already-authored launch line.
         * Treating one replaced lantern as a global plant failure made all
         * command-room buttons inert and prevented missing parked EVAs from
         * being restored.  The lower carrier marker remains physical; the
         * Tokyo-3 surface anchor is deliberately air because the animated
         * hatch and its collision seal live one block above it.  This method
         * remains read-only and never repairs map geometry.
         */
        for (int variant = 0; variant < 3; variant++)
        {
            if (!level.getBlockState(
                            IntegratedNervMapBuilder.lowerLiftBed(level, variant))
                            .is(Blocks.LODESTONE))
            {
                return false;
            }
            if (!level.getBlockState(
                            IntegratedNervMapBuilder.surfaceLiftBed(
                                    level, variant))
                            .isAir())
            {
                return false;
            }
        }
        return true;
    }

    public static BlockPos hangarBed(BlockPos origin, int variant)
    {
        requireVariant(variant);
        return origin.offset(IntegratedNervMapBuilder.LIFT_X[variant],
                HANGAR_BED_ABOVE_ORIGIN, HANGAR_CENTRE_Z);
    }

    public static boolean isHangarBed(BlockPos position)
    {
        for (int variant = 0; variant < 3; variant++)
        {
            if (hangarBed(IntegratedNervMapBuilder.GEOFRONT_ORIGIN, variant)
                    .equals(position))
            {
                return true;
            }
        }
        return false;
    }

    public static boolean isHangarBed(ServerLevel level, BlockPos position)
    {
        for (int variant = 0; variant < 3; variant++)
        {
            if (hangarBed(RegionalFacilityLayout.evaOrigin(level),
                    variant).equals(position))
            {
                return true;
            }
        }
        return false;
    }

    /**
     * True only while this exact airframe is physically inside its assigned
     * GeoFront wet cage. Coordinate equality alone is not enough because the
     * overworld can legitimately contain the same x/z values.
     */
    public static boolean isInsideAssignedCage(ServerLevel level,
                                                EvaUnit01Entity unit,
                                                int variant)
    {
        if (!level.dimension().equals(GeoFrontCommands.GEOFRONT)
                || unit.getUnitVariant() != variant)
        {
            return false;
        }
        BlockPos bed = hangarBed(
                RegionalFacilityLayout.evaOrigin(level), variant);
        return Math.abs(unit.getX() - (bed.getX() + 0.5D)) <= HALF_WIDTH - 1
                && Math.abs(unit.getZ() - (bed.getZ() + 0.5D))
                        <= HALF_DEPTH - 1
                && unit.getY() >= bed.getY() - 2.0D
                && unit.getY() <= bed.getY() + CHAMBER_HEIGHT - 2.0D;
    }

    public static BlockPos controlPosition(BlockPos origin, int variant,
                                           boolean prepare)
    {
        requireVariant(variant);
        return origin.offset(IntegratedNervMapBuilder.LIFT_X[variant]
                        + (prepare ? -2 : 2),
                OBSERVATION_FLOOR_Y + 1, GALLERY_Z + 2);
    }

    /**
     * The red RECALL key in each observation booth, between PREPARE and STATUS.
     *
     * <p>Cancels a launch that is locked at the silo and slides the airframe
     * back into its wet cage, so a pilot who armed the sortie is not stranded
     * on the catapult waiting for a command-room release.
     */
    public static BlockPos cancelControlPosition(BlockPos origin, int variant)
    {
        requireVariant(variant);
        return origin.offset(IntegratedNervMapBuilder.LIFT_X[variant],
                OBSERVATION_FLOOR_Y + 1, GALLERY_Z + 2);
    }

    /**
     * Where the entry plug hangs while the cage is at rest.
     *
     * <p>Anchored to the cage, not derived from the airframe: the plug is
     * hardware belonging to this hangar, and deriving it from a unit that may
     * be mid-transfer put it outside the chamber entirely. It rests level with
     * the dorsal gantry deck so a pilot who has walked the route is standing
     * beside the hatch, not under it.
     */
    public static Vec3 plugRestPosition(BlockPos origin, int variant)
    {
        requireVariant(variant);
        BlockPos bed = hangarBed(origin, variant);
        return new Vec3(bed.getX() + 0.5D,
                bed.getY() + REAR_GANTRY_ABOVE_BED + 2.2D,
                bed.getZ() + REAR_BOARDING_Z_FROM_BED + 0.5D);
    }

    /**
     * Waterproof cage-side external-power socket. Its low mounting point keeps
     * the rendered umbilical within the normal 32-block connection envelope
     * while LCL rises around the restrained airframe.
     */
    public static BlockPos hangarPowerPylonPosition(BlockPos origin,
                                                     int variant)
    {
        BlockPos bed = hangarBed(origin, variant);
        return bed.offset(HALF_WIDTH - 2, 20, 4);
    }

    private static void ensureHangarPowerPylons(ServerLevel level,
                                                 BlockPos origin)
    {
        for (int variant = 0; variant < 3; variant++)
        {
            set(level, hangarPowerPylonPosition(origin, variant),
                    ModBlocks.UMBILICAL_PYLON.get().defaultBlockState());
        }
    }

    /**
     * Restores the single authored cage-side external-power socket without
     * rebuilding any hangar geometry.  S20 deliberately forbids the legacy
     * structure builder, but the launch runtime still needs this one apparatus
     * block so an occupied EVA can charge before the carrier leaves the cage.
     */
    public static boolean ensureRuntimePowerPylon(ServerLevel level,
                                                   BlockPos origin,
                                                   int variant)
    {
        BlockPos position = hangarPowerPylonPosition(origin, variant);
        if (level.getBlockEntity(position)
                instanceof UmbilicalPylonBlockEntity)
        {
            return true;
        }
        BlockState current = level.getBlockState(position);
        if (!current.isAir()
                && !current.getFluidState().is(ModFluids.LCL_SOURCE.get())
                && !current.getFluidState().is(ModFluids.FLOWING_LCL.get())
                && !current.canBeReplaced())
        {
            ProjectSeele.LOGGER.error(
                    "NERV EVA-0{} external-power socket blocked at {} by {}; no scenery was overwritten",
                    variant, position.toShortString(), current);
            return false;
        }
        set(level, position,
                ModBlocks.UMBILICAL_PYLON.get().defaultBlockState());
        return level.getBlockEntity(position)
                instanceof UmbilicalPylonBlockEntity;
    }

    /** Top of the suspension, where the crane cables meet the rail. */
    public static int craneRailAboveBed()
    {
        return HangarStructuralFrameR44.CRANE_RUNNING_SURFACE_ABOVE_BED;
    }

    /**
     * Foot of a rear ladder, on the shoulder catwalk.
     *
     * <p>This is the last point of the boarding route a walking entity can
     * actually reach: it shares the gallery's floor level, whereas the gantry
     * above it is ladder-only.
     */
    public static BlockPos ladderFootPosition(BlockPos origin, int variant)
    {
        requireVariant(variant);
        BlockPos bed = hangarBed(origin, variant);
        return new BlockPos(bed.getX() - SIDE_CATWALK_X,
                bed.getY() + CATWALK_FLOOR_ABOVE_BED + 1,
                bed.getZ() + REAR_GANTRY_Z_FROM_BED - 1);
    }

    /** Human-scale endpoint of the extended dorsal boarding bridge. */
    public static BlockPos boardingPosition(BlockPos origin, int variant)
    {
        BlockPos bed = hangarBed(origin, variant);
        return new BlockPos(bed.getX() + 2,
                bed.getY() + REAR_GANTRY_ABOVE_BED + 1,
                bed.getZ() + REAR_BOARDING_Z_FROM_BED + 3);
    }

    /** Centre of the permanent pilot standby platform facing the EVA. */
    public static BlockPos pilotStandbyPosition(BlockPos origin, int variant)
    {
        BlockPos bed = hangarBed(origin, variant);
        return new BlockPos(bed.getX(),
                bed.getY() + CATWALK_FLOOR_ABOVE_BED + 1,
                bed.getZ() + FRONT_CROSS_Z_FROM_BED);
    }

    /**
     * Physical walking waypoints from the shared gallery to the suspended
     * plug. The route deliberately goes through the left pressure door and
     * around the airframe instead of asking pathfinding to cut straight
     * through the observation window and EVA.
     */
    public static BlockPos boardingRouteWaypoint(BlockPos origin, int variant,
                                                  int leg)
    {
        requireVariant(variant);
        BlockPos bed = hangarBed(origin, variant);
        int walkY = bed.getY() + CATWALK_FLOOR_ABOVE_BED + 1;
        int sideX = bed.getX() - SIDE_CATWALK_X;
        return switch (leg)
        {
            // Inside the shared gallery, immediately before its pressure door.
            case 0 -> new BlockPos(sideX, walkY,
                    origin.getZ() + GALLERY_Z + 7);
            // Outside the observation window, on the shoulder catwalk.
            case 1 -> new BlockPos(sideX, walkY,
                    origin.getZ() + GALLERY_Z + 10);
            // Rear corner where the fixed side gantry meets the moving bridge.
            case 2 -> new BlockPos(sideX, walkY,
                    bed.getZ() + REAR_GANTRY_Z_FROM_BED - 1);
            // Centre of the extended bridge, beside the external capsule.
            case 3 -> new BlockPos(bed.getX() + 2, walkY,
                    bed.getZ() + REAR_BOARDING_Z_FROM_BED + 4);
            default -> boardingPosition(origin, variant);
        };
    }

    public static int gateZ(BlockPos origin)
    {
        return origin.getZ() + GATE_Z;
    }

    public static int hangarZ(BlockPos origin)
    {
        return origin.getZ() + HANGAR_CENTRE_Z;
    }

    public static void setGate(ServerLevel level, BlockPos origin,
                               int variant, boolean open)
    {
        BlockPos bed = hangarBed(origin, variant);
        // A recalled or administratively recovered hull can have a stale wet
        // bay even when its logical sortie gauge is zero. The pressure gate
        // must obey the actual liquid volume before exposing the ramp.
        if (open)
        {
            drainLclEnvelope(level, origin, variant);
        }
        int gateTop = FacilityLayoutR29.active(level.getServer()) ? -370-bed.getY() : 66;
        // The moving gate is narrower than the wet vessel. Fixed returns
        // must remain sealed even while the central transport opening moves.
        for(int side:new int[]{-1,1})for(int x=CORRIDOR_HALF_WIDTH+1;x<=HALF_WIDTH;x++)
            for(int y=0;y<=LCL_SHOULDER_LAYERS;y++)
            {
                BlockPos q=bed.offset(side*x,y,HALF_DEPTH);BlockState old=level.getBlockState(q);
                if(old.isAir()||old.is(ModBlocks.LCL_BLOCK.get()))
                    set(level,q,ModBlocks.NERV_SHAFT_PANEL.get().defaultBlockState());
            }
        BlockState accent = accent(variant);
        for (int x = -CORRIDOR_HALF_WIDTH;
             x <= CORRIDOR_HALF_WIDTH; x++)
        {
            for (int y = 1; y <= gateTop; y++)
            {
                BlockPos position = new BlockPos(bed.getX() + x,
                        bed.getY() + y, origin.getZ() + GATE_Z);
                if (open)
                {
                    if (Math.abs(x) == CORRIDOR_HALF_WIDTH
                            || y == 1 || y == gateTop)
                    {
                        set(level, position,
                                Blocks.IRON_BLOCK.defaultBlockState());
                    }
                    else
                    {
                        clear(level, position);
                    }
                }
                else
                {
                    boolean edge = Math.abs(x) == CORRIDOR_HALF_WIDTH
                            || y == 1 || y == gateTop;
                    set(level, position, edge
                            ? Blocks.IRON_BLOCK.defaultBlockState()
                            : Blocks.BARRIER.defaultBlockState());
                }
            }
        }
    }

    /** Sets the exact number of full LCL layers, bottom-up. */
    public static void setLclLevel(ServerLevel level, BlockPos origin,
                                   int variant, int layers)
    {
        BlockPos bed = hangarBed(origin, variant);
        int safeLayers = Math.max(0, Math.min(LCL_SHOULDER_LAYERS, layers));
        // LCL is a fluid: sources placed on the inner footprint flow outward
        // and settle against the cage walls. Draining therefore has to sweep
        // the whole interior, not just the columns that were filled, or the
        // outermost ring survives every drain.
        for (int y = 1; y <= LCL_SHOULDER_LAYERS; y++)
        {
            boolean filled = y <= safeLayers;
            for (int x = -(HALF_WIDTH - 1); x <= HALF_WIDTH - 1; x++)
            {
                for (int z = -(HALF_DEPTH - 1); z <= HALF_DEPTH - 1; z++)
                {
                    BlockPos position = bed.offset(x, y, z);
                    if (position.equals(hangarPowerPylonPosition(
                            origin, variant)))
                    {
                        continue;
                    }
                    if (filled && Math.abs(x) <= HALF_WIDTH - 1
                            && Math.abs(z) <= HALF_DEPTH - 1)
                    {
                        set(level, position, ModFluids.LCL_SOURCE.get()
                                .defaultFluidState().createLegacyBlock());
                    }
                    else if (level.getFluidState(position).getFluidType()
                            == ModFluids.LCL_TYPE.get())
                    {
                        clearLcl(level, position);
                    }
                }
            }
        }
    }

    public static void setLclLayer(ServerLevel level, BlockPos origin,
                                   int variant, int layer, boolean filled)
    {
        if (layer < 1 || layer > LCL_SHOULDER_LAYERS)
        {
            return;
        }
        BlockPos bed = hangarBed(origin, variant);
        // Drains sweep the full interior for the same reason setLclLevel does:
        // the fluid spreads past the source footprint before it is drained.
        for (int x = -(HALF_WIDTH - 1); x <= HALF_WIDTH - 1; x++)
        {
            for (int z = -(HALF_DEPTH - 1); z <= HALF_DEPTH - 1; z++)
            {
                BlockPos position = bed.offset(x, layer, z);
                if (position.equals(hangarPowerPylonPosition(
                        origin, variant)))
                {
                    continue;
                }
                if (filled && Math.abs(x) <= HALF_WIDTH - 1
                        && Math.abs(z) <= HALF_DEPTH - 1)
                {
                    set(level, position, ModFluids.LCL_SOURCE.get()
                            .defaultFluidState().createLegacyBlock());
                }
                else if (level.getFluidState(position).getFluidType()
                        == ModFluids.LCL_TYPE.get())
                {
                    clearLcl(level, position);
                }
            }
        }
    }
    public static int lclLevel(ServerLevel level, BlockPos origin, int variant)
    {
        BlockPos bed = hangarBed(origin, variant);
        int layers = 0;
        for (int y = 1; y <= LCL_SHOULDER_LAYERS; y++)
        {
            if (level.getFluidState(bed.offset(
                    Math.min(8, HALF_WIDTH - 2), y,
                    Math.min(8, HALF_DEPTH - 2))).getFluidType()
                    == ModFluids.LCL_TYPE.get())
            {
                layers = y;
            }
        }
        return layers;
    }

    /**
     * Removes every remaining LCL cell from the sealed cage and pressure-door
     * apron. Fluid simulation can leave flowing cells beyond a former source
     * layer; logistics must not open the carrier gate until this physical
     * sweep reports an empty envelope.
     *
     * @return remaining LCL cells after the sweep (normally zero).
     */
    public static int drainLclEnvelope(ServerLevel level, BlockPos origin,
                                       int variant)
    {
        BlockPos bed = hangarBed(origin, variant);
        int maximumZ = HALF_DEPTH + 8;
        for (int y = -4; y <= LCL_SHOULDER_LAYERS; y++)
        {
            for (int x = -(HALF_WIDTH - 1); x <= HALF_WIDTH - 1; x++)
            {
                for (int z = -(HALF_DEPTH - 1); z <= maximumZ; z++)
                {
                    BlockPos position = bed.offset(x, y, z);
                    if (level.getFluidState(position).getFluidType()
                            == ModFluids.LCL_TYPE.get())
                    {
                        clearLcl(level, position);
                    }
                }
            }
        }
        return countLclEnvelope(level, origin, variant);
    }

    /** Counts physical LCL cells in the cage plus pressure-door apron. */
    public static int countLclEnvelope(ServerLevel level, BlockPos origin,
                                       int variant)
    {
        BlockPos bed = hangarBed(origin, variant);
        int count = 0;
        int maximumZ = HALF_DEPTH + 8;
        for (int y = -4; y <= LCL_SHOULDER_LAYERS; y++)
        {
            for (int x = -(HALF_WIDTH - 1); x <= HALF_WIDTH - 1; x++)
            {
                for (int z = -(HALF_DEPTH - 1); z <= maximumZ; z++)
                {
                    if (level.getFluidState(bed.offset(x, y, z)).getFluidType()
                            == ModFluids.LCL_TYPE.get())
                    {
                        count++;
                    }
                }
            }
        }
        return count;
    }

    private static void clearLcl(ServerLevel level, BlockPos position)
    {
        // Notify the fluid descendants as well as the renderer. UPDATE_CLIENTS
        // alone leaves orphaned flowing LCL below the door apron indefinitely.
        if (level.getFluidState(position).getFluidType() == ModFluids.LCL_TYPE.get())
        {
            level.setBlock(position, Blocks.AIR.defaultBlockState(), net.minecraft.world.level.block.Block.UPDATE_ALL);
            PerformanceCounters.recordWorldBlockWrites(1);
        }
    }

    /** Moves/restores the visible 29x29 maintenance carrier one block at a time. */
    public static void setCarrier(ServerLevel level, BlockPos origin,
                                  int variant, int centreZ, boolean present)
    {
        BlockPos hangar = hangarBed(origin, variant);
        int y = hangar.getY();
        int centreX = hangar.getX();
        for (int x = -CARRIER_HALF; x <= CARRIER_HALF; x++)
        {
            for (int z = -CARRIER_HALF; z <= CARRIER_HALF; z++)
            {
                BlockPos position = new BlockPos(centreX + x, y, centreZ + z);
                if (present)
                {
                    boolean rim = Math.abs(x) == CARRIER_HALF
                            || Math.abs(z) == CARRIER_HALF;
                    set(level, position, rim
                            ? Blocks.IRON_BLOCK.defaultBlockState()
                            : Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState());
                }
                else
                {
                    set(level, position, transportFloor(level, position, origin, variant));
                }
            }
        }
        if (present)
        {
            set(level, new BlockPos(centreX, y, centreZ),
                    Blocks.LODESTONE.defaultBlockState());
        }
    }

    /**
     * Slides a carrier without destroying and repainting its overlapping
     * 29x29 footprint. Only cells whose final state changes are sent to
     * clients, which keeps three simultaneous EVA transfers within the tick
     * budget.
     */
    public static void moveCarrier(ServerLevel level, BlockPos origin,
                                   int variant, int oldCentreZ, int newCentreZ)
    {
        if (oldCentreZ == newCentreZ)
        {
            return;
        }
        BlockPos hangar = hangarBed(origin, variant);
        int y = hangar.getY();
        int centreX = hangar.getX();
        int minZ = Math.min(oldCentreZ, newCentreZ) - CARRIER_HALF;
        int maxZ = Math.max(oldCentreZ, newCentreZ) + CARRIER_HALF;
        for (int worldZ = minZ; worldZ <= maxZ; worldZ++)
        {
            int relativeNewZ = worldZ - newCentreZ;
            boolean insideNew = Math.abs(relativeNewZ) <= CARRIER_HALF;
            for (int x = -CARRIER_HALF; x <= CARRIER_HALF; x++)
            {
                BlockPos position = new BlockPos(centreX + x, y, worldZ);
                if (insideNew)
                {
                    boolean rim = Math.abs(x) == CARRIER_HALF
                            || Math.abs(relativeNewZ) == CARRIER_HALF;
                    set(level, position, rim
                            ? Blocks.IRON_BLOCK.defaultBlockState()
                            : Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState());
                }
                else
                {
                    set(level, position, transportFloor(level, position, origin, variant));
                }
            }
        }
        set(level, new BlockPos(centreX, y, newCentreZ),
                Blocks.LODESTONE.defaultBlockState());
    }

    public static void restoreStaticCarrier(ServerLevel level, BlockPos origin,
                                            int variant, BlockPos station)
    {
        setCarrier(level, origin, variant, station.getZ(), true);
    }

    /**
     * Reasserts only the visible mechanical guideway on an existing S20
     * transfer floor. Old R28 saves predate the bright rails and therefore
     * showed an EVA gliding across an undifferentiated dark slab. This writes
     * one floor layer only: no air clearing, walls or observation structures.
     */
    public static void ensureTransportGuideway(ServerLevel level,
                                               BlockPos origin, int variant,
                                               BlockPos start, BlockPos end)
    {
        requireVariant(variant);
        BlockPos hangar = hangarBed(origin, variant);
        if (start.getX() != hangar.getX() || end.getX() != hangar.getX()
                || start.getY() != hangar.getY()
                || end.getY() != hangar.getY())
        {
            return;
        }
        int minZ = Math.min(start.getZ(), end.getZ());
        int maxZ = Math.max(start.getZ(), end.getZ());
        for (int z = minZ; z <= maxZ; z++)
        {
            boolean sleeper = Math.floorMod(z - hangar.getZ(), 6) == 0;
            for (int dx = -10; dx <= 10; dx++)
            {
                if (Math.abs(dx) == 5 || dx == 0 || sleeper)
                {
                    BlockPos position = new BlockPos(
                            hangar.getX() + dx, hangar.getY(), z);
                    set(level, position,
                            transportFloor(level, position, origin, variant));
                }
            }
        }
        set(level, start, Blocks.LODESTONE.defaultBlockState());
        set(level, end, Blocks.LODESTONE.defaultBlockState());
    }

    private static void buildChamber(ServerLevel level, BlockPos origin,
                                     int variant)
    {
        BlockPos bed = hangarBed(origin, variant);
        TvPersonnelPlatformRecipeR44.ensure(level, bed).ifPresent(fault ->
                { throw new IllegalStateException("R44 personnel producer rejected before chamber writes: " + fault); });
        BlockState accent = accent(variant);
        for (int x = -HALF_WIDTH; x <= HALF_WIDTH; x++)
        {
            for (int z = -HALF_DEPTH; z <= HALF_DEPTH; z++)
            {
                set(level, bed.offset(x, 0, z), Math.abs(x) == CARRIER_HALF
                        ? Blocks.POLISHED_BASALT.defaultBlockState()
                        : Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                for (int y = 1; y <= CHAMBER_HEIGHT; y++)
                {
                    boolean wall = Math.abs(x) == HALF_WIDTH
                            || Math.abs(z) == HALF_DEPTH
                            || y == CHAMBER_HEIGHT;
                    BlockPos position = bed.offset(x, y, z);
                    if (preservedCrewInfrastructureR44(level, bed, position))
                    {
                        continue;
                    }
                    boolean frontCrewOpening = z >= FRONT_CROSS_Z_FROM_BED
                            && z < FRONT_CROSS_Z_FROM_BED + FRONT_CROSS_DEPTH - 1
                            && Math.abs(x) <= SIDE_CATWALK_X
                            && y > CATWALK_FLOOR_ABOVE_BED
                            && y <= CATWALK_FLOOR_ABOVE_BED + 2;
                    if (frontCrewOpening)
                    {
                        clear(level, position);
                        continue;
                    }
                    if (!wall)
                    {
                        clear(level, position);
                        continue;
                    }
                    boolean observationWindow = z == -HALF_DEPTH
                            && Math.abs(x) <= HALF_WIDTH - 2
                            && y >= 40 && y <= 65;
                    boolean lampBand = (Math.abs(x) == HALF_WIDTH
                            && Math.floorMod(z, 6) == 0
                            && y == CATWALK_FLOOR_ABOVE_BED)
                            || (y == CHAMBER_HEIGHT && Math.floorMod(x + z, 8) == 0);
                    set(level, position, observationWindow
                            ? Blocks.TINTED_GLASS.defaultBlockState()
                            : lampBand ? Blocks.SEA_LANTERN.defaultBlockState()
                            : (y % 9 == 0 ? accent
                            : com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState()));
                }
            }
        }
        // Dedicated shell receipts: these exact corner lamps are audited and
        // must not depend on the decorative ceiling-band modulo pattern.
        set(level, bed.offset(-HALF_WIDTH, CHAMBER_HEIGHT, 0),
                Blocks.SEA_LANTERN.defaultBlockState());
        set(level, bed.offset(HALF_WIDTH, CHAMBER_HEIGHT, 0),
                Blocks.SEA_LANTERN.defaultBlockState());
        set(level, bed, Blocks.LODESTONE.defaultBlockState());
        buildShoulderCatwalk(level, bed, accent);
        buildRearBoardingGantry(level, bed, accent);
        buildPlugCraneRig(level, bed, accent);
        setGate(level, origin, variant, false);
        setLclLevel(level, origin, variant, LCL_SHOULDER_LAYERS);
        set(level, hangarPowerPylonPosition(origin, variant),
                ModBlocks.UMBILICAL_PYLON.get().defaultBlockState());
    }

    private static void buildShoulderCatwalk(ServerLevel level, BlockPos bed,
                                               BlockState accent)
    {
        // Both side runs stay outside the exit lane. Their bed+48 datum is
        // the actual shared gallery floor; boarding remains on the rear.
        int y = CATWALK_FLOOR_ABOVE_BED;
        for (int z = FRONT_CROSS_Z_FROM_BED; z <= REAR_GANTRY_Z_FROM_BED; z++)
        {
            for (int x : new int[] {-SIDE_CATWALK_X,
                    -(SIDE_CATWALK_X - 1), SIDE_CATWALK_X - 1,
                    SIDE_CATWALK_X})
            {
                setCrewBearingR44(level, bed, bed.offset(x, y, z),
                        personnelDeck(level,accent,Math.abs(x)!=SIDE_CATWALK_X));
            }
            // Inner guardrail only on the pure side-catwalk stretch. Across the
            // dorsal boarding deck (z >= boarding) the gantry floor reaches
            // inward to the plug and the pilot — or the walking dummy — has to
            // cross these very columns, so a rail here fences boarding off.
            if (z < REAR_BOARDING_Z_FROM_BED
                    && z >= FRONT_CROSS_Z_FROM_BED + FRONT_CROSS_DEPTH - 1)
            {
                // The inward guard needs a real structural lip. The two
                // public lanes remain offsets18/19; the former template hung
                // this offset17 rail over air without its declared support.
                for (int side : new int[] {-1, 1})
                {
                    setCrewBearingR44(level, bed, bed.offset(side * (SIDE_CATWALK_X - 2), y, z),
                            ModBlocks.NERV_FLOOR_PANEL.get().defaultBlockState());
                    if (Math.floorMod(z - FRONT_CROSS_Z_FROM_BED, 10) == 4)
                    {
                        for (int offset = SIDE_CATWALK_X - 2;
                             offset <= SIDE_CATWALK_X; offset++)
                        {
                            setCrewBearingR44(level, bed, bed.offset(side * offset, y - 1, z),
                                    ModBlocks.NERV_STRUCTURAL_PANEL.get().defaultBlockState());
                        }
                    }
                }
                setCrewRailR44(level, bed, bed.offset(-(SIDE_CATWALK_X - 2), y + 1, z),
                        FacilityEdgeRailR41.empty(ModBlocks.NERV_EDGE_RAIL.get())
                                .setValue(FacilityEdgeRailR41.EAST, true));
                setCrewRailR44(level, bed, bed.offset(SIDE_CATWALK_X - 2, y + 1, z),
                        FacilityEdgeRailR41.empty(ModBlocks.NERV_EDGE_RAIL.get())
                                .setValue(FacilityEdgeRailR41.WEST, true));
            }
            else
            {
                clearOwnedCrewRailR44(level, bed, bed.offset(-(SIDE_CATWALK_X - 2), y + 1, z));
                clearOwnedCrewRailR44(level, bed, bed.offset(SIDE_CATWALK_X - 2, y + 1, z));
            }
        }
        // The front cross faces the EVA and the gallery glass; it is a viewing
        // and service run only. Boarding happens at the rear gantry.
        for (int x = -SIDE_CATWALK_X; x <= SIDE_CATWALK_X; x++)
        {
            for (int row = 0; row < FRONT_CROSS_DEPTH; row++)
            {
                setCrewBearingR44(level, bed, bed.offset(x, y, FRONT_CROSS_Z_FROM_BED + row),
                        Math.floorMod(x + row, 5) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : personnelDeck(level, accent, false));
            }
            // Stop short of the two side runs: this rail guards the cross
            // walkway's inner edge, and carrying it the full width would
            // fence off the very lanes the pilot uses to reach the back.
            if (Math.abs(x) <= SIDE_CATWALK_X - 2)
            {
                // Mount the guard on this declared bearing slab. Placing
                // bars one row beyond the crossway left their feet in air.
                BlockState guard = FacilityEdgeRailR41.empty(ModBlocks.NERV_EDGE_RAIL.get())
                        .setValue(FacilityEdgeRailR41.SOUTH, true);
                if (Math.abs(x) == SIDE_CATWALK_X - 2)
                    guard = guard.setValue(x < 0 ? FacilityEdgeRailR41.EAST : FacilityEdgeRailR41.WEST, true);
                setCrewRailR44(level, bed, bed.offset(x, y + 1,
                        FRONT_CROSS_Z_FROM_BED + FRONT_CROSS_DEPTH - 1), guard);
            }
        }
    }

    private static boolean preservedCrewInfrastructureR44(ServerLevel level, BlockPos bed, BlockPos position)
    {
        if (net.minecraft.core.registries.BuiltInRegistries.BLOCK.getKey(level.getBlockState(position).getBlock())
                .getNamespace().equals("mtr")) return true;
        if (level.getBlockEntity(position) != null) return true;
        // This is a measured complete legacy lift arrival and its approach,
        // including its air apertures. It is not inferred from empty cells.
        return bed.equals(new BlockPos(72, -443, -240))
                && position.getX() >= 85 && position.getX() <= 98
                && position.getY() >= -399 && position.getY() <= -390
                && position.getZ() >= -264 && position.getZ() <= -248;
    }

    private static void setCrewBearingR44(ServerLevel level, BlockPos bed, BlockPos position, BlockState state)
    {
        if (!preservedCrewInfrastructureR44(level, bed, position)) set(level, position, state);
    }

    private static void setCrewRailR44(ServerLevel level, BlockPos bed, BlockPos position, BlockState state)
    {
        if (preservedCrewInfrastructureR44(level, bed, position)) return;
        BlockState before = level.getBlockState(position);
        if (before.isAir() || before.is(Blocks.LIGHT) || before.is(Blocks.IRON_BARS)
                || before.is(ModBlocks.NERV_EDGE_RAIL.get())) set(level, position, state);
    }

    private static void clearOwnedCrewRailR44(ServerLevel level, BlockPos bed, BlockPos position)
    {
        if (preservedCrewInfrastructureR44(level, bed, position)) return;
        BlockState before = level.getBlockState(position);
        if (before.is(ModBlocks.NERV_EDGE_RAIL.get()) || before.is(Blocks.IRON_BARS))
            set(level, position, Blocks.AIR.defaultBlockState());
    }

    /**
     * Fixed dorsal boarding platforms, one per side, plus the ladders that
     * reach them from the shoulder catwalk. Everything here stays clear of the
     * exit lane; only the split bridge between them crosses it.
     */
    private static void buildRearBoardingGantry(ServerLevel level, BlockPos bed,
                                                 BlockState accent)
    {
        int y = REAR_GANTRY_ABOVE_BED;
        int lastFloorZ = REAR_GANTRY_Z_FROM_BED - 1;
        BlockState frame = personnelDeck(level,accent,false);
        for (int z = REAR_BOARDING_Z_FROM_BED; z <= lastFloorZ; z++)
        {
            for (int side : new int[] {-1, 1})
            {
                for (int offset = EXIT_LANE_HALF_WIDTH + 1;
                     offset <= SIDE_CATWALK_X; offset++)
                {
                    int x = side * offset;
                    set(level, bed.offset(x, y, z),
                            Math.floorMod(x + z, 6) == 0
                                    ? Blocks.SEA_LANTERN.defaultBlockState()
                                    : offset == SIDE_CATWALK_X ? frame : personnelDeck(level,accent,true));
                    for (int head = 1; head <= 4; head++)
                    {
                        clearExceptCrane(level, bed.offset(x, y + head, z));
                    }
                }
            }
        }
        // Edge-mounted rails leave the central pilot-sized volume clear.
        // The moving bridge refreshes their boundary after every extension.
    }

    /**
     * Ladders from the shoulder catwalk up to the dorsal gantry, in a clear
     * shaft one block behind the deck.
     *
     * <p>Called at the end of {@code linkHangars} rather than only from the
     * chamber pass. That ramp is shifted twelve blocks off its lane, so its
     * cleared headroom runs straight through the +X ladder of every cage, and
     * it is repainted on every login — a one-time rebuild here would be undone
     * the next time the player joined.
     */
    public static void buildRearLadders(ServerLevel level, BlockPos origin,
                                         int variant)
    {
        requireVariant(variant);
        BlockPos bed = hangarBed(origin, variant);
        for (int side : new int[] {-1, 1})
        {
            int x = side * SIDE_CATWALK_X;
            for (int ladderY = CATWALK_FLOOR_ABOVE_BED + 1;
                 ladderY <= REAR_GANTRY_ABOVE_BED; ladderY++)
            {
                // Backing first: a ladder placed against air is removed by the
                // neighbour-shape update that follows.
                set(level, bed.offset(x, ladderY, REAR_GANTRY_Z_FROM_BED + 1),
                        com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
                set(level, bed.offset(x, ladderY, REAR_GANTRY_Z_FROM_BED),
                        Blocks.LADDER.defaultBlockState()
                                .setValue(LadderBlock.FACING, Direction.NORTH));
            }
            clear(level, bed.offset(x, REAR_GANTRY_ABOVE_BED + 1,
                    REAR_GANTRY_Z_FROM_BED));
        }
    }

    private static void buildTransportTunnel(ServerLevel level, BlockPos origin,
                                             int variant)
    {
        BlockPos bed = hangarBed(origin, variant);
        int destinationZ = IntegratedNervMapBuilder.lowerLiftBed(level, variant).getZ();
        int shaftPortalZ = destinationZ
                - IntegratedNervMapBuilder.SHAFT_OUTER_RADIUS;
        for (int z = bed.getZ() + HALF_DEPTH + 1; z <= destinationZ; z++)
        {
            for (int x = -CORRIDOR_HALF_WIDTH; x <= CORRIDOR_HALF_WIDTH; x++)
            {
                BlockPos floor = new BlockPos(bed.getX() + x, bed.getY(), z);
                set(level, floor, transportFloor(level, floor, origin, variant));
                // Inside the audited launch column, extend only the carrier
                // rail. A tunnel roof here used to cap all three shafts.
                if (z > shaftPortalZ)
                {
                    continue;
                }
                for (int y = 1; y <= 68; y++)
                {
                    BlockPos position = floor.above(y);
                    boolean wall = Math.abs(x) == CORRIDOR_HALF_WIDTH
                            || y == 68;
                    if (wall)
                    {
                        set(level, position, y == 68
                                && Math.floorMod(z, 8) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
                    }
                    else
                    {
                        clear(level, position);
                    }
                }
            }
        }
    }

    /**
     * Clears the complete moving airframe envelope immediately before either
     * horizontal transfer. This removes single legacy gate, bridge or ceiling
     * cells left by older map revisions without touching the pressure walls or
     * carrier floor.
     */
    public static void clearTransferEnvelope(ServerLevel level,
                                             BlockPos origin, int variant)
    {
        requireVariant(variant);
        BlockPos bed = hangarBed(origin, variant);
        BlockPos silo = IntegratedNervMapBuilder.lowerLiftBed(origin, variant);
        int shaftPortalZ = silo.getZ()
                - IntegratedNervMapBuilder.SHAFT_OUTER_RADIUS;
        int minimumZ = bed.getZ() - CARRIER_HALF;
        int maximumZ = silo.getZ() + CARRIER_HALF;
        for (int z = minimumZ; z <= maximumZ; z++)
        {
            int halfWidth = z <= shaftPortalZ
                    ? CORRIDOR_HALF_WIDTH - 1
                    : IntegratedNervMapBuilder.SHAFT_CLEAR_RADIUS;
            for (int x = -halfWidth; x <= halfWidth; x++)
            {
                for (int y = 1; y <= 66; y++)
                {
                    clear(level, new BlockPos(
                            bed.getX() + x, bed.getY() + y, z));
                }
            }
        }
    }

    private static void buildObservationGallery(ServerLevel level, BlockPos origin)
    {
        if (relocatedObservationInstalled(level, origin))
        {
            return;
        }
        int minX = IntegratedNervMapBuilder.LIFT_X[0] - HALF_WIDTH
                - GALLERY_SIDE_MARGIN;
        int maxX = IntegratedNervMapBuilder.LIFT_X[2] + HALF_WIDTH
                + GALLERY_SIDE_MARGIN;
        int minZ = GALLERY_Z - 7;
        int maxZ = GALLERY_Z + 8;
        for (int x = minX; x <= maxX; x++)
        {
            for (int z = minZ; z <= maxZ; z++)
            {
                set(level, origin.offset(x, GALLERY_Y, z),
                        Math.floorMod(x + z, 9) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                set(level, origin.offset(x, OBSERVATION_CEILING_Y, z),
                        Math.floorMod(x - z, 11) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
                for (int y = GALLERY_Y + 1;
                     y < OBSERVATION_CEILING_Y; y++)
                {
                    boolean boundary = x == minX || x == maxX
                            || z == minZ || z == maxZ;
                    BlockPos position = origin.offset(x, y, z);
                    if (!boundary)
                    {
                        clear(level, position);
                    }
                    else if (z == maxZ && y <= GALLERY_Y + 6)
                    {
                        set(level, position,
                                Blocks.GRAY_STAINED_GLASS.defaultBlockState());
                    }
                    else
                    {
                        set(level, position,
                                com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
                    }
                }
            }
        }

        BlockState button = Blocks.STONE_BUTTON.defaultBlockState()
                .setValue(ButtonBlock.FACE, AttachFace.FLOOR)
                .setValue(ButtonBlock.FACING, Direction.NORTH);
        for (int variant = 0; variant < 3; variant++)
        {
            BlockState accent = accent(variant);
            buildObservationControlRoom(level, origin, variant, accent);
            for (boolean prepare : new boolean[] {true, false})
            {
                BlockPos control = controlPosition(origin, variant, prepare);
                set(level, control.below(), prepare ? accent
                        : Blocks.CYAN_CONCRETE.defaultBlockState());
                set(level, control, button);
            }
            BlockPos cancel = cancelControlPosition(origin, variant);
            set(level, cancel.below(), Blocks.RED_CONCRETE.defaultBlockState());
            set(level, cancel, button);
            set(level, origin.offset(IntegratedNervMapBuilder.LIFT_X[variant],
                            OBSERVATION_CEILING_Y, GALLERY_Z),
                    Blocks.BEACON.defaultBlockState());
            buildBoardingConnector(level, origin, variant, accent);
        }

        buildControlRoomBridges(level, origin);
        openShoulderCatwalkDoors(level, origin, maxZ);

        // Two dry ladder towers keep the lower gallery independently usable.
        for (int x : new int[] {minX + 2, maxX - 2})
        {
            for (int y = HANGAR_BED_ABOVE_ORIGIN + 1;
                 y <= GALLERY_Y; y++)
            {
                set(level, origin.offset(x, y, GALLERY_Z - 6),
                        Blocks.LADDER.defaultBlockState()
                                .setValue(LadderBlock.FACING, Direction.SOUTH));
                set(level, origin.offset(x, y, GALLERY_Z - 7),
                        com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
            }
        }
    }

    /** Protects the human-approved S26 rear gallery from legacy regeneration. */
    private static boolean relocatedObservationInstalled(
            ServerLevel level, BlockPos origin)
    {
        if (RegionalFacilityLayout.migrated(level.getServer()))
        {
            return true;
        }
        BlockState floor = level.getBlockState(origin.offset(-43, 73, -107));
        BlockState window = level.getBlockState(origin.offset(-42, 74, -109));
        return (floor.is(Blocks.POLISHED_DEEPSLATE)
                || floor.is(Blocks.SEA_LANTERN))
                && window.is(com.projectseele.registry.ModBlocks
                        .CLEAR_GLASS.get());
    }

    /**
     * Six pressure-door openings join the gallery to both shoulder catwalks.
     * The former unbroken front glass occupied the pilot's head cells at the
     * exact start of every catwalk, so all three otherwise complete boarding
     * routes failed at the same Z coordinate.
     */
    private static void openShoulderCatwalkDoors(ServerLevel level,
                                                  BlockPos origin,
                                                  int galleryFrontZ)
    {
        for (int variant = 0; variant < 3; variant++)
        {
            int centreX = IntegratedNervMapBuilder.LIFT_X[variant];
            for (int side : new int[] {-1, 1})
            {
                int firstX = centreX + side * SIDE_CATWALK_X;
                int secondX = centreX
                        + side * (SIDE_CATWALK_X - 3);
                for (int x = Math.min(firstX, secondX);
                     x <= Math.max(firstX, secondX); x++)
                {
                    for (int y = GALLERY_Y + 1;
                         y <= GALLERY_Y + 5; y++)
                    {
                        clear(level, origin.offset(x, y, galleryFrontZ));
                    }
                }
            }
        }
    }

    /**
     * Reopens the walkable concourse across the observation gallery.
     *
     * <p>Each climbing transit ramp lays a walled corridor north-south straight
     * through the gallery at walking height, which fenced the shared floor into
     * isolated segments. Called at the end of {@code linkHangars} — after those
     * ramps are (re)built by both initial setup and every login repair — this
     * relays a flush floor and clears head height across the gallery's interior
     * width, leaving one continuous east-west walk past all three cages. The
     * booth ladders (z &lt;= GALLERY_Z-5) and the raised booths (y &gt;=
     * OBSERVATION_FLOOR_Y) sit outside the swept band and are untouched.
     */
    public static void clearGalleryConcourse(ServerLevel level, BlockPos origin)
    {
        int minX = IntegratedNervMapBuilder.LIFT_X[0] - HALF_WIDTH
                - GALLERY_SIDE_MARGIN + 1;
        int maxX = IntegratedNervMapBuilder.LIFT_X[2] + HALF_WIDTH
                + GALLERY_SIDE_MARGIN - 1;
        for (int x = minX; x <= maxX; x++)
        {
            for (int z = GALLERY_Z - 4; z <= GALLERY_Z; z++)
            {
                set(level, origin.offset(x, GALLERY_Y, z),
                        Math.floorMod(x + z, 9) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                for (int y = GALLERY_Y + 1; y <= GALLERY_Y + 4; y++)
                {
                    clear(level, origin.offset(x, y, z));
                }
            }
        }
    }

    /**
     * Joins the three second-floor control rooms into one walkable level.
     *
     * <p>Each room is otherwise an isolated glass box, so an operator on the
     * upper floor could not cross from one cage to the next. This lays a floor
     * across the two gaps between rooms and cuts the doorways through their
     * facing walls. It works only in the gap x-ranges (-19..-9 and 9..19),
     * which contain none of the audited lift/glass/beacon sample points, so it
     * cannot flip the hangar audit the way the removed gantry stair did.
     */
    private static void buildControlRoomBridges(ServerLevel level, BlockPos origin)
    {
        BlockState floor = Blocks.POLISHED_DEEPSLATE.defaultBlockState();
        BlockState light = Blocks.SEA_LANTERN.defaultBlockState();
        int minZ = GALLERY_Z - 4;
        int maxZ = GALLERY_Z + 4;
        for (int gap = 0; gap < 2; gap++)
        {
            int leftRoomMaxX = IntegratedNervMapBuilder.LIFT_X[gap]
                    + CONTROL_ROOM_HALF_WIDTH;
            int rightRoomMinX = IntegratedNervMapBuilder.LIFT_X[gap + 1]
                    - CONTROL_ROOM_HALF_WIDTH;
            for (int x = leftRoomMaxX; x <= rightRoomMinX; x++)
            {
                for (int z = minZ; z <= maxZ; z++)
                {
                    set(level, origin.offset(x, OBSERVATION_FLOOR_Y, z),
                            Math.floorMod(x + z, 7) == 0 ? light : floor);
                    // Clearing the walls' cells here is what cuts the doorways
                    // through the two rooms and opens the walkway between them.
                    for (int y = OBSERVATION_FLOOR_Y + 1;
                         y < OBSERVATION_CEILING_Y; y++)
                    {
                        clear(level, origin.offset(x, y, z));
                    }
                }
                // Rail the north and south edges of the new span so nobody
                // walks off into the cage below.
                set(level, origin.offset(x, OBSERVATION_FLOOR_Y + 1, minZ - 1),
                        Blocks.IRON_BARS.defaultBlockState());
                set(level, origin.offset(x, OBSERVATION_FLOOR_Y + 1, maxZ + 1),
                        Blocks.IRON_BARS.defaultBlockState());
            }
        }
    }

    private static void buildObservationControlRoom(ServerLevel level,
                                                     BlockPos origin,
                                                     int variant,
                                                     BlockState accent)
    {
        int centreX = IntegratedNervMapBuilder.LIFT_X[variant];
        int minX = centreX - CONTROL_ROOM_HALF_WIDTH;
        int maxX = centreX + CONTROL_ROOM_HALF_WIDTH;
        int minZ = GALLERY_Z - 6;
        int maxZ = GALLERY_Z + 8;
        for (int x = minX; x <= maxX; x++)
        {
            for (int z = minZ; z <= maxZ; z++)
            {
                set(level, origin.offset(x, OBSERVATION_FLOOR_Y, z),
                        Math.floorMod(x + z, 7) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                for (int y = OBSERVATION_FLOOR_Y + 1;
                     y < OBSERVATION_CEILING_Y; y++)
                {
                    boolean side = x == minX || x == maxX || z == minZ;
                    BlockPos position = origin.offset(x, y, z);
                    if (z == maxZ)
                    {
                        set(level, position,
                                Blocks.GRAY_STAINED_GLASS.defaultBlockState());
                    }
                    else if (side)
                    {
                        set(level, position,
                                Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState());
                    }
                    else
                    {
                        clear(level, position);
                    }
                }
            }
        }

        // A protected internal ladder rises from the bridge gallery into the
        // glass control booth directly above it.
        int ladderX = centreX + 7;
        for (int y = GALLERY_Y + 1; y <= OBSERVATION_FLOOR_Y; y++)
        {
            set(level, origin.offset(ladderX, y, GALLERY_Z - 5),
                    Blocks.LADDER.defaultBlockState()
                            .setValue(LadderBlock.FACING, Direction.SOUTH));
            set(level, origin.offset(ladderX, y, GALLERY_Z - 6),
                    com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
        }
        for (int x = centreX - 5; x <= centreX + 5; x++)
        {
            set(level, origin.offset(x, OBSERVATION_FLOOR_Y + 1,
                            GALLERY_Z + 6),
                    Math.floorMod(x, 4) == 0
                            ? Blocks.SEA_LANTERN.defaultBlockState() : accent);
        }
    }

    /**
     * Draws the visible suspension and, optionally, the telescoping crane arm at
     * the capsule's live position.
     *
     * <p>Only the cells that change are touched: the previous frame's crane is
     * remembered per cage, so carrying the plug costs a handful of block writes
     * instead of a sweep of the whole rail corridor every tick — that sweep, run
     * three times a tick, is what pushed the server seconds behind.
     *
     * @param plugY world Y of the capsule. There is no negative sentinel here:
     *              the GeoFront hangar sits at Y=-443, so an earlier
     *              {@code plugY < 0} "stowed" test was always true and neither
     *              the cables nor the arm were ever drawn at all. Use
     *              {@link #stowPlugCrane} to retract.
     */
    public static void setPlugCrane(ServerLevel level, BlockPos origin,
                                     int variant, double plugY, double plugZ,
                                     boolean withArm)
    {
        requireVariant(variant);
        BlockPos bed = hangarBed(origin, variant);
        int railY = craneRailAboveBed();
        int plugRelativeY = Mth.clamp((int) Math.floor(plugY - bed.getY()),
                1, railY - 1);
        int plugRelativeZ = Double.isNaN(plugZ) ? REAR_BOARDING_Z_FROM_BED
                : Mth.clamp(Mth.floor(plugZ) - bed.getZ(),
                        -HALF_DEPTH + 2, REAR_GANTRY_Z_FROM_BED);
        Map<BlockPos, BlockState> wanted = craneFrame(bed, railY,
                plugRelativeY, plugRelativeZ, variant);
        applyCrane(level, origin, variant, wanted);
    }

    /** Retracts the crane against the ceiling, leaving the deck and lane clear. */
    public static void stowPlugCrane(ServerLevel level, BlockPos origin,
                                      int variant)
    {
        requireVariant(variant);
        BlockPos bed = hangarBed(origin, variant);
        int railY = craneRailAboveBed();
        Set<BlockPos> live = CRANE_CELLS.get(variant);
        if (live == null)
        {
            live = sweepStaleCrane(level, origin, variant);
            CRANE_CELLS.put(variant, live);
        }
        int relativeZ = REAR_GANTRY_Z_FROM_BED;
        int bottomY = railY - 2;
        if (!live.isEmpty())
        {
            int minimumWorldY = live.stream().mapToInt(BlockPos::getY)
                    .min().orElse(bed.getY() + railY - 2);
            bottomY = Mth.clamp(minimumWorldY - bed.getY() + 2,
                    1, railY - 2);
            double averageZ = live.stream()
                    .filter(position -> position.getY() == minimumWorldY)
                    .mapToInt(BlockPos::getZ).average()
                    .orElse(bed.getZ() + REAR_GANTRY_Z_FROM_BED);
            relativeZ = Mth.clamp((int) Math.round(averageZ) - bed.getZ(),
                    -HALF_DEPTH + 2, REAR_GANTRY_Z_FROM_BED);
        }
        Map<BlockPos, BlockState> wanted = craneFrame(bed, railY,
                bottomY, relativeZ, variant);
        if (live != null && live.equals(wanted.keySet()))
        {
            return;
        }
        applyCrane(level, origin, variant, wanted);
    }

    /**
     * Removes only the persisted moving crane palette from its measured
     * shaft. S20 now renders this mechanism as a transient entity, so old
     * polished-deepslate yokes must be retired once instead of being painted
     * back into the authoritative map on every motion tick.
     */
    public static int retirePersistedPlugCrane(ServerLevel level,
                                                BlockPos origin,
                                                int variant)
    {
        requireVariant(variant);
        Set<BlockPos> stale = CRANE_CELLS.get(variant);
        if (stale == null)
        {
            stale = sweepPersistedS20Crane(level, origin, variant);
        }
        int removed = 0;
        for (BlockPos position : stale)
        {
            BlockState state = level.getBlockState(position);
            if (isRetiredS20CraneBlock(state))
            {
                clear(level, position);
                removed++;
            }
        }
        CRANE_CELLS.put(variant, new LinkedHashSet<>());
        return removed;
    }

    /**
     * S20 briefly persisted a much larger polished-deepslate crane shell.
     * Polished deepslate is deliberately not part of isCraneHardware(): that
     * broad predicate is also used by route-clearance checks, where treating
     * authored floors as movable hardware would be unsafe. The retired S20
     * crane has an exact, measured shaft, however, and the approved pre-crane
     * R28 snapshot contains zero polished-deepslate cells in all three such
     * shafts. Reclaim that legacy girder only inside this bounded owner volume.
     */
    private static Set<BlockPos> sweepPersistedS20Crane(
            ServerLevel level, BlockPos origin, int variant)
    {
        BlockPos bed = hangarBed(origin, variant);
        Set<BlockPos> found = sweepStaleCrane(level, origin, variant);
        for (int x = -6; x <= 6; x++)
        {
            for (int y = REAR_GANTRY_ABOVE_BED - 3;
                 y <= CHAMBER_HEIGHT - 1; y++)
            {
                for (int z = -1; z <= REAR_GANTRY_Z_FROM_BED + 1; z++)
                {
                    BlockPos position = bed.offset(x, y, z);
                    if (isRetiredS20CraneBlock(
                            level.getBlockState(position)))
                    {
                        found.add(position);
                    }
                }
            }
        }
        return found;
    }

    private static boolean isRetiredS20CraneBlock(BlockState state)
    {
        return isCraneHardware(state)
                || state.is(Blocks.POLISHED_DEEPSLATE)
                || state.is(Blocks.CUT_COPPER)
                || state.is(Blocks.EXPOSED_CUT_COPPER)
                || state.is(Blocks.WEATHERED_CUT_COPPER)
                || state.is(Blocks.OXIDIZED_CUT_COPPER)
                || state.is(Blocks.WAXED_CUT_COPPER)
                || state.is(Blocks.WAXED_EXPOSED_CUT_COPPER)
                || state.is(Blocks.WAXED_WEATHERED_CUT_COPPER)
                || state.is(Blocks.WAXED_OXIDIZED_CUT_COPPER);
    }

    /** One coherent vanilla-material bridge trolley and suspended spreader. */
    private static Map<BlockPos, BlockState> craneFrame(
            BlockPos bed, int railY, int bottomY, int relativeZ, int variant)
    {
        Map<BlockPos, BlockState> wanted = new LinkedHashMap<>();
        BlockState accent = switch (variant)
        {
            case 0 -> Blocks.ORANGE_CONCRETE.defaultBlockState();
            case 2 -> Blocks.RED_CONCRETE.defaultBlockState();
            default -> Blocks.PURPLE_CONCRETE.defaultBlockState();
        };
        BlockState girder = Blocks.POLISHED_DEEPSLATE.defaultBlockState();
        BlockState casing = Blocks.COPPER_BLOCK.defaultBlockState();
        BlockState brass = Blocks.CUT_COPPER.defaultBlockState();
        BlockState carriage = Blocks.POLISHED_BLACKSTONE.defaultBlockState();
        BlockState pulley = Blocks.PISTON.defaultBlockState()
                .setValue(net.minecraft.world.level.block.piston.PistonBaseBlock.FACING,
                        Direction.DOWN);
        BlockState magnet = Blocks.EXPOSED_COPPER.defaultBlockState();

        for (int dz : new int[] {-1, 1})
        {
            for (int x = -6; x <= 6; x++)
            {
                wanted.put(bed.offset(x, railY, relativeZ + dz), girder);
            }
        }
        for (int x : new int[] {-6, 6})
        {
            for (int dz = -1; dz <= 1; dz++)
            {
                wanted.put(bed.offset(x, railY, relativeZ + dz), girder);
            }
        }
        wanted.put(bed.offset(0, railY, relativeZ), carriage);
        for (int x = -4; x <= 4; x++)
        {
            wanted.put(bed.offset(x, railY - 1, relativeZ),
                    Math.abs(x) == 3 ? pulley : girder);
        }
        for (int x : new int[] {-3, 3})
        {
            for (int y = bottomY + 2; y < railY - 1; y++)
            {
                wanted.put(bed.offset(x, y, relativeZ),
                        Blocks.CHAIN.defaultBlockState());
            }
            wanted.put(bed.offset(x, bottomY + 1, relativeZ), magnet);
        }
        for (int dz : new int[] {-1, 1})
        {
            for (int x = -4; x <= 4; x++)
            {
                wanted.put(bed.offset(x, bottomY, relativeZ + dz), girder);
            }
        }
        for (int x : new int[] {-4, 4})
        {
            for (int dz = -1; dz <= 1; dz++)
            {
                wanted.put(bed.offset(x, bottomY, relativeZ + dz), girder);
            }
        }
        for (int x = -2; x <= 2; x++)
        {
            wanted.put(bed.offset(x, bottomY, relativeZ),
                    x == 0 ? accent : Math.abs(x) == 1 ? brass : casing);
        }
        return wanted;
    }

    private static void applyCrane(ServerLevel level, BlockPos origin,
                                    int variant,
                                    Map<BlockPos, BlockState> wanted)
    {
        /*
         * During this process, mutate only cells recorded in CRANE_CELLS.
         * After a server restart that ownership table is empty while its
         * blocks remain persisted, so first use performs one tightly bounded
         * palette-and-geometry reclaim below instead of a room-wide scan.
         */
        Set<BlockPos> previous = CRANE_CELLS.get(variant);
        if (previous == null)
        {
            /*
             * Dynamic crane cells persist in the save, while CRANE_CELLS does
             * not survive an integrated/dedicated-server restart.  Starting
             * with an empty set therefore stacked a new yoke beside every old
             * one and the orphan hardware subsequently failed the plug-route
             * interlock.  Reclaim only the crane's measured central shaft on
             * first use; static rails are iron/accent/beacon and are excluded
             * by both the palette and the vertical bound below.
             */
            previous = sweepStaleCrane(level, origin, variant);
        }
        for (BlockPos stale : previous)
        {
            if (!wanted.containsKey(stale)
                    && isCraneHardware(level.getBlockState(stale)))
            {
                clear(level, stale);
            }
        }
        for (Map.Entry<BlockPos, BlockState> cell : wanted.entrySet())
        {
            BlockState current = level.getBlockState(cell.getKey());
            // Never displace real structure; the crane threads air only.
            if (current.isAir() || isCraneHardware(current))
            {
                set(level, cell.getKey(), cell.getValue());
            }
        }
        CRANE_CELLS.put(variant, new LinkedHashSet<>(wanted.keySet()));
    }

    /** Exact cells owned by the live plug crane in this server session. */
    public static boolean isActivePlugCraneCell(int variant,
                                                BlockPos position)
    {
        Set<BlockPos> cells = CRANE_CELLS.get(variant);
        return cells != null && cells.contains(position);
    }

    /**
     * Pure geometry form of the moving-crane ownership test. Process-local
     * CRANE_CELLS disappears on reload, but the persisted yoke is still the
     * mechanism carrying the plug and must not collide with its own capsule.
     */
    public static boolean isPlugCraneCell(BlockPos origin, int variant,
                                          double craneEyeY,
                                          double craneEyeZ,
                                          BlockPos position)
    {
        BlockPos bed = hangarBed(origin, variant);
        int railY = craneRailAboveBed();
        int plugY = Mth.clamp(Mth.floor(craneEyeY - bed.getY()),
                1, railY - 1);
        int plugZ = Mth.clamp(Mth.floor(craneEyeZ) - bed.getZ(),
                -HALF_DEPTH + 2, REAR_GANTRY_Z_FROM_BED);
        int dx = position.getX() - bed.getX();
        int dy = position.getY() - bed.getY();
        int dz = position.getZ() - bed.getZ();
        int localZ = dz - plugZ;
        if (Math.abs(localZ) > 1)
        {
            return false;
        }
        boolean topBridge = dy == railY
                && (Math.abs(localZ) == 1 && Math.abs(dx) <= 6
                        || Math.abs(dx) == 6 && Math.abs(localZ) <= 1
                        || dx == 0 && localZ == 0);
        boolean topCrosshead = dy == railY - 1
                && localZ == 0 && Math.abs(dx) <= 4;
        boolean suspension = localZ == 0 && Math.abs(dx) == 3
                && dy > plugY && dy < railY - 1;
        boolean lowerFrame = dy == plugY
                && (Math.abs(localZ) == 1 && Math.abs(dx) <= 4
                        || Math.abs(dx) == 4 && Math.abs(localZ) <= 1
                        || localZ == 0 && Math.abs(dx) <= 2);
        return topBridge || topCrosshead || suspension || lowerFrame;
    }

    /**
     * One bounded corridor pass the first time a cage is driven this session, so
     * crane parts left in the world by an earlier run are collected before the
     * incremental tracking takes over.
     */
    private static Set<BlockPos> sweepStaleCrane(ServerLevel level,
                                                  BlockPos origin, int variant)
    {
        BlockPos bed = hangarBed(origin, variant);
        Set<BlockPos> found = new LinkedHashSet<>();
        for (int x = -6; x <= 6; x++)
        {
            /*
             * All authored capsule yokes travel between the dorsal boarding
             * deck and the ceiling rail.  Restricting recovery to that band
             * prevents similarly-coloured civil structure lower in the cage
             * from ever being classified as moving hardware.
             */
            for (int y = REAR_GANTRY_ABOVE_BED - 3;
                 y <= CHAMBER_HEIGHT - 1; y++)
            {
                for (int z = -1; z <= REAR_GANTRY_Z_FROM_BED + 1; z++)
                {
                    BlockPos position = bed.offset(x, y, z);
                    if (isCraneHardware(level.getBlockState(position)))
                    {
                        found.add(position);
                    }
                }
            }
        }
        return found;
    }

    private static void buildPlugCraneRig(ServerLevel level, BlockPos bed,
                                          BlockState accent)
    {
        // The rail has to cover the whole travel of the plug, from where it
        // hangs behind the airframe to the dorsal socket just above the bed.
        int railY = CHAMBER_HEIGHT - 1;
        for (int z = 0; z <= REAR_GANTRY_Z_FROM_BED - 1; z++)
        {
            set(level, bed.offset(-4, railY, z),
                    Blocks.IRON_BLOCK.defaultBlockState());
            set(level, bed.offset(4, railY, z),
                    Blocks.IRON_BLOCK.defaultBlockState());
            if (Math.floorMod(z, 4) == 0)
            {
                set(level, bed.offset(0, railY, z), accent);
            }
        }
        for (int x = -4; x <= 4; x++)
        {
            set(level, bed.offset(x, railY,
                            REAR_BOARDING_Z_FROM_BED),
                    x == 0 ? Blocks.BEACON.defaultBlockState()
                            : Blocks.IRON_BLOCK.defaultBlockState());
        }
    }

    /**
     * Opens the gallery into both shoulder catwalks. The pilot route runs down
     * a side of the cage and up to the dorsal gantry; it deliberately does not
     * cross in front of the airframe, whose face is what the gallery glass is
     * there to look at.
     */
    private static void buildBoardingConnector(ServerLevel level, BlockPos origin,
                                               int variant, BlockState accent)
    {
        BlockPos bed = hangarBed(origin, variant);
        int floorY = bed.getY() + CATWALK_FLOOR_ABOVE_BED;
        int galleryStartZ = origin.getZ() + GALLERY_Z + 4;
        int doorwayZ = origin.getZ() + HANGAR_CENTRE_Z - HALF_DEPTH;
        int catwalkStartZ = bed.getZ() + FRONT_CROSS_Z_FROM_BED;

        for (int side : new int[] {-1, 1})
        {
            for (int offset = SIDE_CATWALK_X - 1; offset <= SIDE_CATWALK_X; offset++)
            {
                int x = bed.getX() + side * offset;
                for (int z = Math.min(galleryStartZ, catwalkStartZ);
                     z <= Math.max(galleryStartZ, catwalkStartZ); z++)
                {
                    BlockPos floor = new BlockPos(x, floorY, z);
                    setCrewBearingR44(level, bed, floor, personnelDeck(level,accent,Math.floorMod(x+z,5)==0));
                    for (int y = 1; y <= 4; y++)
                    {
                        if (!preservedCrewInfrastructureR44(level, bed, floor.above(y)))
                            clear(level, floor.above(y));
                    }
                }
            }
            // Frame the cut through the shared gallery/cage wall so the
            // opening reads as a pressure door rather than a hole.
            int outer = bed.getX() + side * (SIDE_CATWALK_X + 1);
            int inner = bed.getX() + side * (SIDE_CATWALK_X - 2);
            for (int y = 1; y <= 5; y++)
            {
                setCrewBearingR44(level, bed, new BlockPos(outer, floorY + y, doorwayZ),
                        Blocks.IRON_BLOCK.defaultBlockState());
                // The source doorway's upper frame hangs from its outer
                // post/lintel; its old low inner jamb cut across the first
                // of the three actual front circulation rows.
                if (y > 2)
                    setCrewBearingR44(level, bed, new BlockPos(inner, floorY + y, doorwayZ),
                            Blocks.IRON_BLOCK.defaultBlockState());
            }
            for (int offset = SIDE_CATWALK_X - 2; offset <= SIDE_CATWALK_X + 1; offset++)
            {
                setCrewBearingR44(level, bed, new BlockPos(bed.getX() + side * offset,
                                floorY + 5, doorwayZ),
                        offset == SIDE_CATWALK_X
                                ? Blocks.SEA_LANTERN.defaultBlockState() : accent);
            }
        }
        setBoardingBridgeExtension(level, origin, variant, BRIDGE_SEGMENTS);
    }

    /**
     * Discrete split-panel bridge across the dorsal exit lane. Zero leaves the
     * lane completely clear with both halves parked in their side pockets;
     * {@link #BRIDGE_SEGMENTS} reaches the suspended entry plug. The lane is
     * the same volume the airframe sweeps on its way to the transport gate,
     * so this must be at zero before any transfer starts.
     */
    public static void setBoardingBridgeExtension(ServerLevel level,
                                                   BlockPos origin,
                                                   int variant,
                                                   int extension)
    {
        requireVariant(variant);
        int safeExtension = Math.max(0, Math.min(BRIDGE_SEGMENTS, extension));
        BlockPos bed = hangarBed(origin, variant);
        if(EntryPlugBridgeLayoutR48.enabled(level))
        {
            EntryPlugBridgeLayoutR48.apply(level,bed,safeExtension);
            return;
        }
        BlockState accent = accent(variant);
        int floorY = bed.getY() + REAR_GANTRY_ABOVE_BED;
        for (int segment = 1; segment <= BRIDGE_SEGMENTS; segment++)
        {
            // Segment one is the panel nearest the gantry; the bridge grows
            // forward, toward the plug and the airframe's back.
            int z = bed.getZ() + REAR_GANTRY_Z_FROM_BED - segment;
            boolean extended = segment <= safeExtension;
            for (int x = -SIDE_CATWALK_X; x <= SIDE_CATWALK_X; x++)
            {
                boolean lane = Math.abs(x) <= EXIT_LANE_HALF_WIDTH;
                boolean pocket = Math.abs(x) > EXIT_LANE_HALF_WIDTH
                        && Math.abs(x) <= SIDE_CATWALK_X - 1;
                if (!lane && !pocket)
                {
                    continue;
                }
                BlockPos floor = new BlockPos(bed.getX() + x, floorY, z);
                if (extended && lane)
                {
                    // The final panel splits around the vertical capsule.
                    boolean capsuleWell = segment >= BRIDGE_SEGMENTS - 1
                            && Math.abs(x) <= 2;
                    if (capsuleWell)
                    {
                        clear(level, floor);
                    }
                    else
                    {
                        set(level, floor, personnelDeck(level,accent,Math.floorMod(x+z,5)==0));
                    }
                }
                else if (lane)
                {
                    // Retracted: the lane must be genuinely empty, because the
                    // airframe passes through here.
                    clear(level, floor);
                }
                for (int y = 1; y <= 4; y++)
                {
                    // Leave the crane's own cables and arm standing: this sweep
                    // runs on every login and every retraction step, and it was
                    // deleting the lower half of the suspension and the whole
                    // visible arm the moment they were drawn.
                    BlockPos cell=floor.above(y);
                    if(level.getBlockState(cell).is(ModBlocks.NERV_EDGE_RAIL.get()))set(level,cell,Blocks.AIR.defaultBlockState());
                    else clearExceptCrane(level,cell);
                }
            }
            // Retire the old full-column barriers; the new boundary rails are
            // rebuilt after the complete split deck reaches its next step.
            for (int x : new int[] {
                    -EXIT_LANE_HALF_WIDTH, EXIT_LANE_HALF_WIDTH})
            {
                clear(level, new BlockPos(bed.getX() + x, floorY + 1, z));
            }
        }
        refreshBoardingEdgeRails(level,bed);
    }
    private static void refreshBoardingEdgeRails(ServerLevel level,BlockPos bed)
    {
        int floorY=bed.getY()+REAR_GANTRY_ABOVE_BED;
        for(int x=-SIDE_CATWALK_X;x<=SIDE_CATWALK_X;x++)
            for(int z=REAR_BOARDING_Z_FROM_BED;z<REAR_GANTRY_Z_FROM_BED;z++)
            {
                BlockPos floor=new BlockPos(bed.getX()+x,floorY,bed.getZ()+z);
                if(!level.getBlockState(floor).isFaceSturdy(level,floor,Direction.UP))continue;
                BlockPos at=floor.above();BlockState before=level.getBlockState(at);
                if(!before.isAir()&&!before.is(ModBlocks.NERV_EDGE_RAIL.get())&&!before.is(Blocks.LIGHT))continue;
                BlockState rail=FacilityEdgeRailR41.empty(ModBlocks.NERV_EDGE_RAIL.get());boolean edge=false;
                for(Direction side:Direction.Plane.HORIZONTAL)
                {
                    BlockPos adjacent=floor.relative(side);
                    if(!level.getBlockState(adjacent).isFaceSturdy(level,adjacent,Direction.UP))
                    {rail=rail.setValue(FacilityEdgeRailR41.side(side),true);edge=true;}
                }
                if(edge)set(level,at,rail);
                else if(before.is(ModBlocks.NERV_EDGE_RAIL.get()))set(level,at,Blocks.AIR.defaultBlockState());
            }
    }
    private static boolean isBoardingRouteWalkable(ServerLevel level,
                                                    BlockPos origin,
                                                    int variant)
    {
        return boardingRouteFailure(level, origin, variant) == null;
    }

    private static String boardingRouteFailure(ServerLevel level,
                                                BlockPos origin,
                                                int variant)
    {
        BlockPos bed = hangarBed(origin, variant);
        int catwalkY = bed.getY() + CATWALK_FLOOR_ABOVE_BED;
        if (catwalkY != origin.getY() + GALLERY_Y)
        {
            return "floor-level expected=" + (origin.getY() + GALLERY_Y)
                    + " actual=" + catwalkY;
        }
        // The socket is the ground truth for which side is the back. Deriving
        // it here instead of asserting a sign keeps this gate honest if the
        // parked heading ever changes again.
        int socketZ = (int) Math.round(EntryPlugDirector.socketZOffset());
        if (Integer.signum(REAR_BOARDING_Z_FROM_BED) != Integer.signum(socketZ))
        {
            return "boarding-side-opposite-socket boarding="
                    + REAR_BOARDING_Z_FROM_BED + " socket=" + socketZ;
        }

        int galleryStartZ = origin.getZ() + GALLERY_Z + 4;
        int catwalkStartZ = bed.getZ() + FRONT_CROSS_Z_FROM_BED;
        int gantryZ = bed.getZ() + REAR_GANTRY_Z_FROM_BED;
        int boardingEndZ = bed.getZ() + REAR_BOARDING_Z_FROM_BED;

        // Leg 1: gallery out along both shoulder catwalks to the rear ladders.
        for (int side : new int[] {-1, 1})
        {
            int x = bed.getX() + side * SIDE_CATWALK_X;
            for (int z = galleryStartZ; z <= gantryZ - 1; z++)
            {
                String failure = walkable(level, new BlockPos(x, catwalkY, z));
                if (failure != null)
                {
                    return "catwalk " + failure;
                }
            }
            // Leg 2: the ladder shaft up to the dorsal gantry.
            for (int y = catwalkY + 1;
                 y <= bed.getY() + REAR_GANTRY_ABOVE_BED; y++)
            {
                BlockPos rung = new BlockPos(x, y, gantryZ);
                if (!level.getBlockState(rung).is(Blocks.LADDER))
                {
                    return "ladder " + rung.toShortString() + "="
                            + level.getBlockState(rung).getBlock()
                                    .getDescriptionId();
                }
            }
        }

        // Leg 3: the gantry decks and the extended split bridge to the plug.
        int gantryY = bed.getY() + REAR_GANTRY_ABOVE_BED;
        for (int z = boardingEndZ; z <= gantryZ - 1; z++)
        {
            for (int side : new int[] {-1, 1})
            {
                String failure = walkable(level, new BlockPos(
                        bed.getX() + side * (EXIT_LANE_HALF_WIDTH + 1),
                        gantryY, z));
                if (failure != null)
                {
                    return "gantry " + failure;
                }
            }
            if(EntryPlugBridgeLayoutR48.enabled(level)&&z>bed.getZ()+21)continue;
            int centreOffset = z <= boardingEndZ + (EntryPlugBridgeLayoutR48.enabled(level)?2:1) ? 3 : 0;
            String failure = walkable(level,
                    new BlockPos(bed.getX() + centreOffset, gantryY, z));
            if (failure != null)
            {
                return "bridge " + failure;
            }
        }
        return null;
    }

    /** Sturdy floor plus standing headroom, or a description of why not. */
    private static String walkable(ServerLevel level, BlockPos floor)
    {
        BlockState floorState = level.getBlockState(floor);
        if (!floorState.isFaceSturdy(level, floor, Direction.UP))
        {
            return floor.toShortString() + "="
                    + floorState.getBlock().getDescriptionId();
        }
        // Two blocks: what a pilot or a walking dummy actually occupies. The old
        // four-block demand reached into the crane's own airspace, so the plug's
        // cables and arm could fail the route the moment they were drawn and
        // trigger a full hangar rebuild mid-session.
        for (int y = 1; y <= 2; y++)
        {
            BlockPos clearance = floor.above(y);
            BlockState state = level.getBlockState(clearance);
            if (isCraneHardware(state))
            {
                continue;
            }
            var body=new net.minecraft.world.phys.AABB(.2,1,.2,.8,2.8,.8);
            final int height=y;
            if (state.getCollisionShape(level, clearance).toAabbs().stream().anyMatch(box->box.move(0,height,0).intersects(body)))
            {
                return "clearance " + clearance.toShortString() + "="
                        + state.getBlock().getDescriptionId();
            }
        }
        return null;
    }

    /** Moving plug-crane parts, which are expected to cross the deck. */
    private static boolean isCraneHardware(BlockState state)
    {
        return state.is(Blocks.CHAIN) || state.is(Blocks.COPPER_BLOCK)
                || state.is(Blocks.EXPOSED_COPPER)
                || state.is(Blocks.WEATHERED_COPPER)
                || state.is(Blocks.OXIDIZED_COPPER)
                || state.is(Blocks.WAXED_COPPER_BLOCK)
                || state.is(Blocks.WAXED_EXPOSED_COPPER)
                || state.is(Blocks.WAXED_WEATHERED_COPPER)
                || state.is(Blocks.WAXED_OXIDIZED_COPPER)
                || state.is(Blocks.POLISHED_BLACKSTONE)
                || state.is(Blocks.PISTON)
                || state.is(Blocks.LIGHT_GRAY_CONCRETE)
                || state.is(Blocks.ORANGE_CONCRETE)
                || state.is(Blocks.PURPLE_CONCRETE)
                || state.is(Blocks.RED_CONCRETE)
                || PrivateModVisuals.is(state, "create", "metal_girder")
                || PrivateModVisuals.is(state, "create", "andesite_casing")
                || PrivateModVisuals.is(state, "create", "brass_casing")
                || PrivateModVisuals.is(state, "create", "gantry_carriage")
                || PrivateModVisuals.is(state, "create", "rope_pulley")
                || PrivateModVisuals.is(state, "create", "pulley_magnet")
                || PrivateModVisuals.is(state, "create",
                        "piston_extension_pole");
    }

    /**
     * The observation gallery has to be one continuous walk from the EVA-00
     * booth across to the EVA-02 booth. Sampled one row north of the button
     * line so it never lands on a booth ladder shaft or the front glass.
     */
    private static String galleryCrossWalkFailure(ServerLevel level,
                                                   BlockPos origin)
    {
        // Walk the interior span only: x == minX/maxX are the gallery's own
        // perimeter walls, so including them made the check fail on the very
        // first column of an otherwise perfectly connected floor.
        int minX = IntegratedNervMapBuilder.LIFT_X[0] - HALF_WIDTH
                - GALLERY_SIDE_MARGIN + 1;
        int maxX = IntegratedNervMapBuilder.LIFT_X[2] + HALF_WIDTH
                + GALLERY_SIDE_MARGIN - 1;
        for (int x = minX; x <= maxX; x++)
        {
            String failure = walkable(level,
                    origin.offset(x, GALLERY_Y, GALLERY_Z - 3));
            if (failure != null)
            {
                return "gallery-cross " + failure;
            }
        }
        return null;
    }

    private static String boardingRouteDiagnostics(ServerLevel level,
                                                    BlockPos origin)
    {
        StringBuilder result = new StringBuilder();
        for (int variant = 0; variant < 3; variant++)
        {
            String failure = boardingRouteFailure(level, origin, variant);
            if (failure != null)
            {
                if (!result.isEmpty())
                {
                    result.append("; ");
                }
                result.append("EVA-").append(String.format(Locale.ROOT,
                        "%02d", variant)).append(' ').append(failure);
            }
        }
        return result.isEmpty() ? "ok" : result.toString();
    }

    private static BlockState transportFloor(ServerLevel level, BlockPos position, BlockPos origin,
                                             int variant)
    {
        BlockPos hangar = hangarBed(origin, variant);
        BlockPos silo = IntegratedNervMapBuilder.lowerLiftBed(origin, variant);
        if (position.equals(hangar) || position.equals(silo))
        {
            return Blocks.LODESTONE.defaultBlockState();
        }
        int relativeX = position.getX() - hangar.getX();
        if(TvLaunchFacility.enabled(level))
        {
            if(Math.abs(relativeX)==5)return ModBlocks.NERV_MACHINE_EDGE.get().defaultBlockState();
            if(Math.abs(relativeX)<=10&&Math.floorMod(position.getZ()-hangar.getZ(),6)==0)return ModBlocks.NERV_MACHINE_PANEL.get().defaultBlockState();
            return ModBlocks.NERV_FLOOR_PANEL.get().defaultBlockState();
        }
        if (Math.abs(relativeX) == 5)
        {
            // The original black-on-black basalt rails disappeared into the
            // tunnel floor. Keep a bright physical pair under the moving
            // carrier, and let moveCarrier restore the same pattern behind it.
            return Math.floorMod(position.getZ() - hangar.getZ(), 8) == 0
                    ? Blocks.SEA_LANTERN.defaultBlockState()
                    : Blocks.IRON_BLOCK.defaultBlockState();
        }
        if (Math.abs(relativeX) <= 10
                && Math.floorMod(position.getZ() - hangar.getZ(), 6) == 0)
        {
            return Blocks.CUT_COPPER.defaultBlockState();
        }
        if (relativeX == 0)
        {
            return Blocks.POLISHED_BLACKSTONE.defaultBlockState();
        }
        return Blocks.POLISHED_DEEPSLATE.defaultBlockState();
    }

    private static BlockState personnelDeck(ServerLevel level,BlockState accent,boolean marked)
    {
        if(TvLaunchFacility.enabled(level))return (marked?ModBlocks.NERV_MACHINE_EDGE:ModBlocks.NERV_MACHINE_PANEL).get().defaultBlockState();
        if(!RegionalFacilityLayout.migrated(level.getServer()))return marked?accent:Blocks.IRON_BLOCK.defaultBlockState();
        // These decks are maintained on login and during bridge operation;
        // an offline cosmetic patch alone would be overwritten immediately.
        if(!marked)return Blocks.SMOOTH_STONE.defaultBlockState();
        return (accent.is(Blocks.RED_CONCRETE)?Blocks.RED_TERRACOTTA:accent.is(Blocks.ORANGE_CONCRETE)?Blocks.ORANGE_TERRACOTTA:Blocks.PURPLE_TERRACOTTA).defaultBlockState();
    }

    private static BlockState accent(int variant)
    {
        return switch (variant)
        {
            case 0 -> Blocks.ORANGE_CONCRETE.defaultBlockState();
            case 2 -> Blocks.RED_CONCRETE.defaultBlockState();
            default -> Blocks.PURPLE_CONCRETE.defaultBlockState();
        };
    }

    private static void requireVariant(int variant)
    {
        if (variant < 0 || variant > 2)
        {
            throw new IllegalArgumentException(String.format(Locale.ROOT,
                    "EVA hangar variant must be 0, 1 or 2, got %d", variant));
        }
    }

    private static void clear(ServerLevel level, BlockPos position)
    {
        if (!level.getBlockState(position).isAir()&&!level.getBlockState(position).is(ModBlocks.NERV_EDGE_RAIL.get()))
        {
            set(level, position, Blocks.AIR.defaultBlockState());
        }
    }

    /** Clears headroom without dismantling the plug crane that runs through it. */
    private static void clearExceptCrane(ServerLevel level, BlockPos position)
    {
        if (!isCraneHardware(level.getBlockState(position)))
        {
            clear(level, position);
        }
    }

    private static void set(ServerLevel level, BlockPos position, BlockState state)
    {
        if (TvPersonnelPlatformRecipeR44.owns(level, position)) return;
        if (PilotRestroomsR47.ownsRoomMaintenanceSpaceR47(level, position)) return;
        if (!level.getBlockState(position).equals(state))
        {
            level.setBlock(position, state, UPDATE_CLIENTS);
            PerformanceCounters.recordWorldBlockWrites(1);
        }
    }

    public record HangarAudit(boolean valid, int beds, int shells,
                              int controls, int galleries,
                              int observationRooms, int plugRigs,
                              int walkableRoutes, int wideTransportTunnels,
                              boolean galleryLinked)
    {
        public String summary()
        {
            return String.format(Locale.ROOT,
                    "valid=%s beds=%d/3 shells=%d/3 controls=%d/9 "
                            + "galleries=%d/3 observationRooms=%d/3 "
                            + "plugRigs=%d/3 walkableRoutes=%d/3 "
                            + "wideTunnels=%d/3 galleryLinked=%s",
                    this.valid, this.beds, this.shells, this.controls,
                    this.galleries, this.observationRooms, this.plugRigs,
                    this.walkableRoutes, this.wideTransportTunnels,
                    this.galleryLinked);
        }
    }
}
