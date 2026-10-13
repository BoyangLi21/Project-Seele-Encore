package com.projectseele.world;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;

import com.projectseele.ProjectSeele;
import com.projectseele.visual.GeoFrontCommands;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Display;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.level.block.LadderBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.AttachFace;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/**
 * Walkable MAGI deep laboratory and three persistent maintenance controls.
 *
 * <p>The lab is west of the downloaded command module and below its lowest
 * imported floor.  It never overlaps the three launch shafts or Terminal
 * Dogma.  Each core's online state is encoded by a real status block, so a
 * maintenance isolation survives save/reload without another data store.</p>
 */
public final class MagiDeepLabBuilder
{
    public static final int LAB_FLOOR_Y = -27;
    public static final int LAB_CENTRE_X = -60;
    public static final int LAB_CENTRE_Z = 12;
    public static final int CAMERA_X = -44;
    public static final int CAMERA_Y = -21;
    public static final int CAMERA_Z = 12;

    private static final int UPDATE_CLIENTS = Block.UPDATE_CLIENTS;
    private static final int ENTRY_FLOOR_Y = 7;
    private static final int SHAFT_X = -38;
    private static final int SHAFT_Z = 12;
    private static final int SHAFT_TOP_Y = 7;
    private static final int SHAFT_BOTTOM_Y = LAB_FLOOR_Y;
    private static final int SHAFT_RADIUS = 4;
    private static final int LAB_MIN_X = -78;
    private static final int LAB_MAX_X = -42;
    private static final int LAB_MIN_Z = -6;
    private static final int LAB_MAX_Z = 30;
    private static final int LAB_CEILING_Y = -13;
    private static final int CONTROL_X = -46;
    private static final int CONTROL_Y = -25;
    private static final int[] CONTROL_Z = {2, 12, 22};
    private static final int[][] CORE_CENTRES = {
            {-72, 12}, {-60, 0}, {-60, 24}
    };
    private static final String[] CORE_IDS = {
            "melchior", "balthasar", "casper"
    };
    private static final String[] CORE_NAMES = {
            "MELCHIOR-1", "BALTHASAR-2", "CASPER-3"
    };
    private static final String LABEL_TAG_PREFIX =
            "projectseele.magi_maintenance.";

    private MagiDeepLabBuilder() {}

    public static MagiAudit build(ServerLevel level, BlockPos origin)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return inspect(level, origin);
        FacilityWorldPolicy.requireLegacyGenerationAllowed(
                level.getServer(), "MagiDeepLabBuilder.build");
        PerformanceCounters.recordBuilderCall();
        boolean[] online = new boolean[CORE_NAMES.length];
        for (int index = 0; index < online.length; index++)
        {
            BlockState previous = level.getBlockState(
                    statusPosition(origin, index));
            online[index] = !previous.is(Blocks.RED_CONCRETE);
        }

        buildLaboratoryShell(level, origin);
        buildPribnowBox(level, origin);
        for (int index = 0; index < CORE_NAMES.length; index++)
        {
            buildCore(level, origin, index, online[index]);
        }
        buildMaintenanceControls(level, origin);
        buildDescentShaft(level, origin);
        buildPhysicalAccess(level, origin);
        installLabels(level, origin);
        return inspect(level, origin);
    }

    /**
     * Loads only the chunks which own the three persistent MAGI labels, then
     * restores that entity-only presentation layer.  Saved TextDisplays are
     * not visible to an entity query until their chunks have entered the
     * ServerLevel entity manager; treating that transient state as structural
     * damage would otherwise rebuild the entire GeoFront on every login.
     */
    public static MagiAudit repairRuntimeLabels(ServerLevel level,
                                                BlockPos origin)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return inspect(level, origin);
        if (FacilityWorldPolicy.isS20Rebuild(level.getServer()))
        {
            return inspect(level, origin);
        }
        PerformanceCounters.recordRepairCall();
        for (int index = 0; index < CORE_NAMES.length; index++)
        {
            BlockPos control = controlPosition(origin, index);
            level.getChunk(control.getX() >> 4, control.getZ() >> 4);
        }
        if (!level.players().isEmpty())
        {
            installLabels(level, origin);
        }
        return inspect(level, origin);
    }

    /** Restores missing cosmetic labels only while the deep lab is active. */
    public static void tick(MinecraftServer server)
    {
        if (NervLegacyGenerationGuardR52.retired(server)) return;
        if (FacilityWorldPolicy.isS20Rebuild(server))
        {
            return;
        }
        ServerLevel level = server.getLevel(GeoFrontCommands.GEOFRONT);
        if (level == null || level.players().isEmpty())
        {
            return;
        }
        BlockPos origin = IntegratedNervMapBuilder.GEOFRONT_ORIGIN;
        Vec3 labCentre = Vec3.atCenterOf(origin.offset(
                LAB_CENTRE_X, LAB_FLOOR_Y + 5, LAB_CENTRE_Z));
        boolean occupied = level.players().stream().anyMatch(
                player -> player.position().distanceToSqr(labCentre)
                        <= 96.0D * 96.0D);
        if (!occupied)
        {
            return;
        }
        for (int index = 0; index < CORE_NAMES.length; index++)
        {
            if (!level.hasChunkAt(controlPosition(origin, index)))
            {
                return;
            }
        }
        if (countLabelEntities(level, origin) != CORE_NAMES.length)
        {
            installLabels(level, origin);
        }
    }

    public static MagiAudit inspect(ServerLevel level, BlockPos origin)
    {
        boolean physicalAccess = walkable(level,
                origin.offset(-30, ENTRY_FLOOR_Y, SHAFT_Z))
                && walkable(level, origin.offset(-43, LAB_FLOOR_Y, SHAFT_Z));
        int ladders = 0;
        for (int y = SHAFT_BOTTOM_Y + 1; y <= SHAFT_TOP_Y + 1; y++)
        {
            if (level.getBlockState(origin.offset(
                    SHAFT_X - 3, y, SHAFT_Z)).is(Blocks.LADDER))
            {
                ladders++;
            }
        }
        boolean shaft = ladders == SHAFT_TOP_Y - SHAFT_BOTTOM_Y + 1
                && level.getBlockState(origin.offset(
                SHAFT_X, SHAFT_BOTTOM_Y, SHAFT_Z)).is(Blocks.LODESTONE);
        boolean roomShell = level.getBlockState(origin.offset(
                LAB_MIN_X, LAB_FLOOR_Y + 4, LAB_MIN_Z + 6))
                .is(Blocks.DEEPSLATE_TILES)
                && level.getBlockState(origin.offset(
                LAB_CENTRE_X, LAB_CEILING_Y, LAB_CENTRE_Z))
                .is(Blocks.IRON_BLOCK);
        boolean pribnowBox = level.getBlockState(origin.offset(
                LAB_CENTRE_X, LAB_FLOOR_Y + 4, LAB_CENTRE_Z))
                .is(Blocks.AMETHYST_BLOCK)
                && level.getBlockState(origin.offset(
                LAB_CENTRE_X + 4, LAB_FLOOR_Y + 6, LAB_CENTRE_Z))
                .is(Blocks.TINTED_GLASS);
        int cores = 0;
        int onlineCores = 0;
        int controls = 0;
        for (int index = 0; index < CORE_NAMES.length; index++)
        {
            BlockState status = level.getBlockState(
                    statusPosition(origin, index));
            if (status.is(Blocks.LIME_CONCRETE)
                    || status.is(Blocks.RED_CONCRETE))
            {
                cores++;
            }
            if (status.is(Blocks.LIME_CONCRETE))
            {
                onlineCores++;
            }
            if (level.getBlockState(controlPosition(origin, index))
                    .is(Blocks.STONE_BUTTON))
            {
                controls++;
            }
        }
        int labels = countLabels(level, origin);
        boolean valid = physicalAccess && shaft && roomShell && pribnowBox
                && cores == CORE_NAMES.length
                && controls == CORE_NAMES.length
                && labels == CORE_NAMES.length;
        return new MagiAudit(valid, physicalAccess, ladders, shaft,
                roomShell, pribnowBox, cores, controls, labels, onlineCores);
    }

    /** Handles only the three exact maintenance buttons. */
    public static boolean handleUse(ServerPlayer player, BlockPos position)
    {
        if (NervLegacyGenerationGuardR52.retired(player.serverLevel())) return false;
        if (FacilityWorldPolicy.isS20Rebuild(player.getServer()))
        {
            return false;
        }
        if (!player.serverLevel().dimension().equals(GeoFrontCommands.GEOFRONT))
        {
            return false;
        }
        BlockPos origin = IntegratedNervMapBuilder.GEOFRONT_ORIGIN;
        int index = controlAt(origin, position);
        if (index < 0)
        {
            return false;
        }

        ServerLevel level = player.serverLevel();
        BlockPos statusPosition = statusPosition(origin, index);
        boolean online = !level.getBlockState(statusPosition)
                .is(Blocks.LIME_CONCRETE);
        level.setBlock(statusPosition, online
                        ? Blocks.LIME_CONCRETE.defaultBlockState()
                        : Blocks.RED_CONCRETE.defaultBlockState(),
                UPDATE_CLIENTS);
        installLabels(level, origin);
        int consensus = onlineCount(level, origin);
        String result = online
                ? CORE_NAMES[index] + " ONLINE; MAGI consensus "
                + consensus + "/3."
                : CORE_NAMES[index] + " isolated for maintenance; MAGI consensus "
                + consensus + "/3.";
        player.displayClientMessage(Component.literal("[MAGI] " + result)
                .withStyle(consensus == 3
                        ? ChatFormatting.GREEN : ChatFormatting.GOLD), false);
        ProjectSeele.LOGGER.info(
                "MAGI maintenance action: player={} core={} online={} consensus={}/3 position={}",
                player.getGameProfile().getName(), CORE_IDS[index], online,
                consensus, position.toShortString());
        NervCommandTelemetry.install(level, origin);
        return true;
    }

    /**
     * Removes only the three retired deep-lab TextDisplay labels after R28.
     * The accepted MAGI presentation in Central Tactical Command uses other
     * tags and is deliberately outside this bounded query.
     */
    public static void retireS20DuplicatePresentation(MinecraftServer server)
    {
        if (NervLegacyGenerationGuardR52.retired(server)) return;
        if (!FacilityWorldPolicy.isR28Approved(server))
        {
            return;
        }
        ServerLevel level = server.getLevel(GeoFrontCommands.GEOFRONT);
        if (level == null || level.players().isEmpty())
        {
            return;
        }
        BlockPos origin = IntegratedNervMapBuilder.GEOFRONT_ORIGIN;
        Vec3 labCentre = Vec3.atCenterOf(origin.offset(
                LAB_CENTRE_X, LAB_FLOOR_Y + 6, LAB_CENTRE_Z));
        boolean nearby = level.players().stream().anyMatch(
                player -> player.position().distanceToSqr(labCentre)
                        <= 128.0D * 128.0D);
        if (!nearby)
        {
            return;
        }
        int removed = 0;
        for (String id : CORE_IDS)
        {
            for (Display.TextDisplay label : labels(
                    level, origin, LABEL_TAG_PREFIX + id))
            {
                label.discard();
                removed++;
            }
        }
        if (removed > 0)
        {
            ProjectSeele.LOGGER.info(
                    "R28 retired {} duplicate deep-MAGI labels", removed);
        }
    }

    public static int onlineCount(ServerLevel level, BlockPos origin)
    {
        int online = 0;
        for (int index = 0; index < CORE_NAMES.length; index++)
        {
            if (level.getBlockState(statusPosition(origin, index))
                    .is(Blocks.LIME_CONCRETE))
            {
                online++;
            }
        }
        return online;
    }

    public static String consensusLine(ServerLevel level, BlockPos origin)
    {
        int online = onlineCount(level, origin);
        return online == 3
                ? "MAGI CONSENSUS: 3/3 UNANIMOUS"
                : "MAGI DEGRADED: " + online + "/3 CORES ONLINE";
    }

    private static void buildLaboratoryShell(ServerLevel level, BlockPos origin)
    {
        for (int x = LAB_MIN_X; x <= LAB_MAX_X; x++)
        {
            for (int z = LAB_MIN_Z; z <= LAB_MAX_Z; z++)
            {
                for (int y = LAB_FLOOR_Y; y <= LAB_CEILING_Y; y++)
                {
                    BlockPos position = origin.offset(x, y, z);
                    if (y == LAB_FLOOR_Y)
                    {
                        BlockState floor = Math.floorMod(x + z, 7) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.POLISHED_BLACKSTONE.defaultBlockState();
                        set(level, position, floor);
                    }
                    else if (y == LAB_CEILING_Y)
                    {
                        set(level, position,
                                Math.floorMod(x * 3 + z, 11) == 0
                                        ? Blocks.SEA_LANTERN.defaultBlockState()
                                        : Blocks.IRON_BLOCK.defaultBlockState());
                    }
                    else if (x == LAB_MIN_X || x == LAB_MAX_X
                            || z == LAB_MIN_Z || z == LAB_MAX_Z)
                    {
                        set(level, position,
                                Math.floorMod(y - LAB_FLOOR_Y, 5) == 0
                                        ? Blocks.POLISHED_BASALT.defaultBlockState()
                                        : Blocks.DEEPSLATE_TILES.defaultBlockState());
                    }
                    else
                    {
                        clear(level, position);
                    }
                }
            }
        }

        // Orange cable trenches form a readable triangular MAGI bus.
        buildFloorLine(level, origin, -72, 12, -60, 12,
                Blocks.ORANGE_CONCRETE.defaultBlockState());
        buildFloorLine(level, origin, -60, 0, -60, 12,
                Blocks.ORANGE_CONCRETE.defaultBlockState());
        buildFloorLine(level, origin, -60, 24, -60, 12,
                Blocks.ORANGE_CONCRETE.defaultBlockState());
    }

    private static void buildPribnowBox(ServerLevel level, BlockPos origin)
    {
        for (int x = -4; x <= 4; x++)
        {
            for (int y = 1; y <= 9; y++)
            {
                for (int z = -4; z <= 4; z++)
                {
                    boolean shell = Math.abs(x) == 4 || y == 1 || y == 9
                            || Math.abs(z) == 4;
                    if (shell)
                    {
                        set(level, origin.offset(LAB_CENTRE_X + x,
                                LAB_FLOOR_Y + y, LAB_CENTRE_Z + z),
                                (Math.floorMod(x + y + z, 9) == 0)
                                        ? Blocks.CYAN_STAINED_GLASS.defaultBlockState()
                                        : Blocks.TINTED_GLASS.defaultBlockState());
                    }
                }
            }
        }
        for (int y = LAB_FLOOR_Y + 2; y <= LAB_FLOOR_Y + 8; y++)
        {
            set(level, origin.offset(LAB_CENTRE_X, y, LAB_CENTRE_Z),
                    y == LAB_FLOOR_Y + 4
                            ? Blocks.AMETHYST_BLOCK.defaultBlockState()
                            : Blocks.BUDDING_AMETHYST.defaultBlockState());
        }
        set(level, origin.offset(LAB_CENTRE_X, LAB_FLOOR_Y + 9,
                LAB_CENTRE_Z), Blocks.BEACON.defaultBlockState());
    }

    private static void buildCore(ServerLevel level, BlockPos origin,
                                  int index, boolean online)
    {
        int x = CORE_CENTRES[index][0];
        int z = CORE_CENTRES[index][1];
        BlockState body = switch (index)
        {
            case 0 -> Blocks.ORANGE_TERRACOTTA.defaultBlockState();
            case 1 -> Blocks.RED_TERRACOTTA.defaultBlockState();
            default -> Blocks.PURPLE_TERRACOTTA.defaultBlockState();
        };
        fillBox(level, origin, x - 3, x + 3, LAB_FLOOR_Y, LAB_FLOOR_Y,
                z - 3, z + 3, Blocks.POLISHED_DEEPSLATE.defaultBlockState());
        for (int y = LAB_FLOOR_Y + 1; y <= LAB_FLOOR_Y + 10; y++)
        {
            int half = (y == LAB_FLOOR_Y + 1
                    || y == LAB_FLOOR_Y + 10) ? 3 : 2;
            fillBox(level, origin, x - half, x + half, y, y,
                    z - half, z + half,
                    Math.floorMod(y - LAB_FLOOR_Y, 4) == 0
                            ? Blocks.IRON_BLOCK.defaultBlockState() : body);
        }
        set(level, origin.offset(x, LAB_FLOOR_Y + 11, z),
                Blocks.SEA_LANTERN.defaultBlockState());
        set(level, statusPosition(origin, index), online
                        ? Blocks.LIME_CONCRETE.defaultBlockState()
                        : Blocks.RED_CONCRETE.defaultBlockState());
    }

    private static void buildMaintenanceControls(ServerLevel level,
                                                 BlockPos origin)
    {
        BlockState button = Blocks.STONE_BUTTON.defaultBlockState()
                .setValue(ButtonBlock.FACE, AttachFace.FLOOR)
                .setValue(ButtonBlock.FACING, Direction.WEST);
        BlockState[] bases = {
                Blocks.ORANGE_CONCRETE.defaultBlockState(),
                Blocks.RED_CONCRETE.defaultBlockState(),
                Blocks.PURPLE_CONCRETE.defaultBlockState()
        };
        for (int index = 0; index < CORE_NAMES.length; index++)
        {
            BlockPos control = controlPosition(origin, index);
            set(level, control.below(2),
                    Blocks.POLISHED_BLACKSTONE.defaultBlockState());
            set(level, control.below(), bases[index]);
            set(level, control, button);
        }
    }

    private static void buildDescentShaft(ServerLevel level, BlockPos origin)
    {
        for (int y = SHAFT_BOTTOM_Y; y <= SHAFT_TOP_Y + 6; y++)
        {
            for (int x = -SHAFT_RADIUS; x <= SHAFT_RADIUS; x++)
            {
                for (int z = -SHAFT_RADIUS; z <= SHAFT_RADIUS; z++)
                {
                    BlockPos position = origin.offset(SHAFT_X + x, y,
                            SHAFT_Z + z);
                    if (y == SHAFT_BOTTOM_Y)
                    {
                        set(level, position,
                                Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                    }
                    else if (Math.abs(x) == SHAFT_RADIUS
                            || Math.abs(z) == SHAFT_RADIUS)
                    {
                        set(level, position,
                                Math.floorMod(y - SHAFT_BOTTOM_Y, 8) == 0
                                        ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                                        : Blocks.DEEPSLATE_TILES.defaultBlockState());
                    }
                    else
                    {
                        clear(level, position);
                    }
                }
            }
            if (Math.floorMod(y - SHAFT_BOTTOM_Y, 6) == 0)
            {
                set(level, origin.offset(SHAFT_X + SHAFT_RADIUS, y,
                        SHAFT_Z), Blocks.SEA_LANTERN.defaultBlockState());
            }
        }
        BlockState ladder = Blocks.LADDER.defaultBlockState()
                .setValue(LadderBlock.FACING, Direction.EAST);
        for (int y = SHAFT_BOTTOM_Y + 1; y <= SHAFT_TOP_Y + 1; y++)
        {
            set(level, origin.offset(SHAFT_X - 3, y, SHAFT_Z), ladder);
        }
        set(level, origin.offset(SHAFT_X, SHAFT_BOTTOM_Y, SHAFT_Z),
                Blocks.LODESTONE.defaultBlockState());
    }

    private static void buildPhysicalAccess(ServerLevel level, BlockPos origin)
    {
        // Upper corridor pierces the west wall of the operations centre and
        // ends at the shaft's east face.
        buildCorridorX(level, origin, -34, -23, ENTRY_FLOOR_Y,
                9, 15);
        // Open the shaft door without removing its structural corners.
        for (int y = ENTRY_FLOOR_Y + 1; y <= ENTRY_FLOOR_Y + 5; y++)
        {
            for (int z = 10; z <= 14; z++)
            {
                clear(level, origin.offset(-34, y, z));
            }
        }
        // Bottom doorway joins the shaft directly to the laboratory shell.
        for (int x = -42; x <= -41; x++)
        {
            for (int z = 9; z <= 15; z++)
            {
                set(level, origin.offset(x, LAB_FLOOR_Y, z),
                        Blocks.POLISHED_BLACKSTONE.defaultBlockState());
                for (int y = LAB_FLOOR_Y + 1;
                     y <= LAB_FLOOR_Y + 6; y++)
                {
                    // Preserve the complete bottom six ladder cells and their
                    // west backing column. The laboratory doorway remains
                    // four blocks wide on both sides of this central spine.
                    if (z == SHAFT_Z)
                    {
                        continue;
                    }
                    clear(level, origin.offset(x, y, z));
                }
            }
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
                        Math.floorMod(x, 5) < 2
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

    private static void buildFloorLine(ServerLevel level, BlockPos origin,
                                       int x0, int z0, int x1, int z1,
                                       BlockState state)
    {
        int steps = Math.max(Math.abs(x1 - x0), Math.abs(z1 - z0));
        for (int step = 0; step <= steps; step++)
        {
            double amount = steps == 0 ? 0.0D : step / (double) steps;
            int x = (int) Math.round(x0 + (x1 - x0) * amount);
            int z = (int) Math.round(z0 + (z1 - z0) * amount);
            set(level, origin.offset(x, LAB_FLOOR_Y, z), state);
        }
    }

    private static void installLabels(ServerLevel level, BlockPos origin)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        for (int index = 0; index < CORE_NAMES.length; index++)
        {
            String tagName = LABEL_TAG_PREFIX + CORE_IDS[index];
            List<Display.TextDisplay> matches = labels(level, origin, tagName);
            Display.TextDisplay label;
            boolean pendingAdd = false;
            if (matches.isEmpty())
            {
                label = EntityType.TEXT_DISPLAY.create(level);
                if (label == null)
                {
                    continue;
                }
                label.addTag(tagName);
                label.setNoGravity(true);
                label.setInvulnerable(true);
                label.setSilent(true);
                pendingAdd = true;
            }
            else
            {
                label = matches.get(0);
                for (int duplicate = 1; duplicate < matches.size(); duplicate++)
                {
                    matches.get(duplicate).discard();
                }
            }
            updateLabel(level, origin, label, index);
            if (pendingAdd)
            {
                level.addFreshEntity(label);
            }
        }
    }

    private static void updateLabel(ServerLevel level, BlockPos origin,
                                    Display.TextDisplay label, int index)
    {
        boolean online = level.getBlockState(statusPosition(origin, index))
                .is(Blocks.LIME_CONCRETE);
        Component text = Component.literal(CORE_NAMES[index] + "\n"
                + (online ? "ONLINE" : "MAINTENANCE"))
                .withStyle(online ? ChatFormatting.GREEN : ChatFormatting.RED,
                        ChatFormatting.BOLD);
        CompoundTag tag = label.saveWithoutId(new CompoundTag());
        tag.putString("text", Component.Serializer.toJson(text));
        tag.putInt("line_width", 150);
        tag.putInt("background", 0xC0101418);
        tag.putByte("text_opacity", (byte) -1);
        tag.putBoolean("shadow", true);
        tag.putBoolean("see_through", false);
        tag.putBoolean("default_background", false);
        tag.putString("alignment", "center");
        tag.putString("billboard", "vertical");
        tag.putFloat("view_range", 3.0F);
        tag.putFloat("width", 4.0F);
        tag.putFloat("height", 1.4F);
        tag.putInt("glow_color_override", online ? 0xFF20FF60 : 0xFFFF2020);
        CompoundTag brightness = new CompoundTag();
        brightness.putInt("block", 15);
        brightness.putInt("sky", 15);
        tag.put("brightness", brightness);
        label.load(tag);
        BlockPos control = controlPosition(origin, index);
        label.setPos(control.getX() + 0.5D, control.getY() + 1.35D,
                control.getZ() + 0.5D);
        label.setYRot(90.0F);
        label.setXRot(0.0F);
    }

    public static BlockPos controlPosition(BlockPos origin, int index)
    {
        requireIndex(index);
        return origin.offset(CONTROL_X, CONTROL_Y, CONTROL_Z[index]);
    }

    public static BlockPos statusPosition(BlockPos origin, int index)
    {
        requireIndex(index);
        return switch (index)
        {
            case 0 -> origin.offset(-69, LAB_FLOOR_Y + 6, 12);
            case 1 -> origin.offset(-60, LAB_FLOOR_Y + 6, 3);
            default -> origin.offset(-60, LAB_FLOOR_Y + 6, 21);
        };
    }

    private static int controlAt(BlockPos origin, BlockPos position)
    {
        for (int index = 0; index < CORE_NAMES.length; index++)
        {
            if (controlPosition(origin, index).equals(position))
            {
                return index;
            }
        }
        return -1;
    }

    private static int countLabels(ServerLevel level, BlockPos origin)
    {
        int count = 0;
        for (String id : CORE_IDS)
        {
            if (!labels(level, origin, LABEL_TAG_PREFIX + id).isEmpty())
            {
                count++;
            }
        }
        return count;
    }

    private static int countLabelEntities(ServerLevel level, BlockPos origin)
    {
        int count = 0;
        for (String id : CORE_IDS)
        {
            count += labels(level, origin, LABEL_TAG_PREFIX + id).size();
        }
        return count;
    }

    private static List<Display.TextDisplay> labels(ServerLevel level,
                                                    BlockPos origin,
                                                    String tag)
    {
        AABB bounds = AABB.ofSize(Vec3.atCenterOf(origin.offset(
                LAB_CENTRE_X, LAB_FLOOR_Y + 6, LAB_CENTRE_Z)),
                60.0D, 32.0D, 60.0D);
        List<Display.TextDisplay> result = new ArrayList<>(
                level.getEntitiesOfClass(Display.TextDisplay.class, bounds,
                        display -> display.getTags().contains(tag)));
        result.sort(Comparator.comparingInt(Entity::getId));
        return result;
    }

    private static boolean walkable(ServerLevel level, BlockPos floor)
    {
        return !level.getBlockState(floor).isAir()
                && level.getBlockState(floor.above()).isAir()
                && level.getBlockState(floor.above(2)).isAir();
    }

    private static void requireIndex(int index)
    {
        if (index < 0 || index >= CORE_NAMES.length)
        {
            throw new IllegalArgumentException("MAGI core index must be 0..2");
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

    private static void set(ServerLevel level, BlockPos position,
                            BlockState state)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        if (level.setBlock(position, state, UPDATE_CLIENTS))
        {
            PerformanceCounters.recordWorldBlockWrites(1);
        }
    }

    private static void clear(ServerLevel level, BlockPos position)
    {
        set(level, position, Blocks.AIR.defaultBlockState());
    }

    public record MagiAudit(boolean valid, boolean physicalAccess,
                            int ladders, boolean shaft, boolean roomShell,
                            boolean pribnowBox, int cores, int controls,
                            int labels, int onlineCores)
    {
        /** Text labels are cosmetic entities and may register one tick later. */
        public boolean runtimePhysicalValid()
        {
            return this.physicalAccess && this.shaft && this.roomShell
                    && this.pribnowBox && this.cores == CORE_NAMES.length
                    && this.controls == CORE_NAMES.length;
        }

        public String summary()
        {
            return String.format(Locale.ROOT,
                    "valid=%s physicalAccess=%s ladder=%d/%d shaft=%s room=%s "
                            + "pribnow=%s cores=%d/3 controls=%d/3 labels=%d/3 online=%d/3",
                    this.valid, this.physicalAccess, this.ladders,
                    SHAFT_TOP_Y - SHAFT_BOTTOM_Y + 1, this.shaft,
                    this.roomShell, this.pribnowBox, this.cores,
                    this.controls, this.labels, this.onlineCores);
        }
    }
}
