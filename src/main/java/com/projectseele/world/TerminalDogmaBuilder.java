package com.projectseele.world;

import java.util.Locale;

import com.projectseele.entity.LilithEntity;
import com.projectseele.registry.ModEntities;
import com.projectseele.registry.ModFluids;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.LadderBlock;
import net.minecraft.world.level.block.state.BlockState;

/**
 * Physical Central-Dogma descent and the sealed Terminal-Dogma chamber.
 *
 * <p>The downloaded command module ends at the eastern edge of the lower
 * concourse.  This builder starts there, outside its bounding box, and keeps
 * every deep facility below the imported GeoFront shell.  The player can walk
 * and climb the complete route; the command shortcut is never required.</p>
 */
public final class TerminalDogmaBuilder
{
    /** Moves the complete deep facility down while its shaft still opens at NERV. */
    public static final int FACILITY_Y_OFFSET = -64;
    public static final int SHAFT_X = 42;
    public static final int SHAFT_Z = -23;
    public static final int SHAFT_TOP_Y = 65;
    public static final int SHAFT_BOTTOM_Y = -59;
    public static final int CHAMBER_CENTRE_Y = -58;
    /*
     * Terminal Dogma must read as a buried containment cathedral, not a room
     * wrapped tightly around Lilith. The specimen and crucifix retain their
     * reviewed scale while the shell recedes into darkness around them.
     */
    public static final int CHAMBER_RADIUS_X = 38;
    public static final int CHAMBER_RADIUS_Y = 30;
    public static final int CHAMBER_RADIUS_Z = 46;
    public static final int OBSERVATION_Y = -59;
    public static final int OBSERVATION_Z = 34;
    public static final int LCL_SURFACE_Y = -75;
    public static final int MIN_RELATIVE_Y =
            CHAMBER_CENTRE_Y - CHAMBER_RADIUS_Y;

    private static final int UPDATE_CLIENTS = Block.UPDATE_CLIENTS;
    private static final int SHAFT_RADIUS = 5;
    private static final BlockPos LEGACY_REVISION_MARKER =
            new BlockPos(26, SHAFT_BOTTOM_Y, 8);
    private static final BlockPos REVISION_MARKER =
            new BlockPos(34, SHAFT_BOTTOM_Y, 8);

    private TerminalDogmaBuilder() {}

    public static TerminalDogmaAudit build(ServerLevel level, BlockPos origin)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return inspect(level, origin);
        PerformanceCounters.recordBuilderCall();
        BlockPos facilityOrigin = origin.offset(0, FACILITY_Y_OFFSET, 0);
        buildChamber(level, facilityOrigin);
        buildLclSealLake(level, facilityOrigin);
        buildContainmentCross(level, facilityOrigin);
        spawnLilith(level, facilityOrigin);
        buildObservationCatwalk(level, facilityOrigin);
        buildQuarantineVestibule(level, facilityOrigin);
        buildContainmentLighting(level, facilityOrigin);
        buildCentralDogmaShaft(level, facilityOrigin);
        buildTopAccess(level, facilityOrigin);
        buildDeepAccess(level, facilityOrigin);
        clear(level, facilityOrigin.offset(LEGACY_REVISION_MARKER));
        clear(level, facilityOrigin.offset(LEGACY_REVISION_MARKER).west());
        clear(level, facilityOrigin.offset(LEGACY_REVISION_MARKER).east());
        set(level, facilityOrigin.offset(REVISION_MARKER),
                Blocks.NETHERITE_BLOCK.defaultBlockState());
        set(level, facilityOrigin.offset(REVISION_MARKER).west(),
                Blocks.MAGENTA_CONCRETE.defaultBlockState());
        set(level, facilityOrigin.offset(REVISION_MARKER).east(),
                Blocks.LODESTONE.defaultBlockState());
        return inspect(level, origin);
    }

    /** Applies the canonical chamber/secure-access revision to an old save once. */
    public static TerminalDogmaAudit ensureRevision(ServerLevel level,
                                                    BlockPos origin)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return inspect(level, origin);
        if(TvDetailR04Layout.active(level))return inspect(level,origin);
        if (FacilityWorldPolicy.isS22Coastal(level.getServer()))
        {
            // S22 owns a separately audited vertical seal cathedral. Never
            // replace it with the retired R28 flooded ellipsoid.
            return inspect(level, origin);
        }
        TerminalDogmaAudit audit = inspect(level, origin);
        if (!audit.revision())
        {
            audit = build(level, origin);
        }
        return audit;
    }

    /**
     * Restores the bounded access pieces which shared NERV corridor builders
     * are allowed to touch.  The containment cavern itself is intentionally
     * not regenerated here: doing so during a launch check rewrites hundreds
     * of thousands of blocks and used to make Operations appear frozen.
     */
    public static TerminalDogmaAudit repairRuntimeAccess(ServerLevel level,
                                                          BlockPos origin)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return inspect(level, origin);
        if(TvDetailR04Layout.active(level)){repairRuntimeSpecimen(level,origin);return inspect(level,origin);}
        if (FacilityWorldPolicy.isS22Coastal(level.getServer()))
        {
            repairRuntimeSpecimen(level, origin);
            return inspect(level, origin);
        }
        TerminalDogmaAudit audit = ensureRevision(level, origin);
        if (audit.valid())
        {
            // Block witnesses can already describe the revised south-wall
            // chamber while an entity saved by the old revision still hangs
            // on the north cross. Reconcile the specimen even on a valid
            // block audit; the loaded entity is moved in place, not cloned.
            repairRuntimeSpecimen(level, origin);
            return inspect(level, origin);
        }

        BlockPos facilityOrigin = origin.offset(0, FACILITY_Y_OFFSET, 0);
        if (!audit.shaft() || !audit.topAccess() || !audit.deepAccess())
        {
            buildCentralDogmaShaft(level, facilityOrigin);
            buildTopAccess(level, facilityOrigin);
            buildDeepAccess(level, facilityOrigin);
        }
        if (!audit.observation())
        {
            buildObservationCatwalk(level, facilityOrigin);
        }
        if (!audit.secureVestibule())
        {
            buildQuarantineVestibule(level, facilityOrigin);
        }
        if (!audit.lclSeal())
        {
            buildLclSealLake(level, facilityOrigin);
        }
        if (!audit.containmentCross())
        {
            buildContainmentCross(level, facilityOrigin);
        }
        if (!audit.chamber())
        {
            repairChamberAuditAnchors(level, facilityOrigin);
        }
        repairRuntimeSpecimen(level, origin);
        return inspect(level, origin);
    }

    /**
     * Upgrades an installed save without rebuilding the complete chamber.
     * The legacy quartz marker is intentionally specific so normal logins only
     * perform one bounded entity query and never rewrite the crucifix.
     */
    public static boolean repairRuntimeSpecimen(ServerLevel level,
                                                BlockPos origin)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return false;
        BlockPos facilityOrigin = origin.offset(0, FACILITY_Y_OFFSET, 0);
        // Entity queries only see loaded sections. Runtime repairs used to
        // interpret an unloaded specimen chunk as "Lilith missing" and create
        // another persistent 11k-triangle entity at the same coordinates.
        // Old test saves accumulated more than one hundred identical Liliths,
        // producing severe FPS loss while the player merely stood in NERV.
        BlockPos expectedAnchor = specimenAnchor(level, facilityOrigin);
        level.getChunkAt(expectedAnchor);
        if (!level.areEntitiesLoaded(net.minecraft.world.level.ChunkPos.asLong(expectedAnchor)))
        {
            // FULL block data can arrive before its saved entities. A block
            // load alone must not be interpreted as an empty specimen slot.
            return false;
        }
        if(TvDetailR04Layout.active(level))
        {
            BlockPos oldSouth=facilityOrigin.offset(0,LCL_SURFACE_Y,22);
            level.getChunkAt(oldSouth);
            if(!level.areEntitiesLoaded(net.minecraft.world.level.ChunkPos.asLong(oldSouth)))return false;
        }
        if (!FacilityWorldPolicy.isS22Coastal(level.getServer()))
        {
            // Load the retired north-cross anchor as well. Otherwise an old
            // Lilith can remain invisible to the AABB query, then reappear as
            // a second high-poly entity after the player approaches it.
            BlockPos retiredAnchor = facilityOrigin.offset(0, LCL_SURFACE_Y, -22);
            level.getChunkAt(retiredAnchor);
            if (!level.areEntitiesLoaded(net.minecraft.world.level.ChunkPos.asLong(retiredAnchor)))
            {
                return false;
            }
        }
        AABB bounds = specimenBounds(level,facilityOrigin);
        var specimens = level.getEntitiesOfClass(LilithEntity.class, bounds);
        boolean missing = specimens.isEmpty();
        boolean misplaced = !missing
                && (specimens.size() > 1
                || TvDetailR04Layout.active(level) && Math.abs(specimens.get(0).getContainmentScale()-1.65F)>.001F
                || specimens.get(0).distanceToSqr(
                Vec3.atBottomCenterOf(expectedAnchor)) > 1.0D);
        if (FacilityWorldPolicy.isS22Coastal(level.getServer()))
        {
            if (missing)
            {
                // Only restore the specimen entity. The S22 crucifix and
                // pressure shell are an authored offline packet.
                spawnLilith(level, facilityOrigin);
            }
            else if (misplaced)
            {
                moveSpecimens(level, facilityOrigin, specimens);
            }
            return !level.getEntitiesOfClass(LilithEntity.class,
                    bounds).isEmpty();
        }
        BlockState legacyMarker = level.getBlockState(
                facilityOrigin.offset(0, -43, -22));
        boolean legacy = legacyMarker.is(Blocks.SMOOTH_QUARTZ)
                || legacyMarker.is(Blocks.QUARTZ_BLOCK)
                || legacyMarker.is(Blocks.CALCITE);
        if (missing || legacy || misplaced)
        {
            // Runtime owns only the specimen entity. The south-wall cross is
            // now a human-authored offline asset and must never be rewritten
            // merely because a legacy marker survives elsewhere in R28.
            if (missing)
            {
                spawnLilith(level, facilityOrigin);
            }
            else
            {
                moveSpecimens(level, facilityOrigin, specimens);
            }
        }
        return !level.getEntitiesOfClass(LilithEntity.class,
                bounds).isEmpty();
    }
    public static TerminalDogmaAudit inspect(ServerLevel level, BlockPos origin)
    {
        if(TvDetailR04Layout.active(level))
        {
            boolean entry=isWalkable(level,new BlockPos(12,-567,270));
            boolean observation=isWalkable(level,new BlockPos(30,-567,290));
            boolean lake=level.getFluidState(new BlockPos(30,-601,325)).getFluidType()==ModFluids.LCL_TYPE.get();
            boolean cross=level.getBlockState(new BlockPos(30,-566,361)).is(Blocks.RED_CONCRETE);
            boolean shell=level.getBlockState(new BlockPos(30,-532,332)).is(Blocks.BLACK_CONCRETE);
            boolean specimen=!level.getEntitiesOfClass(LilithEntity.class,TvDetailR04Layout.specimenBounds()).isEmpty();
            return new TerminalDogmaAudit(entry&&observation&&lake&&cross&&shell&&specimen,true,entry,0,true,entry,entry,shell,lake,cross,specimen,observation,entry);
        }
        origin = origin.offset(0, FACILITY_Y_OFFSET, 0);
        boolean revision = level.getBlockState(origin.offset(REVISION_MARKER))
                .is(Blocks.NETHERITE_BLOCK)
                && level.getBlockState(origin.offset(REVISION_MARKER).west())
                .is(Blocks.MAGENTA_CONCRETE)
                && level.getBlockState(origin.offset(REVISION_MARKER).east())
                .is(Blocks.LODESTONE);
        boolean topAccess = isWalkable(level,
                origin.offset(34, SHAFT_TOP_Y, SHAFT_Z));
        int ladders = 0;
        for (int y = SHAFT_BOTTOM_Y + 1; y <= SHAFT_TOP_Y + 1; y++)
        {
            if (level.getBlockState(origin.offset(
                    SHAFT_X, y, SHAFT_Z - 4)).is(Blocks.LADDER))
            {
                ladders++;
            }
        }
        boolean shaftApertures = level.getBlockState(origin.offset(
                SHAFT_X, -11, SHAFT_Z - 3)).isAir()
                && level.getBlockState(origin.offset(
                SHAFT_X, -23, SHAFT_Z - 3)).isAir();
        boolean shaft = ladders == SHAFT_TOP_Y - SHAFT_BOTTOM_Y + 1
                && level.getBlockState(origin.offset(
                SHAFT_X, SHAFT_BOTTOM_Y, SHAFT_Z)).is(Blocks.LODESTONE)
                && shaftApertures;
        boolean deepAccess = isWalkable(level,
                origin.offset(24, SHAFT_BOTTOM_Y, -10));
        boolean chamber = level.getBlockState(origin.offset(
                0, CHAMBER_CENTRE_Y + CHAMBER_RADIUS_Y, 0))
                .is(Blocks.CALCITE)
                && level.getBlockState(origin.offset(
                0, CHAMBER_CENTRE_Y, -CHAMBER_RADIUS_Z))
                .is(Blocks.POLISHED_BASALT)
                && level.getBlockState(origin.offset(
                0, -58, -12)).is(Blocks.LIGHT);
        boolean lclSeal = level.getFluidState(origin.offset(
                0, LCL_SURFACE_Y, 0)).getFluidType()
                == ModFluids.LCL_TYPE.get();
        boolean containmentCross = level.getBlockState(origin.offset(
                0, -50, 25)).is(Blocks.REDSTONE_BLOCK)
                && level.getBlockState(origin.offset(
                20, -50, 23)).is(Blocks.RED_STAINED_GLASS);
        boolean sealedSpecimen = !level.getEntitiesOfClass(LilithEntity.class,
                AABB.ofSize(Vec3.atCenterOf(origin.offset(0, -59, 0)),
                        64.0D, 48.0D, 96.0D)).isEmpty();
        boolean observation = level.getBlockState(origin.offset(
                0, OBSERVATION_Y, OBSERVATION_Z)).is(Blocks.LODESTONE)
                && level.getBlockState(origin.offset(
                35, -68, 28)).is(Blocks.LADDER);
        boolean secureVestibule = isWalkable(level,
                origin.offset(24, SHAFT_BOTTOM_Y, 10))
                && level.getBlockState(origin.offset(
                20, SHAFT_BOTTOM_Y + 3, 10))
                .is(Blocks.RED_STAINED_GLASS);
        if (FacilityWorldPolicy.isS22Coastal(level.getServer()))
        {
            boolean coastalRevision = level.getBlockState(
                    origin.offset(34, -61, 8)).is(Blocks.NETHERITE_BLOCK)
                    && level.getBlockState(origin.offset(33, -61, 8))
                    .is(Blocks.MAGENTA_CONCRETE)
                    && level.getBlockState(origin.offset(35, -61, 8))
                    .is(Blocks.LODESTONE);
            BlockState crown = level.getBlockState(
                    origin.offset(0, -22, 0));
            BlockState northRib = level.getBlockState(
                    origin.offset(0, -66, -48));
            boolean coastalChamber = isPressureShell(crown)
                    && isPressureShell(northRib);
            boolean coastalLcl = level.getFluidState(
                    origin.offset(0, -94, 0)).getFluidType()
                    == ModFluids.LCL_TYPE.get();
            boolean coastalCross = level.getBlockState(
                    origin.offset(0, -66, -28)).is(Blocks.REDSTONE_BLOCK);
            boolean coastalObservation = level.getBlockState(
                    origin.offset(0, -59, 34)).is(Blocks.LODESTONE);
            boolean coastalVestibule = isWalkable(level,
                    origin.offset(25, -59, -23));
            boolean coastalValid = coastalRevision && topAccess && shaft
                    && deepAccess && coastalChamber && coastalLcl
                    && coastalCross && sealedSpecimen
                    && coastalObservation && coastalVestibule;
            return new TerminalDogmaAudit(coastalValid, coastalRevision,
                    topAccess, ladders, shaftApertures, shaft,
                    deepAccess, coastalChamber, coastalLcl, coastalCross,
                    sealedSpecimen, coastalObservation, coastalVestibule);
        }
        boolean valid = revision && topAccess && shaft && deepAccess && chamber
                && lclSeal && containmentCross && sealedSpecimen
                && observation && secureVestibule;
        return new TerminalDogmaAudit(valid, revision, topAccess, ladders,
                shaftApertures, shaft,
                deepAccess, chamber, lclSeal, containmentCross,
                sealedSpecimen, observation, secureVestibule);
    }

    private static boolean isWalkable(ServerLevel level, BlockPos floor)
    {
        return !level.getBlockState(floor).isAir()
                && level.getBlockState(floor.above()).isAir()
                && level.getBlockState(floor.above(2)).isAir();
    }

    private static boolean isPressureShell(BlockState state)
    {
        return state.is(Blocks.POLISHED_BASALT)
                || state.is(Blocks.DEEPSLATE_TILES)
                || state.is(Blocks.DEEPSLATE_BRICKS);
    }

    private static void buildChamber(ServerLevel level, BlockPos origin)
    {
        for (int x = -CHAMBER_RADIUS_X; x <= CHAMBER_RADIUS_X; x++)
        {
            for (int y = -CHAMBER_RADIUS_Y; y <= CHAMBER_RADIUS_Y; y++)
            {
                for (int z = -CHAMBER_RADIUS_Z; z <= CHAMBER_RADIUS_Z; z++)
                {
                    double distance = square(x / (double) CHAMBER_RADIUS_X)
                            + square(y / (double) CHAMBER_RADIUS_Y)
                            + square(z / (double) CHAMBER_RADIUS_Z);
                    if (distance > 1.0D)
                    {
                        continue;
                    }
                    BlockPos position = origin.offset(
                            x, CHAMBER_CENTRE_Y + y, z);
                    if (distance >= 0.86D)
                    {
                        // Deliberate concentric ribs read as an engineered
                        // containment shell.  The previous random calcite
                        // flecks became bright visual noise and hid the
                        // crucifix at normal gameplay exposure.
                        boolean horizontalRib = Math.floorMod(y, 7) == 0;
                        boolean verticalRib = Math.floorMod(x + 24, 12) == 0
                                && Math.floorMod(z + 28, 8) <= 1;
                        BlockState shell = horizontalRib
                                ? Blocks.POLISHED_BASALT.defaultBlockState()
                                : (verticalRib
                                ? Blocks.DEEPSLATE_TILES.defaultBlockState()
                                : Blocks.DEEPSLATE_BRICKS.defaultBlockState());
                        set(level, position, shell);
                    }
                    else
                    {
                        clear(level, position);
                    }
                }
            }
        }

        // Deterministic audit ribs at the crown and east equator.
        set(level, origin.offset(0,
                CHAMBER_CENTRE_Y + CHAMBER_RADIUS_Y, 0),
                Blocks.CALCITE.defaultBlockState());
        // East is opened by the tunnel and both side equators are crossed by
        // the U-shaped observation deck. The sealed north rib is the stable
        // structural marker and never competes with a traversable route.
        set(level, origin.offset(0, CHAMBER_CENTRE_Y,
                -CHAMBER_RADIUS_Z),
                Blocks.POLISHED_BASALT.defaultBlockState());
    }

    private static void buildLclSealLake(ServerLevel level, BlockPos origin)
    {
        final int radiusX = 28;
        final int radiusZ = 20;
        for (int x = -30; x <= 30; x++)
        {
            for (int z = -22; z <= 22; z++)
            {
                double distance = square(x / (double) radiusX)
                        + square(z / (double) radiusZ);
                if (distance <= 1.0D)
                {
                    BlockState bed = Math.floorMod(x * 19 + z * 29, 17) == 0
                            ? Blocks.SEA_LANTERN.defaultBlockState()
                            : Blocks.ORANGE_CONCRETE.defaultBlockState();
                    set(level, origin.offset(x, -83, z), bed);
                    for (int y = -82; y <= LCL_SURFACE_Y; y++)
                    {
                        set(level, origin.offset(x, y, z),
                                ModFluids.LCL_SOURCE.get().defaultFluidState()
                                        .createLegacyBlock());
                    }
                }
                else if (distance <= 1.24D)
                {
                    set(level, origin.offset(x, LCL_SURFACE_Y, z),
                            Math.floorMod(x + z, 5) == 0
                                    ? Blocks.SEA_LANTERN.defaultBlockState()
                                    : Blocks.POLISHED_BLACKSTONE.defaultBlockState());
                }
            }
        }
    }

    private static void buildContainmentCross(ServerLevel level,
                                              BlockPos origin)
    {
        // Retire the north-wall crucifix and its old block-built silhouette.
        // The reviewed R28 arrival is now north of the chamber, so Lilith and
        // the luminous face belong on the south wall and face north.
        for (int x = -22; x <= 22; x++)
        {
            for (int y = -77; y <= -36; y++)
            {
                for (int z = -26; z <= -18; z++)
                {
                    clear(level, origin.offset(x, y, z));
                }
            }
        }
        // A luminous pure-red crucifix has to remain the first readable
        // silhouette even at the deliberately low Terminal-Dogma exposure.
        fillBox(level, origin, -4, 4, -77, -36, 24, 26,
                Blocks.REDSTONE_BLOCK.defaultBlockState());
        fillBox(level, origin, -21, 21, -55, -47, 24, 26,
                Blocks.REDSTONE_BLOCK.defaultBlockState());
        // Red glass in front of a sparse luminous core retains a pure-red
        // face instead of collapsing into a black shape under the chamber's
        // low ambient light.  The specimen is built afterwards and therefore
        // naturally occludes the cross at the body contact points.
        fillBox(level, origin, -4, 4, -77, -36, 23, 23,
                Blocks.RED_STAINED_GLASS.defaultBlockState());
        fillBox(level, origin, -21, 21, -55, -47, 23, 23,
                Blocks.RED_STAINED_GLASS.defaultBlockState());
        for (int y = -76; y <= -37; y += 4)
        {
            set(level, origin.offset(0, y, 24),
                    Blocks.SHROOMLIGHT.defaultBlockState());
        }
        for (int x = -20; x <= 20; x += 4)
        {
            set(level, origin.offset(x, -50, 24),
                    Blocks.SHROOMLIGHT.defaultBlockState());
        }
        // Remove every legacy block-built humanoid and spear. The reviewed local
        // Lilith mesh now supplies the mask, nails, body and Longinus restraint;
        // leaving the old quartz dummy behind it produced two overlapping
        // silhouettes. The bounded clear is intentionally retained as an
        // installed-world migration.
        for (int x = -22; x <= 22; x++)
        {
            for (int y = -77; y <= -36; y++)
            {
                for (int z = -23; z <= -18; z++)
                {
                    clear(level, origin.offset(x, y, z));
                }
            }
        }
        fillBox(level, origin, -4, 4, -77, -36, 23, 23,
                Blocks.RED_STAINED_GLASS.defaultBlockState());
        fillBox(level, origin, -21, 21, -55, -47, 23, 23,
                Blocks.RED_STAINED_GLASS.defaultBlockState());
    }

    private static void buildObservationCatwalk(ServerLevel level,
                                                BlockPos origin)
    {
        final int outerX = 36;
        final int innerX = 33;
        final int outerNorthZ = -40;
        final int innerSouthZ = 33;
        final int outerSouthZ = 36;
        for (int x = -outerX; x <= outerX; x++)
        {
            for (int z = outerNorthZ; z <= outerSouthZ; z++)
            {
                boolean deck = z >= innerSouthZ || Math.abs(x) >= innerX;
                if (!deck)
                {
                    continue;
                }
                set(level, origin.offset(x, OBSERVATION_Y, z),
                        Math.floorMod(x * 3 + z, 9) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.POLISHED_BLACKSTONE.defaultBlockState());
                for (int y = OBSERVATION_Y + 1;
                     y <= OBSERVATION_Y + 4; y++)
                {
                    clear(level, origin.offset(x, y, z));
                }
            }
        }
        // Rails on both the pressure-shell edge and the open containment edge
        // make the full U-shaped gallery survivable without reducing the
        // central crucifix to a view through a solid wall.
        for (int x = -outerX; x <= outerX; x++)
        {
            set(level, origin.offset(x, OBSERVATION_Y + 1,
                            outerSouthZ + 1),
                    Blocks.IRON_BARS.defaultBlockState());
            if (Math.abs(x) <= innerX)
            {
                set(level, origin.offset(x, OBSERVATION_Y + 1,
                                innerSouthZ - 1),
                        Blocks.IRON_BARS.defaultBlockState());
            }
        }
        for (int z = outerNorthZ; z <= outerSouthZ + 1; z++)
        {
            set(level, origin.offset(-outerX - 1,
                            OBSERVATION_Y + 1, z),
                    Blocks.IRON_BARS.defaultBlockState());
            set(level, origin.offset(outerX + 1,
                            OBSERVATION_Y + 1, z),
                    Blocks.IRON_BARS.defaultBlockState());
            if (z <= innerSouthZ - 1)
            {
                set(level, origin.offset(-innerX + 1,
                                OBSERVATION_Y + 1, z),
                        Blocks.IRON_BARS.defaultBlockState());
                set(level, origin.offset(innerX - 1,
                                OBSERVATION_Y + 1, z),
                        Blocks.IRON_BARS.defaultBlockState());
            }
        }
        set(level, origin.offset(0, OBSERVATION_Y, OBSERVATION_Z),
                Blocks.LODESTONE.defaultBlockState());

        // A second physical route descends from the gallery to the LCL rim.
        BlockState ladder = Blocks.LADDER.defaultBlockState()
                .setValue(LadderBlock.FACING, Direction.WEST);
        for (int y = -77; y <= OBSERVATION_Y + 1; y++)
        {
            set(level, origin.offset(36, y, 28),
                    Blocks.BLACK_CONCRETE.defaultBlockState());
            if (y > -77)
            {
                set(level, origin.offset(35, y, 28), ladder);
            }
        }
        for (int x = 28; x <= 35; x++)
        {
            for (int z = 24; z <= 31; z++)
            {
                set(level, origin.offset(x, -77, z),
                        Blocks.POLISHED_BLACKSTONE.defaultBlockState());
            }
        }
    }

    /**
     * Three open security frames turn the route from Central Dogma into a
     * readable high-clearance sequence without ever stranding a survival
     * player behind an unpowered iron door. The western glass looks directly
     * into the LCL production chamber; the eastern wall remains pressure-rated.
     */
    private static void buildQuarantineVestibule(ServerLevel level,
                                                 BlockPos origin)
    {
        int floorY = SHAFT_BOTTOM_Y;
        for (int z = 3; z <= 19; z++)
        {
            for (int x = 21; x <= 27; x++)
            {
                set(level, origin.offset(x, floorY, z),
                        Math.floorMod(z, 6) == 0
                                ? Blocks.RED_CONCRETE.defaultBlockState()
                                : Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                for (int y = floorY + 1; y <= floorY + 6; y++)
                {
                    clear(level, origin.offset(x, y, z));
                }
                set(level, origin.offset(x, floorY + 7, z),
                        Math.floorMod(z, 4) == 0
                                ? Blocks.REDSTONE_LAMP.defaultBlockState()
                                : com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
            }
            for (int y = floorY + 1; y <= floorY + 6; y++)
            {
                set(level, origin.offset(20, y, z),
                        y >= floorY + 2 && y <= floorY + 5
                                ? Blocks.RED_STAINED_GLASS.defaultBlockState()
                                : com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
                set(level, origin.offset(28, y, z),
                        com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
            }
        }

        for (int gateZ : new int[] {3, 11, 19})
        {
            for (int x = 20; x <= 28; x++)
            {
                for (int y = floorY + 1; y <= floorY + 6; y++)
                {
                    boolean aperture = x >= 22 && x <= 26
                            && y <= floorY + 5;
                    set(level, origin.offset(x, y, gateZ), aperture
                            ? Blocks.AIR.defaultBlockState()
                            : (x == 20 || x == 28
                            ? Blocks.RED_CONCRETE.defaultBlockState()
                            : Blocks.IRON_BLOCK.defaultBlockState()));
                }
            }
            set(level, origin.offset(24, floorY + 6, gateZ),
                    Blocks.REDSTONE_LAMP.defaultBlockState());
        }
    }

    private static void buildContainmentLighting(ServerLevel level,
                                                 BlockPos origin)
    {
        // Invisible light blocks preserve the black sealed-chamber material
        // while making the white giant, red cross and orange LCL readable.
        // They have no collision and therefore do not interrupt the gallery.
        for (int x = -30; x <= 30; x += 6)
        {
            for (int y : new int[] {-78, -68, -58, -48, -38})
            {
                set(level, origin.offset(x, y, -18),
                        Blocks.LIGHT.defaultBlockState());
                set(level, origin.offset(x, y, 18),
                        Blocks.LIGHT.defaultBlockState());
            }
        }
        for (int z = -34; z <= 28; z += 6)
        {
            set(level, origin.offset(-30, -54, z),
                    Blocks.LIGHT.defaultBlockState());
            set(level, origin.offset(30, -54, z),
                    Blocks.LIGHT.defaultBlockState());
        }
        for (int x : new int[] {-14, -9, 9, 14})
        {
            for (int y : new int[] {-60, -52, -44})
            {
                set(level, origin.offset(x, y, -19),
                        Blocks.LIGHT.defaultBlockState());
            }
        }
        // Stable interior witness used by the structural audit.  This point is
        // outside the specimen mesh and pedestrian deck, so later facility
        // passes have no legitimate reason to replace it.
        set(level, origin.offset(0, -58, -12),
                Blocks.LIGHT.defaultBlockState());
    }

    private static void repairChamberAuditAnchors(ServerLevel level,
                                                   BlockPos origin)
    {
        BlockPos crown = origin.offset(0,
                CHAMBER_CENTRE_Y + CHAMBER_RADIUS_Y, 0);
        BlockPos northRib = origin.offset(0, CHAMBER_CENTRE_Y,
                -CHAMBER_RADIUS_Z);
        if (level.getBlockState(crown).isAir()
                || level.getBlockState(northRib).isAir())
        {
            // A missing pressure-shell anchor means this is not merely a light
            // overwritten by a route pass; restore the complete sealed shell.
            buildChamber(level, origin);
        }
        set(level, crown, Blocks.CALCITE.defaultBlockState());
        set(level, northRib, Blocks.POLISHED_BASALT.defaultBlockState());
        set(level, origin.offset(0, -58, -12),
                Blocks.LIGHT.defaultBlockState());
    }

    private static void buildCentralDogmaShaft(ServerLevel level,
                                               BlockPos origin)
    {
        for (int y = SHAFT_BOTTOM_Y; y <= SHAFT_TOP_Y + 6; y++)
        {
            for (int x = -SHAFT_RADIUS; x <= SHAFT_RADIUS; x++)
            {
                for (int z = -SHAFT_RADIUS; z <= SHAFT_RADIUS; z++)
                {
                    BlockPos position = origin.offset(
                            SHAFT_X + x, y, SHAFT_Z + z);
                    if (y == SHAFT_BOTTOM_Y)
                    {
                        set(level, position,
                                Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                    }
                    else if (Math.abs(x) == SHAFT_RADIUS
                            || Math.abs(z) == SHAFT_RADIUS)
                    {
                        BlockState wall = Math.floorMod(y, 12) == 0
                                ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                                : Blocks.DEEPSLATE_TILES.defaultBlockState();
                        set(level, position, wall);
                    }
                    else
                    {
                        clear(level, position);
                    }
                }
            }
            if (y > SHAFT_BOTTOM_Y
                    && Math.floorMod(y - SHAFT_BOTTOM_Y, 6) == 0)
            {
                // Visible paired guide lights communicate the full descent
                // and give players a scale reference between landings.
                set(level, origin.offset(SHAFT_X - SHAFT_RADIUS,
                        y, SHAFT_Z), Blocks.SEA_LANTERN.defaultBlockState());
                set(level, origin.offset(SHAFT_X + SHAFT_RADIUS,
                        y, SHAFT_Z), Blocks.SEA_LANTERN.defaultBlockState());
            }
            if (y > SHAFT_BOTTOM_Y && Math.floorMod(y - SHAFT_BOTTOM_Y, 12) == 0)
            {
                for (int x = -3; x <= 4; x++)
                {
                    for (int z = -3; z <= 4; z++)
                    {
                        // A three-wide aperture beside the ladder keeps every
                        // landing climbable and exposes the vertical depth to
                        // the fixed inspection camera.
                        if (Math.abs(x) <= 1 && z <= -2)
                        {
                            clear(level, origin.offset(SHAFT_X + x, y,
                                    SHAFT_Z + z));
                            continue;
                        }
                        set(level, origin.offset(SHAFT_X + x, y,
                                SHAFT_Z + z),
                                Blocks.IRON_BLOCK.defaultBlockState());
                    }
                }
            }
            if (Math.floorMod(y, 8) == 0)
            {
                set(level, origin.offset(SHAFT_X, y, SHAFT_Z + 5),
                        Blocks.SEA_LANTERN.defaultBlockState());
            }
        }

        BlockState ladder = Blocks.LADDER.defaultBlockState()
                .setValue(LadderBlock.FACING, Direction.SOUTH);
        for (int y = SHAFT_BOTTOM_Y + 1; y <= SHAFT_TOP_Y + 1; y++)
        {
            set(level, origin.offset(SHAFT_X, y, SHAFT_Z - 4), ladder);
        }
        set(level, origin.offset(SHAFT_X, SHAFT_BOTTOM_Y, SHAFT_Z),
                Blocks.LODESTONE.defaultBlockState());
    }

    private static void buildTopAccess(ServerLevel level, BlockPos origin)
    {
        buildCorridorX(level, origin, 32, 37, SHAFT_TOP_Y, -26, -20);
        set(level, origin.offset(34, SHAFT_TOP_Y, SHAFT_Z),
                Blocks.ORANGE_CONCRETE.defaultBlockState());
    }

    private static void buildDeepAccess(ServerLevel level, BlockPos origin)
    {
        buildCorridorX(level, origin, 24, 37,
                SHAFT_BOTTOM_Y, -26, -20);
        for (int z = -23; z <= 2; z++)
        {
            for (int x = 21; x <= 27; x++)
            {
                set(level, origin.offset(x, SHAFT_BOTTOM_Y, z),
                        x == 24 && Math.floorMod(z, 5) < 2
                                ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                                : Blocks.POLISHED_BLACKSTONE.defaultBlockState());
                for (int y = SHAFT_BOTTOM_Y + 1;
                     y <= SHAFT_BOTTOM_Y + 6; y++)
                {
                    clear(level, origin.offset(x, y, z));
                }
                set(level, origin.offset(x, SHAFT_BOTTOM_Y + 7, z),
                        Math.floorMod(z, 6) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.IRON_BLOCK.defaultBlockState());
            }
            for (int y = SHAFT_BOTTOM_Y + 1;
                 y <= SHAFT_BOTTOM_Y + 6; y++)
            {
                set(level, origin.offset(20, y, z),
                        Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState());
                set(level, origin.offset(28, y, z),
                        Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState());
            }
        }
        set(level, origin.offset(24, SHAFT_BOTTOM_Y, -10),
                Blocks.LODESTONE.defaultBlockState());

        // Open quarantine ribs rather than a closed redstone door so the
        // route remains traversable in a fresh survival test world.
        for (int y = SHAFT_BOTTOM_Y + 1; y <= SHAFT_BOTTOM_Y + 6; y++)
        {
            set(level, origin.offset(20, y, -4),
                    Blocks.IRON_BLOCK.defaultBlockState());
            set(level, origin.offset(28, y, -4),
                    Blocks.IRON_BLOCK.defaultBlockState());
        }
        for (int x = 20; x <= 28; x++)
        {
            set(level, origin.offset(x, SHAFT_BOTTOM_Y + 7, -4),
                    x % 2 == 0 ? Blocks.REDSTONE_LAMP.defaultBlockState()
                            : Blocks.IRON_BLOCK.defaultBlockState());
        }
    }

    private static void buildCorridorX(ServerLevel level, BlockPos origin,
                                       int minX, int maxX, int floorY,
                                       int minZ, int maxZ)
    {
        for (int x = minX; x <= maxX; x++)
        {
            for (int z = minZ; z <= maxZ; z++)
            {
                set(level, origin.offset(x, floorY, z),
                        z == SHAFT_Z && Math.floorMod(x, 5) < 2
                                ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                                : Blocks.POLISHED_BLACKSTONE.defaultBlockState());
                for (int y = floorY + 1; y <= floorY + 5; y++)
                {
                    clear(level, origin.offset(x, y, z));
                }
                set(level, origin.offset(x, floorY + 6, z),
                        Math.floorMod(x, 6) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.IRON_BLOCK.defaultBlockState());
            }
            for (int y = floorY + 1; y <= floorY + 5; y++)
            {
                set(level, origin.offset(x, y, minZ - 1),
                        Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState());
                set(level, origin.offset(x, y, maxZ + 1),
                        Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState());
            }
        }
    }

    private static void spawnLilith(ServerLevel level, BlockPos origin)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        BlockPos anchor = specimenAnchor(level, origin);
        level.getChunkAt(anchor);
        AABB bounds = specimenBounds(level,origin);
        var specimens = level.getEntitiesOfClass(LilithEntity.class, bounds);
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
                anchor.getZ() + 0.5D, 0.0F, 0.0F);
        specimen.setNoAi(true);
        specimen.setNoGravity(true);
        specimen.setInvulnerable(true);
        specimen.setPersistenceRequired();
        specimen.addTag("projectseele.terminal_dogma_lilith");
        specimen.setContainmentScale(TvDetailR04Layout.active(level)?1.65F:1F);
        specimen.setHealth(specimen.getMaxHealth());
        if (created)
        {
            level.addFreshEntity(specimen);
        }
    }

    private static void moveSpecimens(ServerLevel level, BlockPos origin,
                                      java.util.List<LilithEntity> specimens)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        BlockPos anchor = specimenAnchor(level, origin);
        LilithEntity specimen = specimens.get(0);
        for (int index = 1; index < specimens.size(); index++)
        {
            specimens.get(index).discard();
        }
        specimen.moveTo(anchor.getX() + 0.5D, anchor.getY(),
                anchor.getZ() + 0.5D, 0.0F, 0.0F);
        specimen.setNoAi(true);
        specimen.setNoGravity(true);
        specimen.setInvulnerable(true);
        specimen.setPersistenceRequired();
        specimen.addTag("projectseele.terminal_dogma_lilith");
        specimen.setContainmentScale(TvDetailR04Layout.active(level)?1.65F:1F);
        specimen.setHealth(specimen.getMaxHealth());
    }

    private static BlockPos specimenAnchor(ServerLevel level, BlockPos origin)
    {
        if(TvDetailR04Layout.active(level))return TvDetailR04Layout.specimenAnchor();
        // S22 remains frozen on its separately reviewed north-wall layout.
        // R28 uses the south wall so the B-158 arrival sees Lilith head-on.
        int z = FacilityWorldPolicy.isS22Coastal(level.getServer()) ? -22 : 22;
        return origin.offset(0, LCL_SURFACE_Y, z);
    }


    private static AABB specimenBounds(ServerLevel level,BlockPos origin)
    {
        if(TvDetailR04Layout.active(level))return TvDetailR04Layout.specimenBounds();
        return AABB.ofSize(Vec3.atCenterOf(origin.offset(0, -59, 0)),
                64.0D, 48.0D, 96.0D);
    }
    private static void buildLine(ServerLevel level, BlockPos origin,
                                  int x0, int y0, int z0,
                                  int x1, int y1, int z1,
                                  BlockState state)
    {
        int steps = Math.max(Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)),
                Math.abs(z1 - z0));
        for (int step = 0; step <= steps; step++)
        {
            double amount = steps == 0 ? 0.0D : step / (double) steps;
            int x = (int) Math.round(x0 + (x1 - x0) * amount);
            int y = (int) Math.round(y0 + (y1 - y0) * amount);
            int z = (int) Math.round(z0 + (z1 - z0) * amount);
            set(level, origin.offset(x, y, z), state);
        }
    }

    private static void fillBox(ServerLevel level, BlockPos origin,
                                int minX, int maxX, int minY, int maxY,
                                int minZ, int maxZ, BlockState state)
    {
        for (int x = minX; x <= maxX; x++)
        {
            for (int y = minY; y <= maxY; y++)
            {
                for (int z = minZ; z <= maxZ; z++)
                {
                    set(level, origin.offset(x, y, z), state);
                }
            }
        }
    }

    private static double square(double value)
    {
        return value * value;
    }

    private static void clear(ServerLevel level, BlockPos position)
    {
        set(level, position, Blocks.AIR.defaultBlockState());
    }

    private static void set(ServerLevel level, BlockPos position,
                            BlockState state)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        if (!level.getBlockState(position).equals(state))
        {
            level.setBlock(position, state, UPDATE_CLIENTS);
            PerformanceCounters.recordWorldBlockWrites(1);
        }
    }

    public record TerminalDogmaAudit(boolean valid, boolean revision,
                                     boolean topAccess,
                                     int ladders, boolean shaftApertures,
                                     boolean shaft,
                                     boolean deepAccess, boolean chamber,
                                     boolean lclSeal,
                                     boolean containmentCross,
                                     boolean sealedSpecimen,
                                     boolean observation,
                                     boolean secureVestibule)
    {
        public String summary()
        {
            return String.format(Locale.ROOT,
                    "valid=%s revision=%s topAccess=%s ladder=%d/%d apertures=%s shaft=%s "
                            + "deepAccess=%s chamber=%s lclSeal=%s "
                            + "cross=%s specimen=%s observation=%s vestibule=%s",
                    this.valid, this.revision, this.topAccess, this.ladders,
                    SHAFT_TOP_Y - SHAFT_BOTTOM_Y + 1,
                    this.shaftApertures, this.shaft,
                    this.deepAccess, this.chamber, this.lclSeal,
                    this.containmentCross, this.sealedSpecimen,
                    this.observation, this.secureVestibule);
        }
    }
}
