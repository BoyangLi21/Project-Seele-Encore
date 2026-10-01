package com.projectseele.world;

import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.registry.ModEntities;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.Mth;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.AttachFace;
import net.minecraft.world.entity.Entity;

/**
 * One authoritative pedestrian topology for the complete NERV pyramid.
 *
 * <p>Individual facility builders still own their rooms. This class is written
 * last and owns only pressure corridors, lift shafts and their door thresholds,
 * so room revisions cannot silently strand another part of the headquarters.</p>
 */
public final class NervFacilityTopologyBuilder
{
    private static final int UPDATE_CLIENTS = Block.UPDATE_CLIENTS;
    private static final int CORRIDOR_RADIUS = 3;
    private static final int CORRIDOR_CLEAR_HEIGHT = 4;
    private static final int LIFT_RADIUS = 4;

    private static final BlockPos REVISION_MARKER =
            new BlockPos(108, -21, 140);
    private static final Map<UUID, LiftRide> ACTIVE_RIDES = new HashMap<>();

    private static final LiftSpec COMMAND_LIFT = new LiftSpec(
            "command", "B-20 / COMMAND SUPPORT", 0, 90,
            new int[] {-5, 7},
            new Direction[] {Direction.SOUTH, Direction.NORTH},
            Blocks.ORANGE_CONCRETE.defaultBlockState(), 0);
    private static final LiftSpec MAGI_LIFT = new LiftSpec(
            "magi", "B-30 / MAGI / PRIBNOW BOX", -84, 12,
            new int[] {-27, 7},
            new Direction[] {Direction.EAST, Direction.EAST},
            Blocks.PURPLE_CONCRETE.defaultBlockState(), 1);
    private static final LiftSpec CAGE_LIFT = new LiftSpec(
            "cage", "B-40 / EVA CAGES / LOGISTICS", 78, -104,
            new int[] {1, 49},
            new Direction[] {Direction.SOUTH, Direction.NORTH},
            Blocks.CYAN_CONCRETE.defaultBlockState(), 2);
    private static final LiftSpec DOGMA_LIFT = new LiftSpec(
            "dogma", "CENTRAL DOGMA / TERMINAL DOGMA", 64, 20,
            new int[] {-123, 1},
            new Direction[] {Direction.WEST, Direction.NORTH},
            Blocks.RED_CONCRETE.defaultBlockState(), 3);
    /** Multi-stop staff spine around the imported command-module envelope. */
    private static final LiftSpec CENTRAL_LIFT = new LiftSpec(
            "central", "CENTRAL SHAFT / ADMINISTRATION", -44, 64,
            new int[] {-27, 7, 31, 59, 83},
            new Direction[] {
                    Direction.WEST, Direction.EAST, Direction.EAST,
                    Direction.EAST, Direction.EAST
            },
            Blocks.YELLOW_CONCRETE.defaultBlockState(), 4);
    /** Continuous manual route from the GeoFront overlook to Tokyo-3. */
    private static final LiftSpec SURFACE_LIFT = new LiftSpec(
            "surface", "TOKYO-3 / GEOFRONT PUBLIC TRANSIT", 0,
            GeoFrontBuilder.OBSERVATION_Z,
            new int[] {
                    GeoFrontBuilder.OBSERVATION_Y,
                    IntegratedNervMapBuilder.TOKYO3_ORIGIN.getY()
                            - IntegratedNervMapBuilder.GEOFRONT_ORIGIN.getY()
                            + 1
            },
            new Direction[] {Direction.SOUTH, Direction.NORTH},
            Blocks.LIGHT_BLUE_CONCRETE.defaultBlockState(), 2);

    private static final LiftSpec[] LIFTS = {
            COMMAND_LIFT, MAGI_LIFT, CAGE_LIFT, DOGMA_LIFT,
            CENTRAL_LIFT, SURFACE_LIFT
    };

    private NervFacilityTopologyBuilder() {}

    public static TopologyAudit ensure(ServerLevel level, BlockPos origin)
    {
        TopologyAudit audit = inspect(level, origin);
        if (!audit.valid()
                && FacilityWorldPolicy.legacyGenerationAllowed(level.getServer()))
        {
            build(level, origin);
            audit = inspect(level, origin);
        }
        return audit;
    }

    public static TopologyAudit build(ServerLevel level, BlockPos origin)
    {
        FacilityWorldPolicy.requireLegacyGenerationAllowed(
                level.getServer(), "NervFacilityTopologyBuilder");
        PerformanceCounters.recordBuilderCall();
        buildB20CommandRing(level, origin);
        buildCommandSupportConnection(level, origin);
        buildMagiConnection(level, origin);
        buildLowerInterchange(level, origin);
        buildCageConnection(level, origin);
        buildDogmaConnection(level, origin);
        buildPyramidFacilityPlan(level, origin);
        buildSurfaceAccess(level, origin);

        for (LiftSpec lift : LIFTS)
        {
            buildLift(level, origin, lift);
        }

        // Door apertures are written after both corridors and shafts. This is
        // the single ownership point which prevents either pass sealing the
        // other's threshold.
        for (LiftSpec lift : LIFTS)
        {
            for (int stop = 0; stop < lift.stopCount(); stop++)
            {
                openLanding(level, origin, lift, lift.floor(stop),
                        lift.door(stop));
            }
            installLiftControls(level, origin, lift);
        }

        // Explicit room thresholds. The routes extend several blocks into the
        // destination, but these apertures make the contract independent of
        // whatever wall material the room builder used this revision.
        openRoomThreshold(level, origin, 0, 7, 84, Direction.SOUTH, 3);
        openRoomThreshold(level, origin, -38, 7, 12, Direction.WEST, 2);
        openRoomThreshold(level, origin, -43, -27, 12, Direction.WEST, 2);
        openRoomThreshold(level, origin, 34, 1, -23, Direction.EAST, 2);
        openRoomThreshold(level, origin, 24, -123, -10, Direction.SOUTH, 2);
        openRoomThreshold(level, origin, 62, 49,
                EvaHangarBuilder.GALLERY_Z - 7, Direction.WEST, 3);

        set(level, origin.offset(REVISION_MARKER),
                Blocks.NETHERITE_BLOCK.defaultBlockState());
        set(level, origin.offset(REVISION_MARKER).above(),
                Blocks.CRYING_OBSIDIAN.defaultBlockState());
        set(level, origin.offset(REVISION_MARKER).east(),
                Blocks.LODESTONE.defaultBlockState());
        set(level, origin.offset(REVISION_MARKER).north(),
                Blocks.WAXED_COPPER_BLOCK.defaultBlockState());
        set(level, origin.offset(REVISION_MARKER).south(),
                Blocks.EMERALD_BLOCK.defaultBlockState());
        return inspect(level, origin);
    }

    public static TopologyAudit inspect(ServerLevel level, BlockPos origin)
    {
        boolean revision = level.getBlockState(origin.offset(REVISION_MARKER))
                .is(Blocks.NETHERITE_BLOCK)
                && level.getBlockState(origin.offset(REVISION_MARKER).above())
                .is(Blocks.CRYING_OBSIDIAN)
                && level.getBlockState(origin.offset(REVISION_MARKER).east())
                .is(Blocks.LODESTONE)
                && level.getBlockState(origin.offset(REVISION_MARKER).north())
                .is(Blocks.WAXED_COPPER_BLOCK)
                && level.getBlockState(origin.offset(REVISION_MARKER).south())
                .is(Blocks.EMERALD_BLOCK);

        int lifts = 0;
        for (LiftSpec lift : LIFTS)
        {
            if (liftPresent(level, origin, lift))
            {
                lifts++;
            }
        }

        /*
         * Do not reduce a pedestrian network to a handful of friendly sample
         * points. A single wall, missing floor or later room pass in the
         * middle of a 150-block corridor stranded players while the previous
         * twelve-point audit still passed. Every interior lane is part of the
         * contract; the outer lane is the authored pressure wall.
         */
        int links = 0;
        int expectedLinks = 0;
        int[] result;

        result = auditLineX(level, origin, 7, -34, -13, 17);
        links += result[0]; expectedLinks += result[1];
        result = auditLineZ(level, origin, 7, -34, 12, 86);
        links += result[0]; expectedLinks += result[1];
        result = auditLineX(level, origin, 7, -34, 0, 86);
        links += result[0]; expectedLinks += result[1];
        result = auditLineZ(level, origin, 7, 0, 84, 86);
        links += result[0]; expectedLinks += result[1];
        result = auditLineX(level, origin, 7, -38, -34, 12);
        links += result[0]; expectedLinks += result[1];

        result = auditLineZ(level, origin, -5, 0, 94, 97);
        links += result[0]; expectedLinks += result[1];
        result = auditLineX(level, origin, 7, -80, -34, 12);
        links += result[0]; expectedLinks += result[1];
        result = auditLineX(level, origin, -27, -80, -43, 12);
        links += result[0]; expectedLinks += result[1];

        result = auditLineX(level, origin, 1, -32, 78, -23);
        links += result[0]; expectedLinks += result[1];
        result = auditLineZ(level, origin, 1, 0, -28, 18);
        links += result[0]; expectedLinks += result[1];
        result = auditLineZ(level, origin, 1, 78, -100, -23);
        links += result[0]; expectedLinks += result[1];
        result = auditLineZ(level, origin, 1, 64, -23, 16);
        links += result[0]; expectedLinks += result[1];

        result = auditLineZ(level, origin, EvaHangarBuilder.GALLERY_Y,
                78, EvaHangarBuilder.GALLERY_Z - 7, -108);
        links += result[0]; expectedLinks += result[1];
        result = auditLineX(level, origin, EvaHangarBuilder.GALLERY_Y,
                62, 78, EvaHangarBuilder.GALLERY_Z - 7);
        links += result[0]; expectedLinks += result[1];

        result = auditLineX(level, origin, -123, 24, 60, 20);
        links += result[0]; expectedLinks += result[1];
        result = auditLineZ(level, origin, -123, 24, -10, 20);
        links += result[0]; expectedLinks += result[1];

        boolean facilityPlan = facilityPlanPresent(level, origin);
        boolean surfaceAccess = surfaceAccessPresent(level, origin);
        boolean valid = revision && lifts == LIFTS.length
                && links == expectedLinks && facilityPlan && surfaceAccess;
        return new TopologyAudit(valid, revision, lifts, links,
                expectedLinks);
    }

    /**
     * Handles only the eight controls owned by these lifts.
     *
     * <p>The vanilla button use is left intact by the event handler, so the
     * physical click and powered animation remain visible.</p>
     */
    public static boolean handleUse(ServerPlayer player, BlockPos position)
    {
        ServerLevel level = player.serverLevel();
        BlockPos origin = IntegratedNervMapBuilder.GEOFRONT_ORIGIN;
        for (LiftSpec lift : LIFTS)
        {
            for (int sourceStop = 0;
                 sourceStop < lift.stopCount(); sourceStop++)
            {
                for (int destinationStop = 0;
                     destinationStop < lift.stopCount(); destinationStop++)
                {
                    if (sourceStop == destinationStop
                            || !controlPosition(origin, lift, sourceStop,
                            destinationStop).equals(position))
                    {
                        continue;
                    }
                    FacilityReadinessService.FacilityReadiness readiness =
                            FacilityReadinessService.read(level,
                                    FacilityReadinessService.Operation.ELEVATOR_CALL,
                                    -1);
                    if (!readiness.accepted())
                    {
                        player.displayClientMessage(Component.literal(
                                "NERV ELEVATOR  " + readiness.faultCode()
                                        + ": " + readiness.message())
                                .withStyle(ChatFormatting.RED), true);
                        return true;
                    }
                    if (ACTIVE_RIDES.containsKey(player.getUUID())
                            || liftIsBusy(lift))
                    {
                        player.displayClientMessage(Component.literal(
                                "NERV ELEVATOR  TRANSIT ALREADY ACTIVE")
                                .withStyle(ChatFormatting.RED), true);
                        return true;
                    }

                    int startY = lift.floor(sourceStop);
                    int destinationY = lift.floor(destinationStop);
                    BlockPos destination = origin.offset(
                            lift.x(), destinationY + 1, lift.z());
                    level.getChunkAt(destination);
                    player.stopRiding();
                    closeAllLiftDoors(level, origin, lift);

                    NervCarrierPlatformEntity cabin =
                            spawnCabin(level, origin, lift, startY);
                    int distance = Math.abs(destinationY - startY);
                    int travelTicks = Math.max(30,
                            Mth.ceil(distance / 1.15D));
                    ACTIVE_RIDES.put(player.getUUID(), new LiftRide(
                            level.dimension(), lift, sourceStop,
                            destinationStop, travelTicks,
                            cabin == null ? null : cabin.getUUID()));
                    level.playSound(null, position,
                            SoundEvents.PISTON_EXTEND,
                            SoundSource.BLOCKS, 0.8F, 0.72F);
                    player.teleportTo(level,
                            origin.getX() + lift.x() + 0.5D,
                            origin.getY() + startY + 1.05D,
                            origin.getZ() + lift.z() + 0.5D,
                            player.getYRot(), player.getXRot());
                    player.resetFallDistance();
                    player.displayClientMessage(Component.literal(
                            "NERV ELEVATOR  "
                                    + floorLabel(lift, sourceStop)
                                    + " > "
                                    + floorLabel(lift, destinationStop))
                            .withStyle(ChatFormatting.GOLD), true);
                    return true;
                }
            }
        }
        return false;
    }

    /**
     * Advances a real-time cabin ride. Doors close first, the visible cabin
     * and passenger move together, then only the destination door opens.
     */
    public static void tick(MinecraftServer server)
    {
        if (ACTIVE_RIDES.isEmpty())
        {
            return;
        }
        var iterator = ACTIVE_RIDES.entrySet().iterator();
        while (iterator.hasNext())
        {
            var entry = iterator.next();
            ServerPlayer player = server.getPlayerList()
                    .getPlayer(entry.getKey());
            LiftRide ride = entry.getValue();
            ServerLevel rideLevel = server.getLevel(ride.dimension());
            if (player == null
                    || rideLevel == null
                    || !player.serverLevel().dimension()
                    .equals(ride.dimension()))
            {
                if (rideLevel != null)
                {
                    openAllLiftDoors(rideLevel,
                            IntegratedNervMapBuilder.GEOFRONT_ORIGIN,
                            ride.lift);
                    discardCabin(rideLevel, ride);
                }
                iterator.remove();
                continue;
            }
            ServerLevel level = player.serverLevel();
            BlockPos origin = IntegratedNervMapBuilder.GEOFRONT_ORIGIN;
            ride.elapsed++;
            int motionTick = Math.max(0,
                    ride.elapsed - LiftRide.DOOR_CLOSE_TICKS);
            float progress = Mth.clamp(
                    motionTick / (float) ride.travelTicks, 0.0F, 1.0F);
            float eased = progress * progress * (3.0F - 2.0F * progress);
            double y = Mth.lerp(eased, ride.startY(), ride.destinationY())
                    + 1.05D;
            player.teleportTo(level,
                    origin.getX() + ride.lift.x() + 0.5D,
                    origin.getY() + y,
                    origin.getZ() + ride.lift.z() + 0.5D,
                    player.getYRot(), 0.0F);
            player.setDeltaMovement(0.0D, 0.0D, 0.0D);
            player.resetFallDistance();
            NervCarrierPlatformEntity cabin = resolveCabin(level, ride);
            if (cabin != null)
            {
                cabin.setLiftDoorOpen(progress >= 1.0F);
                cabin.moveControlled(
                        origin.getX() + ride.lift.x() + 0.5D,
                        origin.getY() + y,
                        origin.getZ() + ride.lift.z() + 0.5D);
            }
            if (motionTick > 0 && progress < 1.0F
                    && motionTick % 20 == 0)
            {
                level.playSound(null, player.blockPosition(),
                        SoundEvents.BEACON_AMBIENT, SoundSource.BLOCKS,
                        0.32F, ride.destinationY() > ride.startY()
                                ? 1.08F : 0.82F);
            }
            if (motionTick == ride.travelTicks)
            {
                openLandingDoor(level, origin, ride.lift,
                        ride.destinationStop);
                level.playSound(null, player.blockPosition(),
                        SoundEvents.PISTON_CONTRACT, SoundSource.BLOCKS,
                        0.75F, 1.12F);
            }
            if (ride.elapsed >= LiftRide.DOOR_CLOSE_TICKS
                    + ride.travelTicks + LiftRide.DOOR_OPEN_TICKS)
            {
                BlockPos destination = origin.offset(
                        ride.lift.x(), ride.destinationY() + 1,
                        ride.lift.z());
                player.teleportTo(level,
                        destination.getX() + 0.5D,
                        destination.getY() + 0.05D,
                        destination.getZ() + 0.5D,
                        player.getYRot(), player.getXRot());
                player.setDeltaMovement(0.0D, 0.0D, 0.0D);
                player.resetFallDistance();
                level.playSound(null, destination,
                        SoundEvents.BEACON_ACTIVATE, SoundSource.BLOCKS,
                        0.55F, 1.25F);
                player.displayClientMessage(Component.literal(
                        "NERV ELEVATOR  ARRIVED / " + ride.lift.label())
                        .withStyle(ChatFormatting.GREEN), true);
                openAllLiftDoors(level, origin, ride.lift);
                if (cabin != null)
                {
                    cabin.setLiftDoorOpen(true);
                    cabin.moveControlled(destination.getX() + 0.5D,
                            destination.getY() + 0.05D,
                            destination.getZ() + 0.5D);
                }
                iterator.remove();
            }
        }
    }

    public static void resetRuntime()
    {
        ACTIVE_RIDES.clear();
    }

    private static boolean liftIsBusy(LiftSpec lift)
    {
        for (LiftRide ride : ACTIVE_RIDES.values())
        {
            if (ride.lift.id().equals(lift.id()))
            {
                return true;
            }
        }
        return false;
    }

    private static NervCarrierPlatformEntity spawnCabin(
            ServerLevel level, BlockPos origin, LiftSpec lift, int floorY)
    {
        NervCarrierPlatformEntity cabin =
                ModEntities.NERV_CARRIER_PLATFORM.get().create(level);
        if (cabin == null)
        {
            return null;
        }
        cabin.configurePersonnelLift(lift.accentIndex());
        cabin.setLiftDoorOpen(false);
        cabin.moveControlled(origin.getX() + lift.x() + 0.5D,
                origin.getY() + floorY + 1.05D,
                origin.getZ() + lift.z() + 0.5D);
        if (!level.addFreshEntity(cabin))
        {
            return null;
        }
        return cabin;
    }

    private static NervCarrierPlatformEntity resolveCabin(
            ServerLevel level, LiftRide ride)
    {
        if (ride.cabinId == null)
        {
            return null;
        }
        Entity entity = level.getEntity(ride.cabinId);
        return entity instanceof NervCarrierPlatformEntity cabin
                && cabin.isAlive() ? cabin : null;
    }

    private static void discardCabin(ServerLevel level, LiftRide ride)
    {
        NervCarrierPlatformEntity cabin = resolveCabin(level, ride);
        if (cabin != null)
        {
            cabin.discard();
        }
    }

    private static void buildB20CommandRing(ServerLevel level, BlockPos origin)
    {
        Set<Long> route = new LinkedHashSet<>();
        addLineX(route, -34, -13, 17);
        addLineZ(route, -34, 12, 86);
        addLineX(route, -34, 0, 86);
        addLineZ(route, 0, 84, 86);
        addLineX(route, -38, -34, 12);
        buildCorridor(level, origin, 7, route,
                Blocks.ORANGE_CONCRETE.defaultBlockState());
    }

    private static void buildCommandSupportConnection(ServerLevel level,
                                                       BlockPos origin)
    {
        Set<Long> route = new LinkedHashSet<>();
        addLineZ(route, 0, 84, 86);
        buildCorridor(level, origin, 7, route,
                Blocks.ORANGE_CONCRETE.defaultBlockState());

        route.clear();
        addLineZ(route, 0, 94, 97);
        buildCorridor(level, origin, -5, route,
                Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState());
    }

    private static void buildMagiConnection(ServerLevel level, BlockPos origin)
    {
        Set<Long> route = new LinkedHashSet<>();
        addLineX(route, -80, -34, 12);
        buildCorridor(level, origin, 7, route,
                Blocks.PURPLE_CONCRETE.defaultBlockState());

        route.clear();
        addLineX(route, -80, -43, 12);
        buildCorridor(level, origin, -27, route,
                Blocks.PURPLE_CONCRETE.defaultBlockState());
    }

    private static void buildLowerInterchange(ServerLevel level,
                                               BlockPos origin)
    {
        Set<Long> route = new LinkedHashSet<>();
        addLineX(route, -32, 78, -23);
        addLineZ(route, 0, -28, 18);
        addLineZ(route, 78, -100, -23);
        addLineZ(route, 64, -23, 16);
        buildCorridor(level, origin, 1, route,
                Blocks.POLISHED_BLACKSTONE.defaultBlockState());
    }

    private static void buildCageConnection(ServerLevel level, BlockPos origin)
    {
        Set<Long> route = new LinkedHashSet<>();
        addLineZ(route, 78, EvaHangarBuilder.GALLERY_Z - 7, -108);
        addLineX(route, 62, 78, EvaHangarBuilder.GALLERY_Z - 7);
        buildCorridor(level, origin, EvaHangarBuilder.GALLERY_Y, route,
                Blocks.CYAN_CONCRETE.defaultBlockState());
    }

    private static void buildDogmaConnection(ServerLevel level, BlockPos origin)
    {
        Set<Long> route = new LinkedHashSet<>();
        addLineX(route, 24, 60, 20);
        addLineZ(route, 24, -10, 20);
        buildCorridor(level, origin, -123, route,
                Blocks.RED_CONCRETE.defaultBlockState());
    }

    /**
     * Gives the square pyramid an intentional vertical programme instead of
     * leaving the imported command module suspended in a mostly empty shell.
     *
     * <p>The downloaded module remains the B-20 core. New rooms stay outside
     * its x=-28..27 envelope until B-08, then close toward the central shaft
     * as the pyramid narrows. Every room has one public pressure threshold and
     * one service-side connection; coloured floors lead back to a lift.</p>
     */
    private static void buildPyramidFacilityPlan(ServerLevel level,
                                                  BlockPos origin)
    {
        // B-30: MAGI/Pribnow liaison and quarantine staging.
        buildFacilityRoom(level, origin, -78, -50, -27,
                -8, 32, Blocks.PURPLE_CONCRETE.defaultBlockState(),
                RoomStyle.LAB);
        openFacilityDoor(level, origin, -50, -27, 12,
                Direction.EAST, Blocks.PURPLE_CONCRETE.defaultBlockState());
        buildDeckLink(level, origin, -80, -40, -27, 12,
                Blocks.PURPLE_CONCRETE.defaultBlockState());

        // B-14: staff briefing/cafeteria west, medical/recovery east.
        buildFacilityRoom(level, origin, -74, -34, 31,
                -24, 48, Blocks.ORANGE_CONCRETE.defaultBlockState(),
                RoomStyle.BRIEFING);
        buildFacilityRoom(level, origin, 34, 74, 31,
                -24, 48, Blocks.WHITE_CONCRETE.defaultBlockState(),
                RoomStyle.MEDICAL);
        openFacilityDoor(level, origin, -34, 31, 36,
                Direction.EAST, Blocks.ORANGE_CONCRETE.defaultBlockState());
        openFacilityDoor(level, origin, 34, 31, 36,
                Direction.WEST, Blocks.WHITE_CONCRETE.defaultBlockState());
        buildDeckLink(level, origin, -40, -34, 31, 36,
                Blocks.ORANGE_CONCRETE.defaultBlockState());
        buildDeckLink(level, origin, -44, -34, 31, 64,
                Blocks.YELLOW_CONCRETE.defaultBlockState());
        buildDeckLinkZ(level, origin, -40, 31, 48, 64,
                Blocks.YELLOW_CONCRETE.defaultBlockState());
        openFacilityDoor(level, origin, -40, 31, 48,
                Direction.NORTH, Blocks.YELLOW_CONCRETE.defaultBlockState());

        // B-08: security/records deck above the downloaded shell.
        buildFacilityRoom(level, origin, -56, -8, 59,
                0, 61, Blocks.RED_CONCRETE.defaultBlockState(),
                RoomStyle.SECURITY);
        buildFacilityRoom(level, origin, 8, 56, 59,
                0, 61, Blocks.CYAN_CONCRETE.defaultBlockState(),
                RoomStyle.ARCHIVE);
        openFacilityDoor(level, origin, -8, 59, 40,
                Direction.EAST, Blocks.RED_CONCRETE.defaultBlockState());
        openFacilityDoor(level, origin, 8, 59, 40,
                Direction.WEST, Blocks.CYAN_CONCRETE.defaultBlockState());
        buildDeckLink(level, origin, -40, -8, 59, 64,
                Blocks.YELLOW_CONCRETE.defaultBlockState());
        openFacilityDoor(level, origin, -44, 59, 61,
                Direction.NORTH, Blocks.YELLOW_CONCRETE.defaultBlockState());

        // B-02: commander's office and strategic observation at the crown.
        buildFacilityRoom(level, origin, -38, 36, 83,
                6, 58, Blocks.YELLOW_CONCRETE.defaultBlockState(),
                RoomStyle.EXECUTIVE);
        openFacilityDoor(level, origin, -38, 83, 52,
                Direction.WEST, Blocks.YELLOW_CONCRETE.defaultBlockState());
        buildDeckLink(level, origin, -40, -38, 83, 64,
                Blocks.YELLOW_CONCRETE.defaultBlockState());

        // B-20 central shaft meets the command support gallery through a dry
        // east-facing branch outside the imported module.
        buildDeckLink(level, origin, -40, -30, 7, 64,
                Blocks.YELLOW_CONCRETE.defaultBlockState());
        buildDeckLinkZ(level, origin, -30, 7, 48, 64,
                Blocks.ORANGE_CONCRETE.defaultBlockState());

        // Stable, room-owned witnesses for incremental saves.
        set(level, origin.offset(-68, 32, 20),
                Blocks.LODESTONE.defaultBlockState());
        set(level, origin.offset(45, 60, 40),
                Blocks.LODESTONE.defaultBlockState());
        set(level, origin.offset(0, 84, 40),
                Blocks.LODESTONE.defaultBlockState());
    }

    /**
     * One continuous personnel route from Tokyo-3 to the inhabited cavern.
     * The surface entrance sits just beyond the south city grid and joins it
     * by a lit pressure gallery; the lower station replaces the old isolated
     * overlook without using a command teleport.
     */
    private static void buildSurfaceAccess(ServerLevel level, BlockPos origin)
    {
        int lowerY = SURFACE_LIFT.floor(0);
        int upperY = SURFACE_LIFT.floor(1);
        buildTransitStation(level, origin, 0,
                GeoFrontBuilder.OBSERVATION_Z, lowerY,
                Blocks.ORANGE_CONCRETE.defaultBlockState(), false);
        buildTransitStation(level, origin, 0,
                GeoFrontBuilder.OBSERVATION_Z, upperY,
                Blocks.LIGHT_BLUE_CONCRETE.defaultBlockState(), true);

        // At absolute Z=428 this reaches Tokyo-3 local Z=208, the southern
        // edge of the armoured district. It remains enclosed through the
        // exposed surface landscape.
        int cityThresholdZ = GeoFrontBuilder.OBSERVATION_Z - 58;
        for (int z = cityThresholdZ;
             z <= GeoFrontBuilder.OBSERVATION_Z - 12; z++)
        {
            for (int x = -4; x <= 4; x++)
            {
                set(level, origin.offset(x, upperY, z),
                        x == 0 && Math.floorMod(z, 8) < 3
                                ? Blocks.LIGHT_BLUE_CONCRETE
                                .defaultBlockState()
                                : Blocks.POLISHED_DEEPSLATE
                                .defaultBlockState());
                for (int y = upperY + 1; y <= upperY + 5; y++)
                {
                    boolean wall = Math.abs(x) == 4;
                    set(level, origin.offset(x, y, z), wall
                            ? y >= upperY + 2 && y <= upperY + 4
                                    ? Blocks.GRAY_STAINED_GLASS
                                    .defaultBlockState()
                                    : Blocks.IRON_BLOCK.defaultBlockState()
                            : Blocks.AIR.defaultBlockState());
                }
                set(level, origin.offset(x, upperY + 6, z),
                        Math.floorMod(x + z, 9) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.IRON_BLOCK.defaultBlockState());
            }
        }
        openTransitThreshold(level, origin, 0, upperY, cityThresholdZ,
                Direction.NORTH,
                Blocks.LIGHT_BLUE_CONCRETE.defaultBlockState());
        set(level, origin.offset(10, upperY + 1,
                        GeoFrontBuilder.OBSERVATION_Z),
                Blocks.LODESTONE.defaultBlockState());
    }

    private static void buildTransitStation(ServerLevel level,
                                            BlockPos origin,
                                            int centreX, int centreZ,
                                            int floorY, BlockState accent,
                                            boolean surface)
    {
        int halfX = 12;
        int halfZ = 12;
        int height = surface ? 8 : 9;
        for (int x = -halfX; x <= halfX; x++)
        {
            for (int z = -halfZ; z <= halfZ; z++)
            {
                boolean boundary = Math.abs(x) == halfX
                        || Math.abs(z) == halfZ;
                set(level, origin.offset(centreX + x, floorY,
                                centreZ + z),
                        boundary ? Blocks.POLISHED_BLACKSTONE_BRICKS
                                .defaultBlockState()
                                : Blocks.POLISHED_DEEPSLATE
                                .defaultBlockState());
                for (int y = 1; y < height; y++)
                {
                    BlockState state = boundary
                            ? y >= 2 && y <= height - 2
                                    ? Blocks.GRAY_STAINED_GLASS
                                    .defaultBlockState()
                                    : accent
                            : Blocks.AIR.defaultBlockState();
                    set(level, origin.offset(centreX + x, floorY + y,
                            centreZ + z), state);
                }
                set(level, origin.offset(centreX + x, floorY + height,
                                centreZ + z),
                        Math.floorMod(x + z, 7) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.POLISHED_BLACKSTONE_BRICKS
                                .defaultBlockState());
            }
        }
        openTransitThreshold(level, origin, centreX, floorY,
                centreZ - halfZ, Direction.NORTH, accent);
        openTransitThreshold(level, origin, centreX, floorY,
                centreZ + halfZ, Direction.SOUTH, accent);
    }

    private static void openTransitThreshold(ServerLevel level,
                                              BlockPos origin,
                                              int centreX, int floorY,
                                              int centreZ,
                                              Direction direction,
                                              BlockState accent)
    {
        Direction lateral = direction.getClockWise();
        for (int depth = 0; depth <= 1; depth++)
        {
            for (int side = -3; side <= 3; side++)
            {
                int x = centreX + direction.getStepX() * depth
                        + lateral.getStepX() * side;
                int z = centreZ + direction.getStepZ() * depth
                        + lateral.getStepZ() * side;
                for (int y = 1; y <= 5; y++)
                {
                    set(level, origin.offset(x, floorY + y, z),
                            Blocks.AIR.defaultBlockState());
                }
                set(level, origin.offset(x, floorY, z),
                        side == 0 ? accent
                                : Blocks.POLISHED_DEEPSLATE
                                .defaultBlockState());
            }
        }
    }

    private static void buildFacilityRoom(ServerLevel level, BlockPos origin,
                                          int minimumX, int maximumX,
                                          int floorY,
                                          int minimumZ, int maximumZ,
                                          BlockState accent,
                                          RoomStyle style)
    {
        final int height = 8;
        for (int x = minimumX; x <= maximumX; x++)
        {
            for (int z = minimumZ; z <= maximumZ; z++)
            {
                boolean boundary = x == minimumX || x == maximumX
                        || z == minimumZ || z == maximumZ;
                set(level, origin.offset(x, floorY, z),
                        Math.floorMod(x + z, 13) == 0
                                ? accent
                                : Blocks.POLISHED_DEEPSLATE
                                .defaultBlockState());
                for (int y = 1; y < height; y++)
                {
                    BlockState state;
                    if (!boundary)
                    {
                        state = Blocks.AIR.defaultBlockState();
                    }
                    else if (y >= 3 && y <= 5
                            && Math.floorMod(x * 3 + z, 7) <= 2)
                    {
                        state = Blocks.GRAY_STAINED_GLASS.defaultBlockState();
                    }
                    else
                    {
                        state = Blocks.DEEPSLATE_BRICKS.defaultBlockState();
                    }
                    set(level, origin.offset(x, floorY + y, z), state);
                }
                set(level, origin.offset(x, floorY + height, z),
                        Math.floorMod(x + z, 9) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : com.projectseele.world.NervMaterials.structuralBlock()
                                .defaultBlockState());
            }
        }
        furnishFacilityRoom(level, origin, minimumX, maximumX, floorY,
                minimumZ, maximumZ, accent, style);
    }

    private static void furnishFacilityRoom(
            ServerLevel level, BlockPos origin,
            int minimumX, int maximumX, int floorY,
            int minimumZ, int maximumZ, BlockState accent,
            RoomStyle style)
    {
        int centreX = (minimumX + maximumX) / 2;
        int centreZ = (minimumZ + maximumZ) / 2;
        switch (style)
        {
            case LAB ->
            {
                for (int x = minimumX + 6; x <= maximumX - 6; x += 8)
                {
                    for (int z = minimumZ + 7; z <= maximumZ - 7; z += 11)
                    {
                        set(level, origin.offset(x, floorY + 1, z),
                                Blocks.IRON_BLOCK.defaultBlockState());
                        set(level, origin.offset(x, floorY + 2, z),
                                Blocks.CYAN_STAINED_GLASS.defaultBlockState());
                        set(level, origin.offset(x, floorY + 3, z),
                                Blocks.AMETHYST_BLOCK.defaultBlockState());
                        set(level, origin.offset(x, floorY + 4, z),
                                Blocks.CYAN_STAINED_GLASS.defaultBlockState());
                    }
                }
                buildConsoleBank(level, origin, centreX, floorY + 1,
                        maximumZ - 3, accent, Direction.SOUTH);
            }
            case BRIEFING ->
            {
                for (int z = minimumZ + 12; z <= maximumZ - 10; z += 6)
                {
                    for (int x = minimumX + 7;
                         x <= maximumX - 7; x += 5)
                    {
                        set(level, origin.offset(x, floorY + 1, z),
                                Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS
                                        .defaultBlockState()
                                        .setValue(
                                                net.minecraft.world.level.block.StairBlock.FACING,
                                                Direction.NORTH));
                    }
                }
                for (int x = minimumX + 8; x <= maximumX - 8; x++)
                {
                    for (int y = floorY + 2; y <= floorY + 6; y++)
                    {
                        set(level, origin.offset(x, y, minimumZ + 1),
                                y == floorY + 2 || y == floorY + 6
                                        ? Blocks.BLACK_CONCRETE
                                        .defaultBlockState()
                                        : Math.floorMod(x + y, 5) == 0
                                                ? Blocks.RED_STAINED_GLASS
                                                .defaultBlockState()
                                                : Blocks.BLUE_STAINED_GLASS
                                                .defaultBlockState());
                    }
                }
                buildStaffTables(level, origin, minimumX + 5,
                        maximumX - 5, floorY, maximumZ - 8);
            }
            case MEDICAL ->
            {
                for (int z = minimumZ + 8; z <= maximumZ - 8; z += 10)
                {
                    for (int x = minimumX + 6;
                         x <= maximumX - 6; x += 10)
                    {
                        for (int dx = -2; dx <= 2; dx++)
                        {
                            set(level, origin.offset(x + dx,
                                            floorY + 1, z),
                                    dx == 0
                                            ? Blocks.RED_CONCRETE
                                            .defaultBlockState()
                                            : Blocks.WHITE_WOOL
                                            .defaultBlockState());
                        }
                        set(level, origin.offset(x - 2,
                                        floorY + 2, z),
                                Blocks.IRON_BARS.defaultBlockState());
                    }
                }
                buildConsoleBank(level, origin, centreX, floorY + 1,
                        minimumZ + 3, accent, Direction.NORTH);
            }
            case SECURITY ->
            {
                for (int z = minimumZ + 10; z <= maximumZ - 8; z += 12)
                {
                    for (int x = minimumX + 3; x <= maximumX - 3; x++)
                    {
                        if (Math.abs(x - centreX) <= 2)
                        {
                            continue;
                        }
                        set(level, origin.offset(x, floorY + 1, z),
                                Blocks.IRON_BARS.defaultBlockState());
                        set(level, origin.offset(x, floorY + 2, z),
                                Blocks.IRON_BARS.defaultBlockState());
                    }
                    set(level, origin.offset(centreX - 3,
                                    floorY + 1, z),
                            Blocks.REDSTONE_LAMP.defaultBlockState());
                    set(level, origin.offset(centreX + 3,
                                    floorY + 1, z),
                            Blocks.REDSTONE_LAMP.defaultBlockState());
                }
                buildConsoleBank(level, origin, minimumX + 5,
                        floorY + 1, centreZ, accent, Direction.WEST);
            }
            case ARCHIVE ->
            {
                for (int x = minimumX + 6; x <= maximumX - 6; x += 7)
                {
                    for (int z = minimumZ + 6; z <= maximumZ - 6; z++)
                    {
                        if (Math.abs(z - centreZ) <= 2)
                        {
                            continue;
                        }
                        set(level, origin.offset(x, floorY + 1, z),
                                Blocks.BLACK_GLAZED_TERRACOTTA
                                        .defaultBlockState());
                        set(level, origin.offset(x, floorY + 2, z),
                                Math.floorMod(z, 5) == 0
                                        ? Blocks.SEA_LANTERN
                                        .defaultBlockState()
                                        : Blocks.OBSERVER
                                        .defaultBlockState());
                        set(level, origin.offset(x, floorY + 3, z),
                                Blocks.BLACK_CONCRETE.defaultBlockState());
                    }
                }
            }
            case EXECUTIVE ->
            {
                // Long strategic table, paired seats and a north observation
                // screen echo the austere commander's-office compositions.
                for (int z = centreZ - 10; z <= centreZ + 10; z++)
                {
                    for (int x = -3; x <= 3; x++)
                    {
                        set(level, origin.offset(centreX + x,
                                        floorY + 1, z),
                                Math.abs(x) == 3
                                        ? Blocks.BLACK_CONCRETE
                                        .defaultBlockState()
                                        : Blocks.RED_STAINED_GLASS
                                        .defaultBlockState());
                    }
                    if (Math.floorMod(z, 4) == 0)
                    {
                        set(level, origin.offset(centreX - 5,
                                        floorY + 1, z),
                                Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS
                                        .defaultBlockState()
                                        .setValue(
                                                net.minecraft.world.level.block.StairBlock.FACING,
                                                Direction.EAST));
                        set(level, origin.offset(centreX + 5,
                                        floorY + 1, z),
                                Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS
                                        .defaultBlockState()
                                        .setValue(
                                                net.minecraft.world.level.block.StairBlock.FACING,
                                                Direction.WEST));
                    }
                }
                for (int x = minimumX + 10; x <= maximumX - 10; x++)
                {
                    for (int y = floorY + 2; y <= floorY + 6; y++)
                    {
                        set(level, origin.offset(x, y, minimumZ + 1),
                                Math.floorMod(x + y, 6) == 0
                                        ? Blocks.RED_STAINED_GLASS
                                        .defaultBlockState()
                                        : Blocks.BLACK_CONCRETE
                                        .defaultBlockState());
                    }
                }
            }
        }
    }

    private static void buildConsoleBank(ServerLevel level, BlockPos origin,
                                         int centreX, int y, int centreZ,
                                         BlockState accent,
                                         Direction facing)
    {
        Direction lateral = facing.getClockWise();
        for (int side = -3; side <= 3; side++)
        {
            int x = centreX + lateral.getStepX() * side;
            int z = centreZ + lateral.getStepZ() * side;
            set(level, origin.offset(x, y, z),
                    Blocks.POLISHED_BLACKSTONE.defaultBlockState());
            set(level, origin.offset(x, y + 1, z),
                    side == 0 ? Blocks.SEA_LANTERN.defaultBlockState()
                            : accent);
        }
    }

    private static void buildStaffTables(ServerLevel level, BlockPos origin,
                                         int minimumX, int maximumX,
                                         int floorY, int z)
    {
        for (int x = minimumX; x <= maximumX; x += 8)
        {
            for (int dx = -2; dx <= 2; dx++)
            {
                set(level, origin.offset(x + dx, floorY + 1, z),
                        Blocks.SMOOTH_QUARTZ_SLAB.defaultBlockState());
            }
            set(level, origin.offset(x, floorY + 1, z - 2),
                    Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS
                            .defaultBlockState()
                            .setValue(
                                    net.minecraft.world.level.block.StairBlock.FACING,
                                    Direction.SOUTH));
            set(level, origin.offset(x, floorY + 1, z + 2),
                    Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS
                            .defaultBlockState()
                            .setValue(
                                    net.minecraft.world.level.block.StairBlock.FACING,
                                    Direction.NORTH));
        }
    }

    private static void openFacilityDoor(ServerLevel level, BlockPos origin,
                                         int centreX, int floorY,
                                         int centreZ, Direction inward,
                                         BlockState accent)
    {
        Direction lateral = inward.getClockWise();
        for (int depth = 0; depth <= 2; depth++)
        {
            for (int side = -2; side <= 2; side++)
            {
                int x = centreX + inward.getStepX() * depth
                        + lateral.getStepX() * side;
                int z = centreZ + inward.getStepZ() * depth
                        + lateral.getStepZ() * side;
                for (int y = 1; y <= 5; y++)
                {
                    set(level, origin.offset(x, floorY + y, z),
                            Blocks.AIR.defaultBlockState());
                }
                set(level, origin.offset(x, floorY, z),
                        side == 0 ? accent
                                : Blocks.POLISHED_DEEPSLATE
                                .defaultBlockState());
            }
        }
        for (int side : new int[] {-3, 3})
        {
            int x = centreX + lateral.getStepX() * side;
            int z = centreZ + lateral.getStepZ() * side;
            for (int y = 1; y <= 5; y++)
            {
                set(level, origin.offset(x, floorY + y, z), accent);
            }
        }
        for (int side = -2; side <= 2; side++)
        {
            int x = centreX + lateral.getStepX() * side;
            int z = centreZ + lateral.getStepZ() * side;
            set(level, origin.offset(x, floorY + 6, z),
                    side == 0 ? Blocks.SEA_LANTERN.defaultBlockState()
                            : accent);
        }
    }

    private static void buildDeckLink(ServerLevel level, BlockPos origin,
                                      int minimumX, int maximumX,
                                      int floorY, int z, BlockState accent)
    {
        Set<Long> route = new LinkedHashSet<>();
        addLineX(route, minimumX, maximumX, z);
        buildCorridor(level, origin, floorY, route, accent);
    }

    private static void buildDeckLinkZ(ServerLevel level, BlockPos origin,
                                       int x, int floorY,
                                       int minimumZ, int maximumZ,
                                       BlockState accent)
    {
        Set<Long> route = new LinkedHashSet<>();
        addLineZ(route, x, minimumZ, maximumZ);
        buildCorridor(level, origin, floorY, route, accent);
    }

    private static boolean facilityPlanPresent(ServerLevel level,
                                               BlockPos origin)
    {
        return level.getBlockState(origin.offset(-68, 32, 20))
                .is(Blocks.LODESTONE)
                && level.getBlockState(origin.offset(45, 60, 40))
                .is(Blocks.LODESTONE)
                && level.getBlockState(origin.offset(0, 84, 40))
                .is(Blocks.LODESTONE);
    }

    private static boolean surfaceAccessPresent(ServerLevel level,
                                                BlockPos origin)
    {
        int upperY = SURFACE_LIFT.floor(1);
        return level.getBlockState(origin.offset(10, upperY + 1,
                        GeoFrontBuilder.OBSERVATION_Z))
                .is(Blocks.LODESTONE)
                && level.getBlockState(origin.offset(
                        0, upperY, GeoFrontBuilder.OBSERVATION_Z - 58))
                .is(Blocks.LIGHT_BLUE_CONCRETE)
                && level.getBlockState(origin.offset(
                        0, upperY + 2, GeoFrontBuilder.OBSERVATION_Z - 40))
                .isAir();
    }

    private enum RoomStyle
    {
        LAB,
        BRIEFING,
        MEDICAL,
        SECURITY,
        ARCHIVE,
        EXECUTIVE
    }

    private static void buildCorridor(ServerLevel level, BlockPos origin,
                                      int floorY, Set<Long> centreLine,
                                      BlockState accent)
    {
        Set<Long> cells = new LinkedHashSet<>();
        for (long packed : centreLine)
        {
            int centreX = unpackX(packed);
            int centreZ = unpackZ(packed);
            for (int x = -CORRIDOR_RADIUS; x <= CORRIDOR_RADIUS; x++)
            {
                for (int z = -CORRIDOR_RADIUS; z <= CORRIDOR_RADIUS; z++)
                {
                    cells.add(pack(centreX + x, centreZ + z));
                }
            }
        }

        for (long packed : cells)
        {
            int x = unpackX(packed);
            int z = unpackZ(packed);
            BlockState floor = Math.floorMod(x + z, 11) == 0
                    ? accent
                    : Blocks.POLISHED_DEEPSLATE.defaultBlockState();
            set(level, origin.offset(x, floorY, z), floor);
            for (int y = 1; y <= CORRIDOR_CLEAR_HEIGHT; y++)
            {
                set(level, origin.offset(x, floorY + y, z),
                        Blocks.AIR.defaultBlockState());
            }
            set(level, origin.offset(x,
                            floorY + CORRIDOR_CLEAR_HEIGHT + 1, z),
                    Math.floorMod(x - z, 13) == 0
                            ? Blocks.SEA_LANTERN.defaultBlockState()
                            : com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
        }

        for (long packed : cells)
        {
            int x = unpackX(packed);
            int z = unpackZ(packed);
            for (int[] step : new int[][] {
                    {1, 0}, {-1, 0}, {0, 1}, {0, -1}
            })
            {
                int wallX = x + step[0];
                int wallZ = z + step[1];
                if (cells.contains(pack(wallX, wallZ)))
                {
                    continue;
                }
                for (int y = 1; y <= CORRIDOR_CLEAR_HEIGHT; y++)
                {
                    set(level, origin.offset(wallX, floorY + y, wallZ),
                            y == 2 && Math.floorMod(x + z, 9) == 0
                                    ? Blocks.GRAY_STAINED_GLASS
                                    .defaultBlockState()
                                    : com.projectseele.world.NervMaterials.structuralBlock()
                                    .defaultBlockState());
                }
            }
        }
    }

    private static void buildLift(ServerLevel level, BlockPos origin,
                                  LiftSpec lift)
    {
        int lowerY = lift.minimumFloor();
        int upperY = lift.maximumFloor();
        for (int y = lowerY; y <= upperY + 5; y++)
        {
            for (int x = -LIFT_RADIUS; x <= LIFT_RADIUS; x++)
            {
                for (int z = -LIFT_RADIUS; z <= LIFT_RADIUS; z++)
                {
                    BlockPos position = origin.offset(
                            lift.x() + x, y, lift.z() + z);
                    boolean wall = Math.abs(x) == LIFT_RADIUS
                            || Math.abs(z) == LIFT_RADIUS;
                    boolean landing = lift.hasFloor(y);
                    boolean roof = y == upperY + 5;
                    if (landing || roof)
                    {
                        set(level, position,
                                Math.floorMod(x + z, 7) == 0
                                        ? Blocks.SEA_LANTERN
                                        .defaultBlockState()
                                        : Blocks.POLISHED_DEEPSLATE
                                        .defaultBlockState());
                    }
                    else if (wall)
                    {
                        boolean lightBand = Math.floorMod(y, 8) == 0
                                && (x == 0 || z == 0);
                        set(level, position, lightBand
                                ? lift.accent()
                                : com.projectseele.world.NervMaterials.structuralBlock()
                                .defaultBlockState());
                    }
                    else
                    {
                        set(level, position, Blocks.AIR.defaultBlockState());
                    }
                }
            }
            if (y > lowerY && y < upperY + 5)
            {
                // A rotating sequence of wall lights recreates the readable
                // spiral descent motif without obstructing the cabin.
                int phase = Math.floorMod(y - lowerY, 16);
                int lightX;
                int lightZ;
                if (phase < 4)
                {
                    lightX = -LIFT_RADIUS + phase * 2;
                    lightZ = -LIFT_RADIUS;
                }
                else if (phase < 8)
                {
                    lightX = LIFT_RADIUS;
                    lightZ = -LIFT_RADIUS + (phase - 4) * 2;
                }
                else if (phase < 12)
                {
                    lightX = LIFT_RADIUS - (phase - 8) * 2;
                    lightZ = LIFT_RADIUS;
                }
                else
                {
                    lightX = -LIFT_RADIUS;
                    lightZ = LIFT_RADIUS - (phase - 12) * 2;
                }
                set(level, origin.offset(lift.x() + lightX, y,
                                lift.z() + lightZ),
                        Blocks.SEA_LANTERN.defaultBlockState());
            }
        }
    }

    private static void openLanding(ServerLevel level, BlockPos origin,
                                    LiftSpec lift, int floorY,
                                    Direction direction)
    {
        int boundaryX = lift.x() + direction.getStepX() * LIFT_RADIUS;
        int boundaryZ = lift.z() + direction.getStepZ() * LIFT_RADIUS;
        Direction lateral = direction.getClockWise();
        for (int side = -2; side <= 2; side++)
        {
            int x = boundaryX + lateral.getStepX() * side;
            int z = boundaryZ + lateral.getStepZ() * side;
            for (int y = floorY + 1; y <= floorY + 4; y++)
            {
                set(level, origin.offset(x, y, z),
                        Blocks.AIR.defaultBlockState());
            }
            set(level, origin.offset(x, floorY, z),
                    side == 0 ? lift.accent()
                            : Blocks.POLISHED_DEEPSLATE.defaultBlockState());
            set(level, origin.offset(x, floorY + 5, z),
                    side == 0 ? Blocks.SEA_LANTERN.defaultBlockState()
                            : com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
        }
        for (int y = floorY; y <= floorY + 5; y++)
        {
            int leftX = boundaryX + lateral.getStepX() * -3;
            int leftZ = boundaryZ + lateral.getStepZ() * -3;
            int rightX = boundaryX + lateral.getStepX() * 3;
            int rightZ = boundaryZ + lateral.getStepZ() * 3;
            set(level, origin.offset(leftX, y, leftZ), lift.accent());
            set(level, origin.offset(rightX, y, rightZ), lift.accent());
        }
        // Stepped corners form a hexagonal pressure-door silhouette like the
        // repeated Central-Dogma lift doors in the TV production designs.
        for (int side : new int[] {-2, 2})
        {
            int x = boundaryX + lateral.getStepX() * side;
            int z = boundaryZ + lateral.getStepZ() * side;
            set(level, origin.offset(x, floorY + 1, z), lift.accent());
            set(level, origin.offset(x, floorY + 5, z), lift.accent());
        }
        for (int side = -1; side <= 1; side++)
        {
            int x = boundaryX + lateral.getStepX() * side;
            int z = boundaryZ + lateral.getStepZ() * side;
            set(level, origin.offset(x, floorY + 6, z), lift.accent());
        }
    }

    private static void installLiftControls(ServerLevel level,
                                            BlockPos origin, LiftSpec lift)
    {
        BlockState button = Blocks.STONE_BUTTON.defaultBlockState()
                .setValue(ButtonBlock.FACE, AttachFace.FLOOR)
                .setValue(ButtonBlock.FACING, Direction.NORTH);
        for (int sourceStop = 0; sourceStop < lift.stopCount(); sourceStop++)
        {
            for (int destinationStop = 0;
                 destinationStop < lift.stopCount(); destinationStop++)
            {
                if (sourceStop == destinationStop)
                {
                    continue;
                }
                BlockPos control = controlPosition(origin, lift,
                        sourceStop, destinationStop);
                set(level, control.below(),
                        lift.accent());
                set(level, control, button);
            }
        }
    }

    private static BlockPos controlPosition(BlockPos origin, LiftSpec lift,
                                            int sourceStop,
                                            int destinationStop)
    {
        int ordinal = 0;
        for (int stop = 0; stop < destinationStop; stop++)
        {
            if (stop != sourceStop)
            {
                ordinal++;
            }
        }
        int choices = lift.stopCount() - 1;
        int lateralOffset = ordinal - (choices - 1) / 2;
        Direction door = lift.door(sourceStop);
        Direction lateral = door.getClockWise();
        int inward = LIFT_RADIUS - 2;
        return origin.offset(
                lift.x() + door.getStepX() * inward
                        + lateral.getStepX() * lateralOffset,
                lift.floor(sourceStop) + 2,
                lift.z() + door.getStepZ() * inward
                        + lateral.getStepZ() * lateralOffset);
    }

    private static boolean liftPresent(ServerLevel level, BlockPos origin,
                                       LiftSpec lift)
    {
        int first = 0;
        int last = lift.stopCount() - 1;
        return level.getBlockState(controlPosition(
                        origin, lift, first, first == last ? first : last))
                .is(Blocks.STONE_BUTTON)
                && level.getBlockState(controlPosition(
                        origin, lift, last, last == first ? last : first))
                .is(Blocks.STONE_BUTTON)
                && level.getBlockState(origin.offset(
                        lift.x() - LIFT_RADIUS, lift.minimumFloor() + 3,
                        lift.z() - LIFT_RADIUS))
                .is(com.projectseele.world.NervMaterials.STRUCTURAL_SHELL)
                && level.getBlockState(origin.offset(
                        lift.x() + LIFT_RADIUS, lift.maximumFloor() + 3,
                        lift.z() + LIFT_RADIUS))
                .is(com.projectseele.world.NervMaterials.STRUCTURAL_SHELL);
    }

    private static void closeAllLiftDoors(ServerLevel level, BlockPos origin,
                                          LiftSpec lift)
    {
        for (int stop = 0; stop < lift.stopCount(); stop++)
        {
            setLandingDoor(level, origin, lift, stop, true);
        }
    }

    private static void openAllLiftDoors(ServerLevel level, BlockPos origin,
                                         LiftSpec lift)
    {
        for (int stop = 0; stop < lift.stopCount(); stop++)
        {
            setLandingDoor(level, origin, lift, stop, false);
        }
    }

    private static void openLandingDoor(ServerLevel level, BlockPos origin,
                                        LiftSpec lift, int stop)
    {
        setLandingDoor(level, origin, lift, stop, false);
    }

    /** Sliding five-wide pressure leaves occupy only the shaft boundary. */
    private static void setLandingDoor(ServerLevel level, BlockPos origin,
                                       LiftSpec lift, int stop,
                                       boolean closed)
    {
        int floorY = lift.floor(stop);
        Direction direction = lift.door(stop);
        Direction lateral = direction.getClockWise();
        int boundaryX = lift.x() + direction.getStepX() * LIFT_RADIUS;
        int boundaryZ = lift.z() + direction.getStepZ() * LIFT_RADIUS;
        for (int side = -2; side <= 2; side++)
        {
            int x = boundaryX + lateral.getStepX() * side;
            int z = boundaryZ + lateral.getStepZ() * side;
            for (int y = floorY + 1; y <= floorY + 4; y++)
            {
                BlockState state;
                if (!closed)
                {
                    state = Blocks.AIR.defaultBlockState();
                }
                else if (side == 0)
                {
                    state = lift.accent();
                }
                else
                {
                    state = Blocks.IRON_BLOCK.defaultBlockState();
                }
                set(level, origin.offset(x, y, z), state);
            }
        }
    }

    private static void openRoomThreshold(ServerLevel level, BlockPos origin,
                                          int x, int floorY, int z,
                                          Direction direction, int halfWidth)
    {
        Direction lateral = direction.getClockWise();
        for (int depth = 0; depth <= 2; depth++)
        {
            int centreX = x + direction.getStepX() * depth;
            int centreZ = z + direction.getStepZ() * depth;
            for (int side = -halfWidth; side <= halfWidth; side++)
            {
                int doorX = centreX + lateral.getStepX() * side;
                int doorZ = centreZ + lateral.getStepZ() * side;
                for (int y = 1; y <= 4; y++)
                {
                    set(level, origin.offset(doorX, floorY + y, doorZ),
                            Blocks.AIR.defaultBlockState());
                }
                set(level, origin.offset(doorX, floorY, doorZ),
                        Blocks.POLISHED_DEEPSLATE.defaultBlockState());
            }
        }
    }

    private static boolean walkable(ServerLevel level, BlockPos feet)
    {
        BlockPos floor = feet.below();
        BlockState floorState = level.getBlockState(floor);
        return !floorState.isAir()
                && floorState.getFluidState().isEmpty()
                && floorState.isFaceSturdy(level, floor, Direction.UP)
                && level.noCollision(new net.minecraft.world.phys.AABB(
                        feet.getX() + 0.2D, feet.getY(), feet.getZ() + 0.2D,
                        feet.getX() + 0.8D, feet.getY() + 1.8D,
                        feet.getZ() + 0.8D));
    }

    private static int[] auditLineX(ServerLevel level, BlockPos origin,
                                    int floorY, int minimumX, int maximumX,
                                    int z)
    {
        int passed = 0;
        int expected = (Math.abs(maximumX - minimumX) + 1)
                * (CORRIDOR_RADIUS * 2 - 1);
        for (int x = Math.min(minimumX, maximumX);
             x <= Math.max(minimumX, maximumX); x++)
        {
            for (int lane = -CORRIDOR_RADIUS + 1;
                 lane < CORRIDOR_RADIUS; lane++)
            {
                if (walkable(level, origin.offset(x, floorY + 1, z + lane)))
                {
                    passed++;
                }
            }
        }
        return new int[] {passed, expected};
    }

    private static int[] auditLineZ(ServerLevel level, BlockPos origin,
                                    int floorY, int x, int minimumZ,
                                    int maximumZ)
    {
        int passed = 0;
        int expected = (Math.abs(maximumZ - minimumZ) + 1)
                * (CORRIDOR_RADIUS * 2 - 1);
        for (int z = Math.min(minimumZ, maximumZ);
             z <= Math.max(minimumZ, maximumZ); z++)
        {
            for (int lane = -CORRIDOR_RADIUS + 1;
                 lane < CORRIDOR_RADIUS; lane++)
            {
                if (walkable(level, origin.offset(x + lane, floorY + 1, z)))
                {
                    passed++;
                }
            }
        }
        return new int[] {passed, expected};
    }

    private static void addLineX(Set<Long> route, int minimumX, int maximumX,
                                 int z)
    {
        for (int x = Math.min(minimumX, maximumX);
             x <= Math.max(minimumX, maximumX); x++)
        {
            route.add(pack(x, z));
        }
    }

    private static void addLineZ(Set<Long> route, int x, int minimumZ,
                                 int maximumZ)
    {
        for (int z = Math.min(minimumZ, maximumZ);
             z <= Math.max(minimumZ, maximumZ); z++)
        {
            route.add(pack(x, z));
        }
    }

    private static long pack(int x, int z)
    {
        return ((long) x << 32) | (z & 0xFFFFFFFFL);
    }

    private static int unpackX(long packed)
    {
        return (int) (packed >> 32);
    }

    private static int unpackZ(long packed)
    {
        return (int) packed;
    }

    private static void set(ServerLevel level, BlockPos position,
                            BlockState state)
    {
        if (!level.getBlockState(position).equals(state))
        {
            level.setBlock(position, state, UPDATE_CLIENTS);
            PerformanceCounters.recordWorldBlockWrites(1);
        }
    }

    private static String floorLabel(LiftSpec lift, int stop)
    {
        if (lift == SURFACE_LIFT)
        {
            return stop == 0 ? "GEOFRONT" : "TOKYO-3";
        }
        if (lift == DOGMA_LIFT)
        {
            return stop == 0 ? "TERMINAL DOGMA" : "B-40";
        }
        if (lift == CENTRAL_LIFT)
        {
            return switch (stop)
            {
                case 0 -> "B-30 SCIENCE";
                case 1 -> "B-20 OPERATIONS";
                case 2 -> "B-14 STAFF";
                case 3 -> "B-08 SECURITY";
                default -> "B-02 EXECUTIVE";
            };
        }
        return stop == 0 ? "LOWER" : "UPPER";
    }

    private record LiftSpec(String id, String label, int x, int z,
                            int[] floors, Direction[] doors,
                            BlockState accent, int accentIndex)
    {
        private int stopCount()
        {
            return this.floors.length;
        }

        private int floor(int stop)
        {
            return this.floors[stop];
        }

        private Direction door(int stop)
        {
            return this.doors[stop];
        }

        private int minimumFloor()
        {
            int result = Integer.MAX_VALUE;
            for (int floor : this.floors)
            {
                result = Math.min(result, floor);
            }
            return result;
        }

        private int maximumFloor()
        {
            int result = Integer.MIN_VALUE;
            for (int floor : this.floors)
            {
                result = Math.max(result, floor);
            }
            return result;
        }

        private boolean hasFloor(int y)
        {
            for (int floor : this.floors)
            {
                if (floor == y)
                {
                    return true;
                }
            }
            return false;
        }
    }

    private static final class LiftRide
    {
        private static final int DOOR_CLOSE_TICKS = 14;
        private static final int DOOR_OPEN_TICKS = 12;

        private final ResourceKey<Level> dimension;
        private final LiftSpec lift;
        private final int sourceStop;
        private final int destinationStop;
        private final int travelTicks;
        private final UUID cabinId;
        private int elapsed;

        private LiftRide(ResourceKey<Level> dimension, LiftSpec lift,
                         int sourceStop, int destinationStop,
                         int travelTicks, UUID cabinId)
        {
            this.dimension = dimension;
            this.lift = lift;
            this.sourceStop = sourceStop;
            this.destinationStop = destinationStop;
            this.travelTicks = travelTicks;
            this.cabinId = cabinId;
        }

        private ResourceKey<Level> dimension()
        {
            return this.dimension;
        }

        private int startY()
        {
            return this.lift.floor(this.sourceStop);
        }

        private int destinationY()
        {
            return this.lift.floor(this.destinationStop);
        }
    }

    public record TopologyAudit(boolean valid, boolean revision,
                                int lifts, int routeSamples,
                                int expectedRouteSamples)
    {
        public String summary()
        {
            return String.format(Locale.ROOT,
                    "valid=%s revision=%s lifts=%d/%d routes=%d/%d",
                    valid, revision, lifts, LIFTS.length,
                    routeSamples, expectedRouteSamples);
        }
    }
}
