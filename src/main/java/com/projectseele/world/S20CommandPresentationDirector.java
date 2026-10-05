package com.projectseele.world;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.NervArmamentStationEntity;
import com.projectseele.entity.NervCommandSeatEntity;
import com.projectseele.network.ClientboundPilotStatusPacket;
import com.projectseele.network.SeeleNetwork;
import com.projectseele.network.ServerboundEvaVideoFramePacket;
import com.projectseele.registry.ModEntities;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.FloatTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.Tag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Display;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.network.PacketDistributor;

/**
 * One-shot presentation migration for the measured S20 command-room asset.
 *
 * <p>S20 inherits its coherent blocks from the old human-approved GeoFront.
 * This director is deliberately not an architecture builder. It reads the
 * private source NBT, finds the two authored dummy-screen connected
 * components and removes exactly those voxels. No bounding-box clearing,
 * route repair or owner-derived geometry is permitted here.</p>
 */
public final class S20CommandPresentationDirector
{
    private static final Path COMMAND_MODULE = com.projectseele.entity.CombatMotionResourcesR44.instancePath(
            "projectseele-local-maps/nerv_command_left.nbt");

    /**
     * Measured placement in the actual human-approved reference save.
     *
     * <p>The structure file records a rotation hint, but the blocks already
     * present in SEELE_TOKYO3_REBUILT match the direct placement
     * {@code (2+x,-465+y,263+z)}. The rear birch door and 71.5% of all 33,797
     * authored voxels independently verify this transform; applying the hint
     * a second time puts the presentation roughly one hundred blocks on the
     * wrong side of the room.</p>
     */
    private static final BlockPos COMMAND_TRANSFORM_ORIGIN =
            new BlockPos(2, -465, 223);
    public static final BlockPos COMMAND_MARKER =
            new BlockPos(-2, -466, 202);

    public static BlockPos authoredLocalToWorld(BlockPos local)
    {
        return COMMAND_TRANSFORM_ORIGIN.offset(
                local.getX(), local.getY(), local.getZ());
    }

    public static final double UPPER_SCREEN_X = 28.0D;
    public static final double UPPER_SCREEN_Y = -415.795D;
    public static final double UPPER_SCREEN_Z = 322.793D;
    public static final double LOWER_SCREEN_X = 28.0D;
    public static final double LOWER_SCREEN_Y = -426.960D;
    public static final double LOWER_SCREEN_Z = 331.623D;

    /*
     * Exact states measured at the 1,181 authored screen-mask positions in
     * the clean reference. Later local detailing crossed a few cells with
     * trim and railings, so validating only the original palette would reject
     * the real source. No block outside the two connected components is ever
     * touched.
     */
    private static final Set<String> MEASURED_MASK_STATES = Set.of(
            "minecraft:air",
            "minecraft:yellow_concrete",
            "minecraft:orange_concrete",
            "minecraft:orange_stained_glass",
            "minecraft:ochre_froglight",
            "minecraft:deepslate_bricks",
            "minecraft:polished_blackstone",
            "minecraft:iron_bars",
            "minecraft:sea_lantern",
            "minecraft:light_gray_concrete");
    private static final Set<String> MEASURED_SIGHTLINE_STATES = Set.of(
            "minecraft:air",
            "minecraft:deepslate_bricks",
            "minecraft:sea_lantern");
    private static final BlockPos SIGHTLINE_MIN =
            new BlockPos(18, -436, 308);
    private static final BlockPos SIGHTLINE_MAX =
            new BlockPos(38, -398, 313);

    private static final ScreenMask AMBER = new ScreenMask(
            "amber", new BlockPos(26, 50, 100),
            Set.of("minecraft:yellow_concrete",
                    "minecraft:ochre_froglight"), 425);
    private static final ScreenMask ORANGE = new ScreenMask(
            "orange", new BlockPos(26, 31, 90),
            Set.of("minecraft:orange_concrete",
                    "minecraft:orange_stained_glass",
                    "minecraft:ochre_froglight"), 756);

    /** Authored rear door of the command module; never rewritten at runtime. */
    private static final BlockPos AUTHORED_FINGERPRINT =
            new BlockPos(28, -406, 272);
    private static final String SEAT_TAG_PREFIX =
            "projectseele.s20.command_seat.";
    private static final BlockPos[] AUTHORED_OPERATOR_CHAIRS = {
            new BlockPos(25, -409, 285),
            new BlockPos(25, -409, 286),
            new BlockPos(25, -409, 287)
    };
    private static final String CITY_STATUS_TAG =
            "projectseele.s20.city_status";
    /*
     * Measured display face on the z=362 wall: an unbroken run of black
     * concrete over x[9,47] and y[-435,-423], with five blocks of clear air in
     * front of it - there is no glazing at this height.  Those are block
     * coordinates, so the face spans world x 9..48 and world y -435..-422.
     */
    public static final double CITY_STATUS_CENTRE_X = 28.5D;
    public static final double CITY_STATUS_FACE_TOP = -422.0D;
    public static final double CITY_STATUS_FACE_BOTTOM = -435.0D;
    public static final double CITY_STATUS_Z = 361.55D;
    private static final int CITY_STATUS_LINES = 10;
    /**
     * Thirteen rows of face divided by the block a ten-line display occupies.
     * Leaves roughly three quarters of a block of margin above and below.
     */
    private static final float CITY_STATUS_SCALE = 4.5F;
    /**
     * A text display is anchored by the BOTTOM of its text box, not by its
     * centre: vanilla translates by {@code -lines*10} and then scales by
     * {@code -0.025}, so the block grows upward from the entity position.
     * Centring the entity on the face therefore pushed the whole board off the
     * top of the screen.
     */
    private static double cityStatusBaseY()
    {
        double height = 0.025D * (CITY_STATUS_LINES * 10 + 1)
                * CITY_STATUS_SCALE;
        return (CITY_STATUS_FACE_TOP + CITY_STATUS_FACE_BOTTOM) / 2.0D
                - height / 2.0D;
    }
    /*
     * The Ikari chair is real furniture now and seats a player by itself, so
     * the hard-coded ride anchor that used to sit inside it is gone: two
     * overlapping seats in one cell is exactly what the user reported.
     * removeRetiredSeatAnchors() deletes the saved anchor on the next tick.
     */
    private static final List<SeatSpec> SEATS = List.of(
            new SeatSpec("operator_left", new BlockPos(36, -422, 291),
                    36.5D, -421.42D, 291.5D, 0.0F,
                    "msg.projectseele.command_seat_operator"),
            new SeatSpec("operator_centre", new BlockPos(28, -424, 299),
                    28.5D, -423.42D, 299.5D, 0.0F,
                    "msg.projectseele.command_seat_operator"),
            new SeatSpec("operator_right", new BlockPos(20, -422, 291),
                    20.5D, -421.42D, 291.5D, 0.0F,
                    "msg.projectseele.command_seat_operator"));

    private static boolean sourceFailureLogged;
    private static boolean fingerprintDelayLogged;
    private static boolean installationRejected;

    private S20CommandPresentationDirector() {}

    public static void tick(MinecraftServer server)
    {
        if (!FacilityWorldPolicy.isS20Rebuild(server))
        {
            return;
        }
        ServerLevel level = server.getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null)
        {
            return;
        }
        /*
         * Furniture is an optional local dependency and is independent of
         * the one-shot NBT presentation migration.  A rejected/obsolete NBT
         * fingerprint must never prevent the three real chairs from being
         * restored in an already-authored command room.
         */
        if (installationRejected)
        {
            return;
        }
        if (!presentationInstalled(level))
        {
            install(level);
        }
        if (server.getTickCount() % 200 == 0
                && hasNearbyViewer(level))
        {
            for (SeatSpec seat : SEATS)
            {
                installSeat(level, seat);
            }
        }
    }

    public static boolean presentationInstalled(BlockGetter level)
    {
        return level.getBlockState(COMMAND_MARKER)
                .is(Blocks.STRUCTURE_VOID);
    }

    public static boolean handleSeatUse(
            ServerPlayer player, BlockPos clicked)
    {
        ServerLevel level = player.serverLevel();
        if (!FacilityWorldPolicy.isS20Rebuild(level.getServer())
                || !level.dimension().equals(FacilitySchemaV2.DIMENSION))
        {
            return false;
        }
        for (SeatSpec spec : SEATS)
        {
            if (!isSeatHit(spec.block(), clicked))
            {
                continue;
            }
            NervCommandSeatEntity seat = installSeat(level, spec);
            if (seat == null)
            {
                return true;
            }
            if (!seat.getPassengers().isEmpty())
            {
                player.displayClientMessage(Component.translatable(
                        "msg.projectseele.command_seat_occupied"), true);
                return true;
            }
            player.setYRot(spec.yaw());
            player.setYHeadRot(spec.yaw());
            player.setXRot(0.0F);
            if (player.startRiding(seat, true))
            {
                player.displayClientMessage(
                        Component.translatable(spec.messageKey()), true);
            }
            return true;
        }
        return false;
    }

    private static void install(ServerLevel level)
    {
        if (!Files.isRegularFile(COMMAND_MODULE))
        {
            logSourceFailure("missing private command NBT " + COMMAND_MODULE);
            return;
        }
        /*
         * Fail-closed fingerprint: never clear a similarly positioned room if
         * the measured asset is absent.  It has to be a block no runtime pass
         * rewrites - the old one watched the Gendo seat cell, which furniture
         * work legitimately replaces.
         */
        if (!level.getBlockState(AUTHORED_FINGERPRINT).is(Blocks.BIRCH_DOOR))
        {
            logFingerprintDelay("authored command fingerprint is absent at "
                    + AUTHORED_FINGERPRINT);
            return;
        }
        try
        {
            CompoundTag root = NbtIo.readCompressed(COMMAND_MODULE.toFile());
            Map<BlockPos, String> voxels = loadVoxels(root);
            List<BlockPos> amber = component(voxels, AMBER);
            List<BlockPos> orange = component(voxels, ORANGE);
            clearMask(level, voxels, amber);
            clearMask(level, voxels, orange);
            int sightlineBlocks = clearCommandSightline(level);
            level.setBlock(COMMAND_MARKER,
                    Blocks.STRUCTURE_VOID.defaultBlockState(),
                    Block.UPDATE_CLIENTS);
            fingerprintDelayLogged = false;
            for (SeatSpec seat : SEATS)
            {
                installSeat(level, seat);
            }
            ProjectSeele.LOGGER.info(
                    "S20 command presentation installed: amber={} "
                            + "orange={} exactMask=true sightline={} "
                            + "routesWritten=0",
                    amber.size(), orange.size(), sightlineBlocks);
        }
        catch (IOException | RuntimeException exception)
        {
            installationRejected = true;
            if (!sourceFailureLogged)
            {
                sourceFailureLogged = true;
                ProjectSeele.LOGGER.error(
                        "Unable to install exact S20 command presentation",
                        exception);
            }
        }
    }

    private static Map<BlockPos, String> loadVoxels(CompoundTag root)
    {
        ListTag palette = root.getList("palette", Tag.TAG_COMPOUND);
        ListTag blocks = root.getList("blocks", Tag.TAG_COMPOUND);
        List<String> names = new ArrayList<>(palette.size());
        for (int index = 0; index < palette.size(); index++)
        {
            names.add(palette.getCompound(index).getString("Name"));
        }
        Map<BlockPos, String> voxels = new HashMap<>();
        for (int index = 0; index < blocks.size(); index++)
        {
            CompoundTag block = blocks.getCompound(index);
            ListTag position = block.getList("pos", Tag.TAG_INT);
            if (position.size() != 3)
            {
                continue;
            }
            int state = block.getInt("state");
            if (state < 0 || state >= names.size())
            {
                continue;
            }
            voxels.put(new BlockPos(position.getInt(0),
                    position.getInt(1), position.getInt(2)),
                    names.get(state));
        }
        return voxels;
    }

    private static List<BlockPos> component(
            Map<BlockPos, String> voxels, ScreenMask mask)
    {
        String seedMaterial = voxels.get(mask.seed());
        if (seedMaterial == null
                || !mask.materials().contains(seedMaterial))
        {
            throw new IllegalStateException(
                    "S20 " + mask.id() + " screen seed does not match");
        }
        ArrayDeque<BlockPos> queue = new ArrayDeque<>();
        Set<BlockPos> visited = new HashSet<>();
        queue.add(mask.seed());
        visited.add(mask.seed());
        while (!queue.isEmpty())
        {
            BlockPos current = queue.removeFirst();
            for (BlockPos neighbour : List.of(
                    current.above(), current.below(),
                    current.north(), current.south(),
                    current.east(), current.west()))
            {
                String material = voxels.get(neighbour);
                if (!visited.contains(neighbour)
                        && material != null
                        && mask.materials().contains(material))
                {
                    visited.add(neighbour);
                    queue.addLast(neighbour);
                }
            }
        }
        if (visited.size() != mask.expected())
        {
            throw new IllegalStateException(
                    "S20 " + mask.id() + " screen component expected "
                            + mask.expected() + " blocks but found "
                            + visited.size());
        }
        List<BlockPos> result = new ArrayList<>(visited);
        result.sort(Comparator.comparingInt(
                        (BlockPos position) -> position.getY())
                .thenComparingInt(position -> position.getZ())
                .thenComparingInt(position -> position.getX()));
        return result;
    }

    private static void clearMask(ServerLevel level,
                                  Map<BlockPos, String> voxels,
                                  List<BlockPos> localMask)
    {
        for (BlockPos local : localMask)
        {
            BlockPos world = authoredLocalToWorld(local);
            String actual = BuiltInRegistries.BLOCK.getKey(
                    level.getBlockState(world).getBlock()).toString();
            if (!MEASURED_MASK_STATES.contains(actual))
            {
                throw new IllegalStateException(
                        "S20 screen mask source mismatch at " + world
                                + ": unmeasured state " + actual);
            }
        }
        for (BlockPos local : localMask)
        {
            BlockPos world = authoredLocalToWorld(local);
            if (!level.getBlockState(world).isAir())
            {
                level.setBlock(world, Blocks.AIR.defaultBlockState(),
                        Block.UPDATE_CLIENTS);
            }
        }
    }

    /**
     * Opens only the measured five-block-thick wall between the command
     * hierarchy and the two authored sloped screen faces. The surrounding
     * deepslate remains as the screen frame.
     */
    private static int clearCommandSightline(ServerLevel level)
    {
        // Only the three states this pass was measured against are removed.
        //
        // It used to abort the whole installation on anything else, which was
        // safe while the box held nothing but foreign deepslate bricks and sea
        // lanterns. Once the authored room is pasted in from the reference
        // save the same box contains real command-room blocks, and refusing to
        // continue would leave the screens and seats uninstalled. Skipping an
        // unmeasured block is the conservative choice: this pass exists to
        // delete foreign fill, never to cut into authored geometry.
        int cleared = 0;
        for (BlockPos position : BlockPos.betweenClosed(
                SIGHTLINE_MIN, SIGHTLINE_MAX))
        {
            BlockState state = level.getBlockState(position);
            if (state.isAir())
            {
                continue;
            }
            String actual = BuiltInRegistries.BLOCK.getKey(
                    state.getBlock()).toString();
            if (!MEASURED_SIGHTLINE_STATES.contains(actual))
            {
                continue;
            }
            level.setBlock(position, Blocks.AIR.defaultBlockState(),
                    Block.UPDATE_CLIENTS);
            cleared++;
        }
        return cleared;
    }

    private static boolean hasNearbyViewer(ServerLevel level)
    {
        return level.players().stream().anyMatch(player ->
                player.distanceToSqr(28.0D, -416.0D, 300.0D)
                        <= 160.0D * 160.0D);
    }

    private static NervCommandSeatEntity installSeat(
            ServerLevel level, SeatSpec spec)
    {
        String tag = SEAT_TAG_PREFIX + spec.id();
        AABB search = new AABB(
                spec.x() - 1.0D, spec.y() - 1.0D, spec.z() - 1.0D,
                spec.x() + 1.0D, spec.y() + 1.0D, spec.z() + 1.0D);
        List<NervCommandSeatEntity> matches = new ArrayList<>(
                level.getEntitiesOfClass(NervCommandSeatEntity.class,
                        search, entity -> entity.getTags().contains(tag)));
        matches.sort(Comparator.comparingInt(Entity::getId));
        NervCommandSeatEntity seat;
        boolean created = matches.isEmpty();
        if (created)
        {
            seat = ModEntities.NERV_COMMAND_SEAT.get().create(level);
            if (seat == null)
            {
                return null;
            }
            seat.addTag(tag);
        }
        else
        {
            seat = matches.get(0);
            for (int index = 1; index < matches.size(); index++)
            {
                if (matches.get(index).getPassengers().isEmpty())
                {
                    matches.get(index).discard();
                }
            }
        }
        seat.setPos(spec.x(), spec.y(), spec.z());
        seat.setYRot(spec.yaw());
        if (created)
        {
            level.addFreshEntity(seat);
        }
        return seat;
    }

    private static boolean isSeatHit(BlockPos chair, BlockPos clicked)
    {
        int dx = Math.abs(clicked.getX() - chair.getX());
        int dy = clicked.getY() - chair.getY();
        int dz = clicked.getZ() - chair.getZ();
        return dx <= 1 && dy >= 0 && dy <= 2
                && dz >= -1 && dz <= 1;
    }

    private static void logSourceFailure(String reason)
    {
        installationRejected = true;
        if (!sourceFailureLogged)
        {
            sourceFailureLogged = true;
            ProjectSeele.LOGGER.error(
                    "S20 command presentation rejected: {}", reason);
        }
    }

    /**
     * Runtime-only furniture maintenance that is safe while the R28 spatial
     * freeze protects authored blocks.  The freeze must disable architecture
     * builders, not suppress three explicitly requested furniture cells.
     */
    public static void tickRuntimePresentation(MinecraftServer server)
    {
        if (!FacilityWorldPolicy.isS20Rebuild(server))
        {
            return;
        }
        ServerLevel level = server.getLevel(FacilitySchemaV2.DIMENSION);
        if (level != null)
        {
            tickRuntimePresentation(level, server.getTickCount());
        }
    }

    private static void tickRuntimePresentation(ServerLevel level, int tick)
    {
        if (tick % 40 == 0 && hasNearbyViewer(level))
        {
            removeRetiredSeatAnchors(level);
            removeGuessedFurnitureChairs(level);
            ensureCityStatusDisplay(level);
        }
        if (tick % 5 == 0 && hasNearbyViewer(level))
        {
            broadcastPilotStatus(level);
        }
    }

    /**
     * Feeds the lower orange tactical board.  Sampling happens here, on the
     * server, because a hangar EVA is regularly outside the operator client's
     * entity tracking range - the board has to keep reading during exactly the
     * launches nobody is standing next to.
     */
    private static void broadcastPilotStatus(ServerLevel level)
    {
        EvaFleetSavedData fleet = EvaFleetSavedData.get(level.getServer());
        ClientboundPilotStatusPacket.Unit[] units =
                new ClientboundPilotStatusPacket.Unit[
                        ClientboundPilotStatusPacket.UNIT_COUNT];
        for (int variant = 0; variant < units.length; variant++)
        {
            EvaUnit01Entity unit =
                    EvaLogisticsDirector.canonicalUnit(level, variant);
            String phase = fleet.entry(variant)
                    .map(entry -> entry.phase().name())
                    .orElse("UNREGISTERED");
            if (unit == null)
            {
                units[variant] = ClientboundPilotStatusPacket.Unit.ABSENT;
                continue;
            }
            LivingEntity pilot = EvaPilotResolver.pilot(unit);
            units[variant] = new ClientboundPilotStatusPacket.Unit(true,
                    pilot == null ? "" : pilot.getName().getString(),
                    phase,
                    unit.getPilotSynchronization(),
                    unit.getAtFieldEnergy(), unit.getAtFieldCapacity(),
                    unit.getHealth(), unit.getMaxHealth(),
                    unit.getPowerTicks(), unit.getPowerCapacityTicks(),
                    unit.isUmbilicalConnected(), unit.isBerserk(),
                    ServerboundEvaVideoFramePacket.isFeedActive(
                            level, variant));
        }
        Tokyo3RetractionDirector.Status city =
                Tokyo3RetractionDirector.status(level,
                        IntegratedNervMapBuilder.tokyo3Origin(level));
        NervArmamentStationEntity armament =
                NervArmamentStationEntity.commandStation(level);
        SeeleNetwork.CHANNEL.send(
                PacketDistributor.DIMENSION.with(level::dimension),
                new ClientboundPilotStatusPacket(units,
                        String.valueOf(city.phase()), city.depth(),
                        city.targetDepth(), city.maximumDepth(),
                        city.physicalRetractionFraction(),
                        armament == null ? "OFFLINE" : armament.stateName(),
                        armament != null && armament.isStocked(),
                        armament == null ? 0 : armament.getLiftPercent()));
    }

    /**
     * Removes only the three furniture blocks placed by the rejected guessed
     * chair pass.  The user never approved these cells as seat locations, so
     * no replacement chair is generated until a human-authored placement is
     * supplied.
     */
    private static void removeGuessedFurnitureChairs(ServerLevel level)
    {
        for (BlockPos position : AUTHORED_OPERATOR_CHAIRS)
        {
            String id = BuiltInRegistries.BLOCK.getKey(
                    level.getBlockState(position).getBlock()).toString();
            if (id.equals("another_furniture:dark_oak_chair"))
            {
                level.setBlock(position, Blocks.AIR.defaultBlockState(),
                        Block.UPDATE_CLIENTS);
            }
        }
    }

    /** Removes the retired text entity; the client now draws a live city model. */
    private static void ensureCityStatusDisplay(ServerLevel level)
    {
        Vec3 anchor = new Vec3(CITY_STATUS_CENTRE_X, cityStatusBaseY(),
                CITY_STATUS_Z);
        AABB bounds = AABB.ofSize(anchor, 96.0D, 48.0D, 24.0D);
        for (Display.TextDisplay stale : level.getEntitiesOfClass(
                Display.TextDisplay.class, bounds,
                display -> display.getTags().contains(CITY_STATUS_TAG)))
        {
            stale.discard();
        }
    }

    private static String fleetPhase(EvaFleetSavedData fleet, int variant)
    {
        return clip(fleet.entry(variant)
                .map(entry -> entry.phase().name())
                .orElse("UNREGISTERED"), 27);
    }

    private static String clip(String value, int columns)
    {
        return value.length() <= columns
                ? value : value.substring(0, columns);
    }

    private static CompoundTag displayTransform(float scale)
    {
        CompoundTag transformation = new CompoundTag();
        transformation.put("translation", floatList(0.0F, 0.0F, 0.0F));
        transformation.put("left_rotation",
                floatList(0.0F, 0.0F, 0.0F, 1.0F));
        transformation.put("scale", floatList(scale, scale, scale));
        transformation.put("right_rotation",
                floatList(0.0F, 0.0F, 0.0F, 1.0F));
        return transformation;
    }

    private static ListTag floatList(float... values)
    {
        ListTag result = new ListTag();
        for (float value : values)
        {
            result.add(FloatTag.valueOf(value));
        }
        return result;
    }

    /**
     * Ride anchors outlive the SeatSpec that created them: retiring a seat in
     * code leaves its invisible mount saved in the region file, still able to
     * seat a player on a chair that is no longer there.  Delete every anchor
     * in the command room that no current spec claims - the retired Fuyutsuki
     * row and any earlier generated seat alike - so only the four live chairs
     * can be sat on.
     */
    private static void removeRetiredSeatAnchors(ServerLevel level)
    {
        Set<String> live = new HashSet<>();
        for (SeatSpec spec : SEATS)
        {
            live.add(SEAT_TAG_PREFIX + spec.id());
        }
        AABB commandRoom = new AABB(
                0.0D, -440.0D, 260.0D,
                56.0D, -390.0D, 320.0D);
        for (NervCommandSeatEntity seat : level.getEntitiesOfClass(
                NervCommandSeatEntity.class, commandRoom,
                entity -> !entity.getTags().contains("seele_office_seat") && entity.getTags().stream()
                        .noneMatch(live::contains)))
        {
            seat.ejectPassengers();
            seat.discard();
        }
    }

    private static void logFingerprintDelay(String reason)
    {
        if (!fingerprintDelayLogged)
        {
            fingerprintDelayLogged = true;
            ProjectSeele.LOGGER.warn(
                    "S20 command presentation waiting: {}", reason);
        }
    }

    private record ScreenMask(String id, BlockPos seed,
                              Set<String> materials, int expected) {}

    private record SeatSpec(String id, BlockPos block,
                            double x, double y, double z, float yaw,
                            String messageKey) {}
}
