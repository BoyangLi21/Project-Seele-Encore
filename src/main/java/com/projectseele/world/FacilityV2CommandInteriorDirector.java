package com.projectseele.world;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervCommandSeatEntity;
import com.projectseele.registry.ModEntities;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.FloatTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Display;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.LecternBlock;
import net.minecraft.world.level.block.StairBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/**
 * Original-series-inspired presentation layer for Facility v2 command.
 *
 * <p>The room shell, exits and accepted circulation stay owned by
 * {@link CommandVolumeV2Plan}.  This layer only replaces furniture and the
 * former voxel video wall, so an existing save receives the art direction
 * update without regenerating or disconnecting the command complex.</p>
 */
public final class FacilityV2CommandInteriorDirector
{
    public static final int INTERIOR_REVISION = 9;
    public static final int MARKER_X = 1;
    public static final int MARKER_Y = -309;
    public static final int MARKER_Z = 10;

    private static final int MAX_WRITES_PER_TICK = 8192;
    private static final long MAX_NANOS_PER_TICK = 8_000_000L;
    private static final int DISPLAY_REPAIR_INTERVAL = 200;
    private static final String DISPLAY_TAG_PREFIX =
            "projectseele.facility_v2.command_hologram.";
    private static final String SEAT_TAG_PREFIX =
            "projectseele.facility_v2.command_seat.";

    private static final BlockState AIR = Blocks.AIR.defaultBlockState();
    private static final BlockState BLACK =
            Blocks.BLACK_CONCRETE.defaultBlockState();
    private static final BlockState DARK =
            Blocks.POLISHED_BLACKSTONE.defaultBlockState();
    private static final BlockState STRUCTURE =
            Blocks.POLISHED_BLACKSTONE_BRICKS.defaultBlockState();
    private static final BlockState ORANGE =
            Blocks.ORANGE_CONCRETE.defaultBlockState();
    private static final BlockState RED =
            Blocks.RED_NETHER_BRICKS.defaultBlockState();
    private static final BlockState WHITE =
            Blocks.QUARTZ_BLOCK.defaultBlockState();
    private static final BlockState LIGHT =
            Blocks.SEA_LANTERN.defaultBlockState();
    private static final BlockState GLASS =
            Blocks.TINTED_GLASS.defaultBlockState();
    private static final BlockState NORTH_STAIR =
            Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS.defaultBlockState()
                    .setValue(StairBlock.FACING, Direction.NORTH);
    private static final BlockState WEST_STAIR =
            Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS.defaultBlockState()
                    .setValue(StairBlock.FACING, Direction.WEST);
    private static final BlockState COMMAND_SEAT =
            Blocks.POLISHED_BLACKSTONE_BRICK_STAIRS.defaultBlockState()
                    .setValue(StairBlock.FACING, Direction.NORTH);
    private static final BlockState OPERATOR_SEAT =
            Blocks.SMOOTH_QUARTZ_STAIRS.defaultBlockState()
                    .setValue(StairBlock.FACING, Direction.NORTH);
    private static final BlockState CONSOLE =
            Blocks.LECTERN.defaultBlockState()
                    .setValue(LecternBlock.FACING, Direction.NORTH);

    private static final List<RelativeWrite> WRITES = buildWrites();
    private static final List<PanelSpec> PANELS = List.of(
            /*
             * These are the two authored dummy planes, not a new video wall.
             * Their centres and complementary X rotations come from the
             * measured 1:1 NBT masks in S19_LOCAL_COMMAND_ASSET_AUDIT.md.
             */
            new PanelSpec("authored_amber_upper",
                    1.0D, -319.5D, -36.0D,
                    15.0F, 34.5F, 0.0F, -27.3F,
                    Blocks.YELLOW_STAINED_GLASS.defaultBlockState(),
                    0xFFFFB02E),
            new PanelSpec("authored_orange_lower",
                    1.0D, -330.5D, -45.0D,
                    15.0F, 40.5F, 0.0F, -68.8F,
                    Blocks.ORANGE_STAINED_GLASS.defaultBlockState(),
                    0xFFFF7028));
    private static final List<LabelSpec> LABELS = List.of(
            new LabelSpec("upper_feed_label",
                    1.0D, -319.3D, -35.7D,
                    0.0F, -27.3F, 1.05F,
                    "EVA-00     EVA-01     EVA-02\n"
                            + "ENTRY PLUG OPTICAL FEEDS",
                    ChatFormatting.GOLD, 0xFFFFB02E),
            new LabelSpec("lower_magi_label",
                    1.0D, -330.2D, -44.7D,
                    0.0F, -68.8F, 1.15F,
                    "MAGI / CENTRAL COMMAND\n"
                            + "TACTICAL STATUS  ·  LAUNCH CONTROL",
                    ChatFormatting.RED, 0xFFFF7028));
    private static final List<SeatSpec> SEATS = List.of(
            // These anchors are transformed authored copper-slab chairs from
            // nerv_command_left.nbt, not guessed furniture laid over it.
            new SeatSpec("ikari", 1, -309, 10,
                    1.5D, -308.42D, 10.5D, 180.0F,
                    "msg.projectseele.command_seat_ikari"),
            new SeatSpec("fuyutsuki", 4, -312, 1,
                    4.5D, -311.42D, 1.5D, 180.0F,
                    "msg.projectseele.command_seat_fuyutsuki"),
            new SeatSpec("operator_left", -7, -325, -4,
                    -6.5D, -324.42D, -3.5D, 180.0F,
                    "msg.projectseele.command_seat_operator"),
            new SeatSpec("operator_centre", 1, -327, -12,
                    1.5D, -326.42D, -11.5D, 180.0F,
                    "msg.projectseele.command_seat_operator"),
            new SeatSpec("operator_right", 9, -325, -4,
                    9.5D, -324.42D, -3.5D, 180.0F,
                    "msg.projectseele.command_seat_operator"));

    private FacilityV2CommandInteriorDirector() {}

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
        if (!facility.commissioned()
                || facility.requireZone("COMMAND_VOLUME").state()
                != FacilityV2SavedData.ZoneState.COMPLETE
                || facility.requireZone("COMMAND_MODULE_CAP").state()
                != FacilityV2SavedData.ZoneState.COMPLETE)
        {
            return;
        }

        FacilityV2CommandInteriorSavedData interior =
                FacilityV2CommandInteriorSavedData.get(level);
        interior.prepare(INTERIOR_REVISION);
        if (interior.needsWork(INTERIOR_REVISION))
        {
            advance(level, facility.manifest(), interior);
            return;
        }

        if (server.getTickCount() % DISPLAY_REPAIR_INTERVAL == 0
                && hasNearbyViewer(level, facility.manifest().centre()))
        {
            installDisplays(level, facility.manifest().centre());
        }
    }

    public static void reset(ServerLevel level)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        FacilityWorldPolicy.requireCleanRebuild(level.getServer(),
                "FacilityV2CommandInteriorDirector.reset");
        FacilityV2CommandInteriorSavedData.get(level).reset();
    }

    public static boolean handleSeatUse(ServerPlayer player, BlockPos clicked)
    {
        if (NervLegacyGenerationGuardR52.retired(player.serverLevel())) return false;
        ServerLevel level = player.serverLevel();
        if (!FacilityWorldPolicy.isCleanRebuild(level.getServer())
                || !level.dimension().equals(FacilitySchemaV2.DIMENSION))
        {
            return false;
        }
        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        if (!facility.commissioned()
                || facility.requireZone("COMMAND_VOLUME").state()
                != FacilityV2SavedData.ZoneState.COMPLETE
                || facility.requireZone("COMMAND_MODULE_CAP").state()
                != FacilityV2SavedData.ZoneState.COMPLETE)
        {
            return false;
        }

        BlockPos centre = facility.manifest().centre();
        for (SeatSpec spec : SEATS)
        {
            BlockPos chair = centre.offset(
                    spec.blockX(), spec.blockY(), spec.blockZ());
            if (!isSeatHit(chair, clicked))
            {
                continue;
            }
            NervCommandSeatEntity seat = installSeat(level, centre, spec);
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

    private static boolean isSeatHit(BlockPos chair, BlockPos clicked)
    {
        int dx = Math.abs(clicked.getX() - chair.getX());
        int dy = clicked.getY() - chair.getY();
        int dz = clicked.getZ() - chair.getZ();
        // The visible backrest hides the stair when approached from the rear.
        // Treat the chair, its two arm blocks and the two-block backrest as
        // one interaction target while keeping nearby consoles independent.
        return dx <= 1 && dy >= 0 && dy <= 2
                && dz >= 0 && dz <= 1;
    }

    private static void advance(
            ServerLevel level,
            FacilitySchemaV2.ResolvedManifest manifest,
            FacilityV2CommandInteriorSavedData data)
    {
        long cursor = Math.min(data.cursor(), WRITES.size());
        int changed = 0;
        long started = System.nanoTime();
        BlockPos centre = manifest.centre();
        if (!data.commandAssetInstalled())
        {
            if (!LocalMapAssetLoader.placeCommandModuleV2(level, centre))
            {
                return;
            }
            removeRetiredPresentationEntities(level, centre);
            data.markCommandAssetInstalled();
        }
        while (cursor < WRITES.size()
                && changed < MAX_WRITES_PER_TICK
                && System.nanoTime() - started < MAX_NANOS_PER_TICK)
        {
            RelativeWrite write = WRITES.get((int) cursor);
            cursor++;
            BlockPos position = centre.offset(write.x(), write.y(), write.z());
            BlockState current = level.getBlockState(position);
            if (write.expected() != null
                    && !current.is(write.expected()))
            {
                continue;
            }
            if (current.equals(write.state()))
            {
                continue;
            }
            level.setBlock(position, write.state(),
                    net.minecraft.world.level.block.Block.UPDATE_CLIENTS);
            changed++;
        }
        data.updateCursor(cursor);
        if (cursor >= WRITES.size())
        {
            installDisplays(level, centre);
            data.complete(INTERIOR_REVISION);
            ProjectSeele.LOGGER.info(
                    "Facility v2 command presentation revision {} installed: "
                            + "writes={} panels={} labels={} seats={}",
                    INTERIOR_REVISION, WRITES.size(), PANELS.size(),
                    LABELS.size(), SEATS.size());
        }
    }

    private static boolean hasNearbyViewer(ServerLevel level, BlockPos centre)
    {
        Vec3 command = Vec3.atCenterOf(centre.offset(0, -334, 0));
        return level.players().stream().anyMatch(player ->
                player.position().distanceToSqr(command) <= 180.0D * 180.0D);
    }

    private static void installDisplays(ServerLevel level, BlockPos centre)
    {
        level.getChunkAt(centre.offset(0, -332, -64));
        NervOperationsConsole.installImportedV2Controls(level, centre);
        for (PanelSpec panel : PANELS)
        {
            installPanel(level, centre, panel);
        }
        for (LabelSpec label : LABELS)
        {
            installLabel(level, centre, label);
        }
        for (SeatSpec seat : SEATS)
        {
            installSeat(level, centre, seat);
        }
    }

    private static void removeRetiredPresentationEntities(
            ServerLevel level, BlockPos centre)
    {
        AABB bounds = new AABB(
                centre.getX() - 64.0D, -372.0D,
                centre.getZ() - 80.0D,
                centre.getX() + 76.0D, -288.0D,
                centre.getZ() + 80.0D);
        level.getEntitiesOfClass(Display.class, bounds,
                        entity -> entity.getTags().contains(
                                DISPLAY_TAG_PREFIX + "all"))
                .forEach(Entity::discard);
        level.getEntitiesOfClass(NervCommandSeatEntity.class, bounds,
                        entity -> entity.getTags().contains(
                                SEAT_TAG_PREFIX + "all")
                                && entity.getPassengers().isEmpty())
                .forEach(Entity::discard);
    }

    private static NervCommandSeatEntity installSeat(
            ServerLevel level, BlockPos centre, SeatSpec spec)
    {
        String tag = SEAT_TAG_PREFIX + spec.id();
        AABB bounds = new AABB(
                centre.getX() - 32.0D, -345.0D,
                centre.getZ() - 20.0D,
                centre.getX() + 32.0D, -314.0D,
                centre.getZ() + 48.0D);
        List<NervCommandSeatEntity> matches = new ArrayList<>(
                level.getEntitiesOfClass(NervCommandSeatEntity.class, bounds,
                        entity -> entity.getTags().contains(tag)));
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
            seat.addTag(SEAT_TAG_PREFIX + "all");
        }
        else
        {
            seat = matches.get(0);
            discardDuplicates(matches);
        }
        seat.setPos(centre.getX() + spec.anchorX(),
                centre.getY() + spec.anchorY(),
                centre.getZ() + spec.anchorZ());
        seat.setYRot(spec.yaw());
        if (created)
        {
            level.addFreshEntity(seat);
        }
        return seat;
    }

    private static void installPanel(ServerLevel level, BlockPos centre,
                                     PanelSpec spec)
    {
        String tag = DISPLAY_TAG_PREFIX + "panel." + spec.id();
        List<Display.BlockDisplay> matches = displays(
                level, centre, Display.BlockDisplay.class, tag);
        Display.BlockDisplay display;
        boolean created = matches.isEmpty();
        if (created)
        {
            display = EntityType.BLOCK_DISPLAY.create(level);
            if (display == null)
            {
                return;
            }
            prepareDisplay(display, tag);
        }
        else
        {
            display = matches.get(0);
            discardDuplicates(matches);
        }

        CompoundTag nbt = display.saveWithoutId(new CompoundTag());
        CompoundTag blockState = new CompoundTag();
        blockState.putString("Name", BuiltInRegistries.BLOCK
                .getKey(spec.state().getBlock()).toString());
        nbt.put("block_state", blockState);
        nbt.put("transformation", transformation(
                -spec.width() * 0.5F,
                -spec.height() * 0.5F, -0.04F,
                spec.width(), spec.height(), 0.08F));
        nbt.putString("billboard", "fixed");
        nbt.putFloat("view_range", 4.0F);
        nbt.putFloat("width", spec.width() + 4.0F);
        nbt.putFloat("height", spec.height() + 4.0F);
        nbt.putInt("glow_color_override", spec.glow());
        nbt.putFloat("shadow_radius", 0.0F);
        nbt.putFloat("shadow_strength", 0.0F);
        putFullBrightness(nbt);
        display.load(nbt);
        display.setPos(centre.getX() + spec.x() + 0.5D,
                spec.y(), centre.getZ() + spec.z() + 0.5D);
        display.setYRot(spec.yaw());
        display.setXRot(spec.pitch());
        if (created)
        {
            level.addFreshEntity(display);
        }
    }

    private static void installLabel(ServerLevel level, BlockPos centre,
                                     LabelSpec spec)
    {
        String tag = DISPLAY_TAG_PREFIX + "label." + spec.id();
        List<Display.TextDisplay> matches = displays(
                level, centre, Display.TextDisplay.class, tag);
        Display.TextDisplay display;
        boolean created = matches.isEmpty();
        if (created)
        {
            display = EntityType.TEXT_DISPLAY.create(level);
            if (display == null)
            {
                return;
            }
            prepareDisplay(display, tag);
        }
        else
        {
            display = matches.get(0);
            discardDuplicates(matches);
        }

        Component text = Component.literal(spec.text())
                .withStyle(spec.colour(), ChatFormatting.BOLD);
        CompoundTag nbt = display.saveWithoutId(new CompoundTag());
        nbt.putString("text", Component.Serializer.toJson(text));
        nbt.putInt("line_width", 220);
        nbt.putInt("background", 0x68101820);
        nbt.putByte("text_opacity", (byte) -1);
        nbt.putBoolean("shadow", true);
        nbt.putBoolean("see_through", true);
        nbt.putBoolean("default_background", false);
        nbt.putString("alignment", "center");
        nbt.putString("billboard", "fixed");
        nbt.putFloat("view_range", 4.0F);
        nbt.putFloat("width", 16.0F);
        nbt.putFloat("height", 8.0F);
        nbt.putInt("glow_color_override", spec.glow());
        putFullBrightness(nbt);
        nbt.put("transformation", transformation(
                0.0F, 0.0F, 0.0F,
                spec.scale(), spec.scale(), spec.scale()));
        display.load(nbt);
        display.setPos(centre.getX() + spec.x() + 0.5D,
                spec.y(), centre.getZ() + spec.z() + 0.5D);
        display.setYRot(spec.yaw());
        display.setXRot(spec.pitch());
        if (created)
        {
            level.addFreshEntity(display);
        }
    }

    private static void prepareDisplay(Display display, String tag)
    {
        display.addTag(tag);
        display.addTag(DISPLAY_TAG_PREFIX + "all");
        display.setNoGravity(true);
        display.setInvulnerable(true);
        display.setSilent(true);
    }

    private static void putFullBrightness(CompoundTag nbt)
    {
        CompoundTag brightness = new CompoundTag();
        brightness.putInt("block", 15);
        brightness.putInt("sky", 15);
        nbt.put("brightness", brightness);
    }

    private static CompoundTag transformation(
            float translateX, float translateY, float translateZ,
            float scaleX, float scaleY, float scaleZ)
    {
        CompoundTag transformation = new CompoundTag();
        transformation.put("translation", floatList(
                translateX, translateY, translateZ));
        transformation.put("left_rotation", floatList(
                0.0F, 0.0F, 0.0F, 1.0F));
        transformation.put("scale", floatList(scaleX, scaleY, scaleZ));
        transformation.put("right_rotation", floatList(
                0.0F, 0.0F, 0.0F, 1.0F));
        return transformation;
    }

    private static ListTag floatList(float... values)
    {
        ListTag list = new ListTag();
        for (float value : values)
        {
            list.add(FloatTag.valueOf(value));
        }
        return list;
    }

    private static <T extends Display> List<T> displays(
            ServerLevel level, BlockPos centre, Class<T> type, String tag)
    {
        AABB bounds = new AABB(
                centre.getX() - 60.0D, -368.0D,
                centre.getZ() - 76.0D,
                centre.getX() + 60.0D, -304.0D,
                centre.getZ() + 76.0D);
        List<T> result = new ArrayList<>(
                level.getEntitiesOfClass(type, bounds,
                        entity -> entity.getTags().contains(tag)));
        result.sort(Comparator.comparingInt(Entity::getId));
        return result;
    }

    private static <T extends Entity> void discardDuplicates(List<T> matches)
    {
        for (int index = 1; index < matches.size(); index++)
        {
            matches.get(index).discard();
        }
    }

    private static List<RelativeWrite> buildWrites()
    {
        List<RelativeWrite> writes = new ArrayList<>();

        replaceAuthoredScreenDummies(writes);
        buildCommanderRearSleeve(writes);
        buildCommanderSecureRoute(writes);
        buildOfficeLiftRoute(writes);
        buildAuthoredSouthEntry(writes);
        buildStaffServiceRoute(writes);
        set(writes, MARKER_X, MARKER_Y, MARKER_Z,
                Blocks.WAXED_EXPOSED_CUT_COPPER_SLAB.defaultBlockState());
        return List.copyOf(writes);
    }

    /**
     * Turns only the coloured dummy material into translucent emissive screen
     * faces. Froglight ribs and every structural voxel of the private command
     * asset remain untouched.
     */
    private static void replaceAuthoredScreenDummies(
            List<RelativeWrite> writes)
    {
        for (int y = -334; y <= -304; y++)
        {
            for (int z = -44; z <= -28; z++)
            {
                for (int x = -7; x <= 9; x++)
                {
                    replace(writes, x, y, z, Blocks.YELLOW_CONCRETE,
                            Blocks.YELLOW_STAINED_GLASS
                                    .defaultBlockState());
                }
            }
        }
        for (int y = -338; y <= -322; y++)
        {
            for (int z = -64; z <= -26; z++)
            {
                for (int x = -7; x <= 9; x++)
                {
                    replace(writes, x, y, z, Blocks.ORANGE_CONCRETE,
                            Blocks.ORANGE_STAINED_GLASS
                                    .defaultBlockState());
                }
            }
        }
    }

    /**
     * The authored rear door already leads through the command tower to
     * z=27. This supported straight sleeve occupies only the measured empty
     * z=28..64 volume. The measured rear doorway remains the only opening in
     * the imported asset; the continuation beyond z=64 is authored entirely
     * outside the NBT envelope by {@link #buildCommanderSecureRoute(List)}.
     */
    private static void buildCommanderRearSleeve(
            List<RelativeWrite> writes)
    {
        for (int z = 28; z <= 64; z++)
        {
            for (int x = -5; x <= 5; x++)
            {
                set(writes, x, -310, z,
                        Math.floorMod(x + z, 7) == 0 ? LIGHT : DARK);
                set(writes, x, -301, z, STRUCTURE);
                for (int y = -309; y <= -302; y++)
                {
                    boolean wall = Math.abs(x) == 5;
                    set(writes, x, y, z,
                            wall ? (y == -306 ? ORANGE : STRUCTURE) : AIR);
                }
            }
        }

    }

    /**
     * Connects the authored commander rear door to the registered L3 secure
     * lift lobby at x=55/z=48. The route stays beyond the measured command
     * asset envelope, changes level in one orthogonal flight, and opens only
     * the reciprocal H7x7 lift port.
     */
    private static void buildCommanderSecureRoute(
            List<RelativeWrite> writes)
    {
        // Full-height turn room. North is the existing rear sleeve, east is
        // the single straight stair flight.
        for (int x = -5; x <= 6; x++)
        {
            for (int z = 64; z <= 72; z++)
            {
                set(writes, x, -310, z,
                        Math.floorMod(x + z, 7) == 0 ? LIGHT : DARK);
                set(writes, x, -301, z, STRUCTURE);
                for (int y = -309; y <= -302; y++)
                {
                    boolean northEdge = z == 64
                            && (x < -4 || x > 4);
                    boolean wall = x == -5 || z == 72 || northEdge;
                    set(writes, x, y, z,
                            wall ? (y == -306 ? ORANGE : STRUCTURE) : AIR);
                }
            }
        }

        // Descend exactly fifteen blocks from the commander platform datum
        // to the registered secure-lobby floor. Direction.WEST means the
        // stairs rise westward and therefore descend while walking east.
        for (int x = 7; x <= 22; x++)
        {
            int treadY = -310 - (x - 7);
            for (int z = 65; z <= 71; z++)
            {
                set(writes, x, treadY, z, WEST_STAIR);
                for (int y = treadY + 1; y <= treadY + 6; y++)
                {
                    set(writes, x, y, z, AIR);
                }
                set(writes, x, treadY + 7, z, STRUCTURE);
            }
            for (int z : new int[] {64, 72})
            {
                for (int y = treadY; y <= treadY + 7; y++)
                {
                    set(writes, x, y, z,
                            y == treadY + 3 ? ORANGE : STRUCTURE);
                }
            }
        }

        // Low east-west approach. Leave a seven-wide opening in its north
        // wall for the final turn toward the lift.
        for (int x = 23; x <= 55; x++)
        {
            for (int z = 64; z <= 72; z++)
            {
                boolean northOpening = z == 64 && x >= 49;
                set(writes, x, -325, z,
                        Math.floorMod(x + z, 8) == 0 ? LIGHT : DARK);
                set(writes, x, -317, z, STRUCTURE);
                for (int y = -324; y <= -318; y++)
                {
                    boolean wall = z == 72
                            || (z == 64 && !northOpening);
                    set(writes, x, y, z,
                            wall ? (y == -321 ? ORANGE : STRUCTURE) : AIR);
                }
            }
        }

        // North leg terminates at the already-declared CV-EL-CMD aperture.
        // x=56 belongs to CMD_LIFT_SPINE and is deliberately untouched.
        for (int x = 48; x <= 55; x++)
        {
            for (int z = 44; z <= 65; z++)
            {
                set(writes, x, -325, z,
                        Math.floorMod(x + z, 8) == 0 ? LIGHT : DARK);
                set(writes, x, -317, z, STRUCTURE);
                for (int y = -324; y <= -318; y++)
                {
                    boolean liftPort = x == 55 && z >= 45 && z <= 51;
                    boolean wall = x == 48 || z == 44
                            || (x == 55 && !liftPort);
                    set(writes, x, y, z,
                            wall ? (y == -321 ? ORANGE : STRUCTURE) : AIR);
                }
            }
        }
    }

    /**
     * Extends the authored east operator balcony to the L2 command-lift
     * landing.  The imported room has a real walkable white platform through
     * x=22 around z=0, followed by a four-block decorative facade with no
     * floor.  This route opens that facade deliberately, rather than assuming
     * the visually adjacent CV-OFFICE aperture is already reachable.
     */
    private static void buildOfficeLiftRoute(List<RelativeWrite> writes)
    {
        // Seven-block interior from the measured authored balcony to the
        // east turn. x=23..27 replaces only the facade in front of that
        // existing platform; x=28 onward is outside the NBT envelope.
        for (int x = 23; x <= 55; x++)
        {
            for (int z = -4; z <= 4; z++)
            {
                boolean southOpening = z == 4 && x >= 48 && x <= 54;
                set(writes, x, -333, z,
                        Math.floorMod(x + z, 8) == 0 ? LIGHT : DARK);
                set(writes, x, -326, z, STRUCTURE);
                for (int y = -332; y <= -327; y++)
                {
                    boolean wall = z == -4
                            || (z == 4 && !southOpening)
                            || x == 55;
                    set(writes, x, y, z,
                            wall ? (y == -330 ? ORANGE : STRUCTURE) : AIR);
                }
            }
        }

        // Orthogonal south leg ends at the exact H7x7 CV-OFFICE aperture.
        // x=56 is owned by CMD_LIFT_SPINE and remains untouched.
        for (int x = 47; x <= 55; x++)
        {
            for (int z = 4; z <= 28; z++)
            {
                set(writes, x, -333, z,
                        Math.floorMod(x + z, 8) == 0 ? LIGHT : DARK);
                set(writes, x, -326, z, STRUCTURE);
                for (int y = -332; y <= -327; y++)
                {
                    boolean westWall = x == 47;
                    boolean liftPort = x == 55
                            && z >= 21 && z <= 27;
                    boolean eastWall = x == 55 && !liftPort;
                    boolean southWall = z == 28;
                    boolean northWall = z == 4
                            && (x < 48 || x > 54);
                    boolean wall = westWall || eastWall
                            || southWall || northWall;
                    set(writes, x, y, z,
                            wall ? (y == -330 ? ORANGE : STRUCTURE) : AIR);
                }
            }
        }
    }

    /**
     * The imported room ends at z=64.  This pressure corridor cuts one clear,
     * centred doorway and continues onto the registered H-01/foyer route.
     */
    private static void buildAuthoredSouthEntry(List<RelativeWrite> writes)
    {
        for (int z = 58; z <= 75; z++)
        {
            for (int x = -5; x <= 5; x++)
            {
                set(writes, x, -333, z,
                        Math.floorMod(x + z, 7) == 0 ? LIGHT : DARK);
                set(writes, x, -325, z, STRUCTURE);
                for (int y = -332; y <= -326; y++)
                {
                    set(writes, x, y, z,
                            Math.abs(x) == 5 ? STRUCTURE : AIR);
                }
            }
        }
        for (int y = -332; y <= -326; y++)
        {
            set(writes, -4, y, 64,
                    y == -329 ? ORANGE : AIR);
            set(writes, 4, y, 64,
                    y == -329 ? ORANGE : AIR);
        }
    }

    /**
     * Continues the H-01 lower threshold to the registered staff lift. This is
     * the normal personnel route from command to the three wet cages; it stays
     * one structural layer below the commander secure route and entirely
     * south/east of the measured NBT envelope.
     */
    private static void buildStaffServiceRoute(
            List<RelativeWrite> writes)
    {
        // Cut a supported side doorway through the east wall of the H-01
        // passage. Merely starting the new corridor at x=6 left the existing
        // x=5 wall intact and made two adjacent routes physically disjoint.
        for (int z = 68; z <= 74; z++)
        {
            set(writes, 5, -333, z,
                    Math.floorMod(z, 7) == 0 ? LIGHT : DARK);
            for (int y = -332; y <= -327; y++)
            {
                set(writes, 5, y, z, AIR);
            }
            set(writes, 5, -326, z, STRUCTURE);
        }

        // Eastbound lower corridor begins directly beside the centred H-01
        // passage. z=66 is already beyond the authored asset's z=64 limit.
        for (int x = 6; x <= 55; x++)
        {
            for (int z = 66; z <= 75; z++)
            {
                boolean northOpening = z == 66 && x >= 48;
                set(writes, x, -333, z,
                        Math.floorMod(x + z, 8) == 0 ? LIGHT : DARK);
                set(writes, x, -326, z, STRUCTURE);
                for (int y = -332; y <= -327; y++)
                {
                    boolean wall = z == 75
                            || (z == 66 && !northOpening);
                    set(writes, x, y, z,
                            wall ? (y == -330 ? ORANGE : STRUCTURE) : AIR);
                }
            }
        }

        // North turn reaches the exact H7x6 CV-EL-STAFF aperture. x=56 is
        // owned by STAFF_LIFT_SHAFT and remains untouched.
        for (int x = 48; x <= 55; x++)
        {
            for (int z = 60; z <= 67; z++)
            {
                set(writes, x, -333, z,
                        Math.floorMod(x + z, 8) == 0 ? LIGHT : DARK);
                set(writes, x, -326, z, STRUCTURE);
                for (int y = -332; y <= -327; y++)
                {
                    boolean liftPort = x == 55
                            && z >= 61 && z <= 67;
                    boolean wall = x == 48 || z == 60
                            || (x == 55 && !liftPort);
                    set(writes, x, y, z,
                            wall ? (y == -330 ? ORANGE : STRUCTURE) : AIR);
                }
            }
        }
    }

    private static void buildScreenProscenium(List<RelativeWrite> writes)
    {
        for (int y = -346; y <= -318; y++)
        {
            for (int x : new int[] {-40, -39, 39, 40})
            {
                set(writes, x, y, -72,
                        Math.floorMod(y + 346, 7) == 0 ? LIGHT : STRUCTURE);
            }
        }
        for (int x = -40; x <= 40; x++)
        {
            set(writes, x, -318, -72,
                    Math.floorMod(x + 40, 8) == 0 ? LIGHT : STRUCTURE);
            if (Math.abs(x) <= 36)
            {
                set(writes, x, -346, -72,
                        Math.floorMod(x, 6) == 0 ? ORANGE : BLACK);
            }
        }
        for (int x : new int[] {-28, 28})
        {
            for (int y = -343; y <= -321; y++)
            {
                set(writes, x, y, -71,
                        Math.floorMod(y + 343, 5) == 0 ? ORANGE : BLACK);
            }
        }
    }

    private static void buildCommanderDais(List<RelativeWrite> writes)
    {
        // One rear-wide, forward-tapered command tower. It borrows the old
        // module's unmistakable prow, but every block is re-authored to V2's
        // continuous L3 floor and accepted routes.
        buildTaperedCommandDeck(writes);

        // Ikari alone occupies the sole raised optical axis. The plinth is
        // only one step above L3; Fuyutsuki stays on L3 at the east/rear side.
        for (int z = 30; z <= 39; z++)
        {
            for (int x = -5; x <= 5; x++)
            {
                boolean rim = Math.abs(x) == 5 || z == 30;
                set(writes, x, -324, z, rim ? RED : BLACK);
            }
        }
        for (int x = -2; x <= 2; x++)
        {
            set(writes, x, -324, 40, NORTH_STAIR);
        }
        buildIkariStation(writes);
        buildFuyutsukiStation(writes);
        set(writes, MARKER_X, MARKER_Y, MARKER_Z, RED);

        // A restrained luminous crown marks the single central authority
        // point without enclosing the commanders or breaking the sightline.
        for (int y = -321; y <= -313; y++)
        {
            BlockState rib = Math.floorMod(y + 321, 3) == 0
                    ? LIGHT : STRUCTURE;
            set(writes, -13, y, 43, rib);
            set(writes, 13, y, 43, rib);
        }
        for (int x = -13; x <= 13; x++)
        {
            set(writes, x, -313, 43,
                    Math.floorMod(x + 13, 4) == 0 ? LIGHT : BLACK);
            if (Math.abs(x) <= 7)
            {
                set(writes, x, -315, 38,
                        Math.floorMod(x + 7, 4) == 0 ? ORANGE : STRUCTURE);
            }
        }
        for (int y = -318; y <= -313; y++)
        {
            set(writes, 0, y, 44,
                    Math.floorMod(y + 318, 2) == 0 ? RED : LIGHT);
        }

        // The front remains visually suspended. Load is returned to four
        // rear/side piers, leaving the central look-down volume unobstructed.
        supportPier(writes, -17, -15, 41, 43);
        supportPier(writes, 15, 17, 41, 43);
        supportPier(writes, -14, -12, 30, 32);
        supportPier(writes, 12, 14, 30, 32);
    }

    private static void buildIkariStation(List<RelativeWrite> writes)
    {
        // Hidden plinth extensions directly carry the overhanging desk and
        // arm consoles; the visible upper outline stays narrow.
        for (int x = -6; x <= 6; x++)
        {
            for (int z = 29; z <= 31; z++)
            {
                set(writes, x, -324, z, BLACK);
            }
        }
        for (int z = 32; z <= 36; z++)
        {
            set(writes, -6, -324, z, BLACK);
            set(writes, 6, -324, z, BLACK);
        }
        for (int x = -6; x <= 6; x++)
        {
            for (int z = 29; z <= 31; z++)
            {
                set(writes, x, -323, z,
                        x == 0 && z == 30 ? CONSOLE
                                : (Math.abs(x) == 6 ? RED : DARK));
            }
        }
        for (int z = 32; z <= 36; z++)
        {
            set(writes, -6, -323, z, z == 34 ? LIGHT : DARK);
            set(writes, -5, -323, z, z == 34 ? ORANGE : BLACK);
            set(writes, 5, -323, z, z == 34 ? ORANGE : BLACK);
            set(writes, 6, -323, z, z == 34 ? LIGHT : DARK);
        }
        set(writes, 0, -323, 35, COMMAND_SEAT);
        set(writes, -1, -323, 35, DARK);
        set(writes, 1, -323, 35, DARK);
        set(writes, -1, -323, 36, BLACK);
        set(writes, 0, -322, 36, RED);
        set(writes, 0, -321, 36, BLACK);
        set(writes, 1, -323, 36, BLACK);
    }

    private static void buildFuyutsukiStation(List<RelativeWrite> writes)
    {
        // One compact right/rear deputy station: same command deck, visibly
        // subordinate to the raised centre rather than a mirrored co-throne.
        for (int x = 7; x <= 15; x++)
        {
            for (int z = 35; z <= 37; z++)
            {
                set(writes, x, -324, z,
                        x == 11 && z == 36 ? CONSOLE
                                : (x == 15 ? ORANGE : DARK));
            }
        }
        set(writes, 11, -324, 40, COMMAND_SEAT);
        set(writes, 10, -324, 40, DARK);
        set(writes, 12, -324, 40, DARK);
        set(writes, 11, -323, 41, STRUCTURE);
        set(writes, 11, -322, 41, BLACK);
    }

    private static void buildTaperedCommandDeck(
            List<RelativeWrite> writes)
    {
        for (int z = 26; z <= 45; z++)
        {
            int halfWidth = z < 30 ? 9 : z < 40 ? 15 : 20;
            for (int x = -halfWidth; x <= halfWidth; x++)
            {
                boolean rim = Math.abs(x) == halfWidth
                        || z == 26 || z == 45;
                BlockState state = rim ? ORANGE : DARK;
                if (Math.abs(x) <= 1)
                {
                    state = Math.floorMod(z, 4) == 0 ? LIGHT : WHITE;
                }
                set(writes, x, -325, z, state);
            }
        }
    }

    private static void supportPier(List<RelativeWrite> writes,
                                    int minX, int maxX,
                                    int minZ, int maxZ)
    {
        for (int y = -340; y <= -326; y++)
        {
            for (int z = minZ; z <= maxZ; z++)
            {
                for (int x = minX; x <= maxX; x++)
                {
                    boolean lightBand = Math.floorMod(y + 340, 6) == 0
                            && (x == minX || x == maxX);
                    set(writes, x, y, z,
                            lightBand ? LIGHT : STRUCTURE);
                }
            }
        }
    }

    private static void buildOperatorTerraces(List<RelativeWrite> writes)
    {
        // Three named operator pods, not nine generic chairs. Their open
        // spacing preserves the original-series reporting hierarchy and a
        // continuous view from the commander down to the tactical well.
        for (int centre : new int[] {-18, 0, 18})
        {
            for (int x = centre - 5; x <= centre + 5; x++)
            {
                for (int z = 14; z <= 23; z++)
                {
                    boolean rim = x == centre - 5 || x == centre + 5
                            || z == 14 || z == 23;
                    set(writes, x, -340, z, rim ? ORANGE : BLACK);
                }
            }
            for (int x = centre - 4; x <= centre + 4; x++)
            {
                set(writes, x, -339, 15,
                        x == centre ? CONSOLE : DARK);
                if (Math.abs(x - centre) <= 3)
                {
                    set(writes, x, -339, 16, GLASS);
                }
            }
            set(writes, centre, -339, 21, OPERATOR_SEAT);
            set(writes, centre - 1, -339, 21, DARK);
            set(writes, centre + 1, -339, 21, DARK);
            set(writes, centre - 4, -339, 18, LIGHT);
            set(writes, centre + 4, -339, 18, LIGHT);
            for (int x = centre - 2; x <= centre + 2; x++)
            {
                set(writes, x, -340, 24, NORTH_STAIR);
            }
        }

        // Shared amber data spine makes the stations one command floor rather
        // than three unrelated cubicles.
        for (int x = -29; x <= 29; x++)
        {
            set(writes, x, -341, 26,
                    Math.floorMod(x + 29, 6) == 0 ? LIGHT : ORANGE);
        }
    }

    private static void buildTacticalWellAccent(List<RelativeWrite> writes)
    {
        // Four slim pylons visually support the hovering tactical plane in the
        // open L0 well. They stop below it and never become a walkable shortcut.
        for (int x : new int[] {-12, 12})
        {
            for (int z : new int[] {-31, -17})
            {
                for (int y = -367; y <= -347; y++)
                {
                    set(writes, x, y, z,
                            Math.floorMod(y + 367, 6) == 0 ? ORANGE : BLACK);
                }
            }
        }
        for (int x = -12; x <= 12; x++)
        {
            set(writes, x, -347, -31,
                    Math.floorMod(x, 6) == 0 ? LIGHT : STRUCTURE);
            set(writes, x, -347, -17,
                    Math.floorMod(x, 6) == 0 ? LIGHT : STRUCTURE);
        }
    }

    private static void fill(List<RelativeWrite> writes,
                             int minX, int maxX,
                             int minY, int maxY,
                             int minZ, int maxZ,
                             BlockState state)
    {
        for (int y = minY; y <= maxY; y++)
        {
            for (int z = minZ; z <= maxZ; z++)
            {
                for (int x = minX; x <= maxX; x++)
                {
                    set(writes, x, y, z, state);
                }
            }
        }
    }

    private static void set(List<RelativeWrite> writes,
                            int x, int y, int z, BlockState state)
    {
        writes.add(new RelativeWrite(x, y, z, null, state));
    }

    private static void replace(List<RelativeWrite> writes,
                                int x, int y, int z,
                                Block expected, BlockState state)
    {
        writes.add(new RelativeWrite(x, y, z, expected, state));
    }

    private record RelativeWrite(int x, int y, int z,
                                 Block expected, BlockState state) {}

    private record PanelSpec(String id, double x, double y, double z,
                             float width, float height,
                             float yaw, float pitch,
                             BlockState state, int glow) {}

    private record LabelSpec(String id, double x, double y, double z,
                             float yaw, float pitch, float scale,
                             String text, ChatFormatting colour, int glow) {}

    private record SeatSpec(String id,
                            int blockX, int blockY, int blockZ,
                            double anchorX, double anchorY, double anchorZ,
                            float yaw, String messageKey) {}
}
