package com.projectseele.world;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;

import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Display;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.AttachFace;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** Surface command post which authorizes a stationary EVA's physical recovery. */
public final class Tokyo3RecoveryConsole
{
    public static final int CONTROL_COUNT = 3;

    private static final int CENTRE_Z = -30;
    private static final int HALF_WIDTH = 14;
    private static final int HALF_DEPTH = 8;
    private static final int HEIGHT = 8;
    private static final int CONTROL_Z = CENTRE_Z - 3;
    private static final int ACCESS_HALF_WIDTH = 3;
    private static final int ACCESS_HEIGHT = 6;
    private static final int SOUTH_ACCESS_END_Z = -60;
    private static final String LABEL_TAG_PREFIX =
            "projectseele.tokyo3_recovery.unit";
    private static final int UPDATE_CLIENTS = Block.UPDATE_CLIENTS;

    private Tokyo3RecoveryConsole() {}

    public static RecoveryConsoleAudit ensure(ServerLevel level, BlockPos cityOrigin)
    {
        if (CityLegacyOwnershipR48.inhibits(level, cityOrigin, "Tokyo3RecoveryConsole.ensure"))
            return inspect(level, cityOrigin);
        RecoveryConsoleAudit audit = inspect(level, cityOrigin);
        if (audit.valid())
        {
            return audit;
        }
        build(level, cityOrigin);
        return inspect(level, cityOrigin);
    }

    public static RecoveryConsoleAudit build(ServerLevel level, BlockPos cityOrigin)
    {
        if (CityLegacyOwnershipR48.inhibits(level, cityOrigin, "Tokyo3RecoveryConsole.build"))
            return inspect(level, cityOrigin);
        level.getChunkAt(cityOrigin.offset(0, 0, CENTRE_Z));
        for (int x = -HALF_WIDTH; x <= HALF_WIDTH; x++)
        {
            for (int z = CENTRE_Z - HALF_DEPTH;
                 z <= CENTRE_Z + HALF_DEPTH; z++)
            {
                boolean perimeter = Math.abs(x) == HALF_WIDTH
                        || z == CENTRE_Z - HALF_DEPTH
                        || z == CENTRE_Z + HALF_DEPTH;
                set(level, cityOrigin.offset(x, 0, z),
                        Math.floorMod(x + z, 7) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                set(level, cityOrigin.offset(x, HEIGHT, z),
                        Math.floorMod(x - z, 9) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.POLISHED_BLACKSTONE_BRICKS.defaultBlockState());
                for (int y = 1; y < HEIGHT; y++)
                {
                    BlockPos position = cityOrigin.offset(x, y, z);
                    boolean doorway = (z == CENTRE_Z + HALF_DEPTH
                            || z == CENTRE_Z - HALF_DEPTH)
                            && Math.abs(x) <= ACCESS_HALF_WIDTH && y <= 5;
                    if (!perimeter || doorway)
                    {
                        clear(level, position);
                    }
                    else
                    {
                        boolean window = y >= 2 && y <= 5
                                && (Math.floorMod(x + z, 5) != 0);
                        set(level, position, window
                                ? Blocks.GRAY_STAINED_GLASS.defaultBlockState()
                                : Blocks.POLISHED_BLACKSTONE_BRICKS.defaultBlockState());
                    }
                }
            }
        }

        // A continuous dais is laid before any pedestal or button. This is a
        // visual and structural invariant: no command control may float.
        for (int x = -9; x <= 9; x++)
        {
            for (int z = CONTROL_Z - 2; z <= CONTROL_Z + 2; z++)
            {
                set(level, cityOrigin.offset(x, 0, z),
                        Math.floorMod(x, 6) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.POLISHED_BLACKSTONE.defaultBlockState());
            }
        }

        BlockState button = Blocks.STONE_BUTTON.defaultBlockState()
                .setValue(ButtonBlock.FACE, AttachFace.FLOOR)
                .setValue(ButtonBlock.FACING, Direction.NORTH);
        for (int variant = 0; variant < CONTROL_COUNT; variant++)
        {
            BlockPos position = controlPosition(cityOrigin, variant);
            set(level, position.below(2),
                    Blocks.POLISHED_BLACKSTONE.defaultBlockState());
            set(level, position.below(), accent(variant));
            set(level, position, button);
            installLabel(level, cityOrigin, position, variant);
        }
        set(level, cityOrigin.offset(0, HEIGHT, CENTRE_Z),
                Blocks.BEACON.defaultBlockState());
        buildAccessCorridor(level, cityOrigin,
                CENTRE_Z + HALF_DEPTH + 1, -20);
        buildAccessCorridor(level, cityOrigin,
                CENTRE_Z - HALF_DEPTH - 1, SOUTH_ACCESS_END_Z);
        return inspect(level, cityOrigin);
    }

    public static RecoveryConsoleAudit inspect(ServerLevel level,
                                                BlockPos cityOrigin)
    {
        int controls = 0;
        int bases = 0;
        int supports = 0;
        int labels = 0;
        for (int variant = 0; variant < CONTROL_COUNT; variant++)
        {
            BlockPos position = controlPosition(cityOrigin, variant);
            if (level.getBlockState(position).is(Blocks.STONE_BUTTON))
            {
                controls++;
            }
            if (level.getBlockState(position.below()).equals(accent(variant)))
            {
                bases++;
            }
            if (level.getBlockState(position.below(2))
                    .is(Blocks.POLISHED_BLACKSTONE))
            {
                supports++;
            }
            if (labels(level, cityOrigin, variant).size() == 1)
            {
                labels++;
            }
        }
        boolean shell = level.getBlockState(cityOrigin.offset(
                -HALF_WIDTH, 0, CENTRE_Z - HALF_DEPTH))
                .is(Blocks.POLISHED_DEEPSLATE)
                && level.getBlockState(cityOrigin.offset(0, HEIGHT, CENTRE_Z))
                .is(Blocks.BEACON);
        int accessRoutes = 0;
        if (accessRouteClear(level, cityOrigin,
                CENTRE_Z + HALF_DEPTH + 1, -20))
        {
            accessRoutes++;
        }
        if (accessRouteClear(level, cityOrigin,
                CENTRE_Z - HALF_DEPTH - 1, SOUTH_ACCESS_END_Z))
        {
            accessRoutes++;
        }
        return new RecoveryConsoleAudit(shell && controls == CONTROL_COUNT
                && bases == CONTROL_COUNT && supports == CONTROL_COUNT
                && labels == CONTROL_COUNT && accessRoutes == 2,
                shell, controls, bases, supports, labels, accessRoutes);
    }

    public static BlockPos controlPosition(BlockPos cityOrigin, int variant)
    {
        if (variant < 0 || variant >= CONTROL_COUNT)
        {
            throw new IllegalArgumentException("Recovery control variant must be 0..2");
        }
        return cityOrigin.offset((variant - 1) * 6, 2, CONTROL_Z);
    }

    public static BlockPos entryPosition(BlockPos cityOrigin)
    {
        return cityOrigin.offset(0, 1, CENTRE_Z + HALF_DEPTH - 2);
    }

    /**
     * Builds a pressure-safe pedestrian link from the recovery room to a real
     * Tokyo-3 street. Both the short north airlock and the redundant south
     * egress are rebuilt last, so later district repairs cannot leave the
     * console as a sealed glass box.
     */
    private static void buildAccessCorridor(ServerLevel level,
                                            BlockPos cityOrigin,
                                            int startZ, int endZ)
    {
        int minimumZ = Math.min(startZ, endZ);
        int maximumZ = Math.max(startZ, endZ);
        for (int z = minimumZ; z <= maximumZ; z++)
        {
            for (int x = -ACCESS_HALF_WIDTH - 1;
                 x <= ACCESS_HALF_WIDTH + 1; x++)
            {
                BlockPos floor = cityOrigin.offset(x, 0, z);
                set(level, floor, Math.floorMod(z, 7) == 0
                        ? Blocks.SEA_LANTERN.defaultBlockState()
                        : Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                for (int y = 1; y < ACCESS_HEIGHT; y++)
                {
                    BlockPos position = floor.above(y);
                    if (Math.abs(x) <= ACCESS_HALF_WIDTH)
                    {
                        clear(level, position);
                    }
                    else
                    {
                        set(level, position, y >= 2 && y <= 4
                                ? Blocks.GRAY_STAINED_GLASS.defaultBlockState()
                                : Blocks.POLISHED_BLACKSTONE_BRICKS
                                        .defaultBlockState());
                    }
                }
                set(level, floor.above(ACCESS_HEIGHT),
                        Math.floorMod(x + z, 9) == 0
                                ? Blocks.SEA_LANTERN.defaultBlockState()
                                : Blocks.POLISHED_BLACKSTONE_BRICKS
                                        .defaultBlockState());
            }
        }

        // Open both ends completely; the side walls and lit lintel make the
        // threshold legible without using a collision-bearing iron door.
        for (int z : new int[] {startZ, endZ})
        {
            for (int x = -ACCESS_HALF_WIDTH; x <= ACCESS_HALF_WIDTH; x++)
            {
                for (int y = 1; y <= 5; y++)
                {
                    clear(level, cityOrigin.offset(x, y, z));
                }
            }
        }
    }

    private static boolean accessRouteClear(ServerLevel level,
                                            BlockPos cityOrigin,
                                            int startZ, int endZ)
    {
        int step = Integer.compare(endZ, startZ);
        for (int z = startZ; ; z += step)
        {
            BlockPos floor = cityOrigin.offset(0, 0, z);
            if (!level.getBlockState(floor)
                    .isFaceSturdy(level, floor, Direction.UP)
                    || !level.getBlockState(floor.above()).isAir()
                    || !level.getBlockState(floor.above(2)).isAir())
            {
                return false;
            }
            if (z == endZ)
            {
                return true;
            }
        }
    }
    private static void installLabel(ServerLevel level, BlockPos cityOrigin,
                                     BlockPos button, int variant)
    {
        List<Display.TextDisplay> matches = labels(level, cityOrigin, variant);
        Display.TextDisplay label;
        if (matches.isEmpty())
        {
            label = EntityType.TEXT_DISPLAY.create(level);
            if (label == null)
            {
                return;
            }
            label.addTag(LABEL_TAG_PREFIX + variant);
            label.setNoGravity(true);
            label.setInvulnerable(true);
            label.setSilent(true);
            level.addFreshEntity(label);
        }
        else
        {
            label = matches.get(0);
            for (int index = 1; index < matches.size(); index++)
            {
                matches.get(index).discard();
            }
        }
        Component caption = Component.literal(String.format(Locale.ROOT,
                "EVA-%02d\nRECOVERY", variant))
                .withStyle(colour(variant), ChatFormatting.BOLD);
        CompoundTag tag = label.saveWithoutId(new CompoundTag());
        tag.putString("text", Component.Serializer.toJson(caption));
        tag.putInt("line_width", 100);
        tag.putInt("background", 0xC0101418);
        tag.putBoolean("shadow", true);
        tag.putBoolean("see_through", false);
        tag.putString("alignment", "center");
        tag.putString("billboard", "vertical");
        tag.putFloat("view_range", 3.0F);
        tag.putFloat("width", 3.0F);
        tag.putFloat("height", 1.4F);
        CompoundTag brightness = new CompoundTag();
        brightness.putInt("block", 15);
        brightness.putInt("sky", 15);
        tag.put("brightness", brightness);
        label.load(tag);
        label.setPos(button.getX() + 0.5D, button.getY() + 1.3D,
                button.getZ() + 0.5D);
        label.setYRot(180.0F);
        label.setXRot(0.0F);
    }

    private static List<Display.TextDisplay> labels(ServerLevel level,
                                                    BlockPos cityOrigin,
                                                    int variant)
    {
        String wanted = LABEL_TAG_PREFIX + variant;
        AABB bounds = AABB.ofSize(Vec3.atCenterOf(cityOrigin.offset(
                0, 4, CENTRE_Z)), 40.0D, 16.0D, 30.0D);
        List<Display.TextDisplay> result = new ArrayList<>(
                level.getEntitiesOfClass(Display.TextDisplay.class, bounds,
                        display -> display.getTags().contains(wanted)));
        result.sort(Comparator.comparingInt(Entity::getId));
        return result;
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

    private static ChatFormatting colour(int variant)
    {
        return switch (variant)
        {
            case 0 -> ChatFormatting.GOLD;
            case 2 -> ChatFormatting.RED;
            default -> ChatFormatting.LIGHT_PURPLE;
        };
    }

    private static void clear(ServerLevel level, BlockPos position)
    {
        if (!level.getBlockState(position).isAir())
        {
            level.setBlock(position, Blocks.AIR.defaultBlockState(), UPDATE_CLIENTS);
            PerformanceCounters.recordWorldBlockWrites(1);
        }
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

    public record RecoveryConsoleAudit(boolean valid, boolean shell,
                                       int controls, int bases,
                                       int supports, int labels,
                                       int accessRoutes)
    {
        public String summary()
        {
            return String.format(Locale.ROOT,
                    "valid=%s shell=%s controls=%d/3 bases=%d/3 supports=%d/3 labels=%d/3 access=%d/2",
                    this.valid, this.shell, this.controls, this.bases,
                    this.supports, this.labels, this.accessRoutes);
        }
    }
}
