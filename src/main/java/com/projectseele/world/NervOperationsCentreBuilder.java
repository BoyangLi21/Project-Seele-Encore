package com.projectseele.world;

import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.Set;

import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.LadderBlock;
import net.minecraft.world.level.block.StairBlock;
import net.minecraft.world.level.block.state.BlockState;

/** Original block-built NERV command interior inside the GeoFront pyramid. */
public final class NervOperationsCentreBuilder
{
    public static final int OPERATIONS_FLOOR_Y = 7;
    public static final int OPERATIONS_ENTRY_Z = 18;
    public static final int DISPLAY_Z = -20;

    private static final int UPDATE_CLIENTS = Block.UPDATE_CLIENTS;
    private static final int[] TRANSIT_X = {-28, 0, 28};
    /**
     * The 2x wet cages occupy almost the complete -62..62 frontage. One shared
     * personnel spine therefore leaves the command interchange on centreline,
     * passes around the east shell and enters the common observation gallery.
     */
    private static final int[] HANGAR_ROUTE_LANES = {0};
    private static final int HANGAR_SERVICE_SPINE_X =
            IntegratedNervMapBuilder.LIFT_X[2] + 28;
    private static final int HANGAR_GALLERY_DOOR_X =
            IntegratedNervMapBuilder.LIFT_X[2] + 20;
    private static final int EAST_SHAFT_GAP_X = 21;
    private static final int WEST_SHAFT_GAP_X = -21;
    /**
     * The carrier shaft is centred at z=-76 and its pressure shell reaches
     * seventeen blocks north.  Keep the personnel spine in the x=21 gap
     * through z=-93, then bend east only after the complete shell is behind
     * it.  Starting the bend at -89 put the seven-wide ramp through the
     * EVA-02 clear core at (27,17,-91), so the sortie safety pass correctly
     * erased its floor on every login.
     */
    private static final int SHAFT_NORTH_EDGE_Z = -93;
    private static final int COMMAND_SPINE_X = -21;
    /** First safe pedestrian row south of the 17-block shaft shell. */
    private static final int SOUTH_INTERCHANGE_Z = -58;

    private NervOperationsCentreBuilder() {}

    public static void build(ServerLevel level, BlockPos origin)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        PerformanceCounters.recordBuilderCall();
        boolean localCommand =
                LocalMapAssetLoader.placeCommandModule(level, origin);
        buildLowerConcourse(level, origin);
        if (!localCommand)
        {
            buildOperationsHall(level, origin);
        }
        // The imported-module pressure shell must exist before its inhabited
        // annex cuts the explicit doors and service vestibule through it.
        // Reversing this order let the shell silently refill the finished
        // south access spine with reinforced deepslate.
        buildVideoWall(level, origin, localCommand);
        buildCommandSupportAnnex(level, origin, localCommand);
        buildAccessStairs(level, origin);
        buildLiftTransit(level, origin);
        linkHangars(level, origin);
        sealProceduralRouteSeams(level, origin);
        NervOperationsConsole.install(level, origin);
        NervCommandTelemetry.install(level, origin);
    }

    /**
     * Closes the seams the routing passes cut through the command module.
     *
     * <p>Skipping {@link #buildOperationsHall} when the imported module is
     * present is deliberate — the module supplies a better interior. But the
     * stairwell and the three transit lanes run unconditionally and clear
     * headroom at procedural coordinates that fall inside the module's
     * footprint, so where a route was cut through the module's own floor the
     * walkway is left standing over a void. Only missing support is restored:
     * nothing solid is replaced and no opening is sealed, because from here
     * an open cell is just as likely to be a real doorway of the module as it
     * is to be a hole.
     */
    private static void sealProceduralRouteSeams(ServerLevel level, BlockPos origin)
    {
        for (int laneX : TRANSIT_X)
        {
            for (int z = SOUTH_INTERCHANGE_Z; z <= -28; z++)
            {
                for (int x = -3; x <= 3; x++)
                {
                    supportFloor(level, origin.offset(laneX + x, 1, z));
                }
            }
        }
        for (int step = 0; step <= 5; step++)
        {
            for (int x = -14; x <= -12; x++)
            {
                supportFloor(level, origin.offset(x, 2 + step, 22 - step));
            }
        }
    }

    /** Gives a walkway a floor where the clearing pass removed the module's. */
    private static void supportFloor(ServerLevel level, BlockPos floor)
    {
        BlockPos below = floor.below();
        if (level.getBlockState(below).isAir())
        {
            set(level, below, Blocks.POLISHED_DEEPSLATE.defaultBlockState());
        }
    }

    /**
     * Paints the final, physical interchange after MAGI and Terminal Dogma
     * have opened their own doors. Keeping this pass last prevents either
     * deep-facility builder from hiding the route identity again.
     */
    public static void linkFacilities(ServerLevel level, BlockPos origin)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        BlockState magi = Blocks.PURPLE_CONCRETE.defaultBlockState();
        BlockState terminal = Blocks.RED_CONCRETE.defaultBlockState();

        // West operations-floor route: command centre -> MAGI descent.
        for (int x = -34; x <= -23; x++)
        {
            set(level, origin.offset(x, OPERATIONS_FLOOR_Y, 12), magi);
        }

        // East lower-concourse route: central interchange -> Central Dogma.
        for (int x = 0; x <= 34; x++)
        {
            set(level, origin.offset(x, 1, -23), terminal);
        }

        // A compact three-colour route diagram is set into the existing wall,
        // so it cannot become another freestanding structure inside the shell.
        for (int y = 3; y <= 5; y++)
        {
            for (int x = -30; x <= -12; x++)
            {
                BlockState pixel = x <= -25
                        ? Blocks.PURPLE_STAINED_GLASS.defaultBlockState()
                        : x >= -18
                        ? Blocks.RED_STAINED_GLASS.defaultBlockState()
                        : Blocks.ORANGE_STAINED_GLASS.defaultBlockState();
                set(level, origin.offset(x, y, -17), pixel);
            }
        }
        set(level, origin.offset(-27, 4, -17),
                Blocks.SEA_LANTERN.defaultBlockState());
        set(level, origin.offset(-21, 4, -17),
                Blocks.SEA_LANTERN.defaultBlockState());
        set(level, origin.offset(-15, 4, -17),
                Blocks.SEA_LANTERN.defaultBlockState());
    }

    /**
     * Repairs only the command-room access network used at runtime. This is
     * deliberately bounded: camera shortcuts must never rebuild the 512-block
     * GeoFront sphere merely because an audit chunk was unloaded.
     */
    public static OperationsAudit repairRuntimeAccess(ServerLevel level,
                                                       BlockPos origin)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return inspect(level, origin);
        if (!hasConnectedHangarRoutes(level, origin))
        {
            linkHangars(level, origin);
        }
        if (!level.players().isEmpty())
        {
            NervOperationsConsole.install(level, origin);
        }
        boolean localCommand =
                LocalMapAssetLoader.commandMarkersPresent(level, origin);
        buildVideoWall(level, origin, localCommand);
        // This owns every aperture at the imported module boundary, so it is
        // deliberately the last room builder in the bounded runtime pass.
        buildCommandSupportAnnex(level, origin, localCommand);
        // The imported command module and its sealed support annex both
        // repaint parts of the lower pressure spine. Restore the bounded
        // pedestrian deck after every structural pass so no doorway cleanup
        // can leave a one-block fall at the hangar interchange.
        repairConnectedLowerRoutes(level, origin);
        // Runtime room repair must leave the 31x31 carrier volume as its final
        // writer. Old maps retain a ceiling at z=-61 from the former command
        // corridor; rebuild only the lower hand-off for an affected shaft.
        IntegratedNervMapBuilder.repairLowerSortieInterfaces(level);
        // These three route witnesses are deliberately tiny and do not enter
        // a carrier envelope.  Repaint them after imported-shell, annex and
        // shaft repair so the shared MAGI/Dogma directions cannot be hidden
        // by a later structural owner in the same runtime pass.
        if (!level.players().isEmpty())
        {
            NervCommandTelemetry.install(level, origin);
        }
        linkFacilities(level, origin);
        OperationsAudit audit = inspect(level, origin);
        if (!audit.runtimePhysicalValid())
        {
            ProjectSeele.LOGGER.warn("NERV route diagnostic: {}",
                    routeDiagnostics(level, origin, audit));
        }
        return audit;
    }

    public static OperationsAudit inspect(ServerLevel level, BlockPos origin)
    {
        boolean localCommand =
                LocalMapAssetLoader.commandMarkersPresent(level, origin);
        boolean entrance = localCommand
                || level.getBlockState(origin.offset(0, 7, 34))
                .is(Blocks.ORANGE_CONCRETE);
        boolean tacticalTable = localCommand
                || level.getBlockState(origin.offset(0, 8, 0))
                .is(Blocks.BEACON);
        boolean display = localCommand
                || level.getBlockState(origin.offset(0, 11, DISPLAY_Z))
                .is(Blocks.RED_STAINED_GLASS);
        boolean stairs = level.getBlockState(origin.offset(-13, 2, 22))
                .is(Blocks.SMOOTH_QUARTZ_STAIRS);
        int consoles = localCommand ? 3 : 0;
        if (!localCommand)
        {
            for (int x : new int[] {-10, 0, 10})
            {
                if (level.getBlockState(origin.offset(x, 9, 6))
                        .is(Blocks.COMPARATOR))
                {
                    consoles++;
                }
            }
        }
        int transitLinks = 0;
        for (int x : TRANSIT_X)
        {
            if (!level.getBlockState(origin.offset(x, 1, -50)).isAir()
                    && level.getBlockState(origin.offset(x, 6, -50))
                    .is(Blocks.IRON_BLOCK))
            {
                transitLinks++;
            }
        }
        boolean connectedRoutes = hasConnectedLowerRoutes(level, origin);
        boolean hangarRoutes = hasConnectedHangarRoutes(level, origin);
        boolean facilityLinks =
                level.getBlockState(origin.offset(-30, OPERATIONS_FLOOR_Y, 12))
                        .is(Blocks.PURPLE_CONCRETE)
                        && level.getBlockState(origin.offset(24, 1, -23))
                        .is(Blocks.RED_CONCRETE)
                        && level.getBlockState(origin.offset(-21, 4, -17))
                        .is(Blocks.SEA_LANTERN);
        int telemetryScreens = NervCommandTelemetry.countScreens(level, origin);
        BlockPos videoAnchor = localCommand
                ? origin.offset(0, 17, 58)
                : origin.offset(0, 7, DISPLAY_Z + 1);
        boolean videoWall = level.getBlockState(videoAnchor.offset(0, 4, -1))
                .is(Blocks.BLACK_CONCRETE)
                && level.getBlockState(videoAnchor.offset(-18, 4, -1))
                .is(Blocks.POLISHED_DEEPSLATE);
        boolean safeAnnex = !localCommand
                || level.getBlockState(origin.offset(1, -5, 95))
                .is(Blocks.POLISHED_DEEPSLATE)
                && level.getBlockState(origin.offset(0, -2, 98))
                .is(Blocks.GRAY_STAINED_GLASS)
                && level.getBlockState(origin.offset(-43, 0, 71))
                .is(Blocks.RED_STAINED_GLASS)
                && level.getBlockState(origin.offset(39, -4, 82))
                .is(Blocks.SMOOTH_QUARTZ_SLAB)
                && level.getBlockState(origin.offset(-18, -4, 94)).isAir()
                && level.getBlockState(origin.offset(0, -4, 94)).isAir()
                && level.getBlockState(origin.offset(18, -4, 94)).isAir()
                && level.getBlockState(origin.offset(-18, -5, 94))
                .is(Blocks.ORANGE_CONCRETE)
                && level.getBlockState(origin.offset(18, -5, 94))
                .is(Blocks.RED_CONCRETE)
                && level.getBlockState(origin.offset(-1, -20, -33)).isAir()
                && level.getBlockState(origin.offset(-1, -21, -34))
                .is(Blocks.POLISHED_BLACKSTONE)
                && level.getBlockState(origin.offset(-1, -18, -42)).isAir()
                && level.getBlockState(origin.offset(-3, -18, -42))
                .is(Blocks.ORANGE_CONCRETE)
                && level.getBlockState(origin.offset(24, 20, 70))
                .is(Blocks.DEEPSLATE_BRICKS)
                && level.getBlockState(origin.offset(10, 20, 84))
                .is(Blocks.DEEPSLATE_BRICKS)
                && level.getBlockState(origin.offset(0, 36, 70))
                .is(Blocks.DEEPSLATE_BRICKS)
                && level.getBlockState(origin.offset(0, 8, 84)).isAir()
                && level.getBlockState(origin.offset(0, 7, 87))
                .is(Blocks.POLISHED_DEEPSLATE)
                && level.getBlockState(origin.offset(0, 8, 87)).isAir()
                && level.getBlockState(origin.offset(-30, 20, 40))
                .is(com.projectseele.world.NervMaterials.STRUCTURAL_SHELL)
                && level.getBlockState(origin.offset(30, 20, 40))
                .is(com.projectseele.world.NervMaterials.STRUCTURAL_SHELL)
                && level.getBlockState(origin.offset(20, 58, 40))
                .is(Blocks.DEEPSLATE_TILES)
                && level.getBlockState(origin.offset(0, -22, 40))
                .is(Blocks.POLISHED_DEEPSLATE)
                && level.getBlockState(origin.offset(0, 2, -35)).isAir()
                && hasSafeAnnexRoutes(level, origin);
        NervOperationsConsole.ConsoleAudit commandConsole =
                NervOperationsConsole.inspect(level, origin);
        boolean valid = entrance && tacticalTable && display && stairs
                && consoles == 3 && transitLinks == 3 && connectedRoutes
                && hangarRoutes && facilityLinks && videoWall && safeAnnex
                && telemetryScreens == NervCommandTelemetry.SCREEN_COUNT
                && commandConsole.valid();
        return new OperationsAudit(valid, entrance, tacticalTable, display,
                stairs, consoles, transitLinks, connectedRoutes, hangarRoutes,
                facilityLinks, videoWall, safeAnnex, telemetryScreens,
                commandConsole);
    }

    private static void buildLowerConcourse(ServerLevel level, BlockPos origin)
    {
        BlockState floor = Blocks.POLISHED_BLACKSTONE.defaultBlockState();
        BlockState wall = Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState();
        BlockState accent = Blocks.ORANGE_CONCRETE.defaultBlockState();

        // The southern command bridge enters the pyramid at this nine-block
        // pressure gate and continues through the lower public concourse.
        for (int z = 18; z <= 36; z++)
        {
            for (int x = -5; x <= 5; x++)
            {
                set(level, origin.offset(x, 1, z),
                        x == 0 && z % 4 < 2 ? accent : floor);
                for (int y = 2; y <= 6; y++)
                {
                    set(level, origin.offset(x, y, z), Blocks.AIR.defaultBlockState());
                }
            }
            for (int y = 2; y <= 6; y++)
            {
                set(level, origin.offset(-6, y, z), wall);
                set(level, origin.offset(6, y, z), wall);
            }
            set(level, origin.offset(0, 6, z),
                    z % 5 == 0 ? Blocks.SEA_LANTERN.defaultBlockState()
                            : Blocks.IRON_BLOCK.defaultBlockState());
        }
        for (int x = -6; x <= 6; x++)
        {
            set(level, origin.offset(x, 7, 34),
                    Math.abs(x) <= 2 ? accent : Blocks.IRON_BLOCK.defaultBlockState());
        }

        // A wide lower gallery distributes staff between the three EVA lift
        // corridors without forcing them through the command hall above.
        for (int x = -32; x <= 32; x++)
        {
            for (int z = -28; z <= -18; z++)
            {
                set(level, origin.offset(x, 1, z),
                        z == -23 && Math.floorMod(x, 6) < 3
                                ? accent : floor);
                for (int y = 2; y <= 5; y++)
                {
                    set(level, origin.offset(x, y, z), Blocks.AIR.defaultBlockState());
                }
                set(level, origin.offset(x, 6, z),
                        x % 8 == 0 ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.IRON_BLOCK.defaultBlockState());
            }
        }
        for (int x = -32; x <= 32; x++)
        {
            for (int y = 2; y <= 5; y++)
            {
                set(level, origin.offset(x, y, -29), wall);
                set(level, origin.offset(x, y, -17), wall);
            }
        }

        // Join the southern entrance and northern distribution gallery.
        for (int z = -18; z <= 18; z++)
        {
            for (int x = -5; x <= 5; x++)
            {
                set(level, origin.offset(x, 1, z),
                        x == 0 && z % 6 < 3 ? accent : floor);
                for (int y = 2; y <= 6; y++)
                {
                    set(level, origin.offset(x, y, z), Blocks.AIR.defaultBlockState());
                }
            }
        }
    }

    private static void buildOperationsHall(ServerLevel level, BlockPos origin)
    {
        BlockState floor = Blocks.SMOOTH_STONE.defaultBlockState();
        BlockState wall = Blocks.BLACK_CONCRETE.defaultBlockState();

        for (int x = -23; x <= 23; x++)
        {
            for (int z = -21; z <= 21; z++)
            {
                set(level, origin.offset(x, OPERATIONS_FLOOR_Y, z),
                        Math.floorMod(x + z, 9) == 0
                                ? Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState() : floor);
                for (int y = 8; y <= 13; y++)
                {
                    set(level, origin.offset(x, y, z), Blocks.AIR.defaultBlockState());
                }
                set(level, origin.offset(x, 14, z),
                        x % 8 == 0 && z % 8 == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.GRAY_CONCRETE.defaultBlockState());
            }
        }
        for (int y = 8; y <= 13; y++)
        {
            for (int x = -23; x <= 23; x++)
            {
                set(level, origin.offset(x, y, -21), wall);
                set(level, origin.offset(x, y, 21), wall);
            }
            for (int z = -21; z <= 21; z++)
            {
                set(level, origin.offset(-23, y, z), wall);
                set(level, origin.offset(23, y, z), wall);
            }
        }

        buildTacticalDisplay(level, origin);
        buildConsoleTerraces(level, origin);
        buildSideGalleries(level, origin);
    }

    private static void buildTacticalDisplay(ServerLevel level, BlockPos origin)
    {
        for (int x = -18; x <= 18; x++)
        {
            for (int y = 9; y <= 13; y++)
            {
                BlockState pixel;
                if (y == 9 || y == 13)
                {
                    pixel = Blocks.BLACK_CONCRETE.defaultBlockState();
                }
                else if (Math.abs(x) <= 1)
                {
                    pixel = Blocks.RED_STAINED_GLASS.defaultBlockState();
                }
                else if (Math.abs(x) % 6 == 0)
                {
                    pixel = Blocks.BLACK_CONCRETE.defaultBlockState();
                }
                else if (Math.floorMod(x + y, 5) == 0)
                {
                    pixel = Blocks.LIME_STAINED_GLASS.defaultBlockState();
                }
                else
                {
                    pixel = x < 0 ? Blocks.CYAN_STAINED_GLASS.defaultBlockState()
                            : Blocks.BLUE_STAINED_GLASS.defaultBlockState();
                }
                set(level, origin.offset(x, y, DISPLAY_Z), pixel);
            }
        }

        // Central tactical table: the beacon is an unambiguous runtime
        // signature and the glass map reads from every command tier.
        for (int x = -4; x <= 4; x++)
        {
            for (int z = -3; z <= 3; z++)
            {
                set(level, origin.offset(x, 8, z),
                        Math.abs(x) == 4 || Math.abs(z) == 3
                                ? Blocks.POLISHED_BLACKSTONE.defaultBlockState()
                                : Blocks.ORANGE_STAINED_GLASS.defaultBlockState());
            }
        }
        set(level, origin.offset(0, 8, 0), Blocks.BEACON.defaultBlockState());
        set(level, origin.offset(0, 9, 0), Blocks.RED_STAINED_GLASS.defaultBlockState());
    }

    private static void buildConsoleTerraces(ServerLevel level, BlockPos origin)
    {
        BlockState chair = Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS.defaultBlockState()
                .setValue(StairBlock.FACING, Direction.NORTH);
        for (int z : new int[] {6, 11})
        {
            for (int x = -15; x <= 15; x += 5)
            {
                set(level, origin.offset(x, 8, z),
                        Blocks.POLISHED_BLACKSTONE.defaultBlockState());
                set(level, origin.offset(x, 9, z), Blocks.COMPARATOR.defaultBlockState());
                set(level, origin.offset(x, 8, z + 2), chair);
                if (Math.abs(x) % 10 == 0)
                {
                    set(level, origin.offset(x, 10, z),
                            Blocks.LIME_STAINED_GLASS.defaultBlockState());
                }
            }
        }
        for (int x = -18; x <= 18; x++)
        {
            set(level, origin.offset(x, 8, 16),
                    Math.abs(x) <= 3 ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                            : Blocks.POLISHED_DEEPSLATE.defaultBlockState());
        }
        for (int x : new int[] {-8, 8})
        {
            set(level, origin.offset(x, 9, 16), Blocks.LECTERN.defaultBlockState());
        }
    }

    private static void buildSideGalleries(ServerLevel level, BlockPos origin)
    {
        for (int z = -16; z <= 16; z++)
        {
            for (int x : new int[] {-21, 21})
            {
                set(level, origin.offset(x, 11, z),
                        z % 5 == 0 ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.IRON_BLOCK.defaultBlockState());
                set(level, origin.offset(x > 0 ? x - 1 : x + 1, 12, z),
                        Blocks.IRON_BARS.defaultBlockState());
            }
        }
    }


    /**
     * Finishes the downloaded command module's open boundary as inhabited,
     * pressure-safe NERV space. The source build ends at several naked map
     * edges; those edges must never read as doors onto the GeoFront cliff.
     */
    private static void buildCommandSupportAnnex(ServerLevel level,
                                                  BlockPos origin,
                                                  boolean localCommand)
    {
        if (!localCommand)
        {
            return;
        }

        BlockState floor = Blocks.POLISHED_DEEPSLATE.defaultBlockState();
        BlockState wall = Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState();
        BlockState ceiling = Blocks.GRAY_CONCRETE.defaultBlockState();

        // The large north opening becomes an enclosed observation gallery.
        // At this height the sloping pyramid's north face is z=98..99, so z=98
        // is the deepest pressure wall that stays completely inside the shell.
        buildSafeRoom(level, origin, -30, 30, -5, 4, 94, 98,
                floor, wall, ceiling, true);
        for (int x = -28; x <= 28; x++)
        {
            for (int y = -4; y <= 2; y++)
            {
                set(level, origin.offset(x, y, 98),
                        y >= -3 && y <= 1
                                ? Blocks.GRAY_STAINED_GLASS.defaultBlockState()
                                : wall);
            }
        }
        openGalleryDoorway(level, origin, -18,
                Blocks.ORANGE_CONCRETE.defaultBlockState());
        openGalleryDoorway(level, origin, 0,
                Blocks.PURPLE_CONCRETE.defaultBlockState());
        openGalleryDoorway(level, origin, 18,
                Blocks.RED_CONCRETE.defaultBlockState());
        // A continuous illuminated route makes the three exits read as one
        // inhabited NERV circulation space rather than unrelated holes in the
        // downloaded module. Keep all three interior rows obstacle-free.
        for (int x = -29; x <= 29; x++)
        {
            set(level, origin.offset(x, -5, 96),
                    Math.floorMod(x, 8) == 0
                            ? Blocks.SEA_LANTERN.defaultBlockState()
                            : Blocks.GRAY_CONCRETE.defaultBlockState());
        }
        for (int[] route : new int[][] {
                {-18, 1}, {0, 2}, {18, 3}
        })
        {
            BlockState accent = route[1] == 1
                    ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                    : route[1] == 2
                            ? Blocks.PURPLE_CONCRETE.defaultBlockState()
                            : Blocks.RED_CONCRETE.defaultBlockState();
            for (int z = 94; z <= 97; z++)
            {
                set(level, origin.offset(route[0], -5, z), accent);
            }
        }
        decorateSupportGallery(level, origin);


        // Two real support rooms branch from the gallery without protruding
        // through the sloping pyramid: west is briefing/MAGI liaison, east is
        // medical and launch-control support.
        buildSafeRoom(level, origin, -56, -30, -5, 4, 70, 96,
                floor, wall, ceiling, false);
        buildSafeRoom(level, origin, 30, 56, -5, 4, 70, 96,
                floor, wall, ceiling, false);
        openDoorway(level, origin, -30, -4, 94, Direction.WEST);
        openDoorway(level, origin, 30, -4, 94, Direction.EAST);
        furnishBriefingRoom(level, origin);
        furnishMedicalSupport(level, origin);

        // The lower southern asset opening now terminates in an illuminated
        // pressure vestibule rather than empty cavern air.
        buildSafeRoom(level, origin, -5, 5, -21, -14, -42, -33,
                Blocks.POLISHED_BLACKSTONE.defaultBlockState(), wall,
                Blocks.IRON_BLOCK.defaultBlockState(), false);
        for (int x = -2; x <= 2; x++)
        {
            for (int y = -20; y <= -16; y++)
            {
                set(level, origin.offset(x, y, -42),
                        Blocks.ORANGE_STAINED_GLASS.defaultBlockState());
            }
        }
        openPressureVestibuleDoorway(level, origin);
        buildCommandAccessSpine(level, origin);

        // Two high maintenance apertures are observation windows, not exits.
        for (int x : new int[] {-26, -25, 21, 22})
        {
            set(level, origin.offset(x, 39, 95),
                    Blocks.IRON_BLOCK.defaultBlockState());
            for (int y = 40; y <= 42; y++)
            {
                set(level, origin.offset(x, y, 95),
                        Blocks.RED_STAINED_GLASS.defaultBlockState());
            }
        }
    }

    private static void buildSafeRoom(ServerLevel level, BlockPos origin,
                                      int minimumX, int maximumX,
                                      int floorY, int ceilingY,
                                      int minimumZ, int maximumZ,
                                      BlockState floor, BlockState wall,
                                      BlockState ceiling,
                                      boolean glassNorth)
    {
        for (int x = minimumX; x <= maximumX; x++)
        {
            for (int z = minimumZ; z <= maximumZ; z++)
            {
                set(level, origin.offset(x, floorY, z), floor);
                set(level, origin.offset(x, ceilingY, z),
                        Math.floorMod(x + z, 7) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : ceiling);
                for (int y = floorY + 1; y < ceilingY; y++)
                {
                    boolean boundary = x == minimumX || x == maximumX
                            || z == minimumZ || z == maximumZ;
                    BlockState state = boundary
                            ? glassNorth && z == maximumZ
                                    ? Blocks.GRAY_STAINED_GLASS.defaultBlockState()
                                    : wall
                            : Blocks.AIR.defaultBlockState();
                    set(level, origin.offset(x, y, z), state);
                }
            }
        }
    }

    private static void openGalleryDoorway(ServerLevel level,
                                            BlockPos origin, int centreX,
                                            BlockState accent)
    {
        // The imported module is clipped at relative z=95. A two-block
        // pressure threshold replaces each exposed exit with a real doorway
        // into the sealed support gallery.
        for (int z = 94; z <= 95; z++)
        {
            for (int x = centreX - 2; x <= centreX + 2; x++)
            {
                for (int y = -4; y <= 1; y++)
                {
                    set(level, origin.offset(x, y, z),
                            Blocks.AIR.defaultBlockState());
                }
            }
        }
        for (int y = -4; y <= 2; y++)
        {
            set(level, origin.offset(centreX - 3, y, 94), accent);
            set(level, origin.offset(centreX + 3, y, 94), accent);
        }
        for (int x = centreX - 2; x <= centreX + 2; x++)
        {
            set(level, origin.offset(x, 2, 94),
                    x == centreX
                            ? Blocks.SEA_LANTERN.defaultBlockState()
                            : accent);
        }
    }

    private static void decorateSupportGallery(ServerLevel level,
                                               BlockPos origin)
    {
        // Recessed information bays break up the imported module's blank
        // clipped wall without consuming any of the three walkable rows.
        // Their colours repeat the physical route stripes under each door.
        int[][] panels = {
                {-28, -23, 0}, {-13, -6, 1},
                {6, 13, 2}, {23, 28, 3}
        };
        for (int[] panel : panels)
        {
            BlockState accent = switch (panel[2])
            {
                case 0 -> Blocks.ORANGE_STAINED_GLASS.defaultBlockState();
                case 1 -> Blocks.PURPLE_STAINED_GLASS.defaultBlockState();
                case 2 -> Blocks.RED_STAINED_GLASS.defaultBlockState();
                default -> Blocks.CYAN_STAINED_GLASS.defaultBlockState();
            };
            int centre = (panel[0] + panel[1]) / 2;
            for (int x = panel[0]; x <= panel[1]; x++)
            {
                for (int y = -3; y <= 1; y++)
                {
                    boolean frame = x == panel[0] || x == panel[1]
                            || y == -3 || y == 1;
                    set(level, origin.offset(x, y, 94),
                            frame
                                    ? Blocks.POLISHED_DEEPSLATE
                                            .defaultBlockState()
                                    : Blocks.BLACK_CONCRETE
                                            .defaultBlockState());
                }
            }
            for (int x = panel[0] + 1; x < panel[1]; x += 2)
            {
                set(level, origin.offset(x, -1, 94), accent);
            }
            set(level, origin.offset(centre, 0, 94),
                    Blocks.SEA_LANTERN.defaultBlockState());
        }

        // Full-block mullions make the north face read as a pressure-rated
        // observation window rather than a missing chunk exposing raw rock.
        // They remain in the boundary plane at z=98, outside the aisle.
        for (int x = -28; x <= 28; x += 8)
        {
            for (int y = -3; y <= 1; y++)
            {
                set(level, origin.offset(x, y, 98),
                        Blocks.POLISHED_DEEPSLATE.defaultBlockState());
            }
            set(level, origin.offset(x, -1, 98),
                    Blocks.IRON_BLOCK.defaultBlockState());
        }
    }

    /**
     * A real 22-step pressure tunnel joins the imported module's lower
     * service vestibule to the central hangar interchange at Y=2.
     */
    private static void buildCommandAccessSpine(ServerLevel level,
                                                 BlockPos origin)
    {
        BlockState stair = Blocks.SMOOTH_QUARTZ_STAIRS.defaultBlockState()
                .setValue(StairBlock.FACING, Direction.NORTH);
        for (int z = -40; z >= -61; z--)
        {
            // Keep the rising service spine west of the public Y=1 concourse.
            // Sharing the same X/Z column made one route's floor become the
            // other route's head obstruction on every runtime repair.
            int floorY = -20 + (-z - 40);
            for (int x = -3; x <= 3; x++)
            {
                int routeX = COMMAND_SPINE_X + x;
                set(level, origin.offset(routeX, floorY, z), stair);
                for (int y = 1; y <= 4; y++)
                {
                    set(level, origin.offset(routeX, floorY + y, z),
                            Blocks.AIR.defaultBlockState());
                }
                set(level, origin.offset(routeX, floorY + 5, z),
                        x == 0 && Math.floorMod(z, 5) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.IRON_BLOCK.defaultBlockState());
            }
            for (int y = 0; y <= 5; y++)
            {
                BlockState wall = y == 2 && Math.floorMod(z, 6) == 0
                        ? Blocks.ORANGE_STAINED_GLASS.defaultBlockState()
                        : Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState();
                set(level, origin.offset(COMMAND_SPINE_X - 4,
                        floorY + y, z), wall);
                set(level, origin.offset(COMMAND_SPINE_X + 4,
                        floorY + y, z), wall);
            }
        }

        // Lower landing: the imported service vestibule at X=-1 turns west
        // before the climb begins, so it never passes underneath the public
        // concourse.
        for (int x = COMMAND_SPINE_X; x <= -1; x++)
        {
            set(level, origin.offset(x, -21, -39),
                    Blocks.POLISHED_BLACKSTONE.defaultBlockState());
            for (int y = -20; y <= -17; y++)
            {
                set(level, origin.offset(x, y, -39),
                        Blocks.AIR.defaultBlockState());
            }
            set(level, origin.offset(x, -16, -39),
                    Math.floorMod(x, 5) == 0
                            ? Blocks.SEA_LANTERN.defaultBlockState()
                            : Blocks.IRON_BLOCK.defaultBlockState());
        }

        // Upper landing: remain in the safe x=-21 gap until south of every
        // shaft shell, then turn east on z=-58.  The former z=-61 turn wrote a
        // ceiling into the inclusive edge of the doubled carrier envelope.
        for (int z = -61; z <= SOUTH_INTERCHANGE_Z; z++)
        {
            for (int x = -3; x <= 3; x++)
            {
                set(level, origin.offset(COMMAND_SPINE_X + x, 1, z),
                        Blocks.POLISHED_BLACKSTONE.defaultBlockState());
                for (int y = 2; y <= 5; y++)
                {
                    set(level, origin.offset(COMMAND_SPINE_X + x, y, z),
                            Blocks.AIR.defaultBlockState());
                }
                set(level, origin.offset(COMMAND_SPINE_X + x, 6, z),
                        x == 0 && Math.floorMod(z, 4) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.IRON_BLOCK.defaultBlockState());
            }
        }
        for (int x = COMMAND_SPINE_X; x <= 0; x++)
        {
            set(level, origin.offset(x, 1, SOUTH_INTERCHANGE_Z),
                    Blocks.POLISHED_BLACKSTONE.defaultBlockState());
            for (int y = 2; y <= 5; y++)
            {
                set(level, origin.offset(x, y, SOUTH_INTERCHANGE_Z),
                        Blocks.AIR.defaultBlockState());
            }
            set(level, origin.offset(x, 6, SOUTH_INTERCHANGE_Z),
                    Math.floorMod(x, 5) == 0
                            ? Blocks.SEA_LANTERN.defaultBlockState()
                            : Blocks.IRON_BLOCK.defaultBlockState());
        }

        // Open the ramp through the vestibule's former observation glazing.
        int thresholdFloorY = -19;
        for (int x = -2; x <= 2; x++)
        {
            for (int y = thresholdFloorY + 1;
                 y <= thresholdFloorY + 4; y++)
            {
                set(level, origin.offset(x, y, -42),
                        Blocks.AIR.defaultBlockState());
            }
        }
        for (int y = thresholdFloorY; y <= thresholdFloorY + 5; y++)
        {
            set(level, origin.offset(-3, y, -42),
                    Blocks.ORANGE_CONCRETE.defaultBlockState());
            set(level, origin.offset(3, y, -42),
                    Blocks.ORANGE_CONCRETE.defaultBlockState());
        }
    }
    private static void openPressureVestibuleDoorway(ServerLevel level,
                                                      BlockPos origin)
    {
        // The downloaded module has one genuine three-block service exit on
        // its south boundary. Continue that floor into the sealed vestibule
        // instead of replacing the doorway with a wall or leaving a drop.
        for (int x = -2; x <= 0; x++)
        {
            for (int y = -20; y <= -17; y++)
            {
                set(level, origin.offset(x, y, -33),
                        Blocks.AIR.defaultBlockState());
            }
        }
        for (int y = -21; y <= -16; y++)
        {
            set(level, origin.offset(-3, y, -33),
                    Blocks.ORANGE_CONCRETE.defaultBlockState());
            set(level, origin.offset(1, y, -33),
                    Blocks.ORANGE_CONCRETE.defaultBlockState());
        }
        for (int x = -2; x <= 0; x++)
        {
            set(level, origin.offset(x, -16, -33),
                    x == -1 ? Blocks.SEA_LANTERN.defaultBlockState()
                            : Blocks.ORANGE_CONCRETE.defaultBlockState());
        }
    }



    private static void openDoorway(ServerLevel level, BlockPos origin,
                                    int wallX, int feetY, int centreZ,
                                    Direction direction)
    {
        int inward = direction == Direction.WEST ? -1 : 1;
        for (int x = wallX; x != wallX + inward * 4; x += inward)
        {
            for (int z = centreZ - 1; z <= centreZ + 1; z++)
            {
                for (int y = feetY; y <= feetY + 3; y++)
                {
                    set(level, origin.offset(x, y, z),
                            Blocks.AIR.defaultBlockState());
                }
            }
        }
    }

    private static void furnishBriefingRoom(ServerLevel level, BlockPos origin)
    {
        // Remove the old floor-level slab prototype before installing a
        // readable human-scale table and unobstructed circulation aisle.
        for (int x = -51; x <= -35; x++)
        {
            for (int z = 78; z <= 87; z++)
            {
                set(level, origin.offset(x, -4, z),
                        Blocks.AIR.defaultBlockState());
                set(level, origin.offset(x, -3, z),
                        Blocks.AIR.defaultBlockState());
            }
        }

        for (int x = -48; x <= -38; x++)
        {
            for (int z = 80; z <= 84; z++)
            {
                boolean cutCorner = Math.abs(x + 43) == 5
                        && Math.abs(z - 82) == 2;
                if (!cutCorner)
                {
                    set(level, origin.offset(x, -3, z),
                            Blocks.SMOOTH_QUARTZ_SLAB.defaultBlockState());
                }
            }
        }
        for (int x : new int[] {-47, -39})
        {
            for (int z : new int[] {81, 83})
            {
                set(level, origin.offset(x, -4, z),
                        Blocks.POLISHED_BLACKSTONE_WALL.defaultBlockState());
            }
        }
        set(level, origin.offset(-43, -4, 82),
                Blocks.SEA_LANTERN.defaultBlockState());
        set(level, origin.offset(-43, -3, 82),
                Blocks.CYAN_STAINED_GLASS.defaultBlockState());

        BlockState northChair = Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS
                .defaultBlockState().setValue(StairBlock.FACING,
                        Direction.SOUTH);
        BlockState southChair = Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS
                .defaultBlockState().setValue(StairBlock.FACING,
                        Direction.NORTH);
        for (int x : new int[] {-47, -43, -39})
        {
            set(level, origin.offset(x, -4, 78), northChair);
            set(level, origin.offset(x, -4, 86), southChair);
        }
        set(level, origin.offset(-50, -4, 82),
                Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS.defaultBlockState()
                        .setValue(StairBlock.FACING, Direction.EAST));
        set(level, origin.offset(-36, -4, 82),
                Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS.defaultBlockState()
                        .setValue(StairBlock.FACING, Direction.WEST));

        // A recessed tactical wall sits behind the table, fully inside the
        // room shell. It reads as a screen instead of a freestanding billboard.
        for (int x = -50; x <= -36; x++)
        {
            for (int y = -3; y <= 1; y++)
            {
                boolean frame = x == -50 || x == -36 || y == -3 || y == 1;
                set(level, origin.offset(x, y, 71), frame
                        ? Blocks.PURPLE_CONCRETE.defaultBlockState()
                        : Blocks.BLACK_CONCRETE.defaultBlockState());
            }
        }
        for (int x = -48; x <= -38; x++)
        {
            set(level, origin.offset(x, -1, 71),
                    Math.floorMod(x, 3) == 0
                            ? Blocks.SEA_LANTERN.defaultBlockState()
                            : Blocks.ORANGE_STAINED_GLASS.defaultBlockState());
        }
        set(level, origin.offset(-46, 0, 71),
                Blocks.CYAN_STAINED_GLASS.defaultBlockState());
        set(level, origin.offset(-43, 0, 71),
                Blocks.RED_STAINED_GLASS.defaultBlockState());
        set(level, origin.offset(-40, 0, 71),
                Blocks.CYAN_STAINED_GLASS.defaultBlockState());

        for (int x = -55; x <= -30; x++)
        {
            set(level, origin.offset(x, -5, 94),
                    Blocks.PURPLE_CONCRETE.defaultBlockState());
        }
        for (int z = 72; z <= 94; z++)
        {
            set(level, origin.offset(-56, 0, z),
                    Math.floorMod(z, 6) == 0
                            ? Blocks.PURPLE_STAINED_GLASS.defaultBlockState()
                            : Blocks.BLACK_CONCRETE.defaultBlockState());
        }
    }

    private static void furnishMedicalSupport(ServerLevel level,
                                               BlockPos origin)
    {
        // Clear the former wool benches so each treatment pod has a bed,
        // head monitor, visitor seat and a full-width aisle to the gallery.
        for (int x = 35; x <= 46; x++)
        {
            for (int z = 73; z <= 91; z++)
            {
                set(level, origin.offset(x, -4, z),
                        Blocks.AIR.defaultBlockState());
                set(level, origin.offset(x, -3, z),
                        Blocks.AIR.defaultBlockState());
            }
        }

        for (int centreZ : new int[] {75, 82, 89})
        {
            for (int x = 36; x <= 43; x++)
            {
                for (int z = centreZ; z <= centreZ + 1; z++)
                {
                    BlockState bed = x == 36
                            ? Blocks.IRON_BLOCK.defaultBlockState()
                            : Blocks.SMOOTH_QUARTZ_SLAB.defaultBlockState();
                    set(level, origin.offset(x, -4, z), bed);
                }
            }
            set(level, origin.offset(36, -3, centreZ),
                    Blocks.SEA_LANTERN.defaultBlockState());
            set(level, origin.offset(36, -3, centreZ + 1),
                    Blocks.CYAN_STAINED_GLASS.defaultBlockState());
            set(level, origin.offset(45, -4, centreZ),
                    Blocks.QUARTZ_STAIRS.defaultBlockState()
                            .setValue(StairBlock.FACING, Direction.WEST));
            set(level, origin.offset(45, -4, centreZ + 1),
                    Blocks.QUARTZ_STAIRS.defaultBlockState()
                            .setValue(StairBlock.FACING, Direction.WEST));
        }

        for (int x = 34; x <= 52; x++)
        {
            for (int y = -3; y <= 1; y++)
            {
                boolean frame = x == 34 || x == 52 || y == -3 || y == 1;
                set(level, origin.offset(x, y, 71), frame
                        ? Blocks.CYAN_CONCRETE.defaultBlockState()
                        : Blocks.BLACK_CONCRETE.defaultBlockState());
            }
        }
        for (int x = 36; x <= 50; x++)
        {
            set(level, origin.offset(x, -1, 71),
                    Math.floorMod(x, 4) == 0
                            ? Blocks.REDSTONE_LAMP.defaultBlockState()
                            : Blocks.CYAN_STAINED_GLASS.defaultBlockState());
        }

        for (int z = 74; z <= 92; z += 3)
        {
            set(level, origin.offset(55, -4, z),
                    Blocks.IRON_BLOCK.defaultBlockState());
            set(level, origin.offset(55, -3, z),
                    Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState());
            set(level, origin.offset(55, -2, z),
                    Blocks.CYAN_STAINED_GLASS.defaultBlockState());
            set(level, origin.offset(54, -2, z),
                    Blocks.SEA_LANTERN.defaultBlockState());
        }
        for (int x = 30; x <= 55; x++)
        {
            set(level, origin.offset(x, -5, 94),
                    Blocks.CYAN_CONCRETE.defaultBlockState());
        }
        for (int z = 72; z <= 94; z++)
        {
            set(level, origin.offset(56, 0, z),
                    Math.floorMod(z, 6) == 0
                            ? Blocks.CYAN_STAINED_GLASS.defaultBlockState()
                            : Blocks.BLACK_CONCRETE.defaultBlockState());
        }
        for (int partitionZ : new int[] {79, 86})
        {
            for (int x = 35; x <= 41; x++)
            {
                for (int y = -3; y <= 0; y++)
                {
                    set(level, origin.offset(x, y, partitionZ),
                            Blocks.CYAN_STAINED_GLASS.defaultBlockState());
                }
            }
        }
    }
    /** Builds three physical 16:9 surfaces for authenticated cockpit frames. */
    private static void buildVideoWall(ServerLevel level, BlockPos origin,
                                       boolean localCommand)
    {
        BlockPos anchor = localCommand
                ? origin.offset(0, 17, 58)
                : origin.offset(0, 7, DISPLAY_Z + 1);
        if (localCommand)
        {
            buildImportedOperationsShell(level, origin);
            // The downloaded bridge includes an oversized luminous truss
            // directly between the operator tier and this wall. It fills most
            // of a human-height sightline and hides the live cockpit frames.
            // Keep its ceiling and lower console deck, but open the bounded
            // air volume between them; the video wall itself sits at z=57 and
            // is deliberately outside this sweep.
            for (int x = -18; x <= 18; x++)
            {
                for (int y = 17; y <= 28; y++)
                {
                    for (int z = 60; z <= 70; z++)
                    {
                        set(level, origin.offset(x, y, z),
                                Blocks.AIR.defaultBlockState());
                    }
                }
            }
        }
        for (int x = -18; x <= 18; x++)
        {
            for (int y = 0; y <= 8; y++)
            {
                boolean frame = y == 0 || y == 8
                        || x == -18 || x == -6 || x == 6 || x == 18;
                BlockState state = frame
                        ? (y == 0 && Math.floorMod(x, 6) == 0
                                ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                                : Blocks.POLISHED_DEEPSLATE.defaultBlockState())
                        : Blocks.BLACK_CONCRETE.defaultBlockState();
                set(level, anchor.offset(x, y, -1), state);
            }
        }
        for (int x : new int[] {-12, 0, 12})
        {
            set(level, anchor.offset(x, 0, -1),
                    Blocks.SEA_LANTERN.defaultBlockState());
        }

        // Two upper diagnostic wings keep the strategic and optical-sensor
        // TextDisplays inside the command-room shell.  Their former +/-21 X
        // positions intersected the imported module's side walls, making a
        // valid live sensor invisible from the operations floor.
        for (int centreX : new int[] {-12, 12})
        {
            for (int x = centreX - 6; x <= centreX + 6; x++)
            {
                for (int y = 9; y <= 16; y++)
                {
                    boolean frame = x == centreX - 6 || x == centreX + 6
                            || y == 9 || y == 16;
                    set(level, anchor.offset(x, y, -1), frame
                            ? Blocks.POLISHED_DEEPSLATE.defaultBlockState()
                            : Blocks.BLACK_CONCRETE.defaultBlockState());
                }
            }
            set(level, anchor.offset(centreX, 9, -1),
                    Blocks.SEA_LANTERN.defaultBlockState());
        }
    }

    /**
     * Finishes the imported open bridge as a pressure-safe command theatre.
     *
     * <p>The source map supplies the recognizable bridge, but its upper and
     * rear boundaries end in open GeoFront air.  A continuous recessed ceiling
     * and one central pressure doorway preserve the authored interior while
     * making the console deck a real room rather than a facade.</p>
     */
    private static void buildImportedOperationsShell(ServerLevel level,
                                                      BlockPos origin)
    {
        sealImportedModuleEnvelope(level, origin);
        int minimumX = -24;
        int maximumX = 24;
        int minimumZ = 52;
        int maximumZ = 84;
        int floorY = OPERATIONS_FLOOR_Y;
        int ceilingY = 36;
        BlockState wall = Blocks.DEEPSLATE_BRICKS
                .defaultBlockState();
        for (int x = minimumX; x <= maximumX; x++)
        {
            for (int z = minimumZ; z <= maximumZ; z++)
            {
                BlockPos floor = origin.offset(x, floorY, z);
                if (level.getBlockState(floor).isAir())
                {
                    set(level, floor,
                            Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                }
                set(level, origin.offset(x, ceilingY, z),
                        Math.floorMod(x + z, 8) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : wall);
                for (int y = floorY + 1; y < ceilingY; y++)
                {
                    boolean boundary = x == minimumX || x == maximumX
                            || z == minimumZ || z == maximumZ;
                    if (!boundary)
                    {
                        continue;
                    }
                    boolean rearDoor = z == maximumZ
                            && Math.abs(x) <= 3
                            && y >= floorY + 1 && y <= floorY + 5;
                    set(level, origin.offset(x, y, z), rearDoor
                            ? Blocks.AIR.defaultBlockState() : wall);
                }
            }
        }

        // The command dais stair terminates at this pressure threshold. A
        // short lit landing makes the doorway physically continue into the
        // imported circulation spine instead of opening onto a one-block lip.
        for (int z = maximumZ; z <= maximumZ + 4; z++)
        {
            for (int x = -3; x <= 3; x++)
            {
                set(level, origin.offset(x, floorY, z),
                        x == 0 && z % 2 == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                for (int y = floorY + 1; y <= floorY + 5; y++)
                {
                    set(level, origin.offset(x, y, z),
                            Blocks.AIR.defaultBlockState());
                }
            }
            for (int y = floorY + 1; y <= floorY + 5; y++)
            {
                set(level, origin.offset(-4, y, z), wall);
                set(level, origin.offset(4, y, z), wall);
            }
            set(level, origin.offset(0, floorY + 6, z),
                    Blocks.SEA_LANTERN.defaultBlockState());
        }
    }

    /**
     * The local command module is a stage build, not a pressure-rated
     * building: several exterior faces and its underside are open. Wrap the
     * complete authored volume in one structural envelope while preserving
     * every non-air authored block. Explicit apertures are limited to the
     * lower central spine and the two sealed support-room thresholds.
     */
    private static void sealImportedModuleEnvelope(ServerLevel level,
                                                   BlockPos origin)
    {
        final int minimumX = -30;
        final int maximumX = 30;
        final int minimumY = -22;
        final int maximumY = 58;
        final int minimumZ = -35;
        final int maximumZ = 98;
        BlockState wall = com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
        BlockState floor = Blocks.POLISHED_DEEPSLATE.defaultBlockState();
        BlockState ceiling = Blocks.DEEPSLATE_TILES.defaultBlockState();

        for (int x = minimumX; x <= maximumX; x++)
        {
            for (int z = minimumZ; z <= maximumZ; z++)
            {
                setIfAir(level, origin.offset(x, minimumY, z),
                        Math.floorMod(x + z, 13) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : floor);
                setIfAir(level, origin.offset(x, maximumY, z),
                        Math.floorMod(x - z, 17) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : ceiling);
            }
        }

        for (int y = minimumY + 1; y < maximumY; y++)
        {
            for (int z = minimumZ; z <= maximumZ; z++)
            {
                for (int x : new int[] {minimumX, maximumX})
                {
                    boolean supportDoor = (x == minimumX || x == maximumX)
                            && y >= -4 && y <= -1
                            && z >= 93 && z <= 95;
                    if (!supportDoor)
                    {
                        setIfAir(level, origin.offset(x, y, z),
                                Math.floorMod(y, 12) == 0
                                        ? Blocks.ORANGE_CONCRETE
                                        .defaultBlockState()
                                        : wall);
                    }
                }
            }
            for (int x = minimumX; x <= maximumX; x++)
            {
                for (int z : new int[] {minimumZ, maximumZ})
                {
                    boolean lowerSpineDoor = z == minimumZ
                            && Math.abs(x) <= 6
                            && y >= 2 && y <= 6;
                    if (!lowerSpineDoor)
                    {
                        setIfAir(level, origin.offset(x, y, z),
                                Math.floorMod(y, 12) == 0
                                        ? Blocks.ORANGE_CONCRETE
                                        .defaultBlockState()
                                        : wall);
                    }
                }
            }
        }

        // Reassert the main pressure aperture even when a rejected envelope
        // revision had already filled it with stone.
        for (int x = -6; x <= 6; x++)
        {
            for (int y = 2; y <= 6; y++)
            {
                set(level, origin.offset(x, y, minimumZ),
                        Blocks.AIR.defaultBlockState());
            }
        }
    }

    private static void setIfAir(ServerLevel level, BlockPos position,
                                 BlockState state)
    {
        if (level.getBlockState(position).isAir())
        {
            set(level, position, state);
        }
    }

    private static void buildAccessStairs(ServerLevel level, BlockPos origin)
    {
        BlockState stair = Blocks.SMOOTH_QUARTZ_STAIRS.defaultBlockState()
                .setValue(StairBlock.FACING, Direction.NORTH);
        for (int step = 0; step <= 5; step++)
        {
            int y = 2 + step;
            int z = 22 - step;
            for (int x = -14; x <= -12; x++)
            {
                for (int clearY = y + 1; clearY <= y + 3; clearY++)
                {
                    set(level, origin.offset(x, clearY, z), Blocks.AIR.defaultBlockState());
                }
                set(level, origin.offset(x, y, z), stair);
            }
        }
    }

    private static void buildLiftTransit(ServerLevel level, BlockPos origin)
    {
        for (int laneX : TRANSIT_X)
        {
            BlockState accent = laneX < 0 ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                    : laneX > 0 ? Blocks.RED_CONCRETE.defaultBlockState()
                    : Blocks.PURPLE_CONCRETE.defaultBlockState();
            for (int z = SOUTH_INTERCHANGE_Z; z <= -28; z++)
            {
                for (int x = -3; x <= 3; x++)
                {
                    set(level, origin.offset(laneX + x, 1, z),
                            x == 0 ? accent : Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState());
                    for (int y = 2; y <= 5; y++)
                    {
                        set(level, origin.offset(laneX + x, y, z),
                                Blocks.AIR.defaultBlockState());
                    }
                    set(level, origin.offset(laneX + x, 6, z),
                            x == 0 && Math.floorMod(z, 7) == 0
                                    ? Blocks.SEA_LANTERN.defaultBlockState()
                                    : Blocks.IRON_BLOCK.defaultBlockState());
                }
                for (int y = 2; y <= 5; y++)
                {
                    set(level, origin.offset(laneX - 4, y, z),
                            Blocks.GRAY_CONCRETE.defaultBlockState());
                    set(level, origin.offset(laneX + 4, y, z),
                            Blocks.GRAY_CONCRETE.defaultBlockState());
                }
            }
        }
    }

    /**
     * Street-level maintenance route, independent of the climbing personnel
     * spine. It bends around the west shell and meets the dry gallery ladder;
     * the former +/-14 paths cut straight through the enlarged LCL tanks.
     */
    private static void buildGroundHangarRoute(ServerLevel level, BlockPos origin)
    {
        int floorY = 1;
        int southZ = SOUTH_INTERCHANGE_Z;
        int ladderZ = EvaHangarBuilder.GALLERY_Z - 6;
        int ladderX = IntegratedNervMapBuilder.LIFT_X[0] - 22;
        int routeX = ladderX - 3;

        Set<Long> carved = new LinkedHashSet<>();
        // Move west while still south of the launch-shaft shells.
        addGroundRun(carved, WEST_SHAFT_GAP_X, 0,
                SOUTH_INTERCHANGE_Z, SOUTH_INTERCHANGE_Z + 2);
        for (int z = southZ; z >= ladderZ; z--)
        {
            int centreX;
            if (z >= SHAFT_NORTH_EDGE_Z)
            {
                centreX = WEST_SHAFT_GAP_X;
            }
            else
            {
                centreX = Math.max(routeX, WEST_SHAFT_GAP_X
                        - (SHAFT_NORTH_EDGE_Z - z) * 3);
            }
            addGroundRun(carved, centreX - 2, centreX + 2, z, z);
        }

        BlockState accent = Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState();
        for (long packed : carved)
        {
            int x = (int) (packed >> 32);
            int z = (int) packed;
            set(level, origin.offset(x, floorY, z),
                    Math.floorMod(x + z, 7) == 0 ? accent
                            : Blocks.POLISHED_DEEPSLATE.defaultBlockState());
            for (int y = 1; y <= 4; y++)
            {
                set(level, origin.offset(x, floorY + y, z),
                        Blocks.AIR.defaultBlockState());
            }
            set(level, origin.offset(x, floorY + 5, z),
                    Math.floorMod(x + z, 11) == 0
                            ? Blocks.SEA_LANTERN.defaultBlockState()
                            : com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
        }
        // Wall only where the corridor actually meets open cavern, so every
        // junction stays open and no leg is sealed off.
        for (long packed : carved)
        {
            int x = (int) (packed >> 32);
            int z = (int) packed;
            for (int[] step : new int[][] {{1, 0}, {-1, 0}, {0, 1}, {0, -1}})
            {
                if (carved.contains(pack(x + step[0], z + step[1])))
                {
                    continue;
                }
                // Leave the east side of the north endpoint open onto the dry
                // ladder instead of replacing its rungs with a corridor wall.
                if (x == routeX + 2 && z == ladderZ
                        && step[0] == 1 && step[1] == 0)
                {
                    continue;
                }
                for (int y = 1; y <= 4; y++)
                {
                    set(level, origin.offset(x + step[0], floorY + y, z + step[1]),
                            com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
                }
            }
        }

        // Reassert the pre-existing dry ladder after the route's ceiling and
        // wall pass. This makes the lower maintenance level physically meet
        // the same shared gallery used by the elevated personnel spine.
        for (int y = floorY + 1;
             y <= EvaHangarBuilder.GALLERY_Y; y++)
        {
            set(level, origin.offset(ladderX, y, ladderZ),
                    Blocks.LADDER.defaultBlockState()
                            .setValue(LadderBlock.FACING, Direction.SOUTH));
            set(level, origin.offset(ladderX, y, ladderZ - 1),
                    com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
        }
    }

    private static void addGroundRun(Set<Long> carved, int minX, int maxX,
                                      int minZ, int maxZ)
    {
        for (int x = Math.min(minX, maxX); x <= Math.max(minX, maxX); x++)
        {
            for (int z = Math.min(minZ, maxZ); z <= Math.max(minZ, maxZ); z++)
            {
                carved.add(pack(x, z));
            }
        }
    }

    private static long pack(int x, int z)
    {
        return ((long) x << 32) | (z & 0xFFFFFFFFL);
    }

    public static void linkHangars(ServerLevel level, BlockPos origin)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        linkHangarRoutes(level, origin);
        // The climbing ramp above clears headroom straight through each cage's
        // +X ladder shaft, so the boarding ladders are the last thing written.
        for (int variant = 0; variant < 3; variant++)
        {
            EvaHangarBuilder.buildRearLadders(level, origin, variant);
        }
        // The three ramps wall a corridor straight through the gallery at
        // walking height; reopen the shared east-west concourse last, so an
        // operator can cross from the EVA-00 booth to the EVA-02 booth.
        EvaHangarBuilder.clearGalleryConcourse(level, origin);
    }

    private static void linkHangarRoutes(ServerLevel level, BlockPos origin)
    {
        buildGroundHangarRoute(level, origin);
        buildHangarRouteEntryDogleg(level, origin);
        int galleryDoorZ = EvaHangarBuilder.GALLERY_Z - 7;
        for (int laneX : HANGAR_ROUTE_LANES)
        {
            BlockState accent = laneX < 0
                    ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                    : laneX > 0
                    ? Blocks.RED_CONCRETE.defaultBlockState()
                    : Blocks.PURPLE_CONCRETE.defaultBlockState();
            for (int z = SOUTH_INTERCHANGE_Z; z >= galleryDoorZ; z--)
            {
                int routeX = hangarRouteCentreX(origin, laneX, z);
                int rise = Math.min(EvaHangarBuilder.GALLERY_Y - 1,
                        Math.max(0, (-z - 61) / 2));
                int floorY = 1 + rise;
                int previousRise = Math.min(EvaHangarBuilder.GALLERY_Y - 1,
                        Math.max(0, (-(z + 1) - 61) / 2));
                boolean stepUp = rise > previousRise;
                for (int x = -3; x <= 3; x++)
                {
                    BlockState floor = stepUp
                            ? Blocks.SMOOTH_QUARTZ_STAIRS.defaultBlockState()
                                    .setValue(StairBlock.FACING,
                                            Direction.NORTH)
                            : x == 0 ? accent
                            : Blocks.POLISHED_DEEPSLATE.defaultBlockState();
                    set(level, origin.offset(routeX + x, floorY, z), floor);
                    for (int y = 1; y <= 4; y++)
                    {
                        BlockPos clearance = origin.offset(routeX + x,
                                floorY + y, z);
                        // The final horizontal artery shares eight cells with
                        // the split boarding bridge. Preserve only a rail that
                        // the bridge state machine has actually extended; an
                        // absent rail stays absent while the bridge retracts.
                        boolean liveBridgeRail = floorY
                                == EvaHangarBuilder.GALLERY_Y
                                && y == 1 && Math.abs(x) == 3
                                && level.getBlockState(clearance)
                                .is(Blocks.IRON_BARS);
                        if (!liveBridgeRail)
                        {
                            set(level, clearance, Blocks.AIR.defaultBlockState());
                        }
                    }
                    set(level, origin.offset(routeX + x,
                                    floorY + 5, z),
                            x == 0 && Math.floorMod(z, 8) == 0
                                    ? Blocks.SEA_LANTERN.defaultBlockState()
                                    : Blocks.IRON_BLOCK.defaultBlockState());
                }
                for (int y = 1; y <= 4; y++)
                {
                    set(level, origin.offset(routeX - 4, floorY + y, z),
                            Blocks.GRAY_CONCRETE.defaultBlockState());
                    set(level, origin.offset(routeX + 4, floorY + y, z),
                            Blocks.GRAY_CONCRETE.defaultBlockState());
                }
            }

            // Enter the broad observation gallery through a side pressure
            // door. Returning to the EVA centreline outside the gallery would
            // cross the retractable boarding bridge at Z=142.
            int doorX = hangarRouteCentreX(origin, laneX, galleryDoorZ);
            for (int x = -3; x <= 3; x++)
            {
                for (int y = EvaHangarBuilder.GALLERY_Y + 1;
                     y <= EvaHangarBuilder.GALLERY_Y + 4; y++)
                {
                    set(level, origin.offset(doorX + x, y, galleryDoorZ),
                            Blocks.AIR.defaultBlockState());
                }
            }
            for (int y = EvaHangarBuilder.GALLERY_Y;
                 y <= EvaHangarBuilder.GALLERY_Y + 5; y++)
            {
                set(level, origin.offset(doorX - 4, y, galleryDoorZ), accent);
                set(level, origin.offset(doorX + 4, y, galleryDoorZ), accent);
            }
        }
    }

    private static boolean hasConnectedHangarRoutes(ServerLevel level,
                                                     BlockPos origin)
    {
        int galleryDoorZ = EvaHangarBuilder.GALLERY_Z - 7;
        for (int laneX : HANGAR_ROUTE_LANES)
        {
            for (int z = SOUTH_INTERCHANGE_Z; z >= galleryDoorZ; z--)
            {
                int routeX = hangarRouteCentreX(origin, laneX, z);
                int rise = Math.min(EvaHangarBuilder.GALLERY_Y - 1,
                        Math.max(0, (-z - 61) / 2));
                int floorY = 1 + rise;
                if (!walkable(level,
                        origin.offset(routeX, floorY + 1, z)))
                {
                    return false;
                }
            }
        }
        return true;
    }

    /**
     * Routes staff around all three enlarged wet cages. The seven-wide deck
     * moves east before the first cage wall, stays outside the x=62 shell, and
     * bends back through a pressure door at the east end of the shared gallery.
     */
    private static int hangarRouteCentreX(BlockPos origin, int laneX, int z)
    {
        if (z >= SHAFT_NORTH_EDGE_Z)
        {
            return EAST_SHAFT_GAP_X;
        }
        int cageBypass = Math.min(HANGAR_SERVICE_SPINE_X,
                EAST_SHAFT_GAP_X
                        + (SHAFT_NORTH_EDGE_Z - z) * 3);
        if (cageBypass < HANGAR_SERVICE_SPINE_X)
        {
            return cageBypass;
        }
        if (z >= EvaHangarBuilder.GALLERY_Z)
        {
            return HANGAR_SERVICE_SPINE_X;
        }
        return Math.max(HANGAR_GALLERY_DOOR_X,
                HANGAR_SERVICE_SPINE_X
                        - (EvaHangarBuilder.GALLERY_Z - z) * 2);
    }

    /**
     * The command transit arrives on x=0 immediately south of the shaft
     * shells. This short east-west dogleg enters the safe x=21 gap before the
     * northbound ramp reaches the central and EVA-02 launch columns.
     */
    private static void buildHangarRouteEntryDogleg(ServerLevel level,
                                                     BlockPos origin)
    {
        for (int x = 0; x <= EAST_SHAFT_GAP_X; x++)
        {
            for (int z = SOUTH_INTERCHANGE_Z;
                 z <= SOUTH_INTERCHANGE_Z + 2; z++)
            {
                set(level, origin.offset(x, 1, z),
                        x == EAST_SHAFT_GAP_X
                                ? Blocks.PURPLE_CONCRETE.defaultBlockState()
                                : Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                for (int y = 2; y <= 5; y++)
                {
                    set(level, origin.offset(x, y, z),
                            Blocks.AIR.defaultBlockState());
                }
                set(level, origin.offset(x, 6, z),
                        Math.floorMod(x, 7) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.IRON_BLOCK.defaultBlockState());
            }
            if (x > 3)
            {
                for (int y = 2; y <= 5; y++)
                {
                    set(level, origin.offset(x, y,
                            SOUTH_INTERCHANGE_Z + 3),
                            com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
                }
            }
            if (x < EAST_SHAFT_GAP_X - 3)
            {
                for (int y = 2; y <= 5; y++)
                {
                    set(level, origin.offset(x, y,
                            SOUTH_INTERCHANGE_Z - 1),
                            com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
                }
            }
        }
    }

    private static boolean hasConnectedLowerRoutes(ServerLevel level, BlockPos origin)
    {
        for (int z = SOUTH_INTERCHANGE_Z; z <= 36; z++)
        {
            if (z > -18 || z < -28)
            {
                // The exterior command bridge deliberately rises one block at
                // z=35.  Audit the player's feet above that deck instead of
                // mistaking the accessible transition for an obstruction.
                int feetY = z >= 35 ? 3 : 2;
                if (!walkable(level, origin.offset(0, feetY, z)))
                {
                    return false;
                }
            }
        }
        for (int laneX : TRANSIT_X)
        {
            int minimum = Math.min(0, laneX);
            int maximum = Math.max(0, laneX);
            for (int x = minimum; x <= maximum; x++)
            {
                if (!walkable(level, origin.offset(x, 2, -23)))
                {
                    return false;
                }
            }
            for (int z = SOUTH_INTERCHANGE_Z; z <= -28; z++)
            {
                if (!walkable(level, origin.offset(laneX, 2, z)))
                {
                    return false;
                }
            }
        }
        for (int step = 0; step <= 5; step++)
        {
            int y = 2 + step;
            int z = 22 - step;
            if (!level.getBlockState(origin.offset(-13, y, z))
                    .is(Blocks.SMOOTH_QUARTZ_STAIRS)
                    || !level.getBlockState(origin.offset(-13, y + 1, z)).isAir()
                    || !level.getBlockState(origin.offset(-13, y + 2, z)).isAir())
            {
                return false;
            }
        }
        return true;
    }

    private static boolean hasSafeAnnexRoutes(ServerLevel level,
                                               BlockPos origin)
    {
        for (int x = -29; x <= 29; x++)
        {
            for (int z = 95; z <= 97; z++)
            {
                if (!walkable(level, origin.offset(x, -4, z)))
                {
                    return false;
                }
            }
        }
        for (int x = -55; x <= -30; x++)
        {
            if (!walkable(level, origin.offset(x, -4, 94)))
            {
                return false;
            }
        }
        for (int x = 30; x <= 55; x++)
        {
            if (!walkable(level, origin.offset(x, -4, 94)))
            {
                return false;
            }
        }
        for (int z = 72; z <= 94; z++)
        {
            if (!walkable(level, origin.offset(-32, -4, z)))
            {
                return false;
            }
            if (!walkable(level, origin.offset(53, -4, z)))
            {
                return false;
            }
        }
        for (int z = -39; z <= -33; z++)
        {
            if (!walkable(level, origin.offset(-1, -20, z)))
            {
                return false;
            }
        }
        for (int x = COMMAND_SPINE_X; x <= -1; x++)
        {
            if (!walkable(level, origin.offset(x, -20, -39)))
            {
                return false;
            }
        }
        for (int z = -40; z >= -61; z--)
        {
            int floorY = -20 + (-z - 40);
            if (!walkable(level, origin.offset(COMMAND_SPINE_X,
                    floorY + 1, z)))
            {
                return false;
            }
        }
        for (int x = COMMAND_SPINE_X; x <= 0; x++)
        {
            if (!walkable(level, origin.offset(x, 2,
                    SOUTH_INTERCHANGE_Z)))
            {
                return false;
            }
        }
        return true;
    }
    private static boolean walkable(ServerLevel level, BlockPos feet)
    {
        level.getChunkAt(feet);
        BlockPos floor = feet.below();
        BlockState floorState = level.getBlockState(floor);
        return !floorState.isAir()
                && floorState.getFluidState().isEmpty()
                && !floorState.getCollisionShape(level, floor).isEmpty()
                && level.getBlockState(feet).isAir()
                && level.getBlockState(feet.above()).isAir();
    }

    private static String routeDiagnostics(ServerLevel level, BlockPos origin,
                                           OperationsAudit audit)
    {
        if (!audit.connectedRoutes())
        {
            for (int z = SOUTH_INTERCHANGE_Z; z <= 36; z++)
            {
                if (z > -18 || z < -28)
                {
                    int feetY = z >= 35 ? 3 : 2;
                    BlockPos feet = origin.offset(0, feetY, z);
                    if (!walkable(level, feet))
                    {
                        return "lower-main " + describeWalkable(level, feet);
                    }
                }
            }
            for (int laneX : TRANSIT_X)
            {
                int minimum = Math.min(0, laneX);
                int maximum = Math.max(0, laneX);
                for (int x = minimum; x <= maximum; x++)
                {
                    BlockPos feet = origin.offset(x, 2, -23);
                    if (!walkable(level, feet))
                    {
                        return "lower-cross " + describeWalkable(level, feet);
                    }
                }
                for (int z = SOUTH_INTERCHANGE_Z; z <= -28; z++)
                {
                    BlockPos feet = origin.offset(laneX, 2, z);
                    if (!walkable(level, feet))
                    {
                        return "lower-lane " + describeWalkable(level, feet);
                    }
                }
            }
            return "lower-stair contract failed";
        }
        if (!audit.hangarRoutes())
        {
            int galleryDoorZ = EvaHangarBuilder.GALLERY_Z - 7;
            for (int laneX : HANGAR_ROUTE_LANES)
            {
                for (int z = SOUTH_INTERCHANGE_Z;
                     z >= galleryDoorZ; z--)
                {
                    int routeX = hangarRouteCentreX(origin, laneX, z);
                    int rise = Math.min(EvaHangarBuilder.GALLERY_Y - 1,
                            Math.max(0, (-z - 61) / 2));
                    BlockPos feet = origin.offset(routeX, 2 + rise, z);
                    if (!walkable(level, feet))
                    {
                        return "hangar-lane " + describeWalkable(level, feet);
                    }
                }
            }
        }
        if (!audit.facilityLinks())
        {
            return "facility-links west="
                    + describeBlock(level, origin.offset(
                            -30, OPERATIONS_FLOOR_Y, 12))
                    + " east=" + describeBlock(level,
                    origin.offset(24, 1, -23))
                    + " diagram=" + describeBlock(level,
                    origin.offset(-21, 4, -17));
        }
        if (!audit.safeAnnex())
        {
            return safeAnnexDiagnostics(level, origin);
        }
        return "physical console or facility marker failed";
    }

    private static String safeAnnexDiagnostics(ServerLevel level,
                                               BlockPos origin)
    {
        Object[][] blocks = {
                {"gallery-floor", 1, -5, 95, Blocks.POLISHED_DEEPSLATE},
                {"gallery-glass", 0, -2, 98, Blocks.GRAY_STAINED_GLASS},
                {"briefing-display", -43, 0, 71, Blocks.RED_STAINED_GLASS},
                {"medical-bed", 39, -4, 82, Blocks.SMOOTH_QUARTZ_SLAB},
                {"west-route", -18, -5, 94, Blocks.ORANGE_CONCRETE},
                {"east-route", 18, -5, 94, Blocks.RED_CONCRETE},
                {"vestibule-floor", -1, -21, -34, Blocks.POLISHED_BLACKSTONE},
                {"vestibule-frame", -3, -18, -42, Blocks.ORANGE_CONCRETE},
                {"operations-west-wall", 24, 20, 70, Blocks.DEEPSLATE_BRICKS},
                {"operations-north-wall", 10, 20, 84, Blocks.DEEPSLATE_BRICKS},
                {"operations-ceiling", 0, 36, 70, Blocks.DEEPSLATE_BRICKS},
                {"envelope-west", -30, 20, 40, com.projectseele.world.NervMaterials.structuralBlock()},
                {"envelope-east", 30, 20, 40, com.projectseele.world.NervMaterials.structuralBlock()},
                {"envelope-roof", 20, 58, 40, Blocks.DEEPSLATE_TILES},
                {"envelope-floor", 0, -22, 40, Blocks.POLISHED_DEEPSLATE},
                {"rear-landing", 0, 7, 87, Blocks.POLISHED_DEEPSLATE},
        };
        for (Object[] witness : blocks)
        {
            BlockPos position = origin.offset((int) witness[1],
                    (int) witness[2], (int) witness[3]);
            if (!level.getBlockState(position).is((Block) witness[4]))
            {
                return "support-annex " + witness[0] + " "
                        + position.toShortString() + " expected="
                        + ((Block) witness[4]).getDescriptionId()
                        + " actual=" + describeBlock(level, position);
            }
        }
        int[][] air = {
                {-18, -4, 94}, {0, -4, 94}, {18, -4, 94},
                {-1, -20, -33}, {-1, -18, -42},
                {0, 8, 84}, {0, 8, 87}, {0, 2, -35},
        };
        for (int[] witness : air)
        {
            BlockPos position = origin.offset(
                    witness[0], witness[1], witness[2]);
            if (!level.getBlockState(position).isAir())
            {
                return "support-annex aperture " + position.toShortString()
                        + " actual=" + describeBlock(level, position);
            }
        }
        for (int x = -29; x <= 29; x++)
        {
            for (int z = 95; z <= 97; z++)
            {
                BlockPos feet = origin.offset(x, -4, z);
                if (!walkable(level, feet))
                {
                    return "support-gallery " + describeWalkable(level, feet);
                }
            }
        }
        for (int x = -55; x <= -30; x++)
        {
            BlockPos feet = origin.offset(x, -4, 94);
            if (!walkable(level, feet))
            {
                return "briefing-route " + describeWalkable(level, feet);
            }
        }
        for (int x = 30; x <= 55; x++)
        {
            BlockPos feet = origin.offset(x, -4, 94);
            if (!walkable(level, feet))
            {
                return "medical-route " + describeWalkable(level, feet);
            }
        }
        for (int z = 72; z <= 94; z++)
        {
            for (int x : new int[] {-32, 53})
            {
                BlockPos feet = origin.offset(x, -4, z);
                if (!walkable(level, feet))
                {
                    return "support-room aisle "
                            + describeWalkable(level, feet);
                }
            }
        }
        for (int z = -39; z <= -33; z++)
        {
            BlockPos feet = origin.offset(-1, -20, z);
            if (!walkable(level, feet))
            {
                return "vestibule-route " + describeWalkable(level, feet);
            }
        }
        for (int x = COMMAND_SPINE_X; x <= -1; x++)
        {
            BlockPos feet = origin.offset(x, -20, -39);
            if (!walkable(level, feet))
            {
                return "lower-landing " + describeWalkable(level, feet);
            }
        }
        for (int z = -40; z >= -61; z--)
        {
            int floorY = -20 + (-z - 40);
            BlockPos feet = origin.offset(COMMAND_SPINE_X,
                    floorY + 1, z);
            if (!walkable(level, feet))
            {
                return "access-spine " + describeWalkable(level, feet);
            }
        }
        for (int x = COMMAND_SPINE_X; x <= 0; x++)
        {
            BlockPos feet = origin.offset(x, 2, SOUTH_INTERCHANGE_Z);
            if (!walkable(level, feet))
            {
                return "upper-landing " + describeWalkable(level, feet);
            }
        }
        return "support-annex unknown static contract";
    }

    private static String describeBlock(ServerLevel level, BlockPos position)
    {
        return level.getBlockState(position).getBlock().getDescriptionId();
    }

    private static String describeWalkable(ServerLevel level, BlockPos feet)
    {
        BlockPos floor = feet.below();
        return feet.toShortString() + " floor="
                + level.getBlockState(floor).getBlock().getDescriptionId()
                + " feet=" + level.getBlockState(feet).getBlock().getDescriptionId()
                + " head=" + level.getBlockState(feet.above())
                .getBlock().getDescriptionId();
    }

    private static void repairConnectedLowerRoutes(ServerLevel level,
                                                    BlockPos origin)
    {
        for (int z = SOUTH_INTERCHANGE_Z; z <= 36; z++)
        {
            if (z > -18 || z < -28)
            {
                int feetY = z >= 35 ? 3 : 2;
                BlockState floor = z >= 35
                        ? Blocks.IRON_BLOCK.defaultBlockState()
                        : z < -28
                        ? Blocks.PURPLE_CONCRETE.defaultBlockState()
                        : Blocks.POLISHED_BLACKSTONE.defaultBlockState();
                repairWalkway(level, origin.offset(0, feetY, z), floor);
            }
        }
        for (int laneX : TRANSIT_X)
        {
            BlockState laneFloor = laneX < 0
                    ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                    : laneX > 0
                    ? Blocks.RED_CONCRETE.defaultBlockState()
                    : Blocks.PURPLE_CONCRETE.defaultBlockState();
            int minimum = Math.min(0, laneX);
            int maximum = Math.max(0, laneX);
            for (int x = minimum; x <= maximum; x++)
            {
                repairWalkway(level, origin.offset(x, 2, -23),
                        Blocks.POLISHED_BLACKSTONE.defaultBlockState());
            }
            for (int z = SOUTH_INTERCHANGE_Z; z <= -28; z++)
            {
                repairWalkway(level, origin.offset(laneX, 2, z), laneFloor);
            }
        }

        BlockState stair = Blocks.SMOOTH_QUARTZ_STAIRS.defaultBlockState()
                .setValue(StairBlock.FACING, Direction.NORTH);
        for (int step = 0; step <= 5; step++)
        {
            int y = 2 + step;
            int z = 22 - step;
            BlockPos position = origin.offset(-13, y, z);
            level.getChunkAt(position);
            set(level, position, stair);
            set(level, position.above(), Blocks.AIR.defaultBlockState());
            set(level, position.above(2), Blocks.AIR.defaultBlockState());
        }
    }

    private static void repairWalkway(ServerLevel level, BlockPos feet,
                                       BlockState replacementFloor)
    {
        level.getChunkAt(feet);
        BlockPos floor = feet.below();
        BlockState currentFloor = level.getBlockState(floor);
        if (currentFloor.isAir()
                || !currentFloor.getFluidState().isEmpty()
                || currentFloor.getCollisionShape(level, floor).isEmpty())
        {
            set(level, floor, replacementFloor);
        }
        set(level, feet, Blocks.AIR.defaultBlockState());
        set(level, feet.above(), Blocks.AIR.defaultBlockState());
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

    public record OperationsAudit(boolean valid, boolean entrance,
                                  boolean tacticalTable, boolean display,
                                  boolean stairs, int consoles,
                                  int transitLinks, boolean connectedRoutes,
                                  boolean hangarRoutes, boolean facilityLinks,
                                  boolean videoWall, boolean safeAnnex,
                                  int telemetryScreens,
                                  NervOperationsConsole.ConsoleAudit commandConsole)
    {
        public boolean runtimePhysicalValid()
        {
            return this.entrance && this.tacticalTable && this.display
                    && this.stairs && this.consoles == 3
                    && this.transitLinks == 3 && this.connectedRoutes
                    && this.hangarRoutes && this.facilityLinks
                    && this.videoWall && this.safeAnnex
                    && this.commandConsole.physicalValid();
        }

        public String summary()
        {
            return String.format(Locale.ROOT,
                    "valid=%s entrance=%s tacticalTable=%s display=%s stairs=%s "
                            + "consoles=%d/3 transit=%d/3 connectedRoutes=%s "
                            + "hangarRoutes=%s facilityLinks=%s videoWall=%s safeAnnex=%s",
                    this.valid, this.entrance, this.tacticalTable, this.display,
                    this.stairs, this.consoles, this.transitLinks,
                    this.connectedRoutes, this.hangarRoutes,
                    this.facilityLinks, this.videoWall, this.safeAnnex)
                    + String.format(Locale.ROOT, " telemetry=%d/%d",
                    this.telemetryScreens, NervCommandTelemetry.SCREEN_COUNT)
                    + " commandConsole={" + this.commandConsole.summary() + "}";
        }
    }
}
